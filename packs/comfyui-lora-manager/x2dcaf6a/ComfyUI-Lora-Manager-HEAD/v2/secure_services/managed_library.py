"""Managed catalogue + owned editable records; no scanner/path/HTTP authority.

Actual cloud authentication/backing and legacy sidecar import remain host-owned
integration boundaries. A missing owned record is a new-record case, NOT an
assertion that legacy editable metadata can be replaced by weight headers.
"""
from __future__ import annotations

import json
import re

from comfy_api.latest import sdk

from ..secure_algorithms.lora_requests import requested_loras

FORMAT = 'loramanager.asset-record.v1'
SETTINGS_KEY = 'library.settings'
EXTENSIONS = ('.safetensors', '.ckpt', '.pt', '.bin')


def _logical(name):
    if (type(name) is not str or not name or len(name.encode('utf-8')) > 4096
            or name.startswith(('/', '\\')) or ':' in name or '\\' in name
            or any(part in ('', '.', '..') for part in name.split('/'))):
        raise ValueError('LoRA identity must be a confined logical catalogue name')
    return name


def _stem(name):
    for extension in EXTENSIONS:
        if name.lower().endswith(extension):
            return name[:-len(extension)]
    return name


def _match(name, catalogue):
    """Pinned name/folder and basename fallback order, over admitted names only."""
    name = _stem(_logical(name.replace('\\', '/')))
    basename = name.rsplit('/', 1)[-1]
    fallback = None
    for candidate in catalogue:
        relative = _stem(candidate)
        file_name = relative.rsplit('/', 1)[-1]
        folder = relative.rsplit('/', 1)[0] if '/' in relative else ''
        if name == file_name or name == relative:
            return candidate
        if '/' in name and file_name == basename:
            if folder and name.startswith(folder + '/'):
                fallback = candidate
            elif fallback is None:
                fallback = candidate
    if fallback is None:
        raise ValueError(f'LoRA is not present in the managed catalogue: {name}')
    return fallback


async def _identity(asset_name):
    asset_name = _logical(asset_name)
    asset = await sdk.ctx().assets.resolve('loras', asset_name)
    digest = await sdk.ctx().assets.digest(asset)
    if type(digest) is not str or not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('Managed asset digest is not SHA-256')
    return asset, digest, 'model.digest.' + digest


async def read_record(asset_name):
    # Lazy imports preserve the adapter's shared FORMAT/_identity dependency.
    # Only authored model records move to durable text; recipes/wildcards do not.
    from .durable_model_records import read_document, validate_record
    asset, digest, key = await _identity(asset_name)
    result = await read_document(key, 'model-edits')
    record = result['document']
    if record is not None:
        validate_record(record, digest)
    # Headers remain distinct from authored provider/library metadata.
    header = await sdk.ctx().assets.metadata(asset)
    return {'asset': asset, 'sha256': digest, 'revision': result['revision'],
            'metadata': None if record is None else record['metadata'], 'header': header}


async def read_loader_record(asset_name):
    """Read the loader's authored projection without requiring edit-route CAS.

    The storage owner must import the native record. No weight header replaces
    authored metadata, and no revision is fabricated for this read-only path.
    """
    from .durable_model_records import decode_record, validate_record
    asset, digest, key = await _identity(asset_name)
    value = await sdk.ctx().storage.get(key)
    document = None if value is None else decode_record(value)
    if document is not None:
        validate_record(document, digest)
    return {'asset': asset, 'sha256': digest,
            'metadata': None if document is None else document['metadata']}


async def save_record(asset_name, metadata, revision, *, ttl_seconds=None):
    from .durable_model_records import (encode_record, validate_record, read_document,
        compare_and_set_document)
    if ttl_seconds is not None:
        raise ValueError('Durable authored model records do not accept TTL overrides')
    if type(metadata) is not dict:
        raise ValueError('Model metadata must be an object')
    # Bound the complete encoded record before catalogue/storage operations;
    # a fixed-width placeholder accounts for the digest without resolving twice.
    document = {'format': FORMAT, 'sha256': '0' * 64, 'metadata': metadata}
    encode_record(document)
    _, digest, key = await _identity(asset_name)
    document['sha256'] = digest
    current = await read_document(key, 'model-edits')
    if current['document'] is not None:
        validate_record(current['document'], digest)
    return await compare_and_set_document(key, 'model-edits', revision,
        document)


async def _syntax_format():
    # Same whole durable manager-preferences document used by preview consumers.
    # Import lazily: preview route helpers reference this module's identities.
    from .preview_preferences import KEY, decode
    value = await sdk.ctx().storage.get(KEY)
    document = None if value is None else decode(value)
    settings = {} if document is None else document['preferences']
    # Retain native legacy-only branch semantics: present non-legacy values are
    # not coerced to a menu option or silently defaulted. Only an absent key
    # uses legacy. Permission/store/corruption errors propagate, never reset.
    return settings.get('lora_syntax_format', 'legacy')


def _requested(loras, lora_stack, lora_syntax, syntax_format, *, convert_stack_strengths=True):
    return requested_loras(loras, lora_stack, lora_syntax, syntax_format,
        convert_stack_strengths=convert_stack_strengths)


async def load_managed_loras(model, clip, *, loras=None, lora_stack=None, lora_syntax=''):
    requested = _requested(loras, lora_stack, lora_syntax, await _syntax_format())
    if not requested:
        return model, clip, '', ''
    catalogue = await sdk.ctx().assets.list('loras')
    for name in catalogue:
        _logical(name)
    entries = []
    # Resolve/read the entire chain before the first model operation.
    for display, name, strength, clip_strength in requested:
        logical = _match(name, catalogue)
        record = await read_loader_record(logical)
        metadata = record['metadata']
        civitai = metadata.get('civitai') or {} if metadata is not None else {}
        words = civitai.get('trainedWords', [])
        entries.append((display, record['asset'], strength, clip_strength, words))
    loaded, triggers = [], []
    for display, asset, strength, clip_strength, words in entries:
        # Public signature verified in the actual host and guest contract probe.
        # Keep requested display strengths when there is no CLIP to apply them.
        model, clip = await model.apply_lora(asset, clip, strength,
            clip_strength if clip is not None else 0.,
            skip_zero=False, allow_extended_strengths=True)
        triggers.extend(words)
        loaded.append(f'<lora:{display}:{strength}:{clip_strength}>' if abs(strength - clip_strength) > .001
                      else f'<lora:{display}:{strength}>')
    return model, clip, ',, '.join(triggers), ' '.join(loaded)
