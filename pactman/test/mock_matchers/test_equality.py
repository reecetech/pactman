import pytest
import requests

from pactman import Equals, Consumer, Provider, Like


def test_valid_types():
    types = [None, list(), dict(), 1, 1.0, 'string', 'unicode']
    for t in types:
        Equals(t)


def test_invalid_types():
    with pytest.raises(AssertionError) as e:
        Equals(set())

    assert 'matcher must be one of ' in str(e.value)


def test_basic_type():
    assert Equals(123).generate_matching_rule_v3() == {'matchers': [{'match': 'equality'}]}


def test_mock_usage_pass_validation():
    pact = Consumer('C').has_pact_with(Provider('P')) \
        .given("g").upon_receiving("r").with_request("post", "/foo", body=Like({"a": "spam", "b": Equals("bee")})) \
        .will_respond_with(200)

    with pact:
        requests.post(pact.uri + '/foo', json={"a": "ham", "b": "bee"})


def test_mock_usage_fail_validation():
    pact = Consumer('C').has_pact_with(Provider('P')) \
        .given("g").upon_receiving("r").with_request("post", "/foo", body=Like({"a": "spam", "b": Equals("bee")})) \
        .will_respond_with(200)

    with pact:
        requests.post(pact.uri + '/foo', json={"a": "ham", "b": "wasp"})
