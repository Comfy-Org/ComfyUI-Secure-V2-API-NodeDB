from .find_mask_size import QImageCropCalculator

NODE_CLASS_MAPPINGS = {
    "QImageCropCalculator": QImageCropCalculator,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "QImageCropCalculator": "Q Image Crop Calculator",
}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']