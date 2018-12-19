from unittest.mock import Mock

from pactman import Consumer, Provider
from pactman.mock.pact_request_handler import construct_pact


def test_v2():
    pact = Consumer('consumer').has_pact_with(Provider('provider'), version='2.0.0')
    pact.given("the condition exists").upon_receiving("a request").with_request("GET", "/path") \
        .will_respond_with(200, body='ok')

    result = construct_pact(Mock(consumer_name='consumer', provider_name='provider',
                                 version='2.0.0'), pact._interactions[0])
    assert result == {
        'consumer': {'name': 'consumer'},
        'provider': {'name': 'provider'},
        'interactions': [
            {
                'description': 'a request',
                'providerState': 'the condition exists',
                'request': dict(method='GET', path='/path'),
                'response': dict(status=200, body='ok'),

            }
        ],
        'metadata': dict(pactSpecification=dict(version='2.0.0'))
    }


def test_v3():
    pact = Consumer('consumer').has_pact_with(Provider('provider'), version='3.0.0')
    pact.given([
        dict(name="the condition exists", params={}),
        dict(name="the user exists", params=dict(username='alex')),
    ]).upon_receiving("a request").with_request("GET", "/path").will_respond_with(200, body='ok')

    result = construct_pact(Mock(consumer_name='consumer', provider_name='provider',
                                 version='3.0.0'), pact._interactions[0])
    assert result == {
        'consumer': {'name': 'consumer'},
        'provider': {'name': 'provider'},
        'interactions': [
            {
                'description': 'a request',
                'providerStates': [
                    {'name': 'the condition exists', 'params': {}},
                    {'name': 'the user exists', 'params': {'username': 'alex'}}
                ],
                'request': dict(method='GET', path='/path'),
                'response': dict(status=200, body='ok'),

            }
        ],
        'metadata': dict(pactSpecification=dict(version='3.0.0'))
    }


def test_v3_and_given():
    pact = (
        Consumer('consumer').has_pact_with(Provider('provider'), version='3.0.0')
        .given("the condition exists")
        .and_given("the user exists", username='alex')
        .upon_receiving("a request").with_request("GET", "/path")
        .will_respond_with(200, body='ok')
    )

    result = construct_pact(Mock(consumer_name='consumer', provider_name='provider',
                                 version='3.0.0'), pact._interactions[0])
    assert result == {
        'consumer': {'name': 'consumer'},
        'provider': {'name': 'provider'},
        'interactions': [
            {
                'description': 'a request',
                'providerStates': [
                    {'name': 'the condition exists', 'params': {}},
                    {'name': 'the user exists', 'params': {'username': 'alex'}}
                ],
                'request': dict(method='GET', path='/path'),
                'response': dict(status=200, body='ok'),

            }
        ],
        'metadata': dict(pactSpecification=dict(version='3.0.0'))
    }
