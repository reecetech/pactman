"""Classes for defining request and response data that is variable."""

import datetime
from enum import Enum


class Matcher(object):
    """Base class for defining complex contract expectations."""

    def ruby_protocol(self):  # pragma: no cover
        """
        Serialise this Matcher for the Ruby mocking server.

        :rtype: any
        """
        raise NotImplementedError

    def generate_matching_rule_v3(self):  # pragma: no cover
        raise NotImplementedError


class EachLike(Matcher):
    """
    Expect the data to be a list of similar objects.

    Example:

    >>> from pactman import Consumer, Provider
    >>> pact = Consumer('consumer').has_pact_with(Provider('provider'))
    >>> (pact.given('there are three comments')
    ...  .upon_receiving('a request for the most recent 2 comments')
    ...  .with_request('get', '/comment', query={'limit': 2})
    ...  .will_respond_with(200, body={
    ...    'comments': EachLike(
    ...        {'name': Like('bob'), 'text': Like('Hello!')},
    ...        minimum=2)
    ...  }))

    Would expect the response to be a JSON object, with a comments list. In
    that list should be at least 2 items, and each item should be a `dict`
    with the keys `name` and `text`,
    """

    def __init__(self, matcher, minimum=1):
        """
        Create a new EachLike.

        :param matcher: The expected value that each item in a list should
            look like, this can be other matchers.
        :type matcher: None, list, dict, int, float, str, unicode, Matcher
        :param minimum: The minimum number of items expected.
            Must be greater than or equal to 1.
        :type minimum: int
        """
        self.matcher = matcher
        if minimum < 1:
            raise AssertionError("Minimum must be greater than or equal to 1")
        self.minimum = minimum

    def ruby_protocol(self):
        """
        Serialise this EachLike for the Ruby mocking server.

        :return: A dict containing the information about the contents of the
            list and the provided minimum number of items for that list.
        :rtype: dict
        """
        return {
            "json_class": "Pact::ArrayLike",
            "contents": generate_ruby_protocol(self.matcher),
            "min": self.minimum,
        }

    def generate_matching_rule_v3(self):
        return {"matchers": [{"match": "type", "min": self.minimum}]}


class Like(Matcher):
    """
    Expect the type of the value to be the same as matcher.

    Example:

    >>> from pactman import Consumer, Provider
    >>> pact = Consumer('consumer').has_pact_with(Provider('provider'))
    >>> (pact
    ...  .given('there is a random number generator')
    ...  .upon_receiving('a request for a random number')
    ...  .with_request('get', '/generate-number')
    ...  .will_respond_with(200, body={
    ...    'number': Like(1111222233334444)
    ...  }))

    Would expect the response body to be a JSON object, containing the key
    `number`, which would contain an integer. When the consumer runs this
    contract, the value `1111222233334444` will be returned by the mock
    service, instead of a randomly generated value.
    """

    def __init__(self, matcher):
        """
        Create a new Like.

        :param matcher: The object that should be expected. The mock
            will return this value. When verified against the provider, the
            type of this value will be asserted, while the value will be
            ignored.
        :type matcher: None, list, dict, int, float, str, Matcher
        """
        valid_types = (type(None), list, dict, int, float, str, Matcher)

        assert isinstance(
            matcher, valid_types
        ), f"matcher must be one of '{valid_types}', got '{type(matcher)}'"

        self.matcher = matcher

    def ruby_protocol(self):
        """
        Serialise this Like for the Ruby mocking server.

        :return: A dict containing the information about what the contents of
            the request/response should be.
        :rtype: dict
        """
        return {
            "json_class": "Pact::SomethingLike",
            "contents": generate_ruby_protocol(self.matcher),
        }

    def generate_matching_rule_v3(self):
        return {"matchers": [{"match": "type"}]}


# Remove SomethingLike in major version 1.0.0
SomethingLike = Like


