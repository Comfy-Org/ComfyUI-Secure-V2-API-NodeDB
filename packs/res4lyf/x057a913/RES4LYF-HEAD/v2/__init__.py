"""RES4LYF (ClownsharkBatwing/RES4LYF @ 057a913e): Secure Nodes V2.

- Every node id the original registers is registered here with its original schema (_frozen_nodes.json), so
  saved workflows load unchanged. The exception is ConditioningMultiply: core registers that id itself, and core's
  node serves it, as it does with the original installed (SECURE_CONVERSION.md).
- Converted:
  - ClownsharKSampler_Beta, a reduced exact port (clown.py), including the OPTIONS it can apply exactly;
  - the options nodes SharkOptions_Beta and ClownOptions_DetailBoost_Beta (options_nodes.py);
  - the text and size nodes TextBox1, TextBox2, TextConcatenate, SetImageSize, SetImageSizeWithScale and the sigma
    node "Sigmas Power" (simple_nodes.py);
  - the sigma nodes Sigmas From Text, Sigmas Split Value, Sigmas Rescale, Sigmas Easing and Sigmas Resample
    (sigma_nodes.py);
  - the image nodes Film Grain, Image Grain Add, Frames Slice and VAEEncodeAdvanced (image_nodes.py);
  - the two global scheduler names RES4LYF adds, bong_tangent and beta57 (manifest scheduler providers,
    schedulers.py).
- Every other node refuses by name at queue time and when executed. See SECURE_CONVERSION.md.
"""
from ._secure_runtime import FROZEN, REFUSED
from .clown import ClownsharKSamplerBetaV2
from .image_nodes import CONVERTED as IMAGE_NODES
from .options_nodes import ClownOptionsDetailBoostBetaV2, SharkOptionsBetaV2
from .sigma_nodes import CONVERTED as SIGMA_NODES
from .simple_nodes import (SetImageSizeV2, SetImageSizeWithScaleV2, SigmasPowerV2, TextBox1V2, TextBox2V2,
                           TextConcatenateV2)

CONVERTED = {
    "ClownOptions_DetailBoost_Beta": ClownOptionsDetailBoostBetaV2,
    "ClownsharKSampler_Beta": ClownsharKSamplerBetaV2,
    "SetImageSize": SetImageSizeV2,
    "SetImageSizeWithScale": SetImageSizeWithScaleV2,
    "SharkOptions_Beta": SharkOptionsBetaV2,
    "Sigmas Power": SigmasPowerV2,
    "TextBox1": TextBox1V2,
    "TextBox2": TextBox2V2,
    "TextConcatenate": TextConcatenateV2,
    **IMAGE_NODES,
    **SIGMA_NODES,
}

# Refused ids use the classes _secure_runtime defines at import (the guest finds them there without this file)
NODE_CLASS_MAPPINGS = {node_id: CONVERTED.get(node_id) or REFUSED[node_id] for node_id in sorted(FROZEN)}

__all__ = ["NODE_CLASS_MAPPINGS"]
