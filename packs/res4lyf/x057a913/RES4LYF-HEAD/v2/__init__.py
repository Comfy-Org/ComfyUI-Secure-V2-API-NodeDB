"""RES4LYF (ClownsharkBatwing/RES4LYF @ 057a913e): Secure Nodes V2.

- Every node id the original registers is registered here with its original schema (_frozen_nodes.json), so
  saved workflows load unchanged.
- Converted:
  - ClownsharKSampler_Beta, a reduced exact port (clown.py), including the OPTIONS it can apply exactly;
  - the options nodes SharkOptions_Beta and ClownOptions_DetailBoost_Beta (options_nodes.py);
  - the small value nodes TextBox1, SetImageSizeWithScale and "Sigmas Power" (simple_nodes.py);
  - the two global scheduler names RES4LYF adds, bong_tangent and beta57 (manifest scheduler providers,
    schedulers.py).
- Every other node refuses by name at queue time and when executed. See SECURE_CONVERSION.md.
"""
from ._secure_runtime import FROZEN, REFUSED
from .clown import ClownsharKSamplerBetaV2
from .options_nodes import ClownOptionsDetailBoostBetaV2, SharkOptionsBetaV2
from .simple_nodes import SetImageSizeWithScaleV2, SigmasPowerV2, TextBox1V2

CONVERTED = {
    "ClownOptions_DetailBoost_Beta": ClownOptionsDetailBoostBetaV2,
    "ClownsharKSampler_Beta": ClownsharKSamplerBetaV2,
    "SetImageSizeWithScale": SetImageSizeWithScaleV2,
    "SharkOptions_Beta": SharkOptionsBetaV2,
    "Sigmas Power": SigmasPowerV2,
    "TextBox1": TextBox1V2,
}

# Refused ids use the classes _secure_runtime defines at import (the guest finds them there without this file)
NODE_CLASS_MAPPINGS = {node_id: CONVERTED.get(node_id) or REFUSED[node_id] for node_id in sorted(FROZEN)}

__all__ = ["NODE_CLASS_MAPPINGS"]
