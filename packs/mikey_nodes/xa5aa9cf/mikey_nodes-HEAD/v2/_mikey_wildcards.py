"""mikey_nodes find_and_replace_wildcards for Secure Nodes V2 (pin a5aa9cf637c4).

The function is copied verbatim from the pristine mikey_nodes.py (AST source segment, line range and sha256 below).
It reads `<user directory>/wildcards/<name>.txt`. In the guest that directory is a read-only in-memory tree holding
the files of the `mikey_wildcards` asset kind, which the node loads through the SDK before each run (load_tree).
The stand-ins `folder_paths`, `os` and `open` below serve that tree and nothing else; they are not upstream code.
Copied:
#   mikey_nodes/mikey_nodes.py L313-411 find_and_replace_wildcards
"""
import io as _stdio
import posixpath
import random
import re
import types

_ROOT = "/mikey-guest/user"
_TREE = {}


def load_tree(files):
    """files: {relative path under the wildcards directory: bytes}."""
    _TREE.clear()
    for name, data in files.items():
        _TREE[posixpath.join(_ROOT, "wildcards", name)] = data


def _isfile(path):
    return posixpath.normpath(path) in _TREE


def _isdir(path):
    prefix = posixpath.normpath(path).rstrip("/") + "/"
    return any(key.startswith(prefix) for key in _TREE)


def open(path, mode="r", encoding=None, **_kwargs):  # noqa: A001  (the copied function's builtin open)
    if mode != "r":
        raise PermissionError("the wildcard tree is read-only")
    return _stdio.StringIO(_TREE[posixpath.normpath(path)].decode(encoding or "utf-8"), newline=None)


os = types.SimpleNamespace(path=types.SimpleNamespace(join=posixpath.join, isfile=_isfile, isdir=_isdir,
                                                      dirname=posixpath.dirname))
folder_paths = types.SimpleNamespace(__file__="/mikey-guest/comfyui/folder_paths.py",
                                     get_user_directory=lambda: _ROOT)


# ---------------------------------------------------------------- upstream mikey_nodes.py
# mikey_nodes/mikey_nodes.py L313-411 (pristine sha256 832e4b74ab56a7fbb7c4b8cff463e6b03e884ce33ee777f25e5e2c81749660d5)
def find_and_replace_wildcards(prompt, offset_seed, debug=False):
    # wildcards use the __file_name__ syntax with optional |word_to_find
    wildcard_path = os.path.join(folder_paths.get_user_directory(), 'wildcards')
    # backwards compatibility with pre paths update to comfy
    if not os.path.isdir(wildcard_path):
        wildcard_path = os.path.join(os.path.dirname(folder_paths.__file__), 'wildcards')
    wildcard_regex = r'((\d+)\$\$)?__(!|\+|-|\*)?((?:[^|_]+_)*[^|_]+)((?:\|[^|]+)*)__'
    # r'(\[(\d+)\$\$)?__((?:[^|_]+_)*[^|_]+)((?:\|[^|]+)*)__\]?'
    match_strings = []
    random.seed(offset_seed)
    offset = offset_seed

    new_prompt = ''
    last_end = 0

    for m in re.finditer(wildcard_regex, prompt):
        full_match, lines_count_str, offset_type, actual_match, words_to_find_str = m.groups()
        # Append everything up to this match
        new_prompt += prompt[last_end:m.start()]

        # lock indicator
        lock_indicator = offset_type == '!'
        # increment indicator
        increment_indicator = offset_type == '+'
        # decrement indicator
        decrement_indicator = offset_type == '-'
        # random indicator
        random_indicator = offset_type == '*'

    #for full_match, lines_count_str, actual_match, words_to_find_str in re.findall(wildcard_regex, prompt):
        words_to_find = words_to_find_str.split('|')[1:] if words_to_find_str else None
        if debug:
            print(f'Wildcard match: {actual_match}')
            print(f'Wildcard words to find: {words_to_find}')
        lines_to_insert = int(lines_count_str) if lines_count_str else 1
        if debug:
            print(f'Wildcard lines to insert: {lines_to_insert}')
        match_parts = actual_match.split('/')
        if len(match_parts) > 1:
            wildcard_dir = os.path.join(*match_parts[:-1])
            wildcard_file = match_parts[-1]
        else:
            wildcard_dir = ''
            wildcard_file = match_parts[0]
        search_path = os.path.join(wildcard_path, wildcard_dir)
        file_path = os.path.join(search_path, wildcard_file + '.txt')
        if not os.path.isfile(file_path) and wildcard_dir == '':
            file_path = os.path.join(wildcard_path, wildcard_file + '.txt')
        if os.path.isfile(file_path):
            store_offset = None
            if actual_match in match_strings:
                store_offset = offset
                if lock_indicator:
                    offset = offset_seed
                elif random_indicator:
                    offset = random.randint(0, 1000000)
                elif increment_indicator:
                    offset = offset_seed + 1
                elif decrement_indicator:
                    offset = offset_seed - 1
                else:
                    offset = random.randint(0, 1000000)
            selected_lines = []
            with open(file_path, 'r', encoding='utf-8') as file:
                file_lines = file.readlines()
                num_lines = len(file_lines)
                if words_to_find:
                    for i in range(lines_to_insert):
                        start_idx = (offset + i) % num_lines
                        for j in range(num_lines):
                            line_number = (start_idx + j) % num_lines
                            line = file_lines[line_number].strip()
                            if any(re.search(r'\b' + re.escape(word) + r'\b', line, re.IGNORECASE) for word in words_to_find):
                                selected_lines.append(line)
                                break
                else:
                    start_idx = offset % num_lines
                    for i in range(lines_to_insert):
                        line_number = (start_idx + i) % num_lines
                        line = file_lines[line_number].strip()
                        selected_lines.append(line)
            if len(selected_lines) == 1:
                replacement_text = selected_lines[0]
            else:
                replacement_text = ','.join(selected_lines)
            new_prompt += replacement_text
            match_strings.append(actual_match)
            if store_offset is not None:
                offset = store_offset
                store_offset = None
            offset += lines_to_insert
            if debug:
                print('Wildcard prompt selected: ' + replacement_text)
        else:
            if debug:
                print(f'Wildcard file {wildcard_file}.txt not found in {search_path}')
        last_end = m.end()
    new_prompt += prompt[last_end:]
    return new_prompt

