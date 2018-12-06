import logging
from urllib.parse import parse_qs, urljoin

import requests

from .matching_rule import fold_type, nice_type, rule_matchers_v2, rule_matchers_v3, RuleFailed
from .parse_header import parse_header
from .paths import format_path


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class ProviderStateError(Exception):
    pass


class Interaction:
    def __init__(self, pact, interaction, result_factory):
        self.pact = pact
        self.result = result_factory()
        self.description = interaction['description']
        self.request = interaction['request']
        self.providerState = interaction.get('providerState')
        self.providerStates = interaction.get('providerStates')
        self.response = ResponseVerifier(pact, interaction['response'], self.result)

    def __repr__(self):
        return f"{self.pact.consumer}:{self.description}"

    def verify(self, service_url, setup_url):
        self.result.start(self)
        try:
            self.result.success = self.setup(setup_url)
            if not self.result.success:
                return False
            self.result.success = self.run_service(service_url)
        finally:
            self.result.end()

    def run_service(self, service_url):
        method = self.request['method']
        handler = getattr(self, f'service_{method}', None)
        if handler is None:
            return self.result.fail(f'Request method {method} not implemented in verifier')
        return handler(service_url)

    def service_GET(self, service_url):
        if 'query' in self.request:
            query = self.request['query']
            if isinstance(query, str):
                # version 2 spec used strings, version 3 uses objects
                query = parse_qs(query)
            r = requests.get(self._get_url(service_url), params=query, headers=self._request_headers)
        else:
            r = requests.get(self._get_url(service_url), headers=self._request_headers)
        return self.response.verify(r)

    def service_HEAD(self, service_url):
        if 'query' in self.request:
            query = self.request['query']
            if isinstance(query, str):
                # version 2 spec used strings, version 3 uses objects
                query = parse_qs(query)
            r = requests.head(self._get_url(service_url), params=query, headers=self._request_headers)
        else:
            r = requests.head(self._get_url(service_url), headers=self._request_headers)
        return self.response.verify(r)

    def service_POST(self, service_url):
        if not self._content_type_json:
            return self.result.fail(f'POST content type {self._content_type} not implemented in verifier')
        r = requests.post(self._get_url(service_url), json=self._request_payload, headers=self._request_headers)
        return self.response.verify(r)

    def service_DELETE(self, service_url):
        r = requests.delete(self._get_url(service_url), headers=self._request_headers)
        return self.response.verify(r)

    def service_PUT(self, service_url):
        if not self._content_type_json:
            return self.result.fail(f'PUT content type {self._content_type} not implemented in verifier')
        r = requests.put(self._get_url(service_url), json=self._request_payload, headers=self._request_headers)
        return self.response.verify(r)

    def service_PATCH(self, service_url):
        if not self._content_type_json:
            return self.result.fail(f'PATCH content type {self._content_type} not implemented in verifier')
        r = requests.patch(self._get_url(service_url), json=self._request_payload, headers=self._request_headers)
        return self.response.verify(r)

    def setup(self, setup_url):
        if self.providerState is not None:
            return self.set_up_state(setup_url, 'state', self.providerState)
        elif self.providerStates is not None:
            return self.set_up_state(setup_url, 'states', self.providerStates)
        return True

    def set_up_state(self, setup_url, var, state):
        log.debug(f'Setting up provider state {state!r}')
        args = {
            'provider': self.pact.provider,
            'consumer': self.pact.consumer,
            var: state
        }
        try:
            r = requests.post(setup_url, json=args)
        except requests.exceptions.ConnectionError as e:
            try:
                # try to pull the actual error out of the nested (nested (nested, string-ified))) exception
                reason = str(e.args[0].reason).split(": ", 1)[1]
            except Exception:
                reason = str(e)
            return self.result.fail(f'Unable to configure provider state {state!r} at {setup_url}: {reason}')
        if r.status_code != 200:
            text = repr(r.text)
            if len(text) > 60:
                text = text[:60] + '...' + text[-1]
            log.debug(f'HTTP {r.status_code} from provider state setup URL: {text}')
            return self.result.fail(f'Invalid provider state {state!r}')
        log.info(f'Using provider state {state!r}')
        return True

    def _get_url(self, service_url):
        return urljoin(service_url, self.request['path'])

    @property
    def _request_headers(self):
        return self.request.get('headers', {})

    @property
    def _request_payload(self):
        return self.request.get('body')

    @property
    def _content_type_json(self):
        return 'application/json' in self._content_type

    @property
    def _content_type(self):
        return self._request_headers.get('Content-Type', 'application/json')


