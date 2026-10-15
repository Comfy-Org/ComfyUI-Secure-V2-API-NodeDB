"""Secure Nodes V2 conversion of ComfyUI-AutoTrimBG."""

from .nodes import (
    AutoTrimExtension,
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
    RonLayersTrimBgUltraV2,
    comfy_entrypoint,
)

__all__ = [
    "AutoTrimExtension",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "RonLayersTrimBgUltraV2",
    "comfy_entrypoint",
]
