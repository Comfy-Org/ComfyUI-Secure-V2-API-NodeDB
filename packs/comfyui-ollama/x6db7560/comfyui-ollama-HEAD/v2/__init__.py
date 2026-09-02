"""Secure Nodes V2 entrypoint for comfyui-ollama."""
from __future__ import annotations

from comfy_api.latest import ComfyExtension

from .CompfyuiOllama import (
    NODE_CLASS_MAPPINGS as V2_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as V2_NODE_DISPLAY_NAME_MAPPINGS,
)
from .deprecated_nodes import (
    NODE_CLASS_MAPPINGS as DEPRECATED_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as DEPRECATED_NODE_DISPLAY_NAME_MAPPINGS,
)


NODE_CLASS_MAPPINGS = {
    **V2_NODE_CLASS_MAPPINGS,
    **DEPRECATED_NODE_CLASS_MAPPINGS,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    **V2_NODE_DISPLAY_NAME_MAPPINGS,
    **DEPRECATED_NODE_DISPLAY_NAME_MAPPINGS,
}
WEB_DIRECTORY = "./web"


class OllamaExtension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint():
    return OllamaExtension()


__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "OllamaExtension",
    "WEB_DIRECTORY",
    "comfy_entrypoint",
]
