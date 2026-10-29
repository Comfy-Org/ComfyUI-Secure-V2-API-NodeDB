"""Public boundary adapter; native implementation is a byte-exact private copy."""
from comfy_api.latest import io, sdk
from .._native.src.MultilineStringToList import MultilineStringToList as _Native


class MultilineStringToList(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='MultilineStringToList', display_name='Multiline String to List', category='TextListProduct',
            inputs=[io.String.Input('text', default='', multiline=True, dynamic_prompts=False), io.Boolean.Input('trim_whitespace', default=True), io.Boolean.Input('keep_empty_lines', default=False)], outputs=[io.Custom('LIST').Output(display_name='list', is_output_list=False)])

    @classmethod
    async def execute(cls, **kwargs):
        values = {key: await value.value() if isinstance(value, sdk.ValueRef) else value
            for key, value in kwargs.items()}
        return io.NodeOutput(*_Native().convert_to_list(**values))
