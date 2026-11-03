"""Guest-side stand-ins for the ComfyUI core symbols that the vendored RES4LYF loop references.

The secure guest cannot import ComfyUI core. The vendored modules in ``res4lyf_core`` had their
``comfy`` imports rewritten to this package (see ``res4lyf_core/VENDOR.json``).
- Arithmetic the loop actually performs in the reduced envelope is an exact copy of core.
- Everything else raises ``OutOfEnvelope`` with a node-prefixed message, so a refused path fails
  closed instead of being approximated.
"""
from . import k_diffusion, ldm, model_patcher, model_sampling, nested_tensor, samplers, supported_models, utils

__all__ = [
    "k_diffusion", "ldm", "model_patcher", "model_sampling", "nested_tensor", "samplers",
    "supported_models", "utils",
]
