"""wlsh_nodes (wallish77/wlsh_nodes @ 97807467): Secure Nodes V2.

- Every node id the original registers is registered here with its original schema (_frozen_nodes.json), so saved
  workflows load unchanged.
- Converted:
  - value_nodes.py: SDXL Steps, Multiply Integer, SDXL Resolutions, Resolutions by Ratio, Simple String Combine, and
    the empty-latent nodes Empty Latent by Size, by Ratio and by Pixels and SDXL Quick Empty Latent;
  - image_nodes.py: Image Scale by Shortside and Upscale by Factor with Model;
  - model_nodes.py: Checkpoint Loader w/Name and KSamplerAdvanced (WLSH), on the host's loader and sampler.
- Every other node refuses by name at queue time and when executed. See SECURE_CONVERSION.md.
"""
from ._secure_runtime import FROZEN, REFUSED
from .image_nodes import CONVERTED as IMAGE_NODES
from .model_nodes import CONVERTED as MODEL_NODES
from .value_nodes import CONVERTED as VALUE_NODES

CONVERTED = {**VALUE_NODES, **IMAGE_NODES, **MODEL_NODES}

# Refused ids use the classes _secure_runtime defines at import (the guest finds them there without this file)
NODE_CLASS_MAPPINGS = {node_id: CONVERTED.get(node_id) or REFUSED[node_id] for node_id in sorted(FROZEN)}

__all__ = ["NODE_CLASS_MAPPINGS"]
