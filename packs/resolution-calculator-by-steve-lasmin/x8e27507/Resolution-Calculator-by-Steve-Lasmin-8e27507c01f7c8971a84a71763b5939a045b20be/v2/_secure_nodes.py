"""Original output sink with typed NumberDisplay and direct native compute."""
from comfy_api.latest import io, ComfyExtension
from ._boundary import calculate

class Resolution_Calculator_by_Steve_Lasmin(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Resolution_Calculator_by_Steve_Lasmin', display_name="Resolution Calculator by Steve Lasmin", category="utils",
            is_output_node=True,
            inputs=[io.Int.Input('resolution', default=1024, min=32, max=4096, step=16, display_mode=io.NumberDisplay.number), io.Combo.Input('aspect_preset', options=['custom', '1:1', '3:2', '4:3', '16:9', '16:10', '21:9', '2:3', '3:4', '9:16', '9:21'], default='custom'), io.Int.Input('width_ratio', default=2, min=1, max=999999, step=1, display_mode=io.NumberDisplay.number), io.Int.Input('height_ratio', default=3, min=1, max=999999, step=1, display_mode=io.NumberDisplay.number), io.Combo.Input('multiplier', options=['16', '32', '64'], default='32')],
            outputs=[io.Int.Output("width"), io.Int.Output("height"), io.String.Output("preview")],
        )

    @classmethod
    async def execute(cls, resolution, aspect_preset, width_ratio, height_ratio, multiplier):
        return io.NodeOutput(*calculate(resolution, aspect_preset, width_ratio, height_ratio, multiplier))

NODE_CLASS_MAPPINGS = {'Resolution_Calculator_by_Steve_Lasmin': Resolution_Calculator_by_Steve_Lasmin}

class Extension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())
