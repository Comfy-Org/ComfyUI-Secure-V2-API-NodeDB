"""UniFormer raw checkpoint contract; stdlib selection before new imports."""
from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re

PIN = '0cd290477128d42cdc3e76a826a402d866e8c684'
REPO = 'lllyasviel/Annotators'
FILENAME = 'upernet_global_small.pth'
MAX_BYTES = 512 * 1024 * 1024


def digest(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def validate_selection(item):
    if item.get('approved') is not True:
        raise RuntimeError('UniFormer raw checkpoint metadata/config/vendor/device selection pending')
    if item.get('format') != 'amy-uniformer-managed-selection/1' or item.get('source_pin') != PIN:
        raise RuntimeError('UniFormer exact original source is unselected')
    for key in ('runtime_abi_evidence_sha256', 'preimport_environment_authority_sha256',
                'config_evaluation_authority_sha256', 'exclusive_global_callback_lifetime_sha256',
                'device_correspondence_sha256', 'current_invocation_admission_sha256',
                'restricted_vendor_source_evidence_sha256'):
        if not digest(item.get(key)):
            raise RuntimeError('UniFormer actual vendor/config/environment/device/exclusive lifetime evidence missing')
    if type(item.get('device')) is not str or re.fullmatch(r'cpu|mps|cuda(?::[0-9]+)?', item['device']) is None:
        raise RuntimeError('UniFormer actual native to-device is unselected')
    # L4: the restricted-globals proof uses private torch APIs (get_globals_in_pkl and the default allowlist), so the
    # selection pins the torch build it was inspected on (compared in require_selected_torch).
    if type(item.get('torch_runtime_version')) is not str or not item['torch_runtime_version']:
        raise RuntimeError('UniFormer restricted decode torch runtime version is unselected')
    r = item.get('resource', {})
    if r.get('approved') is not True or r.get('raw_container_approved') is not True:
        raise RuntimeError('UniFormer complete raw metadata/state/storage contract remains held')
    if (r.get('source_repo'), r.get('source_filename')) != (REPO, FILENAME):
        raise RuntimeError('UniFormer exact source resource is unselected')
    for key in ('sha256', 'raw_container_evidence_sha256', 'saved_storage_correspondence_sha256'):
        if not digest(r.get(key)):
            raise RuntimeError('UniFormer actual immutable raw checkpoint evidence is missing')
    if type(r.get('revision')) is not str or re.fullmatch('[0-9a-f]{40}', r['revision']) is None:
        raise RuntimeError('UniFormer publisher revision is unselected')
    if type(r.get('bytes')) is not int or not 0 < r['bytes'] <= MAX_BYTES:
        raise RuntimeError('UniFormer bounded archive count is unselected')
    for key in ('folder', 'catalogue_name'):
        if type(r.get(key)) is not str or not r[key]:
            raise RuntimeError('UniFormer sealed catalogue resource is unselected')
    if r.get('native_saved_storage_all_cpu') is not True:
        raise RuntimeError('UniFormer second no-map_location saved-storage correspondence is held')
    keys = r.get('raw_top_level_keys')
    if type(keys) is not list or 'state_dict' not in keys or 'meta' not in keys or any(type(k) is not str for k in keys) or len(set(keys)) != len(keys):
        raise RuntimeError('UniFormer actual full raw keys/order/metadata are unselected')
    if not digest(r.get('primitive_contract_sha256')) or r.get('state_mapping_kind') not in ('dict', 'OrderedDict'):
        raise RuntimeError('UniFormer exact primitive metadata/container types are unselected')
    if type(r.get('state_keys')) is not list or not r['state_keys'] or any(type(k) is not str for k in r['state_keys']) or len(set(r['state_keys'])) != len(r['state_keys']):
        raise RuntimeError('UniFormer actual ordered state keys are unselected')
    if type(r.get('tensor_bytes')) is not int or not 0 < r['tensor_bytes'] <= MAX_BYTES:
        raise RuntimeError('UniFormer actual bounded state materialization is unselected')
    # M1: the per-checkpoint restricted-globals pin is checked here, before any vendor import, config evaluation or
    # archive read: the exact sorted global list from the restricted inspection.
    pinned = r.get('pickle_globals')
    if type(pinned) is not list or not pinned or any(type(g) is not str or not g for g in pinned) or pinned != sorted(set(pinned)):
        raise RuntimeError('UniFormer restricted decode pinned pickle globals are unselected')
    return r


def require_selected_torch(item):
    # L4: the restricted-globals proof relies on private torch APIs, so the running torch build must be the selected one.
    # It is compared before the sealed read (the port r2 review's Low-3) and again at decode.
    import torch
    if torch.__version__ != item['torch_runtime_version']:
        raise RuntimeError('UniFormer restricted decode torch runtime differs from the selected version')


def selected_checkpoint():
    item = json.loads(Path(__file__).with_name('asset-selection.json').read_text())
    validate_selection(item)
    # Source-owned hash census is not execution authority. Both the owner
    # evidence and exact new private configuration/dependency bytes are needed.
    source = json.loads(Path(__file__).with_name('source-closure.json').read_text())
    for row in source['records']:
        path = Path(__file__).parent / row['result']
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['result_sha256']:
            raise RuntimeError('UniFormer actual private source/config closure differs')
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
        raise RuntimeError('UniFormer constructor exact repo/filename differs')
    require_selected_torch(item)
    from comfy_api.latest import sdk
    assets = sdk.ctx().assets
    ref = await assets.resolve(r['folder'], r['catalogue_name'])
    if await assets.size(ref) != r['bytes'] or await assets.digest(ref, 'sha256') != r['sha256']:
        raise RuntimeError('UniFormer sealed checkpoint count/digest differs')
    from .._sealed_asset_read import read_sealed_asset
    payload = await read_sealed_asset(assets, ref, r['bytes'], r['sha256'])
    if type(payload) is not bytes or len(payload) != r['bytes'] or hashlib.sha256(payload).hexdigest() != r['sha256']:
        raise RuntimeError('UniFormer actual raw archive bytes differ')
    return SealedCheckpoint(payload, item)


def primitive(value, depth=0):
    # Preserve types, order and values in the proof; never normalize the
    # checkpoint object passed to native loaders/CLASSES/PALETTE assignments.
    if depth > 32:
        raise RuntimeError('UniFormer primitive metadata nesting exceeds bound')
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
    raise RuntimeError('UniFormer unsupported raw primitive metadata type; no coercion or safe-global extension')


def validate_raw(raw, item):
    import torch
    r = validate_selection(item)
    if type(raw) not in (dict, OrderedDict) or list(raw) != r['raw_top_level_keys']:
        raise RuntimeError('UniFormer complete raw checkpoint mapping/order differs')
    state = raw['state_dict']
    if type(state).__name__ != r['state_mapping_kind'] or type(state) not in (dict, OrderedDict) or list(state) != r['state_keys']:
        raise RuntimeError('UniFormer native state mapping kind/order differs')
    if type(raw['meta']) not in (dict, OrderedDict) or 'CLASSES' not in raw['meta'] or 'PALETTE' not in raw['meta']:
        raise RuntimeError('UniFormer native checkpoint meta CLASSES/PALETTE missing')
    total = 0
    for value in state.values():
        if type(value) is not torch.Tensor or value.layout != torch.strided or value.device.type != 'cpu' or value.is_quantized or value.is_complex():
            raise RuntimeError('UniFormer restricted state requires genuine real dense CPU Tensor values')
        total += value.numel() * value.element_size()
    if total != r['tensor_bytes'] or total > MAX_BYTES:
        raise RuntimeError('UniFormer actual state materialization count differs')
    # Every non-state primitive, including metadata and state._metadata, must
    # match ACTUAL owning inspection. No CLASSES/PALETTE are guessed or rebuilt.
    proof = [type(raw).__name__, [[k, primitive(v)] for k, v in raw.items() if k != 'state_dict'],
             ['state_mapping_kind', type(state).__name__], ['state_keys', list(state)],
             ['state_metadata_present', hasattr(state, '_metadata')]]
    if hasattr(state, '_metadata'):
        proof.append(['state_metadata', primitive(state._metadata)])
    if hasattr(raw, '_metadata'):
        proof.append(['raw_metadata', primitive(raw._metadata)])
    encoded = json.dumps(proof, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    if len(encoded) > MAX_BYTES or hashlib.sha256(encoded).hexdigest() != r['primitive_contract_sha256']:
        raise RuntimeError('UniFormer actual complete primitive metadata/container proof differs')
    return raw


def load_raw_checkpoint(archive, map_location=None, logger=None):
    if type(archive) is not SealedCheckpoint:
        raise RuntimeError('UniFormer checkpoint constructor requires exact sealed raw bytes')
    validate_selection(archive.selection)
    from io import BytesIO
    import torch
    # This is real retained Torch restricted decoding, not the SDK tensor-only
    # projection. No safe-global additions by this pack, unrestricted pickle or
    # fallback. torch and the ComfyUI host register their own safe globals, so
    # "none registered" never holds; instead the pinned per-checkpoint proof shows
    # this decode resolves only torch DEFAULT-allowlisted globals (consulted first).
    require_selected_torch(archive.selection)
    from .._restricted_globals import require_default_allowlisted
    require_default_allowlisted(archive.payload, archive.selection['resource'].get('pickle_globals'))
    raw = torch.load(BytesIO(archive.payload), map_location=map_location, weights_only=True)
    return validate_raw(raw, archive.selection)
