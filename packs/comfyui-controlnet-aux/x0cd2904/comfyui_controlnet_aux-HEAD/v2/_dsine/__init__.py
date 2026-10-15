"""Native DSINE constructor/loader composition using published individual assets.

Unapproved immutable payload/container selection refuses before asset RPC or
network construction. No cache/network fallback or fabricated catalogue exists.
"""
import json
import re
from pathlib import Path
import torch
from comfy_api.latest import sdk
from .._annotator import common_annotator_call
from .models.dsine_arch import DSINE
from .detector import DsineDetector, load_checkpoint

MAX_STATE_BYTES=512*1024*1024

def selected_checkpoint():
    item=json.loads(Path(__file__).with_name('asset-selection.json').read_text())
    if item.get('approved') is not True:
        raise RuntimeError('DSINE-NormalMapPreprocessor: exact managed dsine model-container selection pending')
    if item.get('format')!='amy-dsine-managed-checkpoint/1' or item.get('source_pin')!='0cd290477128d42cdc3e76a826a402d866e8c684':
        raise ValueError('DSINE selected source differs')
    if (item.get('source_repo'),item.get('source_filename'),item.get('folder'))!=('hr16/Diffusion-Edge','dsine.pt','controlnet'):
        raise ValueError('DSINE asset identity differs from retained source')
    for name,width in [('sha256',64),('revision',40),('restricted_shape_evidence_sha256',64)]:
        if not isinstance(item.get(name),str) or not re.fullmatch('[0-9a-f]{'+str(width)+'}',item[name]):
            raise ValueError('DSINE exact asset/container evidence pending')
    if item.get('published_loader_source_sha256')!='9320cf5c624e96acc1d9ec92ff120ed6387a2142707f3194cb21dd0d11ac2500':
        raise ValueError('DSINE loader policy source differs')
    if type(item.get('bytes')) is not int or not 0 < item['bytes'] <= MAX_STATE_BYTES:
        raise ValueError('DSINE serialized state is not bounded')
    if not isinstance(item.get('catalogue_name'),str) or not item['catalogue_name']:
        raise ValueError('DSINE actual managed catalogue binding pending')
    keys=item.get('raw_top_level_keys')
    if not isinstance(keys,list) or not keys or any(not isinstance(k,str) for k in keys) or len(keys)!=len(set(keys)):
        raise ValueError('DSINE actual original checkpoint keys pending')
    if 'model' not in keys or 'state_dict' in keys:
        raise RuntimeError('DSINE native model container is not preserved by this published loader policy')
    contract='model-only-unwrapped' if keys==['model'] else 'nested-model-retained'
    if item.get('load_state_contract')!=contract:
        raise ValueError('DSINE selected container contract contradicts original keys')
    if item.get('managed_asset_member') != 'model':
        raise RuntimeError('DSINE requires the original literal top-level model member')
    evidence=item.get('published_member_API_deployment_evidence_sha256')
    if not isinstance(evidence,str) or not re.fullmatch('[0-9a-f]{64}',evidence):
        raise RuntimeError('DSINE supported member API live deployment remains pending')
    return item

def model_member(loaded,contract):
    if contract=='literal-top-level-model-member':
        value=loaded
    elif contract=='nested-model-retained':
        # Native KeyError is deliberately preserved for a missing model key.
        value=loaded['model']
    elif contract=='model-only-unwrapped':
        value=loaded
    else:
        raise RuntimeError('DSINE published loader container contract remains unsupported')
    if not isinstance(value,dict) or not 0 < len(value) <= 16384:
        raise ValueError('DSINE requires the native bounded model tensor mapping')
    total=0
    for key,tensor in value.items():
        if not isinstance(key,str) or not isinstance(tensor,torch.Tensor) or tensor.layout!=torch.strided or tensor.device.type!='cpu' or tensor.ndim>4 or tensor.is_quantized or tensor.is_complex():
            raise ValueError('DSINE model member must contain bounded dense CPU tensors')
        total+=tensor.numel()*tensor.element_size()
    if total>MAX_STATE_BYTES:
        raise ValueError('DSINE model member exceeds inherited materialization bound')
    return value

async def managed_detector():
    item=selected_checkpoint()
    asset=await sdk.ctx().assets.resolve(item['folder'],item['catalogue_name'])
    if await sdk.ctx().assets.size(asset)!=item['bytes']:
        raise ValueError('DSINE weight size differs from exact selection')
    if await sdk.ctx().assets.digest(asset)!=item['sha256']:
        raise ValueError('DSINE weight digest differs from exact selection')
    # Native order: resolve file, instantiate whole network, load, eval, detector.
    model=DSINE()
    loaded=await sdk.ctx().assets.load_state_dict(asset,member="model")
    model=load_checkpoint(model_member(loaded,'literal-top-level-model-member'),model)
    model.eval()
    return DsineDetector(model)

async def execute( image, fov=60.0, iterations=5, resolution=512, **kwargs):

    model = (await managed_detector()).to('cpu')
    out = common_annotator_call(model, image, fov=fov, iterations=iterations, resolution=resolution)
    del model
    return (out,)
