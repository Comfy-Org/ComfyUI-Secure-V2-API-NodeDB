"""Secure Nodes V2 entrypoint for ComfyUI-SeedVR2_VideoUpscaler (pin 4490bd1f, v2.5.24).

The four nodes live in secure_seedvr2.py, which imports the pack's modules only inside each node.
A guest never runs this file; it loads secure_seedvr2 from the manifest.
"""

from .secure_seedvr2 import NODE_CLASS_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS"]
