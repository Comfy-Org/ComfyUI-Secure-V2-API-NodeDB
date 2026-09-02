"""Pure string helpers used by the vendored metadata parser."""


def merge_str_to_tuple(item1, item2):
    if not isinstance(item1, tuple):
        item1 = (item1,)
    if not isinstance(item2, tuple):
        item2 = (item2,)
    return item1 + item2


def merge_dict(dict1, dict2):
    result = dict1.copy()
    for key, value in dict2.items():
        result[key] = (
            merge_str_to_tuple(value, result[key]) if key in result else value
        )
    return result


def remove_quotes(string):
    return str(string).replace('"', "").replace("'", "")


def add_quotes(string):
    return f'"{str(string)}"'


def concat_strings(base, addition, separator=", "):
    return f"{base}{separator}{addition}" if base else addition
