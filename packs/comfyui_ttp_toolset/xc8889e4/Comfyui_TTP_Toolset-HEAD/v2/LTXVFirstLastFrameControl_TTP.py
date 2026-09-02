"""Compatibility exports for the Secure Nodes V2 LTX bindings."""

from ._secure_nodes import NODE_CLASS_MAPPINGS


LTXVFirstLastFrameControl_TTP = NODE_CLASS_MAPPINGS[
    "LTXVFirstLastFrameControl_TTP"]
LTXVMiddleFrame_TTP = NODE_CLASS_MAPPINGS["LTXVMiddleFrame_TTP"]
LTXVContext_TTP = NODE_CLASS_MAPPINGS["LTXVContext_TTP"]


__all__ = [
    "LTXVFirstLastFrameControl_TTP",
    "LTXVMiddleFrame_TTP",
    "LTXVContext_TTP",
]
