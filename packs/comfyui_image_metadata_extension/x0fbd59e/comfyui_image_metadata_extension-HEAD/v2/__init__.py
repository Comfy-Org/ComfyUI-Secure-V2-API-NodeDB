"""Secure Nodes V2 conversion of edelvarden/comfyui_image_metadata_extension (0fbd59ee).

Node ids, display names, categories and inputs are the original's. Requires the
0cd9adec guest SDK (comfy_api 0.37.0): graph.execution_metadata and the managed
image writer's png_text / a1111_parameters options.
"""
from comfy_api.latest import ComfyExtension

from .modules.nodes.node import SaveImageWithMetaData, CreateExtraMetaData

# (base_name, class_ref, display_name)
node_definitions = [
    ("SaveImageWithMetaData", SaveImageWithMetaData, "Save Image With MetaData"),
    ("CreateExtraMetaData", CreateExtraMetaData, "Create Extra MetaData"),
]

NODE_CLASS_MAPPINGS = {
    f"{base_name}": class_ref for base_name, class_ref, _ in node_definitions
}

NODE_DISPLAY_NAME_MAPPINGS = {
    f"{base_name}": f"{display_name}" for base_name, _, display_name in node_definitions
}


class ImageMetadataExtension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint():
    return ImageMetadataExtension()


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "comfy_entrypoint"]
