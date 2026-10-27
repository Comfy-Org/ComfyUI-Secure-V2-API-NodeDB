"""Public scalar boundary. Compute remains the retained original methods."""
from comfy_api.latest import io
from .text_modifier import TextModifier as _LegacyTextModifier


class TextModifier(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='TextModifier', display_name='Text Modifier (SG11)',
            category='SG11/text', description='',
            is_output_node=False, is_input_list=False,
            inputs=[
                io.String.Input('text', multiline=True),
                io.String.Input('find_text', multiline=None, default=''),
                io.String.Input('replace_text', multiline=None, default=''),
                io.Combo.Input('operation', options=['replace', 'delete']),
                io.Boolean.Input('case_sensitive', default=True),
            ],
            outputs=[
                io.String.Output(display_name='text'),
                io.Int.Output(display_name='count'),
            ],
        )

    @classmethod
    async def execute(cls, text, find_text, replace_text, operation, case_sensitive):
        result = _LegacyTextModifier().modify_text(text=text, find_text=find_text, replace_text=replace_text, operation=operation, case_sensitive=case_sensitive)
        return io.NodeOutput(*result)

NODE_CLASS_MAPPINGS = {
    'TextModifier': TextModifier,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    'TextModifier': 'Text Modifier (SG11)',
}
