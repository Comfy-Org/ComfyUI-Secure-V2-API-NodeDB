"""Secure Nodes V2 entrypoint for Scale Image to Total Pixels Advanced."""

from .nodes import ImageScaleToTotalPixelsX


WEB_DIRECTORY = "./js"

NODE_CLASS_MAPPINGS = {
    "ImageScaleToTotalPixelsX": ImageScaleToTotalPixelsX,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ImageScaleToTotalPixelsX": "Scale Image to Total Pixels Adv",
}

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
]
