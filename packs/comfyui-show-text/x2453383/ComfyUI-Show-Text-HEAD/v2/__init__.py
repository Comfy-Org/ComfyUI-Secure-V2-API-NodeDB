"""Secure Nodes V2 conversion of ComfyUI Show Text."""

from .nodes import ComfyUIShowText


NODE_CLASS_MAPPINGS = {"ShowText": ComfyUIShowText}
NODE_DISPLAY_NAME_MAPPINGS = {"ShowText": "Show Text"}
WEB_DIRECTORY = "web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
