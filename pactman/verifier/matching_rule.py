"""Implement matching rules as defined in the pact specification version 2:

https://github.com/pact-foundation/pact-specification/tree/version-2
"""
import logging
import re
from collections import OrderedDict, defaultdict

from .paths import format_path


log = logging.getLogger(__name__)


class RuleFailed(Exception):
    def __init__(self, path, message):
        if isinstance(path, list):
            path = format_path(path)
        message = path + ' ' + message
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

    Both paths are passed in as lists which represent the paths split per split_path()

    In spec version 2 paths should always start with ['$', 'body'] and contain object element names or array indexes.

    In spec version 3 the path "context" element (like 'body') is moved outside of the path, and the path contains
    just the elements inside the path. For bodies this always starts at the root '$', so the shortest body path is
    now ['$'].

    Weighting is calculated as:

    * The root node ($) is assigned the value 2.
    * Any path element that does not match is assigned the value 0.
    * Any property name that matches a path element is assigned the value 2.
    * Any array index that matches a path element is assigned the value 2.
    * Any star (*) that matches a property or array index is assigned the value 1.
    * Everything else is assigned the value 0.

    Return the numeric score.
    """
    # if the spec path is more specific than the element path it'll never match
    if len(spec_path) > len(element_path):
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
    if type(obj) == OrderedDict:
        return dict
    return type(obj)


class Matcher:
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
        self.rule = rule

    def __repr__(self):
        return f'<{self.__class__.__name__} path={self.path!r} rule={self.rule}>'

    def __str__(self):
        return f'Rule match by {self.rule} at {self.path}'

    def apply(self, data, spec, path):
        raise NotImplementedError()

    def weight(self, element_path):
        """Given a matching rule path and an element path a blob, determine the weighting for the match.

        Return the weight, or 0 if there is no match.
        """
        return weight_path(list(split_path(self.path)), element_path)

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

    REGISTRY = {}

    def __init_subclass__(cls, **kwargs):
        if cls not in Matcher.REGISTRY:
            Matcher.REGISTRY[cls.type] = cls
        super().__init_subclass__(**kwargs)

    @classmethod
    def get_matcher(cls, path, rule):
        if 'matchers' in rule:
            # v3 matchingRules always have a matchers array, even if there's a single rule
            return MultipleMatchers(path, **rule)
        if 'regex' in rule:
            # there's a weirdness in the spec here: it promotes use of regex without a match type :(
            type_name = 'regex'
        else:
            type_name = rule.get('match', 'type')
        if type_name not in cls.REGISTRY:
            log.warning(f'invalid match type "{type_name}" in rule at path {path}')
            type_name = 'invalid'
        return cls.REGISTRY[type_name](path, rule)


class InvalidMatcher(Matcher):
    type = 'invalid'

    def apply(self, data, spec, path):
        pass


class MatchType(Matcher):
    type = 'type'

    def apply(self, data, spec, path):
        log.debug(f'match type {data!r} {spec!r} {path!r}')
        if type(spec) in (int, float):
            if type(data) not in (int, float):
                raise RuleFailed(path, f'not correct type ({nice_type(data)} is not {nice_type(spec)})')
        elif fold_type(spec) != fold_type(data):
            raise RuleFailed(path, f'not correct type ({nice_type(data)} is not {nice_type(spec)})')
        self.check_min(data, path)
        self.check_max(data, path)


class MatchRegex(Matcher):
    type = 'regex'

    def apply(self, data, spec, path):
        # we have to cast data to str because Java treats all JSON values as strings and thus is happy to
        # specify a regex matcher for an integer (!!)
        log.debug(f'match regex {data!r} {spec!r} {path!r}: {self.rule["regex"]}')
        if re.fullmatch(self.rule['regex'], str(data)) is None:
            raise RuleFailed(path, f'value {data!r} does not match regex {self.rule["regex"]}')


class MatchInteger(Matcher):
    type = 'integer'

    def apply(self, data, spec, path):
        log.debug(f'match integer {data!r} {spec!r} {path!r}')
        if type(data) != int:
            raise RuleFailed(path, f'not correct type ({nice_type(data)} is not integer)')
        self.check_min(data, path)
        self.check_max(data, path)


class MatchDecimal(Matcher):
    type = 'decimal'

    def apply(self, data, spec, path):
        log.debug(f'match decimal {data!r} {spec!r} {path!r}')
        if type(data) != float:
            raise RuleFailed(path, f'not correct type ({nice_type(data)} is not decimal)')
        self.check_min(data, path)
        self.check_max(data, path)


class MatchNumber(Matcher):
    type = 'number'

    def apply(self, data, spec, path):
        log.debug(f'match number {data!r} {spec!r} {path!r}')
        if type(data) not in (int, float):
            raise RuleFailed(path, f'not correct type ({nice_type(data)} is not number)')
        self.check_min(data, path)
        self.check_max(data, path)


class MatchEquality(Matcher):
    type = 'equality'

    def apply(self, data, spec, path):
        log.debug(f'match equality {data!r} {spec!r} {path!r}')
        if data != self.rule['value']:
            raise RuleFailed(path, f'value {data!r} does not equal expected {self.rule["value"]!r}')


class MatchInclude(Matcher):
    type = 'include'

    def apply(self, data, spec, path):
        log.debug(f'match include {data!r} {spec!r} {path!r}')
        if self.rule['value'] not in data:
            raise RuleFailed(path, f'value {data!r} does not contain expected value {self.rule["value"]!r}')


class MatchNull(Matcher):
    type = 'null'

    def apply(self, data, spec, path):
        log.debug(f'match null {data!r} {spec!r} {path!r}')
        if data is not None:
            raise RuleFailed(path, f'value {data!r} is not null')


class MultipleMatchers(Matcher):
    type = '<multiple>'

    def __init__(self, path, matchers=None, combine='AND'):
        super().__init__(path, matchers)
        self.matchers = [Matcher.get_matcher(path, rule) for rule in matchers]
        self.combine = combine

    def apply(self, data, spec, path):
        log.debug(f'MultipleMatchers.__call__ {data!r} {spec!r} {path!r}')
        for matcher in self.matchers:
            log.debug(f'... matching {matcher}')
            try:
                matcher.apply(data, spec, path)
            except RuleFailed:
                if self.combine == 'AND':
                    raise
            else:
                if self.combine == 'OR':
                    return


def rule_matchers_v2(rules):
    """Get spec v2 rule matchers for the rules sets in a pact's ruleMatchers (passed in as "rules").

    v2 rules are specified in a single dictionary with the jsonpath $.<section>[.additional.jsonpath]:

        "matchingRules": {
            "$.body[0][*].email": {
                "match": "type"
            },
            "$.path": {
                "regex": "/user/\\w+/"
            }
        }

    Returns a dict with lists of Matcher subclass instances (e.g. MatchType) for each of path, query, header and body.
    """
    matchers = defaultdict(list)
    for path, spec in rules.items():
        if path == '$.path':
            # "path" rules are a bit different - there's no jsonpath as there's only a single value to compare, so we
            # hard-code the path to '$' which always matches when looking for weighted path matches
            matchers['path'].append(Matcher.get_matcher('$', spec))
        else:
            section = list(split_path(path))[1]
            matchers[section].append(Matcher.get_matcher(path, spec))
    return matchers


def rule_matchers_v3(rules):
    """Get spec v3 rule matchers for the rules sets in a pact's ruleMatchers (passed in as "rules").

    v3 rules are specified in sections with a sub-dict for each of path, query, header and body:

        "matchingRules": {
           "path": {
             "matchers": [
                 { "match": "regex", "regex": "\\w+" }
               ]
           },
           "query": {
             "Q1": {
                 "matchers": [
                   { "match": "regex", "regex": "\\w+" }
                 ]
             }
           },
           "header": {
             "Accept": {
                 "matchers": [
                     { "match" : "regex", "regex" : "\\w+" }
                 ]
             }
           },
           "body": {
             "$.animals": {
                 "matchers": [{"min": 1, "match": "type"}]
             }
           }
        }

    Returns a dict with lists of Matcher subclass instances (e.g. MatchType) for each of path, query, header and body.
    """
    matchers = {}
    if 'path' in rules:
        # "path" rules are a bit different - there's no jsonpath as there's only a single value to compare, so we
        # hard-code the path to '$' which always matches when looking for weighted path matches
        matchers['path'] = [MultipleMatchers('$', **rules['path'])]
    if 'query' in rules:
        # "query" rules are a bit different too - matchingRules are a flat single-level dictionary of keys which map to
        # array elements, but the data they match is keys mapping to an array, so alter the path such that the rule
        # maps to that array: "Q1" becomes "Q1[*]"
        matchers['query'] = [Matcher.get_matcher(path + '[*]', rule)
                             for path, rule in rules['query'].items()]
    for section in ['header', 'body']:
        if section in rules:
            matchers[section] = [Matcher.get_matcher(path, rule)
                                 for path, rule in rules[section].items()]
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
