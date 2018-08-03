import json
import logging
import os
import queue
import traceback
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from multiprocessing import Process, Queue
from pact_verifier.pact import RequestVerifier
from pact_verifier.result import Result

_providers = {}


log = logging.getLogger(__name__)


class Config:
    def __init__(self, consumer_name, provider_name, log_dir, pact_dir):
        self.consumer_name = consumer_name
        self.provider_name = provider_name
        self.log_dir = log_dir
        self.pact_dir = pact_dir
        self.port = self.allocate_port()
        filename = os.path.join(self.pact_dir, f'{self.consumer_name}-{self.provider_name}-pact.json')
        if os.path.exists(filename):
            os.remove(filename)

    PORT_NUMBER = 8150

    @classmethod
    def allocate_port(cls):
        cls.PORT_NUMBER += 5
        return cls.PORT_NUMBER


def getServer(consumer_name, provider_name, log_dir, pact_dir):
    if provider_name not in _providers:
        _providers[provider_name] = Server(Config(consumer_name, provider_name, log_dir, pact_dir))
    return _providers[provider_name]


class Server:
    def __init__(self, config):
        self.config = config
        self.interactions = Queue()
        self.results = Queue()
        self.process = Process(target=run_server, args=(config, self.interactions, self.results))
        self.process.start()

    def setup(self, interactions):
        for interaction in interactions:
            self.interactions.put_nowait(interaction)

    def verify(self):
        while not self.results.empty():
            result = self.results.get()
            if result['status'] == 'error':
                raise MockServerError(result['reason'])
            if result['status'] == 'failed':
                raise AssertionError(result['reason'])

    def terminate(self):
        self.process.terminate()


def run_server(config, interactions, results):
    httpd = MockServer(config, interactions, results, )
    httpd.serve_forever()


class MockServerError(Exception):
    pass


class MockServer(HTTPServer):
    def __init__(self, config, interactions, results):
        self.config = config
        self.incoming_interactions = interactions
        self.outgoing_results = results
        server_address = ('', config.port)
        super().__init__(server_address, MockHTTPRequestHandler)
        self.interactions = []
        self.log = logging.getLogger(__name__ + '.' + config.provider_name)
        self.log.addHandler(logging.FileHandler(f'{config.log_dir}/{config.provider_name}.log'))
        self.log.setLevel(logging.DEBUG)
        self.log.propagate = False


class MockPact:
    def __init__(self, provider_name):
        self.provider = provider_name
        # TODO: pact-python doesn't know how to define the spec level, so we're hard-coding to 3 for now
        self.version = dict(major=3)


class Request:
    def __init__(self, method, path, query, headers, body):
        self.method = method
        self.path = path
        self.query = query
        self.headers = headers
        self.body = body

    def json(self):
        return self.body


class RecordResult(Result):
    def start(self, interaction):
        super().start(interaction)

    def fail(self, message, path=None):
        self.success = self.FAIL
        self.reason = message
        return not message


class MockHTTPRequestHandler(BaseHTTPRequestHandler):
    def __init__(self, request, client_address, server):
        self.response_status_code = None
        self.response_headers = {}
        self.response_body = None
        super().__init__(request, client_address, server)

    def error_result(self, message, content='', status='error', status_code=500):
        self.server.outgoing_results.put({'status': status, 'reason': message})
        self.response_status_code = status_code
        self.response_headers = {'Content-Type': 'text/plain; charset=utf-8'}
        self.response_body = (content or message).encode('utf8')

    def run_request(self, method):
        try:
            self.validate_request(method)
        except Exception as e:
            self.error_result(f'Internal Error: {e}', traceback.format_exc())
        self.send_response(self.response_status_code)
        for header in self.response_headers:
            self.send_header(header, self.response_headers[header])
        self.end_headers()
        if self.response_body:
            self.wfile.write(self.response_body)

    def validate_request(self, method):
        url_parts = urllib.parse.urlparse(self.path)

        try:
            interaction = self.server.incoming_interactions.get(False)
        except queue.Empty:
            return self.error_result(f'Request at {url_parts.path} received but no interaction registered')
        import pprint
        print('Verifying interaction', pprint.pformat(interaction))

        # TODO: we make a pact here and below too in the JSON export...
        pact = MockPact(self.server.config.provider_name)
        # TODO: assuming JSON
        body = None
        for header in self.headers:
            if header.lower() == 'content-length':
                body = json.loads(self.rfile.read(int(self.headers[header])))

        request = Request(method, url_parts.path, url_parts.query, self.headers, body)
        result = RecordResult()
        RequestVerifier(pact, interaction['request'], result).verify(request)
        if not result.success:
            return self.error_result(result.reason, status='failed', status_code=418)
        self.server.outgoing_results.put({'status': 'success'})

        self.write_pact(interaction)

        self.response_status_code = interaction['response']['status']
        if 'headers' in interaction['response']:
            self.response_headers.update(interaction['response']['headers'])
        if 'body' in interaction['response']:
            if not any(h for h in self.headers if h[0].lower() == 'content-type'):
                self.response_headers['Content-Type'] = 'application/json; charset=utf-8'
            # TODO: assuming JSON
            self.response_body = json.dumps(interaction['response']['body']).encode('utf8')

    def write_pact(self, interaction):
        config = self.server.config
        filename = os.path.join(config.pact_dir, f'{config.consumer_name}-{config.provider_name}-pact.json')
        if os.path.exists(filename):
            with open(filename) as f:
                pact = json.load(f)
            for existing in pact['interactions']:
                if (existing['description'] == interaction['description']
                        and existing['provider_state'] == interaction['provider_state']):
                    # already got one of these...
                    # TODO: detect when the pacts differ
                    return
            pact['interactions'].append(interaction)
        else:
            pact = dict(
                consumer=config.consumer_name,
                provider=config.provider_name,
                interactions=[interaction],
                metadata=dict(pactSpecification=dict(version='3.0.0')),
            )

        with open(filename, 'w') as f:
            json.dump(pact, f, indent=2)

    def do_DELETE(self):
        self.run_request('DELETE')

    def do_GET(self):
        self.run_request('GET')

    def do_HEAD(self):
        self.run_request('HEAD')

    def do_POST(self):
        self.run_request('POST')

    def do_PUT(self):
        self.run_request('PUT')

    def log_message(self, format, *args):
        self.server.log.info("MockServer %s\n" % format % args)
