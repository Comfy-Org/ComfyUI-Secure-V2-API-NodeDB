"""Lossless SafeTensors decode using published immutable asset ranges."""
from safetensors.torch import load
import json
import struct
from .bounds import state_bounds
from .safetensor_preflight import preflight

# An implementation chunk size, not a new model-size or dtype restriction.
RANGE_BYTES = 64 * 1024

def decode_safetensors(data, output_itemsize=4):
    """Keep native stored dtypes; the native Boost operation casts afterward."""
    if type(data) is not bytes:
        raise TypeError('immutable SafeTensors bytes required')
    return state_bounds(load(data), output_itemsize=output_itemsize)


def singleton_header(key, descriptor):
    """Encode a native SafeTensors header for one validated original tensor."""
    start, end = descriptor['data_offsets']
    singleton = {key: dict(descriptor, data_offsets=[0, end - start])}
    encoded_header = json.dumps(singleton, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    encoded_header += b' ' * (-len(encoded_header) % 8)
    return struct.pack('<Q', len(encoded_header)) + encoded_header


def decode_singleton(key, data):
    """Use the real decoder, preserving scalar/BF16/empty tensor bytes."""
    if type(data) is not bytes:
        raise TypeError('immutable SafeTensors bytes required')
    return load(data)[key]

async def state_from_asset_ranges(assets, asset, output_itemsize=4):
    """Use genuine brokered bytes without a BF16 tensor-upload graph edge.

    Validate the original layout globally, then decode each tensor with the
    real SafeTensors decoder. Only the current tensor has an encoded byte copy;
    scalar, BF16 and empty shapes retain the stored dtype and exact bytes.
    """
    size = await assets.size(asset)
    header = await preflight(assets, asset, size, output_itemsize)
    original_head = await assets.read_range(asset, 0, 8)
    if type(original_head) is not bytes or len(original_head) != 8:
        raise ValueError('short SafeTensors header')
    data_start = 8 + struct.unpack('<Q', original_head)[0]
    state = {}
    for key, descriptor in header.items():
        if key == '__metadata__':
            continue
        start, end = descriptor['data_offsets']
        buffer = bytearray(singleton_header(key, descriptor))
        for offset in range(data_start + start, data_start + end, RANGE_BYTES):
            length = min(RANGE_BYTES, data_start + end - offset)
            chunk = await assets.read_range(asset, offset, length)
            if type(chunk) is not bytes or len(chunk) != length:
                raise ValueError('short SafeTensors asset range')
            buffer.extend(chunk)
        state[key] = decode_singleton(key, bytes(buffer))
        del buffer
    return state_bounds(state, output_itemsize=output_itemsize)
