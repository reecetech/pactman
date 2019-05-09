import logging
from urllib.parse import parse_qs, urljoin

import requests

from .matching_rule import (RuleFailed, fold_type, nice_type, rule_matchers_v2,
                            rule_matchers_v3)
from .parse_header import parse_header
from .paths import format_path

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class ProviderStateError(Exception):
    pass


class ProviderStateMissing(ProviderStateError):
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
        self.extra_provider_headers = {}

    def __repr__(self):
        return f"<Interaction {self.pact.consumer}:{self.description}>"

    def __str__(self):
        return f"{self.pact.consumer} with request '{self.description}'"

    def verify(self, service_url, setup_url, extra_provider_headers={}):
        self.extra_provider_headers = extra_provider_headers
        self.result.start(self)
        try:
            self.set_provider_state_with_url(setup_url)
            if self.result.success:
                self.result.success = self.run_service(service_url)
        finally:
            self.result.end()

    def verify_with_callable_setup(self, service_url, provider_setup):
        self.result.start(self)
        try:
            try:
                self.set_provider_state(provider_setup)
            except ProviderStateMissing as e:
                self.result.warn(f'Unable to configure provider state: {e}')
            self.result.success = self.run_service(service_url)
        finally:
            self.result.end()

    def run_service(self, service_url):
        method = self.request['method'].upper()
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

    def set_provider_state(self, provider_setup):
        if self.providerState is not None:
            log.debug(f'Setting up provider state {self.providerState!r}')
            provider_setup(self.providerState)
            return
        if self.providerStates is None:
            log.debug(f'No provider state specified!')
            return
        for state in self.providerStates:
            if 'name' not in state:
                raise KeyError(f'provider state missing "name": {state}')
            name = state['name']
            params = state.get('params', {})
            log.debug(f"Setting up provider state {name!r} with params {params}")
            provider_setup(state['name'], **params)
            if params:
                log.info(f'Using provider state {name} with params {params}')
            else:
                log.info(f'Using provider state {name}')

    def set_provider_state_with_url(self, setup_url):
        if self.providerState is not None:
            return self.set_versioned_provider_state(setup_url, 'state', self.providerState)
        elif self.providerStates is not None:
            return self.set_versioned_provider_state(setup_url, 'states', self.providerStates)
        return True

    def set_versioned_provider_state(self, setup_url, var, state):
        log.debug(f'Setting up provider state {state!r}')
        kwargs = dict(json={
            'provider': self.pact.provider,
            'consumer': self.pact.consumer,
            var: state
        })
        if self.extra_provider_headers:
            kwargs['headers'] = self.extra_provider_headers
        try:
            r = requests.post(setup_url, **kwargs)
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
            return self.result.warn(f'Invalid provider state {state!r}')
        log.info(f'Using provider state {state!r}')
        return True

    def _get_url(self, service_url):
        return urljoin(service_url, self.request['path'])

    @property
    def _request_headers(self):
        headers = dict(self.extra_provider_headers)
        headers.update(self.request.get('headers', {}))
        return headers

    @property
    def _request_payload(self):
        return self.request.get('body')

    @property
    def _content_type_json(self):
        return 'application/json' in self._content_type

    @property
    def _content_type(self):
        return self._request_headers.get('Content-Type', 'application/json')


