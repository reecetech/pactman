import pytest

from pactman import EachLike, Like, Term


def test_default_options():
    assert EachLike(1).ruby_protocol() == {'json_class': 'Pact::ArrayLike', 'contents': 1, 'min': 1}


def test_minimum():
    assert EachLike(1, minimum=2).ruby_protocol() == {'json_class': 'Pact::ArrayLike', 'contents': 1, 'min': 2}


def test_minimum_assertion_error():
    with pytest.raises(AssertionError) as e:
        EachLike(1, minimum=0)
    assert str(e.value) == 'Minimum must be greater than or equal to 1'


def test_nested_matchers():
    matcher = EachLike({'username': Term('[a-z]+', 'user'), 'id': Like(123)})
    assert matcher.ruby_protocol() == {
        'json_class': 'Pact::ArrayLike',
        'contents': {
            'username': {
                'json_class': 'Pact::Term',
                'data': {
                    'matcher': {
                        'json_class': 'Regexp',
                        's': '[a-z]+',
                        'o': 0},
                    'generate': 'user'}},
            'id': {
                'json_class': 'Pact::SomethingLike',
                'contents': 123}},
        'min': 1
    }
