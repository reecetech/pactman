import pytest
import semver
from unittest.mock import Mock, mock_open, patch
import os
from pactman.mock import pact_request_handler
from pactman.mock.pact_request_handler import Config, MockPact, PactRequestHandler


@pytest.fixture
def config_patched(monkeypatch):
    monkeypatch.setattr(Config, "allocate_port", Mock())
    monkeypatch.setattr(os, "remove", Mock())
    monkeypatch.setattr(os.path, "exists", Mock())
    os.path.exists.return_value = True
    consumer_name = "CONSUMER"
    provider_name = "PROVIDER"
    log_dir = "/tmp/a"
    pact_dir = "/tmp/pact"
    version = "2.0.0"
    my_conf = Config(consumer_name, provider_name, log_dir, pact_dir, None, version)
    return my_conf


@pytest.mark.parametrize("file_write_mode", [None, "overwrite"])
def test_config_init(monkeypatch, file_write_mode):
    monkeypatch.setattr(Config, "allocate_port", Mock())
    monkeypatch.setattr(Config, "pact_filename", Mock())
    file_name = "/tmp/pact/JSON"
    Config.pact_filename.return_value = file_name
    monkeypatch.setattr(os, "remove", Mock())
    monkeypatch.setattr(os.path, "exists", Mock(return_value=True))
    monkeypatch.setattr(pact_request_handler, "ensure_pact_dir", Mock())

    consumer_name = "CONSUMER"
    provider_name = "PROVIDER"
    log_dir = "/tmp/a"
    pact_dir = "/tmp/pact"
    version = "2.0.0"
    my_conf = Config(consumer_name, provider_name, log_dir, pact_dir, file_write_mode, version)

    assert(my_conf.consumer_name == consumer_name)
    assert(my_conf.provider_name == provider_name)
    assert(my_conf.log_dir == log_dir)
    assert(my_conf.file_write_mode == file_write_mode)
    assert(my_conf.version == version)
    assert(my_conf.semver == semver.parse(version))
    my_conf.allocate_port.assert_called_once_with()
    assert(my_conf.PORT_NUMBER == 8150)
    pact_request_handler.ensure_pact_dir.assert_called_once_with(pact_dir)
    if file_write_mode == "overwrite":
        my_conf.pact_filename.assert_called_once_with()
        os.path.exists.assert_called_once_with(file_name)
        os.remove.assert_called_once_with(file_name)
    else:
        my_conf.pact_filename.assert_not_called()


def test_config_pact_filename(config_patched):
    res = config_patched.pact_filename()
    assert(res == os.path.join(config_patched.pact_dir, "CONSUMER-PROVIDER-pact.json"))


def test_ensure_pact_dir_when_exists(monkeypatch):
    monkeypatch.setattr(os.path, 'exists', Mock(side_effect=[True]))
    monkeypatch.setattr(os, 'mkdir', Mock())
    pact_request_handler.ensure_pact_dir('/tmp/pacts')
    os.mkdir.assert_not_called()


def test_ensure_pact_dir_when_parent_exists(monkeypatch):
    monkeypatch.setattr(os.path, 'exists', Mock(side_effect=[False, True]))
    monkeypatch.setattr(os, 'mkdir', Mock())
    pact_request_handler.ensure_pact_dir('/tmp/pacts')
    os.mkdir.assert_called_once_with('/tmp/pacts')


def test_mock_init(config_patched):
    my_pact = MockPact(config_patched)
    assert(my_pact.provider == config_patched.provider_name)
    assert(my_pact.version == config_patched.version)
    assert(my_pact.semver == config_patched.semver)


def test_pact_request_handler_init(config_patched):
    my_pact = PactRequestHandler(config_patched)
    assert(my_pact.config == config_patched)


@pytest.mark.parametrize("version", ["2.0.0", "3.0.0"])
@patch("builtins.open", new_callable=mock_open, read_data="data")
def test_pact_request_handler_write_pact(monkeypatch, config_patched, version):
    config_patched.version = version
    config_patched.semver = semver.parse(version)
    my_pact = PactRequestHandler(config_patched)
    os.path.exists.return_value = False
    expected_pact = {
        "consumer": "CONSUMER" if version[0] == "2" else {"name": "CONSUMER"},
        "provider": "PROVIDER" if version[0] == "2" else {"name": "PROVIDER"},
        "interactions": [None],
        "metadata": {
            'pactSpecification': {'version': version}
        }
    }
    with patch("json.dump", Mock()) as json_mock:
        my_pact.write_pact(None)
        open.assert_called_once_with(my_pact.config.pact_filename(), "w")
        json_mock.assert_called_once_with(expected_pact, open(), indent=2)
