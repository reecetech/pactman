# -*- encoding: utf8 -*-
from unittest.mock import Mock, call, patch

import urllib3
import urllib3.poolmanager
from urllib3.response import HTTPResponse

from pactman.mock.mock_urlopen import MockURLOpenHandler, patcher


def test_patched_urlopen_calls_service_with_request_parameters():
    pact = Mock(port=1234)
    mock_service = Mock(pact=pact, return_value=HTTPResponse())
    try:
        patcher.add_service(mock_service)
        http = urllib3.PoolManager()
        response = http.request('GET', 'http://api.test:1234/path')
    finally:
        patcher.remove_service(mock_service)
    assert mock_service.call_args == call('GET', '/path', body=None, headers={})
    assert response is mock_service.return_value


@patch.object(urllib3.connectionpool.HTTPConnectionPool, 'urlopen')
def test_patched_urlopen_handles_many_positional_arguments(HTTPConnectionPool_urlopen):
    # urllib3 passes in up to 7 positional arguments to urlopen so we need to ensure
    # our mocked urlopen method handles these
    mock_service = Mock(config=Mock(port=1234), return_value=HTTPResponse())
    try:
        patcher.add_service(mock_service)
        pool = urllib3.poolmanager.pool_classes_by_scheme['http']('api.test', port=5678)
        pool.urlopen('POST', '/path', 'body1', {}, None, True, False)
    finally:
        patcher.remove_service(mock_service)
    expected_call = call('POST', '/path', 'body1', {}, None, True, False)
    assert HTTPConnectionPool_urlopen.call_args == expected_call


def test_urlopen_responder_handles_json_body():
    h = MockURLOpenHandler(Mock())

    interaction = dict(
        response=dict(body={'message': 'hello world'}, status=200)
    )
    r = h.respond_for_interaction(interaction)

    assert r.data == b'{"message": "hello world"}'
    assert r.headers['Content-Type'] == 'application/json; charset=UTF-8'


def test_urlopen_responder_handles_json_string_body():
    h = MockURLOpenHandler(Mock())

    interaction = dict(
        response=dict(body="hello world", status=200)
    )
    r = h.respond_for_interaction(interaction)

    assert r.data == b'"hello world"'
    assert r.headers['Content-Type'] == 'application/json; charset=UTF-8'


def test_urlopen_responder_handles_json_encoding():
    h = MockURLOpenHandler(Mock())

    interaction = dict(
        response=dict(
            headers={'content-type': 'application/json; charset=utf-8'},
            body="héllo world", status=200,
        ),
    )
    r = h.respond_for_interaction(interaction)

    assert r.data == b'"h\\u00e9llo world"'
    assert r.headers['Content-Type'] == 'application/json; charset=utf-8'


def test_urlopen_responder_handles_non_json_body():
    h = MockURLOpenHandler(Mock())

    interaction = dict(
        response=dict(
            headers={'content-type': 'text/plain; charset=utf-8'},
            body="héllo world".encode('utf-8'), status=200,
        ),
    )
    r = h.respond_for_interaction(interaction)

    assert r.data == b'h\xc3\xa9llo world'
    assert r.headers['Content-Type'] == 'text/plain; charset=utf-8'