class Term(Matcher):
    """
    Expect the response to match a specified regular expression.

    Example:

    >>> from pactman import Consumer, Provider
    >>> pact = Consumer('consumer').has_pact_with(Provider('provider'))
    >>> (pact.given('the current user is logged in as `tester`')
    ...  .upon_receiving('a request for the user profile')
    ...  .with_request('get', '/profile')
    ...  .will_respond_with(200, body={
    ...    'name': 'tester',
    ...    'theme': Term('light|dark|legacy', 'dark')
    ...  }))

    Would expect the response body to be a JSON object, containing the key
    `name`, which will contain the value `tester`, and `theme` which must be
    one of the values: light, dark, or legacy. When the consumer runs this
    contract, the value `dark` will be returned by the mock.
    """

    def __init__(self, matcher, generate):
        """
        Create a new Term.

        :param matcher: A regular expression to find.
        :type matcher: basestring
        :param generate: A value to be returned by the mock when
            generating the response to the consumer.
        :type generate: basestring
        """
        self.matcher = matcher
        self.generate = generate

    def ruby_protocol(self):
        """
        Serialise this Term for the Ruby mocking server.

        :return: A dict containing the information about what the contents of
            the request/response should be, and what should match for the requests.
        :rtype: dict
        """
        return {
            "json_class": "Pact::Term",
            "data": {
                "generate": self.generate,
                "matcher": {"json_class": "Regexp", "o": 0, "s": self.matcher},
            },
        }

    def generate_matching_rule_v3(self):
        return {"matchers": [{"match": "regex", "regex": self.matcher}]}


class Equals(Matcher):
    """
    Expect the value to be the same as matcher.

    Example:

    >>> from pactman import Consumer, Provider
    >>> pact = Consumer('consumer').has_pact_with(Provider('provider'))
    >>> (pact
    ...  .given('there is a random number generator')
    ...  .upon_receiving('a request for a random number')
    ...  .with_request('get', '/generate-number')
    ...  .will_respond_with(200, body={
    ...    'number': Equals(1111222233334444)
    ...  }))

    Would expect the response body to be a JSON object, containing the key
    `number`, which would contain the value `1111222233334444`.
    When the consumer runs this contract, the value `1111222233334444`
    will be returned by the mock, instead of a randomly generated value.
    """

    class NotAllowed(TypeError):
        pass

    def __init__(self, matcher):
        """
        Create a new Equals.

        :param matcher: The object that should be expected. The mock
            will return this value. When verified against the provider, the
            value will be asserted.
        :type matcher: None, list, dict, int, float, str
        """
        valid_types = (type(None), list, dict, int, float, str)
        assert isinstance(
            matcher, valid_types
        ), f"matcher must be one of '{valid_types}', got '{type(matcher)}'"

        self.matcher = matcher

    def generate_matching_rule_v3(self):
        return {"matchers": [{"match": "equality"}]}


class Includes(Matcher):
    """
    Expect the string value to contain the matcher.

    Example:

    >>> from pactman import Consumer, Provider
    >>> pact = Consumer('consumer').has_pact_with(Provider('provider'))
    >>> (pact
    ...  .given('there is a random number generator')
    ...  .upon_receiving('a request for a random number')
    ...  .with_request('get', '/generate-number')
    ...  .will_respond_with(200, body={
    ...    'content': Includes('spam', 'Some example spamming content')
    ...  }))

    Would expect the response body to be a JSON object, containing the key
    `content`, which be a string containing `'spam'`.
    When the consumer runs this contract, the value `'Some example spamming content'`
    will be returned by the mock.
    """

    class NotAllowed(TypeError):
        pass

    def __init__(self, matcher, generate):
        """
        Create a new Includes.

        :param matcher: The substring that should be expected. When verified against the
            provider, the value will be asserted.
        :type matcher: string
        :param generate: The mock will return this value.
        :type generate: string
        """
        assert isinstance(matcher, str), f"matcher must be a string, got '{type(matcher)}'"

        self.matcher = matcher
        self.generate = generate

    def generate_matching_rule_v3(self):
        return {"matchers": [{"match": "include", "value": self.matcher}]}


def generate_ruby_protocol(term):
    """
    Parse the provided term into the JSON for the Ruby mock server.

    :param term: The term to be parsed.
    :type term: None, list, dict, int, float, str, unicode, Matcher
    :return: The JSON representation for this term.
    :rtype: dict, list, str
    """
    if term is None:
        return term
    elif isinstance(term, (str, int, float)):
        return term
    elif isinstance(term, dict):
        return {k: generate_ruby_protocol(v) for k, v in term.items()}
    elif isinstance(term, list):
        return [generate_ruby_protocol(t) for i, t in enumerate(term)]
    elif issubclass(term.__class__, (Matcher,)):
        return term.ruby_protocol()
    else:
        raise ValueError("Unknown type: %s" % type(term))


