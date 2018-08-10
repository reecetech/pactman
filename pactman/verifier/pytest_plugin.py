from . import broker_pact


# add the pact broker URL to the pytest output if running verbose
def pytest_report_header(config):
    if config.getoption('verbose') > 0:
        return [f'Loading pacts from {broker_pact.PACT_BROKER_URL}']
