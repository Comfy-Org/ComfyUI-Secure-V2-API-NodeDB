"""Public boundary adapter; native implementation is a byte-exact private copy."""
from comfy_api.latest import io, sdk
from .._native.src.TextListToSequence import TextListToSequence as _Native


class TextListToSequence(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='TextListToSequence', display_name='Text List to Sequence', category='TextListProduct',
            inputs=[io.Custom('LIST').Input('text_list', extra_dict={'forceInput': True})], outputs=[io.String.Output(display_name='string', is_output_list=True)])

    @classmethod
    async def execute(cls, **kwargs):
        values = {key: await value.value() if isinstance(value, sdk.ValueRef) else value
            for key, value in kwargs.items()}
        return io.NodeOutput(*_Native().convert_to_sequence(**values))