class ResponseVerifier:
    interaction_name = 'Response'

    def __init__(self, pact, interaction, result):
        self.pact = pact
        self.status = interaction.get('status', MISSING)
        self.headers = interaction.get('headers', MISSING)
        self.body = interaction.get('body', MISSING)
        rules = interaction.get('matchingRules', {})
        if pact.semver['major'] < 2:
            # there are no matchingRules in v1
            self.matching_rules = {}
        elif pact.semver['major'] < 3:
            self.matching_rules = rule_matchers_v2(rules)
        else:
            self.matching_rules = rule_matchers_v3(rules)
        self.result = result

    def verify(self, response):
        log.debug(f'{self.__class__.__name__}.verify headers={self.headers is not MISSING} '
                  f'body={self.body is not MISSING} rules={self.matching_rules != {}}')
        if self.status is not MISSING and response.status_code != self.status:
            log.debug(f'.. response {response.text}')
            return self.result.fail(f'{self.interaction_name} status code {response.status_code} is not '
                                    f'expected {self.status}')
        if self.headers is not MISSING:
            for header in self.headers:
                expected = self.headers[header]
                for actual in response.headers:
                    if header.lower() != actual.lower():
                        continue
                    actual = response.headers[actual]
                    if not self.check_rules(actual, expected, ['header', header]):
                        log.info(f'{self.interaction_name} headers: {response.json()}')
                        return False
        if self.body is not MISSING:
            if not self.check_rules(response.json(), self.body, ['body']):
                log.info(f'{self.interaction_name} data: {response.json()}')
                return False
        return True

    def check_rules(self, data, spec, path):
        log.debug(f'check_rules {data!r} {spec!r} {path}')
        if self.matching_rules:
            # if we have matchingRules then just look at those things
            r = self.apply_rules(data, spec, path)
        else:
            # otherwise the actual must equal the expected (excepting dict elements in actual that are unexpected)
            if path[0] == 'header':
                r = self.compare_header(data, spec, path)
            else:
                r = self.compare(data, spec, ['body'])
        log.debug(f'check_rules DONE = {r!r}')
        return r

    def compare_header(self, data, spec, path):
        parsed_data = sorted(parse_header(data))
        parsed_spec = sorted(parse_header(spec))
        log.debug(f'compare_header {parsed_data} {parsed_spec}')
        if parsed_data != parsed_spec:
            # there's a mind-bogglingly specific caveat to header matching that says that if the headers don't
            # match and they're a Content-Type and an encoding is supplier but not expected then it's OK to pass
            data_has_charset = [part for part in parsed_data if part.has_param('charset')]
            spec_has_charset = [part for part in parsed_spec if part.has_param('charset')]
            if path[1].lower() == 'content-type' and data_has_charset and not spec_has_charset:
                return True
            return self.result.fail(f'{self.interaction_name} header {path[1]} value {data!r} does not match '
                                    f'expected {spec!r}')
        return True

    def compare(self, data, spec, path):
        log.debug(f'compare {data!r} {spec!r} {path}')
        if fold_type(spec) is list:
            return self.compare_list(data, path, spec)
        if fold_type(spec) is dict:
            return self.compare_dict(data, spec, path)
        if not data == spec:
            return self.result.fail(f'Element mismatch {data!r} != {spec!r}', path)
        return True

    def compare_list(self, data, path, spec):
        if fold_type(data) is not list:
            return self.result.fail(f'{self.interaction_name} element is not an array (is {nice_type(data)})', path)
        if len(data) != len(spec):
            return self.result.fail(f'{self.interaction_name} array is incorrect length (is {len(data)} elements)',
                                    path)
        for i, (data_elem, spec_elem) in enumerate(zip(data, spec)):
            p = path + [i]
            if not self.compare(data_elem, spec_elem, p):
                return self.result.fail(f'{self.interaction_name} element {i} ({nice_type(data_elem)}) '
                                        f'does not match spec ({nice_type(spec_elem)})', path)
        return True

    def compare_dict(self, data, spec, path):
        if fold_type(data) is not dict:
            return self.result.fail(f'{self.interaction_name} element is not an object (is {nice_type(data)})', path)
        for key in spec:
            if key not in data:
                return self.result.fail(f'Expected element {key!r} not in response', path)
            p = path + [key]
            if not self.compare(data[key], spec[key], p):
                return self.result.fail(f'{self.interaction_name} element {key} ({nice_type(data[key])}) '
                                        f'does not match spec ({nice_type(spec[key])})', path)
        return True

    def apply_rules(self, data, spec, path):
        # given some actual data and a pact spec at a certain path, check any rules for that path
        log.debug(f'apply_rules data={data!r} spec={spec!r} path={format_path(path)}')
        rule = self.find_rule(path)
        log.debug(f'... rule lookup got {rule}')
        if rule:
            try:
                rule.apply(data, spec, path)
            except RuleFailed as e:
                log.debug(f'... failed: {e}')
                return self.result.fail(str(e), path)
            log.debug('... passed')

        # we passed the matchingRule but we also need to check the contents of arrays/dicts
        if fold_type(spec) is list:
            r = self.apply_rules_array(data, spec, path)
            log.debug(f'apply_rules {format_path(path)} DONE = {r!r}')
            return r
        elif fold_type(spec) is dict:
            r = self.apply_rules_dict(data, spec, path)
            log.debug(f'apply_rules {format_path(path)} DONE = {r!r}')
            return r
        elif not rule:
            # in the absence of a rule, and we're at a leaf, we fall back on equality
            log.debug('... falling back on equality matching')
            return data == spec
        return True

    def find_rule(self, path):
        section = path[0]
        section_rules = self.matching_rules.get(section)
        if not section_rules:
            return None
        log.debug(f'find_rule got {section_rules} for section {section}')
        if self.pact.semver['major'] > 2:
            # version 3 rules paths don't include the interaction section ("body", "headers", ...)
            path = path[1:]
        if section == 'body':
            # but body paths always have a '$' at the start, yes
            path = ['$'] + path
        weights = sorted((rule.weight(path), i, rule) for i, rule in enumerate(section_rules))
        log.debug(f'... path {path} got weights {weights}')
        weight, i, rule = weights[-1]
        if weight:
            return rule

    def apply_rules_array(self, data, spec, path):
        log.debug(f'apply_rules_array {data!r} {spec!r} {path!r}')
        if fold_type(data) is not list:
            return self.result.fail(f'{self.interaction_name} element is not an array (is {nice_type(data)})', path)

        if not data and not spec:
            # both arrays are empty, there's no further rules to apply
            return True

        if not spec and data:
            return self.result.fail(f'{self.interaction_name} spec requires empty array but data has contents', path)

        if spec and not data:
            return self.result.fail(f'{self.interaction_name} spec requires data in array but data is empty', path)

        # Attempt to find a matchingRule for this path elements in the array - if we find one then we use the first
        # spec value (since they must all satisfy the matchingRule and there may only be one) otherwise
        # we are comparing value to value so pass through the actual value from the spec.
        log.debug('looking for a rule')
        rule = self.find_rule(path + [0])
        if rule is not None:
            log.debug(f'... got a rule {rule}, applying to first elements')
            try:
                rule.apply(data[0], spec[0], path)
            except RuleFailed as e:
                log.debug(f'... failed: {e}')
                return self.result.fail(str(e), path)
        log.debug(f'... performing elementwise rule application')
        for i, data_elem in enumerate(data):
            # always apply matching rules using the first element of the spec array
            spec_elem = spec[0]
            p = path + [i]
            if not self.apply_rules(data_elem, spec_elem, p):
                log.debug(f'apply_rules_array {path!r} failing on item {i}')
                return False
        log.debug(f'apply_rules_array {path!r} DONE = True')
        return True

    def apply_rules_dict(self, data, spec, path):
        log.debug(f'apply_rules_dict {data!r} {spec!r} {path!r}')
        if fold_type(data) is not dict:
            return self.result.fail(f'{self.interaction_name} element is not an object (is {nice_type(data)})', path)
        for k in spec:
            p = path + [k]
            if k not in data:
                # we always flag a failure if a given key is not in the response
                return self.result.fail(f'Expected key {k!r} not in response', path)
            if not self.apply_rules(data[k], spec[k], p):
                return False
        return True


