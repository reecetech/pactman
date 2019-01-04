import pytest

from pactman.mock.matchers import generate_ruby_protocol, get_generated_values, EachLike, Like, Term, \
    get_matching_rules_v2, get_matching_rules_v3, Equals


def test_generated_value_unknown_type():
    with pytest.raises(ValueError):
        get_generated_values(set())


@pytest.mark.parametrize('input, output', [
    (None, None),
    (False, False),
    ('testing', 'testing'),
    (123, 123),
    (3.14, 3.14),
    ({'id': 123, 'info': {'active': False, 'user': 'admin'}}, {'id': 123, 'info': {'active': False, 'user': 'admin'}}),
    ([1, 123, 'sample'], [1, 123, 'sample']),
    (EachLike({'a': 1}), [{'a': 1}]),
    (EachLike({'a': 1}, minimum=5), [{'a': 1}] * 5),
    (Like(123), 123),
    (Term('[a-f0-9]+', 'abc123'), 'abc123'),
    (Equals(['a', Like('b')]), ['a', 'b']),
    ([EachLike({'username': Term('[a-zA-Z]+', 'firstlast'), 'id': Like(123)})],
     [[{'username': 'firstlast', 'id': 123}]]),
])
def test_generation(input, output):
    assert get_generated_values(input) == output


def test_matching_rules_v2_invald_type():
    with pytest.raises(ValueError):
        assert get_matching_rules_v2(set(), '*')


def test_matching_rules_v3_invald_type():
    with pytest.raises(ValueError):
        assert get_matching_rules_v3(set(), '*')


@pytest.mark.parametrize('input, output', [
    (None, None),
    ('testing', 'testing'),
    (123, 123),
    (3.14, 3.14),
    ({'id': 123, 'info': {'active': False, 'user': 'admin'}}, {'id': 123, 'info': {'active': False, 'user': 'admin'}}),
    ([1, 123, 'sample'], [1, 123, 'sample']),
    (EachLike({'a': 1}), {'json_class': 'Pact::ArrayLike', 'contents': {'a': 1}, 'min': 1}),
    (Like(123), {'json_class': 'Pact::SomethingLike', 'contents': 123}),
    (Term('[a-f0-9]+', 'abc123'), {'json_class': 'Pact::Term',
                                   'data': {'matcher': {'json_class': 'Regexp', 's': '[a-f0-9]+', 'o': 0},
                                            'generate': 'abc123'}}),
    ([EachLike({'username': Term('[a-zA-Z]+', 'firstlast'), 'id': Like(123)})], [
        {'contents': {
            'id': {
                'contents': 123,
                'json_class': 'Pact::SomethingLike'},
            'username': {
                'data': {
                    'generate': 'firstlast',
                    'matcher': {'json_class': 'Regexp', 'o': 0, 's': '[a-zA-Z]+'}},
                'json_class': 'Pact::Term'}},
            'json_class': 'Pact::ArrayLike',
            'min': 1}
    ]),
])
def test_from_term(input, output):
    assert generate_ruby_protocol(input) == output


def test_ruby_protocol_unknown_type():
    with pytest.raises(ValueError):
        generate_ruby_protocol(set())
