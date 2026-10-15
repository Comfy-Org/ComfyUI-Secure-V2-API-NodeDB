"""Owned Whisper resource boundary; unchanged original model/config/weights.

No model substitutes are used. Source staging does not qualify construction,
checkpoint loading, feature extraction, or learned Whisper execution.
"""
import json
from pathlib import Path
import re

from comfy_api.latest import sdk
from ._wan_catalogue import valid_catalogue_name
from .wan_workflow_t5_weights import set_module_tensor_to_device

FORMAT = 'wan-whisper-model-v1'
MAX_MODEL_BYTES = 3 * 1024**3
RECIPE_KEYS = {'format', 'name', 'bytes', 'sha256', 'base_precision', 'load_device'}
FEATURE_EXTRACTOR_CONFIG = {
    'chunk_length': 30, 'feature_extractor_type': 'WhisperFeatureExtractor',
    'feature_size': 128, 'hop_length': 160, 'n_fft': 400, 'n_samples': 480000,
    'nb_max_frames': 3000, 'padding_side': 'right', 'padding_value': 0.0,
    'processor_class': 'WhisperProcessor', 'return_attention_mask': False, 'sampling_rate': 16000,
}


def validate_recipe(recipe):
    if type(recipe) is not dict or set(recipe) != RECIPE_KEYS or recipe['format'] != FORMAT:
        raise ValueError('Invalid owned Whisper model recipe')
    if not valid_catalogue_name(recipe['name']):
        raise ValueError('Whisper requires a confined audio encoder catalogue name')
    if type(recipe['bytes']) is not int or not 0 < recipe['bytes'] <= MAX_MODEL_BYTES:
        raise ValueError('Whisper checkpoint exceeds the bounded 3 GiB weight domain')
    if not isinstance(recipe['sha256'], str) or re.fullmatch('[0-9a-f]{64}', recipe['sha256']) is None:
        raise ValueError('Whisper requires an exact model digest')
    if recipe['base_precision'] not in ('fp32', 'bf16', 'fp16') or recipe['load_device'] not in ('main_device', 'offload_device'):
        raise ValueError('Invalid Whisper precision or initial placement')
    return recipe


async def load_whisper(model, base_precision, load_device, *, expected=None, preserve_rng=False):
    import torch
    from accelerate import init_empty_weights
    from transformers import WhisperConfig, WhisperModel, WhisperFeatureExtractor
    assets = sdk.current_context().assets
    if not valid_catalogue_name(model):
        raise ValueError('Whisper requires a confined audio encoder catalogue name')
    asset = await assets.resolve('audio_encoders', model)
    recipe = validate_recipe({'format': FORMAT, 'name': model, 'bytes': await assets.size(asset),
        'sha256': await assets.digest(asset), 'base_precision': base_precision, 'load_device': load_device})
    if expected is not None and recipe != expected:
        raise ValueError('Whisper resource changed since loader execution')
    base_dtype = {'bf16': torch.bfloat16, 'fp16': torch.float16, 'fp32': torch.float32}[base_precision]
    # The source's config and extractor options are preserved byte-for-byte /
    # field-for-field. The admitted compute and offload device is CPU.
    config_path = Path(__file__).parent/'HuMo/whisper_config.json'
    whisper_config = WhisperConfig(**json.loads(config_path.read_text()))
    with torch.random.fork_rng(devices=[], enabled=preserve_rng):
        with init_empty_weights():
            whisper = WhisperModel(whisper_config).eval()
            whisper.decoder = None
        feature_extractor = WhisperFeatureExtractor(**FEATURE_EXTRACTOR_CONFIG)
        from .secure_audio_safetensors import VerifiedAudioSafeTensors
        state = await VerifiedAudioSafeTensors.open(assets, asset, recipe['bytes'], recipe['sha256'])
        for name, param in whisper.named_parameters():
            value = await state.tensor('model.'+name)
            set_module_tensor_to_device(whisper, name, device=torch.device('cpu'), dtype=base_dtype, value=value)
        await state.verify_unchanged()
    return {'feature_extractor': feature_extractor, 'model': whisper, 'dtype': base_dtype}, recipe


async def rebuild_whisper(recipe):
    validate_recipe(recipe)
    value, _ = await load_whisper(recipe['name'], recipe['base_precision'], recipe['load_device'],
                                  expected=recipe, preserve_rng=True)
    return value


def loudness_norm(audio_array, sr=16000, lufs=-23):
    # Complete unchanged original function AST from multitalk/nodes.py.
    try:
        import pyloudnorm
    except Exception:
        raise ImportError('pyloudnorm package is not installed')
    meter = pyloudnorm.Meter(sr)
    loudness = meter.integrated_loudness(audio_array)
    if abs(loudness) > 100:
        return audio_array
    normalized_audio = pyloudnorm.normalize.loudness(audio_array, loudness, lufs)
    return normalized_audio
