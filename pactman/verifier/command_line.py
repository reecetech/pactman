import argparse
import logging
from functools import partial

from colorama import Fore, Style, init

from ..__version__ import __version__
from .broker_pact import BrokerPact, BrokerPacts, log
from .paths import format_path
from .result import Result

# TODO: add these options, which exist in the ruby command line?
'''
@click.option(
    'username', '--pact-broker-username',
    help='Username for Pact Broker basic authentication.')
@click.option(
    'password', '--pact-broker-password',
    envvar='PACT_BROKER_PASSWORD',
    help='Password for Pact Broker basic authentication. Can also be specified'
         ' via the environment variable PACT_BROKER_PASSWORD')
@click.option(
    'header', '--custom-provider-header',
    envvar='CUSTOM_PROVIDER_HEADER',
    help='Header to add to provider state set up and '
         'pact verification requests. '
         'eg \'Authorization: Basic cGFjdDpwYWN0\'. '
         'May be specified multiple times.')
@click.option(
    'timeout', '-t', '--timeout',
    default=30,
    help='The duration in seconds we should wait to confirm verification'
         ' process was successful. Defaults to 30.',
    type=int)
'''

parser = argparse.ArgumentParser(description='Verify pact contracts')

parser.add_argument('provider_name', metavar='PROVIDER_NAME',
                    help='the name of the provider being verified')

parser.add_argument('provider_url', metavar='PROVIDER_URL',
                    help='the URL of the provider service')

parser.add_argument('provider_setup_url', metavar='PROVIDER_SETUP_URL',
                    help='the URL to provider state setup')

parser.add_argument('-b', '--broker-url', default=None,
                    help='the URL of the pact broker; may also be provided in PACT_BROKER_URL environment variable')

parser.add_argument('-l', '--local-pact-file', default=None,
                    help='path to a local pact file')

parser.add_argument('-c', '--consumer', default=None,
                    help='the name of the consumer to test')

parser.add_argument('-r', '--publish-verification-results', default=False, action='store_true',
                    help='send verification results to the pact broker')

parser.add_argument('-a', '--provider-app-version', default=None,
                    help='provider application version, required for results publication (same as -p)')

parser.add_argument('-p', '--provider-version', default=None,
                    help='provider application version, required for results publication (same as -a)')

parser.add_argument('-v', '--verbose', default=False, action='store_true',
                    help='output more information about the verification')

parser.add_argument('-q', '--quiet', default=False, action='store_true',
                    help='output less information about the verification')

parser.add_argument('-V', '--version', default=False, action='version', version=f'%(prog)s {__version__}')


class CaptureResult(Result):
    def __init__(self, *, level=logging.WARNING):
        self.messages = []
        self.level = level
        self.current_consumer = None

    def start(self, interaction):
        super().start(interaction)
        log = logging.getLogger('pactman')
        log.handlers = [self]
        log.setLevel(logging.DEBUG)
        self.messages[:] = []
        if self.current_consumer != interaction.pact.consumer:
            print(f'{Style.BRIGHT}Consumer: {interaction.pact.consumer}')
            self.current_consumer = interaction.pact.consumer
        print(f'Request: "{interaction.description}" ... ', end='')

    def end(self):
        if self.success:
            print(Fore.GREEN + 'PASSED')
        else:
            print(Fore.RED + 'FAILED')
        if self.messages:
            print((Fore.RESET + '\n').join(self.messages))

    def fail(self, message, path=None):
        self.success = self.FAIL
        if path:
            message += ' at ' + format_path(path)
        log.error(message)
        return not message

    def handle(self, record):
        color = ''
        if record.levelno >= logging.ERROR:
            color = Fore.RED
        elif record.levelno >= logging.WARNING:
            color = Fore.YELLOW
        self.messages.append(' ' + color + record.msg)


def main():
    init(autoreset=True)
    args = parser.parse_args()
    provider_version = args.provider_version or args.provider_app_version
    if args.publish_verification_results and not provider_version:
        print('Provider version is required to publish results to the broker')
        return False
    if args.quiet:
        result_log_level = logging.WARNING
    elif args.verbose:
        result_log_level = logging.DEBUG
    else:
        result_log_level = logging.INFO
    result_factory = partial(CaptureResult, level=result_log_level)
    if args.local_pact_file:
        pacts = [BrokerPact.load_file(args.local_pact_file, result_factory)]
    else:
        pacts = BrokerPacts(args.provider_name, args.broker_url, result_factory).consumers()
    success = True
    for pact in pacts:
        if args.consumer and pact.consumer != args.consumer:
            continue
        for interaction in pact.interactions:
            interaction.verify(args.provider_url, args.provider_setup_url)
            success = interaction.result.success and success
        if args.publish_verification_results:
            pact.publish_result(provider_version)
        else:
            print()
    return int(not success)


if __name__ == '__main__':
    import sys
    sys.exit(main())
