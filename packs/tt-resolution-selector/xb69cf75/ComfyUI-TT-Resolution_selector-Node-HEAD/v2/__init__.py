from comfy_api.latest import ComfyExtension
from ._v2_nodes import TTResolutionSelector

NODE_CLASS_MAPPINGS = {"TTResolutionSelector": TTResolutionSelector}
NODE_DISPLAY_NAME_MAPPINGS = {"TTResolutionSelector": "TT分辨率选择器"}


class TTResolutionExtension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint():
    return TTResolutionExtension()
