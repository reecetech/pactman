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


def test_logged_warning(monkeypatch):
    monkeypatch.setattr(result, 'log', Mock())
    r = result.LoggedResult()
    r.warn('message')
    result.log.warning.assert_called_once_with(' message')


def test_logged_fail_result_path(monkeypatch):
    monkeypatch.setattr(result, 'log', Mock())
    r = result.LoggedResult()
    r.fail('message', ['a', 0])
    result.log.warning.assert_called_once_with(' message')


def test_CaptureResult_for_passing_verification(capsys):
    r = result.CaptureResult()
    r.start(Mock())
    r.end()
    captured = capsys.readouterr()
    assert "PASSED" in captured.out


def test_CaptureResult_for_failing_verification(capsys):
    r = result.CaptureResult()
    r.start(Mock())
    r.fail("message1")
    r.end()
    captured = capsys.readouterr()
    assert "FAILED" in captured.out
    assert "message1" in captured.out


def test_CaptureResult_for_fail_with_path(capsys):
    r = result.CaptureResult()
    r.start(Mock())
    r.fail("message1", path=["x", "y"])
    r.end()
    captured = capsys.readouterr()
    assert "message1 at x.y" in captured.out


def test_CaptureResult_for_passing_verification_with_warning(capsys):
    r = result.CaptureResult()
    r.start(Mock())
    r.warn("message1")
    r.end()
    captured = capsys.readouterr()
    assert "PASSED" in captured.out
    assert "message1" in captured.out
