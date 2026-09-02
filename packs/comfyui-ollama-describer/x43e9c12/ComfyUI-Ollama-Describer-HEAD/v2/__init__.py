"""Secure Nodes V2 entrypoint for ComfyUI-Ollama-Describer."""
from __future__ import annotations

from .nodes import (
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
    OllamaDescriberExtension,
)


WEB_DIRECTORY = "./js"


async def comfy_entrypoint():
    return OllamaDescriberExtension()


__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "OllamaDescriberExtension",
    "WEB_DIRECTORY",
    "comfy_entrypoint",
]
