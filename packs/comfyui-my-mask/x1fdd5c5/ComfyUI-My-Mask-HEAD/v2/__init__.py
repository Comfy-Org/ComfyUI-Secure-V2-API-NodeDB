from .wrappers import MaskToBottonHalfConvexMask, MaskToConvexMask

NODE_CLASS_MAPPINGS = {
    "MaskToBottonHalfConvexMask": MaskToBottonHalfConvexMask,
    "MaskToConvexMask": MaskToConvexMask,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "MaskToBottonHalfConvexMask": "Mask To Botton Half Convex Mask",
    "MaskToConvexMask": "Mask To Convex Mask",
}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']