def rules_present(item):
    return "present" if item is not MISSING else "absent"


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

    def log_context(self):
        log.debug(f'Verifying v{self.pact.semver["major"]} Response: status={self.status}, '
                  f'headers={rules_present(self.headers)}, body={rules_present(self.body)}, '
                  f'matching rules={"present" if self.matching_rules != {} else "absent"}')

    def verify(self, response):
        self.log_context()
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
                    # In <v3 the header rules were under $.headers... but in v3 they're {'header': ...} ugh
                    if self.pact.semver['major'] > 2:
                        rule_section = 'header'
                    else:
                        rule_section = 'headers'
                    if not self.check_rules(actual, expected, [rule_section, header]):
                        log.info(f'{self.interaction_name} headers: {response.headers}')
                        return False
                    break
                else:
                    self.result.fail(f'{self.interaction_name} missing header {header!r}')
                    return False

        if self.body is not MISSING:
            if not self.check_rules(response.json(), self.body, ['body']):
                log.info(f'{self.interaction_name} data was: {response.json()}')
                return False
        return True

    def check_rules(self, data, spec, path):
        log.debug(f'check_rules data={data!r} spec={spec!r} path={format_path(path)}')
        if self.matching_rules:
            # if we have matchingRules then just look at those things
            r = self.apply_rules(data, spec, path)
        else:
            # otherwise the actual must equal the expected (excepting dict elements in actual that are unexpected)
            if path[0] in ('header', 'headers'):
                r = self.compare_header(data, spec, path)
            else:
                r = self.compare(data, spec, ['body'])
        log.debug(f'check_rules success={r!r}')
        return r

    def compare_header(self, data, spec, path):
        parsed_data = sorted(parse_header(data))
        parsed_spec = sorted(parse_header(spec))
        log.debug(f'compare_header data={parsed_data} spec={parsed_spec}')
        if parsed_data == parsed_spec:
            return True

        if path[1].lower() != 'content-type':
            return self.result.fail(f'{self.interaction_name} header {path[1]} value {data!r} does not match '
                                    f'expected {spec!r}')
        # there's a specific caveat to header matching that says that if the headers don't match and they're a
        # Content-Type and an encoding present in one and not the other, then that's OK

        # first, confirm the non-charset parts match
        data_without_charset = [part for part in parsed_data if not part.has_param('charset')]
        spec_without_charset = [part for part in parsed_spec if not part.has_param('charset')]
        if data_without_charset != spec_without_charset:
            return self.result.fail(f'{self.interaction_name} header {path[1]} value {data!r} does not match '
                                    f'expected {spec!r} (ignoring charset)')

        # now see whether the presence of the charset differs
        data_has_charset = any(part for part in parsed_data if part.has_param('charset'))
        spec_has_charset = any(part for part in parsed_spec if part.has_param('charset'))
        if data_has_charset == spec_has_charset:
            return self.result.fail(f'{self.interaction_name} header {path[1]} value {data!r} does not match '
                                    f'expected {spec!r}')
        return True

    def compare(self, data, spec, path):
        log.debug(f'compare data={data!r} spec={spec!r} path={format_path(path)}')
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
                return self.result.fail(f'{self.interaction_name} element {key!r} is missing', path)
            p = path + [key]
            if not self.compare(data[key], spec[key], p):
                return self.result.fail(f'{self.interaction_name} element {key} ({nice_type(data[key])}) '
                                        f'does not match spec ({nice_type(spec[key])})', path)
        return True

    def apply_rules(self, data, spec, path):
        # given some actual data and a pact spec at a certain path, check any rules for that path
        log.debug(f'apply_rules data={data!r} spec={spec!r} path={format_path(path)}')
        weighted_rule = self.find_rule(path)
        log.debug(f'... rule lookup got {weighted_rule}')
        if weighted_rule:
            try:
                weighted_rule.rule.apply(data, spec, path)
            except RuleFailed as e:
                log.debug(f'... failed: {e}')
                return self.result.fail(str(e), path)
            log.debug('... passed')

        # we passed the matchingRule but we also need to check the contents of arrays/dicts
        if fold_type(spec) is list:
            r = self.apply_rules_array(data, spec, path)
            log.debug(f'apply_rules {format_path(path)} success={r!r}')
            return r
        elif fold_type(spec) is dict:
            r = self.apply_rules_dict(data, spec, path)
            log.debug(f'apply_rules {format_path(path)} success={r!r}')
            return r
        elif not weighted_rule:
            if path[0] in ('header', 'headers'):
                log.debug('... falling back on header matching')
                return self.compare_header(data, spec, path)
            else:
                # in the absence of a rule, and we're at a leaf, we fall back on equality
                log.debug('... falling back on equality matching')
                return data == spec
        return True

    def find_rule(self, path):
        # rules are trickier to find because the mapping of content to matchingRules isn't 1:1 so...
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
        else:
            # version 2 paths always have a '$' at the start
            path = ['$'] + path
        weighted_rules = sorted(rule.weight(path) for rule in section_rules)
        display = [(weighted_rule.weight, weighted_rule.rule.path) for weighted_rule in weighted_rules]
        log.debug(f'... path {path} got weights {display}')
        weighted_rule = weighted_rules[-1]
        if weighted_rule.weight:
            return weighted_rule

    def apply_rules_array(self, data, spec, path):
        log.debug(f'apply_rules_array data={data!r} spec={spec!r} path={format_path(path)}')
        if fold_type(data) is not list:
            return self.result.fail(f'{self.interaction_name} element is not an array (is {nice_type(data)})', path)

        if not data and not spec:
            # both arrays are empty, there's no further rules to apply
            return True

        if not spec and data:
            return self.result.fail(f'{self.interaction_name} spec requires empty array but data has contents', path)

        if spec and not data:
            return self.result.fail(f'{self.interaction_name} spec requires data in array but data is empty', path)

        # Attempt to find a matchingRule for the elements in the array
        log.debug('iterating elements, looking for rules')
        for index, data_elem in enumerate(data):
            if not self.apply_rules_array_element(data_elem, spec, path + [index], index):
                return self.result.fail(f'apply_rules_array {path!r} failing on item {index}')
        log.debug(f'apply_rules_array {path!r} success=True')
        return True

    def apply_rules_array_element(self, data, spec, path, index):
        # we're iterating an array - attempt to find a rule for the specific data element and if
        # the index of the rule is "*" then just use the first element in the spec, otherwise use
        # the *matching* element of the spec.
        log.debug(f'apply_rules_array_element data={data!r} spec={spec!r} path={format_path(path)}')
        weighted_rule = self.find_rule(path)
        log.debug(f'... element rule lookup got {weighted_rule}')
        if len(spec) == 1 and index:
            # if the spec is a single element but data is longer there's a *good chance* that it's a sample
            # for matching rules to be applied to
            spec = spec[0]
        else:
            # element to element comparisons
            spec = spec[index]

        # now do normal rule application
        return self.apply_rules(data, spec, path)

    def apply_rules_dict(self, data, spec, path):
        log.debug(f'apply_rules_dict data={data!r} spec={spec!r} path={format_path(path)}')
        if fold_type(data) is not dict:
            return self.result.fail(f'{self.interaction_name} element is not an object (is {nice_type(data)})', path)
        for k in spec:
            p = path + [k]
            if k not in data:
                # we always flag a failure if a given key is not in the response
                return self.result.fail(f'{self.interaction_name} element {k!r} is missing', path)
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

    def log_context(self):
        log.debug(f'Verifying v{self.pact.semver["major"]} Request: method={self.method}, '
                  f'path={rules_present(self.path)}, query={rules_present(self.query)}, '
                  f'headers={rules_present(self.headers)}, body={rules_present(self.body)}, '
                  f'matching rules={"present" if self.matching_rules != {} else "absent"}')

    def verify(self, request):
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
        if isinstance(spec_query, str):
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


MISSING = 'MISSING'
