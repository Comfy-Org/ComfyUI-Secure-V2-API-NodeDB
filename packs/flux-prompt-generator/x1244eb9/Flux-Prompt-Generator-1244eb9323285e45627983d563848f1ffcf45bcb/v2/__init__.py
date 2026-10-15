from comfy_api.latest import ComfyExtension
from ._secure_node import NODE_CLASS_MAPPINGS
NODE_DISPLAY_NAME_MAPPINGS={'FluxPromptGenerator':'Flux Prompt Generator'}
class FluxPromptExtension(ComfyExtension):
    async def get_node_list(self):return list(NODE_CLASS_MAPPINGS.values())
async def comfy_entrypoint():return FluxPromptExtension()
