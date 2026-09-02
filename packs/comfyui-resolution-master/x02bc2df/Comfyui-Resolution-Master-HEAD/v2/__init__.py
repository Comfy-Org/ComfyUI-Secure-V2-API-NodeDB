"""Secure Nodes V2 entrypoint for Resolution Master."""

from .aztoolkit import (
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
    ResolutionMaster,
    ResolutionMasterExtension,
    comfy_entrypoint,
)


WEB_DIRECTORY = "./js"


__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "ResolutionMaster",
    "ResolutionMasterExtension",
    "WEB_DIRECTORY",
    "comfy_entrypoint",
]
