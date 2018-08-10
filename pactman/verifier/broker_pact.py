"""Implement verification of pacts as per specification version 2:

https://github.com/pact-foundation/pact-specification/tree/version-2
"""
import json
import logging
import os

import coreapi
import semver
from coreapi import utils as coreapi_utils

from .result import LoggedResult
from .verify import Interaction


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


def pact_id(param):
    return repr(param)


PACT_BROKER_URL = os.environ.get('PACT_BROKER_URL', 'http://pact-broker-dev.reecenet.org/pacts/provider/{}/latest')


# Construct the coreapi client passing in the decoders explicitly so it uses all the installed
# codecs rather than its limited subset "default". RJ: I believe the need to do this is a bug in coreapi
coreapi_client = coreapi.Client(decoders=coreapi_utils.get_installed_codecs().values())


class BrokerPacts:
    def __init__(self, provider_name, pact_broker_url=None, result=LoggedResult()):
        self.pact_broker_url = (pact_broker_url or PACT_BROKER_URL).format(provider_name)
        self.hal = coreapi_client.get(self.pact_broker_url)
        self.result = result

    def consumers(self):
        for pact_name in self.hal['pacts']:
            hal = coreapi_client.action(self.hal, ['pacts', pact_name])
            yield BrokerPact(hal, self.result)

    def all_interactions(self):
        for pact in self.consumers():
            yield from pact.interactions


class BrokerPact:
    def __init__(self, hal, result):
        self.hal = hal
        self.result = result
        self.provider = hal['provider']['name']
        self.consumer = hal['consumer']['name']
        self.metadata = hal['metadata']
        if 'pactSpecification' in self.metadata:
            # the Ruby implementation generates non-compliant metadata, handle that :-(
            self.version = semver.parse(self.metadata['pactSpecification']['version'])
        else:
            self.version = semver.parse(self.metadata['pact-specification']['version'])
        self.interactions = [Interaction(self, interaction, self.result) for interaction in hal['interactions']]

    def __str__(self):
        return f'<Pact consumer={self.consumer} provider={self.provider}>'

    def publish_result(self, version):
        # well, this doesn't look like freakin' black magic AT ALL!!
        params = dict(success=self.result.success, providerApplicationVersion=version)
        overrides = dict(action='POST', encoding='application/json',
                         fields=[coreapi.Field(name='success'),
                                 coreapi.Field(name='providerApplicationVersion')])
        coreapi_client.action(self.hal, ['publish-verification-results'], params=params, overrides=overrides,
                              validate=False)
        # this being the requests version....
        # response = requests.post(self.hal['publish-verification-results'].url, json=params)
        # return response.ok

    @classmethod
    def load_file(cls, filename, result=LoggedResult()):
        with open(filename) as file:
            return cls(json.load(file), result)
