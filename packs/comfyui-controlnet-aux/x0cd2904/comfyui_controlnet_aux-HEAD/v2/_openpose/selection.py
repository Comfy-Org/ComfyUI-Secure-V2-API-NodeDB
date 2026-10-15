"""Immutable OpenPose raw state selection; no scientific import before gate."""
import json
import re
from pathlib import Path

PIN = '0cd290477128d42cdc3e76a826a402d866e8c684'
POLICY = '9320cf5c624e96acc1d9ec92ff120ed6387a2142707f3194cb21dd0d11ac2500'
MAX_STATE_BYTES = 512 * 1024 * 1024


def digest(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def source_triplet(repo, body, hand, face):
    if repo == 'lllyasviel/ControlNet':
        subfolder = 'annotator/ckpts'
        face_repo = 'lllyasviel/Annotators'
    else:
        subfolder = ''
        face_repo = repo
    # Native face inherits subfolder even when its repo changes. No fix.
    return [('body', repo, subfolder, body), ('hand', repo, subfolder, hand),
            ('face', face_repo, subfolder, face)]


def selected_record(item, kind, repo, subfolder, filename):
    matches = [r for r in item['resources'] if (r['kind'], r['source_repo'], r['source_subfolder'],
               r['source_filename']) == (kind, repo, subfolder, filename)]
    if len(matches) != 1 or matches[0].get('approved') is not True:
        raise RuntimeError('OpenPose exact native resource is not approved')
    r = matches[0]
    for field in ('sha256', 'restricted_shape_evidence_sha256', 'native_storage_correspondence_sha256'):
        if not digest(r.get(field)):
            raise RuntimeError('OpenPose actual raw state/byte/storage evidence is missing')
    if type(r.get('revision')) is not str or re.fullmatch('[0-9a-f]{40}', r['revision']) is None:
        raise RuntimeError('OpenPose immutable source revision is unselected')
    for field in ('bytes', 'tensor_bytes'):
        if type(r.get(field)) is not int or not 0 < r[field] <= MAX_STATE_BYTES:
            raise RuntimeError('OpenPose state materialization bound is unselected or exceeded')
    for field in ('folder', 'catalogue_name'):
        if type(r.get(field)) is not str or not r[field]:
            raise RuntimeError('OpenPose exact sealed catalogue input is missing')
    keys = r.get('raw_top_level_keys')
    if type(keys) is not list or not 0 < len(keys) <= 16384 or any(type(k) is not str for k in keys) or len(set(keys)) != len(keys):
        raise RuntimeError('OpenPose original ordered flat raw keys are unselected')
    if 'state_dict' in keys or r.get('load_state_contract') != 'raw-flat-tensor-mapping':
        raise RuntimeError('OpenPose native raw mapping is not preserved by state_dict-priority/unwrapping')
    if r.get('native_saved_storage_all_cpu') is not True:
        raise RuntimeError('OpenPose native no-map_location storage correspondence is held')
    policy = 'exact-original-ordered-metadata' if kind == 'face' else 'native-transfer-discards'
    if r.get('raw_metadata_policy') != policy:
        raise RuntimeError('OpenPose raw metadata is not preserved by the selected public reader')
    if kind == 'face':
        from .face_metadata import METADATA_SHA256
        if r.get('raw_metadata_sha256') != METADATA_SHA256 or not digest(r.get('native_metadata_correspondence_sha256')):
            raise RuntimeError('OpenPose Face original metadata correspondence is unselected')
    return r


def preflight_triplet(item, repo, body, hand, face):
    rows = [selected_record(item, *args) for args in source_triplet(repo, body, hand, face)]
    if sum(r['tensor_bytes'] for r in rows) > MAX_STATE_BYTES:
        raise RuntimeError('OpenPose aggregate state materialization exceeds inherited bound')
    return rows


def selected_checkpoint():
    item = json.loads(Path(__file__).with_name('asset-selection.json').read_text())
    if item.get('approved') is not True:
        raise RuntimeError('OpenPose three raw checkpoints/runtime/device selection pending')
    if item.get('format') != 'amy-openpose-managed-selection/1' or item.get('source_pin') != PIN or item.get('published_loader_source_sha256') != POLICY:
        raise RuntimeError('OpenPose exact source/public reader policy differs')
    for field in ('runtime_abi_evidence_sha256', 'device_correspondence_sha256', 'preimport_context_evidence_sha256'):
        if not digest(item.get(field)):
            raise RuntimeError('OpenPose actual native runtime/device/context evidence is missing')
    if type(item.get('device')) is not str or re.fullmatch(r'cpu|cuda(?::[0-9]+)?', item['device']) is None:
        raise RuntimeError('OpenPose actual to-device is not selected')
    # Default wrapper uses EXACT source HF_MODEL_NAME and filenames. Alternate
    # ControlNet/subfolder selection belongs to an explicit native constructor
    # case, not a hidden default replacement.
    preflight_triplet(item, 'lllyasviel/Annotators', 'body_pose_model.pth', 'hand_pose_model.pth', 'facenet.pth')
    return item


async def selected_asset(record):
    from comfy_api.latest import sdk
    assets = sdk.ctx().assets
    ref = await assets.resolve(record['folder'], record['catalogue_name'])
    if await assets.size(ref) != record['bytes'] or await assets.digest(ref) != record['sha256']:
        raise RuntimeError('OpenPose sealed resource bytes differ from selection')
    return ref


async def selected_state(ref, record):
    from comfy_api.latest import sdk
    import torch
    value = await sdk.ctx().assets.load_state_dict(ref)
    return validate_state(value, record)


def validate_state(value, record):
    import torch
    if not isinstance(value, dict) or list(value) != record['raw_top_level_keys']:
        raise RuntimeError('OpenPose selected raw mapping keys/order differ from public reader')
    total = 0
    for key, tensor in value.items():
        if type(key) is not str or type(tensor) is not torch.Tensor or tensor.layout != torch.strided or tensor.device.type != 'cpu' or tensor.ndim > 4 or tensor.is_complex() or tensor.is_quantized:
            raise RuntimeError('OpenPose restricted state requires actual dense real CPU tensors')
        total += tensor.numel() * tensor.element_size()
    if total != record['tensor_bytes'] or total > MAX_STATE_BYTES:
        raise RuntimeError('OpenPose actual tensor materialization differs from selected raw evidence')
    if record['kind'] == 'face':
        from .face_metadata import restore_face_metadata
        return restore_face_metadata(value, record)
    return value
