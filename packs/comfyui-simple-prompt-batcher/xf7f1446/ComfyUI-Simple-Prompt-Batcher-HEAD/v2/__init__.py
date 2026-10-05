"""Secure Nodes V2 conversion of ComfyUI Simple Prompt Batcher."""

from .nodes import (
    NODE_CLASS_MAPPINGS,
    SimplePromptBatcher,
    SimplePromptBatcherExtension,
    comfy_entrypoint,
)


NODE_DISPLAY_NAME_MAPPINGS = {
    "SimplePromptBatcher": "📝 Simple Prompt Batcher",
}

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "SimplePromptBatcher",
    "SimplePromptBatcherExtension",
    "comfy_entrypoint",
]
