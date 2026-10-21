"""Metric3D raw checkpoint contract; stdlib selection before new imports."""
from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re

PIN = '0cd290477128d42cdc3e76a826a402d866e8c684'
REPO = 'JUGGHM/Metric3D'
BACKBONES = ('vit-small', 'vit-large', 'vit-giant2')
MAX_BYTES = 512 * 1024 * 1024


def digest(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def validate_selection(item):
    if item.get('approved') is not True:
        raise RuntimeError('Metric3D raw checkpoint metadata/config/vendor/device selection pending')
    if item.get('format') != 'amy-metric3d-managed-selection/1' or item.get('source_pin') != PIN:
        raise RuntimeError('Metric3D exact original source is unselected')
    for key in ('runtime_abi_evidence_sha256', 'preimport_environment_authority_sha256',
                'config_evaluation_authority_sha256', 'exclusive_state_cache_lifetime_sha256',
                'device_correspondence_sha256', 'current_invocation_admission_sha256',
                'restricted_vendor_source_evidence_sha256', 'fixed_crop_workspace_admission_sha256', 'internal_device_policy_sha256'):
        if not digest(item.get(key)):
            raise RuntimeError('Metric3D actual vendor/config/environment/device/exclusive lifetime evidence missing')
    if type(item.get('device')) is not str or re.fullmatch(r'cpu|mps|cuda(?::[0-9]+)?', item['device']) is None:
        raise RuntimeError('Metric3D actual native to-device is unselected')
    r = item.get('resource', {})
    if r.get('approved') is not True or r.get('raw_container_approved') is not True:
        raise RuntimeError('Metric3D complete raw metadata/state/storage contract remains held')
    if (r.get('source_repo'), r.get('source_filename')) != (REPO, 'metric_depth_' + item['backbone'].replace('-', '_') + '_800k.pth'):
        raise RuntimeError('Metric3D exact source resource is unselected')
    for key in ('sha256', 'raw_container_evidence_sha256', 'saved_storage_correspondence_sha256'):
        if not digest(r.get(key)):
            raise RuntimeError('Metric3D actual immutable raw checkpoint evidence is missing')
    if type(r.get('revision')) is not str or re.fullmatch('[0-9a-f]{40}', r['revision']) is None:
        raise RuntimeError('Metric3D publisher revision is unselected')
    if type(r.get('bytes')) is not int or not 0 < r['bytes'] <= MAX_BYTES:
        raise RuntimeError('Metric3D bounded archive count is unselected')
    for key in ('folder', 'catalogue_name'):
        if type(r.get(key)) is not str or not r[key]:
            raise RuntimeError('Metric3D sealed catalogue resource is unselected')
    keys = r.get('raw_top_level_keys')
    if type(keys) is not list or 'model_state_dict' not in keys or any(type(k) is not str for k in keys) or len(set(keys)) != len(keys):
        raise RuntimeError('Metric3D actual full raw keys/order/metadata are unselected')
    diagnostic = r.get('native_model_path_discriminator')
    if type(diagnostic) is not str or not digest(r.get('native_path_regex_correspondence_sha256')):
        raise RuntimeError('Metric3D actual acquisition-path regex correspondence pending')
    if re.findall(r'metric_depth_vit_(\w+)_', diagnostic)[:1] != [item['backbone'].split('vit-', 1)[1]]:
        raise RuntimeError('Metric3D original path regex does not select this actual backbone')
    if not digest(r.get('primitive_contract_sha256')) or r.get('state_mapping_kind') not in ('dict', 'OrderedDict'):
        raise RuntimeError('Metric3D exact primitive metadata/container types are unselected')
    if type(r.get('state_keys')) is not list or not r['state_keys'] or any(type(k) is not str for k in r['state_keys']) or len(set(r['state_keys'])) != len(r['state_keys']):
        raise RuntimeError('Metric3D actual ordered state keys are unselected')
    if type(r.get('tensor_bytes')) is not int or not 0 < r['tensor_bytes'] <= MAX_BYTES:
        raise RuntimeError('Metric3D actual bounded state materialization is unselected')
    return r


def selected_checkpoint(backbone):
    item = json.loads(Path(__file__).with_name('asset-selection.json').read_text())
    if item.get('approved') is not True:
        raise RuntimeError('Metric3D raw checkpoint/config/vendor/device/state-cache selection pending')
    if backbone not in BACKBONES:
        raise RuntimeError('Metric3D actual source backbone selection pending')
    item = dict(item, backbone=backbone, resource=item['resources'][backbone])
    validate_selection(item)
    closure = json.loads(Path(__file__).with_name('source-closure.json').read_text())
    for row in closure['records']:
        path = Path(__file__).parent / row['result']
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['result_sha256']:
            raise RuntimeError('Metric3D actual private config/network closure differs')
    # The real existing MMCV graph is inherited, not copied into Metric3D.
    parent = Path(__file__).parent.parent / '_uniformer'
    content = (parent / 'source-closure.json').read_bytes()
    if hashlib.sha256(content).hexdigest() != closure['reused_uniformer_closure_sha256']:
        raise RuntimeError('Metric3D reused actual private MMCV source census differs')
    for row in json.loads(content)['records']:
        if row['result'].startswith('custom_mmpkg/'):
            if hashlib.sha256((parent / row['result']).read_bytes()).hexdigest() != row['result_sha256']:
                raise RuntimeError('Metric3D reused actual private MMCV source differs')
    return item


@dataclass(frozen=True)
class SealedCheckpoint:
    payload: bytes
    selection: dict

    def __str__(self):
        return 'sealed:' + self.selection['resource']['catalogue_name']


async def selected_archive(item, repo, filename):
    r = validate_selection(item)
    if (repo, filename) != (r['source_repo'], r['source_filename']):
        raise RuntimeError('Metric3D constructor exact repo/filename differs')
    from comfy_api.latest import sdk
    assets = sdk.ctx().assets
    ref = await assets.resolve(r['folder'], r['catalogue_name'])
    if await assets.size(ref) != r['bytes'] or await assets.digest(ref, 'sha256') != r['sha256']:
        raise RuntimeError('Metric3D sealed checkpoint count/digest differs')
    from .._sealed_asset_read import read_sealed_asset
    payload = await read_sealed_asset(assets, ref, r['bytes'], r['sha256'])
    if type(payload) is not bytes or len(payload) != r['bytes'] or hashlib.sha256(payload).hexdigest() != r['sha256']:
        raise RuntimeError('Metric3D actual raw archive bytes differ')
    return SealedCheckpoint(payload, item)


def primitive(value, depth=0):
    # Preserve types, order and values in the proof; never normalize the
    # checkpoint object passed to native loaders/CLASSES/PALETTE assignments.
    if depth > 32:
        raise RuntimeError('Metric3D primitive metadata nesting exceeds bound')
    if value is None or type(value) in (bool, int, str):
        return [type(value).__name__, value]
    if type(value) is float and math.isfinite(value):
        return ['float', value]
    if type(value) in (list, tuple):
        return [type(value).__name__, [primitive(v, depth + 1) for v in value]]
    if type(value) in (dict, OrderedDict) and all(type(k) is str for k in value):
        result = [type(value).__name__, [[k, primitive(v, depth + 1)] for k, v in value.items()]]
        if hasattr(value, '_metadata'):
            result.append(['_metadata', primitive(value._metadata, depth + 1)])
        return result
    raise RuntimeError('Metric3D unsupported raw primitive metadata type; no coercion or safe-global extension')


def validate_raw(raw, item):
    import torch
    r = validate_selection(item)
    if type(raw) not in (dict, OrderedDict) or list(raw) != r['raw_top_level_keys']:
        raise RuntimeError('Metric3D complete raw checkpoint mapping/order differs')
    state = raw['model_state_dict']
    if type(state).__name__ != r['state_mapping_kind'] or type(state) not in (dict, OrderedDict) or list(state) != r['state_keys']:
        raise RuntimeError('Metric3D native state mapping kind/order differs')
    total = 0
    for value in state.values():
        if type(value) is not torch.Tensor or value.layout != torch.strided or value.device.type != 'cpu' or value.is_quantized or value.is_complex():
            raise RuntimeError('Metric3D restricted state requires genuine real dense CPU Tensor values')
        total += value.numel() * value.element_size()
    if total != r['tensor_bytes'] or total > MAX_BYTES:
        raise RuntimeError('Metric3D actual state materialization count differs')
    # Every non-state primitive, including metadata and state._metadata, must
    # match ACTUAL owning inspection. No CLASSES/PALETTE are guessed or rebuilt.
    proof = [type(raw).__name__, [[k, primitive(v)] for k, v in raw.items() if k != 'model_state_dict'],
             ['state_mapping_kind', type(state).__name__], ['state_keys', list(state)],
             ['state_metadata_present', hasattr(state, '_metadata')]]
    if hasattr(state, '_metadata'):
        proof.append(['state_metadata', primitive(state._metadata)])
    if hasattr(raw, '_metadata'):
        proof.append(['raw_metadata', primitive(raw._metadata)])
    encoded = json.dumps(proof, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    if len(encoded) > MAX_BYTES or hashlib.sha256(encoded).hexdigest() != r['primitive_contract_sha256']:
        raise RuntimeError('Metric3D actual complete primitive metadata/container proof differs')
    return raw


def load_raw_checkpoint(archive):
    if type(archive) is not SealedCheckpoint:
        raise RuntimeError('Metric3D checkpoint constructor requires exact sealed raw bytes')
    validate_selection(archive.selection)
    from io import BytesIO
    import torch
    # This is real retained Torch restricted decoding, not the SDK tensor-only
    # projection. No safe-global additions by this pack, unrestricted pickle or
    # fallback. torch and the ComfyUI host register their own safe globals, so
    # "none registered" never holds; instead the pinned per-checkpoint proof shows
    # this decode resolves only torch DEFAULT-allowlisted globals (consulted first).
    from .._restricted_globals import require_default_allowlisted
    require_default_allowlisted(archive.payload, archive.selection['resource'].get('pickle_globals'))
    raw = torch.load(BytesIO(archive.payload), map_location="cpu", weights_only=True)
    return validate_raw(raw, archive.selection)


def sealed_checkpoint_present(archive):
    if type(archive) is not SealedCheckpoint:
        raise RuntimeError('Metric3D requires approved sealed archive, never a host path')
    validate_selection(archive.selection)
    r = archive.selection['resource']
    if type(archive.payload) is not bytes or len(archive.payload) != r['bytes'] or hashlib.sha256(archive.payload).hexdigest() != r['sha256']:
        raise RuntimeError('Metric3D sealed archive is absent or changed')
    return True
