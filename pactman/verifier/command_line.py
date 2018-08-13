import argparse
import logging

from colorama import Fore, Style, init

from .broker_pact import BrokerPact, BrokerPacts, log
from .result import Result


# TODO roll in this stuff?
'''

@click.command()
@click.argument('pacts', nargs=-1)
@click.option(
    'base_url', '--provider-base-url',
    help='Base URL of the provider to verify against.',
    required=True)
@click.option(
    'pact_url', '--pact-url',
    help='DEPRECATED: specify pacts as arguments instead.\n'
         'The URI of the pact to verify.'
         ' Can be an HTTP URI, a local file or directory path. '
         ' It can be specified multiple times to verify several pacts.',
    multiple=True)  # Remove in major version 1.0.0
@click.option(
    'pact_urls', '--pact-urls',
    default='',
    help='DEPRECATED: specify pacts as arguments instead.\n'
         'The URI(s) of the pact to verify.'
         ' Can be an HTTP URI(s) or local file path(s).'
         ' Provide multiple URI separated by a comma.',
    multiple=True)  # Remove in major version 1.0.0
@click.option(
    'states_url', '--provider-states-url',
    help='DEPRECATED: URL to fetch the provider states for'
         ' the given provider API.')  # Remove in major version 1.0.0
@click.option(
    'states_setup_url', '--provider-states-setup-url',
    help='URL to send PUT requests to setup a given provider state.')
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
@click.option(
    'provider_app_version', '-a', '--provider-app-version',
    help='The provider application version, '
         'required for publishing verification results'
    )
@click.option(
    'publish_verification_results', '-r', '--publish-verification-results',
    default=False,
    help='Publish verification results to the broker',
    is_flag=True)
@click.option(
    '--verbose/--no-verbose',
    default=False,
    help='Toggle verbose logging, defaults to False.')
def main(pacts, base_url, pact_url, pact_urls, states_url,
         states_setup_url, username, password, header, timeout,
         provider_app_version, publish_verification_results, verbose):
    """
    Verify one or more contracts against a provider service.

    Minimal example:

        pact-verifier --provider-base-url=http://localhost:8080 ./pacts
    """  # NOQA
    error = click.style('Error:', fg='red')
    warning = click.style('Warning:', fg='yellow')
    all_pact_urls = list(pacts) + list(pact_url)
    for urls in pact_urls:  # Remove in major version 1.0.0
        all_pact_urls.extend(p for p in urls.split(',') if p)

    if len(pact_urls) > 1:
        click.echo(
            warning
            + ' Multiple --pact-urls arguments are deprecated. '
              'Please provide a comma separated list of pacts to --pact-urls, '
              'or multiple --pact-url arguments.')

    if not all_pact_urls:
        click.echo(
            error
            + ' You must supply at least one pact file or directory to verify')
        raise click.Abort()

    all_pact_urls = expand_directories(all_pact_urls)
    missing_files = [path for path in all_pact_urls if not path_exists(path)]
    if missing_files:
        click.echo(
            error
            + ' The following Pact files could not be found:\n'
            + '\n'.join(missing_files))
        raise click.Abort()

    options = {
        '--provider-base-url': base_url,
        '--provider-states-setup-url': states_setup_url,
        '--broker-username': username,
        '--broker-password': password,
        '--custom-provider-header': header,
    }
    command = [VERIFIER_PATH]
    command.extend(all_pact_urls)
    command.extend(['{}={}'.format(k, v) for k, v in options.items() if v])

    if publish_verification_results:
        if not provider_app_version:
            click.echo(
                error
                + 'Provider application version is required '
                + 'to publish verification results to broker'
            )
            raise click.Abort()
        command.extend(["--provider-app-version",
                        provider_app_version,
                        "--publish-verification-results"])

    if verbose:
        command.extend(['--verbose'])

    env = os.environ.copy()
    env['PACT_INTERACTION_RERUN_COMMAND'] = rerun_command()
    p = subprocess.Popen(command, bufsize=1, env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, universal_newlines=True)

    sanitize_logs(p, verbose)
    p.wait()
    sys.exit(p.returncode)


def expand_directories(paths):
    """
    Iterate over paths and expand any that are directories into file paths.

    :param paths: A list of file paths to expand.
    :type paths: list
    :return: A list of file paths with any directory paths replaced with the
        JSON files in those directories.
    :rtype: list
    """
    paths_ = []
    for path in paths:
        if path.startswith('http://') or path.startswith('https://'):
            paths_.append(path)
        elif isdir(path):
            paths_.extend(
                [join(path, p) for p in listdir(path) if p.endswith('.json')])
        else:
            paths_.append(path)

    # Ruby pact verifier expects forward slashes regardless of OS
    return [p.replace('\\', '/') for p in paths_]


def path_exists(path):
    """
    Determine if a particular path exists.

    Can be provided a URL or local path. URLs always result in a True. Local
    paths are True only if a file exists at that location.

    :param path: The path to check.
    :type path: str
    :return: True if the path exists and is a file, otherwise False.
    :rtype: bool
    """
    if path.startswith('http://') or path.startswith('https://'):
        return True

    return isfile(path)

'''


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
