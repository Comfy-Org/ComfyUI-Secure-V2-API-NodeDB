"""Lazy links for future reviewed advanced execution slices.

The first trained T2V boundary rejects these features before entering the
sampler. They must never be replaced by a substitute model or silent no-op.
"""


def apply_lora(*args, **kwargs):
    from ..wan_workflow_lora_runtime import apply_lora as execute
    return execute(*args, **kwargs)


def set_lora_params_gguf(*args, **kwargs):
    from .gguf.gguf import set_lora_params_gguf as execute
    return execute(*args, **kwargs)


def multitalk_loop(*args, **kwargs):
    from .multitalk.multitalk_loop import multitalk_loop as execute
    return execute(*args, **kwargs)
