from unittest.mock import Mock

from pactman import Consumer, Provider, EachLike
from pactman.mock.pact_request_handler import construct_pact


def test_eachlike():
    pact = (
        Consumer('consumer').has_pact_with(Provider('provider'), version='2.0.0')
        .given("the condition exists")
        .upon_receiving("a request")
        .with_request("POST", "/path", body=EachLike(1))
        .will_respond_with(200, body={"results": EachLike(1)})
    )

    result = construct_pact(Mock(consumer_name='consumer', provider_name='provider',
                                 version='2.0.0'), pact._interactions[0])
    assert result == {
        'consumer': {'name': 'consumer'},
        'provider': {'name': 'provider'},
        'interactions': [
            {
                'description': 'a request',
                'providerState': 'the condition exists',
                'request': dict(method='POST', path='/path', body=[1],
                                matchingRules={'$.body': {'match': 'type', 'min': 1}}),
                'response': dict(status=200, body={'results': [1]},
                                 matchingRules={'$.body.results': {'match': 'type', 'min': 1}}),

            }
        ],
        'metadata': dict(pactSpecification=dict(version='2.0.0'))
    }
