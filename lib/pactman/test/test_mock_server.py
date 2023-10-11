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
    s = mock_server.Server(Mock())
    s.results = results
    with pytest.raises(exception) as e:
        s.verify()
    assert "spam" in str(e.value)
