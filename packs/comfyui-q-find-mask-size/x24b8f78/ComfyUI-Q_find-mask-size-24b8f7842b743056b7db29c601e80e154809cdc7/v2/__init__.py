from comfy_api.latest import ComfyExtension
from .find_mask_size import QImageCropCalculator

NODE_CLASS_MAPPINGS = {
    "QImageCropCalculator": QImageCropCalculator,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "QImageCropCalculator": "Q Image Crop Calculator",
}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']


class QMaskSizeExtension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint():
    return QMaskSizeExtension()
