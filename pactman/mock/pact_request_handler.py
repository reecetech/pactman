import json
import os
import os.path
import urllib.parse

import semver

from ..verifier.verify import RequestVerifier
from ..verifier.result import Result


def ensure_pact_dir(pact_dir):
    if not os.path.exists(pact_dir):
        parent_dir = os.path.dirname(pact_dir)
        if not os.path.exists(parent_dir):
            raise ValueError(f'Pact destination directory {pact_dir} does not exist')
        os.mkdir(pact_dir)


class Config:
    def __init__(self, consumer_name, provider_name, log_dir, pact_dir, file_write_mode, version):
        self.consumer_name = consumer_name
        self.provider_name = provider_name
        self.log_dir = log_dir

        # ensure destination directory exists
        ensure_pact_dir(pact_dir)
        self.pact_dir = pact_dir

        self.file_write_mode = file_write_mode
        self.version = version
        self.semver = semver.parse(version)
        self.port = self.allocate_port()
        if file_write_mode == 'overwrite':
            filename = self.pact_filename()
            if os.path.exists(filename):
                os.remove(filename)

    PORT_NUMBER = 8150

    @classmethod
    def allocate_port(cls):
        cls.PORT_NUMBER += 5
        return cls.PORT_NUMBER

    def pact_filename(self):
        return os.path.join(self.pact_dir, f'{self.consumer_name}-{self.provider_name}-pact.json')


class MockPact:
    def __init__(self, config):
        self.provider = config.provider_name
        self.version = config.version
        self.semver = config.semver


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


class PactRequestHandler:
    def __init__(self, config):
        self.config = config

    def validate_request(self, method):
        url_parts = urllib.parse.urlparse(self.path)

        interaction = self.get_interaction(url_parts.path)

        pact = MockPact(self.config)
        if self.body:
            body = json.loads(self.body)
        else:
            body = ''

        request = Request(method, url_parts.path, url_parts.query, self.headers, body)
        result = RecordResult()
        RequestVerifier(pact, interaction['request'], result).verify(request)
        if not result.success:
            return self.handle_failure(result.reason)
        self.handle_success(interaction)
        self.write_pact(interaction)
        return self.respond_for_interaction(interaction)

    def get_interaction(self, path):
        raise NotImplementedError()

    def handle_success(self, interaction):
        raise NotImplementedError()

    def handle_failure(self, reason):
        raise NotImplementedError()

    def respond_for_interaction(self, reason):
        raise NotImplementedError()

    def write_pact(self, interaction):
        config = self.config
        filename = self.config.pact_filename()
        if config.semver["major"] >= 3:
            consumer_name = {"name": config.consumer_name}
            provider_name = {"name": config.provider_name}
            provider_state_key = 'providerStates'
        else:
            consumer_name = config.consumer_name
            provider_name = config.provider_name
            provider_state_key = 'providerState'

        if os.path.exists(filename):
            with open(filename) as f:
                pact = json.load(f)
            for existing in pact['interactions']:
                if (existing['description'] == interaction['description']
                        and existing[provider_state_key] == interaction[provider_state_key]):
                    # already got one of these...
                    assert existing == interaction, 'Existing "{existing["description"]}" pact given ' \
                        '"{existing[provider_state_key]}" exists with different request/response'.format(**locals())
                    return
            pact['interactions'].append(interaction)
        else:
            pact = dict(
                consumer=consumer_name,
                provider=provider_name,
                interactions=[interaction],
                metadata=dict(pactSpecification=dict(version=self.config.version)),
            )

        with open(filename, 'w') as f:
            json.dump(pact, f, indent=2)
