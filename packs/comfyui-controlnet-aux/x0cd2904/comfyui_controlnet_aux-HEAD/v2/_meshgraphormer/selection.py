"""Real sealed-byte paths; unsupported licensed/raw/vendor construction held."""
from dataclasses import dataclass
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re

PIN='0cd290477128d42cdc3e76a826a402d866e8c684'
MAX_BYTES=512*1024*1024


def require_setup(item):
    if item.get('approved') is not True:
        raise RuntimeError('MeshGraphormer managed dependencies/resource/vendor/device/lifetime selection pending; no pip')
    if item.get('format')!='amy-meshgraphormer-managed-selection/1' or item.get('source_pin')!=PIN:
        raise RuntimeError('MeshGraphormer exact native source unselected')
    for key in ('runtime_abi','vendor_source','bert_complete_local_config_contract','preimport_environment',
                'global_rng_and_args_hrnet_config_exclusive_lifetime','device_internal_policy','current_invocation',
                'finite_workspace','mediapipe_buffer_constructor_code_provenance'):
        value=item.get('authority',{}).get(key)
        if type(value) is not str or re.fullmatch('[0-9a-f]{64}',value) is None:
            raise RuntimeError('MeshGraphormer actual vendor/config/device/global lifecycle authority absent')


def require_construction(construction):
    require_setup(construction['selection'])
    # No currently proved native MANO pickle/object-matrix restricted contract.
    # A receipt boolean cannot turn unrestricted native deserialization into a
    # published safe reader. Preserve an explicit refusal until owning source
    # selection and an actual supported constructor are separately implemented.
    raise RuntimeError('MeshGraphormer MANO pickle and NumPy object-matrix reader contract unsupported; construction held')


def selected_construction():
    item=json.loads(Path(__file__).with_name('asset-selection.json').read_text())
    require_setup(item)
    require_construction({'selection':item})
    return item


@dataclass(frozen=True)
class SealedArchive:
    payload:bytes
    selection:dict
    def __str__(self):return 'sealed:'+self.selection['catalogue_name']


async def selected_archive(item,key,repo,filename):
    require_construction({'selection':item})
    row=item['resources'][key]
    if row.get('approved') is not True or (repo,filename)!=(row['source_repo'],row['source_filename']):
        raise RuntimeError('MeshGraphormer exact immutable sealed archive unselected')
    if type(row['bytes']) is not int or not 0<row['bytes']<=MAX_BYTES:
        raise RuntimeError('MeshGraphormer actual resource count unselected')
    if type(row['sha256']) is not str or re.fullmatch('[0-9a-f]{64}',row['sha256']) is None:
        raise RuntimeError('MeshGraphormer actual resource digest unselected')
    from comfy_api.latest import sdk
    assets=sdk.ctx().assets
    ref=await assets.resolve(row['folder'],row['catalogue_name'])
    if await assets.size(ref)!=row['bytes'] or await assets.digest(ref,'sha256')!=row['sha256']:
        raise RuntimeError('MeshGraphormer sealed size/digest differs')
    payload=await assets.read_bytes(ref)
    if type(payload) is not bytes or len(payload)!=row['bytes'] or hashlib.sha256(payload).hexdigest()!=row['sha256']:
        raise RuntimeError('MeshGraphormer sealed actual bytes differ')
    return SealedArchive(payload,row)


async def prepare_construction(item):
    require_construction({'selection':item})
    # Native eager initial HRNet acquisition comes before pipeline import;
    # graphormer/second HRNet come at their original classmethod points.
    initial=await selected_archive(item,'initial_hrnet','hr16/ControlNet-HandRefiner-pruned','hrnetv2_w64_imagenet_pretrained.pth')
    from .pipeline import args
    args.hrnet_checkpoint=initial
    hand=await selected_archive(item,'hand_landmarker',item['resources']['hand_landmarker']['source_repo'],'hand_landmarker.task')
    return {'selection':item,'initial_hrnet':initial,'hand_landmarker':hand}


def sealed_checkpoint_present(archive):
    if type(archive) is not SealedArchive:
        raise RuntimeError('MeshGraphormer requires sealed checkpoint, never an ambient path')
    if archive.selection.get('approved') is not True or hashlib.sha256(archive.payload).hexdigest()!=archive.selection['sha256']:
        raise RuntimeError('MeshGraphormer sealed checkpoint unselected or changed')
    return True


def read_restricted_checkpoint(archive):
    sealed_checkpoint_present(archive)
    row=archive.selection
    if row.get('saved_storage_all_cpu') is not True or row.get('raw_mapping_evidence_sha256') is None:
        raise RuntimeError('MeshGraphormer exact raw mapping/storage proof absent')
    import torch
    if torch.serialization.get_safe_globals():
        raise RuntimeError('MeshGraphormer safe-global extension is unsupported')
    # This retains native no-map_location saved storage. Actual CPU storage and
    # full dense/sparse mapping contract need restricted numerical inspection.
    return torch.load(BytesIO(archive.payload),weights_only=True)


def load_checkpoint(construction,key,discriminator,whole_model):
    require_construction(construction)
    if whole_model:
        raise RuntimeError('MeshGraphormer whole executable model pickle branch unsupported; never substitute a state dict')
    archive=construction[key]
    if discriminator!=archive.selection['native_resume_discriminator'] or 'state_dict' not in discriminator:
        raise RuntimeError('MeshGraphormer native resume-path branch correspondence absent')
    return read_restricted_checkpoint(archive)
