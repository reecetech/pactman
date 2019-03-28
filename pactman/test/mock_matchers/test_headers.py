import pytest
import requests

from pactman import Pact, Term


def test_regex_passes():
    pact = Pact('Consumer', 'Provider', file_write_mode='never').given('spam'). \
        with_request('GET', '/', headers={'Spam': Term(r'\w+', 'spam')}).will_respond_with(200)
    with pact:
        requests.get(pact.uri, headers={'Spam': 'ham'})


def test_regex_fails():
    pact = Pact('Consumer', 'Provider', file_write_mode='never').given('spam'). \
        with_request('GET', '/', headers={'Spam': Term(r'\w+', 'spam')}).will_respond_with(200)
    with pact:
        with pytest.raises(AssertionError):
            requests.get(pact.uri, headers={'Spam': '!@#$'})


def test_regex_passes_v3():
    pact = Pact('Consumer', 'Provider', file_write_mode='never', version='3.0.0').given('spam'). \
        with_request('GET', '/', headers={'Spam': Term(r'\w+', 'spam')}).will_respond_with(200)
    with pact:
        requests.get(pact.uri, headers={'Spam': 'ham'})


def test_regex_fails_v3():
    pact = Pact('Consumer', 'Provider', file_write_mode='never', version='3.0.0').given('spam'). \
        with_request('GET', '/', headers={'Spam': Term(r'\w+', 'spam')}).will_respond_with(200)
    with pact:
        with pytest.raises(AssertionError):
            requests.get(pact.uri, headers={'Spam': '!@#$'})
