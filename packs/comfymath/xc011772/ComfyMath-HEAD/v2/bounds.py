"""Pack-local supported workload admission; not physical allocation authority."""
import math
import numpy as np

MAX_INPUT_BITS = 2048
MAX_OUTPUT_BITS = 4096
MAX_FACTORIAL = 512
MAX_EXPONENT = 4096
MAX_VECTOR = 4

# Closed exact scalar classes, never object/structured/string/datetime subclasses.
NP_TYPES = frozenset(np.dtype(name).type for name in (
    'bool', 'int8', 'int16', 'int32', 'int64', 'uint8', 'uint16', 'uint32', 'uint64',
    'float16', 'float32', 'float64', 'complex64', 'complex128'))

def scalar(value):
    if type(value) not in (bool, int, float, complex) and type(value) not in NP_TYPES:
        raise TypeError('expected a closed numeric scalar')
    if type(value) in (int, bool) or isinstance(value, np.integer):
        if abs(int(value)).bit_length() > MAX_INPUT_BITS:
            raise ValueError('input integer bit budget exceeded')

def vector(value):
    if type(value) not in (tuple, list):
        raise TypeError('vector must be an exact flat tuple/list')
    if len(value) > MAX_VECTOR:
        raise ValueError('vector length budget exceeded')
    for item in value:
        scalar(item)

def integer_projection(op, a, b=None):
    # Source bool-as-int semantics and small-domain errors are retained.
    if type(a) not in (int, bool) or (b is not None and type(b) not in (int, bool)):
        raise TypeError('integer operation requires integer operands')
    bits = max(1, abs(a).bit_length())
    other = max(1, abs(b).bit_length()) if b is not None else 0
    if op == 'Factorial':
        if a < 0: return  # math.factorial emits the original native error.
        if a > MAX_FACTORIAL: raise ValueError('factorial work budget exceeded')
        projected = math.ceil(math.lgamma(a + 1) / math.log(2)) + 1
    elif op == 'Pow':
        if abs(b) > MAX_EXPONENT: raise ValueError('power work budget exceeded')
        if b < 0: return  # native float/zero/overflow behavior, no integer expansion.
        projected = 1 if abs(a) <= 1 else bits * b
    elif op in ('Shl', 'Shr'):
        if b < 0: return  # native negative shift error.
        if b > MAX_EXPONENT: raise ValueError('shift work budget exceeded')
        projected = bits + b if op == 'Shl' else bits
    elif op == 'Mul': projected = bits + other
    elif op == 'Sqr': projected = bits * 2
    elif op == 'Cube': projected = bits * 3
    elif op in ('Add', 'Sub'): projected = max(bits, other) + 1
    else: projected = max(bits, other) + 1
    if projected > MAX_OUTPUT_BITS:
        raise ValueError('projected integer output budget exceeded')

def preflight(node_id, fields):
    for name, value in fields.items():
        if name in ('cls', 'image'): continue
        if name in ('op', 'resolution'):
            if type(value) is str and len(value) > 128:
                raise ValueError('choice text budget exceeded')
            # Nonstring numeric resolution retains native .split AttributeError.
            if type(value) is not str: scalar(value)
        elif node_id.startswith('CM_Vec') or node_id.startswith('CM_BreakoutVec'):
            if name == 'a' or (name == 'b' and 'ScalarOperation' not in node_id): vector(value)
            else: scalar(value)
        else: scalar(value)
    if node_id.startswith('CM_Vec') and 'a' in fields:
        # Object-dtype numeric dot can multiply Python ints. Project its tiny
        # fixed work/result before np.array, not only after the operation.
        a, b = fields['a'], fields.get('b')
        if fields.get('op') == 'Dot' and type(b) in (tuple, list):
            if all(type(x) in (int, bool) for x in (*a, *b)):
                left = max((max(1, abs(x).bit_length()) for x in a), default=1)
                right = max((max(1, abs(x).bit_length()) for x in b), default=1)
                if left + right + 2 > MAX_OUTPUT_BITS:
                    raise ValueError('projected vector integer output budget exceeded')
    if node_id in ('CM_IntUnaryOperation', 'CM_IntBinaryOperation'):
        integer_projection(fields['op'], fields['a'], fields.get('b'))
    elif node_id in ('CM_FloatUnaryOperation', 'CM_FloatBinaryOperation'):
        # A prior FLOAT Round/Floor result may be an actual Python int. Preserve
        # that native type, but bound the integer computation before expansion.
        values = [fields[n] for n in ('a', 'b') if n in fields]
        if all(type(v) in (int, bool) for v in values):
            integer_projection(fields['op'], fields['a'], fields.get('b'))

def output_guard(output):
    def check(value):
        if type(value) in (tuple, list):
            if len(value) > 4: raise ValueError('output arity budget exceeded')
            for item in value: check(item)
        elif type(value) is int and abs(value).bit_length() > MAX_OUTPUT_BITS:
            raise ValueError('output integer bit budget exceeded')
    check(output.result)
    return output
