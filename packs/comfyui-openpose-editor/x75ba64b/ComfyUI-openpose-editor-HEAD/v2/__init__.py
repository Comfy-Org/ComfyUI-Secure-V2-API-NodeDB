"""Secure Nodes V2 entry point for ComfyUI OpenPose Editor."""

from .openpose_editor_nodes import LoadOpenposeJSONNode


NODE_CLASS_MAPPINGS = {
    "huchenlei.LoadOpenposeJSON": LoadOpenposeJSONNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "huchenlei.LoadOpenposeJSON": "Load Openpose JSON",
}


__all__ = [
    "LoadOpenposeJSONNode",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
]
