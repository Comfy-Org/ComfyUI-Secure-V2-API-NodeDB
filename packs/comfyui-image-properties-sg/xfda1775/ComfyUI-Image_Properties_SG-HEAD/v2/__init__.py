"""Secure Nodes V2 entry point for Image Properties SG."""

from comfy_api.latest import ComfyExtension, io

from .nodes import ALL_NODE_CLASSES


NODE_CLASS_MAPPINGS = {
    node_class.define_schema().node_id: node_class
    for node_class in ALL_NODE_CLASSES
}
NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: node_class.define_schema().display_name
    for node_id, node_class in NODE_CLASS_MAPPINGS.items()
}


class ImagePropertiesSGExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return ALL_NODE_CLASSES


async def comfy_entrypoint() -> ImagePropertiesSGExtension:
    return ImagePropertiesSGExtension()


WEB_DIRECTORY = "./web"

__all__ = [
    "NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY",
    "comfy_entrypoint",
]
