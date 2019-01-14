from pactman import Term


def test_regex():
    assert Term('[a-zA-Z]', 'abcXYZ').ruby_protocol() == {
        'json_class': 'Pact::Term',
        'data': {
            'matcher': {
                'json_class': 'Regexp',
                's': '[a-zA-Z]',
                'o': 0},
            'generate': 'abcXYZ'}
    }
