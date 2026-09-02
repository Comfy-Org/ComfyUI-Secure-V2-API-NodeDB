"""Secure Nodes V2 entrypoint for ComfyUI-Unload-Model."""

from typing_extensions import override
from comfy_api.latest import ComfyExtension

from .unloadModel import (
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
    UnloadAllModelsNode,
    UnloadModelNode,
)


class UnloadModelExtension(ComfyExtension):
    @override
    async def get_node_list(self):
        return [UnloadModelNode, UnloadAllModelsNode]


async def comfy_entrypoint():
    return UnloadModelExtension()


__all__ = [
    'NODE_CLASS_MAPPINGS',
    'NODE_DISPLAY_NAME_MAPPINGS',
    'UnloadAllModelsNode',
    'UnloadModelNode',
    'UnloadModelExtension',
    'comfy_entrypoint',
]
