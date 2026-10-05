"""Secure Nodes V2 conversion of ComfyUI Better Strings."""

from .nodes import (
    BetterString,
    BetterStringsExtension,
    NODE_CLASS_MAPPINGS,
    comfy_entrypoint,
)


NODE_DISPLAY_NAME_MAPPINGS = {
    "BetterString": "Better Multiline String 💡",
}

__all__ = [
    "BetterString",
    "BetterStringsExtension",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "comfy_entrypoint",
]
