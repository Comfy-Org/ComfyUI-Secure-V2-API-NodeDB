from comfy_api.latest import ComfyExtension

from .api_nodes import (
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
    SimpleAspectRatio,
)


class SimpleAspectRatioExtension(ComfyExtension):
    async def get_node_list(self):
        return [SimpleAspectRatio]


async def comfy_entrypoint():
    return SimpleAspectRatioExtension()


__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "comfy_entrypoint",
]
