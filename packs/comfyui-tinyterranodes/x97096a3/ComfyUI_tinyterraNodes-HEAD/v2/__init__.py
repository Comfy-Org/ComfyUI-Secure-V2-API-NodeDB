"""Secure Nodes V2 registration for the complete tinyterra source census."""
from comfy_api.latest import ComfyExtension
from ._nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
WEB_DIRECTORY = './web'
ASSET_DIRECTORIES = {'tinyterra': '.'}
class TinyTerraExtension(ComfyExtension):
    async def get_node_list(self):return list(NODE_CLASS_MAPPINGS.values())
async def comfy_entrypoint():return TinyTerraExtension()
__all__=['comfy_entrypoint','NODE_CLASS_MAPPINGS','NODE_DISPLAY_NAME_MAPPINGS']
