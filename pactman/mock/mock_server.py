import json
import logging
import queue
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from multiprocessing import Process, Queue

from .pact_request_handler import PactRequestHandler

_providers = {}


log = logging.getLogger(__name__)


def getMockServer(config):
    if config.provider_name not in _providers:
        _providers[config.provider_name] = Server(config)
    return _providers[config.provider_name]


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
                raise MockServer.Error(result['reason'])
            if result['status'] == 'failed':
                raise AssertionError(result['reason'])

    def terminate(self):
        self.process.terminate()


def run_server(config, interactions, results):
    httpd = MockServer(config, interactions, results)
    httpd.serve_forever()


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

    class Error(Exception):
        pass


class MockHTTPRequestHandler(BaseHTTPRequestHandler, PactRequestHandler):
    def __init__(self, request, client_address, server):
        self.response_status_code = None
        self.response_headers = {}
        self.response_body = None
        PactRequestHandler.__init__(self, server.config)
        BaseHTTPRequestHandler.__init__(self, request, client_address, server)

    def error_result(self, message, content='', status='error', status_code=500):
        self.server.outgoing_results.put({'status': status, 'reason': message})
        self.response_status_code = status_code
        self.response_headers = {'Content-Type': 'text/plain; charset=utf-8'}
        self.response_body = (content or message).encode('utf8')

    def run_request(self, method):
        try:
            self.body = None
            for header in self.headers:
                if header.lower() == 'content-length':
                    self.body = self.rfile.read(int(self.headers[header]))
            self.validate_request(method)
        except AssertionError as e:
            self.error_result(str(e))
        except Exception as e:
            self.error_result(f'Internal Error: {e}', traceback.format_exc())
        self.send_response(self.response_status_code)
        for header in self.response_headers:
            self.send_header(header, self.response_headers[header])
        self.end_headers()
        if self.response_body:
            self.wfile.write(self.response_body)

    def get_interaction(self, path):
        try:
            interaction = self.server.incoming_interactions.get(False)
        except queue.Empty:
            raise AssertionError(f'Request at {path} received but no interaction registered') from None
        return interaction

    def handle_success(self, interaction):
        self.server.outgoing_results.put({'status': 'success'})

    def handle_failure(self, reason):
        self.error_result(reason, status='failed', status_code=418)

    def respond_for_interaction(self, interaction):
        self.response_status_code = interaction['response']['status']
        if 'headers' in interaction['response']:
            self.response_headers.update(interaction['response']['headers'])
        if 'body' in interaction['response']:
            is_json = False
            for h in self.response_headers:
                if h.lower() == 'content-type':
                    is_json = self.response_headers[h].startswith('application/json')
                    break
            else:
                is_json = True
                self.response_headers['Content-Type'] = 'application/json; charset=utf-8'
            if is_json:
                self.response_body = json.dumps(interaction['response']['body']).encode('utf8')
            else:
                self.response_body = interaction['response']['body']

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
