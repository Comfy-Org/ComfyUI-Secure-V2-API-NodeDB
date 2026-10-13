from comfy_api.latest import ComfyExtension
from .entry import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

class JSONHelperExtension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())

async def comfy_entrypoint():
    return JSONHelperExtension()

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'comfy_entrypoint']
