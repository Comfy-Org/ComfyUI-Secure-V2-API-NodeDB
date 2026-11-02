"""Secure Nodes V2 entrypoint for ComfyUI-Frame-Interpolation (pin 26545cc2).

Upstream's __init__.py put the pack folder on sys.path and imported every model
module at load time. In v2, the nodes live in secure_nodes.py. Each upstream
model module is imported inside the node that needs it, with package-relative
imports, so nothing here touches sys.path. A guest never runs this file; it
loads secure_nodes from the manifest.
"""

from .secure_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
