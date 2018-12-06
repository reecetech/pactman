# pactman

Python version of Pact mocking, generation and verification.

Enables [consumer driven contract testing], providing unit test mocking of provider services
and DSL for the consumer project, and interaction playback and verification for the service
provider project. Currently supports versions 1.1, 2 and 3 of the [Pact specification].

For more information about what Pact is, and how it can help you
test your code more efficiently, check out the [Pact documentation].

Contains code originally from the [pact-python](https://github.com/pact-foundation/pact-python) project.

pactman is maintained by the [ReeceTech](https://www.reecetech.com.au/) team as part of their toolkit to
keep their large (and growing) microservices architecture under control.

## pactman vs pact-python

The key difference is all functionality is implemented in Python, rather than shelling out or forking
to the ruby implementation. This allows for a much nicer mocking user experience (it mocks urllib3
directly), is faster, less messy configuration (multiple providers means multiple ruby processes spawned
on different ports).

It also supports a broader set of the pact specification (versions 1.1 through to 3).

The pact verifier has been engineered from the start to talk to a pact broker (both to discover pacts
and to return verification results).

There’s a few other quality of life improvements, but those are the big ones.

# How to use pactman

## Installation

`pactman` requires Python 3.6 to run.

```
pip install pactman
```

## Writing a Pact
Creating a complete contract is a two step process:

1. Create a test on the consumer side that declares the expectations it has of the provider
2. Create a provider state that allows the contract to pass when replayed against the provider

## Writing the Consumer Test

If we have a method that communicates with one of our external services, which we'll call
`Provider`, and our product, `Consumer` is hitting an endpoint on `Provider` at
`/users/<user>` to get information about a particular user.

If the code to fetch a user looked like this:

```python
import requests

def get_user(user_name):
    response = requests.get(f'http://service.example/users/{user_name}')
    return response.json()
```

Then `Consumer`'s contract test might look something like this:

```python
import atexit
import unittest

from pactman import Consumer, Provider


pact = Consumer('Consumer').has_pact_with(Provider('Provider'))
pact.start_mocking()
atexit.register(pact.stop_mocking)


class GetUserInfoContract(unittest.TestCase):
  def test_get_user(self):
    expected = {
      'username': 'UserA',
      'id': 123,
      'groups': ['Editors']
    }

    pact.given(
        'UserA exists and is not an administrator'
    ).upon_receiving(
        'a request for UserA'
    ).with_request(
        'GET', '/users/UserA'
    ) .will_respond_with(200, body=expected)

    with pact:
      result = get_user('UserA')

    self.assertEqual(result, expected)

```

This does a few important things:

 - Defines the Consumer and Provider objects that describe our product and our service under test
 - Uses `given` to define the setup criteria for the Provider `UserA exists and is not an administrator`
 - Defines what the request that is expected to be made by the consumer will contain
 - Defines how the server is expected to respond

Using the Pact object as a [context manager], we call our method under test
which will then communicate with the Pact mock service. The mock service will respond with
the items we defined, allowing us to assert that the method processed the response and
returned the expected value. If you want more control over when the mock service is
configured and the interactions verified, use the `setup` and `verify` methods, respectively:

```python
    pact.given(
        'UserA exists and is not an administrator'
    ).upon_receiving(
        'a request for UserA'
    ).with_request(
        'GET', '/users/UserA'
    ) .will_respond_with(200, body=expected)

    pact.setup()
    try:
        # Some additional steps before running the code under test
        result = get_user('UserA')
        # Some additional steps before verifying all interactions have occurred
    finally:
        pact.verify()
```

### Requests

When defining the expected HTTP request that your code is expected to make you
can specify the method, path, body, headers, and query:

```python
pact.with_request(
    method='GET',
    path='/api/v1/my-resources/',
    query={'search': 'example'}
)
```

`query` is used to specify URL query parameters, so the above example expects
a request made to `/api/v1/my-resources/?search=example`.

```python
pact.with_request(
    method='POST',
    path='/api/v1/my-resources/123',
    body={'user_ids': [1, 2, 3]},
    headers={'Content-Type': 'application/json'},
)
```

You can define exact values for your expected request like the examples above,
or you can use the matchers defined later to assist in handling values that are
variable.

### Some important has_pact_with options

The `has_pact_with(provider...)` call has quite a few options documented in its API, but a couple are
worth mentioning in particular:

`version` declares the pact specification version that the provider supports. This defaults to "2.0.0", but "3.0.0"
is also acceptable if your provider supports [Pact specification version 3]:

```python
from pactman import Consumer, Provider
pact = Consumer('Consumer').has_pact_with(Provider('Provider'), version='3.0.0')
```

`use_mocking_server` defaults to `False` and controls the mocking method used by `pactman`. The default is to
patch `urllib3`, which is the library underpinning `requests` and is also used by some other projects. If you
are using a different library to make your HTTP requests which does not use `urllib3` underneath then you will need
to set the `use_mocking_server` argument to `True`. This causes `pactman` to run an actual HTTP server to mock the
requests (the server is listening on `pact.uri` - use that to redirect your HTTP requests to the mock server.) You
may also set the `USE_MOCKING_SERVER` environment variable to "yes" to force your entire suite to use the server
approach.

```python
from pactman import Consumer, Provider
pact = Consumer('Consumer').has_pact_with(Provider('Provider'), use_mocking_server=True)
```

## Expecting Variable Content
The above test works great if that user information is always static, but what happens if
the user has a last updated field that is set to the current time every time the object is
modified? To handle variable data and make your tests more robust, there are 3 helpful matchers:

### Term(matcher, generate)
Asserts the value should match the given regular expression. You could use this
to expect a timestamp with a particular format in the request or response where
you know you need a particular format, but are unconcerned about the exact date:

```python
from pactman import Term
...
body = {
    'username': 'UserA',
    'last_modified': Term('\d+-\d+-\d+T\d+:\d+:\d+', '2016-12-15T20:16:01')
}

(pact
 .given('UserA exists and is not an administrator')
 .upon_receiving('a request for UserA')
 .with_request('get', '/users/UserA/info')
 .will_respond_with(200, body=body))
```

When you run the tests for the consumer, the mock service will return the value you provided
as `generate`, in this case `2016-12-15T20:16:01`. When the contract is verified on the
provider, the regex will be used to search the response from the real provider service
and the test will be considered successful if the regex finds a match in the response.

### Like(matcher)
Asserts the element's type matches the matcher. For example:

```python
from pactman import Like
Like(123)  # Matches if the value is an integer
Like('hello world')  # Matches if the value is a string
Like(3.14)  # Matches if the value is a float
```
The argument supplied to `Like` will be what the mock service responds with.

When a dictionary is used as an argument for Like, all the child objects (and their child objects etc.) will be matched according to their types, unless you use a more specific matcher like a Term.

```python
from pactman import Like, Term
Like({
    'username': Term('[a-zA-Z]+', 'username'),
    'id': 123, # integer
    'confirmed': False, # boolean
    'address': { # dictionary
        'street': '200 Bourke St' # string
    }
})

```

### EachLike(matcher, minimum=1)
Asserts the value is an array type that consists of elements
like the one passed in. It can be used to assert simple arrays:

```python
from pactman import EachLike
EachLike(1)  # All items are integers
EachLike('hello')  # All items are strings
```

Or other matchers can be nested inside to assert more complex objects:

```python
from pactman import EachLike, Term
EachLike({
    'username': Term('[a-zA-Z]+', 'username'),
    'id': 123,
    'groups': EachLike('administrators')
})
```

> Note, you do not need to specify everything that will be returned from the Provider in a
> JSON response, any extra data that is received will be ignored and the tests will still pass.

For more information see [Matching](https://docs.pact.io/documentation/matching.html)

## Verifying Pacts Against a Service
Run `pactman-verifier -h` to see the options available. To run all pacts registered to a provider in a [Pact Broker]:

    pactman-verifier -b http://pact-broker.example/ <provider name> <provider url> <provider setup url>

You may also specify the broker URL in the environment variable `PACT_BROKER_URL`.

You can pass in a local pact file with `-l`, this will verify the service against the local file instead of the broker:

    pactman-verifier -l /tmp/localpact.json <provider name> <provider url> <provider setup url>

### Provider States
In many cases, your contracts will need very specific data to exist on the provider
to pass successfully. If you are fetching a user profile, that user needs to exist,
if querying a list of records, one or more records needs to exist. To support
decoupling the testing of the consumer and provider, Pact offers the idea of provider
states to communicate from the consumer what data should exist on the provider.

When setting up the testing of a provider you will also need to setup the management of
these provider states. The Pact verifier does this by making additional HTTP requests to
the `<provider setup url>` you provide. This URL could be
on the provider application or a separate one. Some strategies for managing state include:

- Having endpoints in your application that are not active in production that create and delete your datastore state
- A separate application that has access to the same datastore to create and delete,
  like a separate App Engine module or Docker container pointing to the same datastore
- A standalone application that can start and stop the other server with different datastore states

For more information about provider states, refer to the [Pact documentation] on [Provider States].

# Development
Please read [CONTRIBUTING.md](CONTRIBUTING.md)

To setup a development environment:

1. Clone the repository `https://github.com/reecetech/pactman` and invoke `git submodule update --init`
2. Install Python 3.6 from source or using a tool like [pyenv]
3. Its recommended to create a Python [virtualenv] for the project

To run tests, use:
`tox`

To package the application, run:
`python setup.py sdist`

This creates a `dist/pactman-N.N.N.tar.gz` file, where the Ns are the current version.
From there you can use pip to install it:
`pip install ./dist/pactman-N.N.N.tar.gz`

## Release History

2.5.0

- Fix some bugs around empty array verification

2.4.0

- Create the pact destination dir if it's missing and its parent exists 

2.3.0

- Fix some issues around mocking request queries and the mock's verification of same
- Fix header regex matching in mock verification
- Actually use the version passed in to `has_pact_with()`
- Fix some pact v3 generation issues (thanks pan Jacek)

2.2.0

- Reinstate lost result output.

2.1.0

- Corrected the definition of request payload when there is no `body` in the request

2.0.0

- Correctly determine pact verification result when publishing to broker.

1.2.0

- Corrected use of format_path in command line error handling.
- Tweaked README for clarity.

1.1.0

- Renamed the `pact-verifier` command to `pactman-verifier` to avoid
  confusion with other pre-existing packages that provide a command-line
  incompatible `pact-verifier` command.
- Support verification of HEAD requests (oops).

1.0.8

- Corrected project URL in project metadata (thanks Jonathan Moss)
- Fix verbose output

1.0.7

- Added some Trove classifiers to aid potential users.

1.0.6

- Corrected mis-named command-line option.

1.0.5

- Corrected some packaging issues

1.0.4

- Initial release of pactman, including ReeceTech's pact-verifier version 3.17 and pact-python version 0.17.0

[consumer driven contract testing]: https://2018.pycon-au.org/talks/44811-pact-in-python/
[context manager]: https://en.wikibooks.org/wiki/Python_Programming/Context_Managers
[Pact]: https://www.gitbook.com/book/pact-foundation/pact/details
[Pact Broker]: https://docs.pact.io/documentation/sharings_pacts.html
[Pact documentation]: https://docs.pact.io/
[Pact Mock Service]: https://github.com/bethesque/pact-mock_service
[Pact specification]: https://github.com/pact-foundation/pact-specification
[Pact specification version 3]: https://github.com/pact-foundation/pact-specification/tree/version-3
[Provider States]: https://docs.pact.io/documentation/provider_states.html
[pact-provider-verifier]: https://github.com/pact-foundation/pact-provider-verifier
[pyenv]: https://github.com/pyenv/pyenv
[virtualenv]: http://python-guide-pt-br.readthedocs.io/en/latest/dev/virtualenvs/
