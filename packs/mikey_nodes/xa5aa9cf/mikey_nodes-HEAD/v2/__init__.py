"""mikey_nodes, Secure Nodes V2 (pin a5aa9cf637c4, version 1.0.5).

The original __init__ imports mikey_nodes.py, which reaches folder_paths, nodes, comfy, latent_preview, spandrel and
requests at import. This entry imports none of them. It registers the converted node types (_secure_used.py) and
every other declared node with its original schema and a named refusal (_secure_unconverted.py). The original
module is kept in v2/ unchanged for reference and is never imported; the converted code runs its classes and
helpers from _mikey_upstream.py (verbatim copies).
"""
from comfy_api.latest import ComfyExtension

from ._frozen_schema import schema_for
from ._secure_unconverted import NODE_CLASS_MAPPINGS as _UNCONVERTED
from ._secure_used import NODE_CLASS_MAPPINGS as _USED

NODE_CLASS_MAPPINGS = {**_UNCONVERTED, **_USED}
NODE_DISPLAY_NAME_MAPPINGS = {node_id: schema_for(node_id).display_name for node_id in NODE_CLASS_MAPPINGS}


class MikeySecureExtension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint():
    return MikeySecureExtension()


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "comfy_entrypoint"]
