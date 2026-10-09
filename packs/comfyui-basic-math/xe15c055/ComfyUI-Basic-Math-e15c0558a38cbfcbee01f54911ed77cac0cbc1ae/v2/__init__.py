from comfy_api.latest import ComfyExtension
from ._secure_nodes import NODE_CLASS_MAPPINGS, MATH_NODE_DISPLAY_NAME_MAPPINGS

NODE_DISPLAY_NAME_MAPPINGS = MATH_NODE_DISPLAY_NAME_MAPPINGS

class BasicMathExtension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())

async def comfy_entrypoint():
    return BasicMathExtension()

