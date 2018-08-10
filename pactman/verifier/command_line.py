import argparse
import logging

from colorama import Fore, Style, init

from .broker_pact import BrokerPact, BrokerPacts, log
from .result import Result


parser = argparse.ArgumentParser(description='Verify pact contracts')

parser.add_argument('provider_name', metavar='PROVIDER_NAME',
                    help='the name of the provider being verified')

parser.add_argument('provider_url', metavar='PROVIDER_URL',
                    help='the URL of the provider service')

parser.add_argument('provider_setup_url', metavar='PROVIDER_SETUP_URL',
                    help='the URL to provider state setup')

parser.add_argument('-b', '--broker-url', default=None,
                    help='the URL of the pact broker')

parser.add_argument('-l', '--local-pact-file', default=None,
                    help='path to a local pact file')

parser.add_argument('-c', '--consumer', default=None,
                    help='the name of the consumer to test')

parser.add_argument('-r', '--results-to-broker', default=False, action='store_true',
                    help='send verification results to the pact broker')

parser.add_argument('-p', '--provider-version', default=None,
                    help='provider application version, required for results publication')

parser.add_argument('-v', '--verbose', default=False, action='store_true',
                    help='output more information about the verification')

parser.add_argument('-q', '--quiet', default=False, action='store_true',
                    help='output less information about the verification')


class CaptureResult(Result):
    def __init__(self):
        log.handlers = [self]
        log.setLevel(logging.DEBUG)
        self.messages = []
        self.level = logging.WARNING
        self.current_consumer = None

    def start(self, interaction):
        super().start(interaction)
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
            message += ' at ' + self.format_path(path)
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
    result = CaptureResult()
    args = parser.parse_args()
    if args.results_to_broker and not args.provider_version:
        print('Provider version is required to publish results to the broker')
        return False
    if args.quiet:
        result.level = logging.WARNING
    elif args.verbose:
        result.level = logging.DEBUG
    else:
        result.level = logging.INFO
    if args.local_pact_file:
        pacts = [BrokerPact.load_file(args.local_pact_file, result)]
    else:
        pacts = BrokerPacts(args.provider_name, args.broker_url, result).consumers()
    success = True
    for pact in pacts:
        if args.consumer and pact.consumer != args.consumer:
            continue
        for interaction in pact.interactions:
            interaction.verify(args.provider_url, args.provider_setup_url)
            success = interaction.result.success and success
        if args.results_to_broker:
            pact.publish_result(args.provider_version)
        else:
            print()
    return int(not success)


if __name__ == '__main__':
    import sys
    sys.exit(main())
