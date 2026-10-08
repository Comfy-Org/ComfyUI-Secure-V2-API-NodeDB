from .image_filter_adjustments_node import KMCDEV_Image_Filter_Adjustments
from .image_processor import KMCDEV_Image_Blank_Alpha, KMCDEV_Image_Blend_Mask, KMCDEV_Mix_Color_By_Mask

NODE_CLASS_MAPPINGS = {
    "ImageFilterAdjustments": KMCDEV_Image_Filter_Adjustments,
    "ImageBlankAlpha": KMCDEV_Image_Blank_Alpha,
    "ImageBlendMask": KMCDEV_Image_Blend_Mask,
    "ImageMixColorByMask": KMCDEV_Mix_Color_By_Mask,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ImageFilterAdjustments": "Image Filter Adjustments",
    "ImageBlankAlpha": "Image Blank with Alpha",
    "ImageBlendMask": "Image Blend Mask",
    "ImageMixColorByMask": "Image Mix Color by Mask",
}
