"""Implement verification of pacts as per specification version 2:

https://github.com/pact-foundation/pact-specification/tree/version-2
"""
import json
import os
import urllib.parse

import semver
from restnavigator import Navigator

from .result import LoggedResult
from .verify import Interaction


def pact_id(param):
    return repr(param)


class PactBrokerConfig:
    def __init__(self, url=None, token=None):
        url = url or os.environ.get('PACT_BROKER_URL')
        if not url:
            raise ValueError('pact broker URL must be specified')

        # pull the hostname and optionally any basic auth from the broker URL
        # (backwards compat to once upon a time when the broker config URL was specified with a path)
        url_parts = urllib.parse.urlparse(url)
        host = netloc = url_parts.netloc
        self.auth = None
        if '@' in netloc:
            url_auth, host = netloc.split('@')
            self.auth = tuple(url_auth.split(':'))
        self.url = f'{url_parts.scheme}://{host}/'

        if not self.auth:
            auth = os.environ.get('PACT_BROKER_AUTH')
            if auth:
                self.auth = tuple(auth.split(':'))

        token = token or os.environ.get('PACT_BROKER_TOKEN')
        self.headers = None
        if token:
            self.headers = {'Authorization': f'Bearer {token}'}

    def get_broker_navigator(self):
        return Navigator.hal(self.url, default_curie='pb', auth=self.auth, headers=self.headers)


class BrokerPacts:
    def __init__(self, provider_name, pact_broker_config=None, result_factory=LoggedResult):
        self.provider_name = provider_name
        self.pact_broker_config = pact_broker_config or PactBrokerConfig()
        self.result_factory = result_factory

    def consumers(self):
        nav = self.pact_broker_config.get_broker_navigator()
        try:
            broker_provider = nav['latest-provider-pacts'](provider=self.provider_name)
        except Exception as e:
            raise ValueError(f'error fetching pacts from {self.pact_broker_config.url} for {self.provider_name}: {e}')
        broker_provider.fetch()
        for broker_pact in broker_provider['pacts']:
            pact_contents = broker_pact.fetch()
            yield BrokerPact(pact_contents, self.result_factory, broker_pact)

    def all_interactions(self):
        for pact in self.consumers():
            yield from pact.interactions

    def __iter__(self):
        return self.all_interactions()


class BrokerPact:
    def __init__(self, pact, result_factory, broker_pact=None):
        self.pact = pact
        self.provider = pact['provider']['name']
        self.consumer = pact['consumer']['name']
        self.metadata = pact['metadata']
        if 'pactSpecification' in self.metadata:
            # the Ruby implementation generates non-compliant metadata, handle that :-(
            self.version = self.metadata['pactSpecification']['version']
        else:
            self.version = self.metadata['pact-specification']['version']
        self.semver = semver.parse(self.version)
        self.interactions = [Interaction(self, interaction, result_factory) for interaction in pact['interactions']]
        self.broker_pact = broker_pact

    def __repr__(self):
        return f'<Pact consumer={self.consumer} provider={self.provider}>'

    def __str__(self):
        return f'Pact between consumer {self.consumer} and provider {self.provider}'

    @property
    def success(self):
        return all(interaction.result.success for interaction in self.interactions)

    def publish_result(self, version):
        if self.broker_pact is None:
            return
        self.broker_pact['publish-verification-results'].create(dict(success=self.success,
                                                                     providerApplicationVersion=version))

    @classmethod
    def load_file(cls, filename, result_factory=LoggedResult):
        with open(filename) as file:
            return cls(json.load(file), result_factory)
