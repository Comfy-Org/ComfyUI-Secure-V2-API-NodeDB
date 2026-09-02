"""Secure Nodes V2 entry point for sd-dynamic-thresholding."""

from typing_extensions import override

from comfy_api.latest import ComfyExtension

from .dynthres_comfyui import (
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
    DynamicThresholdingComfyNode,
    DynamicThresholdingSimpleComfyNode,
)


class DynamicThresholdingExtension(ComfyExtension):
    @override
    async def get_node_list(self):
        return [
            DynamicThresholdingSimpleComfyNode,
            DynamicThresholdingComfyNode,
        ]


async def comfy_entrypoint():
    return DynamicThresholdingExtension()


__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "DynamicThresholdingComfyNode",
    "DynamicThresholdingExtension",
    "DynamicThresholdingSimpleComfyNode",
    "comfy_entrypoint",
]
