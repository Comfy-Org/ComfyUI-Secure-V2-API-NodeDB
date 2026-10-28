"""V2 boundary adapter. Pixel/scalar compute is the byte-retained original module."""
from comfy_api.latest import io, sdk
from . import _original


async def _value(value):
    return await value.value() if isinstance(value, sdk.ValueRef) else value


class NanoBananaSizeCalculator(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='NanoBananaSizeCalculator', display_name='Nano Banana Size Calculator', category='image/transform',
            inputs=[
                io.Image.Input('image'),
                io.Combo.Input('preset', options=['NB 1', 'NB 2 (1K)', 'NB 2 (2K)', 'NB 2 (4K)', 'Nano Banana 2 Flash (1K)', 'Nano Banana 2 Flash (2K)', 'Nano Banana 2 Flash (4K)'], default='NB 2 (2K)'),
                io.Combo.Input('method', options=['Clamp (reccomended)', 'Dynamic (legacy)', 'Static'], default='Clamp (reccomended)'),
                io.Combo.Input('aspect_ratio', options=['auto', '1:1', '2:3', '3:2', '3:4', '4:3', '4:5', '5:4', '9:16', '16:9', '21:9', '1:4', '1:8', '4:1', '8:1'], default='auto', optional=True),
            ],
            outputs=[io.Int.Output(display_name='width'), io.Int.Output(display_name='height'), io.String.Output(display_name='info'), io.String.Output(display_name='aspect_ratio')],
        )

    @classmethod
    async def execute(cls, image, preset, method, aspect_ratio='auto'):
        pixels = await image.raw()
        result = _original.NanoBananaSizeCalculator().calculate_size(
            pixels, await _value(preset), await _value(method), await _value(aspect_ratio))
        return io.NodeOutput(*result)


NODE_CLASS_MAPPINGS = {'NanoBananaSizeCalculator': NanoBananaSizeCalculator}
NODE_DISPLAY_NAME_MAPPINGS = {'NanoBananaSizeCalculator': 'Nano Banana Size Calculator'}
