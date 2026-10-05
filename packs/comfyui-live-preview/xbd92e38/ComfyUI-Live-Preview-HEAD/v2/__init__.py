"""Secure Nodes V2 conversion of ComfyUI Live Preview."""

from .nodes import LivePreview, LivePreviewExtension, NODE_CLASS_MAPPINGS, comfy_entrypoint


NODE_DISPLAY_NAME_MAPPINGS = {"LivePreview": "Live Preview (Large)"}
WEB_DIRECTORY = "web"

__all__ = [
    "LivePreview",
    "LivePreviewExtension",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
    "comfy_entrypoint",
]
