"""Implement matching rules as defined in the pact specification version 2:

https://github.com/pact-foundation/pact-specification/tree/version-2
"""
import logging
import re
from collections import OrderedDict

import coreapi

from .paths import format_path


log = logging.getLogger(__name__)


class RuleFailed(Exception):
    def __init__(self, path, message):
        message = format_path(path) + ' ' + message
        super().__init__(message)


def split_path(path):
    """Split a JSON path from a pact matchingRule.

    Pact does not support the full JSON path expressions, only ones that match the following rules:

    * All paths start with a dollar ($), representing the root.
    * All path elements are either separated by periods (`.`) or use the JSON path bracket notation (square brackets
      and single quotes around the values: e.g. `['x.y']`), except array indices which use square brackets (`[]`).
      For elements where the value contains white space or non-alphanumeric characters, the JSON path bracket notation
      (`['']`) should be used.
    * The second element of the path is the http type that the matcher is applied to (e.g., $.body or $.header).
    * Path elements represent keys.
    * A star (*) can be used to match all keys of a map or all items of an array (one level only).

    Returns an iterator that has each path element as an item with array indexes converted to integers.
    """
    for elem in re.split(r'[\.\[]', path):
        if elem == '*]':
            yield '*'
        elif elem[0] in "'\"":
            yield elem[1:-2]
        elif elem[-1] == ']':
            yield int(elem[:-1])
        else:
            yield elem


def weight_path(spec_path, element_path):
    """Determine the weighting number for a matchingRule path spec applied to an actual element path from a
    response body.

    The response path should always start with ['$', 'body'] and contain object element names or array indexes.

    Weighting is calculated as:

    * The root node ($) is assigned the value 2.
    * Any path element that does not match is assigned the value 0.
    * Any property name that matches a path element is assigned the value 2.
    * Any array index that matches a path element is assigned the value 2.
    * Any star (*) that matches a property or array index is assigned the value 1.
    * Everything else is assigned the value 0.

    Return the numeric score.
    """
    if len(spec_path) != len(element_path):
        return 0
    score = 1
    for spec, element in zip(spec_path, element_path):
        if spec == element:
            score *= 2
        elif spec == '*':
            score *= 1
        else:
            return 0
    return score


def fold_type(obj):
    if type(obj) == coreapi.document.Object:
        return dict
    if type(obj) == OrderedDict:
        return dict
    if type(obj) == coreapi.document.Array:
        return list
    return type(obj)


class Matcher:
    def match_type(self, data, spec, path):
        log.debug(f'match_type {data!r} {spec!r} {path!r}')
        if type(spec) in (int, float):
            if type(data) not in (int, float):
                raise RuleFailed(path, f'not correct type ({nice_type(data)} is not {nice_type(spec)})')
        elif fold_type(spec) != fold_type(data):
            raise RuleFailed(path, f'not correct type ({nice_type(data)} is not {nice_type(spec)})')
        self.check_min(data, path)
        self.check_max(data, path)

    def match_regex(self, data, spec, path):
        # we have to cast data to str because Java treats all JSON values as strings and thus is happy to
        # specify a regex matcher for an integer (!!)
        log.debug(f'match_regex {data!r} {spec!r} {path!r}: {self.rule["regex"]}')
        if re.fullmatch(self.rule['regex'], str(data)) is None:
            raise RuleFailed(path, f'value {data!r} does not match regex {self.rule["regex"]}')

    def check_min(self, data, path):
        if 'min' not in self.rule:
            return
        if type(data) not in (dict, list, str):
            return
        if len(data) < self.rule['min']:
            raise RuleFailed(path, f'size {len(data)!r} is smaller than minimum size {self.rule["min"]}')

    def check_max(self, data, path):
        if 'max' not in self.rule:
            return
        if type(data) not in (dict, list, str):
            return
        if len(data) > self.rule['max']:
            raise RuleFailed(path, f'size {len(data)!r} is larger than maximum size {self.rule["max"]}')

    def match_integer(self, data, spec, path):
        log.debug(f'match_integer {data!r} {spec!r} {path!r}')
        if type(data) != int:
            raise RuleFailed(path, f'not correct type ({nice_type(data)} is not integer)')
        self.check_min(data, path)
        self.check_max(data, path)

    def match_decimal(self, data, spec, path):
        log.debug(f'match_decimal {data!r} {spec!r} {path!r}')
        if type(data) != float:
            raise RuleFailed(path, f'not correct type ({nice_type(data)} is not decimal)')
        self.check_min(data, path)
        self.check_max(data, path)

    def match_number(self, data, spec, path):
        log.debug(f'match_number {data!r} {spec!r} {path!r}')
        if type(data) not in (int, float):
            raise RuleFailed(path, f'not correct type ({nice_type(data)} is not number)')
        self.check_min(data, path)
        self.check_max(data, path)

    def match_equality(self, data, spec, path):
        log.debug(f'match_equality {data!r} {spec!r} {path!r}')
        if data != self.rule['value']:
            raise RuleFailed(path, f'value {data!r} does not equal expected {self.rule["value"]!r}')

    def match_include(self, data, spec, path):
        log.debug(f'match_include {data!r} {spec!r} {path!r}')
        if self.rule['value'] not in data:
            raise RuleFailed(path, f'value {data!r} does not contain expected value {self.rule["value"]!r}')

    def match_null(self, data, spec, path):
        log.debug(f'match_null {data!r} {spec!r} {path!r}')
        if data is not None:
            raise RuleFailed(path, f'value {data!r} is not null')


