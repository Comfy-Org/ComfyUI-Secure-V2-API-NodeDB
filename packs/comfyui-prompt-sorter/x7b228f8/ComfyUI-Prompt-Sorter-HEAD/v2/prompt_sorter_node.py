"""One original STRING purpose, using the complete unchanged native algorithm."""
from comfy_api.latest import io
from . import _native

class IllustriousPromptSorter(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='IllustriousPromptSorter',
            display_name='Illustrious Prompt Sorter 🛠️',
            category='utils',
            is_input_list=False, is_output_node=False,
            inputs=[io.String.Input('text', multiline=True, force_input=True)],
            outputs=[io.String.Output(display_name='sorted_text', is_output_list=False)])

    @classmethod
    async def execute(cls, text):
        return io.NodeOutput(*_native.IllustriousPromptSorter().sort_prompt(text))

NODE_CLASS_MAPPINGS = {'IllustriousPromptSorter': IllustriousPromptSorter}
NODE_DISPLAY_NAME_MAPPINGS = {'IllustriousPromptSorter': 'Illustrious Prompt Sorter 🛠️'}
