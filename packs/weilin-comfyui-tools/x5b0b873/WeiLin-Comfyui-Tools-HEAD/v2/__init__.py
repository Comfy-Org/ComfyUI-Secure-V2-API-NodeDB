"""Secure Nodes V2 conversion of weilin9999/WeiLin-Comfyui-Tools (5b0b8730): the three prompt nodes.

Node ids, inputs, defaults and outputs are the original's. The original chose Chinese or English strings
from the host locale at import (zh_CN or not); V2 uses the English (non-zh_CN) strings. At import the
original also installed its requirements with pip, registered the js_node web directory and imported
app/server (HTTP routes for its prompt editor, a local database, a tag-image worker). None of that is
part of the V2 pack: the nodes below need only their inputs (SECURE_CONVERSION.md).
"""
from comfy_api.latest import ComfyExtension

from ._v2_nodes import WeiLinPromptUI, WeiLinPromptUIOnlyLoraStack, WeiLinPromptUIWithoutLora

# A dictionary that contains all nodes you want to export with their names
# NOTE: names should be globally unique
NODE_CLASS_MAPPINGS = {
    "WeiLinPromptUI": WeiLinPromptUI,
    "WeiLinPromptUIWithoutLora": WeiLinPromptUIWithoutLora,
    "WeiLinPromptUIOnlyLoraStack": WeiLinPromptUIOnlyLoraStack,
}

# A dictionary that contains the friendly/humanly readable titles for the nodes
NODE_DISPLAY_NAME_MAPPINGS = {
    "WeiLinPromptUI": "All-Round WeiLin Prompt Editor",
    "WeiLinPromptUIWithoutLora": "WeiLin Prompt Editor",
    "WeiLinPromptUIOnlyLoraStack": "WeiLin Lora Stack",
}


class WeiLinExtension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint():
    return WeiLinExtension()


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "comfy_entrypoint"]
