from comfy_api.latest import ComfyExtension
from ._v2_nodes import ConvertNumbersNode,ConvertNumbersToWordsNode
NODE_CLASS_MAPPINGS={'ConvertNumbersNode':ConvertNumbersNode,'ConvertNumbersToWords':ConvertNumbersToWordsNode}
NODE_DISPLAY_NAME_MAPPINGS={'ConvertNumbersNode': '数字归一化😄', 'ConvertNumbersToWords': 'Convert Numbers to Words'}
class PackExtension(ComfyExtension):
    async def get_node_list(self):return list(NODE_CLASS_MAPPINGS.values())
async def comfy_entrypoint():return PackExtension()
