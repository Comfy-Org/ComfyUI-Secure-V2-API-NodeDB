"""Pinned Qwen algorithms; real vendor model construction is unqualified until admitted."""


import logging
import torch
import torch.nn as nn
from .qwen.system_prompt import SYSTEM_PROMPT_MAP
log = logging.getLogger(__name__)
offload_device = torch.device("cpu")


config_3b = {'architectures': ['Qwen2ForCausalLM'], 'attention_dropout': 0.0, 'bos_token_id': 151643, 'eos_token_id': 151645, 'hidden_act': 'silu', 'hidden_size': 2048, 'initializer_range': 0.02, 'intermediate_size': 11008, 'max_position_embeddings': 32768, 'max_window_layers': 70, 'model_type': 'qwen2', 'num_attention_heads': 16, 'num_hidden_layers': 36, 'num_key_value_heads': 2, 'rms_norm_eps': 1e-06, 'rope_theta': 1000000.0, 'sliding_window': 32768, 'tie_word_embeddings': True, 'torch_dtype': 'bfloat16', 'transformers_version': '4.43.1', 'use_cache': True, 'use_sliding_window': False, 'vocab_size': 151936}


config_7b = {'architectures': ['Qwen2ForCausalLM'], 'attention_dropout': 0.0, 'bos_token_id': 151643, 'eos_token_id': 151645, 'hidden_act': 'silu', 'hidden_size': 3584, 'initializer_range': 0.02, 'intermediate_size': 18944, 'max_position_embeddings': 32768, 'max_window_layers': 28, 'model_type': 'qwen2', 'num_attention_heads': 28, 'num_hidden_layers': 28, 'num_key_value_heads': 4, 'rms_norm_eps': 1e-06, 'rope_theta': 1000000.0, 'sliding_window': 131072, 'tie_word_embeddings': False, 'torch_dtype': 'bfloat16', 'transformers_version': '4.43.1', 'use_cache': True, 'use_sliding_window': False, 'vocab_size': 152064}


def check_device_same(first_device, second_device):
    if first_device.type != second_device.type:
        return False
    if first_device.type == 'cuda' and first_device.index is None:
        first_device = torch.device('cuda', index=0)
    if second_device.type == 'cuda' and second_device.index is None:
        second_device = torch.device('cuda', index=0)
    return first_device == second_device


def set_module_tensor_to_device(module, tensor_name, device, value=None, dtype=None):
    """
    A helper function to set a given tensor (parameter of buffer) of a module on a specific device (note that doing
    `param.to(device)` creates a new tensor not linked to the parameter, which is why we need this function).

    Args:
        module (`torch.nn.Module`):
            The module in which the tensor we want to move lives.
        tensor_name (`str`):
            The full name of the parameter/buffer.
        device (`int`, `str` or `torch.device`):
            The device on which to set the tensor.
        value (`torch.Tensor`, *optional*):
            The value of the tensor (useful when going from the meta device to any other device).
        dtype (`torch.dtype`, *optional*):
            If passed along the value of the parameter will be cast to this `dtype`. Otherwise, `value` will be cast to
            the dtype of the existing parameter in the model.
    """
    if '.' in tensor_name:
        splits = tensor_name.split('.')
        for split in splits[:-1]:
            new_module = getattr(module, split)
            if new_module is None:
                raise ValueError(f'{module} has no attribute {split}.')
            module = new_module
        tensor_name = splits[-1]
    if tensor_name not in module._parameters and tensor_name not in module._buffers:
        raise ValueError(f'{module} does not have a parameter or a buffer named {tensor_name}.')
    is_buffer = tensor_name in module._buffers
    old_value = getattr(module, tensor_name)
    if old_value.device == torch.device('meta') and device not in ['meta', torch.device('meta')] and (value is None):
        raise ValueError(f'{tensor_name} is on the meta device, we need a `value` to put in on {device}.')
    param = module._parameters[tensor_name] if tensor_name in module._parameters else None
    param_cls = type(param)
    if value is not None:
        if dtype is None:
            value = value.to(old_value.dtype)
        elif not str(value.dtype).startswith(('torch.uint', 'torch.int', 'torch.bool')):
            value = value.to(dtype)
    device_quantization = None
    with torch.no_grad():
        if value is None:
            new_value = old_value.to(device)
            if dtype is not None and device in ['meta', torch.device('meta')]:
                if not str(old_value.dtype).startswith(('torch.uint', 'torch.int', 'torch.bool')):
                    new_value = new_value.to(dtype)
                if not is_buffer:
                    module._parameters[tensor_name] = param_cls(new_value, requires_grad=old_value.requires_grad)
        elif isinstance(value, torch.Tensor):
            new_value = value.to(device)
        else:
            new_value = torch.tensor(value, device=device)
        if device_quantization is not None:
            device = device_quantization
        if is_buffer:
            module._buffers[tensor_name] = new_value
        elif value is not None or not check_device_same(device, module._parameters[tensor_name].device):
            param_cls = type(module._parameters[tensor_name])
            new_value = param_cls(new_value, requires_grad=False)
            module._parameters[tensor_name] = new_value


