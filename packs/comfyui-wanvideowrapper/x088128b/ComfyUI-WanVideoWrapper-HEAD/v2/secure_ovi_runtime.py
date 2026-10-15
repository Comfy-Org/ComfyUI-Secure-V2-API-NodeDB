"""Owned two-checkpoint Ovi resource; CPU and trained qualification pending."""
from comfy_api.latest import sdk
from ._owned_ovi.weights import describe_resource, validate_resource

FORMAT = 'wan-ovi-mmaudio-vae-v1'
KEYS = {'format', 'vae', 'vocoder', 'precision'}
MAX_TOTAL_WEIGHT_BYTES = 3 * 1024**3


def validate_recipe(recipe):
    if type(recipe) is not dict or set(recipe) != KEYS or recipe['format'] != FORMAT:
        raise ValueError('Invalid owned Ovi VAE recipe')
    validate_resource(recipe['vae'])
    validate_resource(recipe['vocoder'])
    if recipe['precision'] not in ('bf16', 'fp16', 'fp32'):
        raise ValueError('Invalid Ovi precision')
    if recipe['vae']['bytes'] + recipe['vocoder']['bytes'] > MAX_TOTAL_WEIGHT_BYTES:
        raise ValueError('Ovi checkpoints exceed the bounded total 3 GiB weight domain')
    return recipe


async def _materialize(recipe, *, preserve_rng):
    import torch
    from ._owned_ovi.features import FeaturesUtils

    validate_recipe(recipe)
    dtype = {'bf16': torch.bfloat16, 'fp16': torch.float16, 'fp32': torch.float32}[recipe['precision']]
    with torch.random.fork_rng(devices=[], enabled=preserve_rng):
        vae = await FeaturesUtils.create(
            tod_vae_ckpt=recipe['vae'], bigvgan_vocoder_ckpt=recipe['vocoder'],
            mode='16k', need_vae_encoder=True)
        vae.to(device=torch.device('cpu'), dtype=dtype)
        vae.eval()
    return vae


async def load_ovi(vae, vocoder, precision):
    # Preserve the original vae-over-mmaudio name precedence. Both original
    # folders must be operator-admitted; a missing mmaudio catalogue is not
    # silently substituted with another folder.
    assets = sdk.current_context().assets
    vae_files = await assets.list('vae')
    recipe = validate_recipe({'format': FORMAT, 'precision': precision,
        'vae': await describe_resource('vae' if vae in vae_files else 'mmaudio', vae),
        'vocoder': await describe_resource('vae' if vocoder in vae_files else 'mmaudio', vocoder)})
    value = await _materialize(recipe, preserve_rng=False)
    return value, recipe


async def rebuild_ovi(recipe):
    return await _materialize(recipe, preserve_rng=True)


def soft_empty_cache():
    """The exact original Core soft_empty_cache CPU-mode branch returns None."""
    return None
