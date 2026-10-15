"""Original FantasyPortrait adapter and complete weight recipe; trained test pending."""
import re
import torch
from comfy_api.latest import io,sdk
from ._wan_catalogue import valid_catalogue_name
from .fantasyportrait.model import PortraitAdapter

FORMAT='wan-fantasy-portrait-recipe-v1'
RECIPE_KEYS={'format','model_name','weights_sha256','base_precision'}
PRECISIONS=('fp8_e4m3fn','fp8_e4m3fn_fast','bf16','fp16','fp16_fast','fp32')
MAX_WEIGHT_BYTES=2*1024**3
offload_device=torch.device('cpu')


def build_portrait_resource(sd,base_precision):
    from accelerate import init_empty_weights
    from accelerate.utils import set_module_tensor_to_device
    base_dtype = {'fp8_e4m3fn': torch.float8_e4m3fn, 'fp8_e4m3fn_fast': torch.float8_e4m3fn,
        'bf16': torch.bfloat16, 'fp16': torch.float16, 'fp16_fast': torch.float16, 'fp32': torch.float32}[base_precision]
    adapter_in_dim = sd['proj_model.norm.weight'].shape[0]
    with init_empty_weights():
        fantasyportrait_proj_adapter = PortraitAdapter(adapter_in_dim=adapter_in_dim,
            adapter_proj_dim=adapter_in_dim,dtype=base_dtype)
    for name,param in fantasyportrait_proj_adapter.named_parameters():
        set_module_tensor_to_device(fantasyportrait_proj_adapter,name,device=offload_device,
            dtype=base_dtype,value=sd[name])
    fantasyportrait={'proj_model':fantasyportrait_proj_adapter,'sd':sd}
    return fantasyportrait


def validate_portrait_recipe(recipe):
    if (not isinstance(recipe,dict) or set(recipe)!=RECIPE_KEYS
            or recipe['format']!=FORMAT or not valid_catalogue_name(recipe['model_name'])
            or recipe['base_precision'] not in PRECISIONS
            or not isinstance(recipe['weights_sha256'],str)
            or re.fullmatch('[0-9a-f]{64}',recipe['weights_sha256']) is None):
        raise ValueError('Invalid digest-bound FantasyPortrait recipe')


async def load_portrait_resource(model,base_precision,*,expected_sha256=None,preserve_rng=False):
    if (not valid_catalogue_name(model) or not model.lower().endswith(('.safetensors','.sft'))
            or base_precision not in PRECISIONS):
        raise ValueError('FantasyPortrait requires a confined safetensors asset and original precision')
    assets=sdk.current_context().assets
    asset=await assets.resolve('diffusion_models',model)
    size=await assets.size(asset)
    if not 0<size<=MAX_WEIGHT_BYTES:
        raise ValueError('FantasyPortrait exceeds its bounded 2 GiB weight domain')
    digest=await assets.digest(asset)
    if expected_sha256 is not None and expected_sha256!=digest:
        raise ValueError('FantasyPortrait checkpoint changed after recipe creation')
    state=await assets.load_state_dict(asset)
    if await assets.digest(asset)!=digest:
        raise ValueError('FantasyPortrait checkpoint changed during loading')
    norm=state['proj_model.norm.weight']
    if not isinstance(norm,torch.Tensor) or norm.ndim!=1 or not 1<=norm.shape[0]<=8192:
        raise ValueError('FantasyPortrait adapter exceeds the bounded 8192-channel resource domain')
    with torch.random.fork_rng(devices=[],enabled=preserve_rng):
        resource=build_portrait_resource(state,base_precision)
    recipe={'format':FORMAT,'model_name':model,'weights_sha256':digest,'base_precision':base_precision}
    return resource,recipe


async def rebuild_portrait_resource(recipe):
    validate_portrait_recipe(recipe)
    return await load_portrait_resource(recipe['model_name'],recipe['base_precision'],
        expected_sha256=recipe['weights_sha256'],preserve_rng=True)


class FantasyPortraitModelLoader(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('assets','raw','models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='FantasyPortraitModelLoader',display_name='FantasyPortrait Model Loader',
            category='WanVideoWrapper',inputs=[
                io.Combo.Input('model',options=[],
                    tooltip="These models are loaded from the 'ComfyUI/models/diffusion_models' -folder",
                    remote=io.RemoteOptions(route='/models/diffusion_models',refresh_button=True,control_after_refresh='first')),
                io.Combo.Input('base_precision',options=['fp32','bf16','fp16'],default='fp16')],
            outputs=[io.Custom('FANTASYPORTRAITMODEL').Output(display_name='model')])

    @classmethod
    def validate_inputs(cls,input_types=None,**kwargs):
        name=kwargs.get('model')
        return True if name is None or valid_catalogue_name(name) else 'FantasyPortrait requires a confined logical catalogue name'

    @classmethod
    async def execute(cls,model,base_precision):
        _,recipe=await load_portrait_resource(model,base_precision)
        return io.NodeOutput(recipe)


NODE_CLASS_MAPPINGS={'FantasyPortraitModelLoader':FantasyPortraitModelLoader}
