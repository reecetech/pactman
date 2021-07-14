import glob
import logging
import os
import warnings

import pytest
from _pytest.outcomes import Failed
from _pytest.reports import TestReport

from .broker_pact import BrokerPact, BrokerPacts, PactBrokerConfig
from .result import PytestResult, log


def pytest_addoption(parser):
    group = parser.getgroup("pact specific options (pactman)")
    group.addoption(
        "--pact-files", default=None, help="pact JSON files to verify (wildcards allowed)"
    )
    group.addoption("--pact-broker-url", default="", help="pact broker URL")
    group.addoption("--pact-broker-token", default="", help="pact broker bearer token")
    group.addoption(
        "--pact-provider-name", default=None, help="pact name of provider being verified"
    )
    group.addoption(
        "--pact-consumer-name",
        default=None,
        help="consumer name to limit pact verification to - "
             "DEPRECATED, use --pact-verify-consumer instead",
    )
    group.addoption(
        "--pact-verify-consumer", default=None, help="consumer name to limit pact verification to"
    )
    group.addoption(
        "--pact-verify-consumer-tag",
        metavar="TAG",
        action="append",
        help="limit broker pacts verified to those matching the tag. May be "
             "specified multiple times in which case pacts matching any of these "
             "tags will be verified.",
    )
    group.addoption(
        "--pact-publish-results",
        action="store_true",
        default=False,
        help="report pact verification results to pact broker",
    )
    group.addoption(
        "--pact-provider-version",
        default=None,
        help="provider version to use when reporting pact results to pact broker",
    )
    group.addoption(
        "--pact-allow-fail",
        default=False,
        action="store_true",
        help="do not fail the pytest run if any pacts fail verification",
    )


# Future options to be implemented. Listing them here so naming consistency can be a thing.
#    group.addoption("--pact-publish-pacts", action="store_true", default=False,
#                    help="publish pacts to pact broker")
#    group.addoption("--pact-consumer-version", default=None,
#                    help="consumer version to use when publishing pacts to the broker")
#    group.addoption("--pact-consumer-version-source", default=None,
#                    help="generate consumer version from source 'git-tag' or 'git-hash'")
#    group.addoption("--pact-consumer-version-tag", metavar='TAG', action="append",
#                    help="tag(s) that should be applied to the consumer version when pacts "
#                         "are uploaded to the broker; multiple tags may be supplied")


def get_broker_url(config):
    return config.getoption("pact_broker_url") or os.environ.get("PACT_BROKER_URL")


def get_provider_name(config):
    return config.getoption("pact_provider_name") or os.environ.get("PACT_PROVIDER_NAME")


# add the pact broker URL to the pytest output if running verbose
def pytest_report_header(config):
    if config.getoption("verbose") > 0:
        location = get_broker_url(config) or config.getoption("pact_files")
        return [f"Loading pacts from {location}"]


def pytest_configure(config):
    logging.getLogger("pactman").handlers = []
    logging.basicConfig(format="%(message)s")
    verbosity = config.getoption("verbose")
    if verbosity > 0:
        log.setLevel(logging.DEBUG)


class PytestPactVerifier:
    def __init__(self, publish_results, provider_version, interaction, consumer):
        self.publish_results = publish_results
        self.provider_version = provider_version
        self.interaction = interaction
        self.consumer = consumer

    def verify(self, provider_url, provider_setup, extra_provider_headers={}):
        try:
            self.interaction.verify_with_callable_setup(provider_url, provider_setup, extra_provider_headers)
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


def load_pact_files(file_location):
    for filename in glob.glob(file_location,  recursive=True):
        yield BrokerPact.load_file(filename, result_factory=PytestResult)


def test_id(identifier):
    interaction, _ = identifier
    return str(interaction)


def pytest_generate_tests(metafunc):
    if "pact_verifier" in metafunc.fixturenames:
        broker_url = get_broker_url(metafunc.config)
        if not broker_url:
            pact_files_location = metafunc.config.getoption("pact_files")
            if not pact_files_location:
                raise ValueError("need a --pact-broker-url or --pact-files option")
            pact_files = load_pact_files(pact_files_location)
            metafunc.parametrize(
                "pact_verifier", flatten_pacts(pact_files), ids=test_id, indirect=True
            )
        else:
            provider_name = get_provider_name(metafunc.config)
            if not provider_name:
                raise ValueError("--pact-broker-url requires the --pact-provider-name option")
            broker = PactBrokerConfig(
                broker_url,
                metafunc.config.getoption("pact_broker_token"),
                metafunc.config.getoption("pact_verify_consumer_tag", []),
            )
            broker_pacts = BrokerPacts(
                provider_name, pact_broker=broker, result_factory=PytestResult
            )
            pacts = broker_pacts.consumers()
            filter_consumer_name = metafunc.config.getoption("pact_verify_consumer")
            if not filter_consumer_name:
                filter_consumer_name = metafunc.config.getoption("pact_consumer_name")
                if filter_consumer_name:
                    warnings.warn(
                        "The --pact-consumer-name command-line option is deprecated "
                        "and will be removed in the 3.0.0 release.",
                        DeprecationWarning,
                    )
            if filter_consumer_name:
                pacts = [pact for pact in pacts if pact.consumer == filter_consumer_name]
            metafunc.parametrize("pact_verifier", flatten_pacts(pacts), ids=test_id, indirect=True)


class PactTestReport(TestReport):
    """Custom TestReport that allows us to attach an interaction to the result, and
    then display the interaction's verification result ouput as well as the traceback
    of the failure.
    """

    @classmethod
    def from_item_and_call(cls, item, call, interaction):
        report = super().from_item_and_call(item, call)
        report.pact_interaction = interaction
        # the toterminal() call can't reasonably get at this config, so we store it here
        report.verbosity = item.config.option.verbose
        return report

    def toterminal(self, out):
        out.line("Pact failure details:", bold=True)
        for text, kw in self.pact_interaction.result.results_for_terminal():
            out.line(text, **kw)
        if self.verbosity > 0:
            out.line("Traceback:", bold=True)
            return super().toterminal(out)
        else:
            out.line("Traceback not shown, use pytest -v to show it")


def pytest_runtest_makereport(item, call):
    if call.when != "call" or "pact_verifier" not in getattr(item, "fixturenames", []):
        return
    # use our custom TestReport subclass if we're reporting on a pact verification call
    interaction = item.funcargs["pact_verifier"].interaction
    report = PactTestReport.from_item_and_call(item, call, interaction)
    if report.failed and item.config.getoption("pact_allow_fail"):
        # convert the fail into an "expected" fail, which allows the run to pass
        report.wasxfail = True
        report.outcome = "passed"
    return report


def pytest_report_teststatus(report, config):
    if not hasattr(report, "pact_interaction"):
        return
    if hasattr(report, "wasxfail"):
        # wasxfail usually displays an "X" but since it's not *expected* to fail an "f" is a little clearer
        return "ignore fail", "f", "IGNORE_FAIL"


@pytest.fixture()
def pact_verifier(pytestconfig, request):
    interaction, consumer = request.param
    p = PytestPactVerifier(
        pytestconfig.getoption("pact_publish_results"),
        pytestconfig.getoption("pact_provider_version"),
        interaction,
        consumer,
    )
    yield p
    p.finish()
