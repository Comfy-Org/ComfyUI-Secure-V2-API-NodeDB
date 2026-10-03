from .ImagePreviewPause import ImagePreviewPause

WEB_DIRECTORY = "./js"

NODE_CLASS_MAPPINGS = {
    "ImagePreviewPause": ImagePreviewPause,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ImagePreviewPause": "Preview Image with Pause",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
