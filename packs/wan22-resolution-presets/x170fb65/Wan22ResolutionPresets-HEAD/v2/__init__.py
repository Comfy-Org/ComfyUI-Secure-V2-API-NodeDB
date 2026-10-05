"""Secure Nodes V2 conversion of ComfyUI-Wan22ResolutionPresets."""

from .nodes import VideoResolutionSelector, Wan22ResolutionPresets


NODE_CLASS_MAPPINGS = {
    "Wan22ResolutionPresets": Wan22ResolutionPresets,
    "VideoResolutionSelector": VideoResolutionSelector,
}
WEB_DIRECTORY = "web"

__all__ = ["NODE_CLASS_MAPPINGS", "WEB_DIRECTORY"]
