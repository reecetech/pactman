import socket
from queue import Queue
from unittest.mock import Mock

import pytest
from pactman.mock import mock_server


def queue(*a):
    q = Queue()
    for value in a:
        q.put(value)
    return q


@pytest.mark.parametrize(
    "results,exception",
    [
        (queue(dict(status="error", reason="spam")), mock_server.MockServer.Error),
        (queue(dict(status="failed", reason="spam")), AssertionError),
    ],
)
def test_correct_result_assertion(mocker, results, exception):
    mocker.patch("pactman.mock.mock_server.Process", autospec=True)
    mocker.patch("pactman.mock.mock_server.SimpleQueue", autospec=True)
    s = mock_server.Server(Mock())
    s.results = results
    with pytest.raises(exception) as e:
        s.verify()
    assert "spam" in str(e.value)


@pytest.fixture
def unused_port():
    with socket.socket() as s:
        s.bind(("localhost", 0))
        _, port = s.getsockname()[:2]
        return port


@pytest.fixture
def a_mock_server(tmpdir, unused_port):
    from pactman import Consumer, Provider

    pact = Consumer("consumer").has_pact_with(
        Provider("provider"),
        pact_dir=str(tmpdir),
        log_dir=str(tmpdir),
        host_name="localhost",
        port=unused_port,
    )

    server = mock_server.Server(pact)
    yield server
    server.terminate()


def test_mockserver_is_connectable(a_mock_server):

    pact = a_mock_server.pact
    with socket.socket() as s:
        # Will fail with ConnectionRefusedError if the server is not already
        # bound and listening
        s.connect((pact.host_name, pact.port))
