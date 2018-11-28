from unittest import TestCase

from pactman import Term, Like
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

    def test_matcher_in_query(self):
        target = Request('GET', '/test-path', query={'q': [Like('spam')], 'l': [Term(r'\d+', '10')]})
        result = target.json('3.0.0')
        self.maxDiff = None
        self.assertEqual(result, {
            'method': 'GET',
            'path': '/test-path',
            'query': {'q': ['spam'], 'l': ['10']},
            'matchingRules': {
                'query': {
                    'q': {
                        'matchers': [
                            {
                                'match': 'type'
                            },
                        ]
                    },
                    'l': {
                        'matchers': [
                            {
                                'match': 'regex',
                                'regex': r'\d+',
                            }
                        ]
                    },
                }
            }
        })
