import os
from unittest import TestCase
from unittest.mock import patch, call

import pytest

from pactman.mock.consumer import Consumer
from pactman.mock.provider import Provider
from pactman.mock.pact import Pact


class PactTestCase(TestCase):
    def setUp(self):
        self.consumer = Consumer('TestConsumer')
        self.provider = Provider('TestProvider')

    def test_init_defaults(self):
        target = Pact(self.consumer, self.provider)
        self.assertIs(target.consumer, self.consumer)
        self.assertEqual(target.host_name, 'localhost')
        self.assertEqual(target.log_dir, os.getcwd())
        self.assertEqual(target.pact_dir, os.getcwd())
        self.assertEqual(target.port, 1234)
        self.assertIs(target.provider, self.provider)
        self.assertIs(target.ssl, False)
        self.assertIsNone(target.sslcert)
        self.assertIsNone(target.sslkey)
        self.assertEqual(target.uri, 'http://localhost:1234')
        self.assertEqual(target.version, '2.0.0')
        self.assertEqual(len(target._interactions), 0)

    def test_init_custom_mock_service(self):
        target = Pact(
            self.consumer, self.provider, host_name='192.168.1.1', port=8000,
            log_dir='/logs', ssl=True, sslcert='/ssl.cert', sslkey='/ssl.pem',
            pact_dir='/pacts', version='3.0.0', file_write_mode='merge',
            use_mocking_server=False)

        self.assertIs(target.consumer, self.consumer)
        self.assertEqual(target.host_name, '192.168.1.1')
        self.assertEqual(target.log_dir, '/logs')
        self.assertEqual(target.pact_dir, '/pacts')
        self.assertEqual(target.port, 8000)
        self.assertIs(target.provider, self.provider)
        self.assertIs(target.ssl, True)
        self.assertEqual(target.sslcert, '/ssl.cert')
        self.assertEqual(target.sslkey, '/ssl.pem')
        self.assertEqual(target.uri, 'https://192.168.1.1:8000')
        self.assertEqual(target.version, '3.0.0')
        self.assertEqual(target.file_write_mode, 'merge')
        self.assertEqual(len(target._interactions), 0)
        self.assertIs(target.use_mocking_server, False)

    def test_definition_sparse(self):
        target = Pact(self.consumer, self.provider)
        (target
         .given('I am creating a new pact using the Pact class')
         .upon_receiving('a specific request to the server')
         .with_request('GET', '/path')
         .will_respond_with(200, body='success'))

        self.assertEqual(len(target._interactions), 1)

        self.assertEqual(
            target._interactions[0]['providerState'],
            'I am creating a new pact using the Pact class')

        self.assertEqual(
            target._interactions[0]['description'],
            'a specific request to the server')

        self.assertEqual(target._interactions[0]['request'],
                         {'path': '/path', 'method': 'GET'})
        self.assertEqual(target._interactions[0]['response'],
                         {'status': 200, 'body': 'success'})

    def test_definition_all_options(self):
        target = Pact(self.consumer, self.provider)
        (target
         .given('I am creating a new pact using the Pact class')
         .upon_receiving('a specific request to the server')
         .with_request('GET', '/path',
                       body={'key': 'value'},
                       headers={'Accept': 'application/json'},
                       query={'search': 'test'})
         .will_respond_with(
             200,
             body='success', headers={'Content-Type': 'application/json'}))

        self.assertEqual(
            target._interactions[0]['providerState'],
            'I am creating a new pact using the Pact class')

        self.assertEqual(
            target._interactions[0]['description'],
            'a specific request to the server')

        self.assertEqual(target._interactions[0]['request'], {
            'path': '/path',
            'method': 'GET',
            'body': {'key': 'value'},
            'headers': {'Accept': 'application/json'},
            'query': {'search': 'test'}})
        self.assertEqual(target._interactions[0]['response'], {
            'status': 200,
            'body': 'success',
            'headers': {'Content-Type': 'application/json'}})

    def test_definition_v3_requires_new_providerStates(self):
        target = Pact(self.consumer, self.provider, version='3.0.0')
        with pytest.raises(ValueError):
            target.given('I am creating a new pact using the Pact class')

    def test_definition_v3(self):
        target = Pact(self.consumer, self.provider, version='3.0.0')
        (target
         .given([{'name': 'I am creating a new pact using the Pact class', 'params': {}}])
         .upon_receiving('a specific request to the server')
         .with_request('GET', '/path',
                       body={'key': 'value'},
                       headers={'Accept': 'application/json'},
                       query={'search': 'test'})
         .will_respond_with(
             200,
             body='success', headers={'Content-Type': 'application/json'}))

        self.assertEqual(
            target._interactions[0]['providerStates'],
            [{'name': 'I am creating a new pact using the Pact class', 'params': {}}])

        self.assertEqual(
            target._interactions[0]['description'],
            'a specific request to the server')

        self.assertEqual(target._interactions[0]['request'], {
            'path': '/path',
            'method': 'GET',
            'body': {'key': 'value'},
            'headers': {'Accept': 'application/json'},
            'query': {'search': 'test'}})
        self.assertEqual(target._interactions[0]['response'], {
            'status': 200,
            'body': 'success',
            'headers': {'Content-Type': 'application/json'}})

    def test_definition_multiple_interactions(self):
        target = Pact(self.consumer, self.provider)
        (target
         .given('I am creating a new pact using the Pact class')
         .upon_receiving('a specific request to the server')
         .with_request('GET', '/foo')
         .will_respond_with(200, body='success')
         .given('I am creating another new pact using the Pact class')
         .upon_receiving('a different request to the server')
         .with_request('GET', '/bar')
         .will_respond_with(200, body='success'))

        self.assertEqual(len(target._interactions), 2)

        self.assertEqual(
            target._interactions[1]['providerState'],
            'I am creating a new pact using the Pact class')
        self.assertEqual(
            target._interactions[0]['providerState'],
            'I am creating another new pact using the Pact class')

        self.assertEqual(
            target._interactions[1]['description'],
            'a specific request to the server')
        self.assertEqual(
            target._interactions[0]['description'],
            'a different request to the server')

        self.assertEqual(target._interactions[1]['request'],
                         {'path': '/foo', 'method': 'GET'})
        self.assertEqual(target._interactions[0]['request'],
                         {'path': '/bar', 'method': 'GET'})

        self.assertEqual(target._interactions[1]['response'],
                         {'status': 200, 'body': 'success'})
        self.assertEqual(target._interactions[0]['response'],
                         {'status': 200, 'body': 'success'})


