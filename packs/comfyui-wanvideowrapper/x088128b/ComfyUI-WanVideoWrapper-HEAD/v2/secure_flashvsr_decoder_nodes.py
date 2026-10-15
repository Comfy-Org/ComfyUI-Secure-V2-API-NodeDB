"""Staged FlashVSR decoder lifecycle using bounded public model assets.

The original complete TCDecoder stays pack-owned. Graph outputs carry a
digest-bound recipe; the decoder consumer rebuilds it inside its own guest.
Trained loading and consumer integration require separate qualification.
"""
import re
from comfy_api.latest import io, sdk
from ._wan_catalogue import valid_catalogue_name

FORMAT = 'wan-flashvsr-decoder-recipe-v1'
MAX_WEIGHT_BYTES = 256 * 1024 * 1024


async def load_flashvsr_decoder(model_name, precision, expected_sha256=None):
    import torch
    from .FlashVSR.TCDecoder import build_tcdecoder
    dtype = {'bf16':torch.bfloat16,'fp16':torch.float16,'fp32':torch.float32}[precision]
    if not valid_catalogue_name(model_name):
        raise ValueError('FlashVSR decoder requires a confined logical catalogue name')
    assets = sdk.current_context().assets
    asset = await assets.resolve('vae',model_name)
    size = await assets.size(asset)
    if not 0 < size <= MAX_WEIGHT_BYTES:
        raise ValueError('FlashVSR decoder weights exceed the bounded 256 MiB domain')
    digest = await assets.digest(asset)
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError('FlashVSR decoder resource changed since loader execution')
    # This public domain invokes Core's genuine safe loader, preserving its
    # SafeTensors, state_dict and one-member Torch checkpoint conventions.
    state = await assets.load_state_dict(asset)
    if await assets.digest(asset)!=digest:
        raise ValueError('FlashVSR decoder resource changed during read')
    if isinstance(state,dict):
        tensor_bytes = sum(value.numel()*value.element_size() for value in state.values() if isinstance(value,torch.Tensor))
        if tensor_bytes>MAX_WEIGHT_BYTES:
            raise ValueError('FlashVSR decoder tensors exceed the bounded 256 MiB domain')
    # Native helper defaults to CUDA. Preserve that declared behavior here;
    # guest GPU/device policy remains an explicit unresolved integration gate.
    decoder = build_tcdecoder(new_channels=[512,256,128,128],new_latent_channels=16+768,dtype=dtype)
    decoder.load_state_dict(state,strict=True)
    decoder.to(dtype)
    recipe = {'format':FORMAT,'model_name':model_name,'weights_sha256':digest,'precision':precision}
    return decoder,recipe


async def rebuild_flashvsr_decoder(recipe):
    if (type(recipe) is not dict or set(recipe)!={'format','model_name','weights_sha256','precision'}
            or recipe['format']!=FORMAT):
        raise ValueError('Invalid FlashVSR decoder recipe')
    digest = recipe['weights_sha256']
    if not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest):
        raise ValueError('FlashVSR decoder recipe requires an exact resource digest')
    decoder,_ = await load_flashvsr_decoder(recipe['model_name'],recipe['precision'],digest)
    return decoder


class WanVideoFlashVSRDecoderLoader(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets','raw')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoFlashVSRDecoderLoader',
            display_name='WanVideo FlashVSR Decoder Loader',category='WanVideoWrapper',
            description="Loads Wan VAE model from 'ComfyUI/models/vae'",inputs=[
                io.Combo.Input('model_name',options=[],tooltip="These models are loaded from 'ComfyUI/models/vae'",
                    remote=io.RemoteOptions(route='/models/vae',refresh_button=True,control_after_refresh='first')),
                io.Combo.Input('precision',options=['fp16','fp32','bf16'],optional=True,default='bf16'),
            ],outputs=[io.Custom('WANVAE').Output(display_name='vae')])

    @classmethod
    def validate_inputs(cls,input_types=None,**kwargs):
        name = kwargs.get('model_name')
        return True if name is None or valid_catalogue_name(name) else 'FlashVSR decoder requires a confined logical catalogue name'

    @classmethod
    async def execute(cls,model_name,precision):
        _,recipe = await load_flashvsr_decoder(model_name,precision)
        return io.NodeOutput(recipe)


NODE_CLASS_MAPPINGS = {'WanVideoFlashVSRDecoderLoader':WanVideoFlashVSRDecoderLoader}
