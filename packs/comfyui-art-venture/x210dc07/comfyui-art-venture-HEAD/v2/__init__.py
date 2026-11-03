"""comfyui-art-venture (sipherxyz/comfyui-art-venture @ 210dc072): Secure Nodes V2.

- Every node id the original registers (without the optional packs it integrates with) is registered here with its
  original schema (_frozen_nodes.json), so saved workflows load unchanged.
- Converted (utility_nodes.py): StringToInt, BooleanPrimitive, SeedSelector, SDXLAspectRatioSelector,
  AspectRatioSelector, ImageScaleDownBy, ImageScaleDownToSize, ImageScaleToMegapixels, ImageGaussianBlur,
  ImageApplyChannel, CheckpointNameSelector, RandomInt, RandomFloat (verbatim global RNG, as upstream).
- Every other node refuses by name at queue time and when executed. See SECURE_CONVERSION.md.
"""
from ._secure_runtime import FROZEN, REFUSED
from .utility_nodes import CONVERTED

# Refused ids use the classes _secure_runtime defines at import (the guest finds them there without this file)
NODE_CLASS_MAPPINGS = {node_id: CONVERTED.get(node_id) or REFUSED[node_id] for node_id in sorted(FROZEN)}

__all__ = ["NODE_CLASS_MAPPINGS"]
