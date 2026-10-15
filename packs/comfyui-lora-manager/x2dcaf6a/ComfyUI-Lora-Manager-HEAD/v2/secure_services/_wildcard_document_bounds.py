"""Unchanged predecessor document guards, isolated from tensor storage."""
import math

MAX_NODES = 65536
MAX_DEPTH = 32

def _validate_tree(document, limit):
    pending = [(document, 0)]
    count = total = 0
    while pending:
        value, depth = pending.pop()
        count += 1
        if count > MAX_NODES or depth > MAX_DEPTH:
            raise ValueError('Document exceeds work/depth bounds')
        if value is None or type(value) is bool:
            continue
        if type(value) is int:
            if value.bit_length() > 64:
                raise ValueError('Document integer exceeds bounds')
        elif type(value) is float:
            if not math.isfinite(value):
                raise ValueError('Document numbers must be finite')
        elif type(value) is str:
            if len(value) > limit:
                raise ValueError('Document string exceeds bounds')
            total += len(value.encode('utf-8'))
            if total > limit:
                raise ValueError('Document text exceeds byte bounds')
        elif type(value) is dict:
            if any(type(key) is not str for key in value):
                raise ValueError('Document keys must be text')
            if 2 * len(value) > MAX_NODES - count - len(pending):
                raise ValueError('Document dictionary exceeds bounds')
            for key, item in value.items():
                pending.extend(((key, depth + 1), (item, depth + 1)))
        elif type(value) is list:
            if len(value) > MAX_NODES - count - len(pending):
                raise ValueError('Document array exceeds bounds')
            pending.extend((item, depth + 1) for item in value)
        else:
            raise ValueError('Document must contain only closed JSON data')

def _preflight_json_depth(text):
    quoted = escaped = False
    depth = 0
    for char in text:
        if quoted:
            if escaped: escaped = False
            elif char == '\\': escaped = True
            elif char == '"': quoted = False
        elif char == '"': quoted = True
        elif char in '[{':
            depth += 1
            if depth > MAX_DEPTH:
                raise ValueError('Stored document exceeds depth bounds')
        elif char in ']}': depth -= 1
