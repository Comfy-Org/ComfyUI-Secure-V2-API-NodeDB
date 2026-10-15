"""Explicit CPU policy and the original Wan CLIP SDPA branch.

CLIP SelfAttention always selects sdpa. This retains the original branch,
including its omission of dropout_p and causal from the Torch SDPA call.
No Comfy host module or model object is imported into the pack.
"""
import torch


def autocast_device(device):
    if not isinstance(device, torch.device) or device.type != 'cpu':
        raise ValueError('This Wan CLIP resource is qualified for the CPU tier only')
    return device.type


def attention(q, k, v, dropout_p=0., causal=False, attention_mode='sdpa', attn_mask=None):
    if attention_mode != 'sdpa':
        raise ValueError('The original Wan CLIP architecture selects sdpa')
    if not (q.dtype == k.dtype == v.dtype):
        return torch.nn.functional.scaled_dot_product_attention(q.transpose(1, 2), k.transpose(1, 2).to(q.dtype), v.transpose(1, 2).to(q.dtype), attn_mask=attn_mask).transpose(1, 2).contiguous()
    return torch.nn.functional.scaled_dot_product_attention(q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2), attn_mask=attn_mask).transpose(1, 2).contiguous()
