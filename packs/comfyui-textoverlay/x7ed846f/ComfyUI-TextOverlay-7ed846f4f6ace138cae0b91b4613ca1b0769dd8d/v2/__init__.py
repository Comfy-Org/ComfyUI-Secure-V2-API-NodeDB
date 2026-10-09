from comfy_api.latest import ComfyExtension
from ._secure_nodes import NODE_CLASS_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS"]

class TextOverlayExtension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())

async def comfy_entrypoint():
    return TextOverlayExtension()
