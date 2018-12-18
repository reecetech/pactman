# Raising issues

_Before raising an issue, please ensure that you are using the latest version of pactman._

Please provide the following information with your issue to enable us to respond as quickly as possible.

* The relevant versions of the packages you are using.
* The steps to recreate your issue.
* The full stacktrace if there is an exception.
* An executable code example where possible.

# Contributing

1. Fork it
2. Create your feature branch (`git checkout -b my-new-feature`)
3. Commit your changes (`git commit -am 'Add some feature'`)
4. Push to the branch (`git push origin my-new-feature`)
5. Create new Pull Request

If you are intending to implement a fairly large feature we'd appreciate if you open
an issue with GitHub detailing your use case and intended solution to discuss how it
might impact other work that is in flight.

We also appreciate it if you take the time to update and write tests for any changes
you submit.


# Releasing

When a release is ready upload it to pypi and then tag like so:

    git tag -am 'Release 2.6.1' 2.6.1
    git push origin 2.6.1
