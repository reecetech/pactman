import glob
import logging
import pytest
import os
from _pytest.outcomes import Failed

from .broker_pact import BrokerPact, BrokerPacts
from .result import log, PytestResult


def pytest_addoption(parser):
    parser.addoption("--pact-files", default=None,
                     help="pact JSON files to verify (wildcards allowed)")
    parser.addoption("--pact-broker-url", default='',
                     help="pact broker URL")
    parser.addoption("--pact-provider-name", default=None,
                     help="provider pact name")
    parser.addoption("--pact-consumer-name", default=None,
                     help="consumer to limit verification to")
    parser.addoption("--pact-publish-results", action="store_true", default=False,
                     help="report pact results to pact broker")
    parser.addoption("--pact-provider-version", default=None,
                     help="provider version to use when reporting pact results to pact broker")


def get_broker_url(config):
    return config.getoption('pact_broker_url') or os.environ.get('PACT_BROKER_URL')


# add the pact broker URL to the pytest output if running verbose
def pytest_report_header(config):
    if config.getoption('verbose') > 0:
        location = get_broker_url(config) or config.getoption('pact_files')
        return [f'Loading pacts from {location}']


def pytest_configure(config):
    logging.getLogger('pactman').handlers = []
    logging.basicConfig(format='%(message)s')
    verbosity = config.getoption('verbose')
    if verbosity > 0:
        log.setLevel(logging.DEBUG)


class PytestPactVerifier:
    def __init__(self, publish_results, provider_version, interaction, consumer):
        self.publish_results = publish_results
        self.provider_version = provider_version
        self.interaction = interaction
        self.consumer = consumer

    def verify(self, provider_url, provider_setup):
        try:
            self.interaction.verify_with_callable_setup(provider_url, provider_setup)
        except (Failed, AssertionError) as e:
            raise Failed(str(e)) from None

    def finish(self):
        if self.consumer and self.publish_results and self.provider_version:
            self.consumer.publish_result(self.provider_version)


def flatten_pacts(pacts):
    for consumer in pacts:
        last = consumer.interactions[-1]
        for interaction in consumer.interactions:
            if interaction is last:
                yield (interaction, consumer)
            else:
                yield (interaction, None)


def get_pact_files(file_location):
    if not file_location:
        return []
    for filename in glob.glob(file_location):
        yield BrokerPact.load_file(filename, result_factory=PytestResult)


def test_id(identifier):
    interaction, _ = identifier
    return str(interaction)


def pytest_generate_tests(metafunc):
    if 'pact_verifier' in metafunc.fixturenames:
        broker_url = get_broker_url(metafunc.config)
        if not broker_url:
            pact_files = get_pact_files(metafunc.config.getoption('pact_files'))
            if not pact_files:
                raise ValueError('need a --pact-broker-url or --pact-files option')
            metafunc.parametrize("pact_verifier", flatten_pacts(pact_files), ids=test_id, indirect=True)
        else:
            provider_name = metafunc.config.getoption('pact_provider_name')
            if not provider_name:
                raise ValueError('--pact-broker-url requires the --pact-provider-name option')
            broker_pacts = BrokerPacts(provider_name, pact_broker_url=broker_url, result_factory=PytestResult)
            pacts = broker_pacts.consumers()
            filter_consumer_name = metafunc.config.getoption('pact_consumer_name')
            if filter_consumer_name:
                pacts = [pact for pact in pacts if pact.consumer == filter_consumer_name]
            metafunc.parametrize("pact_verifier", flatten_pacts(pacts), ids=test_id, indirect=True)


@pytest.fixture()
def pact_verifier(pytestconfig, request):
    interaction, consumer = request.param
    p = PytestPactVerifier(pytestconfig.getoption('pact_publish_results'),
                           pytestconfig.getoption('pact_provider_version'),
                           interaction, consumer)
    yield p
    p.finish()
