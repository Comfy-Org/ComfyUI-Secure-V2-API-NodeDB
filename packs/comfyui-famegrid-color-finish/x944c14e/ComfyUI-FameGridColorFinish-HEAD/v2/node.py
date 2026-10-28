"""V2 boundary adapter. Pixel/scalar compute is the byte-retained original module."""
from comfy_api.latest import io, sdk
from . import _original


async def _value(value):
    return await value.value() if isinstance(value, sdk.ValueRef) else value


class FameGridColorFinish(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='FameGridColorFinish', display_name='Color Finish (FameGrid)', category='FameGrid/Color',
            description='FameGrid color and detail finish with separate master strengths.',
            inputs=[io.Image.Input('image'),
                io.Float.Input('color_strength', default=1.0, min=0.0, max=1.0, step=0.05, optional=True),
                io.Float.Input('sharpen_strength', default=0.6, min=0.0, max=1.0, step=0.05, optional=True),
            ],
            outputs=[io.Image.Output(display_name='image')],
        )

    @classmethod
    async def execute(cls, image, color_strength=1.0, sharpen_strength=0.6):
        pixels = await image.raw()
        result = _original.FameGridColorFinish().finish(pixels, await _value(color_strength), await _value(sharpen_strength))
        return io.NodeOutput(await sdk.ImageRef.from_value(result[0]))


NODE_CLASS_MAPPINGS = {'FameGridColorFinish': FameGridColorFinish}
NODE_DISPLAY_NAME_MAPPINGS = {'FameGridColorFinish': 'Color Finish (FameGrid)'}