# For backwards compatiblity with test code that uses pact-python to declare pacts,
# allow the various classes from that package to also be used to define rules
try:
    import pact as pact_python

    LIKE_CLASSES = (Like, pact_python.Like)
    EACHLIKE_CLASSES = (EachLike, pact_python.EachLike)
    TERM_CLASSES = (Term, pact_python.Term)
except ImportError:
    pact_python = None
    LIKE_CLASSES = (Like,)
    EACHLIKE_CLASSES = (EachLike,)
    TERM_CLASSES = (Term,)


# this function is long and complex (C901) because it has to handle the pact-python
# types :-(
def get_generated_values(input):  # noqa: C901
    """
    Resolve (nested) Matchers to their generated values for assertion.

    :param input: The input to be resolved to its generated values.
    :type input: None, list, dict, int, float, bool, str, unicode, Matcher
    :return: The input resolved to its generated value(s)
    :rtype: None, list, dict, int, float, bool, str, unicode, Matcher
    """
    if input is None:
        return input
    if isinstance(input, (str, int, float, bool)):
        return input
    if isinstance(input, dict):
        return {k: get_generated_values(v) for k, v in input.items()}
    if isinstance(input, list):
        return [get_generated_values(t) for i, t in enumerate(input)]
    elif isinstance(input, LIKE_CLASSES):
        return get_generated_values(input.matcher)
    elif isinstance(input, EACHLIKE_CLASSES):
        return [get_generated_values(input.matcher)] * input.minimum
    elif isinstance(input, Term):
        return input.generate
    elif pact_python is not None and isinstance(input, pact_python.Term):
        return input._generate
    elif isinstance(input, Equals):
        return get_generated_values(input.matcher)
    elif isinstance(input, Includes):
        return input.generate
    else:
        raise ValueError("Unknown type: %s" % type(input))


# this function is long and complex (C901) because it has to handle the pact-python
# types :-(
def get_matching_rules_v2(input, path):  # noqa: C901
    """Turn a matcher into the matchingRules structure for pact JSON.

    This is done recursively, adding new paths as new matching rules
    are encountered.
    """
    if input is None or isinstance(input, (str, int, float, bool)):
        return {}
    if isinstance(input, dict):
        rules = {}
        for k, v in input.items():
            sub_path = path + "." + k
            rules.update(get_matching_rules_v2(v, sub_path))
        return rules
    if isinstance(input, list):
        rules = {}
        for i, v in enumerate(input):
            sub_path = path + "[*]"
            rules.update(get_matching_rules_v2(v, sub_path))
        return rules
    if isinstance(input, LIKE_CLASSES):
        rules = {path: {"match": "type"}}
        rules.update(get_matching_rules_v2(input.matcher, path))
        return rules
    if isinstance(input, EACHLIKE_CLASSES):
        rules = {path: {"match": "type", "min": input.minimum}}
        rules.update(get_matching_rules_v2(input.matcher, path))
        return rules
    if isinstance(input, TERM_CLASSES):
        return {path: {"regex": input.matcher}}
    if isinstance(input, Equals):
        raise Equals.NotAllowed("Equals() cannot be used in pact version 2")
    if isinstance(input, Includes):
        raise Includes.NotAllowed("Includes() cannot be used in pact version 2")

    raise ValueError("Unknown type: %s" % type(input))


class MatchingRuleV3(dict):
    def generate(self, input, path):
        if self.handle_basic_types(input, path):
            return
        if self.handle_pactman_types(input, path):
            return
        if self.handle_pact_python_types(input, path):
            return
        raise ValueError("Unknown type: %s" % type(input))

    def handle_basic_types(self, input, path):
        if input is None or isinstance(input, (str, int, float, bool)):
            return True
        if isinstance(input, dict):
            for k, v in input.items():
                self.generate(v, path + "." + k)
            return True
        if isinstance(input, list):
            for v in input:
                self.generate(v, path + "[*]")
            return True
        return False

    def handle_pactman_types(self, input, path):
        if not hasattr(input, "generate_matching_rule_v3"):
            return False
        self[path] = input.generate_matching_rule_v3()
        if isinstance(input.matcher, (list, dict)):
            self.handle_basic_types(input.matcher, path)
        return True

    def handle_pact_python_types(self, input, path):
        if pact_python is None:
            return False

        if isinstance(input, pact_python.Like):
            self[path] = {"matchers": [{"match": "type"}]}
            self.generate(input.matcher, path)
        elif isinstance(input, pact_python.EachLike):
            self[path] = {"matchers": [{"match": "type", "min": input.minimum}]}
            self.generate(input.matcher, path)
        elif isinstance(input, pact_python.Term):
            self[path] = {"matchers": [{"match": "regex", "regex": input.matcher}]}
        else:
            return False

        return True


