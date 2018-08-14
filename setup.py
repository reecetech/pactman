import os

from setuptools import setup


here = os.path.abspath(os.path.dirname(__file__))

about = {}
with open(os.path.join(here, "pactman", "__version__.py")) as f:
    exec(f.read(), about)


def read(filename):
    path = os.path.realpath(os.path.join(os.path.dirname(__file__), filename))
    with open(path, 'rb') as f:
        return f.read().decode('utf-8')


setup(
    name='pactman',
    version=about['__version__'],
    description=('Tools for creating and verifying consumer driven contracts'
                 ' using the Pact framework.'),
    long_description=read('README.md'),
    author='ReeceTech',
    author_email='richard.jones@reece.com.au',
    url='https://github.com/reecetech/pact-python',
    entry_points='''
        [console_scripts]
        pact-verifier=pactman.verifier.command_line:main
    ''',
    install_requires=[
        'pytest',
        'requests',
        'semver',
        'colorama',
        'restnavigator'
        # 'click',
    ],
    packages=['pactman'],
    license=read('LICENSE')
)
