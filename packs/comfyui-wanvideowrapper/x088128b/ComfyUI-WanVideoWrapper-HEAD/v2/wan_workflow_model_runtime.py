"""Digest-bound plain Wan2.1 1.3B CPU resource lifecycle.

This first workflow domain is explicit. Advanced model resources and alternate
backends require their own implementations and qualification before admission.
"""
from contextlib import AsyncExitStack, asynccontextmanager
import gc

from .wan_workflow_context import make_model_context, model_options, model_resource
from .wan_workflow_resources import describe_asset, inspect_header, private_weight_file

MODEL_RESOURCE_FORMAT = 'wan-video-model-loader-resource-v1'
PLAIN_13B_SHA256 = 'bcb3c10ad5bbb03e597ebbf3ec1d1ce3e76180df99d4d11e1cc933ff92c066d5'


async def load_model_context(context, model, base_precision, load_device, quantization,
                             compile_args=None, attention_mode='sdpa', block_swap_args=None,
                             lora=None, vram_management_args=None, extra_model=None,
                             fantasytalking_model=None, multitalk_model=None,
                             fantasyportrait_model=None, rms_norm_function='default'):
    assert not (vram_management_args is not None and block_swap_args is not None), "Can't use both block_swap_args and vram_management_args at the same time"
    if base_precision != 'bf16' or quantization != 'disabled' or attention_mode != 'sdpa' or rms_norm_function != 'default':
        raise NotImplementedError('This staged trained workflow admits bf16, unquantized, SDPA and original RMSNorm only')
    if load_device not in ('main_device', 'offload_device'):
        raise ValueError('Invalid original model load device')
    if any(value is not None for value in (compile_args, lora, vram_management_args,
            extra_model, fantasyportrait_model)):
        raise NotImplementedError('Advanced model resources are outside the first staged T2V workflow domain')
    if block_swap_args is not None:
        raise NotImplementedError('Block swap execution requires separate CPU policy qualification')
    from .wan_workflow_audio_projection_consumer import projection_recipes
    audio_recipes = projection_recipes(fantasytalking_model, multitalk_model)
    weights = await describe_asset(context.assets, 'diffusion_models', model)
    if weights['sha256'] != PLAIN_13B_SHA256:
        raise NotImplementedError('First staged workflow is bound to the approved trained Wan2.1 1.3B resource')
    header = await inspect_header(context.assets, weights)
    if header['patch_embedding.weight']['shape'] != [1536, 16, 1, 2, 2]:
        raise ValueError('Trained diffusion resource architecture changed')
    resource = {'format': MODEL_RESOURCE_FORMAT, 'weights': weights,
                'model_name': model, 'base_precision': base_precision,
                'load_device': load_device, 'quantization': quantization,
                'rms_norm_function': rms_norm_function}
    options = {'transformer_options': {'block_swap_args': block_swap_args, 'merge_loras': False}}
    if audio_recipes is not None:
        # Pure metadata in the extensible options container. Keep the shared
        # read-only resource descriptor and context rev4 fields unchanged.
        options['audio_projection_recipes'] = audio_recipes
    return make_model_context(resource, attention_mode, options)


def load_plain_weights(transformer, state, base_dtype):
    """Original non-GGUF/no-block-swap parameter placement and dtype rules."""
    import torch
    from .wan_workflow_t5_weights import set_module_tensor_to_device
    params_to_keep = {'time_in', 'patch_embedding', 'time_', 'modulation', 'text_embedding',
                     'adapter', 'add', 'ref_conv', 'casual_audio_encoder', 'cond_encoder',
                     'frame_packer', 'audio_proj_glob', 'face_encoder', 'fuser_block'}
    weight_dtype = base_dtype
    for name, param in transformer.named_parameters():
        if 'loras' in name or 'uni3c' in name:
            continue
        key = name.replace('_orig_mod.', '')
        value = state[key]
        dtype_to_use = base_dtype if any(keyword in name for keyword in params_to_keep) else weight_dtype
        dtype_to_use = weight_dtype if value.dtype == weight_dtype else dtype_to_use
        scale_key = key.replace('.weight', '.scale_weight')
        if scale_key in state:
            dtype_to_use = value.dtype
        if 'bias' in name or 'img_emb' in name:
            dtype_to_use = base_dtype
        if any(k in name for k in ('patch_embedding', 'motion_encoder', 'condition_embedding')):
            dtype_to_use = torch.float32
        if 'modulation' in name or 'norm' in name:
            dtype_to_use = value.dtype if value.dtype == torch.float32 else base_dtype
        set_module_tensor_to_device(transformer, name, device=torch.device('cpu'),
                                    dtype=dtype_to_use, value=value)


@asynccontextmanager
async def materialize_model(model, context):
    import torch
    from accelerate import init_empty_weights
    from safetensors.torch import load_file
    from .wan_workflow_math.wanvideo.modules.model import WanModel
    from .wan_workflow_model_config import configuration_13b
    resource = model_resource(model)
    fields = {'format', 'weights', 'model_name', 'base_precision', 'load_device',
              'quantization', 'rms_norm_function'}
    if type(resource) is not dict or set(resource) != fields or resource['format'] != MODEL_RESOURCE_FORMAT:
        raise ValueError('Invalid owned diffusion loader resource')
    if resource['weights']['sha256'] != PLAIN_13B_SHA256 or resource['base_precision'] != 'bf16' or resource['quantization'] != 'disabled' or resource['rms_norm_function'] != 'default':
        raise ValueError('Diffusion resource is outside the staged trained domain')
    options = model_options(model)
    transformer_options = options.get('transformer_options')
    if type(transformer_options) is not dict:
        raise ValueError('Diffusion resource requires transformer_options')
    if options.get('lora_resource_plan') is not None or transformer_options.get('controlnet') is not None:
        raise NotImplementedError('Owned control/LoRA recipes require the explicit consumer lifecycle; the plain route cannot ignore them')
    if transformer_options.get('block_swap_args') is not None or transformer_options.get('merge_loras'):
        raise NotImplementedError('Advanced parameter residency/LoRA execution is not admitted in the first staged workflow')
    from .wan_workflow_audio_projection_consumer import (
        validate_projection_recipes, apply_audio_projection_state,
    )
    audio_recipes = validate_projection_recipes(options.get('audio_projection_recipes'))
    header = await inspect_header(context.assets, resource['weights'])
    if header['patch_embedding.weight']['shape'] != [1536, 16, 1, 2, 2]:
        raise ValueError('Unexpected trained diffusion architecture')
    async with AsyncExitStack() as lifetime:
        path = await lifetime.enter_async_context(private_weight_file(context.assets, resource['weights']))
        state = load_file(str(path), device='cpu')
        transformer = None
        try:
            configuration = configuration_13b(state)
            with init_empty_weights():
                transformer = WanModel(**configuration).eval()
            if audio_recipes is not None:
                state = await apply_audio_projection_state(context, transformer, state,
                    audio_recipes, dim=configuration['dim'], num_heads=configuration['num_heads'],
                    attention_mode=configuration['attention_mode'],
                    transformer_load_device=torch.device('cpu'), gguf=False,
                    gguf_reader=None, lifetime=lifetime)
                state = {k.replace('.weight_scale', '.scale_weight'): v for k, v in state.items()}
            load_plain_weights(transformer, state, torch.bfloat16)
            del state
            gc.collect()
            yield transformer, transformer_options
        finally:
            transformer = None
            gc.collect()
