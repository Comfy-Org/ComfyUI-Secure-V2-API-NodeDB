"""Secure Nodes 2.0 entrypoint for the pinned Efficiency Nodes snapshot."""

from ._secure_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS


WEB_DIRECTORY = "./js"
CC_VERSION = 2.0

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
    "CC_VERSION",
]
