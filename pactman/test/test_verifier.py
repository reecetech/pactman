import json
import pathlib
from itertools import chain
from unittest.mock import Mock

import requests

import pytest
import semver
from pactman.verifier.broker_pact import BrokerPact, BrokerPacts, pact_id
from pactman.verifier.result import Result
from pactman.verifier.verify import (Interaction, RequestVerifier,
                                     ResponseVerifier)
from restnavigator import Navigator

BASE_DIR = pathlib.Path(__file__).absolute().parents[0]


def all_testcases(path, version):
    for entry in path.iterdir():
        if entry.is_file() and entry.suffix == '.json':
            yield str(entry), version
        elif entry.is_dir():
            yield from all_testcases(entry, version)


@pytest.fixture
def fake_interaction():
    return {
        'description': 'dummy',
        'request': {'method': 'GET', 'path': '/users-service/user/alex'},
        'response': {'headers': {}, 'status': 200}
    }


@pytest.fixture
def fake_pact(fake_interaction):
    return {
        'provider': {'name': 'SpamProvider'},
        'consumer': {'name': 'SpamConsumer'},
        'interactions': [fake_interaction],
        'metadata': {'pact-specification': {'version': '2.0.0'}},
    }


@pytest.fixture
def mock_pact():
    def create_mock(version):
        return Mock(provider='SpamProvider', consumer='SpamConsumer', version=version,
                    semver=semver.parse(version))
    return create_mock


@pytest.fixture
def mock_result():
    result = Result()
    result.fail = Mock(return_value=False)
    result.warn = Mock()
    return result


@pytest.fixture
def mock_result_factory(mock_result):
    return Mock(return_value=mock_result)


def test_pact_id():
    assert pact_id(1) == repr(1)


def test_pact_loading(monkeypatch, fake_pact):
    p = BrokerPacts('SpamProvider', 'http://broker.example/')
    mock_pact = Mock(fetch=Mock(return_value=fake_pact))
    mock_provider = Mock(fetch=lambda: None, __getitem__=lambda s, k: [mock_pact])
    monkeypatch.setattr(Navigator, 'hal', lambda url, default_curie=None: {
        'latest-provider-pacts': lambda provider=None: mock_provider
    })

    for e in p.consumers():
        assert str(e) == 'Pact between consumer SpamConsumer and provider SpamProvider'
        assert e.provider == 'SpamProvider'

    for e in p.all_interactions():
        assert e.description == 'dummy'


def test_pact_publish_uses_interaction_result(fake_pact):
    result_factory = Mock(return_value=Mock(success=True))
    mock_result_publisher = Mock()
    broker_pact = {'publish-verification-results': mock_result_publisher}
    p = BrokerPact(fake_pact, result_factory, broker_pact)
    p.publish_result('1.0')
    mock_result_publisher.create.assert_called_once()
    payload = mock_result_publisher.create.call_args[0][0]
    assert payload == {"success": True, "providerApplicationVersion": "1.0"}


@pytest.mark.parametrize('first_success, second_success, combined_success', [
    (False, True, False),
    (True, False, False),
    (True, True, True),
])
def test_pact_publish_aggregates_interaction_results(
    fake_pact, fake_interaction, first_success, second_success, combined_success
):
    result_factory = Mock()
    fake_pact = {**fake_pact, 'interactions': [fake_interaction, fake_interaction]}
    result_factory.side_effect = [Mock(success=first_success), Mock(success=second_success)]
    mock_result_publisher = Mock()
    broker_pact = {'publish-verification-results': mock_result_publisher}
    BrokerPact(fake_pact, result_factory, broker_pact).publish_result('1.0')
    payload = mock_result_publisher.create.call_args[0][0]
    assert payload == {"success": combined_success, "providerApplicationVersion": "1.0"}


def test_pact_file_loading(fake_interaction):
    p = BrokerPact.load_file(str(BASE_DIR / 'testcases-version-3' / 'dummypact.json'))
    assert str(p) == 'Pact between consumer SpamConsumer and provider SpamProvider'
    assert p.provider == 'SpamProvider'
    for e in p.interactions:
        assert e.description == 'dummy'


def test_interaction(mock_pact, mock_result_factory, fake_interaction):
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result_factory)
    assert repr(i) == '<Interaction SpamConsumer:dummy>'


def test_interaction_verify_get(monkeypatch, mock_pact, mock_result_factory, fake_interaction):
    monkeypatch.setattr(requests, 'post', Mock())
    monkeypatch.setattr(requests, 'get', Mock())
    monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result_factory)
    i.verify('http://provider.example/', 'http://provider.example/pact-setup/')

    requests.post.assert_not_called()
    requests.get.assert_called_with('http://provider.example/users-service/user/alex', headers={})
    i.response.verify.assert_called()


