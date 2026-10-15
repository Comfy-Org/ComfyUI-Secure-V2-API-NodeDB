from typing import Any, Callable, Mapping
DEFAULT_BOOL = ('BOOLEAN', {'default': False})
BOOL_UNARY_OPERATIONS: Mapping[str, Callable[[bool], bool]] = {'Not': lambda a: not a}
BOOL_BINARY_OPERATIONS: Mapping[str, Callable[[bool, bool], bool]] = {'Nor': lambda a, b: not (a or b), 'Xor': lambda a, b: a ^ b, 'Nand': lambda a, b: not (a and b), 'And': lambda a, b: a and b, 'Xnor': lambda a, b: not a ^ b, 'Or': lambda a, b: a or b, 'Eq': lambda a, b: a == b, 'Neq': lambda a, b: a != b}
