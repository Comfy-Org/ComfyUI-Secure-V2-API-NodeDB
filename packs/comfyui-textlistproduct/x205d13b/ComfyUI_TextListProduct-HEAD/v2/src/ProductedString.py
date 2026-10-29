"""Public boundary adapter; native implementation is a byte-exact private copy."""
from comfy_api.latest import io, sdk
from .._native.src.ProductedString import ProductedString as _Native


class ProductedString(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='ProductedString', display_name='Producted String', category='TextListProduct',
            inputs=[io.String.Input('separator', default=', '), io.Int.Input('max_results', default=0, min=0, step=1), io.String.Input('newline_char', default='\n'), io.Custom('LIST').Input('list_a', optional=True, extra_dict={'forceInput': True}), io.Custom('LIST').Input('list_b', optional=True, extra_dict={'forceInput': True}), io.Custom('LIST').Input('list_c', optional=True, extra_dict={'forceInput': True}), io.Custom('LIST').Input('list_d', optional=True, extra_dict={'forceInput': True}), io.Custom('LIST').Input('list_e', optional=True, extra_dict={'forceInput': True}), io.Custom('LIST').Input('list_f', optional=True, extra_dict={'forceInput': True})], outputs=[io.String.Output(display_name='STRING', is_output_list=False), io.Custom('LIST').Output(display_name='list', is_output_list=False)])

    @classmethod
    async def execute(cls, **kwargs):
        values = {key: await value.value() if isinstance(value, sdk.ValueRef) else value
            for key, value in kwargs.items()}
        return io.NodeOutput(*_Native().combine_input_lists(**values))
