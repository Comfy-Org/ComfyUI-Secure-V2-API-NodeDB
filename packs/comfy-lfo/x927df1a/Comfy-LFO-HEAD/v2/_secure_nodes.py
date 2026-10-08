"""Value-mode scalar wrappers; original waveform methods remain byte-exact."""
import math
from comfy_api.latest import io
from . import lfonodes as source

def make_node(node_id, original):
    class SecureWave(io.ComfyNode):
        SDK_REFS = False
        SDK_PERMISSIONS = ()
        FUNCTION = 'execute'

        @classmethod
        def define_schema(cls):
            return io.Schema(node_id=node_id, category=original.CATEGORY,
                inputs=[io.Float.Input(name, **spec[1]) for name, spec in original.INPUT_TYPES()['required'].items()],
                outputs=[io.Float.Output()])

        @classmethod
        def execute(cls, **inputs):
            for value in inputs.values():
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError('wave inputs must be finite nonboolean numeric scalars')
            result = getattr(original(), original.FUNCTION)(**inputs)
            if not math.isfinite(result[0]):
                raise ValueError('wave output must be a finite scalar')
            return io.NodeOutput(*result)
    SecureWave.__name__ = original.__name__ + 'Secure'
    SecureWave.__qualname__ = SecureWave.__name__
    SecureWave.__module__ = __name__
    return SecureWave

NODE_CLASS_MAPPINGS = {}
for node_id, original in source.NODE_CLASS_MAPPINGS.items():
    node = make_node(node_id, original)
    globals()[node.__name__] = node
    NODE_CLASS_MAPPINGS[node_id] = node
