import io
import json
import logging
import urllib3.connectionpool
import urllib3.poolmanager

from urllib3.response import HTTPResponse

from .pact_request_handler import PactRequestHandler

_providers = {}


log = logging.getLogger(__name__)


class MockPool:
    mocks = {}

    @classmethod
    def add_mock(cls, mock):
        cls.mocks[mock.config.port] = mock

    @classmethod
    def remove_mock(cls, mock):
        del cls.mocks[mock.config.port]


class MockConnectionPool(urllib3.connectionpool.HTTPConnectionPool, MockPool):
    def urlopen(self, method, url, body=None, headers=None, **spam):
        if self.port not in self.mocks:
            return super().urlopen(method, url, body=body, headers=headers, **spam)
        return self.mocks[self.port](method, url, body=body, headers=headers)


class MonkeyPatcher:
    def __init__(self):
        self.patched = False
        self.handlers = {}

    def add_service(self, handler):
        MockPool.add_mock(handler)
        if not self.patched:
            self.patch()

    def remove_service(self, handler):
        MockPool.remove_mock(handler)
        if not self.handlers:
            self.clear()

    def patch(self):
        urllib3.poolmanager.pool_classes_by_scheme["http"] = MockConnectionPool
        self.patched = True

    def clear(self):
        urllib3.poolmanager.pool_classes_by_scheme["http"] = urllib3.connectionpool.HTTPConnectionPool
        self.patched = False


patcher = MonkeyPatcher()


class MockURLOpenHandler(PactRequestHandler):
    def __init__(self, config):
        self.interactions = []
        super().__init__(config)
        patcher.add_service(self)

    def terminate(self):
        patcher.remove_service(self)

    def setup(self, interactions):
        self.interactions = interactions

    def verify(self):
        pass

    def __call__(self, method, url, redirect=True, headers=None, body=None, **kw):
        self.path = url
        self.headers = headers or {}
        self.body = body
        return self.validate_request(method)

    def get_interaction(self, path):
        try:
            interaction = self.interactions.pop()
        except IndexError:
            raise AssertionError(f'Request at {path} received but no interaction registered') from None
        return interaction

    def handle_failure(self, reason):
        raise AssertionError(reason)

    def handle_success(self, interaction):
        pass

    def respond_for_interaction(self, interaction):
        headers = {}
        if 'headers' in interaction['response']:
            headers.update(interaction['response']['headers'])
        if 'body' in interaction['response']:
            body = io.BytesIO(json.dumps(interaction['response']['body']).encode('utf8'))
            if not any(h for h in self.headers if h[0].lower() == 'content-type'):
                headers['Content-Type'] = 'application/json; charset=utf-8'
        else:
            body = io.BytesIO(b'')
        return HTTPResponse(body=body,
                            status=interaction['response']['status'],
                            preload_content=False,
                            headers=headers)
