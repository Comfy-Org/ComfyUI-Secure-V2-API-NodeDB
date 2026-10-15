"""V3 boundary; original template loader/composition algorithms unchanged."""
from comfy_api.latest import io
from . import _resources
_resources.verify()
from . import prompt_styler as source
from . import _limits

NODE_DISPLAY_NAME_MAPPINGS = source.NODE_DISPLAY_NAME_MAPPINGS

class ComfyUIStylerSecure(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()
    FUNCTION = 'execute'

    @classmethod
    def define_schema(cls):
        fields = []
        for name, row in source.NODE_CLASS_MAPPINGS['ComfyUIStyler'].INPUT_TYPES()['required'].items():
            kind, options = row[0], dict(row[1]) if len(row) > 1 else {}
            if isinstance(kind, list):
                fields.append(io.Combo.Input(name, options=kind, **options))
            elif kind == 'STRING':
                fields.append(io.String.Input(name, **options))
            else:
                fields.append(io.Boolean.Input(name, **options))
        return io.Schema(node_id='ComfyUIStyler', display_name='ComfyUI Styler',
            category='ALL_IN_ONE_STYLER', inputs=fields,
            outputs=[io.String.Output(display_name='text_positive'), io.String.Output(display_name='text_negative')])

    @classmethod
    def execute(cls, **values):
        _limits.before(values, source)
        result = source.NODE_CLASS_MAPPINGS['ComfyUIStyler']().prompt_styler(**values)
        return io.NodeOutput(*result)

NODE_CLASS_MAPPINGS = {'ComfyUIStyler': ComfyUIStylerSecure}
