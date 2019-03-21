import json
import logging
import sys
from unittest.mock import Mock

import semver

from pactman.test.test_verifier import FakeResponse
from pactman.verifier.result import LoggedResult
from pactman.verifier.verify import ResponseVerifier


logging.basicConfig(level=logging.DEBUG)

result = LoggedResult()
version = sys.argv[1]
verifier = ResponseVerifier
response = FakeResponse

with open(sys.argv[2]) as file:
    case = json.load(file)

    pact = Mock(provider='SpamProvider', consumer='SpamConsumer', version=version,
                semver=semver.parse(version))
    verifier(pact, case['expected'], result).verify(response(case['actual']))
