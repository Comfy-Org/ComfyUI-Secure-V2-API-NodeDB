"""Explicit ordered native Save cache snapshots over public durable storage.

Exports come from the operator's native scanner. Business paths remain opaque
metadata; they never authorize filesystem access. Each row retains its own
authored metadata even when multiple native files have the same content hash.
"""
import json

from comfy_api.latest import sdk

from .documents import _validate_tree, _preflight_json_depth
from .durable_model_records import encode_record
from .managed_library import _logical

FORMAT = 'loramanager.native-save-cache.v1'
COMMIT = '2dcaf6a30e50e6eace230c8311f25890a23473f0'
MAX_BYTES = 1024 * 1024


def _key(folder):
    if folder not in ('loras', 'checkpoints'):
        raise ValueError('Invalid Save cache folder')
    return 'manager.native-save-cache.' + folder


def validate_snapshot(document, folder):
    _key(folder)
    if (type(document) is not dict
            or set(document) != {'format', 'original_commit', 'folder', 'roots', 'rows'}
            or document['format'] != FORMAT or document['original_commit'] != COMMIT
            or document['folder'] != folder or type(document['roots']) is not list
            or any(type(root) is not str for root in document['roots'])
            or type(document['rows']) is not list or len(document['rows']) > 2048):
        raise ValueError('Invalid imported native Save cache')
    _validate_tree(document, MAX_BYTES)
    paths = set()
    for row in document['rows']:
        if (type(row) is not dict or set(row) != {'logical_name', 'record'}):
            raise ValueError('Invalid native Save cache row')
        _logical(row['logical_name'])
        record = row['record']
        # Reuse the complete authored-record validation and byte limits.
        encode_record(record)
        metadata = record['metadata']
        if (type(metadata.get('file_name')) is not str
                or type(metadata.get('file_path')) is not str
                or metadata['file_path'] in paths
                or metadata.get('sha256') != record['sha256']
                or type(metadata.get('civitai') or {}) is not dict
                or type(metadata.get('base_model') or '') is not str):
            raise ValueError('Invalid native Save cache row metadata')
        paths.add(metadata['file_path'])
    return document


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate native Save cache field')
        result[key] = value
    return result


def _constant(value):
    raise ValueError('Nonfinite native Save cache field')


async def _verify_asset(folder, row):
    asset = await sdk.ctx().assets.resolve(folder, row['logical_name'])
    if await sdk.ctx().assets.digest(asset) != row['record']['sha256']:
        raise ValueError('Native Save cache asset digest mismatch')
    return row['record']['metadata']


async def import_native_save_cache(document):
    """Persist an explicit complete export; no sidecar discovery or CAS claim."""
    folder = document.get('folder') if type(document) is dict else None
    validate_snapshot(document, folder)
    raw = json.dumps(document, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    if len(raw.encode('utf-8')) > MAX_BYTES:
        raise ValueError('Imported native Save cache exceeds byte bounds')
    # Verify every bound asset before a single whole-snapshot publication.
    for row in document['rows']:
        await _verify_asset(folder, row)
    await sdk.ctx().storage.set(_key(folder), raw)
    return await sdk.ctx().storage.get(_key(folder)) == raw


async def read_native_save_cache(folder):
    raw = await sdk.ctx().storage.get(_key(folder))
    if raw is None:
        return None
    if type(raw) is not str or len(raw) > MAX_BYTES or len(raw.encode('utf-8')) > MAX_BYTES:
        raise ValueError('Imported native Save cache exceeds byte bounds')
    _preflight_json_depth(raw)
    document = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
    return validate_snapshot(document, folder)


async def imported_save_resources(folder, labels):
    snapshot = await read_native_save_cache(folder)
    if snapshot is None:
        return None
    table = {}
    for label in labels:
        basename = label.rsplit('/', 1)[-1]
        stem = basename.rsplit('.', 1)[0] if '.' in basename else basename
        candidates = (label, basename, stem)
        row = next((row for row in snapshot['rows']
                    if row['record']['metadata']['file_name'] in candidates), None)
        if row is None:
            continue
        metadata = await _verify_asset(folder, row)
        table[label] = {'sha256': row['record']['sha256'],
                        'civitai': metadata.get('civitai') or {},
                        'base_model': metadata.get('base_model') or ''}
    return table
