# pactman

[![](https://img.shields.io/pypi/v/pactman.svg)](https://pypi.org/project/pactman/)

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

Where `pact-python` required management of a background Ruby server, and manually starting and stopping
it, `pactman` allows a much nicer usage like:

```python
import requests
from pactman import Consumer, Provider

pact = Consumer('Consumer').has_pact_with(Provider('Provider'))

def test_interaction():
    pact.given("some data exists").upon_receiving("a request") \
        .with_request("get", "/", query={"foo": ["bar"]}).will_respond_with(200)
    with pact:
        requests.get(pact.uri, params={"foo": ["bar"]})
```

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
import unittest
from pactman import Consumer, Provider

pact = Consumer('Consumer').has_pact_with(Provider('Provider'))

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
which will then communicate with the Pact mock. The mock will respond with
the items we defined, allowing us to assert that the method processed the response and
returned the expected value.

If you want more control over when the mock is configured and the interactions verified,
use the `setup` and `verify` methods, respectively:

```python
Consumer('Consumer').has_pact_with(Provider('Provider')).given(
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

### An important not about pact relationship definition

You may have noticed that the pact relationship is defined at the module level in our
examples:

```python
pact = Consumer('Consumer').has_pact_with(Provider('Provider'))
```

This is because it *must only be done once* per test suite. By default the pact file is
cleared out when that relationship is defined, so if you define it more than once per test
suite you'll end up only storing the *last* pact declared per relationship. For more on this
subject, see [writing multiple pacts](#writing-multiple-pacts).

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

`file_write_mode` defaults to `"overwrite"` and should be that or `"merge"`. Overwrite ensures
that any existing pact file will be removed when `has_pact_with()` is invoked. Merge will retain
the pact file and add new pacts to that file. See [writing multiple pacts](#writing-multiple-pacts).
If you absolutely do not want pact files to be written, use `"never"`. 

`use_mocking_server` defaults to `False` and controls the mocking method used by `pactman`. The default is to
patch `urllib3`, which is the library underpinning `requests` and is also used by some other projects. If you
are using a different library to make your HTTP requests which does not use `urllib3` underneath then you will need
to set the `use_mocking_server` argument to `True`. This causes `pactman` to run an actual HTTP server to mock the
requests (the server is listening on `pact.uri` - use that to redirect your HTTP requests to the mock server.) You
may also set the `PACT_USE_MOCKING_SERVER` environment variable to "yes" to force your entire suite to use the server
approach. You should declare the pact particpants (consumer and provider) outside of your tests and will need
to start and stop the mocking service outside of your tests too. The code below shows what using the server might
look like:

```python
import atexit
from pactman import Consumer, Provider
pact = Consumer('Consumer').has_pact_with(Provider('Provider'), use_mocking_server=True)
pact.start_mocking()
atexit.register(pact.stop_mocking)
``````

You'd then use `pact` to declare pacts between those participants.

### Writing multiple pacts

During a test run you're likely to need to write multiple pact interactions for a consumer/provider
relationship. `pactman` will manage the pact file as follows:

- When `has_pact_with()` is invoked it will by default remove any existing pact JSON file for the
  stated consumer & provider.
- You may invoke `Consumer('Consumer').has_pact_with(Provider('Provider'))` once at the start of
  your tests. This could be done as a pytest module or session fixture, or through some other
  mechanism and store it in a variable. By convention this is called `pact` in all of our examples.
- If that is not suitable, you may manually indicate to `has_pact_with()` that it should either
  retain (`file_write_mode="merge"`) or remove (`file_write_mode="overwrite"`) the existing
  pact file.

### Some words about given()

You use `given()` to indicate to the provider that they should have some state in order to
be able to satisfy the interaction. You should agree upon the state and its specification
in discussion with the provider.

If you are defining a version 3 pact you may define provider states more richly, for example:

```python
(pact
    .given("this is a simple state as in v2")
    .and_given("also the user must exist", username="alex")
)
```

Now you may specify additional parameters to accompany your provider state text. These are
passed as keyword arguments, and they're optional. You may also provider additional provider
states using the `and_given()` call, which may be invoked many times if necessary. It and
`given()` have the same calling convention: a provider state name and any optional parameters.

## Expecting Variable Content
The default validity testing of equal values works great if that user information is always
static, but what happens if the user has a last updated field that is set to the current time
every time the object is modified? To handle variable data and make your tests more robust,
there are several helpful matchers:

### Includes(matcher, sample_data)

*Available in version 3.0.0+ pacts*

Asserts that the value should contain the given substring, for example::

```python
from pactman import Includes, Like
Like({
    'id': 123, # match integer, value varies
    'content': Includes('spam', 'Sample spamming content')  # content must contain the string "spam"
})
```

The `matcher` and `sample_data` are used differently by consumer and provider depending
upon whether they're used in the `with_request()` or `will_respond_with()` sections
of the pact. Using the above example:

#### Includes in request
When you run the tests for the consumer, the mock will verify that the data
the consumer uses in its request contains the `matcher` string, raising an AssertionError
if invalid. When the contract is verified by the provider, the `sample_data` will be
used in the request to the real provider service, in this case `'Sample spamming content'`.

#### Includes in response
When you run the tests for the consumer, the mock will return the data you provided
as `sample_data`, in this case `'Sample spamming content'`. When the contract is verified on the
provider, the data returned from the real provider service will be verified to ensure it
contains the `matcher` string.

### Term(matcher, sample_data)
Asserts the value should match the given regular expression. You could use this
to expect a timestamp with a particular format in the request or response where
you know you need a particular format, but are unconcerned about the exact date:

```python
from pactman import Term

(pact
 .given('UserA exists and is not an administrator')
 .upon_receiving('a request for UserA')
 .with_request(
   'post',
   '/users/UserA/info',
   body={'commencement_date': Term('\d+-\d+-\d', '1972-01-01')})
 .will_respond_with(200, body={
    'username': 'UserA',
    'last_modified': Term('\d+-\d+-\d+T\d+:\d+:\d+', '2016-12-15T20:16:01')
 }))
```

The `matcher` and `sample_data` are used differently by consumer and provider depending
upon whether they're used in the `with_request()` or `will_respond_with()` sections
of the pact. Using the above example:

#### Term in request
When you run the tests for the consumer, the mock will verify that the `commencement_date`
the consumer uses in its request matches the `matcher`, raising an AssertionError
if invalid. When the contract is verified by the provider, the `sample_data` will be
used in the request to the real provider service, in this case `1972-01-01`.

#### Term in response
When you run the tests for the consumer, the mock will return the `last_modified` you provided
as `sample_data`, in this case `2016-12-15T20:16:01`. When the contract is verified on the
provider, the regex will be used to search the response from the real provider service
and the test will be considered successful if the regex finds a match in the response.

### Like(sample_data)
Asserts the element's type matches the `sample_data`. For example:

```python
from pactman import Like
Like(123)  # Matches if the value is an integer
Like('hello world')  # Matches if the value is a string
Like(3.14)  # Matches if the value is a float
```

#### Like in request
When you run the tests for the consumer, the mock will verify that values are
of the correct type, raising an AssertionError if invalid. When the contract is
verified by the provider, the `sample_data` will be used in the request to the
real provider service.

#### Like in response
When you run the tests for the consumer, the mock will return the `sample_data`.
When the contract is verified on the provider, the values generated by the provider
service will be checked to match the type of `sample_data`.

#### Applying Like to complex data structures
When a dictionary is used as an argument for Like, all the child objects (and their child objects etc.)
will be matched according to their types, unless you use a more specific matcher like a Term.

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

### EachLike(sample_data, minimum=1)
Asserts the value is an array type that consists of elements
like `sample_data`. It can be used to assert simple arrays:

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

### Enforcing equality matching with Equals

*Available in version 3.0.0+ pacts*

If you have a sub-term of a `Like` which needs to match an exact value like the default
validity test then you can use `Equals`, for example::

```python
from pactman import Equals, Like
Like({
    'id': 123, # match integer, value varies
    'username': Equals('alex')  # username must always be "alex"
})
```

### Body payload rules
The `body` payload is assumed to be JSON data. In the absence of a `Content-Type` header
we assume `Content-Type: application/json; charset=UTF-8` (JSON text is Unicode and the
default encoding is UTF-8).

During verification non-JSON payloads are compared for equality

During mocking, the HTTP response will be handled as:

1. If there's no `Content-Type` header, assume JSON: serialise with `json.dumps()`, encode to
   UTF-8 and add the header `Content-Type: application/json; charset=UTF-8`.
2. If there's a `Content-Type` header and it says `application/json` then serialise with
   json.dumps() and use the charset in the header, defaulting to UTF-8.
3. Otherwise pass through the `Content-Type` header and body as-is.
   Binary data is not supported.


## Verifying Pacts Against a Service
You have two options for verifying pacts against a service you created:

1. Use the `pactman-verifier` command-line program which replays the pact assertions against
   a running instance of your service, or
2. Use the `pytest` support built into pactman to replay the pacts as test cases, allowing
   use of other testing mechanisms such as mocking and transaction control.

### Using `pactman-verifier`

Run `pactman-verifier -h` to see the options available. To run all pacts registered to a provider in a [Pact Broker]:

    pactman-verifier -b http://pact-broker.example/ <provider name> <provider url> <provider setup url>

You may also specify the broker URL in the environment variable `PACT_BROKER_URL`.

You can pass in a local pact file with `-l`, this will verify the service against the local file instead of the broker:

    pactman-verifier -l /tmp/localpact.json <provider name> <provider url> <provider setup url>

You can use `--custom-provider-header` to pass in headers to be passed to provider state setup and verify calls. it can 
be used multiple times

    pactman-verifier -b <broker url> --custom-provider-header "someheader:value" --custom-provider-header 
    "this:that" <provider name> <provider url> <provider state url>
    
An additional header may also be supplied in the `PROVIDER_EXTRA_HEADER` environment variable, though the command
line argument(s) would override this.

#### Provider States

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

### Verifying Pacts Using `pytest`

To verify pacts for a provider you would write a new pytest test module in the provider's test suite.
If you don't want it to be exercised in your usual unit test run you can call it `verify_pacts.py`.

Your test code needs to use the `pact_verifier` fixture provided by pactman, invoking
its `verify()` method with the URL to the running instance of your service (`pytest-django` provides
a handy `live_server` fixture which works well here) and a callback to set up provider states (described
below).

You'll need to include some extra command-line arguments to pytest (also described below) to indicate
where the pacts should come from, and whether verification results should be posted to a pact broker.

An example for a Django project might contain:

```python
from django.contrib.auth.models import User
from pactman.verifier.verify import ProviderStateMissing

def provider_state(name, **params):
    if name == 'the user "pat" exists':
        User.objects.create(username='pat', fullname=params['fullname'])
    else:
        raise ProviderStateMissing(name)

def test_pacts(live_server, pact_verifier):
    pact_verifier.verify(live_server.url, provider_state)
```

The test function may do any level of mocking and data setup using standard pytest fixtures - so mocking
downstream APIs or other interactions within the provider may be done with standard monkeypatching.

#### Provider states using `pytest`

The `provider_state` function passed to `pact_verifier.verify` will be passed the `providerState` and
`providerStates` for all pacts being verified.

- For pacts with **providerState** the `name` argument will be the `providerState` value,
  and `params` will be empty.
- For pacts with **providerStates** the function will be invoked once per entry in `providerStates`
  array with the `name` argument taken from the array entry `name` parameter, and `params` from
  the `params` parameter. 

#### Command line options to control `pytest` verifying pacts

Once you have written the pytest code, you need to invoke pytest with additional arguments:

`--pact-broker-url=<URL>` provides the base URL of the Pact broker to retrieve pacts from for the
provider. You must also provide `--pact-provider-name=<ProviderName>` to identify which provider to
retrieve pacts for from the broker. You may provider `--pact-consumer-name=<ConsumerName>` to limit
the pacts verified to just that consumer.

`--pact-files=<file pattern>` verifies some on-disk pact JSON files identified by the wildcard pattern
(unix glob pattern matching).

If you pulled the pacts from a broker and wish to publish verification results, use `--pact-publish-results`
to turn on publishing the results. This option also requires you to specify `--pact-provider-version=<version>`.

So, for example:

```bash
# verify some local pacts in /tmp/pacts
$ pytest --pact-files=/tmp/pacts/*.json tests/verify_pacts.py

# verify some pacts in a broker for the provider MyService
$ pytest --pact-broker-url=http://pact-broker.example/ --pact-provider-name=MyService tests/verify_pacts.py
```


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

2.22.0

- Better implementation of change in 2.21.0

2.21.0

- Handle warning level messages in command line output handler

2.20.0

- Fix pytest mode to correctly detect array element rule failure as a pytest failure
- Allow restricting pytest verification runs to a single consumer using --pact-consumer-name

2.19.0

- Correct teardown of pact context manager where the pact is used in multiple
  interactions (`with interaction1, interaction2` instead of `with pact`).

2.18.0

- Correct bug in cleanup that resulted in urllib mocking breaking.

2.17.0

- Handle absence of any provider state (!) in pytest setup.

2.16.0

- Delay shenanigans around checking pacts directory until pacts are actually written
  to allow module-level pact definition without side effects.

2.15.0

- Fix structure of serialisation for header matching rules.
- Add `"never"` to the `file_write_mode` options.
- Handle x-www-form-urlencoded POST request bodies.

2.14.0

- Improve verbose messages to clarify what they're saying.

2.13.0

- Add ability to supply additional headers to provider during verification (thanks @ryallsa)

2.12.1

- Fix pact-python Term compatibility

2.12.0

- Add `Equals` and `Includes` matchers for pact v3+
- Make verification fail if missing header specified in interaction
- Significantly improved support for pytest provider verification of pacts
- Turned pact state call failures into warnings rather than errors

2.11.0

- Ensure query param values are lists

2.10.0

- Allow `has_pact_with()` to accept `file_write_mode`
- Fix bug introduced in 2.9.0 where generating multiple pacts would result in a single pact
  being recorded

2.9.0

- Fix `with_request` when called with a dict query (thanks Cong)
- Make `start_mocking()` and `stop_mocking()` optional with non-server mocking
- Add shortcut so `python -m pactman.verifier.command_line` is just `python -m pactman`
  (mostly used in testing before release)
- Handle the `None` provider state
- Ensure pact spec versions are consistent across all mocks used to generate a pact file

2.8.0

- Close up some edge cases in body content during mocking, and document in README

2.7.0

- Added `and_given()` as a method of defining additonal provider states for v3+ pacts
- Added more tests for pact generation (serialisation) which fixed a few edge case bugs
- Fix handling of lower-case HTTP methods in verifier (thanks Cong!)

2.6.1

- Fix issue where mocked `urlopen` didn't handle the correct number of positional arguments

2.6.0

- Fix several issues cause by a failure to detect failure in several test cases
  (header, path and array element rules may not have been applied)
- Fix rules applying to a single non-first element in an array
- Fix generation of consumer / provider name in <v3 pacts

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
[Pact Broker]: https://docs.pact.io/getting_started/sharing_pacts
[Pact documentation]: https://docs.pact.io/
[Pact specification]: https://github.com/pact-foundation/pact-specification
[Pact specification version 3]: https://github.com/pact-foundation/pact-specification/tree/version-3
[Provider States]: https://docs.pact.io/documentation/provider_states.html
[pact-provider-verifier]: https://github.com/pact-foundation/pact-provider-verifier
[pyenv]: https://github.com/pyenv/pyenv
[virtualenv]: http://python-guide-pt-br.readthedocs.io/en/latest/dev/virtualenvs/
