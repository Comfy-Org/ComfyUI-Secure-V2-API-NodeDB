"""Public boundary adapter; native implementation is a byte-exact private copy."""
from comfy_api.latest import io, sdk
from .._native.src.PromptPairConcat import PromptPairConcat as _Native


class PromptPairConcat(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='PromptPairConcat', display_name='Prompt Pair Concat', category='TextListProduct',
            inputs=[io.String.Input('separator', default=','), io.Combo.Input('isClean', options=['true', 'false']), io.Combo.Input('trailing_separator', options=['false', 'true']), io.Custom('LIST').Input('list_a', optional=True, extra_dict={'forceInput': True}), io.Custom('LIST').Input('list_b', optional=True, extra_dict={'forceInput': True})], outputs=[io.Custom('LIST').Output(display_name='list', is_output_list=False)])

    @classmethod
    async def execute(cls, **kwargs):
        values = {key: await value.value() if isinstance(value, sdk.ValueRef) else value
            for key, value in kwargs.items()}
        return io.NodeOutput(*_Native().concat_lists(**values))
