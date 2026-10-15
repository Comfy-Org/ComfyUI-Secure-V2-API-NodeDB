"""Whole authored model records over public durable text storage.

The host selects account/pack identity and backing. No VALUE/TTL fallback,
automatic migration, truncation, sharding, quota reset or hidden CAS retry.
"""
import json
from comfy_api.latest import sdk

from .documents import _validate_tree, _preflight_json_depth
from .managed_library import FORMAT, _identity

MAX_RECORD_BYTES = 1024 * 1024


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate stored JSON key')
        result[key] = value
    return result


def _constant(_value):
    raise ValueError('Nonfinite stored JSON')


def validate_record(document, digest=None):
    if (type(document) is not dict or set(document) != {'format', 'sha256', 'metadata'}
            or document['format'] != FORMAT or type(document['sha256']) is not str
            or len(document['sha256']) != 64
            or any(char not in '0123456789abcdef' for char in document['sha256'])
            or (digest is not None and document['sha256'] != digest)
            or type(document['metadata']) is not dict):
        raise ValueError('Corrupt stored model record')
    _validate_tree(document, MAX_RECORD_BYTES)


def encode_record(document):
    validate_record(document)
    # Iterative encoding bounds punctuation and key overhead as well as text;
    # no giant tensor, typed data snapshot, or post-publication size refusal.
    parts = []
    size = 0
    encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    for part in encoder.iterencode(document):
        size += len(part.encode('utf-8'))
        if size > MAX_RECORD_BYTES:
            raise ValueError('Encoded durable model record exceeds byte bounds')
        parts.append(part)
    return ''.join(parts)


def decode_record(value):
    if type(value) is not str or len(value) > MAX_RECORD_BYTES or len(value.encode('utf-8')) > MAX_RECORD_BYTES:
        raise ValueError('Stored durable model record exceeds byte bounds')
    _preflight_json_depth(value)
    document = json.loads(value, object_pairs_hook=_pairs, parse_constant=_constant)
    validate_record(document)
    return document


async def read_document(key, kind):
    if kind != 'model-edits':
        raise ValueError('Durable adapter only admits model records')
    result = await sdk.ctx().storage.read(key)
    return {'revision': result['revision'], 'document': None if result['value'] is None else decode_record(result['value'])}


async def compare_and_set_document(key, kind, revision, document):
    if kind != 'model-edits':
        raise ValueError('Durable adapter only admits model records')
    value = encode_record(document)
    result = await sdk.ctx().storage.compare_and_set(key, revision, value)
    # The conflict value is not exported to the browser or silently merged.
    return {'updated': result['updated'], 'revision': result['revision']}


async def read_record(name):
    _, digest, key = await _identity(name)
    record = await read_document(key, 'model-edits')
    document = record['document']
    if document is not None:
        validate_record(document, digest)
    return {'sha256': digest, 'revision': record['revision'],
            'metadata': None if document is None else document['metadata']}
