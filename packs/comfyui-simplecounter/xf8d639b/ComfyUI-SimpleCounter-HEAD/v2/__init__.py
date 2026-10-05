"""Secure Nodes V2 conversion of ComfyUI SimpleCounter."""

from .nodes import SimpleCounter


NODE_CLASS_MAPPINGS = {"Simple Counter": SimpleCounter}
WEB_DIRECTORY = "web"

__all__ = ["NODE_CLASS_MAPPINGS", "WEB_DIRECTORY"]
