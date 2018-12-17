import urllib3
from urllib3.response import HTTPResponse
from unittest.mock import Mock, call, patch
import urllib3.poolmanager

from pactman.mock.mock_urlopen import patcher


def test_patched_urlopen_calls_service_with_request_parameters():
    config = Mock(port=1234)
    mock_service = Mock(config=config, return_value=HTTPResponse())
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
