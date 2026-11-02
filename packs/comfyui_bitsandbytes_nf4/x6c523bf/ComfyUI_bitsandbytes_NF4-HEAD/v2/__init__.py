"""Secure Nodes V2 entrypoint for ComfyUI_bitsandbytes_NF4 (pin 6c523bf1).

The node lives in nodes.py. The Forge-derived bitsandbytes 4-bit operations
in the pristine __init__.py are not carried into v2: they only work as
operations inside the host's model loader. See SECURE_CONVERSION.md.
"""

from .nodes import NODE_CLASS_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS"]
