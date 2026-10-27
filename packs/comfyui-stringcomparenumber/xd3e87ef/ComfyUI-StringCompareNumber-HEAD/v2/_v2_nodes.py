"""Public scalar boundary. Compute remains the retained original methods."""
from comfy_api.latest import io
from .string_compare_node import StringCompareNumber as _LegacyStringCompareNumber


class StringCompareNumber(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='StringCompareNumber', display_name='String Compare Number (字符串数字比较)',
            category='utils/string', description='',
            is_output_node=False, is_input_list=False,
            inputs=[
                io.String.Input('input_string', multiline=True, default='', tooltip='需要进行比较的字符串'),
                io.Combo.Input('delimiter', options=['comma (,)', 'semicolon (;)', 'space ( )', 'tab (\\t)', 'newline (\\n / \\r\\n / \\r)', 'any whitespace (空白字符)', 'pipe (|)', 'slash (/)', 'colon (:)', 'dash (-)', 'underscore (_)', 'dot (.)', 'none (whole string)', 'custom'], default='comma (,)', tooltip='字符串分割方式'),
                io.String.Input('custom_delimiter', default='', multiline=False, tooltip='自定义分隔符（仅当 delimiter 选择 custom 时生效）'),
                io.Combo.Input('operator', options=['==', '!=', '>', '>=', '<', '<='], default='==', tooltip='比较方式'),
                io.Float.Input('compare_value', default=0.0, min=-1e+18, max=1e+18, step=0.0001, tooltip='用于比较的数字'),
                io.Boolean.Input('strip_whitespace', default=True, tooltip='是否去除每段首尾空白字符'),
                io.Boolean.Input('ignore_empty', default=True, tooltip='是否忽略空字符串分段（不参与比较）'),
            ],
            outputs=[
                io.Int.Output(display_name='result'),
                io.String.Output(display_name='detail'),
            ],
        )

    @classmethod
    async def execute(cls, input_string, delimiter, custom_delimiter, operator, compare_value, strip_whitespace, ignore_empty):
        result = _LegacyStringCompareNumber().compare(input_string=input_string, delimiter=delimiter, custom_delimiter=custom_delimiter, operator=operator, compare_value=compare_value, strip_whitespace=strip_whitespace, ignore_empty=ignore_empty)
        return io.NodeOutput(*result)

NODE_CLASS_MAPPINGS = {
    'StringCompareNumber': StringCompareNumber,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    'StringCompareNumber': 'String Compare Number (字符串数字比较)',
}
