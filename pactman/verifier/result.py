import logging
from colorama import Fore

log = logging.getLogger(__name__)


class Result:
    PASS = True
    FAIL = False
    success = PASS

    def start(self, message):
        self.success = self.PASS

    def end(self):
        pass

    def warn(self, message):
        raise NotImplementedError()

    def fail(self, message, path=None):
        raise NotImplementedError()   # pragma: no cover


class LoggedResult(Result):
    def start(self, interaction):
        super().start(interaction)
        log.info(f'Verifying {interaction}')

    def warn(self, message):
        log.warning(' ' + message)

    def fail(self, message, path=None):
        self.success = self.FAIL
        log.warning(' ' + message)
        return not message


class PytestResult(Result):   # pragma: no cover
    def start(self, interaction):
        log.info(f'Verifying {interaction}')

    def warn(self, message):
        log.warning(Fore.RED + message + Fore.RESET)

    def fail(self, message, path=None):
        from _pytest.outcomes import Failed
        __tracebackhide__ = True
        self.success = self.FAIL
        log.warning(' ' + message)
        raise Failed(message) from None
