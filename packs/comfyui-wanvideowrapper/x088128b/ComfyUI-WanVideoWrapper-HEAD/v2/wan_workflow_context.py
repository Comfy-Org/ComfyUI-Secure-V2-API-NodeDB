"""Owned Wan transport contexts; these are not Core ModelPatcher objects.

Dict/list option containers and subclasses are copied. Resources and all other
values, including tuples and tensors, retain identity. Native cycles raise.
"""
MODEL_FORMAT = 'wan-video-model-context-v1'
TEXT_FORMAT = 'wan-text-encoder-context-v1'
_EXTENDER_MEMO = {}


def clone_options(value, memo=None):
    """Match Core deepcopy_list_dict, including keys and post-traversal memo."""
    if memo is None:
        memo = {}
    identity = id(value)
    if identity in memo:
        return memo[identity]
    if isinstance(value, dict):
        result = {clone_options(key, memo): clone_options(item, memo)
                  for key, item in value.items()}
    elif isinstance(value, list):
        result = [clone_options(item, memo) for item in value]
    else:
        result = value
    memo[identity] = result
    return result


def make_model_context(resource, original_attention_mode, model_options=None):
    if not isinstance(original_attention_mode, str):
        raise TypeError('Original attention mode must be text')
    if model_options is None:
        model_options = {'transformer_options': {}}
    if type(model_options) is not dict:
        raise TypeError('Model options must be a dict')
    return {'__wan_context__': MODEL_FORMAT, 'resource': resource,
            'original_attention_mode': original_attention_mode,
            'model_options': model_options}


def _model(value):
    if type(value) is not dict or value.get('__wan_context__') != MODEL_FORMAT:
        raise TypeError('Expected owned WANVIDEOMODEL context')
    if type(value.get('model_options')) is not dict:
        raise TypeError('Model options must be a dict')
    return value


def clone_model(value):
    value = _model(value)
    result = dict(value)
    result['model_options'] = clone_options(value['model_options'])
    return result


def model_options(value):
    return _model(value)['model_options']


def transformer_options(value, create=False):
    options = model_options(value)
    if create and 'transformer_options' not in options:
        options['transformer_options'] = {}
    return options['transformer_options']


def original_attention_mode(value):
    """Read loader attention mode, never an attention_mode_override value."""
    return _model(value)['original_attention_mode']


def model_resource(value):
    """Read-only shared loader descriptor. Controls must not mutate it."""
    return _model(value)['resource']


def make_text_context(resource, name, precision='bf16',
                      load_device='offload_device', quantization='disabled'):
    if precision not in ('fp32', 'bf16'):
        raise ValueError('Unsupported public T5 precision')
    if load_device not in ('main_device', 'offload_device'):
        raise ValueError('Unsupported T5 load device')
    if quantization not in ('disabled', 'fp8_e4m3fn'):
        raise ValueError('Unsupported T5 quantization')
    return {'__wan_context__': TEXT_FORMAT, 'resource': resource, 'name': name,
            'precision': precision,
            'dtype': {'fp32': 'float32', 'bf16': 'bfloat16'}[precision],
            'load_device': load_device, 'quantization': quantization}


def literal_prompts(prompt):
    if not isinstance(prompt, str):
        raise TypeError('Prompt must be text')
    return [prompt]


async def encode_literal(t5, prompt, context, force_offload=True, device='gpu',
                         model_to_offload=None):
    """Stable child API; model materialization remains JACK's main-six work.

    Runtime implementation is deliberately a separate module, never a fallback
    encoder or a second child-owned T5. Returns the native ordered tensor list.
    """
    from .wan_workflow_text_runtime import encode_prompts
    return await encode_prompts(t5, literal_prompts(prompt), context,
                                force_offload=force_offload, device=device,
                                model_to_offload=model_to_offload)


def extender_key(original_prompt, extender_args):
    return original_prompt, str(extender_args)


def get_extended_prompt(original_prompt, extender_args):
    return _EXTENDER_MEMO.get(extender_key(original_prompt, extender_args))


def remember_extended_prompt(original_prompt, extender_args, extended_prompt):
    _EXTENDER_MEMO[extender_key(original_prompt, extender_args)] = extended_prompt
