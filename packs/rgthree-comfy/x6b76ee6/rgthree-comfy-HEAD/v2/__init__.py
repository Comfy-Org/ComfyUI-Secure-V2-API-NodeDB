"""rgthree-comfy Secure Nodes 2.0 entrypoint.

The production secure loader consumes ``secure-nodes.json`` and never executes
this package initializer. Keeping the same mappings here makes local schema
generation and conversion tests use the exact guest classes named by the
manifest, without importing rgthree's legacy server bootstrap.
"""
from .py.secure_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS


WEB_DIRECTORY = "./web/comfyui"

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
]
