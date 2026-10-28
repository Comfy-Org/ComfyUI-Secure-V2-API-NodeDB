"""Complete public V2 boundary. Original implementation modules unchanged."""
from comfy_api.latest import io

def _output(value):
    if type(value) is dict:
        return io.NodeOutput(*value['result'],ui=value.get('ui'),expand=value.get('expand'),block_execution=value.get('block_execution'))
    return io.NodeOutput(*value)

class ConvertNumbersNode(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='ConvertNumbersNode',display_name='数字归一化😄',category='🔢NumberConvert',
            inputs=[io.String.Input('text_input',multiline=True,default='输入需要转换的文本'),io.String.Input('additional_units',default='')],outputs=[io.String.Output()],
            is_input_list=False,is_output_node=False)
    @classmethod
    async def execute(cls,text_input,additional_units):
        from .NumberNormalization_ZN import ConvertNumbersNode as Original
        return _output(Original().convert_text(text_input=text_input,additional_units=additional_units))

class ConvertNumbersToWordsNode(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='ConvertNumbersToWords',display_name='Convert Numbers to Words',category='🔢NumberConvert',
            inputs=[io.String.Input('input_text',multiline=True,default='输入需要转换的文本')],outputs=[io.String.Output()],
            is_input_list=False,is_output_node=False)
    @classmethod
    async def execute(cls,input_text):
        from .NumberNormalization_EN import ConvertNumbersToWordsNode as Original
        return _output(Original().convert_numbers_to_words(input_text=input_text))

