from comfy_api.latest import io, sdk
from .admission import geometry
from . import nodes as original

class _MaskNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("inspect", "raw")
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id=cls.__name__, display_name=cls.DISPLAY,
                         category=cls.__name__, inputs=[io.Mask.Input("mask")],
                         outputs=[io.Mask.Output()])
    @classmethod
    async def execute(cls, mask):
        shape = geometry(await mask.describe())
        value = await mask.raw()
        import torch
        if type(value) is not torch.Tensor or list(value.shape) != shape:
            raise TypeError("My-Mask raw geometry must match the admitted tensor")
        result = getattr(original, cls.__name__)().generate_convex_mask(value)[0]
        # Native no-contour result retains the original managed identity.
        if result is value:
            return io.NodeOutput(mask)
        return io.NodeOutput(await sdk.MaskRef.from_value(result))

class MaskToBottonHalfConvexMask(_MaskNode):
    DISPLAY = "Mask To Botton Half Convex Mask"
class MaskToConvexMask(_MaskNode):
    DISPLAY = "Mask To Convex Mask"
