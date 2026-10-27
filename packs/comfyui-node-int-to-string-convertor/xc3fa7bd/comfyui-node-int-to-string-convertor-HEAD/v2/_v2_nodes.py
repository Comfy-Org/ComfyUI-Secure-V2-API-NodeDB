"""Existing public V2 boundary; original str(INT) implementation unchanged."""
from comfy_api.latest import io,sdk
from .int_to_string_conversion import IVRIntToString as _Original

class IVRIntToString(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Int To String',display_name='Int To String Convertor',
            inputs=[io.Int.Input('INT_input',force_input=True)],outputs=[io.String.Output()])
    @classmethod
    async def execute(cls,INT_input):
        value=await INT_input.value() if isinstance(INT_input,sdk.ValueRef) else INT_input
        return io.NodeOutput(*_Original().convert(value))
