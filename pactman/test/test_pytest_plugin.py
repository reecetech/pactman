import os

import pytest

from pactman.verifier.pytest_plugin import pytest_generate_tests


class TestConfig:
    def __init__(self, options=None):
        if options is None:
            options = {}
        self.options = options

    def getoption(self, option: str, default=None) -> str:
        return self.options.get(option, default)


class TestMetaFunc:
    fixturenames = ['pact_verifier']

    def __init__(self, config):
        self.config = config

    def parametrize(self, argnames, argvalues, indirect=False, ids=None, scope=None):
        pass


def test_requires_either_pact_broker_url_or_pact_files(cleanup_environment_variables):
    # given:
    if 'PACT_BROKER_URL' in os.environ:
        del os.environ['PACT_BROKER_URL']
    # and:
    config = TestConfig()
    metafunction = TestMetaFunc(config)

    # expect:
    with pytest.raises(ValueError) as e:
        pytest_generate_tests(metafunction)

    # then:
    assert str(e.value) == 'need a --pact-broker-url or --pact-files option'


def test_pact_broker_url_option_requires_pact_provider_name():
    # given:
    config = TestConfig({'pact_broker_url': 'foo'})
    metafunction = TestMetaFunc(config)

    # expect:
    with pytest.raises(ValueError) as e:
        pytest_generate_tests(metafunction)

    # then:
    assert str(e.value) == '--pact-broker-url requires the --pact-provider-name option'


def test_pact_broker_url_environment_variable_requires_pact_provider_name(cleanup_environment_variables):
    # given:
    os.environ['PACT_BROKER_URL'] = 'foo'
    # and:
    config = TestConfig()
    metafunction = TestMetaFunc(config)

    # expect:
    with pytest.raises(ValueError) as e:
        pytest_generate_tests(metafunction)

    # then:
    assert str(e.value) == '--pact-broker-url requires the --pact-provider-name option'


def test_pact_broker_url_can_be_loaded_from_options():
    # given:
    config = TestConfig({'pact_broker_url': 'foo', 'pact_provider_name': 'bar'})
    metafunction = TestMetaFunc(config)

    # when:
    pytest_generate_tests(metafunction)

    # then:
    # no exception thrown


def test_pact_broker_url_can_be_loaded_from_environment_variables(cleanup_environment_variables):
    # given:
    config = TestConfig({'pact_provider_name': 'bar'})
    metafunction = TestMetaFunc(config)
    # and:
    os.environ['PACT_BROKER_URL'] = 'foo'

    # when:
    pytest_generate_tests(metafunction)

    # then:
    # no exception thrown


@pytest.fixture
def cleanup_environment_variables():
    backup = {key: os.environ.get(key, None) for key in ['PACT_BROKER_URL']}
    yield
    for (k, v) in backup.items():
        if v:
            os.environ[k] = v
        elif k in os.environ:
            del os.environ[k]
