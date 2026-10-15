"""Conversion arithmetic stays pack-side, with original dtype/order preserved."""
import torch
from .bounds import state_bounds


def quantize_to_fp8(tensor):
    if tensor.dtype != torch.bfloat16:
        raise ValueError('Input tensor must be in BF16 format.')
    tensor = tensor.to(torch.float16)
    fp8_max = 240.0
    fp8_min = -fp8_max
    clamped_tensor = tensor.clamp(min=fp8_min, max=fp8_max)
    scale = fp8_max / torch.max(torch.abs(clamped_tensor))
    quantized_tensor = torch.round(clamped_tensor * scale) / scale
    return quantized_tensor.to(torch.float8_e4m3fn)


def boost(state):
    state_bounds(state, output_itemsize=4)
    return {key: tensor.to(torch.float32) for key, tensor in state.items()}


def cut(state):
    state_bounds(state, output_itemsize=1)
    # Exact pinned CUDA policy. No CPU fallback or CPU-Cut parity assertion.
    result = {}
    for key, tensor in state.items():
        tensor = tensor.to(dtype=torch.bfloat16, device='cuda')
        result[key] = quantize_to_fp8(tensor).cpu()
    return result


def alpha_state(state):
    state_bounds(state)
    prefix = None
    for pfx in ['model.diffusion_model.', 'model.', 'net.']:
        if any([x.startswith(pfx) for x in state.keys()]):
            prefix = pfx
            break
    sd = {}
    for k, v in state.items():
        # Preserve substring membership + replace-all, NOT an startswith fix.
        if prefix and prefix not in k:
            continue
        if prefix:
            k = k.replace(prefix, '')
        sd[k] = v
    return sd
