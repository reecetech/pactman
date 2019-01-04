from pactman import Consumer, Provider


def test_full_payload_v2():
    pact = Consumer('consumer').has_pact_with(Provider('provider'), version='2.0.0')
    (pact
        .given('UserA exists and is not an administrator')
        .upon_receiving('a request for UserA')
        .with_request('get', '/users/UserA', headers={'Accept': 'application/json'}, query='term=test')
        .will_respond_with(200, body={'username': 'UserA'}, headers={'Content-Type': 'application/json'}))
    result = pact.construct_pact(pact._interactions[0])
    assert result == {
        'consumer': {'name': 'consumer'},
        'provider': {'name': 'provider'},
        'interactions': [
            {
                'description': 'a request for UserA',
                'providerState': 'UserA exists and is not an administrator',
                'request': dict(method='get', path='/users/UserA', headers={'Accept': 'application/json'},
                                query='term=test'),
                'response': dict(status=200, body={'username': 'UserA'},
                                 headers={'Content-Type': 'application/json'})
            }
        ],
        'metadata': dict(pactSpecification=dict(version='2.0.0'))
    }


def test_full_payload_v3():
    pact = Consumer('consumer').has_pact_with(Provider('provider'), version='3.0.0')
    (pact
     .given([{"name": "User exists and is not an administrator", "params": {"username": "UserA"}}])
     .upon_receiving('a request for UserA')
     .with_request('get', '/users/UserA', headers={'Accept': 'application/json'}, query=dict(term=['test']))
     .will_respond_with(200, body={'username': 'UserA'}, headers={'Content-Type': 'application/json'}))
    result = pact.construct_pact(pact._interactions[0])
    assert result == {
        'consumer': {'name': 'consumer'},
        'provider': {'name': 'provider'},
        'interactions': [
            {
                'description': 'a request for UserA',
                'providerStates': [{
                    "name": "User exists and is not an administrator",
                    "params": {"username": "UserA"}
                }],
                'request': dict(method='get', path='/users/UserA', headers={'Accept': 'application/json'},
                                query=dict(term=['test'])),
                'response': dict(status=200, body={'username': 'UserA'},
                                 headers={'Content-Type': 'application/json'})
            }
        ],
        'metadata': dict(pactSpecification=dict(version='3.0.0'))
    }
