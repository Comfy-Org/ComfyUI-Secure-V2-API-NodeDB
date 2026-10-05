"""Secure Nodes V2 conversion of Radar Weights Node."""

from .nodes import RadarWeightsNode


NODE_CLASS_MAPPINGS = {"RadarWeightsNode": RadarWeightsNode}
WEB_DIRECTORY = "web"

__all__ = ["NODE_CLASS_MAPPINGS", "WEB_DIRECTORY"]
