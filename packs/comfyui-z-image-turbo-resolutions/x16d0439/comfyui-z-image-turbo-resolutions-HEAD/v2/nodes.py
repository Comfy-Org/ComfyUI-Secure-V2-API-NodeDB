"""V2 boundary over the byte-identical original primitive computation."""
from comfy_api.latest import io
from .z_image_turbo_resolutions import ZImageTurboResolutions as _Original


class ZImageTurboResolutions(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        required = _Original.INPUT_TYPES()['required']
        return io.Schema(
            node_id='ZImageTurboResolutions',
            display_name='Z Image Turbo Resolutions',
            category='image/resolution',
            inputs=[
                io.Combo.Input('resolution', options=required['resolution'][0], default=required['resolution'][1]['default']),
                io.Combo.Input('ratio', options=required['ratio'][0], default=required['ratio'][1]['default']),
            ],
            outputs=[
                io.Int.Output(display_name='resolution'),
                io.Int.Output(display_name='width'),
                io.Int.Output(display_name='height'),
            ],
        )

    @classmethod
    def execute(cls, resolution, ratio):
        return io.NodeOutput(*_Original().get_dimensions(resolution, ratio))


NODE_CLASS_MAPPINGS = {'ZImageTurboResolutions': ZImageTurboResolutions}
NODE_DISPLAY_NAME_MAPPINGS = {'ZImageTurboResolutions': 'Z Image Turbo Resolutions'}
