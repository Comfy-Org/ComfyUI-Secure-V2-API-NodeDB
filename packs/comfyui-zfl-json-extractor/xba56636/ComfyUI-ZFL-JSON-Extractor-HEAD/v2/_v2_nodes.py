"""Public scalar boundary. Compute remains the retained original methods."""
from comfy_api.latest import io
from ._original import JSONExtractorFourWay as _LegacyJSONExtractorFourWay


class JSONExtractorFourWay(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='JSONExtractorFourWay', display_name='ZFL JSON Extractor',
            category='CustomNodes/TextProcessing', description='',
            is_output_node=False, is_input_list=False,
            inputs=[
                io.String.Input('json_string', multiline=True, default=''),
                io.String.Input('key_1', multiline=None, default='name'),
                io.String.Input('key_2', multiline=None, default='instruct'),
                io.String.Input('key_3', multiline=None, default='text'),
                io.String.Input('key_4', multiline=None, default='other'),
                io.String.Input('delimiter', multiline=None, default='\n'),
            ],
            outputs=[
                io.String.Output(display_name='output_1'),
                io.String.Output(display_name='output_2'),
                io.String.Output(display_name='output_3'),
                io.String.Output(display_name='output_4'),
            ],
        )

    @classmethod
    async def execute(cls, json_string, key_1, key_2, key_3, key_4, delimiter):
        result = _LegacyJSONExtractorFourWay().extract_json(json_string=json_string, key_1=key_1, key_2=key_2, key_3=key_3, key_4=key_4, delimiter=delimiter)
        return io.NodeOutput(*result)

NODE_CLASS_MAPPINGS = {
    'JSONExtractorFourWay': JSONExtractorFourWay,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    'JSONExtractorFourWay': 'ZFL JSON Extractor',
}
