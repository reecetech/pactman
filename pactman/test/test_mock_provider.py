from unittest import TestCase

from pactman.mock.provider import Provider


class ProviderTestCase(TestCase):
    def test_init(self):
        result = Provider('TestProvider')
        self.assertIsInstance(result, Provider)
        self.assertEqual(result.name, 'TestProvider')
