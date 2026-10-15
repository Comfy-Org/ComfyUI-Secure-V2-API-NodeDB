"""Save LoRA resources from the real pack-owned ordered cache.

The default LoRA path retains cache None, stale rows and refresh semantics.
Explicit imported-native-cache compatibility preserves the earlier reader;
it is never a silent fallback for an absent current pack cache. Checkpoint
resources retain their prior explicit import/registered-record path.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from comfy_api.latest import sdk

from ..secure_algorithms.bounds import bounded_json
from ..secure_algorithms.image_save_parameters import image_parameters
from .managed_library import _logical
from .durable_model_records import decode_record, validate_record
from .image_save_cache import imported_save_resources
from .catalogue_cache import read_cache


def _requests(metadata):
    bounded_json(metadata)
    if type(metadata) is not dict:
        raise ValueError('Save metadata must be an object')
    checkpoint = metadata.get('checkpoint') or ''
    loras = metadata.get('loras') or ''
    if type(checkpoint) is not str or type(loras) is not str:
        raise ValueError('Save resource names must be text')
    if loras.count('<lora:') > 64:
        raise ValueError('Save resource requests exceed bounds')
    names = [name for name, _ in re.findall(r'<lora:([^:]+):([^>]+)>', loras)]
    for name in [checkpoint, *names]:
        if len(name.encode('utf-8')) > 4096:
            raise ValueError('Save resource label exceeds bounds')
    return {'checkpoint_scanner': [checkpoint] if checkpoint else [],
            'lora_scanner': list(dict.fromkeys(names))}


def _stem(name):
    basename = name.rsplit('/', 1)[-1]
    return basename.rsplit('.', 1)[0] if '.' in basename else basename


def _native_cache_civitai(civitai):
    """Return a lightweight civitai payload containing only frequently used keys."""
    if not isinstance(civitai, Mapping) or not civitai:
        return None
    slim = {}
    for key in ('id', 'modelId', 'name'):
        value = civitai.get(key)
        if value not in (None, '', []):
            slim[key] = value
    creator = civitai.get('creator')
    if isinstance(creator, Mapping):
        username = creator.get('username')
        if username:
            slim['creator'] = {'username': username}
    trained_words = civitai.get('trainedWords')
    if trained_words:
        slim['trainedWords'] = list(trained_words) if isinstance(trained_words, list) else trained_words
    civitai_model = civitai.get('model')
    if isinstance(civitai_model, Mapping):
        model_type_value = civitai_model.get('type')
        if model_type_value not in (None, '', []):
            slim['model'] = {'type': model_type_value}
    return slim or None


async def pack_cache_lora_resources(labels):
    current = await read_cache()
    rows = [] if current['cache'] is None else current['cache']['rows']
    table = {}
    for label in labels:
        candidates = (label, label.rsplit('/', 1)[-1], _stem(label))
        row = next((row for row in rows if row['metadata']['file_name'] in candidates), None)
        if row is None:
            continue
        authored = row['metadata']
        civitai = _native_cache_civitai(authored.get('civitai')) or {}
        base_model = authored.get('base_model') or ''
        bounded_json([civitai, base_model])
        if type(civitai) is not dict or type(base_model) is not str:
            raise ValueError('Save pack cache projection has invalid fields')
        # Native Save resolves stored cache identity without a fresh file read.
        # Preserve cache order and stale rows until a real cache refresh.
        table[label] = {'sha256': row['sha256'], 'civitai': civitai, 'base_model': base_model}
    return table


async def read_save_resources(metadata, *, lora_source='pack-cache'):
    """Resolve only registered names; source labels never become host paths."""
    if lora_source not in ('pack-cache', 'imported-native-cache'):
        raise ValueError('Invalid Save LoRA metadata source')
    requests = _requests(metadata)
    result = {}
    for scanner, folder in (('checkpoint_scanner', 'checkpoints'), ('lora_scanner', 'loras')):
        labels = requests[scanner]
        if not labels:
            continue
        if folder == 'loras' and lora_source == 'pack-cache':
            result[scanner] = await pack_cache_lora_resources(labels)
            # The original's scanner indexes every library LoRA (sidecar or not) at server start;
            # this pack cache fills only on an explicit refresh and cannot index sidecar-less files.
            # Labels it lacks resolve as checkpoints do below: catalogue name -> digest -> record.
            labels = [label for label in labels if label not in result[scanner]]
            if not labels:
                continue
        else:
            imported = await imported_save_resources(folder, labels)
            if imported is not None:
                result[scanner] = imported
                continue
        catalogue = await sdk.ctx().assets.list(folder)
        if type(catalogue) is not list or len(catalogue) > 2048:
            raise ValueError('Save resource catalogue exceeds bounds')
        for name in catalogue:
            _logical(name)
        if len(set(catalogue)) != len(catalogue):
            raise ValueError('Duplicate save resource catalogue identity')
        table = result.setdefault(scanner, {})
        for label in labels:
            # The pinned scanner first matches file_name against the original,
            # basename and stem labels. Here filenames come from a closed
            # catalogue, not arbitrary scanner objects or supplied host paths.
            candidates = (label, label.rsplit('/', 1)[-1], _stem(label))
            logical = next((name for name in catalogue if _stem(name) in candidates), None)
            if logical is None:
                continue
            try:
                asset = await sdk.ctx().assets.resolve(folder, logical)
                digest = await sdk.ctx().assets.digest(asset)
            except FileNotFoundError:
                continue
            if type(digest) is not str or not re.fullmatch('[0-9a-f]{64}', digest):
                raise ValueError('Save resource digest is not SHA-256')
            # Save only reads the owned encoded record. Its formatter has no
            # revision/CAS input; use the existing public value getter rather
            # than requiring an unavailable editing interface.
            encoded = await sdk.ctx().storage.get('model.digest.' + digest)
            record = None if encoded is None else decode_record(encoded)
            if record is not None:
                validate_record(record, digest)
                authored = record['metadata']
            else:
                authored = {}
            civitai = authored.get('civitai') or {}
            base_model = authored.get('base_model') or ''
            bounded_json([civitai, base_model])
            if type(civitai) is not dict or type(base_model) is not str:
                raise ValueError('Save record projection has invalid fields')
            if await sdk.ctx().assets.digest(asset) != digest:
                raise ValueError('Save asset identity changed during record read')
            table[label] = {'sha256': digest, 'civitai': civitai, 'base_model': base_model}
    return result


async def format_managed_parameters(metadata, *, add_loras_to_prompt=False, lora_source='pack-cache'):
    resources = await read_save_resources(metadata, lora_source=lora_source)
    return image_parameters(metadata, resources, add_loras_to_prompt=add_loras_to_prompt), resources
