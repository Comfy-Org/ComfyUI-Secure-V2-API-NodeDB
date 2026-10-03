"""Secure Nodes V2 conversion of ComfyUI Preview 360 Panorama."""

from .nodes import PanoramaVideoViewerNode, PanoramaViewerNode


NODE_CLASS_MAPPINGS = {
    "PanoramaViewerNode": PanoramaViewerNode,
    "PanoramaVideoViewerNode": PanoramaVideoViewerNode,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "PanoramaViewerNode": "Preview 360 Panorama",
    "PanoramaVideoViewerNode": "Preview 360 Video Panorama",
}
WEB_DIRECTORY = "web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
