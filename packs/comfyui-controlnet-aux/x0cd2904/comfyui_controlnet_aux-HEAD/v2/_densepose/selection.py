"""Pack-owned immutable executable-code selection. No scientific imports."""
import hashlib
import json
from pathlib import Path
import re

PIN = '0cd290477128d42cdc3e76a826a402d866e8c684'
REPO = 'LayerNorm/DensePose-TorchScript-with-hint-image'
FILES = ('densepose_r50_fpn_dl.torchscript', 'densepose_r101_fpn_dl.torchscript')
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024


def digest(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def selected_record(item, repo, filename):
    validate_selection(item)
    if repo != REPO or filename not in FILES:
        raise RuntimeError('DensePose exact native archive selection is unavailable')
    rows = [r for r in item.get('resources', [])
            if (r.get('source_repo'), r.get('source_filename')) == (repo, filename)]
    if len(rows) != 1 or rows[0].get('approved') is not True or rows[0].get('executable_code_approved') is not True:
        raise RuntimeError('DensePose immutable archive and executable code are not approved')
    row = rows[0]
    for key in ('sha256', 'code_provenance_sha256', 'operator_abi_evidence_sha256', 'sealed_catalogue_evidence_sha256'):
        if not digest(row.get(key)):
            raise RuntimeError('DensePose actual archive/code/operator/catalogue evidence is missing')
    if type(row.get('revision')) is not str or re.fullmatch('[0-9a-f]{40}', row['revision']) is None:
        raise RuntimeError('DensePose immutable publisher revision is unselected')
    if type(row.get('bytes')) is not int or not 0 < row['bytes'] <= MAX_ARCHIVE_BYTES:
        raise RuntimeError('DensePose selected archive materialization is unbounded')
    if row.get('format') != 'torchscript':
        raise RuntimeError('DensePose requires genuine executable TorchScript, not a state dictionary')
    for key in ('folder', 'catalogue_name'):
        if type(row.get(key)) is not str or not row[key]:
            raise RuntimeError('DensePose exact sealed catalogue resource is missing')
    return row


def validate_selection(item):
    if item.get('approved') is not True:
        raise RuntimeError('DensePose executable archive/runtime/operator/device selection pending')
    if item.get('format') != 'amy-densepose-managed-selection/1' or item.get('source_pin') != PIN:
        raise RuntimeError('DensePose selected original source differs')
    for key in ('runtime_abi_evidence_sha256', 'torchvision_nms_registration_evidence_sha256',
                'device_correspondence_sha256', 'preimport_context_evidence_sha256',
                'current_invocation_admission_sha256'):
        if not digest(item.get(key)):
            raise RuntimeError('DensePose runtime/operator/device/current invocation evidence is missing')
    if type(item.get('device')) is not str or re.fullmatch(r'cpu|cuda(?::[0-9]+)?', item['device']) is None:
        raise RuntimeError('DensePose actual native to-device is unselected')


def selected_checkpoint(filename):
    item = json.loads(Path(__file__).with_name('asset-selection.json').read_text())
    selected_record(item, REPO, filename)
    return item


async def selected_bytes(item, repo, filename):
    # Recheck the approved exact resource before any SDK import or RPC.
    row = selected_record(item, repo, filename)
    from comfy_api.latest import sdk
    assets = sdk.ctx().assets
    ref = await assets.resolve(row['folder'], row['catalogue_name'])
    if await assets.size(ref) != row['bytes'] or await assets.digest(ref, 'sha256') != row['sha256']:
        raise RuntimeError('DensePose sealed archive identity differs from selection')
    from .._sealed_asset_read import read_sealed_asset
    payload = await read_sealed_asset(assets, ref, row['bytes'], row['sha256'])
    if type(payload) is not bytes or len(payload) != row['bytes'] or hashlib.sha256(payload).hexdigest() != row['sha256']:
        raise RuntimeError('DensePose actual executable archive bytes differ from selection')
    return payload
