"""Secure Nodes V2 conversion of Wan/MiniMax/LTX Resolutions."""

from .nodes import (
    NODE_CLASS_MAPPINGS,
    LTXResolutions,
    LTXUpscalerPower,
    MiniMaxH3Resolutions,
    WanResolutions,
    WanResolutionsExtension,
    comfy_entrypoint,
)

NODE_DISPLAY_NAME_MAPPINGS = {
    "WanResolutions": "WanResolutions",
    "MiniMaxH3Resolutions": "MiniMax H3 Resolutions",
    "LTXResolutions": "LTXResolutions",
    "LTXUpscalerPower": "LTX Upscaler Power",
}

WEB_DIRECTORY = "./web"

__all__ = [
    "LTXResolutions",
    "LTXUpscalerPower",
    "MiniMaxH3Resolutions",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WanResolutions",
    "WanResolutionsExtension",
    "WEB_DIRECTORY",
    "comfy_entrypoint",
]
