"""Secure Nodes V2 conversion of ComfyUI-AutoNotes."""

from .autonotes import AutoNotesNode

NODE_CLASS_MAPPINGS = {"AutoNotesNode": AutoNotesNode}
NODE_DISPLAY_NAME_MAPPINGS = {"AutoNotesNode": "Auto Notes"}
WEB_DIRECTORY = "web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
