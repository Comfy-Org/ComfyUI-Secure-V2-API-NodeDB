"""Secure Nodes V2 conversion of sdxl-recommended-res-calc."""

from .nodes import (
    NODE_CLASS_MAPPINGS,
    RecommendedResCalc,
    RecommendedResolutionExtension,
    comfy_entrypoint,
)


NODE_DISPLAY_NAME_MAPPINGS = {
    "RecommendedResCalc": "Recommended Resolution Calculator",
}

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "RecommendedResCalc",
    "RecommendedResolutionExtension",
    "comfy_entrypoint",
]
