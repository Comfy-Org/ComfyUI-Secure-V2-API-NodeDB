"""Secure Nodes 2.0 entrypoint for the pinned mxToolkit snapshot."""

from ._secure_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS


WEB_DIRECTORY = "./js"


__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
]
