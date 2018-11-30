"""API for creating a contract and configuring the mock service."""
from __future__ import unicode_literals

import os

import semver
from pactman.mock.request import Request
from pactman.mock.response import Response
from .mock_server import getMockServer
from .mock_urlopen import MockURLOpenHandler
from .pact_request_handler import Config


USE_MOCKING_SERVER = os.environ.get('PACT_USE_MOCKING_SERVER', 'no') == 'yes'


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

    def __init__(self, consumer, provider, host_name='localhost', port=1234,
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
        :param port: The port number where the mock service is running.
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
        self.port = port
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

    @property
    def uri(self):
        return '{scheme}://{host_name}:{port}'.format(host_name=self.host_name, port=self.port, scheme=self.scheme)

    def given(self, provider_state):
        """
        Define the provider state for this pact.

        When the provider verifies this contract, they will use this field to
        setup pre-defined data that will satisfy the response expectations.

        In pact v2 the provider state is a short sentence that is unique to describe
        the provider state for this contract. For example:

            "an alligator with the given name Mary exists and the user Fred is logged in"

        In pact v3 the provider state is a list of state specifications with a name and
        associated params to define specific values for the state. For example:

            [
                {
                    "name": "an alligator with the given name exists",
                    "params": {"name" : "Mary"}
                }, {
                    "name": "the user is logged in",
                    "params" : { "username" : "Fred"}
                }
            ]

        :param provider_state: The state as described above.
        :type provider_state: basestring
        :rtype: Pact
        """
        if self.semver["major"] < 3:
            provider_state_key = 'providerState'
            if not isinstance(provider_state, str):
                raise ValueError('pact v2 provider states must be strings')
        else:
            provider_state_key = 'providerStates'
            if not isinstance(provider_state, list):
                raise ValueError('pact v3+ provider states must be lists of {name: "", params: {}} specs')
        self._interactions.insert(0, {provider_state_key: provider_state})
        return self

    def setup(self):
        self._mock_handler.setup(self._interactions)

    def start_mocking(self):
        # TODO hmm, the config is looking a lot like this Pact instance...
        config = Config(self.consumer.name, self.provider.name, self.log_dir, self.pact_dir, self.file_write_mode,
                        self.version)
        self.port = config.port
        if self.use_mocking_server:
            self._mock_handler = getMockServer(config)
        else:
            # ain't no port, we're monkey-patching (but the URLs we generate still need to look correct)
            self._mock_handler = MockURLOpenHandler(config)

    def stop_mocking(self):
        self._mock_handler.terminate()

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
            # clear the interactions once we've attempted to verify, allowing re-use of the server
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
        :type query: dict, basestring, or None
        :rtype: Pact
        """
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

    def __enter__(self):
        """
        Handler for entering a Python context.

        Sets up the mock service to expect the client requests.
        """
        self.setup()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Handler for exiting a Python context.

        Calls the mock service to verify that all interactions occurred as
        expected, and has it write out the contracts to disk.
        """
        if (exc_type, exc_val, exc_tb) != (None, None, None):
            return

        self.verify()
