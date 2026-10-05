"""Secure V2 entry point for ComfyUI-Krea2TextEncoder."""

from .nodes import (
    Krea2SystemPrompt,
    Krea2TextEncoderExtension,
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
    TextEncodeKrea2,
    comfy_entrypoint,
)

WEB_DIRECTORY = "./web"

__all__ = [
    "Krea2SystemPrompt",
    "Krea2TextEncoderExtension",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "TextEncodeKrea2",
    "WEB_DIRECTORY",
    "comfy_entrypoint",
]
