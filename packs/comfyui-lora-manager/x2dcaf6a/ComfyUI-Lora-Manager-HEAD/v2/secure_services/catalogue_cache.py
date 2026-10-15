"""Pack-owned durable cache over existing public asset and storage APIs.

Refresh is real bounded work, resumable across owning Guest calls. Cache state
is never imported from a native scanner. The admitted source profile reads
existing alongside metadata assets; centralized/provider sources are explicit
unsupported operations until a genuine generic metadata provider exists.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import PurePosixPath

from comfy_api.latest import sdk
from ..secure_algorithms.bounds import bounded_json
from .managed_library import _logical

KEY = 'library.pack-owned-cache.v1'
FORMAT = 'loramanager.pack-owned-cache.v1'
MAX_ROWS = 2048
MAX_BYTES = 1024 * 1024
SOURCE = 'alongside-metadata-assets'
_ABSENT = object()


class UnsupportedMetadataSource(ValueError):
    pass


def _source(source):
    if source != SOURCE:
        raise UnsupportedMetadataSource(
            'Pack cache metadata source is unsupported: centralized/provider '
            'authored metadata requires an implemented public catalogue metadata provider')


def _empty():
    # This is the actual absent pack cache, not a successful empty rebuild.
    return {'format': FORMAT, 'cache': None, 'initializing': False, 'pending': None}


def _encode(value):
    bounded_json(value)
    text = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    if len(text.encode('utf-8')) > MAX_BYTES:
        raise ValueError('Pack cache document exceeds byte bounds')
    return text


def _validate(value):
    bounded_json(value)
    if type(value) is not dict or set(value) != {'format', 'cache', 'initializing', 'pending'} or value['format'] != FORMAT:
        raise ValueError('Invalid pack cache document')
    if type(value['initializing']) is not bool:
        raise ValueError('Invalid pack cache initializing state')
    cache, pending = value['cache'], value['pending']
    if cache is not None:
        if type(cache) is not dict or set(cache) != {'rows'} or type(cache['rows']) is not list or len(cache['rows']) > MAX_ROWS:
            raise ValueError('Invalid pack cache rows')
        for row in cache['rows']:
            _validate_row(row)
    if value['initializing'] != (pending is not None):
        raise ValueError('Pack cache work/state mismatch')
    if pending is not None:
        if type(pending) is not dict or set(pending) != {'source', 'names', 'cursor', 'rows'}:
            raise ValueError('Invalid pending pack refresh')
        _source(pending['source'])
        _names(pending['names'])
        if type(pending['cursor']) is not int or not 0 <= pending['cursor'] <= len(pending['names']):
            raise ValueError('Invalid pack refresh cursor')
        if type(pending['rows']) is not list or len(pending['rows']) > pending['cursor']:
            raise ValueError('Invalid pending pack refresh rows')
        for row in pending['rows']:
            _validate_row(row)
    return value


def _names(names):
    if type(names) is not list or len(names) > MAX_ROWS or len(set(names)) != len(names):
        raise ValueError('Invalid pack cache catalogue')
    for name in names:
        _logical(name)
        if not name.lower().endswith('.safetensors'):
            raise ValueError('Pack LoRA cache only admits safetensors assets')
    return names


def _validate_row(row):
    if type(row) is not dict or set(row) != {'name', 'sha256', 'metadata'}:
        raise ValueError('Invalid pack cached row')
    _logical(row['name'])
    if type(row['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', row['sha256']):
        raise ValueError('Invalid pack cached asset digest')
    if type(row['metadata']) is not dict or 'file_path' in row['metadata']:
        raise ValueError('Invalid public cache metadata projection')


async def read_cache():
    text = await sdk.ctx().storage.get(KEY)
    if text is None:
        return _empty()
    if type(text) is not str or len(text.encode('utf-8')) > MAX_BYTES:
        raise ValueError('Invalid pack cache byte profile')
    return _validate(json.loads(text))


async def _store(value):
    _validate(value)
    await sdk.ctx().storage.set(KEY, _encode(value))
    return copy.deepcopy(value)


async def reset_cache():
    """Real library-change invalidation; no background worker is fabricated."""
    return await _store(_empty())


async def begin_refresh(*, source=SOURCE):
    """Acquire a real catalogue and persist its pending metadata scan."""
    _source(source)  # Never replace a valid cache on unsupported source.
    current = await read_cache()
    if current['initializing']:
        raise ValueError('Pack cache refresh is already in progress; continue or cancel it')
    names = _names(await sdk.ctx().assets.list('loras'))
    current['initializing'] = True
    current['pending'] = {'source': source, 'names': names, 'cursor': 0, 'rows': []}
    return await _store(current)


def alongside_metadata_name(name):
    """A confined asset name, not a native filesystem sidecar location.

    This mapping is valid only for the explicitly admitted alongside profile.
    Native oracle fixtures always write through the original sidecar helper.
    It cannot resolve centralized sidecar storage and never guesses that root.
    """
    return _logical(str(PurePosixPath(_logical(name)).with_suffix('.metadata.json')))


async def _read_json_asset(name):
    # Remote resolve errors cross the RPC boundary as wrapped exceptions.
    # Only the public existence result establishes an absent sidecar; errors
    # from existence/resolve/read remain errors, including deletion races.
    if (await sdk.ctx().assets.exists('loras', name)) is False:
        return _ABSENT
    ref = await sdk.ctx().assets.resolve('loras', name)
    if await sdk.ctx().assets.size(ref) > MAX_BYTES:
        raise ValueError('Alongside metadata exceeds byte bounds')
    # read_range enforces the finite bound even if the asset grows after size.
    content = await sdk.ctx().assets.read_range(ref, 0, MAX_BYTES + 1)
    if not isinstance(content, bytes):
        raise TypeError('Public metadata read_range must return bytes')
    if len(content) > MAX_BYTES:
        raise ValueError('Alongside metadata exceeds byte bounds')
    value = json.loads(content.decode('utf-8'))
    bounded_json(value)
    return value


def _project_metadata(metadata, name):
    # Native load_metadata constructs LoraMetadata, then the cache normalizes
    # names and selected fields. Preserve row-specific authored values.
    required = {'file_name', 'model_name', 'file_path', 'size', 'modified', 'sha256',
                'base_model', 'preview_url'}
    if type(metadata) is not dict or not required.issubset(metadata):
        return None  # Native skips an existing unparseable metadata sidecar.
    if metadata.get('exclude', False):
        return None
    result = {key: copy.deepcopy(metadata[key]) for key in (
        'model_name', 'base_model', 'civitai', 'tags', 'usage_tips', 'favorite',
        'preview_nsfw_level', 'allowNoCredit', 'allowCommercialUse',
        'allowDerivatives', 'allowDifferentLicense') if key in metadata}
    model_name = result.get('model_name')
    result['model_name'] = model_name if isinstance(model_name, str) else ('' if model_name is None else str(model_name))
    path = PurePosixPath(name)
    result['file_name'] = path.stem
    result['folder'] = '' if str(path.parent) == '.' else str(path.parent)
    if result.get('civitai') is None:
        result['civitai'] = {}
    if result.get('tags') is None:
        result['tags'] = []
    bounded_json(result)
    return result


async def _scan_row(name):
    try:
        asset = await sdk.ctx().assets.resolve('loras', name)
        digest = await sdk.ctx().assets.digest(asset)
    except FileNotFoundError:
        return None  # Actual asset deletion between catalogue and scan.
    if type(digest) is not str or not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('Asset identity must be SHA-256')
    try:
        metadata = await _read_json_asset(alongside_metadata_name(name))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None  # Actual native corrupt-sidecar skip, not empty metadata.
    if metadata is _ABSENT:
        raise UnsupportedMetadataSource(
            'No alongside authored metadata asset: native header/default and '
            '.civitai.info migration are not implemented by this cache profile')
    if type(metadata) is dict and not metadata.get('civitai'):
        legacy_name = _logical(str(PurePosixPath(name).with_suffix('.civitai.info')))
        if await sdk.ctx().assets.exists('loras', legacy_name):
            raise UnsupportedMetadataSource(
                'Native read-only .civitai.info migration/restore is not implemented by this cache profile')
    projected = _project_metadata(metadata, name)
    if projected is None:
        return None
    return {'name': name, 'sha256': digest, 'metadata': projected}


async def continue_refresh(*, batch_size=16):
    if type(batch_size) is not int or not 1 <= batch_size <= 32:
        raise ValueError('Pack cache batch size must be between 1 and 32')
    current = await read_cache()
    pending = current['pending']
    if pending is None:
        raise ValueError('No pack cache refresh is in progress')
    try:
        stop = min(pending['cursor'] + batch_size, len(pending['names']))
        while pending['cursor'] < stop:
            name = pending['names'][pending['cursor']]
            row = await _scan_row(name)
            if row is not None:
                pending['rows'].append(row)
            pending['cursor'] += 1
            _encode(current)  # Bound retained rows during actual work.
        if pending['cursor'] == len(pending['names']):
            current['cache'] = {'rows': pending['rows']}
            current['initializing'] = False
            current['pending'] = None
        return await _store(current)
    except Exception:
        # Failed work is not published as a successful empty rebuild.
        # Keep the real previous cache, clear the genuine failed work state,
        # and preserve the original permission/backend/unsupported error.
        current['initializing'] = False
        current['pending'] = None
        await _store(current)
        raise


async def cancel_refresh():
    current = await read_cache()
    current['initializing'] = False
    current['pending'] = None
    return await _store(current)


async def refresh_cache(*, source=SOURCE):
    current = await begin_refresh(source=source)
    while current['initializing']:
        current = await continue_refresh()
    return current


async def missing_loras(names):
    """Native unknown/initializing bypass over actual pack-owned cache state."""
    current = await read_cache()
    if current['cache'] is None or current['initializing']:
        return []
    from .hooks import _queue_match
    available = [row['name'] for row in current['cache']['rows']]
    missing = []
    for name in names:
        logical = _queue_match(name, available)
        if logical is None:
            missing.append(name)
            continue
        # Native queue validation checks current file liveness even while its
        # completed cache is stale. Only real False means missing; permission
        # and backend errors propagate across the public SDK boundary.
        if (await sdk.ctx().assets.exists('loras', logical)) is False:
            missing.append(name)
    return missing


async def validate_stacker_entries(loras):
    if not loras:
        return True
    from .hooks import get_loras_list, apply_lora_syntax_format
    from .managed_library import _syntax_format
    names = []
    for row in get_loras_list({'loras': loras}):
        if isinstance(row, dict) and row.get('active', False):
            name = apply_lora_syntax_format(str(row.get('name') or ''), await _syntax_format())
            if name:
                names.append(name)
    missing = await missing_loras(names)
    return 'Missing LoRA(s) in local library: ' + ', '.join(missing) if missing else True


async def cached_metadata(name):
    current = await read_cache()
    if current['cache'] is None:
        return None
    from .managed_library import _match
    rows = current['cache']['rows']
    try:
        logical = _match(name, [row['name'] for row in rows])
    except ValueError:
        return None
    return copy.deepcopy(next(row['metadata'] for row in rows if row['name'] == logical))