def test_interaction_verify_method_not_supported(monkeypatch, mock_pact, mock_result_factory, fake_interaction):
    monkeypatch.setattr(requests, 'get', Mock())
    monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    fake_interaction['request']['method'] = 'FLEBBLE'
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result_factory)
    i.verify('http://provider.example/', 'http://provider.example/pact-setup/')
    i.result.fail.assert_called_with("Request method FLEBBLE not implemented in verifier")
    i.response.verify.assert_not_called()


def test_interaction_verify_qs(monkeypatch, mock_pact, mock_result_factory, fake_interaction):
    monkeypatch.setattr(requests, 'post', Mock())
    monkeypatch.setattr(requests, 'get', Mock())
    monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    fake_interaction['request']['query'] = 'a=b&c=d'
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result_factory)
    i.verify('http://provider.example/', 'http://provider.example/pact-setup/')

    requests.get.assert_called_with(
        'http://provider.example/users-service/user/alex',
        params=dict(a=['b'], c=['d']),
        headers={},
    )
    i.response.verify.assert_called()


def test_interaction_verify_post(monkeypatch, mock_pact, mock_result_factory, fake_interaction):
    monkeypatch.setattr(requests, 'post', Mock())
    monkeypatch.setattr(requests, 'get', Mock())
    monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    fake_interaction['request']['method'] = 'POST'
    fake_interaction['request']['body'] = 'spam'
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result_factory)
    i.verify('http://provider.example/', 'http://provider.example/pact-setup/')

    requests.get.assert_not_called()
    requests.post.assert_called_with(
        'http://provider.example/users-service/user/alex',
        json='spam',
        headers={},
    )
    i.response.verify.assert_called()


def test_interaction_verify_post_unsupported_content_type(
    monkeypatch, mock_pact, mock_result_factory, fake_interaction
):
    monkeypatch.setattr(requests, 'post', Mock())
    monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    fake_interaction['request']['method'] = 'POST'
    fake_interaction['request']['headers'] = {'Content-Type': 'spam/ham'}
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result_factory)
    i.verify('http://provider.example/', 'http://provider.example/pact-setup/')
    i.result.fail.assert_called_with("POST content type spam/ham not implemented in verifier")

    requests.post.assert_not_called()


def test_interaction_verify_delete(monkeypatch, mock_pact, mock_result_factory):
    monkeypatch.setattr(requests, 'delete', Mock())
    monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    fake_interaction = {
        'description': 'dummy',
        'request': {'method': 'DELETE', 'path': '/diary-notes/diary-note/1'},
        'response': {'headers': {}, 'status': 200}
    }
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result_factory)
    i.verify('http://provider.example/', 'http://provider.example/pact-setup/')

    requests.delete.assert_called_with('http://provider.example/diary-notes/diary-note/1', headers={})
    i.response.verify.assert_called()


def test_interaction_verify_put(monkeypatch, mock_pact, mock_result_factory, fake_interaction):
    monkeypatch.setattr(requests, 'put', Mock())
    monkeypatch.setattr(requests, 'get', Mock())
    monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    fake_interaction['request']['method'] = 'PUT'
    fake_interaction['request']['body'] = 'spam'
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result_factory)
    i.verify('http://provider.example/', 'http://provider.example/pact-setup/')

    requests.get.assert_not_called()
    requests.put.assert_called_with(
        'http://provider.example/users-service/user/alex',
        json='spam',
        headers={},
    )
    i.response.verify.assert_called()


def test_interaction_verify_put_unsupported_content_type(monkeypatch, mock_pact, mock_result_factory, fake_interaction):
    monkeypatch.setattr(requests, 'put', Mock())
    monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    fake_interaction['request']['method'] = 'PUT'
    fake_interaction['request']['headers'] = {'Content-Type': 'spam/ham'}
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result_factory)
    i.verify('http://provider.example/', 'http://provider.example/pact-setup/')
    i.result.fail.assert_called_with("PUT content type spam/ham not implemented in verifier")

    requests.put.assert_not_called()


def test_interaction_verify_patch(monkeypatch, mock_pact, mock_result_factory, fake_interaction):
    monkeypatch.setattr(requests, 'patch', Mock())
    monkeypatch.setattr(requests, 'get', Mock())
    monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    fake_interaction['request']['method'] = 'PATCH'
    fake_interaction['request']['body'] = 'spam'
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result_factory)
    i.verify('http://provider.example/', 'http://provider.example/pact-setup/')
    requests.get.assert_not_called()
    requests.patch.assert_called_with(
        'http://provider.example/users-service/user/alex',
        json='spam',
        headers={},
    )
    i.response.verify.assert_called()


