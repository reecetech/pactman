from unittest import TestCase

from pactman.mock.response import Response


class ResponseTestCase(TestCase):
    def test_sparse(self):
        target = Response(200)
        result = target.json('2.0.0')
        self.assertEqual(result, {'status': 200})

    def test_all_options(self):
        target = Response(
            202, headers={'Content-Type': 'application/json'}, body='the body')

        result = target.json('2.0.0')
        self.assertEqual(result, {
            'status': 202,
            'body': 'the body',
            'headers': {'Content-Type': 'application/json'}})

    def test_falsey_body(self):
        target = Response(200, body=[])
        result = target.json('2.0.0')
        self.assertEqual(result, {'status': 200, 'body': []})
