"""Public boundary adapter; native implementation is a byte-exact private copy."""
from comfy_api.latest import io, sdk
from .._native.src.TextListProduct import TextListProduct as _Native


class TextListProduct(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='TextListProduct', display_name='Text List Product', category='TextListProduct',
            inputs=[io.String.Input('separator', default=', '), io.Int.Input('max_results', default=0, min=0, step=1), io.Custom('LIST').Input('list_a', extra_dict={'forceInput': True}), io.Custom('LIST').Input('list_b', extra_dict={'forceInput': True})], outputs=[io.Custom('LIST').Output(display_name='list', is_output_list=False)])

    @classmethod
    async def execute(cls, **kwargs):
        values = {key: await value.value() if isinstance(value, sdk.ValueRef) else value
            for key, value in kwargs.items()}
        return io.NodeOutput(*_Native().combine_input_lists(**values))
