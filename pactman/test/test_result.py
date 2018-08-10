from unittest.mock import Mock

from pactman.verifier import result


def test_logged_start_result(monkeypatch):
    monkeypatch.setattr(result, 'log', Mock())
    r = result.LoggedResult()
    r.start(Mock())
    result.log.info.assert_called_once()


def test_logged_fail_result(monkeypatch):
    monkeypatch.setattr(result, 'log', Mock())
    r = result.LoggedResult()
    r.fail('message')
    result.log.warning.assert_called_once_with(' message')


def test_logged_fail_result_path(monkeypatch):
    monkeypatch.setattr(result, 'log', Mock())
    r = result.LoggedResult()
    r.fail('message', ['a', 0])
    result.log.warning.assert_called_once_with(' message')
