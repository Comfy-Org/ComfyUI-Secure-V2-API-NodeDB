"""Public scalar boundary. Compute remains the retained original methods."""
from comfy_api.latest import io
from ._original import toUpper as _LegacytoUpper
from ._original import toMiddle as _LegacytoMiddle
from ._original import toLower as _LegacytoLower


class toUpper(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='String to Upper Case', display_name='String to Upper Case',
            category='Utils', description='',
            is_output_node=False, is_input_list=False,
            inputs=[
                io.String.Input('text', multiline=None),
            ],
            outputs=[
                io.String.Output(),
            ],
        )

    @classmethod
    async def execute(cls, text):
        result = _LegacytoUpper().toUpper(text=text)
        return io.NodeOutput(*result)

class toMiddle(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='String to Title Case', display_name='String to Title Case',
            category='Utils', description='',
            is_output_node=False, is_input_list=False,
            inputs=[
                io.String.Input('text', multiline=None),
            ],
            outputs=[
                io.String.Output(),
            ],
        )

    @classmethod
    async def execute(cls, text):
        result = _LegacytoMiddle().toUpper(text=text)
        return io.NodeOutput(*result)

class toLower(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='String to Lower Case', display_name='String to Lower Case',
            category='Utils', description='',
            is_output_node=False, is_input_list=False,
            inputs=[
                io.String.Input('text', multiline=None),
            ],
            outputs=[
                io.String.Output(),
            ],
        )

    @classmethod
    async def execute(cls, text):
        result = _LegacytoLower().toUpper(text=text)
        return io.NodeOutput(*result)

NODE_CLASS_MAPPINGS = {
    'String to Upper Case': toUpper,
    'String to Title Case': toMiddle,
    'String to Lower Case': toLower,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    'String to Upper Case': 'String to Upper Case',
    'String to Title Case': 'String to Title Case',
    'String to Lower Case': 'String to Lower Case',
}
