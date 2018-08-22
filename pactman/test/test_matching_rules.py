import collections
from unittest.mock import Mock

import pytest

from pactman.verifier.matching_rule import (
    Matcher,
    RuleFailed,
    fold_type,
    split_path,
    weight_path,
    MatchType, MatchNull, MatchInclude, MatchEquality, MatchNumber, MatchDecimal, MatchInteger, MatchRegex,
    InvalidMatcher, log)


def test_stringify():
    r = MatchType('$', {'match': 'type'})
    assert str(r) == "Rule match by {'match': 'type'} at $"
    assert repr(r) == "<MatchType $ {'match': 'type'}>"


def test_invalid_match_type(monkeypatch):
    monkeypatch.setattr(log, 'warning', Mock())
    assert isinstance(Matcher.get_matcher('$', {'match': 'spam'}), InvalidMatcher)
    log.warning.assert_called_once()


@pytest.mark.parametrize('path, weight', [
    ('$.body', 0),
    ('$.body.item1.level[0].id', 0),
    ('$.body.item1.level[1].id', 64),
    ('$.body.item1.level[*].id', 32),
    ('$.body.*.level[*].id', 16),
])
def test_weightings(path, weight):
    rule = Matcher(path, {'match': 'type'})
    assert rule.weight(['body', 'item1', 'level', 1, 'id']) == weight
    assert rule.weight(['body', 'item2', 'spam', 1, 'id']) == 0


@pytest.mark.parametrize('path, result', [
    ('$', ['$']),
    ('$.body', ['$', 'body']),
    ('$.body.item1', ['$', 'body', 'item1']),
    ('$.body.item2', ['$', 'body', 'item2']),
    ('$.header.item1', ['$', 'header', 'item1']),
    ('$.body.item1.level', ['$', 'body', 'item1', 'level']),
    ('$.body.item1.level[1]', ['$', 'body', 'item1', 'level', 1]),
    ('$.body.item1.level[1].id', ['$', 'body', 'item1', 'level', 1, 'id']),
    ('$.body.item1.level[1].name', ['$', 'body', 'item1', 'level', 1, 'name']),
    ('$.body.item1.level[2]', ['$', 'body', 'item1', 'level', 2]),
    ('$.body.item1.level[2].id', ['$', 'body', 'item1', 'level', 2, 'id']),
    ('$.body.item1.level[*].id', ['$', 'body', 'item1', 'level', '*', 'id']),
    ('$.body.*.level[*].id', ['$', 'body', '*', 'level', '*', 'id']),
])
def test_split_path(path, result):
    assert list(split_path(path)) == result


@pytest.mark.parametrize('path, other, result', [
    (['a'], ['b'], 0),
    (['*'], ['a'], 1),
    (['a', '*'], ['a', 'b'], 2),
    (['a', 'b'], ['a', 'b'], 4),
    (['a', 'b', 'c'], ['a', 'b'], 0),
    (['a', 'b'], ['a', 'b', 'c'], 0),
])
def test_weight_path(path, other, result):
    assert weight_path(path, other) == result


@pytest.mark.parametrize('data, spec', [
    (1, 1),
    (1, 1.0),
    (1.0, 1.0),
    (1.0, 1.0),
])
def test_numbers(data, spec):
    MatchType('$', dict(match='type')).apply(data, spec, ['a'])


def test_regex():
    MatchRegex('$', dict(match='regex', regex='\w+')).apply('spam', None, ['a'])


def test_regex_fail():
    with pytest.raises(RuleFailed):
        MatchRegex('$', dict(match='regex', regex='\W+')).apply('spam', None, ['a'])


def test_integer():
    MatchInteger('$', dict(match='integer')).apply(1, None, ['a'])


def test_integer_fail():
    with pytest.raises(RuleFailed):
        MatchInteger('$', dict(match='integer')).apply(1.0, None, ['a'])


def test_decimal():
    MatchDecimal('$', dict(match='decimal')).apply(1.0, None, ['a'])


def test_decimal_fail():
    with pytest.raises(RuleFailed):
        MatchDecimal('$', dict(match='decimal')).apply(1, None, ['a'])


@pytest.mark.parametrize('value', [1, 1.0])
def test_number(value):
    MatchNumber('$', dict(match='number')).apply(value, None, ['a'])


def test_number_fail():
    with pytest.raises(RuleFailed):
        MatchNumber('$', dict(match='number')).apply('spam', None, ['a'])


def test_equality():
    MatchEquality('$', dict(match='equality', value='spam')).apply('spam', None, ['a'])


def test_equality_fail():
    with pytest.raises(RuleFailed):
        MatchEquality('$', dict(match='equality', value='spam')).apply('ham', None, ['a'])


def test_include():
    MatchInclude('$', dict(match='include', value='spam')).apply('spammer', None, ['a'])


def test_include_fail():
    with pytest.raises(RuleFailed):
        MatchInclude('$', dict(match='include', value='spam')).apply('ham', None, ['a'])


def test_null():
    MatchNull('$', dict(match='null')).apply(None, None, ['a'])


def test_null_fail():
    with pytest.raises(RuleFailed):
        MatchNull('$', dict(match='null')).apply('ham', None, ['spam'])


def test_min():
    MatchType('$', dict(match='type', min=1)).apply(['spam'], ['a'], [])


def test_min_not_met():
    with pytest.raises(RuleFailed):
        MatchType('$', dict(match='type', min=2)).apply(['spam'], ['a', 'b'], ['spam'])


def test_min_ignored():
    MatchType('$', dict(match='type', min=1)).apply(0, 0, [])


def test_max():
    MatchType('$', dict(match='type', max=1)).apply(['spam'], ['a'], [])


def test_max_not_met():
    with pytest.raises(RuleFailed):
        MatchType('$', dict(match='type', max=2)).apply([1, 2, 3], [1, 2], ['spam'])


def test_max_ignored():
    MatchType('$', dict(match='type', max=1)).apply(0, 0, [])


@pytest.mark.parametrize('source, result', [
    ({}, dict),
    ([], list),
    (collections.OrderedDict(), dict),
])
def test_fold_type(source, result):
    assert fold_type(source) == result
