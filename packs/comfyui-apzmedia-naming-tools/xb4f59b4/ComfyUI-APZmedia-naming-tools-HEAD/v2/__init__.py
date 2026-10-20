"""APZ source candidate:12implemented/2purpose gaps; not wholepack acceptance."""
from comfy_api.latest import ComfyExtension
from .naming_nodes import NODE_CLASS_MAPPINGS


class APZNamingExtension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint():
    return APZNamingExtension()