class MultipleMatchers(Matcher):
    def __init__(self, matchers, combine='AND'):
        self.matchers = matchers
        self.combine = combine

    def __call__(self, data, spec, path):
        log.debug(f'MultipleMatchers.__call__ {data!r} {spec!r} {path!r}')
        for rule in self.matchers:
            log.debug(f'... matching {rule}')
            matcher = getattr(self, 'match_' + rule.get('match', 'type'))
            self.rule = rule   # FIXME this is a hack to make the match methods work :/
            try:
                matcher(data, spec, path)
            except RuleFailed:
                if self.combine == 'AND':
                    raise
            else:
                if self.combine == 'OR':
                    return


class MatchingRule(Matcher):
    """Hold a JSONpath spec and a matchingRule rule and know how to test it.

    The valid rules are:

    `{"match": "regex", "regex": "\\d+"}`
      This executes a regular expression match against the string representation of a values.

    `{"match": "type"}`
       This executes a type based match against the values, that is, they are equal if they are the same type.

    `{"match": "type", "min": 2}`
      This executes a type based match against the values, that is, they are equal if they are the same type.
      In addition, if the values represent a collection, the length of the actual value is compared against the minimum.

    `{"match": "type", "max": 10}`
      This executes a type based match against the values, that is, they are equal if they are the same type.
      In addition, if the values represent a collection, the length of the actual value is compared against the maximum.

    Note that this code
    """
    def __init__(self, path, rule):
        log.debug(f'MatchingRule.__init__ {path!r} {rule!r}')
        self.path = path
        self.split_path = list(split_path(self.path))
        self.rule = rule
        if 'matchers' in rule:
            self.apply = MultipleMatchers(**rule)
        else:
            self.apply = getattr(self, 'match_' + rule.get('match', 'type'), None)
        if self.apply is None:
            raise RuleFailed(self.split_path, f'Invalid match type in contract {rule["match"]!r}')

    def __repr__(self):
        return f'<MatchingRule {self.path} {self.rule}>'

    def __str__(self):
        return f'Rule match by {self.rule} at {self.path}'

    def weight(self, element_path):
        """Given a matching rule path and an element path a blob, determine the weighting for the match.

        Return the weight, or 0 if there is no match.
        """
        return weight_path(self.split_path, ['$'] + element_path)


class PathMatchingRule(Matcher):
    """Variant matcher that has no jsonpath to match, is used for matching path in the interaction.
    """
    def __init__(self, rule):
        log.debug(f'PathMatchingRule.__init__ {rule!r}')
        self.rule = rule
        self.apply = MultipleMatchers(**rule)

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.rule}>'

    def weight(self, element_path):
        return 1


def rule_matchers(rules):
    matchers = {}
    if 'path' in rules:
        matchers['path'] = [PathMatchingRule(rules['path'])]
    for section in ['query', 'header', 'body']:
        if section in rules:
            matchers[section] = [MatchingRule(*i) for i in rules[section].items()]
    return matchers


def nice_type(obj):
    """Turn our Python type name into a JSON type name.
    """
    t = fold_type(obj)
    return {
        str: 'string',
        int: 'number',
        float: 'number',
        type(None): 'null',
        list: 'array',
        dict: 'object',
    }.get(t, str(t))
