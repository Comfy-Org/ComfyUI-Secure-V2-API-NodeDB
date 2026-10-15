"""Public asset recipes for the original Qwen model; trained qualification pending."""
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace
from comfy_api.latest import sdk
from ._wan_catalogue import valid_catalogue_name
from .qwen.system_prompt import SYSTEM_PROMPT_MAP

FORMAT = 'wan-qwen-model-recipe-v1'
RECIPE_KEYS = {'format', 'model_name', 'weights_sha256', 'precision', 'load_device', 'tokenizer_bundle_sha256'}
PRECISIONS = ('fp8_e4m3fn', 'fp8_e4m3fn_fast', 'bf16', 'fp16', 'fp16_fast', 'fp32')
MAX_WEIGHT_BYTES = 16*1024**3
MAX_TEXT_BYTES = 65536
MAX_INPUT_TOKENS = 8192


def tokenizer_bindings():
    return json.loads((Path(__file__).parent/'secure_qwen_tokenizer_bindings.json').read_text())


def load_qwen_tokenizer():
    """Exact bundled data with a fixed installed tokenizer and no remote code."""
    from transformers import AutoTokenizer
    bindings = tokenizer_bindings()
    root = Path(__file__).parent/'qwen/tokenizer'
    assert set(bindings['files']) == {'merges.txt', 'vocab.json', 'tokenizer.json', 'tokenizer_config.json'}
    for name, row in bindings['files'].items():
        path = root/name
        if path.stat().st_size != row['bytes'] or path.stat().st_size > 8*1024**2:
            raise ValueError('Bundled original Qwen tokenizer size changed')
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Bundled original Qwen tokenizer bytes changed')
    config = json.loads((root/'tokenizer_config.json').read_text())
    if config.get('tokenizer_class') != 'Qwen2Tokenizer' or 'auto_map' in config:
        raise ValueError('Qwen requires its fixed installed tokenizer implementation')
    return AutoTokenizer.from_pretrained(str(root), trust_remote_code=False, local_files_only=True)


def validate_qwen_recipe(recipe):
    if (not isinstance(recipe, dict) or set(recipe) != RECIPE_KEYS or recipe['format'] != FORMAT
            or not valid_catalogue_name(recipe['model_name'])
            or recipe['precision'] not in PRECISIONS
            or not isinstance(recipe['load_device'], str) or len(recipe['load_device']) > 32
            or not isinstance(recipe['weights_sha256'], str)
            or re.fullmatch('[0-9a-f]{64}', recipe['weights_sha256']) is None
            or recipe['tokenizer_bundle_sha256'] != tokenizer_bindings()['bundle_sha256']):
        raise ValueError('Invalid digest-bound original Qwen recipe')


async def _materialize_qwen(model, load_device, precision, *, expected_sha256=None, preserve_rng=False, tokenizer=None):
    import torch
    if (not valid_catalogue_name(model) or not model.lower().endswith(('.safetensors', '.sft'))
            or precision not in PRECISIONS or not isinstance(load_device, str) or len(load_device) > 32):
        raise ValueError('Qwen requires a confined safetensors resource and original precision')
    assets = sdk.current_context().assets
    asset = await assets.resolve('text_encoders', model)
    size = await assets.size(asset)
    if not 0 < size <= MAX_WEIGHT_BYTES:
        raise ValueError('Original Qwen resource exceeds the 16 GiB source domain')
    digest = await assets.digest(asset)
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError('Qwen checkpoint changed after recipe creation')
    state = await assets.load_state_dict(asset)
    if await assets.digest(asset) != digest:
        raise ValueError('Qwen checkpoint changed during public asset loading')
    if tokenizer is None:
        tokenizer = load_qwen_tokenizer()
    from .secure_qwen_math import build_qwen_model
    dtype = {'fp8_e4m3fn': torch.float8_e4m3fn, 'fp8_e4m3fn_fast': torch.float8_e4m3fn,
             'bf16': torch.bfloat16, 'fp16': torch.float16, 'fp16_fast': torch.float16,
             'fp32': torch.float32}[precision]
    # On this raw CPU tier main/offload coincide. Retain the original string,
    # including Cached's direct 'cpu' argument, in the recipe.
    selected = torch.device('cpu')
    with torch.random.fork_rng(devices=[], enabled=preserve_rng):
        instance = build_qwen_model(state, tokenizer, model, selected, dtype)
    del state
    recipe = {'format': FORMAT, 'model_name': model, 'weights_sha256': digest,
              'precision': precision, 'load_device': load_device,
              'tokenizer_bundle_sha256': tokenizer_bindings()['bundle_sha256']}
    return SimpleNamespace(model=instance, tokenizer=tokenizer), recipe


async def load_qwen_resource(model, load_device, precision):
    resource, recipe = await _materialize_qwen(model, load_device, precision)
    del resource
    return recipe


def preflight_qwen_text(tokenizer, prompt, system_prompt, custom_system_prompt, max_new_tokens):
    if not isinstance(prompt, str) or custom_system_prompt is not None and not isinstance(custom_system_prompt, str):
        raise ValueError('Qwen prompt inputs must be text')
    if type(max_new_tokens) is not int or not 1 <= max_new_tokens <= 2048:
        raise ValueError('Qwen generated token count must be 1..2048')
    selected = (next((item['prompt'] for item in SYSTEM_PROMPT_MAP if item['label'] == system_prompt), '')
                if custom_system_prompt is None else custom_system_prompt)
    if len(prompt.encode('utf-8')) + len(selected.encode('utf-8')) > MAX_TEXT_BYTES:
        raise ValueError('Qwen prompt and system text exceed 64 KiB')
    text = tokenizer.apply_chat_template([{'role': 'system', 'content': selected},
                                         {'role': 'user', 'content': prompt}],
                                        tokenize=False, add_generation_prompt=True)
    values = tokenizer([text], return_tensors='pt')
    if values.input_ids.shape != (1, values.input_ids.shape[-1]) or values.input_ids.shape[-1] > MAX_INPUT_TOKENS:
        raise ValueError('Qwen input exceeds the bounded 8192-token CPU domain')
    return text


async def extend_qwen_prompt(qwen, prompt, device, force_offload, max_new_tokens,
                             system_prompt=None, custom_system_prompt=None, seed=0):
    validate_qwen_recipe(qwen)
    if device not in ('gpu', 'cpu') or type(force_offload) is not bool:
        raise ValueError('Invalid Qwen device/offload setting')
    if type(seed) is not int or not 0 <= seed <= 0xffffffffffffffff:
        raise ValueError('Qwen seed must be an unsigned 64-bit integer')
    tokenizer = load_qwen_tokenizer()
    preflight_qwen_text(tokenizer, prompt, system_prompt, custom_system_prompt, max_new_tokens)
    instance, _ = await _materialize_qwen(qwen['model_name'], qwen['load_device'], qwen['precision'],
        expected_sha256=qwen['weights_sha256'], preserve_rng=True, tokenizer=tokenizer)
    from .secure_qwen_math import generate_qwen_original
    return generate_qwen_original(instance, prompt, device, force_offload, max_new_tokens,
                                  system_prompt, custom_system_prompt, seed)
