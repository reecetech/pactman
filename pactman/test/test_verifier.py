import json
import pathlib
from itertools import chain
from unittest.mock import Mock

import coreapi
import hal_codec
import pytest
import requests
import semver

from pactman.verifier.broker_pact import BrokerPact, BrokerPacts, pact_id
from pactman.verifier.result import Result
from pactman.verifier.verify import Interaction, RequestVerifier, ResponseVerifier


BASE_DIR = pathlib.Path(__file__).absolute().parents[0]


def all_testcases(path):
    for entry in path.iterdir():
        if entry.is_file() and entry.suffix == '.json':
            yield str(entry)
        elif entry.is_dir():
            yield from all_testcases(entry)


@pytest.fixture
def fake_interaction():
    return {
        'description': 'dummy',
        'request': {'method': 'GET', 'path': '/users-service/user/alex'},
        'response': {'headers': {}, 'status': 200}
    }


@pytest.fixture
def mock_pact():
    def create_mock(version):
        return Mock(provider='SpamProvider', consumer='SpamConsumer', version=semver.parse(version))
    return create_mock


@pytest.fixture
def mock_result():
    result = Result()
    result.fail = Mock(return_value=False)
    return result


def test_pact_id():
    assert pact_id(1) == repr(1)


@pytest.mark.parametrize('specname', ['pact-specification', 'pactSpecification'])
def test_pact_loading(monkeypatch, fake_interaction, specname):
    provider_hal = hal_codec._parse_document({
        '_links': {
            'pacts': [{'href': 'http://broker.example/consumer/1', 'name': 'SpamConsumer'}]
        }
    })
    pact_hal = hal_codec._parse_document({
        'provider': {'name': 'SpamProvider'},
        'consumer': {'name': 'SpamConsumer'},
        'interactions': [fake_interaction],
        'metadata': {specname: {'version': '2.0.0'}}
    })
    monkeypatch.setattr(coreapi.Client, 'get', Mock(return_value=provider_hal))
    monkeypatch.setattr(coreapi.Client, 'action', Mock(return_value=pact_hal))

    p = BrokerPacts('SpamProvider', 'http://broker.example/{}')
    assert p.pact_broker_url == 'http://broker.example/SpamProvider'
    coreapi.Client.get.assert_called_with('http://broker.example/SpamProvider')

    for e in p.consumers():
        assert str(e) == '<Pact consumer=SpamConsumer provider=SpamProvider>'
        assert e.provider == 'SpamProvider'
    coreapi.Client.action.assert_called_with(provider_hal, ['pacts', 'SpamConsumer'])

    for e in p.all_interactions():
        assert e.description == 'dummy'


def test_pact_publish(monkeypatch, fake_interaction):
    pact_hal = hal_codec._parse_document({
        'provider': {'name': 'SpamProvider'},
        'consumer': {'name': 'SpamConsumer'},
        'interactions': [fake_interaction],
        'metadata': {'pact-specification': {'version': '2.0.0'}}
    })
    monkeypatch.setattr(coreapi.Client, 'action', Mock(return_value=pact_hal))

    BrokerPact(pact_hal, Mock()).publish_result('1.0')
    coreapi.Client.action.assert_called_once()


def test_pact_file_loading(monkeypatch, fake_interaction):
    p = BrokerPact.load_file(str(BASE_DIR / 'testcases-version-3' / 'dummypact.json'))
    assert str(p) == '<Pact consumer=SpamConsumer provider=SpamProvider>'
    assert p.provider == 'SpamProvider'
    for e in p.interactions:
        assert e.description == 'dummy'


def test_interaction(monkeypatch, mock_pact, mock_result, fake_interaction):
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result)
    assert repr(i) == 'SpamConsumer:dummy'


def test_interaction_verify_get(monkeypatch, mock_pact, mock_result, fake_interaction):
    monkeypatch.setattr(requests, 'post', Mock())
    monkeypatch.setattr(requests, 'get', Mock())
    monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result)
    i.verify('http://provider.example/', 'http://provider.example/pact-setup/')

    requests.post.assert_not_called()
    requests.get.assert_called_with('http://provider.example/users-service/user/alex', headers={})
    i.response.verify.assert_called()


