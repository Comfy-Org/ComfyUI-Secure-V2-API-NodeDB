"""Managed AnimeFace composition. Missing exact resource selection stays refused."""
import json
import re
from pathlib import Path
import torch
from comfy_api.latest import sdk
from ._annotator import common_annotator_call
from ._anime_face_network import UNet
from ._anime_face_background import AnimeSegmentation
from ._anime_face_detector import AnimeFaceSegmentor

MAX_STATE_BYTES = 256 * 1024 * 1024

def selected_artifacts():
    value = json.loads(Path(__file__).with_name('_anime_face_assets.json').read_text())
    if value.get('approved') is not True:
        raise RuntimeError('AnimeFace_SemSegPreprocessor: exact UNet/ISNet/MobileNet managed artifact selection pending')
    if value.get('format') != 'amy-anime-face-managed-artifacts/1' or value.get('source_pin') != '0cd290477128d42cdc3e76a826a402d866e8c684' or value.get('folder') != 'controlnet':
        raise ValueError('AnimeFace artifact selection does not match retained source')
    assets = value['artifacts']
    if set(assets) != {'unet', 'background', 'mobilenet'}:
        raise ValueError('AnimeFace constructor requires three exact assets')
    sources = {'unet': ('bdsqlsz/qinglong_controlnet-lllite','Annotators/UNet.pth'),
               'background': ('skytnt/anime-seg','isnetis.ckpt')}
    for key, item in assets.items():
        if not isinstance(item.get('sha256'),str) or not re.fullmatch('[0-9a-f]{64}',item['sha256']):
            raise ValueError('AnimeFace asset needs a complete reviewed digest')
        if type(item.get('bytes')) is not int or not 0 < item['bytes'] <= MAX_STATE_BYTES:
            raise ValueError('AnimeFace serialized asset size is not bounded')
        if not isinstance(item.get('catalogue_name'),str) or not item['catalogue_name']:
            raise ValueError('AnimeFace asset needs an actual managed catalogue binding')
        if key in sources:
            if (item.get('source_repo'),item.get('source_filename')) != sources[key] or not isinstance(item.get('revision'),str) or not re.fullmatch('[0-9a-f]{40}',item['revision']):
                raise ValueError('AnimeFace Hugging Face source pin is not exact')
        elif item.get('source_url') != 'https://download.pytorch.org/models/mobilenet_v2-b0353104.pth':
            raise ValueError('AnimeFace MobileNet source identity differs')
    if sum(item['bytes'] for item in assets.values()) > MAX_STATE_BYTES:
        raise ValueError('AnimeFace serialized assets exceed aggregate bound')
    return assets

async def resolve(item):
    asset = await sdk.ctx().assets.resolve('controlnet', item['catalogue_name'])
    if await sdk.ctx().assets.digest(asset) != item['sha256']:
        raise ValueError('AnimeFace asset digest differs from exact selection')
    return asset

async def state(asset):
    value = await sdk.ctx().assets.load_state_dict(asset)
    if not isinstance(value,dict) or not 0 < len(value) <= 8192:
        raise ValueError('AnimeFace requires a bounded string-to-tensor mapping')
    total=0
    for key, tensor in value.items():
        if not isinstance(key,str) or not isinstance(tensor,torch.Tensor) or tensor.layout != torch.strided or tensor.device.type != 'cpu' or tensor.ndim > 4 or tensor.is_complex() or tensor.is_quantized:
            raise ValueError('AnimeFace state must contain bounded dense CPU tensors')
        total += tensor.numel() * tensor.element_size()
    if total > MAX_STATE_BYTES:
        raise ValueError('AnimeFace state exceeds aggregate materialization bound')
    return value,total

async def execute(image, remove_background_using_abg=True, resolution=512, **kwargs):
    selection = selected_artifacts()
    # Source resolves UNet + ABG paths, then constructs/loads MobileNet inside
    # UNet before loading UNet and ABG states. Do not skip any false-branch load.
    unet_asset = await resolve(selection['unet'])
    background_asset = await resolve(selection['background'])
    mobilenet_asset = await resolve(selection['mobilenet'])
    mobilenet_state, mobile_bytes = await state(mobilenet_asset)
    network = UNet(mobilenet_state)
    unet_state, unet_bytes = await state(unet_asset)
    if mobile_bytes + unet_bytes > MAX_STATE_BYTES:
        raise ValueError('AnimeFace constructor state exceeds aggregate bound')
    network.load_state_dict(unet_state, strict=True)
    network.eval()
    background_state, background_bytes = await state(background_asset)
    if mobile_bytes + unet_bytes + background_bytes > MAX_STATE_BYTES:
        raise ValueError('AnimeFace constructor state exceeds aggregate bound')
    background = AnimeSegmentation(background_state, device='cpu')
    model = AnimeFaceSegmentor(network, background).to('cpu')
    if remove_background_using_abg:
        out_image_with_mask = common_annotator_call(model,image,resolution=resolution,remove_background=True)
        out_image = out_image_with_mask[..., :3]
        mask = out_image_with_mask[..., 3:].permute(0,3,1,2)
    else:
        out_image = common_annotator_call(model,image,resolution=resolution,remove_background=False)
        N,H,W,C = out_image.shape
        # Preserve native NCHW ones, including three channels. No MASK squeeze.
        mask = torch.ones(N,C,H,W)
    del model
    return out_image,mask
