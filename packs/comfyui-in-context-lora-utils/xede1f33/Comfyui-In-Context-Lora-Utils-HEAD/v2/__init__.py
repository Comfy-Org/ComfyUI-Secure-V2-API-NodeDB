"""Secure Nodes V2 conversion of Comfyui-In-Context-Lora-Utils."""

from comfy_api.latest import ComfyExtension, io

from .nodes import (
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
    AddMaskForICLora,
    AutoPatch,
    ConcatContextWindow,
    CreateContextWindow,
)


class InContextLoraUtilsExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [
            AddMaskForICLora,
            CreateContextWindow,
            ConcatContextWindow,
            AutoPatch,
        ]


async def comfy_entrypoint() -> InContextLoraUtilsExtension:
    return InContextLoraUtilsExtension()


__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "AddMaskForICLora",
    "AutoPatch",
    "ConcatContextWindow",
    "CreateContextWindow",
    "InContextLoraUtilsExtension",
    "comfy_entrypoint",
]