class RequestVerifier(ResponseVerifier):
    interaction_name = 'Request'

    def __init__(self, pact, interaction, result):
        self.method = interaction.get('method', MISSING)
        self.path = interaction.get('path', MISSING)
        self.query = interaction.get('query', MISSING)
        super().__init__(pact, interaction, result)

    def verify(self, request):
        log.debug(f'{self.__class__.__name__}.verify method={self.method is not MISSING} '
                  f'path={self.path is not MISSING} query={self.query is not MISSING}')
        if self.method is not MISSING and request.method.lower() != self.method.lower():
            return self.result.fail(f'Request method {request.method!r} does not match expected {self.method!r}')
        if self.path is not MISSING:
            if self.pact.semver['major'] > 1 and self.matching_rules.get('path'):
                return self.apply_rules(request.path, self.path, ['path'])
            if request.path != self.path:
                return self.result.fail(f'Request path {request.path!r} does not match expected {self.path!r}')
        if self.query is not MISSING:
            if not self.verify_query(self.query, request):
                return False
        return super().verify(request)

    def verify_query(self, spec_query, request):
        if self.pact.semver['major'] < 3:
            spec_query = parse_qs(spec_query)
        request_query = request.query
        if isinstance(request_query, str):
            request_query = parse_qs(request_query)
        if self.pact.semver['major'] > 1 and self.matching_rules.get('query'):
            if not self.apply_rules(request_query, spec_query, ['query']):
                return self.result.fail(f'Request query params {request_query} do not match '
                                        f'expected {spec_query}')
        elif request_query != spec_query:
            return self.result.fail(f'Request query {request_query!r} does not match expected {spec_query!r}')
        return True

    def compare_dict(self, data, spec, path):
        if not super().compare_dict(data, spec, path):
            return False
        # check for unexpected data in the request
        for k in data:
            if k not in spec:
                return self.result.fail(f'Unexpected data in request', path + [k])
        return True


MISSING = object()
