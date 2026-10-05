"""Secure Nodes V2 conversion of comfyui-image-blender."""

from .nodes import (
    ImageBlender,
    ImageBlenderExtension,
    NODE_CLASS_MAPPINGS,
    comfy_entrypoint,
)


NODE_DISPLAY_NAME_MAPPINGS = {"ImageBlender": "ImageBlender"}

__all__ = [
    "ImageBlender",
    "ImageBlenderExtension",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "comfy_entrypoint",
]
