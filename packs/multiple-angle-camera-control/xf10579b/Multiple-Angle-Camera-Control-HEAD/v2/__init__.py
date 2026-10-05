"""Secure Nodes V2 conversion of Multiple Angle Camera Control."""

from .nodes import (
    CameraControlPromptNode,
    MultipleAngleCameraControlExtension,
    NODE_CLASS_MAPPINGS,
    RelightingPromptNode,
    comfy_entrypoint,
)


NODE_DISPLAY_NAME_MAPPINGS = {
    "CameraControlPromptNode": "Camera Control Prompt Generator",
    "RelightingPromptNode": "Relighting Prompt Generator",
}

__all__ = [
    "CameraControlPromptNode",
    "MultipleAngleCameraControlExtension",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "RelightingPromptNode",
    "comfy_entrypoint",
]
