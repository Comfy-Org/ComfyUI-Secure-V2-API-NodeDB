"""Public scalar boundary. Compute remains the retained original methods."""
from comfy_api.latest import io
from .text_concatenate import TextConcatenateDJ as _LegacyTextConcatenateDJ


class TextConcatenateDJ(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='ComfyUI-DJ_TextConcat', display_name='ComfyUI-DJ_TextConcat_文本拼接',
            category='DJ/TextConcat', description='',
            is_output_node=False, is_input_list=False,
            inputs=[
                io.String.Input('分隔符', multiline=None, default=''),
                io.Combo.Input('清理首尾空白', options=['是', '否'], default='否'),
                io.String.Input('文本1', optional=True, multiline=None, force_input=True),
                io.String.Input('文本2', optional=True, multiline=None, force_input=True),
                io.String.Input('文本3', optional=True, multiline=None, force_input=True),
                io.String.Input('文本4', optional=True, multiline=None, force_input=True),
                io.String.Input('文本5', optional=True, multiline=None, force_input=True),
                io.String.Input('文本6', optional=True, multiline=None, force_input=True),
                io.String.Input('文本7', optional=True, multiline=None, force_input=True),
                io.String.Input('文本8', optional=True, multiline=None, force_input=True),
                io.String.Input('文本9', optional=True, multiline=None, force_input=True),
                io.String.Input('文本10', optional=True, multiline=None, force_input=True),
                io.String.Input('文本11', optional=True, multiline=None, force_input=True),
                io.String.Input('文本12', optional=True, multiline=None, force_input=True),
            ],
            outputs=[
                io.String.Output(display_name='文本'),
            ],
        )

    @classmethod
    async def execute(cls, 分隔符, 清理首尾空白, **kwargs):
        result = _LegacyTextConcatenateDJ().run(分隔符=分隔符, 清理首尾空白=清理首尾空白, **kwargs)
        return io.NodeOutput(*result)

NODE_CLASS_MAPPINGS = {
    'ComfyUI-DJ_TextConcat': TextConcatenateDJ,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    'ComfyUI-DJ_TextConcat': 'ComfyUI-DJ_TextConcat_文本拼接',
}
