"""Secure Nodes V2 entrypoint for the frontend-only workflow encrypt pack."""


# Upstream imported ComfyUI's global NODE_CLASS_MAPPINGS and accidentally
# re-exported every core node as if it belonged to this pack.  This extension
# defines no backend nodes; its one real registration lives in WEB_DIRECTORY.
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
WEB_DIRECTORY = "./js"

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
]
