"""Pack-owned immutable LeReS assets/options/device selection; public APIs only."""
import json
import math
import re
import copy
from pathlib import Path
import torch
from comfy_api.latest import sdk

PIN='0cd290477128d42cdc3e76a826a402d866e8c684'
POLICY='9320cf5c624e96acc1d9ec92ff120ed6387a2142707f3194cb21dd0d11ac2500'
MAX_STATE_BYTES=512*1024*1024

def digest_field(value):
    return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None

def option_projection(opt):
    def project(value):
        if type(value) is float and not math.isfinite(value):
            return {'native_float': 'nan' if math.isnan(value) else ('+inf' if value>0 else '-inf')}
        if type(value) in (str,int,float,bool) or value is None:return value
        if type(value) is list:return [project(item) for item in value]
        raise TypeError('LeReS parsed option projection requires actual primitive values')
    return {key:project(value) for key,value in sorted(vars(opt).items())}

def selected_checkpoint():
    item=json.loads(Path(__file__).with_name('asset-selection.json').read_text())
    if item.get('approved') is not True:
        raise RuntimeError('LeReS: exact dual checkpoint, native argv/options and device selection pending')
    if item.get('format')!='amy-leres-managed-selection/1' or item.get('source_pin')!=PIN or item.get('published_loader_source_sha256')!=POLICY:
        raise ValueError('LeReS exact source/managed-reader policy differs')
    argv=item.get('argv')
    if type(argv) is not list or len(argv)>256 or any(type(arg) is not str for arg in argv) or sum(len(arg.encode()) for arg in argv)>65536:
        raise ValueError('LeReS explicit source-corresponding argv is required and bounded')
    for field in ('argv_correspondence_evidence_sha256','device_correspondence_evidence_sha256'):
        if not digest_field(item.get(field)):raise ValueError('LeReS trusted native options/device evidence unselected')
    if type(item.get('expected_cuda_available')) is not bool or type(item.get('expected_effective_options')) is not dict:
        raise ValueError('LeReS actual CUDA/parsed options correspondence unselected')
    for field in ('depth_device','expected_pix2pix_device'):
        if not isinstance(item.get(field),str) or not re.fullmatch(r'cpu|cuda(?::[0-9]+)?',item[field]):
            raise ValueError('LeReS actual selected device required; no neutral CPU assumption')
    if not isinstance(item.get('pix2pix_save_dir_label'),str) or not item['pix2pix_save_dir_label']:
        raise ValueError('LeReS native pix2pix save-dir correspondence label unselected')
    # This label is used only in native load-name calculation/diagnostics.
    # Managed state injection performs no file IO through it.
    assets=item.get('assets')
    if not isinstance(assets,dict) or set(assets)!={'depth','pix2pix'}:
        raise ValueError('LeReS both original constructor assets are required even without boost')
    for kind,filename in [('depth','res101.pth'),('pix2pix','latest_net_G.pth')]:
        asset=assets[kind]
        if (asset.get('source_repo'),asset.get('source_filename'),asset.get('folder'))!=('lllyasviel/Annotators',filename,'controlnet'):
            raise ValueError('LeReS native asset source identity differs')
        if not digest_field(asset.get('sha256')) or not digest_field(asset.get('restricted_shape_evidence_sha256')):
            raise ValueError('LeReS actual byte/container evidence required')
        if not isinstance(asset.get('revision'),str) or re.fullmatch('[0-9a-f]{40}',asset['revision']) is None:
            raise ValueError('LeReS actual immutable publisher revision required')
        if type(asset.get('bytes')) is not int or not 0<asset['bytes']<=MAX_STATE_BYTES:
            raise ValueError('LeReS serialized state exceeds inherited materialization bound')
        if not isinstance(asset.get('catalogue_name'),str) or not asset['catalogue_name']:
            raise ValueError('LeReS real managed catalogue name unselected')
        keys=asset.get('raw_top_level_keys')
        if type(keys) is not list or not keys or any(type(k) is not str for k in keys) or len(keys)!=len(set(keys)):
            raise ValueError('LeReS actual raw checkpoint keys required')
        if 'state_dict' in keys:raise RuntimeError('LeReS raw state_dict-prioritized layout does not preserve native source loading')
        if kind=='depth':
            if 'depth_model' not in keys:raise RuntimeError('LeReS native depth_model member missing in selected raw evidence')
            contract='depth-model-only-unwrapped' if keys==['depth_model'] else 'nested-depth-model-retained'
        else:contract='pix2pix-flat-tensor-map'
        if asset.get('load_state_contract')!=contract:
            raise ValueError('LeReS managed container contract contradicts actual raw checkpoint evidence')
    return item

async def selected_asset(item):
    ref=await sdk.ctx().assets.resolve(item['folder'],item['catalogue_name'])
    if await sdk.ctx().assets.size(ref)!=item['bytes'] or await sdk.ctx().assets.digest(ref)!=item['sha256']:
        raise ValueError('LeReS actual asset bytes differ from selection')
    return ref

def selected_member(loaded,item):
    contract=item['load_state_contract']
    if contract=='nested-depth-model-retained':value=loaded['depth_model']
    elif contract in ('depth-model-only-unwrapped','pix2pix-flat-tensor-map'):value=loaded
    else:raise RuntimeError('LeReS unsupported managed checkpoint container')
    if not isinstance(value,dict) or not 0<len(value)<=16384:
        raise ValueError('LeReS selected checkpoint must be a bounded tensor mapping')
    if contract=='pix2pix-flat-tensor-map' and list(value)!=item['raw_top_level_keys']:
        raise ValueError('LeReS pix2pix raw ordered keys changed by managed reader')
    total=0
    for key,tensor in value.items():
        if type(key) is not str or not isinstance(tensor,torch.Tensor) or tensor.layout!=torch.strided or tensor.device.type!='cpu' or tensor.ndim>4 or tensor.is_quantized or tensor.is_complex():
            raise ValueError('LeReS selected model mapping requires bounded dense real CPU tensors')
        total+=tensor.numel()*tensor.element_size()
    if total>MAX_STATE_BYTES:raise ValueError('LeReS tensor materialization exceeds inherited bound')
    return value

def native_map_location(value,device):
    """Restore native pix2pix load's str(self.device) tensor placement.

    The public restricted reader supplies CPU values. Preserve the actual
    dictionary class/order/metadata while copying tensors to the actual
    constructor device, without dtype conversion or migrating the model.
    """
    result=copy.copy(value)
    for key,tensor in value.items():result[key]=tensor.to(device)
    return result
