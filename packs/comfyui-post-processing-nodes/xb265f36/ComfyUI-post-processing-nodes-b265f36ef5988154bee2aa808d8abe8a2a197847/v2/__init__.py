from comfy_api.latest import ComfyExtension
from ._secure_nodes import NODE_CLASS_MAPPINGS

class PostProcessingExtension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())

async def comfy_entrypoint():
    return PostProcessingExtension()

__all__ = ["NODE_CLASS_MAPPINGS"]
