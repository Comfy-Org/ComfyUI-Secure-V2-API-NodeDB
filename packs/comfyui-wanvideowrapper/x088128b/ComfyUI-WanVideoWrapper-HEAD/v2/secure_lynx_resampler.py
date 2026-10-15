"""Original Lynx resampler behind the public asset broker; trained test pending."""
import re
import torch
from comfy_api.latest import io,sdk
from ._wan_catalogue import valid_catalogue_name
from .lynx.resampler import Resampler

FORMAT='wan-lynx-resampler-recipe-v1'
RECIPE_KEYS={'format','model_name','weights_sha256','precision'}
MAX_WEIGHT_BYTES=1024**3
offload_device=torch.device('cpu')


def build_lynx_resampler(resampler_sd,precision):
    dtype = {'bf16': torch.bfloat16, 'fp16': torch.float16, 'fp32': torch.float32}[precision]
    output_dim = resampler_sd['proj_out.weight'].shape[0]
    resampler = Resampler(depth=4, dim=1280, dim_head=64, embedding_dim=512,
        ff_mult=4, heads=20, num_queries=16, output_dim=output_dim, dtype=dtype).eval()
    resampler.to(offload_device, dtype)
    resampler.load_state_dict(resampler_sd, strict=True)
    return resampler


def validate_lynx_recipe(recipe):
    if (not isinstance(recipe,dict) or set(recipe)!=RECIPE_KEYS
            or recipe['format']!=FORMAT or not valid_catalogue_name(recipe['model_name'])
            or recipe['precision'] not in ('fp32','bf16','fp16')
            or not isinstance(recipe['weights_sha256'],str)
            or re.fullmatch('[0-9a-f]{64}',recipe['weights_sha256']) is None):
        raise ValueError('Invalid digest-bound original Lynx resampler recipe')


async def load_lynx_resampler(model_name,precision,*,expected_sha256=None,preserve_rng=False):
    if (not valid_catalogue_name(model_name)
            or not model_name.lower().endswith(('.safetensors','.sft'))
            or precision not in ('fp32','bf16','fp16')):
        raise ValueError('Lynx resampler requires a confined safetensors asset and original precision')
    assets=sdk.current_context().assets
    asset=await assets.resolve('diffusion_models',model_name)
    size=await assets.size(asset)
    if not 0<size<=MAX_WEIGHT_BYTES:
        raise ValueError('Lynx resampler exceeds its bounded 1 GiB weight domain')
    digest=await assets.digest(asset)
    if expected_sha256 is not None and digest!=expected_sha256:
        raise ValueError('Lynx resampler asset changed after recipe creation')
    state=await assets.load_state_dict(asset)
    if await assets.digest(asset)!=digest:
        raise ValueError('Lynx resampler asset changed during loading')
    output=state['proj_out.weight']
    if (not isinstance(output,torch.Tensor) or output.ndim!=2
            or output.shape[1]!=1280 or not 1<=output.shape[0]<=8192):
        raise ValueError('Lynx projection exceeds bounded original 1280-channel model domain')
    with torch.random.fork_rng(devices=[],enabled=preserve_rng):
        model=build_lynx_resampler(state,precision)
    del state
    recipe={'format':FORMAT,'model_name':model_name,'weights_sha256':digest,'precision':precision}
    return model,recipe


async def rebuild_lynx_resampler(recipe):
    validate_lynx_recipe(recipe)
    return await load_lynx_resampler(recipe['model_name'],recipe['precision'],
        expected_sha256=recipe['weights_sha256'],preserve_rng=True)


class LoadLynxResampler(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('assets','raw','models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='LoadLynxResampler',display_name='Load Lynx Resampler',
            category='WanVideoWrapper',inputs=[
                io.Combo.Input('model_name',options=[],
                    tooltip="These models are loaded from 'ComfyUI/models/diffusion_models'",
                    remote=io.RemoteOptions(route='/models/diffusion_models',refresh_button=True,control_after_refresh='first')),
                io.Combo.Input('precision',options=['fp32','bf16','fp16'],default='fp16')],
            outputs=[io.Custom('LYNXRESAMPLER').Output(display_name='resampler')])

    @classmethod
    def validate_inputs(cls,input_types=None,**kwargs):
        name=kwargs.get('model_name')
        return True if name is None or valid_catalogue_name(name) else 'Lynx resampler requires a confined logical catalogue name'

    @classmethod
    async def execute(cls,model_name,precision):
        _,recipe=await load_lynx_resampler(model_name,precision)
        return io.NodeOutput(recipe)


NODE_CLASS_MAPPINGS={'LoadLynxResampler':LoadLynxResampler}
