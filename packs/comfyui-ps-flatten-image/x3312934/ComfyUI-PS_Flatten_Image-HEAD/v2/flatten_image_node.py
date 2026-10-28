"""V2 boundary adapter. Pixel/scalar compute is the byte-retained original module."""
from comfy_api.latest import io, sdk
from . import _original


async def _value(value):
    return await value.value() if isinstance(value, sdk.ValueRef) else value


class FlattenImage(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='FlattenImage', display_name='PS Flatten Image', category='PS Operations',
            inputs=[io.Image.Input('images')],
            outputs=[io.Image.Output(display_name='image')],
        )

    @classmethod
    async def execute(cls, images):
        pixels = await images.raw()
        result = _original.FlattenImage().flatten_layers(pixels)
        output = images if result[0] is pixels else await sdk.ImageRef.from_value(result[0])
        return io.NodeOutput(output)


NODE_CLASS_MAPPINGS = {'FlattenImage': FlattenImage}
NODE_DISPLAY_NAME_MAPPINGS = {'FlattenImage': 'PS Flatten Image'}
