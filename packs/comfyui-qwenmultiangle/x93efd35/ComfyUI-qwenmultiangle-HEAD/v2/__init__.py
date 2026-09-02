"""Secure registration for ComfyUI-qwenmultiangle."""

from .nodes import (
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
    QwenMultiangleCameraNode,
    QwenMultiangleCameraTranslateNode,
    QwenMultiangleExtension,
    comfy_entrypoint,
)


WEB_DIRECTORY = "./js"


__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "QwenMultiangleCameraNode",
    "QwenMultiangleCameraTranslateNode",
    "QwenMultiangleExtension",
    "WEB_DIRECTORY",
    "comfy_entrypoint",
]
