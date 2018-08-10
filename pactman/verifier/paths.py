

def format_path(path):
    s = path[0]
    for elem in path[1:]:
        if isinstance(elem, int):
            s += f'[{elem}]'
        else:
            s += '.' + elem
    return s
