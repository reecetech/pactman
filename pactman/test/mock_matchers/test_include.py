import pytest
import requests

from pactman import Consumer, Provider, Like, Includes


def test_valid_types():
    Includes('string', 'sample data')


@pytest.mark.parametrize('object', [None, list(), dict(), set(), 1, 1.0, b'bytes'])
def test_invalid_types(object):
    with pytest.raises(AssertionError) as e:
        Includes(object, 'sample data')

    assert 'matcher must be a string' in str(e.value)


def test_basic_type():
    assert Includes('spam', 'sample data').generate_matching_rule_v3() == \
           {'matchers': [{'match': 'include', 'value': 'spam'}]}


def test_v2_not_allowed():
    with pytest.raises(Includes.NotAllowed):
        Consumer('C').has_pact_with(Provider('P'), version='2.0.0') \
            .given("g").upon_receiving("r").with_request("post", "/foo", body=Includes("bee", 'been')) \
            .will_respond_with(200)


def test_mock_usage_pass_validation():
    pact = Consumer('C').has_pact_with(Provider('P'), version='3.0.0') \
        .given("g").upon_receiving("r").with_request("post", "/foo", body=Like({"a": "spam",
                                                                                "b": Includes("bee", 'been')})) \
        .will_respond_with(200)

    with pact:
        requests.post(pact.uri + '/foo', json={"a": "ham", "b": "has bee in it"})


def test_mock_usage_fail_validation():
    pact = Consumer('C').has_pact_with(Provider('P'), version='3.0.0') \
        .given("g").upon_receiving("r").with_request("post", "/foo", body=Like({"a": "spam",
                                                                                "b": Includes("bee", 'been')})) \
        .will_respond_with(200)

    with pytest.raises(AssertionError), pact:
        requests.post(pact.uri + '/foo', json={"a": "ham", "b": "wasp"})
