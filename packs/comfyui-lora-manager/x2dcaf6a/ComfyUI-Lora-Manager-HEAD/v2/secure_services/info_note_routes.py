"""Closed note handlers; authenticated routing is provided by the trusted host.

Whole-record durable text admission is explicitly <=1MiB, not the old 4MiB
temporary fixture. Registration stays held until actual composition is proved.
"""
from __future__ import annotations

import json
import re

from .documents import _validate_tree
from .durable_model_records import (MAX_RECORD_BYTES, encode_record, validate_record,
    compare_and_set_document, read_document, read_record)
from .managed_library import FORMAT, _identity, _logical

MAX_ENVELOPE_BYTES = 1024**2  # Independent public route request/response ceiling.


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def _constant(_value):
    raise ValueError('Nonfinite JSON is not allowed')


def _parse(body):
    if type(body) is not str or len(body) > MAX_ENVELOPE_BYTES:
        raise ValueError('Commit envelope exceeds bounds')
    if len(body.encode('utf-8')) > MAX_ENVELOPE_BYTES:
        raise ValueError('Commit envelope exceeds bounds')
    depth = 0
    quoted = escaped = False
    for char in body:
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in '{[':
            depth += 1
            if depth > 34:
                raise ValueError('Commit envelope exceeds depth bounds')
        elif char in '}]':
            depth -= 1
    return json.loads(body, object_pairs_hook=_pairs, parse_constant=_constant)


def _revision(value):
    if value is not None and (type(value) is not str or not value
                              or len(value.encode('utf-8')) > 1024):
        raise ValueError('Invalid record revision')


def _reply(status, data):
    text = json.dumps(data, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':'))
    if len(text.encode('utf-8')) > MAX_ENVELOPE_BYTES:
        raise ValueError('Record response exceeds bounds')
    return {'status': status, 'content_type': 'application/json', 'body': text}


def _request(request, method):
    if (type(request) is not dict or
            set(request) != {'method', 'path', 'query', 'body'} or
            request['method'].upper() != method or
            type(request['query']) is not dict):
        raise ValueError('Invalid closed record request')


async def read_info_record(request):
    """GET logical name only; never expose asset/header/host path objects."""
    _request(request, 'GET')
    if set(request['query']) != {'name'} or request['body'] != '':
        raise ValueError('Record read accepts only name')
    name = _logical(request['query']['name'])
    record = await read_record(name)
    return _reply(200, {key: record[key] for key in
                        ('sha256', 'revision', 'metadata')})


async def compare_and_set_info_record(request):
    """Resolve once; bind the entire commit to that digest and its CAS key."""
    _request(request, 'POST')
    if request['query']:
        raise ValueError('Record commit accepts no query overrides')
    data = _parse(request['body'])
    if type(data) is not dict or set(data) != {'name', 'sha256', 'revision', 'metadata'}:
        raise ValueError('Invalid closed model record commit')
    name = _logical(data['name'])
    if type(data['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', data['sha256']):
        raise ValueError('Invalid record digest')
    _revision(data['revision'])
    if type(data['metadata']) is not dict:
        raise ValueError('Model metadata must be an object')
    _validate_tree(data['metadata'], MAX_RECORD_BYTES)
    document = {'format': FORMAT, 'sha256': data['sha256'], 'metadata': data['metadata']}
    encode_record(document)  # Include every envelope byte before asset/storage work.
    _, digest, key = await _identity(name)
    if digest != data['sha256']:
        return _reply(409, {'error': 'Selected model digest changed'})
    current = await read_document(key, 'model-edits')
    old = current['document']
    if old is not None:
        validate_record(old, digest)
    # No TTL override or temporary VALUE fallback.
    # No retries, resets or commit to a re-resolved successor asset.
    result = await compare_and_set_document(key, 'model-edits', data['revision'], document)
    return _reply(200, {'updated': result['updated'], 'revision': result['revision']})
