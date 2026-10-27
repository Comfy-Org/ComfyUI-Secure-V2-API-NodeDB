"""Existing public-f1 adapter; native Textline method retained byte-exact."""
from comfy_api.latest import io
from . import _native

class TextLineCounter(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='TextLineCounter', display_name='Text Line Counter', category='Text Processing',
            is_input_list=False, inputs=[io.String.Input('text_input', multiline=True, default='')],
            outputs=[io.String.Output(display_name='original_text', is_output_list=False),
                     io.Int.Output(display_name='line_count', is_output_list=False),
                     io.String.Output(display_name='processed_text', is_output_list=False)])

    @classmethod
    async def execute(cls, text_input):
        return io.NodeOutput(*_native.TextLineCounter().process_text_and_count_lines(text_input))

NODE_CLASS_MAPPINGS = {'TextLineCounter': TextLineCounter}
NODE_DISPLAY_NAME_MAPPINGS = {'TextLineCounter': 'Text Line Counter'}
