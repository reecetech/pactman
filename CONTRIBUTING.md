# Raising issues

_Before raising an issue, please ensure that you are using the latest version of pactman._

Please provide the following information with your issue to enable us to respond as quickly as possible.

* The relevant versions of the packages you are using.
* The steps to recreate your issue.
* The full stacktrace if there is an exception.
* An executable code example where possible.

# Contributing

To setup a development environment:

1. Clone the repository `https://github.com/reecetech/pactman` and invoke `git submodule update --init`.
2. Install Python 3.6 from source or using a tool like [pyenv].
3. It's recommended (but not required) to use [pre-commit] to automatically handle code styling.
   After installing `pre-commit` run `pre-commit install` in your local pactman clone.

Then for a change you're making:

1. Create your feature branch (`git checkout -b my-new-feature`).
2. Commit your changes (`git commit -am 'Add some feature'`).
3. Push to the branch (`git push origin my-new-feature`).
4. Run the test suite (`tox`).
4. Create new Pull Request.

If you are intending to implement a fairly large feature we'd appreciate if you open
an issue with GitHub detailing your use case and intended solution to discuss how it
might impact other work that is in flight.

We also appreciate it if you take the time to update and write tests for any changes
you submit.

# Releasing

To package the application, run:
`python setup.py sdist`

This creates a `dist/pactman-N.N.N.tar.gz` file, where the Ns are the current version.
From there you can use pip to install it:
`pip install ./dist/pactman-N.N.N.tar.gz`


[pyenv]: https://github.com/pyenv/pyenv
[pre-commit]: https://pre-commit.com/
