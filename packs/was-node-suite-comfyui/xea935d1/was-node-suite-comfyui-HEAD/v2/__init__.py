"""Secure Nodes V2 entry of WAS Node Suite (WASasquatch/was-node-suite-comfyui at ea935d10).

The original's __init__.py imported WAS_Node_Suite.py, which at import writes configuration and history files into
its pack folder, runs pip, and imports host modules. V2 never imports it: every declared node id is registered from
the original's own declarations (was_v2/schemas.json), the converted ones run the original's logic through the guest
SDK, and the others refuse with a named message (SECURE_CONVERSION.md).
"""
from comfy_api.latest import ComfyExtension

from .was_v2.nodes import NODE_CLASS_MAPPINGS


class WASNodeSuiteExtension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint():
    return WASNodeSuiteExtension()


__all__ = ['NODE_CLASS_MAPPINGS', 'comfy_entrypoint']
