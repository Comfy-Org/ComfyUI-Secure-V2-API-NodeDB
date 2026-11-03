import logging
from comfy_api.latest import ComfyExtension, io
from ._secure_nodes import (
    ColorPatchFlatten, ColorPatchMerge,
    AchromaticStabilizer, LoadICCProfile,
    SaveImageAdvancedCustom, SaveImageJPG,
    SaveImageAdvancedJPG, SaveImageBMP, SaveImageAdvancedBMP,
    SaveImageTIFF, SaveImageAdvancedTIFF, SaveImageTGA,
    SaveImageAdvancedTGA, SaveImageAVIF, SaveImageAdvancedAVIF,
    SaveImageICO, SaveImageAdvancedICO, ICOPacker
)
from .define import define

logger = logging.getLogger(define.logger_name)

WEB_DIRECTORY = "./web"
__all__ = ['WEB_DIRECTORY']

class ImageProcessExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [
            ColorPatchFlatten,
            ColorPatchMerge,
            AchromaticStabilizer,
            LoadICCProfile,
            SaveImageAdvancedCustom,
            SaveImageJPG,
            SaveImageAdvancedJPG,
            SaveImageBMP,
            SaveImageAdvancedBMP,
            SaveImageTIFF,
            SaveImageAdvancedTIFF,
            SaveImageTGA,
            SaveImageAdvancedTGA,
            SaveImageAVIF,
            SaveImageAdvancedAVIF,
            SaveImageICO,
            SaveImageAdvancedICO,
            ICOPacker
        ]

async def comfy_entrypoint() -> ImageProcessExtension:
    return ImageProcessExtension()