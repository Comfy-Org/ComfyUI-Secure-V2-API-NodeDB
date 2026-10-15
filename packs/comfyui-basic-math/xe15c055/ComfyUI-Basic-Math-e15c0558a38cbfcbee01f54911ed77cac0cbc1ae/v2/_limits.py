"""Proposed pack-local admission; native algorithms/regex engine are unchanged."""
import re

MAX_INTEGER_BITS = 2048
MAX_OUTPUT_INTEGER_BITS = 4096
MAX_TEXT_BYTES = 65536
MAX_ITEMS = 4096
MAX_DEPTH = 16
MAX_REGEX_SUBJECT = 8192
MAX_REGEX_PATTERN = 1024
MAX_REGEX_TOKENS = 256

class ProfileError(ValueError):
    pass

def value_work(value, *, integer_bits=MAX_INTEGER_BITS):
    """Charge a conservative repr bound BEFORE any native formatting/conversion."""
    items = 0
    text = 0
    active = set()
    def walk(v, depth):
        nonlocal items, text
        items += 1
        if items > MAX_ITEMS or depth > MAX_DEPTH:
            raise ProfileError('Basic Math aggregate tree budget')
        if v is None or type(v) is bool:
            text += 5
        elif type(v) is int:
            bits = v.bit_length()
            if bits > integer_bits:
                raise ProfileError('Basic Math integer bit budget')
            text += bits // 3 + 3
        elif type(v) is float:
            text += 32
        elif type(v) is str:
            # Python repr escapes ASCII controls/backslashes and quotes.
            text += 6 * len(v.encode('utf-8', errors='surrogatepass')) + 2
        elif type(v) in (list, tuple, dict):
            if id(v) in active:
                raise ProfileError('Basic Math cyclic tree outside profile')
            if len(v) > MAX_ITEMS - items:
                raise ProfileError('Basic Math aggregate tree budget')
            active.add(id(v))
            text += 2 + 4 * len(v)
            if type(v) is dict:
                for k, child in v.items():
                    walk(k, depth + 1)
                    walk(child, depth + 1)
            else:
                for child in v:
                    walk(child, depth + 1)
            active.remove(id(v))
        else:
            raise ProfileError('Basic Math plain-value profile; opaque objects are not materialized')
        if text > MAX_TEXT_BYTES:
            raise ProfileError('Basic Math aggregate text/format budget')
    walk(value, 0)
    return items, text

def regex_work(subject, pattern):
    if len(subject) > MAX_REGEX_SUBJECT or len(pattern.encode('utf-8', errors='surrogatepass')) > MAX_REGEX_PATTERN:
        raise ProfileError('Basic Math regex input budget')
    # Parse using the same pinned Python re engine. Malformed patterns are left
    # to the original source's re.match/bare-except -> False branch.
    try:
        parsed = re._parser.parse(pattern, 0)
    except (re.error, RecursionError, OverflowError):
        return
    count = 0
    repeats = 0
    simple = {'LITERAL', 'NOT_LITERAL', 'ANY', 'IN', 'CATEGORY'}
    def atom(op, arg):
        if str(op) == 'IN':
            if any(str(k) not in {'LITERAL', 'RANGE', 'CATEGORY', 'NEGATE'} for k, _ in arg):
                raise ProfileError('Basic Math unsupported regex character class')
        elif str(op) not in simple:
            raise ProfileError('Basic Math unsupported regex consuming atom')
    def visit(sequence, depth=0):
        nonlocal count, repeats
        if depth > MAX_DEPTH:
            raise ProfileError('Basic Math regex depth budget')
        for op, arg in sequence:
            count += 1
            if count > MAX_REGEX_TOKENS:
                raise ProfileError('Basic Math regex token budget')
            name = str(op)
            if name in simple:
                atom(op, arg)
            elif name == 'AT':
                pass
            elif name == 'SUBPATTERN':
                visit(arg[3], depth + 1)
            elif name in {'MAX_REPEAT', 'MIN_REPEAT', 'POSSESSIVE_REPEAT'}:
                repeats += 1
                low, high, body = arg
                if repeats > 1 or low > MAX_REGEX_SUBJECT or (high != re._constants.MAXREPEAT and high > MAX_REGEX_SUBJECT) or len(body) != 1:
                    raise ProfileError('Basic Math regex repetition profile')
                atom(*body[0])
            else:
                raise ProfileError('Basic Math unsupported regex syntax: ' + name)
    visit(parsed)

def before(source_class, kwargs):
    value_work(kwargs)
    schema = source_class.INPUT_TYPES()
    for group in ('required', 'optional'):
        for key, row in schema.get(group, {}).items():
            if key not in kwargs:
                continue
            value = kwargs[key]
            kind = str(row[0]) if isinstance(row[0], str) else 'COMBO'
            types = {'INT': (int, bool), 'FLOAT': (int, float, bool), 'INT,FLOAT': (int, float, bool), 'STRING': (str,), 'BOOLEAN': (bool,), 'COMBO': (str,)}
            if kind in types and type(value) not in types[kind]:
                raise ProfileError('Basic Math declared scalar profile: ' + key)
    name = source_class.__name__
    if name in ('BasicMath', 'IntMath') and all(k in kwargs for k in ('a', 'b', 'operation')):
        a, b, operation = (kwargs[k] for k in ('a', 'b', 'operation'))
        if type(a) in (int, bool) and type(b) in (int, bool):
            bits = 0
            if operation in ('+', '-'):
                bits = max(a.bit_length(), b.bit_length()) + 1
            elif operation == '*':
                bits = a.bit_length() + b.bit_length()
            elif operation == '**' and b >= 0 and abs(a) > 1:
                bits = abs(a).bit_length() * b
            elif operation == '<<' and b >= 0:
                bits = a.bit_length() + b
            if bits > MAX_OUTPUT_INTEGER_BITS:
                raise ProfileError('Basic Math projected integer work budget')
    if name == 'NumberRound' and type(kwargs.get('decimals')) in (int, bool) and abs(kwargs['decimals']) > 1000:
        raise ProfileError('Basic Math round decimal work budget')
    if name == 'StringComparison' and kwargs.get('operation') == 'a MATCH REGEX(b)' and all(k in kwargs for k in ('a', 'b', 'case_sensitive')):
        a, b = kwargs['a'], kwargs['b']
        if not kwargs['case_sensitive']:
            a, b = a.lower(), b.lower()
        regex_work(a, b)

def after(result):
    value_work(result, integer_bits=MAX_OUTPUT_INTEGER_BITS)
    return result
