"""comfyui-vrgamedevgirl, Secure Nodes V2 (pin 5f2882d835bf, v9.1.1).

The original __init__ imports 59 submodules (reaching folder_paths, server, aiohttp, librosa,
torchaudio, cv2, transformers, ...) and writes placeholder text files under the output directory at
import. This entry does neither. It registers the six converted node types
(_secure_used.py), and every other declared node with its original schema and a named refusal
(_secure_unconverted.py). No original module is imported and no frontend file is served.
"""
from comfy_api.latest import ComfyExtension

from ._frozen_schema import schema_for
from ._secure_unconverted import NODE_CLASS_MAPPINGS as _UNCONVERTED
from ._secure_used import NODE_CLASS_MAPPINGS as _USED

NODE_CLASS_MAPPINGS = {**_UNCONVERTED, **_USED}
NODE_DISPLAY_NAME_MAPPINGS = {node_id: schema_for(node_id).display_name for node_id in NODE_CLASS_MAPPINGS}


class VRGDGSecureExtension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint():
    return VRGDGSecureExtension()


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "comfy_entrypoint"]
