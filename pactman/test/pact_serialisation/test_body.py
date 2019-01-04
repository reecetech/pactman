from pactman import Consumer, EachLike, Provider
from pactman.mock.request import Request
from pactman.mock.response import Response


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


def test_falsey_request_body():
    target = Request('GET', '/path', body=[])
    assert target.json('2.0.0') == {'method': 'GET', 'path': '/path', 'body': []}


def test_falsey_response_body():
    target = Response(200, body=[])
    assert target.json('2.0.0') == {'status': 200, 'body': []}
