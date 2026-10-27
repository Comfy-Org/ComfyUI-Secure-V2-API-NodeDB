from comfy_api.latest import ComfyExtension
from ._v2_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

WEB_DIRECTORY = './web'  # Upstream declares this empty/nonexistent directory; no frontend resources.

class comfyui_stringcomparenumber_Extension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())

async def comfy_entrypoint():
    return comfyui_stringcomparenumber_Extension()
