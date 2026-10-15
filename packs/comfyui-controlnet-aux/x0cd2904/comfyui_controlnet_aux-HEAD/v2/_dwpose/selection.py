"""Pack-owned sealed inputs. No engine, realm or generation authority is invented."""
import hashlib
import io
import json
from dataclasses import dataclass, field
from pathlib import Path

MAX_ASSET_BYTES = 512 * 1024 * 1024
TORCH_JIT_SOURCE_SHA256 = '6193834f0c6f313eb1f9554e8997c480b4781ee27df78cf609141948bc8600f6'


def digest(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def selected_family(node_id):
    item = json.loads(Path(__file__).with_name('asset-selection.json').read_text())
    if item.get('approved') is not True:
        raise RuntimeError(node_id + ': immutable DWpose/AnimalPose resources/runtime remain unselected')
    for field in ('runtime_abi_evidence_sha256', 'serialized_code_provenance_sha256',
                  'provider_device_correspondence_sha256', 'resource_generation_sha256'):
        if not digest(item.get(field)):
            raise RuntimeError(node_id + ': missing actual ' + field)
    if type(item.get('torchscript_device')) is not str or not item['torchscript_device']:
        raise RuntimeError(node_id + ': original TorchScript placement is not selected')
    # A receipt or ambient environment variable alone cannot establish the
    # current authenticated realm/generation. The consumed published guest
    # asset interface has no such identity accessor. Do not guess one.
    raise RuntimeError(node_id + ': published current realm/resource/provider/device generation binding is held; native warm cache cannot be admitted')


@dataclass(frozen=True)
class SealedResource:
    source_repo: str
    filename: str
    payload: bytes = field(repr=False)
    sha256: str
    format: str

    def __str__(self):
        # Native fallback diagnostics receive a sealed source filename label,
        # never payload repr or a fabricated/exposed host cache pathname.
        return self.filename


def resource_name(value):
    if value is None:
        return None
    if not isinstance(value, SealedResource):
        raise TypeError('DWpose construction requires a selected sealed resource, never a host path')
    return value.filename


def resource_record(item, repo, filename):
    if filename is None:
        # Animal native acquisition calls Path.joinpath(..., filename) even
        # for None. DW's native constructor skips this call when det is None.
        Path('selected-native-acquisition-shape').joinpath(filename)
    if type(repo) is not str or type(filename) is not str:
        raise TypeError('native resource repository/filename must be strings')
    if '/' in filename or '\\' in filename or filename in ('', '.', '..'):
        raise RuntimeError('resource filename is not a selected native basename')
    records = [r for r in item['resources'] if r['source_repo'] == repo and r['source_filename'] == filename]
    if len(records) != 1:
        raise RuntimeError('exact native repository/filename resource is unselected')
    r = records[0]
    if r.get('approved') is not True:
        raise RuntimeError('resource identity/code provenance is not approved')
    for f in ('sha256', 'serialized_code_provenance_sha256', 'constructor_correspondence_sha256'):
        if not digest(r.get(f)):
            raise RuntimeError('missing actual immutable resource ' + f)
    if type(r.get('revision')) is not str or not r['revision']:
        raise RuntimeError('immutable upstream revision is missing')
    if type(r.get('bytes')) is not int or not 0 < r['bytes'] <= MAX_ASSET_BYTES:
        raise RuntimeError('resource byte bound is unselected or exceeds inherited materialization limit')
    for f in ('folder', 'catalogue_name'):
        if type(r.get(f)) is not str or not r[f]:
            raise RuntimeError('sealed catalogue input is not selected')
    if filename.endswith('.torchscript.pt'):
        if r.get('format') != 'torchscript' or r.get('constructor_source_sha256') != TORCH_JIT_SOURCE_SHA256:
            raise RuntimeError('actual TorchScript filelike construction contract is not selected')
    elif 'onnx' in filename:
        # No vendor ABI/filelike/byte constructor contract has been supplied
        # for ORT or OpenCV. Refuse BEFORE resolving/reading an asset or
        # constructing an engine. Classification/fallback source stays exact.
        raise RuntimeError('ONNX ORT/OpenCV sealed-byte constructor contract is held')
    else:
        raise RuntimeError('native serialization format construction is held')
    return r


def preflight_resources(item, det_repo, det_filename, pose_repo, pose_filename, *, skip_none_detector):
    rows = []
    if not (skip_none_detector and det_filename is None):
        rows.append(resource_record(item, det_repo, det_filename))
    rows.append(resource_record(item, pose_repo, pose_filename))
    if sum(r['bytes'] for r in rows) > MAX_ASSET_BYTES:
        raise RuntimeError('aggregate serialized inputs exceed inherited bounded materialization')


async def selected_resource(item, repo, filename):
    r = resource_record(item, repo, filename)
    from comfy_api.latest import sdk
    assets = sdk.ctx().assets
    ref = await assets.resolve(r['folder'], r['catalogue_name'])
    if await assets.size(ref) != r['bytes'] or await assets.digest(ref, 'sha256') != r['sha256']:
        raise RuntimeError('sealed resource size/digest differs from selection')
    payload = await assets.read_bytes(ref)
    if type(payload) is not bytes or len(payload) != r['bytes'] or hashlib.sha256(payload).hexdigest() != r['sha256']:
        raise RuntimeError('actual serialized resource bytes differ from selection')
    return SealedResource(repo, filename, payload, r['sha256'], r['format'])


def engine_input(resource, engine):
    if not isinstance(resource, SealedResource):
        raise TypeError('engine input must be a genuine sealed resource')
    if engine != 'torchscript' or resource.format != 'torchscript':
        raise RuntimeError('ONNX ORT/OpenCV byte/buffer construction remains held')
    # Published Torch2.8 source accepts BytesIO and calls the genuine C++
    # import_ir_module_from_buffer. No map_location override: native load then
    # .to(torchscript_device) and its original serialized-code semantics stay.
    return io.BytesIO(resource.payload)