def test_interaction_verify_patch_unsupported_content_type(
    monkeypatch, mock_pact, mock_result_factory, fake_interaction
):
    monkeypatch.setattr(requests, 'patch', Mock())
    monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    fake_interaction['request']['method'] = 'PATCH'
    fake_interaction['request']['headers'] = {'Content-Type': 'spam/ham'}
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result_factory)
    i.verify('http://provider.example/', 'http://provider.example/pact-setup/')
    i.result.fail.assert_called_with("PATCH content type spam/ham not implemented in verifier")
    requests.patch.assert_not_called()


@pytest.mark.parametrize('method', ['GET', 'POST', 'DELETE', 'PUT', 'PATCH'])
def test_interaction_sends_headers(monkeypatch, mock_pact, mock_result_factory, fake_interaction, method):
    headers = {'key1': 'value1'}
    requests_method = Mock()
    monkeypatch.setattr(requests, method.lower(), requests_method)
    monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    fake_interaction['request']['method'] = method
    fake_interaction['request']['body'] = 'body-data'
    fake_interaction['request']['headers'] = headers
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result_factory)
    i.verify('http://provider.example/', 'http://provider.example/pact-setup/')
    request_kwargs = requests_method.call_args[1]
    assert request_kwargs["headers"] == headers


@pytest.mark.parametrize('option, arg', [('providerState', 'state'), ('providerStates', 'states')])
def test_interaction_verify_with_setup(monkeypatch, mock_pact, mock_result_factory, fake_interaction, option, arg):
    monkeypatch.setattr(requests, 'post', Mock(return_value=Mock(status_code=200)))
    monkeypatch.setattr(requests, 'get', Mock())
    monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    fake_interaction[option] = 'some state'
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result_factory)
    i.verify('http://provider.example/', 'http://provider.example/pact-setup/')

    requests.post.assert_called_with(
        'http://provider.example/pact-setup/',
        json={'provider': "SpamProvider", 'consumer': "SpamConsumer", arg: "some state"}
    )
    i.response.verify.assert_called()


@pytest.mark.parametrize('option', ['providerState', 'providerStates'])
def test_interaction_setup_fails(monkeypatch, mock_pact, mock_result_factory, fake_interaction, option):
    monkeypatch.setattr(requests, 'post', Mock(return_value=Mock(status_code=400, text='fail')))
    monkeypatch.setattr(requests, 'get', Mock())
    monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    fake_interaction[option] = 'some state'
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result_factory)
    i.verify('http://provider.example/', 'http://provider.example/pact-setup/')
    i.result.warn.assert_called_with("Invalid provider state 'some state'")


def test_interaction_setup_connection_fails(monkeypatch, mock_pact, mock_result_factory, fake_interaction):
    monkeypatch.setattr(requests, 'post', Mock(side_effect=requests.exceptions.ConnectionError('barf')))
    monkeypatch.setattr(requests, 'get', Mock())
    # monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    fake_interaction['providerState'] = 'some state'
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result_factory)
    i.set_versioned_provider_state('http://provider.example/pact-setup/', 'state', 'some state')
    i.result.fail.assert_called_once()


def test_response_verifier(fake_interaction, mock_pact):
    fake_interaction['response']['body'] = dict(a='b', c=1)  # note: no rule for matching of c
    fake_interaction['response']['matchingRules'] = {
        '$.body.a': dict(match='type'),
    }
    fake_interaction['response']['headers'] = {'Content-Type': 'json-yeah'}
    r = ResponseVerifier(mock_pact('2.0.0'), fake_interaction['response'], Mock())
    r.verify(Mock(status_code=200, headers={'Content-Type': 'json-yeah'}, json=Mock(return_value=dict(a='b', c='c'))))


@pytest.mark.parametrize("interaction", [
    {'body': {'key1': 1}},
    {'body': {'key1': 1}, 'matchingRules': {'$.body.key1': {'match': 'type'}}},
])
def test_ResponseVerifier_reports_correct_message_when_key_missing(mock_pact, interaction):
    mock_result = Mock()
    r = ResponseVerifier(mock_pact('2.0.0'), interaction, mock_result)
    r.verify(FakeResponse({"body": {}}))
    mock_result.fail.assert_called_with("Response element 'key1' is missing", ['body'])


@pytest.mark.parametrize("interaction", [
    {'body': {'key1': 1}},
    {'body': {'key1': 1}, 'matchingRules': {'$.body.key1': {'match': 'type'}}},
])
def test_RequestVerifier_reports_correct_message_when_key_missing(mock_pact, interaction):
    mock_result = Mock()
    r = RequestVerifier(mock_pact('2.0.0'), interaction, mock_result)
    r.verify(FakeRequest({"body": {}}))
    mock_result.fail.assert_called_with("Request element 'key1' is missing", ['body'])


