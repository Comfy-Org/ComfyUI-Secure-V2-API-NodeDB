"""Whole authored wildcard record over the existing public text/CAS contract.

Private source-family successor, not manager registration or legacy file import.
No temporary VALUE, raw read, TTL, sharding, truncation or hidden conflict retry.
"""
from __future__ import annotations

import json

from ..secure_algorithms.bounds import bounded_json
from ._durable_wildcard_math import FullLibraryExpander
from ._wildcard_document_bounds import _preflight_json_depth

KEY = 'wildcard.library.text.v1'
FORMAT = 'loramanager.wildcard-library.v1'
MAX_RECORD_BYTES = 1024 * 1024


def _storage(storage):
    if storage is not None:
        return storage
    # Ordinary production path; fixtures supply only the same public domain methods.
    from comfy_api.latest import sdk
    return sdk.ctx().storage


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate stored wildcard JSON key')
        result[key] = value
    return result


def _constant(_value):
    raise ValueError('Nonfinite stored wildcard JSON')


def validate_document(document):
    if (type(document) is not dict or set(document) != {'format', 'entries'}
            or document['format'] != FORMAT):
        raise ValueError('Wildcard library document identity is invalid')
    # Retains the predecessor candidate/tree/work policies. The durable encoded
    # limit is checked separately and cannot promote the old 4MiB fixture tier.
    FullLibraryExpander(document['entries'])


def encode_document(entries):
    document = {'format': FORMAT, 'entries': entries}
    validate_document(document)
    parts = []
    size = 0
    encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    for part in encoder.iterencode(document):
        size += len(part.encode('utf-8'))
        if size > MAX_RECORD_BYTES:
            raise ValueError('Encoded durable wildcard record exceeds 1MiB byte bound')
        parts.append(part)
    return ''.join(parts)


def decode_document(value):
    if (type(value) is not str or len(value) > MAX_RECORD_BYTES or
            len(value.encode('utf-8')) > MAX_RECORD_BYTES):
        raise ValueError('Stored durable wildcard record exceeds byte bound')
    _preflight_json_depth(value)
    document = json.loads(value, object_pairs_hook=_pairs, parse_constant=_constant)
    validate_document(document)
    return document


async def read_library(*, storage=None):
    record = await _storage(storage).read(KEY)
    if record['value'] is None:
        # Only truly absent data gets the native empty-library fallback.
        return {'revision': record['revision'], 'entries': {}}
    document = decode_document(record['value'])
    return {'revision': record['revision'], 'entries': document['entries']}


async def save_library(entries, revision, *, storage=None):
    # Refuse invalid/oversized whole records before resolving or calling storage.
    value = encode_document(entries)
    result = await _storage(storage).compare_and_set(KEY, revision, value)
    return {'updated': result['updated'], 'revision': result['revision']}


async def expand_saved_text(text, seed=None, *, storage=None):
    bounded_json([text, seed])
    # Expansion needs only the documented get operation, not revision/CAS.
    # Preserve the old route APIs as explicitly unqualified; no synthetic revision.
    value = await _storage(storage).get(KEY)
    entries = {} if value is None else decode_document(value)['entries']
    return FullLibraryExpander(entries).expand_text(text, seed)
