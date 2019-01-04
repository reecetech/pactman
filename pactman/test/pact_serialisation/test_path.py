from pactman import Term
from pactman.mock.request import Request


def test_matcher_in_path_gets_converted():
    target = Request('GET', Term(r'\/.+', '/test-path'))
    assert target.json('2.0.0') == {
        'method': 'GET',
        'path': '/test-path',
        'matchingRules': {
            '$.path': {
                'regex': r'\/.+'
            }
        }
    }
