"""Owned CPU T5 resource lifecycle and original Wan prompt semantics.

The complete original T5 neural module is used. Only asset, device, cache and
model lifetime boundaries are owned here. Trained guest qualification pending.
"""
import asyncio
import gc
import logging
import re
from contextlib import asynccontextmanager
from importlib.resources import files

from .wan_workflow_context import TEXT_FORMAT, make_text_context
from .wan_workflow_resources import describe_asset, inspect_header, private_weight_file, validate_resource
from .wan_workflow_text_cache import TextEmbeddingCache

log = logging.getLogger(__name__)


def _text_recipe(t5):
    fields = {'__wan_context__', 'resource', 'name', 'precision', 'dtype', 'load_device', 'quantization'}
    if type(t5) is not dict or set(t5) != fields or t5['__wan_context__'] != TEXT_FORMAT:
        raise ValueError('Expected owned WANTEXTENCODER context')
    checked = make_text_context(t5['resource'], t5['name'], t5['precision'], t5['load_device'], t5['quantization'])
    if checked != t5 or t5['resource']['kind'] != 'text_encoders' or t5['name'] != t5['resource']['name']:
        raise ValueError('Inconsistent T5 resource context')
    validate_resource(t5['resource'])
    return t5


def _validate_t5_header(header):
    if 'token_embedding.weight' not in header and 'shared.weight' not in header:
        raise ValueError("Invalid T5 text encoder model, this node expects the 'umt5-xxl' model")
    if 'scaled_fp8' in header:
        raise ValueError('Invalid T5 text encoder model, fp8 scaled is not supported by this node')


async def load_text_context(context, model_name, precision, load_device='offload_device', quantization='disabled'):
    # Validate selections before any asset operation.
    make_text_context({}, model_name, precision, load_device, quantization)
    resource = await describe_asset(context.assets, 'text_encoders', model_name)
    header = await inspect_header(context.assets, resource)
    _validate_t5_header(header)
    if quantization == 'disabled' and any(item['dtype'] == 'F8_E4M3' for item in header.values()):
        quantization = 'fp8_e4m3fn'
    return make_text_context(resource, model_name, precision, load_device, quantization)


def _convert_huggingface_keys(state):
    if 'shared.weight' not in state:
        return state
    converted = {}
    for key, value in state.items():
        if key.startswith('encoder.block.'):
            block_num = key.split('.')[2]
            if 'layer.0.SelfAttention' in key:
                if key.endswith('.k.weight'):
                    new_key = f'blocks.{block_num}.attn.k.weight'
                elif key.endswith('.o.weight'):
                    new_key = f'blocks.{block_num}.attn.o.weight'
                elif key.endswith('.q.weight'):
                    new_key = f'blocks.{block_num}.attn.q.weight'
                elif key.endswith('.v.weight'):
                    new_key = f'blocks.{block_num}.attn.v.weight'
                elif 'relative_attention_bias' in key:
                    new_key = f'blocks.{block_num}.pos_embedding.embedding.weight'
                else:
                    new_key = key
            elif 'layer.0.layer_norm' in key:
                new_key = f'blocks.{block_num}.norm1.weight'
            elif 'layer.1.layer_norm' in key:
                new_key = f'blocks.{block_num}.norm2.weight'
            elif 'layer.1.DenseReluDense' in key:
                if 'wi_0' in key:
                    new_key = f'blocks.{block_num}.ffn.gate.0.weight'
                elif 'wi_1' in key:
                    new_key = f'blocks.{block_num}.ffn.fc1.weight'
                elif 'wo' in key:
                    new_key = f'blocks.{block_num}.ffn.fc2.weight'
                else:
                    new_key = key
            else:
                new_key = key
        elif key == 'shared.weight':
            new_key = 'token_embedding.weight'
        elif key == 'encoder.final_layer_norm.weight':
            new_key = 'norm.weight'
        else:
            new_key = key
        converted[new_key] = value
    return converted


def _selected_device(device):
    import torch
    if device not in ('gpu', 'cpu'):
        raise ValueError('Invalid original T5 execution device selection')
    # This conversion lane targets CPU policy; original main and offload devices
    # are both CPU in the frozen native reference. No CUDA capability is claimed.
    return torch.device('cpu')