def test_interaction_verify_method_not_supported(monkeypatch, mock_pact, mock_result, fake_interaction):
    monkeypatch.setattr(requests, 'get', Mock())
    monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    fake_interaction['request']['method'] = 'FLEBBLE'
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result)
    i.verify('http://provider.example/', 'http://provider.example/pact-setup/')
    i.result.fail.assert_called_with("Request method FLEBBLE not implemented in verifier")
    i.response.verify.assert_not_called()


def test_interaction_verify_qs(monkeypatch, mock_pact, mock_result, fake_interaction):
    monkeypatch.setattr(requests, 'post', Mock())
    monkeypatch.setattr(requests, 'get', Mock())
    monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    fake_interaction['request']['query'] = 'a=b&c=d'
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result)
    i.verify('http://provider.example/', 'http://provider.example/pact-setup/')

    requests.get.assert_called_with(
        'http://provider.example/users-service/user/alex',
        params=dict(a=['b'], c=['d']),
        headers={},
    )
    i.response.verify.assert_called()


def test_interaction_verify_post(monkeypatch, mock_pact, mock_result, fake_interaction):
    monkeypatch.setattr(requests, 'post', Mock())
    monkeypatch.setattr(requests, 'get', Mock())
    monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    fake_interaction['request']['method'] = 'POST'
    fake_interaction['request']['body'] = 'spam'
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result)
    i.verify('http://provider.example/', 'http://provider.example/pact-setup/')

    requests.get.assert_not_called()
    requests.post.assert_called_with(
        'http://provider.example/users-service/user/alex',
        json='spam',
        headers={},
    )
    i.response.verify.assert_called()


def test_interaction_verify_post_unsupported_content_type(monkeypatch, mock_pact, mock_result, fake_interaction):
    monkeypatch.setattr(requests, 'post', Mock())
    monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    fake_interaction['request']['method'] = 'POST'
    fake_interaction['request']['headers'] = {'Content-Type': 'spam/ham'}
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result)
    i.verify('http://provider.example/', 'http://provider.example/pact-setup/')
    i.result.fail.assert_called_with("POST content type spam/ham not implemented in verifier")

    requests.post.assert_not_called()


def test_interaction_verify_delete(monkeypatch, mock_pact, mock_result):
    monkeypatch.setattr(requests, 'delete', Mock())
    monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    fake_interaction = {
        'description': 'dummy',
        'request': {'method': 'DELETE', 'path': '/diary-notes/diary-note/1'},
        'response': {'headers': {}, 'status': 200}
    }
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result)
    i.verify('http://provider.example/', 'http://provider.example/pact-setup/')

    requests.delete.assert_called_with('http://provider.example/diary-notes/diary-note/1', headers={})
    i.response.verify.assert_called()


def test_interaction_verify_put(monkeypatch, mock_pact, mock_result, fake_interaction):
    monkeypatch.setattr(requests, 'put', Mock())
    monkeypatch.setattr(requests, 'get', Mock())
    monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    fake_interaction['request']['method'] = 'PUT'
    fake_interaction['request']['body'] = 'spam'
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result)
    i.verify('http://provider.example/', 'http://provider.example/pact-setup/')

    requests.get.assert_not_called()
    requests.put.assert_called_with(
        'http://provider.example/users-service/user/alex',
        json='spam',
        headers={},
    )
    i.response.verify.assert_called()


def test_interaction_verify_put_unsupported_content_type(monkeypatch, mock_pact, mock_result, fake_interaction):
    monkeypatch.setattr(requests, 'put', Mock())
    monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    fake_interaction['request']['method'] = 'PUT'
    fake_interaction['request']['headers'] = {'Content-Type': 'spam/ham'}
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result)
    i.verify('http://provider.example/', 'http://provider.example/pact-setup/')
    i.result.fail.assert_called_with("PUT content type spam/ham not implemented in verifier")

    requests.put.assert_not_called()


def test_interaction_verify_patch(monkeypatch, mock_pact, mock_result, fake_interaction):
    monkeypatch.setattr(requests, 'patch', Mock())
    monkeypatch.setattr(requests, 'get', Mock())
    monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    fake_interaction['request']['method'] = 'PATCH'
    fake_interaction['request']['body'] = 'spam'
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result)
    i.verify('http://provider.example/', 'http://provider.example/pact-setup/')
    requests.get.assert_not_called()
    requests.patch.assert_called_with(
        'http://provider.example/users-service/user/alex',
        json='spam',
        headers={},
    )
    i.response.verify.assert_called()


