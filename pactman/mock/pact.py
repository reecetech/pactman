"""API for creating a contract and configuring the mock service."""
from __future__ import unicode_literals

import os

import semver

from ..mock.request import Request
from ..mock.response import Response
from .mock_server import getMockServer
from .mock_urlopen import MockURLOpenHandler

USE_MOCKING_SERVER = os.environ.get('PACT_USE_MOCKING_SERVER', 'no') == 'yes'


def ensure_pact_dir(pact_dir):
    if not os.path.exists(pact_dir):
        parent_dir = os.path.dirname(pact_dir)
        if not os.path.exists(parent_dir):
            raise ValueError(f'Pact destination directory {pact_dir} does not exist')
        os.mkdir(pact_dir)


class Pact(object):
    """
    Represents a contract between a consumer and provider.

    Provides Python context handlers to configure the Pact mock service to
    perform tests on a Python consumer. For example:

    >>> from pactman import Consumer, Provider
    >>> pact = Consumer('consumer').has_pact_with(Provider('provider'))
    >>> (pact.given('the echo service is available')
    ...  .upon_receiving('a request is made to the echo service')
    ...  .with_request('get', '/echo', query={'text': 'Hello!'})
    ...  .will_respond_with(200, body='Hello!'))
    >>> with pact:
    ...   requests.get(pact.uri + '/echo?text=Hello!')

    The GET request is made to the mock service, which will verify that it
    was a GET to /echo with a query string with a key named `text` and its
    value is `Hello!`. If the request does not match an error is raised, if it
    does match the defined interaction, it will respond with the text `Hello!`.
    """

    HEADERS = {'X-Pact-Mock-Service': 'true'}

    def __init__(self, consumer, provider, host_name='localhost', port=None,
                 log_dir=None, ssl=False, sslcert=None, sslkey=None,
                 pact_dir=None, version='2.0.0',
                 file_write_mode='overwrite', use_mocking_server=USE_MOCKING_SERVER):
        """
        Constructor for Pact.

        :param consumer: The consumer for this contract.
        :type consumer: pact.Consumer
        :param provider: The provider for this contract.
        :type provider: pact.Provider
        :param host_name: The host name where the mock service is running.
        :type host_name: str
        :param port: The port number where the mock service is running. Defaults
            to a port >= 8050.
        :type port: int
        :param log_dir: The directory where logs should be written. Defaults to
            the current directory.
        :type log_dir: str
        :param ssl: Flag to control the use of a self-signed SSL cert to run
            the server over HTTPS , defaults to False.
        :type ssl: bool
        :param sslcert: Path to a custom self-signed SSL cert file, 'ssl'
            option must be set to True to use this option. Defaults to None.
        :type sslcert: str
        :param sslkey: Path to a custom key and self-signed SSL cert key file,
            'ssl' option must be set to True to use this option.
            Defaults to None.
        :type sslkey: str
        :param pact_dir: Directory where the resulting pact files will be
            written. Defaults to the current directory.
        :type pact_dir: str
        :param version: The Pact Specification version to use, defaults to
            '2.0.0'.
        :type version: str
        :param file_write_mode: `overwrite` or `merge`. Use `merge` when
            running multiple mock service instances in parallel for the same
            consumer/provider pair. Ensure the pact file is deleted before
            running tests when using this option so that interactions deleted
            from the code are not maintained in the file. Defaults to
            `overwrite`.
        :type file_write_mode: str
        :param use_mocking_server: If True the mocking will be done using a
            HTTP server rather than patching urllib3 connections.
        :type use_mocking_server: bool
        """
        self.scheme = 'https' if ssl else 'http'
        self.consumer = consumer
        self.file_write_mode = file_write_mode
        self.host_name = host_name
        self.log_dir = log_dir or os.getcwd()
        self.pact_dir = pact_dir or os.getcwd()
        self.port = port or self.allocate_port()
        self.provider = provider
        # TODO implement SSL
        self.ssl = ssl
        self.sslcert = sslcert
        self.sslkey = sslkey
        self.version = version
        self.semver = semver.parse(self.version)
        self.use_mocking_server = use_mocking_server
        self._interactions = []
        self._mock_handler = None
        self._pact_dir_checked = False
        self._enter_count = 0

    @property
    def uri(self):
        return '{scheme}://{host_name}:{port}'.format(host_name=self.host_name, port=self.port, scheme=self.scheme)

    BASE_PORT_NUMBER = 8150

    @classmethod
    def allocate_port(cls):
        cls.BASE_PORT_NUMBER += 5
        return cls.BASE_PORT_NUMBER

    def check_existing_file(self):
        # ensure destination directory exists
        if self.file_write_mode == 'never':
            return
        if self._pact_dir_checked:
            return
        self._pact_dir_checked = True
        ensure_pact_dir(self.pact_dir)
        if self.file_write_mode == 'overwrite':
            if os.path.exists(self.pact_json_filename):
                os.remove(self.pact_json_filename)

    @property
    def pact_json_filename(self):
        self.check_existing_file()
        return os.path.join(self.pact_dir, f'{self.consumer.name}-{self.provider.name}-pact.json')

    def given(self, provider_state, **params):
        """
        Define the provider state for this pact.

        When the provider verifies this contract, they will use this field to
        setup pre-defined data that will satisfy the response expectations.

        In pact v2 the provider state is a short sentence that is unique to describe
        the provider state for this contract. For example:

            "an alligator with the given name Mary exists and the spam nozzle is operating"

        In pact v3 the provider state is a list of state specifications with a name and
        associated params to define specific values for the state. This may be provided
        in two ways. Either call with a single list, for example:

            [
                {
                    "name": "an alligator with the given name exists",
                    "params": {"name" : "Mary"}
                }, {
                    "name": "the spam nozzle is operating",
                    "params" : {}
                }
            ]

        or for convenience call `.given()` with a string as in v2, which implies a single
        provider state, with params taken from keyword arguments like so:

            .given("an alligator with the given name exists", name="Mary")

        If additional provider states are required for a v3 pact you may either use the list
        form above, or make an additional call to `.and_given()`.

        If you don't have control over the provider, and they cannot implement a provider
        state, you may use an explicit `None` for the provider state value. This is
        discouraged as it introduces fragile external dependencies in your tests.

        :param provider_state: The state as described above.
        :type provider_state: string or list as above
        :rtype: Pact
        """
        if provider_state is None:
            self._interactions.insert(0, {})
            return self

        if self.semver["major"] < 3:
            provider_state_key = 'providerState'
            if not isinstance(provider_state, str):
                raise ValueError('pact v2 provider states must be strings')
        else:
            provider_state_key = 'providerStates'
            if isinstance(provider_state, str):
                provider_state = [{'name': provider_state, 'params': params}]
            elif not isinstance(provider_state, list):
                raise ValueError('pact v3+ provider states must be lists of {name: "", params: {}} specs')
        self._interactions.insert(0, {provider_state_key: provider_state})
        return self

    def and_given(self, provider_state, **params):
        """
        Define an additional provider state for this pact.

        Supply the provider state name and any params taken in keyword arguments like so:

            .given("an alligator with the given name exists", name="Mary")

        :param provider_state: The state as described above.
        :type provider_state: string or list as above
        :rtype: Pact
        """
        if self.semver["major"] < 3:
            raise ValueError('pact v2 only allows a single provider state')
        elif not self._interactions:
            raise ValueError('only invoke and_given() after given()')
        self._interactions[-1]['providerStates'].append({'name': provider_state, 'params': params})
        return self

    def setup(self):
        self._mock_handler.setup(self._interactions)

    def start_mocking(self):
        if self.use_mocking_server:
            self._mock_handler = getMockServer(self)
        else:
            # ain't no port, we're monkey-patching (but the URLs we generate still need to look correct)
            self._mock_handler = MockURLOpenHandler(self)

    def stop_mocking(self):
        self._mock_handler.terminate()
        self._mock_handler = None

    # legacy pact-python API support
    start_service = start_mocking
    stop_service = stop_mocking

    def upon_receiving(self, scenario):
        """
        Define the name of this contract.

        :param scenario: A unique name for this contract.
        :type scenario: basestring
        :rtype: Pact
        """
        self._interactions[0]['description'] = scenario
        return self

    def verify(self):
        """
        Have the mock service verify all interactions occurred.

        Calls the mock service to verify that all interactions occurred as
        expected, and has it write out the contracts to disk.

        :raises AssertionError: When not all interactions are found.
        """
        try:
            self._mock_handler.verify()
        finally:
            # clear the interactions once we've attempted to verify, allowing re-use of the mock
            self._interactions[:] = []

    def with_request(self, method, path, body=None, headers=None, query=None):
        """
        Define the request the request that the client is expected to perform.

        :param method: The HTTP method.
        :type method: str
        :param path: The path portion of the URI the client will access.
        :type path: str, Matcher
        :param body: The request body, can be a string or an object that will
            serialize to JSON, like list or dict, defaults to None.
        :type body: list, dict or None
        :param headers: The headers the client is expected to include on with
            this request. Defaults to None.
        :type headers: dict or None
        :param query: The query options the client is expected to send. Can be
            a dict of keys and values, or a URL encoded string.
            Defaults to None.
        :type query: dict, str, or None
        :rtype: Pact
        """
        # ensure all query values are lists of values
        if isinstance(query, dict):
            for k, v in query.items():
                if isinstance(v, str):
                    query[k] = [v]
        self._interactions[0]['request'] = Request(
            method, path, body=body, headers=headers, query=query).json(self.version)
        return self

    def will_respond_with(self, status, headers=None, body=None):
        """
        Define the response the server is expected to create.

        :param status: The HTTP status code.
        :type status: int
        :param headers: All required headers. Defaults to None.
        :type headers: dict or None
        :param body: The response body, or a collection of Matcher objects to
            allow for pattern matching. Defaults to None.
        :type body: Matcher, dict, list, basestring, or None
        :rtype: Pact
        """
        self._interactions[0]['response'] = Response(status,
                                                     headers=headers,
                                                     body=body).json(self.version)
        return self

    _auto_mocked = False

    def __enter__(self):
        """
        Handler for entering a Python context.

        Sets up the mock service to expect the client requests.
        """
        if not self.use_mocking_server and not self._mock_handler:
            self._auto_mocked = True
            self.start_mocking()

        self.setup()
        self._enter_count += 1

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Handler for exiting a Python context.

        Calls the mock service to verify that all interactions occurred as
        expected, and has it write out the contracts to disk.
        """
        self._enter_count -= 1

        if (exc_type, exc_val, exc_tb) != (None, None, None):
            # let the exception go through to the keeper
            return

        # don't invoke teardown until all interactions for this pact are exited
        if self._enter_count:
            return

        self.verify()

        if not self.use_mocking_server and self._auto_mocked:
            self.stop_mocking()

    def construct_pact(self, interaction):
        """Construct a pact JSON data structure for the interaction.
        """
        return dict(
            consumer={"name": self.consumer.name},
            provider={"name": self.provider.name},
            interactions=[interaction],
            metadata=dict(pactSpecification=dict(version=self.version)),
        )