def test_ResponseVerifier_checks_for_missing_headers(mock_pact):
    interaction = {"headers": {"X-Custom-Header": "value1"}}
    mock_result = Mock()
    r = ResponseVerifier(mock_pact("2.0.0"), interaction, mock_result)
    assert r.verify(FakeResponse({"headers": {}})) is False
    mock_result.fail.assert_called_with("Response missing header 'X-Custom-Header'")


def test_RequestVerifier_checks_for_missing_headers(mock_pact):
    interaction = {"headers": {"X-Custom-Header": "value1"}}
    mock_result = Mock()
    r = RequestVerifier(mock_pact("2.0.0"), interaction, mock_result)
    assert r.verify(FakeRequest({"headers": {}})) is False
    mock_result.fail.assert_called_with("Request missing header 'X-Custom-Header'")


def test_provider_state_uses_custom_headers(monkeypatch, mock_pact, mock_result_factory, fake_interaction):
    fake_interaction['request']['headers'] = dict(request_header='value')
    monkeypatch.setattr(requests, 'post', Mock(return_value=Mock(status_code=200)))
    monkeypatch.setattr(requests, 'get', Mock())
    monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    fake_interaction['providerStates'] = 'some state'

    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result_factory)
    i.verify('http://provider.example/', 'http://provider.example/pact-setup/',
             extra_provider_headers={'some_header': 'some_header'})

    requests.post.assert_called_with(
        'http://provider.example/pact-setup/',
        json={'provider': "SpamProvider", 'consumer': "SpamConsumer", 'states': "some state"},
        headers={'some_header': "some_header"}
    )

    requests.get.assert_called_with('http://provider.example/users-service/user/alex',
                                    headers={'request_header': 'value', 'some_header': "some_header"})
    i.response.verify.assert_called()


class FakeResponse:
    status = 200
    body = None
    text = 'fake response text'

    def __init__(self, attrs):
        self.__dict__.update(attrs)
        self.status_code = self.status

    def __repr__(self):
        return f'<FakeResponse {self.__dict__}>'

    def json(self):
        return self.body


class FakeRequest:
    method = 'GET'
    body = None

    def __init__(self, attrs):
        self.__dict__.update(attrs)

    def __repr__(self):
        return f'<FakeRequest {self.__dict__}>'

    def json(self):
        return self.body


@pytest.mark.parametrize(
    'filename, version, verifier, response',
    chain(
        ((f, v, ResponseVerifier, FakeResponse) for f, v in chain(
            all_testcases(BASE_DIR / 'pact-spec-version-1.1' / 'testcases' / 'response', '1.1.0'),
            all_testcases(BASE_DIR / 'pact-spec-version-2' / 'testcases' / 'response', '2.0.0'),
            all_testcases(BASE_DIR / 'pact-spec-version-3' / 'testcases' / 'response', '3.0.0'),
            all_testcases(BASE_DIR / 'testcases-version-2' / 'response', '2.0.0'),
            all_testcases(BASE_DIR / 'testcases-version-3' / 'response', '3.0.0'),
        )),
        ((f, v, RequestVerifier, FakeRequest) for f, v in chain(
            all_testcases(BASE_DIR / 'pact-spec-version-1.1' / 'testcases' / 'request', '1.1.0'),
            all_testcases(BASE_DIR / 'pact-spec-version-2' / 'testcases' / 'request', '2.0.0'),
            all_testcases(BASE_DIR / 'pact-spec-version-3' / 'testcases' / 'request', '3.0.0'),
            all_testcases(BASE_DIR / 'testcases-version-2' / 'request', '2.0.0'),
            all_testcases(BASE_DIR / 'testcases-version-3' / 'request', '3.0.0'),
        ))
    )
)
def test_testcases(filename, version, verifier, response, mock_pact, mock_result):
    if filename.endswith(' xml.json'):
        # some of the files don't declare the damned content-type!
        raise pytest.skip('XML content type not supported')
    with open(filename) as file:
        try:
            case = json.load(file)
        except json.JSONDecodeError:
            raise pytest.skip('JSON test case mal-formed')
        if case['expected'].get('headers', {}).get('Content-Type', "") == 'application/xml':
            raise pytest.skip('XML content type not supported')
        rv = verifier(mock_pact(version), case['expected'], mock_result)
        result = rv.verify(response(case['actual']))
        success = not bool(rv.result.fail.call_count)
        assert result == success, 'fail() was not called for failure here'
        assert case['match'] == success
