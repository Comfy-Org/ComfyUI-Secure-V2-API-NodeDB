"""Two editable projections of a whole durable manager-preferences record.

The trusted storage owner selects account and pack. No temporary VALUE, TTL,
path, credentials, migration, corruption reset, hidden retry or field sharding.
Other authored settings stay in the same record and are never sent to this UI.
"""
from __future__ import annotations

import json
from comfy_api.latest import sdk

from .documents import _validate_tree, _preflight_json_depth
from .info_note_routes import _pairs, _constant, _request, _parse, _revision, _reply

KEY = 'manager.preferences'
FORMAT = 'loramanager.preferences.v1'
MAX_BYTES = 1024 * 1024
DEFAULTS = {'show_only_sfw': False, 'model_name_display': 'model_name'}


def validate(document):
    if (type(document) is not dict or set(document) != {'format', 'preferences'}
            or document['format'] != FORMAT or type(document['preferences']) is not dict):
        raise ValueError('Corrupt manager preferences record')
    _validate_tree(document, MAX_BYTES)
    values = document['preferences']
    # The editable projection admits these source-valid values. A malformed
    # present field is refused, not silently defaulted, clamped or overwritten.
    if 'show_only_sfw' in values and type(values['show_only_sfw']) is not bool:
        raise ValueError('Invalid stored show_only_sfw preference')
    if ('model_name_display' in values and
            (type(values['model_name_display']) is not str or
             values['model_name_display'] not in ('model_name', 'file_name'))):
        raise ValueError('Invalid stored model_name_display preference')


def encode(document):
    validate(document)
    parts = []
    size = 0
    for part in json.JSONEncoder(ensure_ascii=False, allow_nan=False,
                                separators=(',', ':')).iterencode(document):
        size += len(part.encode('utf-8'))
        if size > MAX_BYTES:
            raise ValueError('Encoded manager preferences exceed durable bounds')
        parts.append(part)
    return ''.join(parts)


def decode(text):
    if (type(text) is not str or len(text) > MAX_BYTES or
            len(text.encode('utf-8')) > MAX_BYTES):
        raise ValueError('Stored manager preferences exceed durable bounds')
    _preflight_json_depth(text)
    document = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
    validate(document)
    return document


def project(document):
    if document is not None:
        validate(document)
    values = {} if document is None else document['preferences']
    return {key: values[key] if key in values else default for key, default in DEFAULTS.items()}


async def read_preferences():
    current = await sdk.ctx().storage.read(KEY)
    document = None if current['value'] is None else decode(current['value'])
    return {'revision': current['revision'], 'document': document,
            'preferences': project(document)}


async def compare_and_set_preferences(revision, changes):
    _revision(revision)
    if type(changes) is not dict or not changes or not set(changes) <= set(DEFAULTS):
        raise ValueError('Only the two preview preference fields may be edited')
    # Validate edit before reading storage, then read the current whole record.
    validate({'format': FORMAT, 'preferences': changes})
    current = await read_preferences()  # Corrupt data is never repaired by a write.
    if current['revision'] != revision:
        return {'updated': False, 'revision': current['revision']}
    values = {} if current['document'] is None else current['document']['preferences'].copy()
    values.update(changes)
    text = encode({'format': FORMAT, 'preferences': values})
    result = await sdk.ctx().storage.compare_and_set(KEY, revision, text)
    return {'updated': result['updated'], 'revision': result['revision']}


async def read_preview_preferences(request):
    _request(request, 'GET')
    if request['query'] or request['body'] != '':
        raise ValueError('Preferences read accepts no identity or query overrides')
    current = await read_preferences()
    return _reply(200, {'revision': current['revision'], 'preferences': current['preferences']})


async def compare_and_set_preview_preferences(request):
    _request(request, 'POST')
    if request['query']:
        raise ValueError('Preferences commit accepts no query overrides')
    data = _parse(request['body'])
    if type(data) is not dict or set(data) != {'revision', 'changes'}:
        raise ValueError('Invalid closed preferences commit')
    result = await compare_and_set_preferences(data['revision'], data['changes'])
    return _reply(200, result)