def test_interaction_verify_patch_unsupported_content_type(monkeypatch, mock_pact, mock_result, fake_interaction):
    monkeypatch.setattr(requests, 'patch', Mock())
    monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    fake_interaction['request']['method'] = 'PATCH'
    fake_interaction['request']['headers'] = {'Content-Type': 'spam/ham'}
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result)
    i.verify('http://provider.example/', 'http://provider.example/pact-setup/')
    i.result.fail.assert_called_with("PATCH content type spam/ham not implemented in verifier")
    requests.patch.assert_not_called()


@pytest.mark.parametrize('method', ['GET', 'POST', 'DELETE', 'PUT', 'PATCH'])
def test_interaction_sends_headers(monkeypatch, mock_pact, mock_result, fake_interaction, method):
    headers = {'key1': 'value1'}
    requests_method = Mock()
    monkeypatch.setattr(requests, method.lower(), requests_method)
    monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    fake_interaction['request']['method'] = method
    fake_interaction['request']['body'] = 'body-data'
    fake_interaction['request']['headers'] = headers
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result)
    i.verify('http://provider.example/', 'http://provider.example/pact-setup/')
    request_kwargs = requests_method.call_args[1]
    assert request_kwargs["headers"] == headers


@pytest.mark.parametrize('option, arg', [('providerState', 'state'), ('providerStates', 'states')])
def test_interaction_verify_with_setup(monkeypatch, mock_pact, mock_result, fake_interaction, option, arg):
    monkeypatch.setattr(requests, 'post', Mock(return_value=Mock(status_code=200)))
    monkeypatch.setattr(requests, 'get', Mock())
    monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    fake_interaction[option] = 'some state'
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result)
    i.verify('http://provider.example/', 'http://provider.example/pact-setup/')

    requests.post.assert_called_with(
        'http://provider.example/pact-setup/',
        json={'provider': "SpamProvider", 'consumer': "SpamConsumer", arg: "some state"}
    )
    i.response.verify.assert_called()


@pytest.mark.parametrize('option', ['providerState', 'providerStates'])
def test_interaction_setup_fails(monkeypatch, mock_pact, mock_result, fake_interaction, option):
    monkeypatch.setattr(requests, 'post', Mock(return_value=Mock(status_code=400, text='fail')))
    monkeypatch.setattr(requests, 'get', Mock())
    monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    fake_interaction[option] = 'some state'
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result)
    i.verify('http://provider.example/', 'http://provider.example/pact-setup/')
    i.result.fail.assert_called_with("Invalid provider state 'some state'")


def test_interaction_setup_connection_fails(monkeypatch, mock_pact, mock_result, fake_interaction):
    monkeypatch.setattr(requests, 'post', Mock(side_effect=requests.exceptions.ConnectionError('barf')))
    monkeypatch.setattr(requests, 'get', Mock())
    # monkeypatch.setattr(ResponseVerifier, 'verify', Mock())
    fake_interaction['providerState'] = 'some state'
    i = Interaction(mock_pact('2.0.0'), fake_interaction, mock_result)
    i.set_up_state('http://provider.example/pact-setup/', 'state', 'some state')
    i.result.fail.assert_called_once()


def test_response_verifier(fake_interaction, mock_pact):
    fake_interaction['response']['body'] = dict(a='b', c=1)  # note: no rule for matching of c
    fake_interaction['response']['matchingRules'] = {
        '$.body.a': dict(match='type'),
    }
    fake_interaction['response']['headers'] = {'Content-Type': 'json-yeah'}
    r = ResponseVerifier(mock_pact('2.0.0'), fake_interaction['response'], Mock())
    r.verify(Mock(status_code=200, headers={'Content-Type': 'json-yeah'}, json=Mock(return_value=dict(a='b', c='c'))))


def test_build_matching_rules_ignores_rule_with_unknown_type(fake_interaction, mock_pact):
    fake_interaction['response']['matchingRules'] = {
        "$": {"match": "SPAM"},
        "$.body[*].*": {"match": "type"}
    }
    r = ResponseVerifier(mock_pact('2.0.0'), fake_interaction['response'], Mock())
    assert len(r.matching_rules) == 1


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
    'filename',
    all_testcases(BASE_DIR / 'pact-spec-version-1.1' / 'testcases' / 'response')
)
def test_version_1_1_response_testcases(filename, mock_pact, mock_result):
    with open(filename) as file:
        case = json.load(file)
        expected = coreapi.Object(case['expected'])
        rv = ResponseVerifier(mock_pact('1.1.0'), expected, mock_result)
        rv.verify(FakeResponse(case['actual']))
        success = not bool(rv.result.fail.call_count)
        assert case['match'] == success