class PactSetupTestCase(PactTestCase):
    def setUp(self):
        super(PactSetupTestCase, self).setUp()
        self.addCleanup(patch.stopall)
        self.target = Pact(self.consumer, self.provider)
        (self.target
         .given('I am creating a new pact using the Pact class')
         .upon_receiving('a specific request to the server')
         .with_request('GET', '/path')
         .will_respond_with(200, body='success'))

        self.delete_call = call('delete', 'http://localhost:1234/interactions',
                                headers={'X-Pact-Mock-Service': 'true'})

        self.put_interactions_call = call(
            'put', 'http://localhost:1234/interactions',
            data=None,
            headers={'X-Pact-Mock-Service': 'true'},
            json={'interactions': [{
                'response': {'status': 200, 'body': 'success'},
                'request': {'path': '/path', 'method': 'GET'},
                'description': 'a specific request to the server',
                'providerState': 'I am creating a new pact using the Pact class'}]})


class PactContextManagerTestCase(PactTestCase):
    def setUp(self):
        super(PactContextManagerTestCase, self).setUp()
        self.addCleanup(patch.stopall)
        self.mock_setup = patch.object(
            Pact, 'setup', autospec=True).start()

        self.mock_verify = patch.object(
            Pact, 'verify', autospec=True).start()

    def test_successful(self):
        pact = Pact(self.consumer, self.provider)
        with pact:
            pass

        self.mock_setup.assert_called_once_with(pact)
        self.mock_verify.assert_called_once_with(pact)

    def test_context_raises_error(self):
        pact = Pact(self.consumer, self.provider)
        with self.assertRaises(RuntimeError):
            with pact:
                raise RuntimeError

        self.mock_setup.assert_called_once_with(pact)
        self.assertFalse(self.mock_verify.called)
