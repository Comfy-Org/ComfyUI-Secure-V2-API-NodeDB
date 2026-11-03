"""Secure Nodes V2 entrypoint for comfyui-reservedvram (pin cd9f1911).

The node lives in nodes.py. The original imports comfy.model_management and tries pynvml at import time (pristine
nodes.py:1-22); neither is available to a sandboxed pack, so v2 uses the public SDK instead. See SECURE_CONVERSION.md.
"""

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
