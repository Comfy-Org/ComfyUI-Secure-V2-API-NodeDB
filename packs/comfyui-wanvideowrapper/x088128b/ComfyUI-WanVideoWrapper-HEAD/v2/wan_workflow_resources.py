"""Digest-bound public asset IO into a private temporary SafeTensors file.

No host path is transported. Full-model guest disk/memory admission is a
separate execution gate; the bounds here are input validation, not admission.
"""
import hashlib
import json
import math
import re
import struct
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

RESOURCE_FORMAT = 'wan-workflow-asset-v1'
MAX_FILE_BYTES = 12 * 1024**3
MAX_HEADER_BYTES = 4 * 1024**2
CHUNK_BYTES = 8 * 1024**2
DTYPE_BYTES = {'F64': 8, 'F32': 4, 'F16': 2, 'BF16': 2, 'I64': 8,
               'I32': 4, 'I16': 2, 'I8': 1, 'U8': 1, 'BOOL': 1,
               'F8_E4M3': 1, 'F8_E5M2': 1}


def logical_name(name):
    return (isinstance(name, str) and bool(name) and len(name) <= 1024
            and '\\' not in name and ':' not in name and '\x00' not in name
            and not name.startswith('/')
            and all(part not in ('', '.', '..') for part in name.split('/')))


def validate_resource(resource):
    if type(resource) is not dict or set(resource) != {'format', 'kind', 'name', 'bytes', 'sha256'}:
        raise ValueError('Invalid owned Wan asset descriptor')
    if resource['format'] != RESOURCE_FORMAT or resource['kind'] not in ('text_encoders', 'diffusion_models', 'controlnet', 'loras'):
        raise ValueError('Invalid owned Wan asset kind')
    if not logical_name(resource['name']) or not resource['name'].lower().endswith(('.safetensors', '.sft')):
        raise ValueError('Wan workflow requires a logical SafeTensors catalogue name')
    if type(resource['bytes']) is not int or not 10 <= resource['bytes'] <= MAX_FILE_BYTES:
        raise ValueError('Wan weight file exceeds the bounded input domain')
    if not isinstance(resource['sha256'], str) or re.fullmatch('[0-9a-f]{64}', resource['sha256']) is None:
        raise ValueError('Wan workflow asset needs an exact SHA256')
    return resource


async def describe_asset(assets, kind, name):
    if not logical_name(name):
        raise ValueError('Wan workflow requires a confined logical catalogue name')
    ref = await assets.resolve(kind, name)
    descriptor = {'format': RESOURCE_FORMAT, 'kind': kind, 'name': name,
                  'bytes': await assets.size(ref), 'sha256': await assets.digest(ref)}
    return validate_resource(descriptor)


async def _resolve_bound(assets, resource):
    validate_resource(resource)
    ref = await assets.resolve(resource['kind'], resource['name'])
    if await assets.size(ref) != resource['bytes'] or await assets.digest(ref) != resource['sha256']:
        raise ValueError('Wan workflow resource changed since loader execution')
    return ref


async def _range(assets, ref, offset, length):
    value = await assets.read_range(ref, offset=offset, length=length)
    if not isinstance(value, bytes) or len(value) != length:
        raise ValueError('Wan workflow resource range was truncated')
    return value


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate SafeTensors header key')
        result[key] = value
    return result


async def inspect_header(assets, resource):
    ref = await _resolve_bound(assets, resource)
    prefix = await _range(assets, ref, 0, 8)
    length = struct.unpack('<Q', prefix)[0]
    if not 2 <= length <= MAX_HEADER_BYTES or 8 + length > resource['bytes']:
        raise ValueError('Invalid SafeTensors header bound')
    header = json.loads(await _range(assets, ref, 8, length), object_pairs_hook=_unique_object)
    if type(header) is not dict or len(header) > 50001:
        raise ValueError('Invalid SafeTensors header')
    intervals = []
    for name, item in header.items():
        if name == '__metadata__':
            if type(item) is not dict or any(not isinstance(k, str) or not isinstance(v, str) for k, v in item.items()):
                raise ValueError('Invalid SafeTensors metadata')
            continue
        if not isinstance(name, str) or not name or len(name) > 4096 or type(item) is not dict or set(item) != {'dtype', 'shape', 'data_offsets'}:
            raise ValueError('Invalid SafeTensors tensor descriptor')
        shape, offsets, dtype = item['shape'], item['data_offsets'], item['dtype']
        if not isinstance(dtype, str) or dtype not in DTYPE_BYTES:
            raise ValueError('Unsupported SafeTensors dtype')
        if type(shape) is not list or len(shape) > 16 or any(type(v) is not int or not 0 <= v <= 2**63 - 1 for v in shape):
            raise ValueError('Invalid SafeTensors shape')
        if type(offsets) is not list or len(offsets) != 2 or any(type(v) is not int for v in offsets):
            raise ValueError('Invalid SafeTensors offsets')
        start, end = offsets
        if start < 0 or end < start or end > resource['bytes'] - 8 - length or end - start != math.prod(shape) * DTYPE_BYTES[dtype]:
            raise ValueError('SafeTensors shape/offset mismatch')
        if end > start:
            intervals.append((start, end))
    position = 0
    for start, end in sorted(intervals):
        if start != position:
            raise ValueError('SafeTensors data contains holes or overlaps')
        position = end
    if position != resource['bytes'] - 8 - length:
        raise ValueError('SafeTensors header does not cover the complete file')
    return {name: item for name, item in header.items() if name != '__metadata__'}


@asynccontextmanager
async def private_weight_file(assets, resource):
    """Stream bounded ranges, verify all bytes, then expose only a guest path."""
    ref = await _resolve_bound(assets, resource)
    with TemporaryDirectory(prefix='wan-workflow-weights-') as directory:
        path = Path(directory) / 'weights.safetensors'
        digest = hashlib.sha256()
        with path.open('xb') as stream:
            for offset in range(0, resource['bytes'], CHUNK_BYTES):
                data = await _range(assets, ref, offset, min(CHUNK_BYTES, resource['bytes'] - offset))
                stream.write(data)
                digest.update(data)
                del data
        if digest.hexdigest() != resource['sha256'] or await assets.digest(ref) != resource['sha256']:
            raise ValueError('Complete Wan workflow weight SHA256 changed')
        yield path
