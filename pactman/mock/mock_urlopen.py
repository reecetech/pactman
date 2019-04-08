import io
import logging

import urllib3.connectionpool
import urllib3.poolmanager
from urllib3.response import HTTPResponse

from .pact_request_handler import PactRequestHandler

_providers = {}


log = logging.getLogger(__name__)


class MockConnectionPool(urllib3.connectionpool.HTTPConnectionPool):
    mocks = {}

    @classmethod
    def add_mock(cls, mock):
        cls.mocks[mock.pact.port] = mock

    @classmethod
    def remove_mock(cls, mock):
        del cls.mocks[mock.pact.port]

    def urlopen(self, method, url, body=None, headers=None, *args, **kwargs):
        if self.port not in self.mocks:
            return super().urlopen(method, url, body, headers, *args, **kwargs)
        return self.mocks[self.port](method, url, body=body, headers=headers)


class MonkeyPatcher:
    def __init__(self):
        self.patched = False

    def add_service(self, handler):
        MockConnectionPool.add_mock(handler)
        if not self.patched:
            self.patch()

    def remove_service(self, handler):
        MockConnectionPool.remove_mock(handler)
        if not MockConnectionPool.mocks:
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
            body = self.handle_response_encoding(interaction['response'], headers)
        else:
            body = b''
        return HTTPResponse(body=io.BytesIO(body),
                            status=interaction['response']['status'],
                            preload_content=False,
                            headers=headers)
