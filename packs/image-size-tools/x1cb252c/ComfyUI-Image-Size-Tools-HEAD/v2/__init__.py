"""
ComfyUI Image Size Tool

A node pack providing resolution calculators for AI image generation models.
Simple, bulletproof, zero-dependency architecture.
"""

from .image_size_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

# Export for ComfyUI
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
# Public V2 extension entrypoint; the original mappings above remain exported.
from .image_size_nodes import comfy_entrypoint
