"""Secure Nodes V2 entrypoint for the frontend-only translation pack."""


# The upstream package has no backend nodes.  Its Python file existed only to
# expose a locale HTTP endpoint and to copy browser scripts into ComfyUI's web
# tree.  V2 contributes the same locale data through the typed frontend
# localization facade, so importing this package has no host side effects.
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
WEB_DIRECTORY = "./"

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
]
