"""Public scalar boundary. Compute remains the retained original methods."""
from comfy_api.latest import io
from .string_concatenate import StringConcatenate5 as _LegacyStringConcatenate5


class StringConcatenate5(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='StringConcatenate5', display_name='5文字列改行結合',
            category='text', description='5つの文字列を改行で結合。ノード上でプレビュー表示。出力は未接続でもエラーになりません。',
            is_output_node=True, is_input_list=False,
            inputs=[
                io.String.Input('string_1', default='', multiline=True),
                io.String.Input('string_2', default='', multiline=True),
                io.String.Input('string_3', default='', multiline=True),
                io.String.Input('string_4', default='', multiline=True),
                io.String.Input('string_5', default='', multiline=True),
            ],
            outputs=[
                io.String.Output(display_name='text'),
                io.String.Output(display_name='preview'),
            ],
        )

    @classmethod
    async def execute(cls, string_1, string_2, string_3, string_4, string_5):
        result = _LegacyStringConcatenate5().concatenate(string_1=string_1, string_2=string_2, string_3=string_3, string_4=string_4, string_5=string_5)
        return io.NodeOutput.from_dict(result)

NODE_CLASS_MAPPINGS = {
    'StringConcatenate5': StringConcatenate5,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    'StringConcatenate5': '5文字列改行結合',
}
