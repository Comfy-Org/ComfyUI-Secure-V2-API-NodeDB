from .nodes import ImageExpandMerger, ImageExpandNoiser, ImageExpandOption

NODE_CLASS_MAPPINGS = {
    "ImageExpandNoiser": ImageExpandNoiser,
    "ImageExpandMerger": ImageExpandMerger,
    "ImageExpandOption": ImageExpandOption,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "ImageExpandNoiser": "Image Expand Noiser",
    "ImageExpandMerger": "Image Expand Merger",
    "ImageExpandOption": "Image Expand Option",
}
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
