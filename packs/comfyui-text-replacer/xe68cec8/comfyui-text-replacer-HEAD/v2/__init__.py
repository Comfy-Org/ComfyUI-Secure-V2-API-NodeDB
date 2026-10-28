from comfy_api.latest import ComfyExtension
from .text_replacer import WordReplacer

NODE_CLASS_MAPPINGS = {'WordReplacer': WordReplacer}
NODE_DISPLAY_NAME_MAPPINGS = {'WordReplacer': 'Word Replacer (Validated)'}


class WordReplacerExtension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint():
    return WordReplacerExtension()
