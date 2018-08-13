from unittest import TestCase

from pactman import Term
from pactman.mock.request import Request


class RequestTestCase(TestCase):
    def test_sparse(self):
        target = Request('GET', '/path')
        result = target.json('2.0.0')
        self.assertEqual(result, {
            'method': 'GET',
            'path': '/path'})

    def test_all_options(self):
        target = Request(
            'POST', '/path',
            body='the content',
            headers={'Accept': 'application/json'},
            query='term=test')

        result = target.json('2.0.0')
        self.assertEqual(result, {
            'method': 'POST',
            'path': '/path',
            'body': 'the content',
            'headers': {'Accept': 'application/json'},
            'query': 'term=test'})

    def test_falsey_body(self):
        target = Request('GET', '/path', body=[])
        result = target.json('2.0.0')
        self.assertEqual(result, {
            'method': 'GET',
            'path': '/path',
            'body': []})

    def test_matcher_in_path_gets_converted(self):
        target = Request('GET', Term(r'\/.+', '/test-path'))
        result = target.json('2.0.0')
        self.assertEqual(result, {
            'method': 'GET',
            'path': '/test-path',
            'matchingRules': {
                '$.path': {
                    'regex': r'\/.+'
                }
            }
        })
