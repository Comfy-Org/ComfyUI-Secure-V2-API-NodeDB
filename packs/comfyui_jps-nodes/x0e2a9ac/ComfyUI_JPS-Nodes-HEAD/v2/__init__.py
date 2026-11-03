"""ComfyUI_JPS-Nodes, Secure Nodes V2 (pin 0e2a9aca02b1).

The original __init__ imports jps_nodes.py, which reaches comfy.sd, comfy.samplers, folder_paths and comfy.cli_args at
import. This entry imports none of them. It registers the converted node types (_secure_used.py) and every other
declared node with its original schema and a named refusal (_secure_unconverted.py). The original module stays in
v2/ unchanged and is never imported; the converted classes run its class bodies from _jps_upstream.py (verbatim).
"""
from comfy_api.latest import ComfyExtension

from ._frozen_schema import schema_for
from ._secure_unconverted import NODE_CLASS_MAPPINGS as _UNCONVERTED
from ._secure_used import NODE_CLASS_MAPPINGS as _USED

NODE_CLASS_MAPPINGS = {**_UNCONVERTED, **_USED}
NODE_DISPLAY_NAME_MAPPINGS = {node_id: schema_for(node_id).display_name for node_id in NODE_CLASS_MAPPINGS}


class JPSSecureExtension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint():
    return JPSSecureExtension()


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "comfy_entrypoint"]
