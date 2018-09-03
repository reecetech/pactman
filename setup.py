import os

from setuptools import find_packages, setup


here = os.path.abspath(os.path.dirname(__file__))

about = {}
with open(os.path.join(here, "pactman", "__version__.py")) as f:
    exec(f.read(), about)


def read(filename):
    with open(os.path.join(here, filename), 'rb') as f:
        return f.read().decode('utf-8')


setup(
    name='pactman',
    version=about['__version__'],
    description=('Tools for creating and verifying consumer driven contracts'
                 ' using the Pact framework.'),
    long_description=read('README.md'),
    long_description_content_type='text/markdown',
    author='ReeceTech',
    author_email='richard.jones@reece.com.au',
    url='https://github.com/reecetech/pactman',
    entry_points='''
        [console_scripts]
        pactman-verifier=pactman.verifier.command_line:main
    ''',
    install_requires=[
        'pytest',
        'requests',
        'semver',
        'colorama',
        'restnavigator'
    ],
    packages=find_packages(),
    license='MIT, Copyright (c) 2018 ReeceTech',
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development :: Testing',
        'Topic :: Software Development :: Testing :: Mocking',
        'Topic :: Software Development :: Testing :: Acceptance',
    ]
)