def get_matching_rules_v3(input, path):
    """Turn a matcher into the matchingRules structure for pact JSON.

    This is done recursively, adding new paths as new matching rules
    are encountered.
    """
    rules = MatchingRuleV3()
    rules.generate(input, path)
    return rules


class Format:
    """
    Class of regular expressions for common formats.

    Example:
    >>> from pact import Consumer, Provider
    >>> from pact.matchers import Format
    >>> pact = Consumer('consumer').has_pact_with(Provider('provider'))
    >>> (pact.given('the current user is logged in as `tester`')
    ...  .upon_receiving('a request for the user profile')
    ...  .with_request('get', '/profile')
    ...  .will_respond_with(200, body={
    ...    'id': Format().identifier,
    ...    'lastUpdated': Format().time
    ...  }))

    Would expect `id` to be any valid int and `lastUpdated` to be a valid time.
    When the consumer runs this contract, the value of that will be returned
    is the second value passed to Term in the given function, for the time
    example it would be datetime.datetime(2000, 2, 1, 12, 30, 0, 0).time()

    """

    def __init__(self):
        """Create a new Formatter."""
        self.identifier = self.integer_or_identifier()
        self.integer = self.integer_or_identifier()
        self.decimal = self.decimal()
        self.ip_address = self.ip_address()
        self.hexadecimal = self.hexadecimal()
        self.ipv6_address = self.ipv6_address()
        self.uuid = self.uuid()
        self.timestamp = self.timestamp()
        self.date = self.date()
        self.time = self.time()

    def integer_or_identifier(self):
        """
        Match any integer.

        :return: a Like object with an integer.
        :rtype: Like
        """
        return Like(1)

    def decimal(self):
        """
        Match any decimal.

        :return: a Like object with a decimal.
        :rtype: Like
        """
        return Like(1.0)

    def ip_address(self):
        """
        Match any ip address.

        :return: a Term object with an ip address regex.
        :rtype: Term
        """
        return Term(self.Regexes.ip_address.value, '127.0.0.1')

    def hexadecimal(self):
        """
        Match any hexadecimal.

        :return: a Term object with a hexdecimal regex.
        :rtype: Term
        """
        return Term(self.Regexes.hexadecimal.value, '3F')

    def ipv6_address(self):
        """
        Match any ipv6 address.

        :return: a Term object with an ipv6 address regex.
        :rtype: Term
        """
        return Term(self.Regexes.ipv6_address.value, '::ffff:192.0.2.128')

    def uuid(self):
        """
        Match any uuid.

        :return: a Term object with a uuid regex.
        :rtype: Term
        """
        return Term(
            self.Regexes.uuid.value, 'fc763eba-0905-41c5-a27f-3934ab26786c'
        )

    def timestamp(self):
        """
        Match any timestamp.

        :return: a Term object with a timestamp regex.
        :rtype: Term
        """
        return Term(
            self.Regexes.timestamp.value, datetime.datetime(
                2000, 2, 1, 12, 30, 0, 0
            ).isoformat()
        )

    def date(self):
        """
        Match any date.

        :return: a Term object with a date regex.
        :rtype: Term
        """
        return Term(
            self.Regexes.date.value, datetime.datetime(
                2000, 2, 1, 12, 30, 0, 0
            ).date().isoformat()
        )

    def time(self):
        """
        Match any time.

        :return: a Term object with a time regex.
        :rtype: Term
        """
        return Term(
            self.Regexes.time_regex.value, datetime.datetime(
                2000, 2, 1, 12, 30, 0, 0
            ).time().isoformat()
        )

    class Regexes(Enum):
        """Regex Enum for common formats."""

        ip_address = r'(\d{1,3}\.)+\d{1,3}'
        hexadecimal = r'[0-9a-fA-F]+'
        ipv6_address = r'(\A([0-9a-f]{1,4}:){1,1}(:[0-9a-f]{1,4}){1,6}\Z)|' \
            r'(\A([0-9a-f]{1,4}:){1,2}(:[0-9a-f]{1,4}){1,5}\Z)|(\A([0-9a-f]' \
            r'{1,4}:){1,3}(:[0-9a-f]{1,4}){1,4}\Z)|(\A([0-9a-f]{1,4}:)' \
            r'{1,4}(:[0-9a-f]{1,4}){1,3}\Z)|(\A([0-9a-f]{1,4}:){1,5}(:[0-' \
            r'9a-f]{1,4}){1,2}\Z)|(\A([0-9a-f]{1,4}:){1,6}(:[0-9a-f]{1,4})' \
            r'{1,1}\Z)|(\A(([0-9a-f]{1,4}:){1,7}|:):\Z)|(\A:(:[0-9a-f]{1,4})' \
            r'{1,7}\Z)|(\A((([0-9a-f]{1,4}:){6})(25[0-5]|2[0-4]\d|[0-1]' \
            r'?\d?\d)(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3})\Z)|(\A(([0-9a-f]' \
            r'{1,4}:){5}[0-9a-f]{1,4}:(25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25' \
            r'[0-5]|2[0-4]\d|[0-1]?\d?\d)){3})\Z)|(\A([0-9a-f]{1,4}:){5}:[' \
            r'0-9a-f]{1,4}:(25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]|2[0-4' \
            r']\d|[0-1]?\d?\d)){3}\Z)|(\A([0-9a-f]{1,4}:){1,1}(:[0-9a-f]' \
            r'{1,4}){1,4}:(25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]|2[0-4]' \
            r'\d|[0-1]?\d?\d)){3}\Z)|(\A([0-9a-f]{1,4}:){1,2}(:[0-9a-f]{1,4}' \
            r'){1,3}:(25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]|2[0-4]\d|[0' \
            r'-1]?\d?\d)){3}\Z)|(\A([0-9a-f]{1,4}:){1,3}(:[0-9a-f]{1,4}){1,' \
            r'2}:(25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]|2[0-4]\d|[0-1]' \
            r'?\d?\d)){3}\Z)|(\A([0-9a-f]{1,4}:){1,4}(:[0-9a-f]{1,4}){1,1}:' \
            r'(25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]|2[0-4]\d|[0-1]?\d?' \
            r'\d)){3}\Z)|(\A(([0-9a-f]{1,4}:){1,5}|:):(25[0-5]|2[0-4]\d|[0' \
            r'-1]?\d?\d)(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}\Z)|(\A:(:[' \
            r'0-9a-f]{1,4}){1,5}:(25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]' \
            r'|2[0-4]\d|[0-1]?\d?\d)){3}\Z)'
        uuid = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
        timestamp = r'^([\+-]?\d{4}(?!\d{2}\b))((-?)((0[1-9]|1[0-2])(\3(' \
            r'[12]\d|0[1-9]|3[01]))?|W([0-4]\d|5[0-2])(-?[1-7])?|(00[1-' \
            r'9]|0[1-9]\d|[12]\d{2}|3([0-5]\d|6[1-6])))([T\s]((([01]\d|2' \
            r'[0-3])((:?)[0-5]\d)?|24\:?00)([\.,]\d+(?!:))?)?(\17[0-5]\d' \
            r'([\.,]\d+)?)?([zZ]|([\+-])([01]\d|2[0-3]):?([0-5]\d)?)?)?)?$'
        date = r'^([\+-]?\d{4}(?!\d{2}\b))((-?)((0[1-9]|1[0-2])(\3([12]\d|' \
            r'0[1-9]|3[01]))?|W([0-4]\d|5[0-2])(-?[1-7])?|(00[1-9]|0[1-9]\d|' \
            r'[12]\d{2}|3([0-5]\d|6[1-6])))?)'
        time_regex = r'^(T\d\d:\d\d(:\d\d)?(\.\d+)?(([+-]\d\d:\d\d)|Z)?)?$'
