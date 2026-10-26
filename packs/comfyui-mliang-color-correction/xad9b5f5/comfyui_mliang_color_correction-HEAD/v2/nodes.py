"""Public V2 boundary; all numerical work is the retained original module."""
from comfy_api.latest import io, sdk
from . import _original


async def _value(value):
    # Public wrap_inputs deliberately leaves ordinary scalar data unchanged.
    return await value.value() if isinstance(value, sdk.ValueRef) else value


class MLiangColorCorrection(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)
    NODE_ID = 'MLiangColorCorrection'
    DISPLAY_NAME = 'MLiang Color Correction'
    DEPRECATED = False

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id=cls.NODE_ID, display_name=cls.DISPLAY_NAME,
            category='image/color', is_deprecated=cls.DEPRECATED,
            inputs=[
                io.Image.Input('image'),
                io.Float.Input('exposure', default=0.0, min=-5.0, max=5.0, step=0.05),
                io.Float.Input('brightness', default=0.0, min=-1.0, max=1.0, step=0.01),
                io.Float.Input('contrast', default=1.0, min=0.0, max=3.0, step=0.01),
                io.Float.Input('saturation', default=1.0, min=0.0, max=3.0, step=0.01),
                io.Float.Input('gamma', default=1.0, min=0.1, max=5.0, step=0.01),
                io.Float.Input('temperature', default=0.0, min=-1.0, max=1.0, step=0.01),
                io.Float.Input('tint', default=0.0, min=-1.0, max=1.0, step=0.01),
                io.Float.Input('hue_shift', default=0.0, min=-180.0, max=180.0, step=1.0),
                io.Float.Input('shadows', default=0.0, min=-1.0, max=1.0, step=0.01),
                io.Float.Input('highlights', default=0.0, min=-1.0, max=1.0, step=0.01),
                io.Float.Input('strength', default=1.0, min=0.0, max=1.0, step=0.01),
            ], outputs=[io.Image.Output(display_name='image')],
        )

    @classmethod
    async def execute(cls, image, exposure, brightness, contrast, saturation, gamma,
                      temperature, tint, hue_shift, shadows, highlights, strength):
        pixels = await image.raw()
        result = _original.NODE_CLASS_MAPPINGS[cls.NODE_ID]().correct(
            pixels, await _value(exposure), await _value(brightness),
            await _value(contrast), await _value(saturation), await _value(gamma),
            await _value(temperature), await _value(tint), await _value(hue_shift),
            await _value(shadows), await _value(highlights), await _value(strength))
        return io.NodeOutput(await sdk.ImageRef.from_value(result[0]))


class MLiangWhiteBalance(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)
    NODE_ID = 'MLiangWhiteBalance'
    DISPLAY_NAME = 'MLiang White Balance'
    DEPRECATED = False

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id=cls.NODE_ID, display_name=cls.DISPLAY_NAME,
            category='image/color', is_deprecated=cls.DEPRECATED,
            inputs=[
                io.Image.Input('image'),
                io.Float.Input('red', default=1.0, min=0.0, max=3.0, step=0.01),
                io.Float.Input('green', default=1.0, min=0.0, max=3.0, step=0.01),
                io.Float.Input('blue', default=1.0, min=0.0, max=3.0, step=0.01),
                io.Boolean.Input('normalize_luma', default=True),
                io.Float.Input('strength', default=1.0, min=0.0, max=1.0, step=0.01),
            ], outputs=[io.Image.Output(display_name='image')],
        )

    @classmethod
    async def execute(cls, image, red, green, blue, normalize_luma, strength):
        pixels = await image.raw()
        result = _original.NODE_CLASS_MAPPINGS[cls.NODE_ID]().balance(
            pixels, await _value(red), await _value(green), await _value(blue),
            await _value(normalize_luma), await _value(strength))
        return io.NodeOutput(await sdk.ImageRef.from_value(result[0]))


class CodexColorCorrection(MLiangColorCorrection):
    NODE_ID = 'CodexColorCorrection'
    DISPLAY_NAME = 'MLiang Color Correction (Legacy)'
    DEPRECATED = True


class CodexWhiteBalance(MLiangWhiteBalance):
    NODE_ID = 'CodexWhiteBalance'
    DISPLAY_NAME = 'MLiang White Balance (Legacy)'
    DEPRECATED = True


NODE_CLASS_MAPPINGS = {
    'MLiangColorCorrection': MLiangColorCorrection,
    'MLiangWhiteBalance': MLiangWhiteBalance,
    'CodexColorCorrection': CodexColorCorrection,
    'CodexWhiteBalance': CodexWhiteBalance,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    'MLiangColorCorrection': 'MLiang Color Correction',
    'MLiangWhiteBalance': 'MLiang White Balance',
    'CodexColorCorrection': 'MLiang Color Correction (Legacy)',
    'CodexWhiteBalance': 'MLiang White Balance (Legacy)',
}
