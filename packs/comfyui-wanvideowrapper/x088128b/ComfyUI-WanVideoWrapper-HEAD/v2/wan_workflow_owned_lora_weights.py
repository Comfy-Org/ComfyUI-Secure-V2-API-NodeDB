"""Explicit owned tensor data; not a Core adapter or patcher.

The complete pinned native LoRA loader method is preserved, including its key
precedence and mutation of the shared loaded-key set. Only its return annotation
names this owned data class. The finite executor enforces plain matrix A/B.
"""
from dataclasses import dataclass
from typing import Optional
import torch

@dataclass
class OwnedLoRAWeights:
    loaded_keys: set
    weights: tuple

    @classmethod
    def load(cls, x: str, lora: dict[str, torch.Tensor], alpha: float, dora_scale: torch.Tensor, loaded_keys: set[str]=None) -> Optional['OwnedLoRAWeights']:
        if loaded_keys is None:
            loaded_keys = set()
        reshape_name = '{}.reshape_weight'.format(x)
        regular_lora = '{}.lora_up.weight'.format(x)
        diffusers_lora = '{}_lora.up.weight'.format(x)
        diffusers2_lora = '{}.lora_B.weight'.format(x)
        diffusers3_lora = '{}.lora.up.weight'.format(x)
        mochi_lora = '{}.lora_B'.format(x)
        transformers_lora = '{}.lora_linear_layer.up.weight'.format(x)
        qwen_default_lora = '{}.lora_B.default.weight'.format(x)
        A_name = None
        if regular_lora in lora.keys():
            A_name = regular_lora
            B_name = '{}.lora_down.weight'.format(x)
            mid_name = '{}.lora_mid.weight'.format(x)
        elif diffusers_lora in lora.keys():
            A_name = diffusers_lora
            B_name = '{}_lora.down.weight'.format(x)
            mid_name = None
        elif diffusers2_lora in lora.keys():
            A_name = diffusers2_lora
            B_name = '{}.lora_A.weight'.format(x)
            mid_name = None
        elif diffusers3_lora in lora.keys():
            A_name = diffusers3_lora
            B_name = '{}.lora.down.weight'.format(x)
            mid_name = None
        elif mochi_lora in lora.keys():
            A_name = mochi_lora
            B_name = '{}.lora_A'.format(x)
            mid_name = None
        elif transformers_lora in lora.keys():
            A_name = transformers_lora
            B_name = '{}.lora_linear_layer.down.weight'.format(x)
            mid_name = None
        elif qwen_default_lora in lora.keys():
            A_name = qwen_default_lora
            B_name = '{}.lora_A.default.weight'.format(x)
            mid_name = None
        if A_name is not None:
            mid = None
            if mid_name is not None and mid_name in lora.keys():
                mid = lora[mid_name]
                loaded_keys.add(mid_name)
            reshape = None
            if reshape_name in lora.keys():
                try:
                    reshape = lora[reshape_name].tolist()
                    loaded_keys.add(reshape_name)
                except:
                    pass
            weights = (lora[A_name], lora[B_name], alpha, mid, dora_scale, reshape)
            loaded_keys.add(A_name)
            loaded_keys.add(B_name)
            return cls(loaded_keys, weights)
        else:
            return None
