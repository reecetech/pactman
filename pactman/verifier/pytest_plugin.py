import glob
import os

import pytest

from .broker_pact import BrokerPact, BrokerPacts
from .result import PytestResult


def pytest_addoption(parser):
    parser.addoption("--pact-files", default=None,
                     help="pact JSON files to verify (wildcards allowed)")
    parser.addoption("--pact-broker-url", default='',
                     help="pact broker URL")
    parser.addoption("--provider-name", default=None,
                     help="provider pact name")
    parser.addoption("--publish-results", action="store_true", default=False,
                     help="report pact results to pact broker")
    parser.addoption("--provider-version", default=None,
                     help="provider version to use when reporting pact results to pact broker")


def get_broker_url(config):
    if config.getoption('pact_broker_url'):
        return config.getoption('pact_broker_url')
    if os.environ.get('PACT_BROKER_URL'):
        return os.environ.get('PACT_BROKER_URL')
    return None


# add the pact broker URL to the pytest output if running verbose
def pytest_report_header(config):
    if config.getoption('verbose') > 0:
        location = get_broker_url(config) or config.getoption('pact_files')
        return [f'Loading pacts from {location}']


class PytestPactVerifier:
    def __init__(self, publish_results, provider_version, interaction_or_pact):
        self.publish_results = publish_results
        self.provider_version = provider_version
        self.interaction_or_pact = interaction_or_pact

    def verify(self, provider_url, provider_setup):
        if isinstance(self.interaction_or_pact, BrokerPact):
            if self.publish_results and self.provider_version:
                self.interaction_or_pact.publish_result(self.provider_version)
            assert self.interaction_or_pact.success, f'Verification of {self.interaction_or_pact} failed'
        else:
            self.interaction_or_pact.verify_with_callable_setup(provider_url, provider_setup)


def flatten_pacts(pacts, with_consumer=True):
    for consumer in pacts:
        yield from consumer.interactions
        if with_consumer:
            yield consumer


def get_pact_files(file_location):
    if not file_location:
        return []
    for filename in glob.glob(file_location):
        yield BrokerPact.load_file(filename, result_factory=PytestResult)


def pytest_generate_tests(metafunc):
    if 'pact_verifier' in metafunc.fixturenames:
        broker_url = get_broker_url(metafunc.config)
        if not broker_url:
            pact_files = get_pact_files(metafunc.config.getoption('pact_files'))
            if not pact_files:
                raise ValueError('need a --pact-broker-url or --pact-files option')
            metafunc.parametrize("pact_verifier", flatten_pacts(pact_files, with_consumer=False), ids=str,
                                 indirect=True)
        else:
            provider_name = metafunc.config.getoption('provider_name')
            if not provider_name:
                raise ValueError('--pact-broker-url requires the --provider-name option')
            broker_pacts = BrokerPacts(provider_name, pact_broker_url=broker_url, result_factory=PytestResult)
            metafunc.parametrize("pact_verifier", flatten_pacts(broker_pacts.consumers()),
                                 ids=str, indirect=True)


@pytest.fixture()
def pact_verifier(pytestconfig, request):
    return PytestPactVerifier(pytestconfig.getoption('publish_results'), pytestconfig.getoption('provider_version'),
                              request.param)
