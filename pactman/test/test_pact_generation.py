import json
import os
import requests
from unittest.mock import Mock, mock_open, patch

import pactman.mock.pact
import pytest
import semver
from pactman.mock.consumer import Consumer
from pactman.mock.pact import Pact
from pactman.mock.pact_request_handler import PactRequestHandler, PactVersionConflict
from pactman.mock.provider import Provider


@pytest.fixture
def mock_pact(monkeypatch):
    def f(file_write_mode=None, version='2.0.0'):
        monkeypatch.setattr(Pact, "allocate_port", Mock())
        monkeypatch.setattr(os, "remove", Mock())
        monkeypatch.setattr(os.path, "exists", Mock(return_value=True))
        log_dir = "/tmp/a"
        pact_dir = "/tmp/pact"
        return Pact(Consumer("CONSUMER"), Provider("PROVIDER"), log_dir=log_dir, pact_dir=pact_dir, version=version,
                    file_write_mode=file_write_mode)
    return f


@pytest.mark.parametrize("file_write_mode", [None, "overwrite"])
def test_pact_init(monkeypatch, file_write_mode, mock_pact):
    monkeypatch.setattr(pactman.mock.pact, 'ensure_pact_dir', Mock(return_value=True))
    mock_pact = mock_pact(file_write_mode)
    mock_pact.pact_filename()

    assert(mock_pact.consumer.name == "CONSUMER")
    assert(mock_pact.provider.name == "PROVIDER")
    assert(mock_pact.log_dir == "/tmp/a")
    assert(mock_pact.version == "2.0.0")
    assert(mock_pact.semver == semver.parse("2.0.0"))
    mock_pact.allocate_port.assert_called_once_with()
    assert(mock_pact.BASE_PORT_NUMBER >= 8150)
    pactman.mock.pact.ensure_pact_dir.assert_called_once_with("/tmp/pact")
    if file_write_mode == "overwrite":
        os.path.exists.assert_called_once_with("/tmp/pact/CONSUMER-PROVIDER-pact.json")
        os.remove.assert_called_once_with("/tmp/pact/CONSUMER-PROVIDER-pact.json")
    else:
        os.path.exists.assert_not_called()
        os.remove.assert_not_called()


def test_config_pact_filename(mock_pact):
    mock_pact = mock_pact()
    res = mock_pact.pact_filename()
    assert(res == os.path.join(mock_pact.pact_dir, "CONSUMER-PROVIDER-pact.json"))


def test_ensure_pact_dir_when_exists(monkeypatch):
    monkeypatch.setattr(os.path, 'exists', Mock(side_effect=[True]))
    monkeypatch.setattr(os, 'mkdir', Mock())
    pactman.mock.pact.ensure_pact_dir('/tmp/pacts')
    os.mkdir.assert_not_called()


def test_ensure_pact_dir_when_parent_exists(monkeypatch):
    monkeypatch.setattr(os.path, 'exists', Mock(side_effect=[False, True]))
    monkeypatch.setattr(os, 'mkdir', Mock())
    pactman.mock.pact.ensure_pact_dir('/tmp/pacts')
    os.mkdir.assert_called_once_with('/tmp/pacts')


def generate_pact(version):
    return {
        "consumer": {"name": "CONSUMER"},
        "provider": {"name": "PROVIDER"},
        "interactions": [dict(description='spam')],
        "metadata": {
            'pactSpecification': {'version': version}
        }
    }


@pytest.mark.parametrize("version", ["2.0.0", "3.0.0"])
@patch("builtins.open", new_callable=mock_open, read_data="data")
def test_pact_request_handler_write_pact(mock_open, monkeypatch, mock_pact, version):
    monkeypatch.setattr(pactman.mock.pact, 'ensure_pact_dir', Mock(return_value=True))
    mock_pact = mock_pact(version=version)
    mock_pact.semver = semver.parse(version)
    my_pact = PactRequestHandler(mock_pact)
    os.path.exists.return_value = False
    with patch("json.dump", Mock()) as json_mock:
        my_pact.write_pact(dict(description='spam'))
        mock_open.assert_called_once_with(mock_pact.pact_filename(), "w")
        json_mock.assert_called_once_with(generate_pact(version), mock_open(), indent=2)


@patch("builtins.open", new_callable=mock_open, read_data="data")
def test_versions_are_consistent(mock_open, monkeypatch, mock_pact):
    monkeypatch.setattr(pactman.mock.pact, 'ensure_pact_dir', Mock(return_value=True))
    monkeypatch.setattr(json, 'dump', Mock())
    monkeypatch.setattr(json, 'load', lambda f: generate_pact('2.0.0'))

    # write the v2 pact
    pact = mock_pact()
    pact.semver = semver.parse(pact.version)
    hdlr = PactRequestHandler(pact)
    hdlr.write_pact(dict(description='spam'))

    # try to add the v3 pact
    pact = mock_pact(version='3.0.0')
    pact.semver = semver.parse(pact.version)
    hdlr = PactRequestHandler(pact)
    with pytest.raises(PactVersionConflict):
        hdlr.write_pact(dict(description='spam'))


@patch("builtins.open", new_callable=mock_open, read_data="data")
def test_immediate_pact_usage(mock_open):
    pact = Consumer('C').has_pact_with(Provider('P')) \
        .given("g").upon_receiving("r").with_request("get", "/", query={"foo": ["bar"]}).will_respond_with(200)
    with pact:
        requests.get(pact.uri, params={"foo": ["bar"]})

    # force a failure
    pact = Consumer('C').has_pact_with(Provider('P')) \
        .given("g").upon_receiving("r").with_request("get", "/", query={"bar": ["foo"]}).will_respond_with(200)
    with pytest.raises(AssertionError):
        with pact:
            requests.get(pact.uri, params={"foo": ["bar"]})

    # make sure mocking still works
    pact = Consumer('C').has_pact_with(Provider('P')) \
        .given("g").upon_receiving("r").with_request("get", "/", query={"bar": ["foo"]}).will_respond_with(400)
    with pact:
        requests.get(pact.uri, params={"bar": ["foo"]})
