from pactman import Consumer, Like, Provider


def test_v2():
    pact = Consumer('consumer').has_pact_with(Provider('provider'), version='2.0.0')

    pact.given("the condition exists").upon_receiving("a request") \
        .with_request("GET", "/path", query="fields=first,second").will_respond_with(200, body='ok')

    result = pact.construct_pact(pact._interactions[0])
    assert result == {
        'consumer': {'name': 'consumer'},
        'provider': {'name': 'provider'},
        'interactions': [
            {
                'description': 'a request',
                'providerState': 'the condition exists',
                'request': dict(method='GET', path='/path', query='fields=first,second'),
                'response': dict(status=200, body='ok'),

            }
        ],
        'metadata': dict(pactSpecification=dict(version='2.0.0'))
    }


def test_v3():
    pact = Consumer('consumer').has_pact_with(Provider('provider'), version='3.0.0')
    pact.given([{'name': "the condition exists", 'params': {}}]).upon_receiving("a request") \
        .with_request("GET", "/path", query=dict(fields='first,second')).will_respond_with(200, body='ok')

    result = pact.construct_pact(pact._interactions[0])
    assert result == {
        'consumer': {'name': 'consumer'},
        'provider': {'name': 'provider'},
        'interactions': [
            {
                'description': 'a request',
                'providerStates': [{'name': 'the condition exists', 'params': {}}],
                'request': dict(method='GET', path='/path', query=dict(fields='first,second')),
                'response': dict(status=200, body='ok'),

            }
        ],
        'metadata': dict(pactSpecification=dict(version='3.0.0'))
    }


def test_like_v2():
    pact = Consumer('consumer').has_pact_with(Provider('provider'), version='2.0.0')

    pact.given("the condition exists").upon_receiving("a request") \
        .with_request("GET", "/path", query=Like("fields=first,second")).will_respond_with(200, body='ok')

    result = pact.construct_pact(pact._interactions[0])
    assert result == {
        'consumer': {'name': 'consumer'},
        'provider': {'name': 'provider'},
        'interactions': [
            {
                'description': 'a request',
                'providerState': 'the condition exists',
                'request': dict(method='GET', path='/path', query='fields=first,second',
                                matchingRules={'$.query': {'match': 'type'}}),
                'response': dict(status=200, body='ok'),

            }
        ],
        'metadata': dict(pactSpecification=dict(version='2.0.0'))
    }


def test_like_v3():
    pact = (
        Consumer('consumer').has_pact_with(Provider('provider'), version='3.0.0')
        .given("the condition exists")
        .upon_receiving("a request")
        .with_request("GET", "/path", query=dict(fields=Like(['first,second'])))
        .will_respond_with(200, body='ok')
    )

    result = pact.construct_pact(pact._interactions[0])
    assert result == {
        'consumer': {'name': 'consumer'},
        'provider': {'name': 'provider'},
        'interactions': [
            {
                'description': 'a request',
                'providerStates': [{'name': 'the condition exists', 'params': {}}],
                'request': dict(method='GET', path='/path', query=dict(fields=['first,second']),
                                matchingRules={'query': {'fields': {'matchers': [{'match': 'type'}]}}}),
                'response': dict(status=200, body='ok'),

            }
        ],
        'metadata': dict(pactSpecification=dict(version='3.0.0'))
    }


def test_broader_like_v3():
    pact = (
        Consumer('consumer').has_pact_with(Provider('provider'), version='3.0.0')
        .given("the condition exists")
        .upon_receiving("a request")
        .with_request("GET", "/path", query=Like(dict(fields=['first,second'])))
        .will_respond_with(200, body='ok')
    )

    result = pact.construct_pact(pact._interactions[0])
    assert result == {
        'consumer': {'name': 'consumer'},
        'provider': {'name': 'provider'},
        'interactions': [
            {
                'description': 'a request',
                'providerStates': [{'name': 'the condition exists', 'params': {}}],
                'request': dict(method='GET', path='/path', query=dict(fields=['first,second']),
                                matchingRules={'query': {'*': {'matchers': [{'match': 'type'}]}}}),
                'response': dict(status=200, body='ok'),
            }
        ],
        'metadata': dict(pactSpecification=dict(version='3.0.0'))
    }
