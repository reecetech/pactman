"""Implement verification of pacts as per specification version 2:

https://github.com/pact-foundation/pact-specification/tree/version-2
"""
import json
import logging
import os
import urllib.parse

import semver
from restnavigator import Navigator

from .result import LoggedResult
from .verify import Interaction


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


def pact_id(param):
    return repr(param)


class BrokerPacts:
    def __init__(self, provider_name, pact_broker_url=None, result=LoggedResult()):
        self.provider_name = provider_name
        self.pact_broker_url = pact_broker_url or os.environ.get('PACT_BROKER_URL')
        if not self.pact_broker_url:
            raise ValueError('pact broker URL must be specified')
        self.result = result

    def get_broker_navigator(self):
        # TODO: remove the manipulation of the URL to allow broker URLs with path components at the root
        # (this manipulation is here as an interim measure for older usages which specified a more complex
        # pact broker URL pointing to a different resource)
        url_parts = urllib.parse.urlparse(self.pact_broker_url)
        url = f'{url_parts.scheme}://{url_parts.netloc}/'
        return Navigator.hal(url, default_curie='pb')

    def consumers(self):
        nav = self.get_broker_navigator()
        broker_provider = nav['latest-provider-pacts'](provider=self.provider_name)
        broker_provider.fetch()
        for broker_pact in broker_provider['pacts']:
            pact_contents = broker_pact.fetch()
            yield BrokerPact(pact_contents, self.result, broker_pact)

    def all_interactions(self):
        for pact in self.consumers():
            yield from pact.interactions


class BrokerPact:
    def __init__(self, pact, result, broker_pact=None):
        self.result = result
        self.pact = pact
        self.provider = pact['provider']['name']
        self.consumer = pact['consumer']['name']
        self.metadata = pact['metadata']
        if 'pactSpecification' in self.metadata:
            # the Ruby implementation generates non-compliant metadata, handle that :-(
            self.version = semver.parse(self.metadata['pactSpecification']['version'])
        else:
            self.version = semver.parse(self.metadata['pact-specification']['version'])
        self.interactions = [Interaction(self, interaction, self.result) for interaction in pact['interactions']]
        self.broker_pact = broker_pact

    def __str__(self):
        return f'<Pact consumer={self.consumer} provider={self.provider}>'

    def publish_result(self, version):
        if self.broker_pact is None:
            return
        self.broker_pact['publish-verification-results'].create(dict(success=self.result.success,
                                                                     providerApplicationVersion=version))

    @classmethod
    def load_file(cls, filename, result=LoggedResult()):
        with open(filename) as file:
            return cls(json.load(file), result)
