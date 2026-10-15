"""Real connected text producer for owned browser tests only; no inference."""
from comfy_api.latest import io

class WidgetBrowserStringSource(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='MOE_ZImageWidgetStringSource_TestOnly',
            display_name='Widget browser connected string source',category='testing',
            inputs=[io.String.Input('text',multiline=True)],
            outputs=[io.String.Output(tooltip='The prompt after applying the selected style.')])
    @classmethod
    def execute(cls,text):
        return io.NodeOutput(text)
    @classmethod
    def validate_inputs(cls,**kwargs):
        return True
