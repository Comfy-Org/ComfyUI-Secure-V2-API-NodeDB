"""Original MTV loader and pose encoder, prepared only for an admitted GPU lane."""
import hashlib
import json
from pathlib import Path
import re
import torch
from comfy_api.latest import io,sdk
from ._wan_catalogue import valid_catalogue_name
from .secure_tensor_nodes import _bound_payload

FORMAT='wan-mtv-vqvae-recipe-v1'
RECIPE_KEYS={'format','model_name','weights_sha256'}
MAX_WEIGHT_BYTES=2*1024**3


def require_native_mtv_cuda():
    # Native VectorQuantizer.reset_codebook unconditionally calls .cuda().
    # Preserve that device requirement rather than silently substituting CPU.
    if not torch.cuda.is_available():
        raise RuntimeError('Original MTV VQVAE requires an admitted CUDA compute lane; this CPU lane cannot execute it')


def validate_mtv_recipe(recipe):
    if (not isinstance(recipe,dict) or set(recipe)!=RECIPE_KEYS
            or recipe['format']!=FORMAT or not valid_catalogue_name(recipe['model_name'])
            or not isinstance(recipe['weights_sha256'],str)
            or re.fullmatch('[0-9a-f]{64}',recipe['weights_sha256']) is None):
        raise ValueError('Invalid digest-bound original MTV VQVAE recipe')


def verify_mtv_data():
    root=Path(__file__).parent
    bindings=json.loads((root/'secure_mtv_data_bindings.json').read_text())
    if set(bindings)!={'mean.npy','std.npy'}:
        raise ValueError('Unexpected MTV normalization data bindings')
    for name,row in bindings.items():
        path=root/'MTV/data'/name
        if path.stat().st_size!=row['bytes'] or row['bytes']>1024**2:
            raise ValueError('Original MTV normalization data size changed')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('Original MTV normalization data bytes changed')


def preflight_mtv_poses(poses):
    _bound_payload(poses)
    if not isinstance(poses,dict) or 'joints3d_nonparam' not in poses:
        raise ValueError('MTV requires the original NLF joints3d_nonparam structure')
    batch=poses['joints3d_nonparam']
    if not isinstance(batch,(list,tuple,torch.Tensor)) or len(batch)<1:
        raise ValueError('MTV requires at least one original NLF batch')
    sequence=batch[0]
    if not isinstance(sequence,(list,tuple,torch.Tensor)) or not 1<=len(sequence)<=64:
        raise ValueError('MTV pose sequence exceeds the bounded 64-frame domain')
    for frame in sequence:
        if (not isinstance(frame,torch.Tensor) or frame.layout!=torch.strided
                or frame.ndim!=3 or frame.shape[0]<1 or tuple(frame.shape[1:])!=(24,3)):
            raise ValueError('MTV requires dense original person-by-24-by-3 joint tensors')
    latent_frames=(len(sequence)+3)//4+2
    if latent_frames*24*8192*4*2>64*1024**2:
        raise ValueError('MTV quantizer projected work exceeds 64 MiB')


async def load_mtv_vqvae(model_name,*,expected_sha256=None,preserve_rng=False):
    if not valid_catalogue_name(model_name) or not model_name.lower().endswith(('.safetensors','.sft')):
        raise ValueError('MTV VQVAE requires a confined safetensors asset')
    require_native_mtv_cuda()
    assets=sdk.current_context().assets
    asset=await assets.resolve('vae',model_name)
    size=await assets.size(asset)
    if not 0<size<=MAX_WEIGHT_BYTES:
        raise ValueError('MTV VQVAE exceeds its bounded 2 GiB resource domain')
    digest=await assets.digest(asset)
    if expected_sha256 is not None and digest!=expected_sha256:
        raise ValueError('MTV VQVAE asset changed after recipe creation')
    state=await assets.load_state_dict(asset)
    if await assets.digest(asset)!=digest:
        raise ValueError('MTV VQVAE asset changed during loading')
    from .secure_mtv_algorithms import build_mtv_vqvae
    with torch.random.fork_rng(devices=[torch.cuda.current_device()],enabled=preserve_rng):
        model=build_mtv_vqvae(state)
    del state
    return model,{'format':FORMAT,'model_name':model_name,'weights_sha256':digest}


async def rebuild_mtv_vqvae(recipe):
    validate_mtv_recipe(recipe)
    return await load_mtv_vqvae(recipe['model_name'],expected_sha256=recipe['weights_sha256'],preserve_rng=True)


class LoadVQVAE(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw','assets','models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='LoadVQVAE',display_name='Load VQVAE',category='WanVideoWrapper',
            inputs=[io.Combo.Input('model_name',options=[],
                tooltip="These models are loaded from 'ComfyUI/models/vae'",
                remote=io.RemoteOptions(route='/models/vae',refresh_button=True,control_after_refresh='first'))],
            outputs=[io.Custom('VQVAE').Output(display_name='vqvae')])

    @classmethod
    def validate_inputs(cls,input_types=None,**kwargs):
        name=kwargs.get('model_name')
        return True if name is None or valid_catalogue_name(name) else 'MTV VQVAE requires a confined logical catalogue name'

    @classmethod
    async def execute(cls,model_name):
        _,recipe=await load_mtv_vqvae(model_name)
        return io.NodeOutput(recipe)


class MTVCrafterEncodePoses(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw','assets','models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='MTVCrafterEncodePoses',display_name='MTV Crafter Encode Poses',category='WanVideoWrapper',
            inputs=[io.Custom('VQVAE').Input('vqvae',tooltip='VQVAE model'),
                io.Custom('NLFPRED').Input('poses',tooltip='Input poses for the model')],
            outputs=[io.Custom('MTVCRAFTERMOTION').Output(display_name='mtvcrafter_motion'),
                io.Custom('NLFPRED').Output(display_name='pose_results')])

    @classmethod
    async def execute(cls,vqvae,poses):
        preflight_mtv_poses(poses)
        verify_mtv_data()
        model,_=await rebuild_mtv_vqvae(vqvae)
        from .secure_mtv_algorithms import encode_mtv_poses_original
        with torch.inference_mode():
            result,reconstruction=encode_mtv_poses_original(model,poses)
        _bound_payload((result,reconstruction))
        return io.NodeOutput(result,reconstruction)


NODE_CLASS_MAPPINGS={'LoadVQVAE':LoadVQVAE,'MTVCrafterEncodePoses':MTVCrafterEncodePoses}
