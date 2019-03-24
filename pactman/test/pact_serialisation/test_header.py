from pactman import Term
from pactman.mock.request import Request


def test_matcher_in_path_gets_converted():
    target = Request('GET', '/', headers={'Spam': Term(r'\w+', 'spam')})
    assert target.json('3.0.0') == {
        'method': 'GET',
        'path': '/',
        'headers': {'Spam': 'spam'},
        'matchingRules': {
            'header': {
                "Spam": {
                    "matchers": [
                        {
                            "match": "regex",
                            "regex": "\\w+"
                        }
                    ]
                }
            }
        }
    }
