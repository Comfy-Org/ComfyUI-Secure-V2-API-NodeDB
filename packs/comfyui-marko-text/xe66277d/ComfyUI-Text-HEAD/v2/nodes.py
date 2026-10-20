"""Public V2 wrappers over the unchanged four original string computations."""
from comfy_api.latest import io
from . import _algorithms

class ShowText(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='ShowText', category='MK/text',
            inputs=[io.String.Input('text', force_input=True)], outputs=[io.String.Output(display_name='text')],
            is_output_node=True)

    @classmethod
    def execute(cls, text):
        result = _algorithms.ShowText().show_text(text)
        return io.NodeOutput.from_dict(result)


class CombinationText(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CombinationText', category='MK/text',
            inputs=[io.String.Input('text1', multiline=True), io.String.Input('text2', multiline=True), io.String.Input('connector', default=',')], outputs=[io.String.Output(display_name='text')])

    @classmethod
    def execute(cls, text1, text2, connector):
        return io.NodeOutput(*_algorithms.CombinationText().combination_text(text1, text2, connector))


class PlaceholderText(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='PlaceholderText', category='MK/text',
            inputs=[io.String.Input('text1', multiline=True), io.String.Input('text2', multiline=True), io.String.Input('placeholder', default='$1,$2')], outputs=[io.String.Output(display_name='text')])

    @classmethod
    def execute(cls, text1, text2, placeholder):
        return io.NodeOutput(*_algorithms.PlaceholderText().placeholder_text(text1, text2, placeholder))


class ReplaceText(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='ReplaceText', category='MK/text',
            inputs=[io.String.Input('text', multiline=True), io.String.Input('old_string', default=''), io.String.Input('new_string', default='')], outputs=[io.String.Output(display_name='text')])

    @classmethod
    def execute(cls, text, old_string, new_string):
        return io.NodeOutput(*_algorithms.ReplaceText().replace_text(text, old_string, new_string))


NODE_CLASS_MAPPINGS = {
    'ShowText': ShowText,
    'CombinationText': CombinationText,
    'PlaceholderText': PlaceholderText,
    'ReplaceText': ReplaceText,
}
