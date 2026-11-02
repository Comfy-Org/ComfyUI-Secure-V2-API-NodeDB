"""Guest-side stand-ins for the two comfy.model_management helpers this pack uses.

A Secure Nodes V2 guest cannot import comfy.model_management. Upstream's call
sites (`get_torch_device()`, `soft_empty_cache()`) stay unchanged and import
these instead. This is a pack-local helper, not a stub of the host module.
"""

import torch


def get_torch_device():
    # Upstream uses ComfyUI's torch device. A guest has no ComfyUI device manager:
    # use this guest process's CUDA device when it has one, otherwise the CPU (the
    # same choice as whiterabbit v2/_secure_nodes.py:280). With CUDA this matches
    # comfy.model_management.get_torch_device(), torch.device(torch.cuda.current_device()).
    if torch.cuda.is_available():
        return torch.device(torch.cuda.current_device())
    return torch.device("cpu")


def soft_empty_cache(force=False):
    # comfy.model_management.soft_empty_cache only releases cached accelerator memory;
    # it never changes a result.
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()
