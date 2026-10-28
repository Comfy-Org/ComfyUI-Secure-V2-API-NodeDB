"""Complete public V2 boundary. Original implementation modules unchanged."""
from comfy_api.latest import io

def _output(value):
    if type(value) is dict:
        return io.NodeOutput(*value['result'],ui=value.get('ui'),expand=value.get('expand'),block_execution=value.get('block_execution'))
    return io.NodeOutput(*value)

class MargeStringList(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='MargeStringList',display_name='Merge String List',category='text/tags',
            inputs=[io.String.Input('text',force_input=True,multiline=True),io.String.Input('separator',default=', '),io.Boolean.Input('sort_tags',default=False),io.Boolean.Input('case_sensitive',default=False)],outputs=[io.String.Output(display_name='text')],
            is_input_list=True,is_output_node=False)
    @classmethod
    async def execute(cls,text,separator=', ',sort_tags=False,case_sensitive=False):
        from .nodes import MargeStringList as Original
        return _output(Original().merge(text=text,separator=separator,sort_tags=sort_tags,case_sensitive=case_sensitive))

