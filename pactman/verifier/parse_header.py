from functools import total_ordering


@total_ordering
class Part:
    def __init__(self, value, params):
        self.value = value
        self.params = params

    def has_param(self, name):
        for k, v in self.params:
            if k == name:
                return True
        return False

    def __repr__(self):
        return f'<Part {", ".join(self.value + ["%s=%s"%i for i in self.params])}>'

    def __eq__(self, other):
        return (self.value, self.params) == (other.value, other.params)

    def __lt__(self, other):
        return (self.value, self.params) < (other.value, other.params)


def _parseparam(s, marker):
    while s[:1] == marker:
        s = s[1:]
        end = s.find(marker)
        while end > 0 and (s.count('"', 0, end) - s.count('\\"', 0, end)) % 2:
            end = s.find(marker, end + 1)
        if end < 0:
            end = len(s)
        f = s[:end]
        yield f.strip()
        s = s[end:]


def parse_header(line):
    parts = _parseparam(';' + line, ';')
    for part in parts:
        params = []
        key = []
        for option in _parseparam(',' + part, ','):
            i = option.find('=')
            if i >= 0:
                name = option[:i].strip().lower()
                value = option[i+1:].strip()
                if len(value) >= 2 and value[0] == value[-1] == '"':
                    value = value[1:-1]
                    value = value.replace('\\\\', '\\').replace('\\"', '"')
                params.append((name, value))
            else:
                key.append(option)
        yield Part(key, params)
