from .matchers import get_generated_values, get_matching_rules_v2, get_matching_rules_v3


class Response:
    """Represents an HTTP response and supports Matchers on its properties."""

    def __init__(self, status, headers=None, body=None):
        """
        Create a new Response.

        :param status: The expected HTTP status of the response.
        :type status: int
        :param headers: The expected headers of the response.
        :type headers: dict
        :param body: The expected body of the response.
        :type body: str, dict, or list
        """
        self.status = status
        self.body = body
        self.headers = headers

    def json(self, spec_version):
        """Convert the Response to a JSON Pact."""
        response = {'status': self.status}
        if self.body is not None:
            response['body'] = get_generated_values(self.body)

        if self.headers:
            response['headers'] = get_generated_values(self.headers)

        if spec_version == '2.0.0':
            matchingRules = self.generate_v2_matchingRules()
        elif spec_version == '3.0.0':
            matchingRules = self.generate_v3_matchingRules()
        else:
            raise ValueError(f'Invalid Pact specification version={spec_version}')

        if matchingRules:
            response['matchingRules'] = matchingRules

        return response

    def generate_v2_matchingRules(self):
        # TODO check there's generation *and* verification tests for all these
        matchingRules = get_matching_rules_v2(self.headers, '$.headers')
        matchingRules.update(get_matching_rules_v2(self.body, '$.body'))
        return matchingRules

    def generate_v3_matchingRules(self):
        # TODO check there's generation *and* verification tests for all these
        matchingRules = get_matching_rules_v3(self.headers, 'headers')
        body_rules = get_matching_rules_v3(self.body, '$')
        if body_rules:
            matchingRules['body'] = body_rules
        return matchingRules
