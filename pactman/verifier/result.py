import logging


log = logging.getLogger(__name__)


class Result:
    PASS = True
    FAIL = False
    success = PASS

    def start(self, message):
        self.success = self.PASS

    def end(self):
        pass

    def fail(self, message, path=None):
        raise NotImplementedError()   # pragma: no cover


class LoggedResult(Result):
    def start(self, interaction):
        super().start(interaction)
        log.info(f'Verifying {interaction}')

    def fail(self, message, path=None):
        self.success = self.FAIL
        log.warning(' ' + message)
        return not message


class PytestResult(Result):   # pragma: no cover
    def start(self, interaction):
        log.info(f'Verifying {interaction}')

    def fail(self, message, path=None):
        from _pytest.outcomes import Failed
        __tracebackhide__ = True
        self.success = self.FAIL
        log.warning(' ' + message)
        raise Failed(message) from None

    def configure_logging(self, verbosity):
        logging.getLogger().handlers = []
        logging.basicConfig(format='%(message)s')
        log.setLevel({0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}[verbosity])
