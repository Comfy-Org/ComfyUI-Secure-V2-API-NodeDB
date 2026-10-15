from .nodes import ColorMatch2Refs, ColorMatchBlendAutoWeights

NODE_CLASS_MAPPINGS = {
    "ColorMatch2Refs": ColorMatch2Refs,
    "ColorMatchBlendAutoWeights": ColorMatchBlendAutoWeights,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "ColorMatch2Refs": "Color Match 2Refs",
    "ColorMatchBlendAutoWeights": "Color Match 2Refs Blend AutoWeights",
}
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
