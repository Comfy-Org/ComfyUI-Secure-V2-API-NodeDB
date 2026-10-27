from comfy_api.latest import ComfyExtension
from ._v2_nodes import IVRIntToString
NODE_CLASS_MAPPINGS={'Int To String':IVRIntToString}
NODE_DISPLAY_NAME_MAPPINGS={'Int To String':'Int To String Convertor'}
class IntToStringExtension(ComfyExtension):
    async def get_node_list(self):return [IVRIntToString]
async def comfy_entrypoint():return IntToStringExtension()
