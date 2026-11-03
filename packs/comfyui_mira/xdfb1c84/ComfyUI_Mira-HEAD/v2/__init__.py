"""ComfyUI_Mira, Secure Nodes V2 (pin dfb1c847, version 0.6.0.1).

The original __init__ imports every module, and several reach cv2, onnxruntime, comfy, folder_paths, requests or
piexif at import (Util.py, Tagger.py, Lora.py, Mask.py, image_saver/). This entry imports none of them: it registers
the converted node types (_secure_used.py) and every other node with its original schema and a named refusal
(_secure_unconverted.py). The original modules stay in v2/ unchanged; v2 imports only those that need nothing but
comfy_api (Arithmetic.py, Numeral.py, Text.py, v3schema.py).
"""
from comfy_api.latest import ComfyExtension

from ._frozen_schema import schema_for
from ._secure_unconverted import NODE_CLASS_MAPPINGS as _UNCONVERTED
from ._secure_used import NODE_CLASS_MAPPINGS as _USED

NODE_CLASS_MAPPINGS = {**_UNCONVERTED, **_USED}
NODE_DISPLAY_NAME_MAPPINGS = {node_id: schema_for(node_id).display_name for node_id in NODE_CLASS_MAPPINGS}


class MiraSecureExtension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint():
    return MiraSecureExtension()


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "comfy_entrypoint"]
