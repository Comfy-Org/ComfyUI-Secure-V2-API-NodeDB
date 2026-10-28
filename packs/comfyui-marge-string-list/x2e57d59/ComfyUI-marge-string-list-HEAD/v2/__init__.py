from comfy_api.latest import ComfyExtension
from ._v2_nodes import MargeStringList
NODE_CLASS_MAPPINGS={'MargeStringList':MargeStringList}
NODE_DISPLAY_NAME_MAPPINGS={'MargeStringList': 'Merge String List'}
class PackExtension(ComfyExtension):
    async def get_node_list(self):return list(NODE_CLASS_MAPPINGS.values())
async def comfy_entrypoint():return PackExtension()
