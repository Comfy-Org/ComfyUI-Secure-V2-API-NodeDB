from comfy_api.latest import ComfyExtension
from ._v2_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

class comfyui_zfl_json_extractor_Extension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())

async def comfy_entrypoint():
    return comfyui_zfl_json_extractor_Extension()
