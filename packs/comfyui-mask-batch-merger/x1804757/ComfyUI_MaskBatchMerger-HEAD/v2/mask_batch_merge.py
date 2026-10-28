"""V2 boundary adapter. Pixel/scalar compute is the byte-retained original module."""
from comfy_api.latest import io, sdk
from . import _original


async def _value(value):
    return await value.value() if isinstance(value, sdk.ValueRef) else value


class MaskBatchMerge(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='MaskBatchMergeAdd', display_name='Mask Merger', category='mmmmmmmmm',
            inputs=[io.Mask.Input('mask_batch')],
            outputs=[io.Mask.Output(display_name='merged_mask')],
        )

    @classmethod
    async def execute(cls, mask_batch):
        pixels = await mask_batch.raw()
        result = _original.MaskBatchMerge().merge_masks(pixels)
        return io.NodeOutput(await sdk.MaskRef.from_value(result[0]))


NODE_CLASS_MAPPINGS = {'MaskBatchMergeAdd': MaskBatchMerge}
NODE_DISPLAY_NAME_MAPPINGS = {'MaskBatchMergeAdd': 'Mask Merger'}
