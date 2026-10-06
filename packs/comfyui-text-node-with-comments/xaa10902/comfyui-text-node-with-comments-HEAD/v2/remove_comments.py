import re


def remove_comments(text):
    def replacer(match):
        value = match.group(0)
        # Removing, rather than replacing with a space, is upstream behavior.
        return "" if value.startswith("/") else value

    pattern = re.compile(
        r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"',
        re.DOTALL | re.MULTILINE,
    )
    return re.sub(pattern, replacer, text)
