"""Secure Nodes V2 conversion of ComfyUI-2D-Pose-Editor."""

from .nodes import PoseEditor2D

NODE_CLASS_MAPPINGS = {"PoseEditor2D": PoseEditor2D}
NODE_DISPLAY_NAME_MAPPINGS = {"PoseEditor2D": "2D Pose Editor"}
WEB_DIRECTORY = "web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
