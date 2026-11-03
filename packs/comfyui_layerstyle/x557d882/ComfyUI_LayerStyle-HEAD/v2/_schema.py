"""Retained source-derived schemas, reconstructed through public io constructors."""
import copy
import inspect
import json
from enum import Enum
from pathlib import Path

from comfy_api.latest import io

ROWS = json.loads(Path(__file__).with_name('_schemas.json').read_text())


def decode(value):
    if isinstance(value, list):
        return [decode(item) for item in value]
    if not isinstance(value, dict):
        return value
    tag = value.get('$type')
    if tag == 'tuple':
        return tuple(decode(item) for item in value['items'])
    if tag == 'enum':
        kind = getattr(io, value['enum'])
        assert issubclass(kind, Enum)
        return kind[value['name']]
    if tag == 'remote-options':
        attrs = decode(value['attrs'])
        return construct(io.RemoteOptions, attrs)
    if tag == 'io-class':
        return io_type(value['io_type'])
    if tag is not None:
        raise ValueError(f'Unsupported retained schema encoding {tag!r}')
    return {key: decode(item) for key, item in value.items()}


def io_type(name):
    for candidate in vars(io).values():
        if isinstance(candidate, type) and getattr(candidate, 'io_type', None) == name:
            return candidate
    return io.Custom(name)


def construct(constructor, fields):
    args = copy.deepcopy(fields)
    if 'rawLink' in args:
        args['raw_link'] = args.pop('rawLink')
    parameters = inspect.signature(constructor).parameters
    extra = {key: value for key, value in args.items() if key not in parameters}
    for key in extra:
        del args[key]
    result = constructor(**args)
    # Some native widgets inherit metadata that their constructor does not
    # accept (Color.Input creates extra_dict={} via WidgetInput). Preserve it
    # only when the public constructor actually produced the retained value.
    # Missing fields, including unknown None fields, are explicit refusals.
    for key, value in extra.items():
        attribute = 'rawLink' if key == 'raw_link' else key
        if not hasattr(result, attribute) or getattr(result, attribute) != value:
            raise ValueError(f'Unsupported retained schema field {constructor}: {key}={value!r}')
    return result


def schema_for(node_id):
    row = ROWS[node_id]['schema']
    attrs = decode(row['attrs'])
    attrs['inputs'] = [construct(io_type(item['io_type']).Input, decode(item['attrs'])) for item in row['inputs']]
    attrs['outputs'] = [construct(io_type(item['io_type']).Output, decode(item['attrs'])) for item in row['outputs']]
    attrs['hidden'] = [io.Hidden[name] for name in row['hidden']]
    return io.Schema(**attrs)
