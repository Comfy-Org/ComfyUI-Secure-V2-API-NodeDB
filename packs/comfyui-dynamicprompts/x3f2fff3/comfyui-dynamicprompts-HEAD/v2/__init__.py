"""comfyui-dynamicprompts, Secure Nodes V2 entry (pin 3f2fff32358c, version 0.2.1).

The original __init__ imports nodes/__init__.py, which imports all six node modules. A guest cannot
import magicprompt.py, because it imports transformers at module import. This entry registers all six
node ids from _secure_dp.py: four run the original classes, and two refuse by name.
"""
from comfy_api.latest import ComfyExtension

from ._secure_dp import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__version__ = "0.2.1"


class DynamicPromptsSecureExtension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint():
    return DynamicPromptsSecureExtension()


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "comfy_entrypoint"]