@asynccontextmanager
async def _encoder(t5, context, force_offload, device):
    import torch
    from safetensors.torch import load_file
    from .wan_workflow_t5 import T5EncoderModel
    from .wan_workflow_t5_weights import set_module_tensor_to_device
    t5 = _text_recipe(t5)
    if type(force_offload) is not bool:
        raise ValueError('force_offload must be boolean')
    target = _selected_device(device)
    header = await inspect_header(context.assets, t5['resource'])
    _validate_t5_header(header)
    dtype = {'bf16': torch.bfloat16, 'fp32': torch.float32}[t5['precision']]
    encoder = None
    placed = False
    async with private_weight_file(context.assets, t5['resource']) as path:
        state = _convert_huggingface_keys(load_file(str(path), device='cpu'))
        quantization = t5['quantization']
        if quantization == 'disabled' and any(value.dtype == torch.float8_e4m3fn for value in state.values()):
            quantization = 'fp8_e4m3fn'
        try:
            encoder = T5EncoderModel(text_len=512, dtype=dtype, device=target,
                state_dict=state, tokenizer_path=str(files('wan_wrapper_t5_resources') / 'T5_tokenizer'),
                quantization=quantization)
            cast_dtype = torch.float8_e4m3fn if quantization == 'fp8_e4m3fn' else encoder.dtype
            params_to_keep = {'norm', 'pos_embedding', 'token_embedding'}
            for name, param in list(encoder.model.named_parameters()):
                dtype_to_use = dtype if any(keyword in name for keyword in params_to_keep) else cast_dtype
                set_module_tensor_to_device(encoder.model, name, device=target,
                                            dtype=dtype_to_use, value=state[name])
            placed = True
            del encoder.state_dict
            del state
            gc.collect()
            yield encoder, target
        finally:
            if encoder is not None and placed and force_offload:
                encoder.model.to(torch.device('cpu'))
            # Resource contexts reconstruct at graph boundaries. No unbounded
            # global model cache retains a 6GiB encoder during diffusion sampling.
            encoder = None
            gc.collect()


async def offload_model_for_text(model_to_offload=None, device='gpu'):
    """Original best-effort branch for CPU policy and recipe-only resources.

    Call after cache misses only. Both main/offload devices are CPU and a
    WANVIDEOMODEL descriptor owns no resident module. Reading it cannot load a
    video model. Errors remain swallowed as in the original text nodes.
    """
    if model_to_offload is not None and device == 'gpu':
        try:
            from .wan_workflow_context import model_resource
            model_resource(model_to_offload)
        except Exception:
            pass


def _encode_batch(encoder, prompts, target):
    import torch
    with torch.inference_mode(), torch.autocast(device_type=target.type, dtype=encoder.dtype,
                                               enabled=encoder.quantization != 'disabled'):
        return encoder(prompts, target)


async def encode_prompts(t5, prompts, context, force_offload=True, device='gpu',
                         model_to_offload=None):
    if type(prompts) is not list or any(not isinstance(p, str) for p in prompts):
        raise TypeError('T5 expects the ordered original prompt list')
    await offload_model_for_text(model_to_offload, device)
    async with _encoder(t5, context, force_offload, device) as (encoder, target):
        return await asyncio.to_thread(_encode_batch, encoder, prompts, target)


def parse_prompt_weights(prompt):
    pattern = r'\((.*?):([\d\.]+)\)'
    matches = re.findall(pattern, prompt)
    cleaned_prompt = prompt
    weights = {}
    for match in matches:
        text, weight = match
        orig_text = f'({text}:{weight})'
        cleaned_prompt = cleaned_prompt.replace(orig_text, text)
        weights[text] = float(weight)
    return cleaned_prompt, weights


def positive_prompts(positive_prompt):
    if '|' in positive_prompt:
        raw = [p.strip() for p in positive_prompt.split('|')]
    elif '[1]' in positive_prompt:
        segments = re.split(r'\[\d+\]', positive_prompt)
        raw = [segment.strip() for segment in segments if segment.strip()]
        assert len(raw) > 1 and len(raw) < 7, 'Input shot num must between 2~6 !'
    else:
        raw = [positive_prompt.strip()]
    parsed = [parse_prompt_weights(p) for p in raw]
    return [p for p, _ in parsed], [w for _, w in parsed]


async def encode_main(positive_prompt, negative_prompt, context, t5=None,
                      force_offload=True, model_to_offload=None,
                      use_disk_cache=False, device='gpu'):
    if not isinstance(positive_prompt, str) or not isinstance(negative_prompt, str):
        raise TypeError('Wan text prompts must be text')
    if t5 is None and not use_disk_cache:
        raise ValueError('T5 encoder is required for text encoding. Please provide a valid T5 encoder or enable disk cache.')
    echoshot = '[1]' in positive_prompt
    cache = TextEmbeddingCache(context.storage) if use_disk_cache else None
    positive = negative = None
    if cache is not None:
        positive, negative = await cache.get_pair(positive_prompt, negative_prompt)
        if positive is not None and negative is not None:
            return {'prompt_embeds': positive, 'negative_prompt_embeds': negative, 'echoshot': echoshot}
    if t5 is None:
        raise ValueError('No cached text embeds found for prompts, please provide a T5 encoder.')
    await offload_model_for_text(model_to_offload, device)
    prompts, all_weights = positive_prompts(positive_prompt)
    async with _encoder(t5, context, force_offload, device) as (encoder, target):
        if positive is None:
            positive = await asyncio.to_thread(_encode_batch, encoder, prompts, target)
            for i, weights in enumerate(all_weights):
                for text, weight in weights.items():
                    log.info('Applying weight %s to prompt: %s', weight, text)
                    if len(weights) > 0:
                        positive[i] = positive[i] * weight
        if negative is None:
            negative = await asyncio.to_thread(_encode_batch, encoder, [negative_prompt], target)
    if cache is not None:
        await cache.store_if_absent(positive_prompt, positive)
        await cache.store_if_absent(negative_prompt, negative)
    return {'prompt_embeds': positive, 'negative_prompt_embeds': negative, 'echoshot': echoshot}
