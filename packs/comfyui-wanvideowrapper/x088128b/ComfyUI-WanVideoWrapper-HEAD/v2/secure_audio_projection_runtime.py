"""Owned FantasyTalking/MultiTalk projection resources for CPU execution.

Only the small digest-bound recipe crosses the graph boundary. The exact
original architectures and private state remain in their consuming worker.
Source staging does not qualify constructors, weights or the main Wan consumer.
"""
import re

from comfy_api.latest import sdk
from ._wan_catalogue import valid_catalogue_name

FANTASY_FORMAT = 'wan-fantasytalking-model-v1'
MULTITALK_FORMAT = 'wan-multitalk-model-v1'
MAX_MODEL_BYTES = 3 * 1024**3
FANTASY_KEYS = {'format', 'name', 'bytes', 'sha256', 'base_precision'}
MULTITALK_KEYS = {'format', 'name', 'bytes', 'sha256', 'model_type'}


def _common_recipe(recipe, keys, marker):
    if type(recipe) is not dict or set(recipe) != keys or recipe['format'] != marker:
        raise ValueError('Invalid owned audio projection model recipe')
    if not valid_catalogue_name(recipe['name']):
        raise ValueError('Audio projection requires a confined diffusion_models catalogue name')
    if type(recipe['bytes']) is not int or not 0 < recipe['bytes'] <= MAX_MODEL_BYTES:
        raise ValueError('Audio projection checkpoint exceeds the bounded 3 GiB domain')
    if type(recipe['sha256']) is not str or re.fullmatch('[0-9a-f]{64}', recipe['sha256']) is None:
        raise ValueError('Audio projection requires an exact model digest')


def validate_fantasytalking_recipe(recipe):
    _common_recipe(recipe, FANTASY_KEYS, FANTASY_FORMAT)
    if recipe['base_precision'] not in ('fp32', 'bf16', 'fp16'):
        raise ValueError('Invalid FantasyTalking projection precision')
    if not recipe['name'].lower().endswith(('.safetensors', '.sft')):
        raise ValueError('The owned FantasyTalking range loader requires SafeTensors')
    return recipe


def validate_multitalk_recipe(recipe):
    _common_recipe(recipe, MULTITALK_KEYS, MULTITALK_FORMAT)
    expected = 'InfiniteTalk' if 'infinite' in recipe['name'].lower() else 'MultiTalk'
    if recipe['model_type'] != expected:
        raise ValueError('MultiTalk model discriminator differs from the original name rule')
    return recipe


async def _checkpoint(name):
    if not valid_catalogue_name(name):
        raise ValueError('Audio projection requires a confined diffusion_models catalogue name')
    assets = sdk.current_context().assets
    # Native MultiTalk lists unet_gguf too, but resolves diffusion_models only.
    # Preserve that lookup rather than silently granting a fallback folder.
    ref = await assets.resolve('diffusion_models', name)
    return assets, ref, {'name': name, 'bytes': await assets.size(ref),
                         'sha256': await assets.digest(ref)}


async def load_fantasytalking(model, base_precision, *, expected=None, preserve_rng=False):
    import torch
    from accelerate import init_empty_weights
    from accelerate.utils import set_module_tensor_to_device
    from .fantasytalking.model import FantasyTalkingAudioConditionModel
    from .secure_audio_safetensors import VerifiedAudioSafeTensors

    # Match the original precision mapping; public schema admits its three
    # normal choices. No projection state is replaced or initialized on CPU.
    base_dtype = {'fp8_e4m3fn': torch.float8_e4m3fn,
        'fp8_e4m3fn_fast': torch.float8_e4m3fn, 'bf16': torch.bfloat16,
        'fp16': torch.float16, 'fp16_fast': torch.float16, 'fp32': torch.float32}[base_precision]
    assets, ref, resource = await _checkpoint(model)
    recipe = validate_fantasytalking_recipe({'format': FANTASY_FORMAT,
        **resource, 'base_precision': base_precision})
    if expected is not None and recipe != expected:
        raise ValueError('FantasyTalking resource changed since loader execution')
    offload_device = torch.device('cpu')
    with torch.random.fork_rng(devices=[], enabled=preserve_rng):
        reader = await VerifiedAudioSafeTensors.open(assets, ref, recipe['bytes'], recipe['sha256'])
        # Preserve ALL checkpoint keys for the original main model's sd.update,
        # and materialize before the projection constructor, as in the source.
        # SafeTensors safe_open.keys() uses lexical key order.
        sd = {name: await reader.tensor(name) for name in sorted(reader.tensors)}
        await reader.verify_unchanged()
        with init_empty_weights():
            fantasytalking_proj_model = FantasyTalkingAudioConditionModel(audio_in_dim=768, audio_proj_dim=2048)
        for name, param in fantasytalking_proj_model.named_parameters():
            set_module_tensor_to_device(fantasytalking_proj_model, name, device=offload_device, dtype=base_dtype, value=sd[name])
    return {'proj_model': fantasytalking_proj_model, 'sd': sd}, recipe


async def rebuild_fantasytalking(recipe):
    validate_fantasytalking_recipe(recipe)
    value, _ = await load_fantasytalking(recipe['name'], recipe['base_precision'],
                                       expected=recipe, preserve_rng=True)
    return value


async def load_multitalk(model, base_precision=None, *, expected=None, preserve_rng=False):
    import torch
    from accelerate import init_empty_weights
    from .wan_workflow_math.multitalk.multitalk import AudioProjModel

    assets, ref, resource = await _checkpoint(model)
    recipe = validate_multitalk_recipe({'format': MULTITALK_FORMAT, **resource,
        'model_type': 'InfiniteTalk' if 'infinite' in model.lower() else 'MultiTalk'})
    if expected is not None and recipe != expected:
        raise ValueError('MultiTalk resource changed since loader execution')
    audio_window = 5
    intermediate_dim = 512
    output_dim = 768
    context_tokens = 32
    vae_scale = 4
    norm_output_audio = True
    with torch.random.fork_rng(devices=[], enabled=preserve_rng):
        with init_empty_weights():
            multitalk_proj_model = AudioProjModel(
                seq_len=audio_window, seq_len_vf=audio_window + vae_scale - 1,
                intermediate_dim=intermediate_dim, output_dim=output_dim,
                context_tokens=context_tokens, norm_output_audio=norm_output_audio)
    # This is an internal worker value, not the graph output. JACK's main
    # consumer must resolve/read this asset and preserve its original GGUF or
    # safe-load branch. A host path is deliberately not invented.
    return {'proj_model': multitalk_proj_model, 'asset': ref,
            'model_name': model, 'model_type': recipe['model_type']}, recipe


async def rebuild_multitalk(recipe):
    validate_multitalk_recipe(recipe)
    value, _ = await load_multitalk(recipe['name'], expected=recipe, preserve_rng=True)
    return value
