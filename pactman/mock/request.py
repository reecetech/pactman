from .matchers import get_generated_values, get_matching_rules_v2, get_matching_rules_v3


class Request:
    """Represents an HTTP request and supports Matchers on its properties."""

    def __init__(self, method, path, body=None, headers=None, query=''):
        """
        Create a new instance of Request.

        :param method: The HTTP method that is expected.
        :type method: str
        :param path: The URI path that is expected on this request.
        :type path: str, Matcher
        :param body: The contents of the body of the expected request.
        :type body: str, dict, list
        :param headers: The headers of the expected request.
        :type headers: dict
        :param query: The URI query of the expected request.
        :type query: str or dict
        """
        self.method = method
        self.path = path
        self.body = body
        self.headers = headers
        self.query = query

    def json(self, spec_version):
        """Convert the Request to a JSON Pact."""
        request = {
            'method': self.method,
            'path': get_generated_values(self.path)
        }

        if self.headers:
            request['headers'] = get_generated_values(self.headers)

        if self.body is not None:
            request['body'] = get_generated_values(self.body)

        if self.query:
            request['query'] = get_generated_values(self.query)

        if spec_version == '2.0.0':
            matchingRules = self.generate_v2_matchingRules()
        elif spec_version == '3.0.0':
            matchingRules = self.generate_v3_matchingRules()
        else:
            raise ValueError(f'Invalid Pact specification version={spec_version}')

        if matchingRules:
            request['matchingRules'] = matchingRules

        return request

    def generate_v2_matchingRules(self):
        # TODO check there's generation *and* verification tests for all these
        matchingRules = get_matching_rules_v2(self.path, '$.path')
        matchingRules.update(get_matching_rules_v2(self.headers, '$.headers'))
        matchingRules.update(get_matching_rules_v2(self.body, '$.body'))
        matchingRules.update(get_matching_rules_v2(self.query, '$.query'))
        return matchingRules

    def generate_v3_matchingRules(self):
        # TODO check there's generation *and* verification tests for all these
        matchingRules = get_matching_rules_v3(self.path, 'path')
        matchingRules.update(get_matching_rules_v3(self.headers, 'headers'))

        # body and query rules look different
        body_rules = get_matching_rules_v3(self.body, '$')
        if body_rules:
            matchingRules['body'] = body_rules
        query_rules = get_matching_rules_v3(self.query, 'query')
        if query_rules:
            expand_query_rules(query_rules)
            matchingRules['query'] = query_rules
        return matchingRules


def expand_query_rules(rules):
    # Query rules in the pact JSON are declared without the array notation (even though they always
    # match arrays).
    # The matchers will be coded to JSON paths by get_matching_rules_v3, and we need to extract
    # them out to a dictionary where the original rule path will look like 'query.param[*]'
    # and we need to extract "param".
    for rule_path in list(rules):
        matchers = rules.pop(rule_path)
        rule_param = rule_path[6:-3]
        rules[rule_param] = matchers
