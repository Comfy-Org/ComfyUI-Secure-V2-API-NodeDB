"""Secure Nodes V2 conversion of ComfyUI Image Compare."""

from .nodes import ImageCompareNode


NODE_CLASS_MAPPINGS = {"ImageCompareNode": ImageCompareNode}
NODE_DISPLAY_NAME_MAPPINGS = {"ImageCompareNode": "Image Compare"}
WEB_DIRECTORY = "web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
