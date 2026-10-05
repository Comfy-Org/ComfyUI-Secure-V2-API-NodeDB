"""Secure Nodes V2 conversion of ComfyUI Display Value."""

from .nodes import (
    DisplayValue,
    DisplayValueExtension,
    NODE_CLASS_MAPPINGS,
    comfy_entrypoint,
)


NODE_DISPLAY_NAME_MAPPINGS = {"DisplayValue": "Display Value"}
WEB_DIRECTORY = "web"

__all__ = [
    "DisplayValue",
    "DisplayValueExtension",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
    "comfy_entrypoint",
]
