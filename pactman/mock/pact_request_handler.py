import json
import os
import os.path
import urllib.parse

from ..verifier.parse_header import get_header_param
from ..verifier.result import Result
from ..verifier.verify import RequestVerifier


class Request:
    def __init__(self, method, path, query, headers, body):
        self.method = method
        self.path = path
        self.query = query
        self.headers = headers
        self.body = body

    def json(self):
        return self.body


class RecordResult(Result):
    def start(self, interaction):
        super().start(interaction)

    def fail(self, message, path=None):
        self.success = self.FAIL
        self.reason = message
        return not message


class PactVersionConflict(AssertionError):
    pass


class PactInteractionMismatch(AssertionError):
    pass


class PactRequestHandler:
    def __init__(self, pact):
        self.pact = pact

    def validate_request(self, method):
        url_parts = urllib.parse.urlparse(self.path)

        interaction = self.get_interaction(url_parts.path)
        body = self.get_body()

        request = Request(method, url_parts.path, url_parts.query, self.headers, body)
        result = RecordResult()
        RequestVerifier(self.pact, interaction['request'], result).verify(request)
        if not result.success:
            return self.handle_failure(result.reason)
        self.handle_success(interaction)
        if self.pact.file_write_mode != 'never':
            self.write_pact(interaction)
        return self.respond_for_interaction(interaction)

    def get_body(self):
        if not self.body:
            return ''
        content_type = [self.headers[h] for h in self.headers if h.lower() == 'content-type']
        if content_type:
            content_type = content_type[0]
        else:
            # default content type for pacts
            content_type = 'application/json'

        if content_type == 'application/json':
            return json.loads(self.body)
        elif content_type == 'application/x-www-form-urlencoded':
            return urllib.parse.parse_qs(self.body)
        raise ValueError(f'Unhandled body content type {content_type}')

    def get_interaction(self, path):
        raise NotImplementedError()

    def handle_success(self, interaction):
        raise NotImplementedError()

    def handle_failure(self, reason):
        raise NotImplementedError()

    def respond_for_interaction(self, reason):
        raise NotImplementedError()

    def handle_response_encoding(self, response, headers):
        # default to content-type to json
        # rfc4627 states JSON is Unicode and defaults to UTF-8
        content_type = [headers[h] for h in headers if h.lower() == 'content-type']
        if content_type:
            content_type = content_type[0]
            if 'application/json' not in content_type:
                return response['body']
            charset = get_header_param(content_type, 'charset')
            if not charset:
                charset = 'UTF-8'
        else:
            headers['Content-Type'] = 'application/json; charset=UTF-8'
            charset = 'UTF-8'
        return json.dumps(response['body']).encode(charset)

    def write_pact(self, interaction):
        if self.pact.semver["major"] >= 3:
            provider_state_key = 'providerStates'
        else:
            provider_state_key = 'providerState'

        if os.path.exists(self.pact.pact_json_filename):
            with open(self.pact.pact_json_filename) as f:
                pact = json.load(f)
            existing_version = pact['metadata']['pactSpecification']['version']
            if existing_version != self.pact.version:
                raise PactVersionConflict(f'Existing pact ("{pact["interactions"][0]["description"]}") specifies '
                                          f'version {existing_version} but new pact ("interaction["description"]") '
                                          f'specifies version {self.pact.version}')
            for existing in pact['interactions']:
                if (existing['description'] == interaction['description']
                        and existing.get(provider_state_key) == interaction.get(provider_state_key)):
                    # already got one of these...
                    if existing != interaction:
                        raise PactInteractionMismatch(
                            f'Existing "{existing["description"]}" pact given {existing.get(provider_state_key)!r} '
                            'exists with different request/response')
                    return
            pact['interactions'].append(interaction)
        else:
            pact = self.pact.construct_pact(interaction)

        with open(self.pact.pact_json_filename, 'w') as f:
            json.dump(pact, f, indent=2)
