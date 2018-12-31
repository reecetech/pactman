from pactman import Consumer, EachLike, Provider


def test_eachlike():
    pact = (
        Consumer('consumer').has_pact_with(Provider('provider'), version='2.0.0')
        .given("the condition exists")
        .upon_receiving("a request")
        .with_request("POST", "/path", body=EachLike(1))
        .will_respond_with(200, body={"results": EachLike(1)})
    )

    result = pact.construct_pact(pact._interactions[0])
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
