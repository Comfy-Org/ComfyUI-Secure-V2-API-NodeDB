"""Public scalar boundary. Compute remains the retained original methods."""
from comfy_api.latest import io
from .wqx_dual_ratio_calc import Wqx_DualRatioTools as _LegacyWqx_DualRatioTools


class Wqx_DualRatioTools(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Wqx_DualRatioTools', display_name='Wqx 单比例双分辨率(统一multiple)',
            category='Wqx/Tools', description='',
            is_output_node=False, is_input_list=False,
            inputs=[
                io.Combo.Input('asp', options=['1:1 (Square)', '2:3 (Portrait Photo)', '3:2 (Photo)', '3:4 (Portrait Standard)', '4:3 (Standard)', '9:16 (Portrait Widescreen)', '16:9 (Widescreen)', '21:9 (Ultrawide)'], default='9:16 (Portrait Widescreen)'),
                io.Float.Input('megapixels1', default=0.6, min=0.1, max=16.0, step=0.05),
                io.Float.Input('megapixels2', default=2.0, min=0.1, max=16.0, step=0.05),
                io.Int.Input('multiple', default=32, min=8, max=128),
            ],
            outputs=[
                io.Int.Output(display_name='size1_w'),
                io.Int.Output(display_name='size1_h'),
                io.Int.Output(display_name='size2_w'),
                io.Int.Output(display_name='size2_h'),
                io.Float.Output(display_name='aspect_float'),
            ],
        )

    @classmethod
    async def execute(cls, asp, megapixels1, megapixels2, multiple):
        result = _LegacyWqx_DualRatioTools().calc(asp=asp, megapixels1=megapixels1, megapixels2=megapixels2, multiple=multiple)
        return io.NodeOutput(*result)

NODE_CLASS_MAPPINGS = {
    'Wqx_DualRatioTools': Wqx_DualRatioTools,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    'Wqx_DualRatioTools': 'Wqx 单比例双分辨率(统一multiple)',
}
