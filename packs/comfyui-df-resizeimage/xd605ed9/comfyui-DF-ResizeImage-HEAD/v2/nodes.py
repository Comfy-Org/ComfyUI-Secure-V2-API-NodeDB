"""V2 boundary adapter. Pixel/scalar compute is the byte-retained original module."""
from comfy_api.latest import io, sdk
from . import _original


async def _value(value):
    return await value.value() if isinstance(value, sdk.ValueRef) else value


class FlexibleResizeToMultiple(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='comfyui-DF-ResizeImage', display_name='comfyui-DF-ResizeImage', category='image/resize',
            inputs=[
                io.Image.Input('image'),
                io.Combo.Input('mode', options=['long_side', 'short_side', 'scale_factor', 'long_and_short']),
                io.Combo.Input('interpolation', options=['bicubic', 'bilinear', 'area', 'nearest']),
                io.Int.Input('multiple_of', default=16, min=1, max=512, step=1),
                io.Combo.Input('rounding', options=['nearest', 'floor', 'ceil']),
                io.Int.Input('long_side', default=1536, min=1, max=32768, step=1),
                io.Int.Input('short_side', default=1024, min=1, max=32768, step=1),
                io.Float.Input('scale_factor', default=1.0, min=0.01, max=64.0, step=0.01),
            ],
            outputs=[io.Image.Output(display_name='image'), io.Int.Output(display_name='width'), io.Int.Output(display_name='height')],
        )

    @classmethod
    async def execute(cls, image, mode, interpolation, multiple_of, rounding, long_side, short_side, scale_factor):
        pixels = await image.raw()
        result = _original.FlexibleResizeToMultiple().resize(
            pixels, await _value(mode), await _value(interpolation), await _value(multiple_of),
            await _value(rounding), await _value(long_side), await _value(short_side), await _value(scale_factor))
        return io.NodeOutput(await sdk.ImageRef.from_value(result[0]), *result[1:])


NODE_CLASS_MAPPINGS = {'comfyui-DF-ResizeImage': FlexibleResizeToMultiple}
NODE_DISPLAY_NAME_MAPPINGS = {'comfyui-DF-ResizeImage': 'comfyui-DF-ResizeImage'}
