from .nodes import BlurMask

NODE_CLASS_MAPPINGS = {"comfypsi_blur_mask": BlurMask}
NODE_DISPLAY_NAME_MAPPINGS = {"comfypsi_blur_mask": "Blur Mask"}
WEB_DIRECTORY = "web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
