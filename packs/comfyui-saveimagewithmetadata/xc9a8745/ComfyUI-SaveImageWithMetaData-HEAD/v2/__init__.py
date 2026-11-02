"""Secure Nodes V2 conversion of nkchocoai/ComfyUI-SaveImageWithMetaData (c9a87453).

Node ids, display names, categories and inputs are the original's. Requires the 0cd9adec
guest SDK (comfy_api 0.37.0): graph.execution_metadata and the managed image writer's
png_text / a1111_parameters options.
"""
from comfy_api.latest import ComfyExtension

from .py.nodes.node import SaveImageWithMetaData, CreateExtraMetaData

NODE_CLASS_MAPPINGS = {
    "SaveImageWithMetaData": SaveImageWithMetaData,
    "CreateExtraMetaData": CreateExtraMetaData,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SaveImageWithMetaData": "Save Image With Metadata",
    "CreateExtraMetaData": "Create Extra MetaData",
}


class SaveImageWithMetaDataExtension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint():
    return SaveImageWithMetaDataExtension()


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "comfy_entrypoint"]
