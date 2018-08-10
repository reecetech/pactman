import pytest

from pactman.verifier.parse_header import Part, parse_header


def test_comma_whitespace_ignored():
    assert list(parse_header('spam, ham')) == list(parse_header('spam,ham'))


@pytest.mark.parametrize(['header', 'result'], [
    (('audio/*; q=0.2, audio/basic'), [Part(['audio/*'], []), Part(['audio/basic'], [('q', '0.2')])]),
    (('''text/plain; q=0.5, text/html,
         text/x-dvi; q="0.8", text/x-c'''), [Part(['text/plain'], []),
                                             Part(['text/html', 'text/x-dvi'], [('q', '0.5')]),
                                             Part(['text/x-c'], [('q', '0.8')])]),
    (('"xyz\\"zy",W/"r2d2,xxxx","spam"'), [Part(['"xyz\\"zy"', 'W/"r2d2,xxxx"', '"spam"'], [])]),
])
def test_accept_variants(header, result):
    assert list(parse_header(header)) == result