@pytest.mark.parametrize(
    'filename',
    all_testcases(BASE_DIR / 'pact-spec-version-1.1' / 'testcases' / 'request')
)
def test_version_1_1_request_testcases(filename, mock_pact, mock_result):
    with open(filename) as file:
        case = json.load(file)
        expected = coreapi.Object(case['expected'])
        rv = RequestVerifier(mock_pact('1.1.0'), expected, mock_result)
        rv.verify(FakeRequest(case['actual']))
        success = not bool(rv.result.fail.call_count)
        assert case['match'] == success


@pytest.mark.parametrize(
    'filename',
    all_testcases(BASE_DIR / 'pact-spec-version-2' / 'testcases' / 'response')
)
def test_version_2_response_testcases(filename, mock_pact, mock_result):
    if filename.endswith(' xml.json'):
        # some of the files don't declare the damned content-type!
        raise pytest.skip('XML content type not supported')
    with open(filename) as file:
        case = json.load(file)
        if case['expected'].get('headers', {}).get('Content-Type', "") == 'application/xml':
            raise pytest.skip('XML content type not supported')
        expected = coreapi.Object(case['expected'])
        rv = ResponseVerifier(mock_pact('2.0.0'), expected, mock_result)
        rv.verify(FakeResponse(case['actual']))
        success = not bool(rv.result.fail.call_count)
        assert case['match'] == success


@pytest.mark.parametrize(
    'filename',
    all_testcases(BASE_DIR / 'pact-spec-version-2' / 'testcases' / 'request')
)
def test_version_2_request_testcases(filename, mock_pact, mock_result):
    with open(filename) as file:
        case = json.load(file)
        if case['expected'].get('headers', {}).get('Content-Type', "") == 'application/xml':
            raise pytest.skip('XML content type not supported')
        expected = coreapi.Object(case['expected'])
        rv = RequestVerifier(mock_pact('2.0.0'), expected, mock_result)
        rv.verify(FakeRequest(case['actual']))
        success = not bool(rv.result.fail.call_count)
        assert case['match'] == success


@pytest.mark.parametrize(
    'filename',
    all_testcases(BASE_DIR / 'pact-spec-version-3' / 'testcases' / 'request')
)
def test_version_3_request_testcases(filename, mock_pact, mock_result):
    with open(filename) as file:
        case = json.load(file)
        if case['expected'].get('headers', {}).get('Content-Type', "") == 'application/xml':
            raise pytest.skip('XML content type not supported')
        expected = coreapi.Object(case['expected'])
        rv = RequestVerifier(mock_pact('3.0.0'), expected, mock_result)
        rv.verify(FakeRequest(case['actual']))
        success = not bool(rv.result.fail.call_count)
        assert case['match'] == success


@pytest.mark.parametrize(
    'filename',
    all_testcases(BASE_DIR / 'pact-spec-version-3' / 'testcases' / 'response')
)
def test_version_3_response_testcases(filename, mock_pact, mock_result):
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
        expected = coreapi.Object(case['expected'])
        rv = ResponseVerifier(mock_pact('3.0.0'), expected, mock_result)
        rv.verify(FakeResponse(case['actual']))
        success = not bool(rv.result.fail.call_count)
        assert case['match'] == success


@pytest.mark.parametrize(
    'filename, verifier, result',
    chain(
        ((t, RequestVerifier, FakeRequest) for t in all_testcases(BASE_DIR / 'testcases-version-3' / 'request')),
        ((t, ResponseVerifier, FakeResponse) for t in all_testcases(BASE_DIR / 'testcases-version-3' / 'response'))
    )
)
def test_local_version_3_testcases(filename, verifier, result, mock_pact, mock_result):
    with open(filename) as file:
        case = json.load(file)
        rv = verifier(mock_pact('3.0.0'), case['expected'], mock_result)
        rv.verify(result(case['actual']))
        success = not bool(rv.result.fail.call_count)
        assert case['match'] == success
