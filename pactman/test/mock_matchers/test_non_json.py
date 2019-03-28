import requests

from pactman import Pact


def test_params_url_coded():
    pact = Pact('Consumer', 'Provider', file_write_mode='never').given('everything is ideal') \
        .upon_receiving('a request').with_request(
            method='POST',
            path="/",
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            query={
                 "client_id": ["test1"],
                 "secret": ["test1-secret-key"],
                 "scope": ['openid', 'profile', 'phone', 'offline_access']
            }
        ).will_respond_with(200, body='some data')
    with pact:
        requests.post(pact.uri, params=dict(client_id='test1', secret='test1-secret-key',
                                            scope='openid profile phone offline_access'.split()),
                      headers={'Content-Type': 'application/x-www-form-urlencoded'})


def test_body_url_coded():
    pact = Pact('Consumer', 'Provider', file_write_mode='never').given('everything is ideal') \
        .upon_receiving('a request').with_request(
             method='POST',
             path="/",
             headers={'Content-Type': 'application/x-www-form-urlencoded'},
             body={
                 "client_id": ["test1"],
                 "secret": ["test1-secret-key"],
                 "scope": ['openid', 'profile', 'phone', 'offline_access']
             }
        ).will_respond_with(200, body='some data')
    with pact:
        requests.post(pact.uri, data=dict(client_id='test1', secret='test1-secret-key',
                                          scope='openid profile phone offline_access'.split()),
                      headers={'Content-Type': 'application/x-www-form-urlencoded'})