def build_qwen_model(sd, tokenizer, model, transformer_load_device, base_dtype):
    from transformers.models.qwen2.configuration_qwen2 import Qwen2Config
    from transformers.models.qwen2.modeling_qwen2 import Qwen2ForCausalLM
    from accelerate import init_empty_weights
    hf_config = Qwen2Config(**config_3b if '3b' in model.lower() else config_7b)
    actual_vocab_size = len(tokenizer)
    if hf_config.vocab_size != actual_vocab_size:
        log.warning(f'Adjusting vocab_size from {hf_config.vocab_size} to {actual_vocab_size} to match tokenizer')
        hf_config.vocab_size = actual_vocab_size
    with init_empty_weights():
        hf_model = Qwen2ForCausalLM(hf_config)
    log.info('Using accelerate to load and assign model weights to device...')
    for name, param in hf_model.named_parameters():
        if name not in sd:
            log.warning(f'Parameter {name} not found in state dict, skipping.')
            continue
        set_module_tensor_to_device(hf_model, name, device=transformer_load_device, dtype=base_dtype, value=sd[name])
    hf_model.lm_head = nn.Linear(hf_model.config.hidden_size, hf_model.config.vocab_size, bias=False)
    if hf_config.tie_word_embeddings:
        hf_model.lm_head.weight = hf_model.get_input_embeddings().weight
    elif 'lm_head.weight' in sd:
        set_module_tensor_to_device(hf_model, 'lm_head.weight', device=transformer_load_device, dtype=base_dtype, value=sd['lm_head.weight'])
    else:
        hf_model.lm_head.weight = hf_model.get_input_embeddings().weight
    hf_model.lm_head.to(hf_model.device, dtype=base_dtype)
    return hf_model


def generate_qwen_original(qwen, prompt, device, force_offload, max_new_tokens, system_prompt=None, custom_system_prompt=None, seed=0):
    if device == 'gpu':
        device = torch.device('cpu')
    elif device == 'cpu':
        device = torch.device('cpu')
    if custom_system_prompt is None:
        sys_prompt = next((item['prompt'] for item in SYSTEM_PROMPT_MAP if item['label'] == system_prompt), '')
    else:
        sys_prompt = custom_system_prompt
    messages = [{'role': 'system', 'content': sys_prompt}, {'role': 'user', 'content': prompt}]
    text = qwen.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    model_inputs = qwen.tokenizer([text], return_tensors='pt').to(device)
    torch.manual_seed(seed)
    qwen.model.to(device)
    generated_ids = qwen.model.generate(**model_inputs, max_new_tokens=max_new_tokens, do_sample=True, temperature=0.7, top_p=0.8, top_k=20, repetition_penalty=1.05)
    if force_offload:
        qwen.model.to(offload_device)
    generated_ids = [output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)]
    response = qwen.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
    return response
