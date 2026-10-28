"""Public scalar boundary with immutable source-derived schema defaults."""
from comfy_api.latest import io, sdk
from ._native import WordReplacer as _Native

RULES_DEFAULT = '# These are the default replacement rules\ncat: dog\nblue: red\nhappy: ecstatic\nold: new\n'


class WordReplacer(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WordReplacer', display_name='Word Replacer (Validated)', category='text/utils',
            inputs=[io.String.Input('text', multiline=True, default='The quick brown fox jumps over the lazy cat.'),
                io.String.Input('rules', multiline=True, default=RULES_DEFAULT,
                    tooltip="Format: 'find:replace'. Every non-empty line must contain a colon.")],
            outputs=[io.String.Output(display_name='output_text')])

    @classmethod
    async def execute(cls, **kwargs):
        values = {key: await value.value() if isinstance(value, sdk.ValueRef) else value
            for key, value in kwargs.items()}
        return io.NodeOutput(*_Native().replace_words(**values))
