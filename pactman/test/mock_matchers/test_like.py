import pytest

from pactman import SomethingLike, Like
from pactman.mock.matchers import Matcher, Term


def test_is_something_like():
    assert SomethingLike is Like


def test_valid_types():
    types = [None, list(), dict(), 1, 1.0, 'string', 'unicode', Matcher()]

    for t in types:
        SomethingLike(t)


def test_invalid_types():
    with pytest.raises(AssertionError) as e:
        SomethingLike(set())

    assert 'matcher must be one of ' in str(e.value)


def test_basic_type():
    assert SomethingLike(123).ruby_protocol() == {'json_class': 'Pact::SomethingLike', 'contents': 123}


def test_complex_type():
    assert SomethingLike({'name': Term('.+', 'admin')}).ruby_protocol() == {
        'json_class': 'Pact::SomethingLike',
        'contents': {'name': {
            'json_class': 'Pact::Term',
            'data': {
                'matcher': {
                    'json_class': 'Regexp',
                    's': '.+',
                    'o': 0
                },
                'generate': 'admin'
            }
        }}
    }
