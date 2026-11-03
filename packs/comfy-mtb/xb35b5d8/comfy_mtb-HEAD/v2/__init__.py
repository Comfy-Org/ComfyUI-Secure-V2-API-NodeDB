"""comfy_mtb, Secure Nodes V2 (pin b35b5d8a, version 0.5.4).

The original __init__ imports every module in nodes/ (they reach Core, folder_paths, server, OpenCV, scikit-image,
onnxruntime, tensorflow, requests and more), registers server routes and static folders, and builds each id from its
class name. This entry imports none of that. It registers the converted node types (_secure_used.py) and every other
id with its original schema and a named refusal (_secure_unconverted.py), in the original's order. The original
files stay in v2/ unchanged and are never imported; the converted nodes run the original's code from
_mtb_upstream.py (verbatim copies).
"""
from comfy_api.latest import ComfyExtension

from ._frozen_schema import schema_for
from ._secure_unconverted import NODE_CLASS_MAPPINGS as _UNCONVERTED
from ._secure_unconverted import ORDER
from ._secure_used import NODE_CLASS_MAPPINGS as _USED

WEB_DIRECTORY = "./web"
_ALL = {**_UNCONVERTED, **_USED}
NODE_CLASS_MAPPINGS = {node_id: _ALL[node_id] for node_id in ORDER}
NODE_DISPLAY_NAME_MAPPINGS = {node_id: schema_for(node_id).display_name for node_id in NODE_CLASS_MAPPINGS}


class MtbSecureExtension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint():
    return MtbSecureExtension()


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY", "comfy_entrypoint"]
