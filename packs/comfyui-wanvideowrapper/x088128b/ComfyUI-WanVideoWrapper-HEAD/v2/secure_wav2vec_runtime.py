"""Original Tencent Wav2Vec2 via digest-bound public model assets.

Construction, weight placement and learned execution require separate genuine
model tests. No substitute encoder or provider is used.
"""
import json
from pathlib import Path
import re

from comfy_api.latest import sdk
from ._wan_catalogue import valid_catalogue_name
from .wan_workflow_t5_weights import set_module_tensor_to_device

FORMAT = 'wan-tencent-wav2vec-model-v1'
MAX_MODEL_BYTES = 1024**3
RECIPE_KEYS = {'format', 'name', 'bytes', 'sha256', 'base_precision', 'load_device', 'model_type'}
FEATURE_EXTRACTOR_CONFIG = {
    'do_normalize': False, 'feature_size': 1, 'padding_side': 'right',
    'padding_value': 0.0, 'return_attention_mask': False, 'sampling_rate': 16000,
}


def validate_recipe(recipe):
    if type(recipe) is not dict or set(recipe) != RECIPE_KEYS or recipe['format'] != FORMAT:
        raise ValueError('Invalid owned Tencent Wav2Vec model recipe')
    if not valid_catalogue_name(recipe['name']):
        raise ValueError('Wav2Vec requires a confined wav2vec2 catalogue name')
    if type(recipe['bytes']) is not int or not 0 < recipe['bytes'] <= MAX_MODEL_BYTES:
        raise ValueError('Wav2Vec checkpoint exceeds the bounded 1 GiB weight domain')
    if not isinstance(recipe['sha256'], str) or re.fullmatch('[0-9a-f]{64}', recipe['sha256']) is None:
        raise ValueError('Wav2Vec requires an exact model digest')
    if recipe['model_type'] != 'tencent':
        raise ValueError('Invalid Tencent Wav2Vec model discriminator')
    if recipe['base_precision'] not in ('fp32', 'bf16', 'fp16') or recipe['load_device'] not in ('main_device', 'offload_device'):
        raise ValueError('Invalid Wav2Vec precision or initial placement')
    return recipe


async def load_tencent_wav2vec(model, base_precision, load_device, *, expected=None, preserve_rng=False):
    import torch
    from accelerate import init_empty_weights
    from transformers import Wav2Vec2Config, Wav2Vec2FeatureExtractor
    from .multitalk.wav2vec2 import Wav2Vec2Model as MultiTalkWav2Vec2Model
    assets = sdk.current_context().assets
    if not valid_catalogue_name(model):
        raise ValueError('Wav2Vec requires a confined wav2vec2 catalogue name')
    asset = await assets.resolve('wav2vec2', model)
    recipe = validate_recipe({'format': FORMAT, 'name': model, 'bytes': await assets.size(asset),
        'sha256': await assets.digest(asset), 'base_precision': base_precision,
        'load_device': load_device, 'model_type': 'tencent'})
    if expected is not None and recipe != expected:
        raise ValueError('Wav2Vec resource changed since loader execution')
    base_dtype = {'bf16': torch.bfloat16, 'fp16': torch.float16, 'fp32': torch.float32}[base_precision]
    config_path = Path(__file__).parent/'multitalk/wav2vec2_config.json'
    wav2vec2_config = Wav2Vec2Config(**json.loads(config_path.read_text()))
    offload_device = torch.device('cpu')
    with torch.random.fork_rng(devices=[], enabled=preserve_rng):
        with init_empty_weights():
            wav2vec2 = MultiTalkWav2Vec2Model(wav2vec2_config).eval()
        wav2vec_feature_extractor = Wav2Vec2FeatureExtractor(**FEATURE_EXTRACTOR_CONFIG)
        sd = await assets.load_state_dict(asset)
        if await assets.digest(asset) != recipe['sha256']:
            raise ValueError('Wav2Vec resource changed while loading weights')
        for name, param in wav2vec2.named_parameters():
            key = 'wav2vec2.' + name
            if 'original0' in name:
                key = 'wav2vec2.encoder.pos_conv_embed.conv.weight_g'
            elif 'original1' in name:
                key = 'wav2vec2.encoder.pos_conv_embed.conv.weight_v'
            value = sd[key]
            set_module_tensor_to_device(wav2vec2, name, device=offload_device, dtype=base_dtype, value=value)
    return {'feature_extractor': wav2vec_feature_extractor, 'model': wav2vec2,
            'dtype': base_dtype, 'model_type': 'tencent'}, recipe


async def rebuild_wav2vec(recipe):
    validate_recipe(recipe)
    value, _ = await load_tencent_wav2vec(recipe['name'], recipe['base_precision'], recipe['load_device'],
                                        expected=recipe, preserve_rng=True)
    return value
