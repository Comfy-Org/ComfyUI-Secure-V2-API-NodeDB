"""Secure Nodes V2 entrypoint for the pinned cg-image-filter snapshot."""
from __future__ import annotations

from comfy_api.latest import ComfyExtension, io

from .image_filter_nodes import ImageFilter, MaskImageFilter, TextImageFilter
from .utility_nodes.list_utility_nodes import (
    BatchFromImageList,
    ImageListFromBatch,
    PickFromList,
)
from .utility_nodes.mask_utility_nodes import MaskedSection
from .utility_nodes.string_utility_nodes import (
    AnyListToString,
    SplitByCommas,
    StringToFloat,
    StringToInt,
    StringToStringList,
)


VERSION = "1.9"
WEB_DIRECTORY = "./js"

NODE_CLASS_MAPPINGS = {
    "Image Filter": ImageFilter,
    "Mask Image Filter": MaskImageFilter,
    "Text Image Filter": TextImageFilter,
    "Pick from List": PickFromList,
    "Batch from Image List": BatchFromImageList,
    "Image List From Batch": ImageListFromBatch,
    "Split String by Commas": SplitByCommas,
    "Any List to String": AnyListToString,
    "StringToStringList": StringToStringList,
    "cg_String to Float": StringToFloat,
    "cg_String to Int": StringToInt,
    "Masked Section": MaskedSection,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: node_class.GET_SCHEMA().display_name
    for node_id, node_class in NODE_CLASS_MAPPINGS.items()
}


async def comfy_entrypoint() -> ComfyExtension:
    class CgImageFilterExtension(ComfyExtension):
        async def get_node_list(self) -> list[type[io.ComfyNode]]:
            return list(NODE_CLASS_MAPPINGS.values())

    return CgImageFilterExtension()


__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "VERSION",
    "WEB_DIRECTORY",
    "comfy_entrypoint",
]
