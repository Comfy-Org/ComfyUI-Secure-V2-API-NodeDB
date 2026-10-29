"""Public boundary adapter; native implementation is a byte-exact private copy."""
from comfy_api.latest import io, sdk
from .._native.src.StringsToList import StringsToList as _Native


class StringsToList(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='StringsToList', display_name='Strings to List', category='TextListProduct',
            inputs=[io.String.Input('text_a', optional=True, force_input=True), io.String.Input('text_b', optional=True, force_input=True), io.String.Input('text_c', optional=True, force_input=True), io.String.Input('text_d', optional=True, force_input=True), io.String.Input('text_e', optional=True, force_input=True), io.String.Input('text_f', optional=True, force_input=True), io.String.Input('text_g', optional=True, force_input=True)], outputs=[io.Custom('LIST').Output(display_name='list', is_output_list=False)])

    @classmethod
    async def execute(cls, **kwargs):
        values = {key: await value.value() if isinstance(value, sdk.ValueRef) else value
            for key, value in kwargs.items()}
        return io.NodeOutput(*_Native().collect_strings(**values))
