"""V3 boundary only: all source algorithms and native catches remain unchanged."""
from comfy_api.latest import io
from .math_nodes import MATH_NODE_CLASS_MAPPINGS as SOURCES, MATH_NODE_DISPLAY_NAME_MAPPINGS
from . import _limits

KINDS = {'INT': io.Int, 'FLOAT': io.Float, 'STRING': io.String, 'BOOLEAN': io.Boolean, '*': io.AnyType}
NUMBER = io.Custom('INT,FLOAT')

def schema(node_id, source):
    inputs = []
    for group, fields in source.INPUT_TYPES().items():
        for name, row in fields.items():
            kind = row[0]
            options = dict(row[1]) if len(row) > 1 else {}
            if group == 'optional':
                options['optional'] = True
            if isinstance(kind, list):
                inputs.append(io.Combo.Input(name, options=kind, **options))
            elif str(kind) == 'INT,FLOAT':
                optional = options.pop('optional', False)
                inputs.append(NUMBER.Input(name, optional=optional, extra_dict=options))
            else:
                # Use actual typed inputs so manifest reconstruction retains
                # their required attributes. Explicit None preserves omitted
                # source STRING multiline rather than injecting a new option.
                if str(kind) == 'STRING' and 'multiline' not in options:
                    options['multiline'] = None
                inputs.append(KINDS[str(kind)].Input(name, **options))
    listed = getattr(source, 'OUTPUT_IS_LIST', ())
    outputs = [(NUMBER if str(kind) == 'INT,FLOAT' else KINDS[str(kind)]).Output(
        display_name=source.RETURN_NAMES[i], is_output_list=listed[i] if i < len(listed) else False)
        for i, kind in enumerate(source.RETURN_TYPES)]
    return io.Schema(node_id=node_id, display_name=MATH_NODE_DISPLAY_NAME_MAPPINGS[node_id],
        category=source.CATEGORY, inputs=inputs, outputs=outputs)

def create(node_id, source):
    class Converted(io.ComfyNode):
        SDK_REFS = False
        SDK_PERMISSIONS = ()
        FUNCTION = 'execute'

        @classmethod
        def define_schema(cls):
            return schema(node_id, source)

        @classmethod
        def validate_inputs(cls, input_types):
            return source.VALIDATE_INPUTS(input_types)

        @classmethod
        def execute(cls, **values):
            _limits.before(source, values)
            result = getattr(source(), source.FUNCTION)(**values)
            if result is None:
                # Preserve a native unsupported-option return, not fabricated slots.
                return None
            return io.NodeOutput(*_limits.after(result))
    Converted.__name__ = source.__name__ + 'Secure'
    Converted.__qualname__ = Converted.__name__
    Converted.__module__ = __name__
    return Converted

NODE_CLASS_MAPPINGS = {node_id: create(node_id, source) for node_id, source in SOURCES.items()}
globals().update({cls.__name__: cls for cls in NODE_CLASS_MAPPINGS.values()})
