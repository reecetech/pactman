"""Classes and methods to describe contract Consumers."""
import os

from .pact import Pact
from .provider import Provider


USE_MOCKING_SERVER = os.environ.get('PACT_USE_MOCKING_SERVER', 'no') == 'yes'


class Consumer(object):
    """
    A Pact consumer.

    Use this class to describe the service making requests to the provider and
    then use `has_pact_with` to create a contract with a specific service:

    >>> from pactman import Consumer, Provider
    >>> consumer = Consumer('my-web-front-end')
    >>> consumer.has_pact_with(Provider('my-backend-serivce'))
    """

    def __init__(self, name, service_cls=Pact):
        """
        Constructor for the Consumer class.

        :param name: The name of this Consumer. This will be shown in the Pact
            when it is published.
        :type name: str
        :param service_cls: Pact, or a sub-class of it, to use when creating
            the contracts. This is useful when you have a custom URL or port
            for your mock service and want to use the same value on all of
            your contracts.
        :type service_cls: pact.Pact
        """
        self.name = name
        self.service_cls = service_cls

    def has_pact_with(self, provider, host_name='localhost', port=1234,
                      log_dir=None, ssl=False, sslcert=None, sslkey=None,
                      pact_dir=None, version='2.0.0', use_mocking_server=USE_MOCKING_SERVER):
        """
        Create a contract between the `provider` and this consumer.

        If you are running the Pact mock service in a non-default location,
        you can provide the host name and port here:

        >>> from pactman import Consumer, Provider
        >>> consumer = Consumer('my-web-front-end')
        >>> consumer.has_pact_with(
        ...   Provider('my-backend-serivce'),
        ...   host_name='192.168.1.1',
        ...   port=8000)

        :param provider: The provider service for this contract.
        :type provider: pact.Provider
        :param host_name: An optional host name to use when contacting the
            Pact mock service. This will need to be the same host name used by
            your code under test to contact the mock service. It defaults to:
            `localhost`.
        :type host_name: str
        :param port: The TCP port to use when contacting the Pact mock service.
            This will need to tbe the same port used by your code under test
            to contact the mock service. It defaults to: 1234
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
        :param use_mocking_server: If True the mocking will be done using a
            HTTP server rather than patching urllib3 connections. Can be set
            by the environment variable PACT_USE_MOCKING_SERVER which has
            values "no" (default) or "yes".
        :type use_mocking_server: bool
        :return: A Pact object which you can use to define the specific
            interactions your code will have with the provider.
        :rtype: pact.Pact
        """
        if not isinstance(provider, (Provider,)):
            raise ValueError(
                'provider must be an instance of the Provider class.')

        return self.service_cls(
            consumer=self,
            provider=provider,
            host_name=host_name,
            port=port,
            log_dir=log_dir,
            ssl=ssl,
            sslcert=sslcert,
            sslkey=sslkey,
            pact_dir=pact_dir,
            version=version,
            use_mocking_server=use_mocking_server,
        )
