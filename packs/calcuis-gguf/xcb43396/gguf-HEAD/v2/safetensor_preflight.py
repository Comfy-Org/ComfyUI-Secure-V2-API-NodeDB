"""Validate the complete immutable SafeTensors layout before payload reads."""
import json
import math
import struct

# The installed native SafeTensors parser's format limit, not a transport
# request ceiling. Verified against actual native decoder boundary errors.
MAX_HEADER_BYTES = 100_000_000
HEADER_CHUNK_BYTES = 64 * 1024

DTYPE_BYTES = {'BOOL': 1, 'U8': 1, 'I8': 1, 'I16': 2, 'U16': 2, 'I32': 4, 'U32': 4, 'I64': 8, 'U64': 8, 'F16': 2, 'BF16': 2, 'F32': 4, 'F64': 8, 'F8_E4M3': 1, 'F8_E5M2': 1, 'F8_E8M0': 1}


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate SafeTensors header key')
        value[key] = item
    return value


async def preflight(assets, asset, size, output_itemsize):
    if type(size) is not int or size < 8:
        raise ValueError('invalid state artifact size')
    if type(output_itemsize) is not int or output_itemsize < 1:
        raise ValueError('positive projected output item size required')
    head = await assets.read_range(asset, 0, 8)
    if type(head) is not bytes or len(head) != 8:
        raise ValueError('short SafeTensors header')
    length = struct.unpack('<Q', head)[0]
    validate_header_length(size, length)
    raw = await read_header_chunks(assets, asset, length)
    header = json.loads(raw, object_pairs_hook=unique_object)
    return validate_header(header, size, length, output_itemsize)


def validate_header(header, size, length, output_itemsize):
    """Pure descriptor validation shared by genuine asset and byte fixtures."""
    validate_header_length(size, length)
    if type(output_itemsize) is not int or output_itemsize < 1:
        raise ValueError('positive projected output item size required')
    if type(header) is not dict:
        raise ValueError('closed SafeTensors header required')
    tensors = {key: value for key, value in header.items() if key != '__metadata__'}
    metadata = header.get('__metadata__', {})
    if type(metadata) is not dict or any(type(k) is not str or type(v) is not str for k, v in metadata.items()):
        raise ValueError('SafeTensors metadata must contain string pairs')
    spans = []
    for key, value in tensors.items():
        if type(key) is not str or type(value) is not dict:
            raise ValueError('string key and tensor descriptor required')
        if set(value) != {'dtype', 'shape', 'data_offsets'}:
            raise ValueError('closed tensor descriptor required')
        shape, offsets = value['shape'], value['data_offsets']
        if type(shape) is not list or any(type(axis) is not int or axis < 0 for axis in shape):
            raise ValueError('nonnegative tensor shape required before materialization')
        if type(offsets) is not list or len(offsets) != 2 or any(type(offset) is not int for offset in offsets) or not 0 <= offsets[0] <= offsets[1] <= size - length - 8:
            raise ValueError('tensor data span outside asset')
        if type(value['dtype']) is not str or value['dtype'] not in DTYPE_BYTES:
            raise ValueError('unsupported SafeTensors dtype budget')
        count = math.prod(shape)
        expected = count * DTYPE_BYTES[value['dtype']]
        if expected != offsets[1] - offsets[0]:
            raise ValueError('tensor dtype/shape/data span mismatch')
        spans.append(tuple(offsets))
    cursor = 0
    for start, end in sorted(spans):
        if start != cursor:
            raise ValueError('SafeTensors payload has overlapping spans or holes')
        cursor = end
    if cursor != size - length - 8:
        raise ValueError('SafeTensors payload has unreferenced bytes')
    return header


def validate_header_length(size, length):
    if type(size) is not int or size < 8 or type(length) is not int or not 2 <= length <= MAX_HEADER_BYTES or length + 8 > size:
        raise ValueError('invalid native SafeTensors header span')


def header_ranges(length):
    """Each request stays within the existing SDK per-call range ceiling."""
    for offset in range(8, 8 + length, HEADER_CHUNK_BYTES):
        yield offset, min(HEADER_CHUNK_BYTES, 8 + length - offset)


async def read_header_chunks(assets, asset, length):
    buffer = bytearray()
    for offset, count in header_ranges(length):
        chunk = await assets.read_range(asset, offset, count)
        append_header_chunk(buffer, chunk, count)
    return bytes(buffer)


def append_header_chunk(buffer, chunk, count):
    """Shared strict assembly for genuine SDK ranges and native byte fixtures."""
    if type(chunk) is not bytes or len(chunk) != count:
        raise ValueError('short SafeTensors header')
    buffer.extend(chunk)
