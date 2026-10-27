"""Public scalar boundary. Compute remains the retained original methods."""
from comfy_api.latest import io
from .src.just_some_math.nodes import MultiplyInt as _LegacyMultiplyInt
from .src.just_some_math.nodes import MultiplyFloat as _LegacyMultiplyFloat
from .src.just_some_math.nodes import ArithemticInt as _LegacyArithemticInt
from .src.just_some_math.nodes import ArithemticFloat as _LegacyArithemticFloat


class MultiplyInt(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='JSM-Multiply-Int', display_name='Multiply Int',
            category='utils', description='Multiply Int node',
            is_output_node=False, is_input_list=False,
            inputs=[
                io.Int.Input('int', default=1, min=1, extra_dict={'display': 'number'}),
                io.Int.Input('multiplier', default=1, min=1, extra_dict={'display': 'number'}),
            ],
            outputs=[
                io.Int.Output(),
            ],
        )

    @classmethod
    async def execute(cls, int, multiplier):
        result = _LegacyMultiplyInt().multiply(int=int, multiplier=multiplier)
        return io.NodeOutput(*result)

class MultiplyFloat(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='JSM-Multiply-Float', display_name='Multiply Float',
            category='utils', description='Multiply Float node',
            is_output_node=False, is_input_list=False,
            inputs=[
                io.Float.Input('float', default=1.0, min=0.0, step=0.01, extra_dict={'display': 'number'}),
                io.Float.Input('multiplier', default=1.0, min=0.0, step=0.01, extra_dict={'display': 'number'}),
            ],
            outputs=[
                io.Float.Output(),
            ],
        )

    @classmethod
    async def execute(cls, float, multiplier):
        result = _LegacyMultiplyFloat().multiply(float=float, multiplier=multiplier)
        return io.NodeOutput(*result)

class ArithemticInt(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='JSM-Arithemtic-Int', display_name='Arithmetic Int',
            category='utils', description='Base arithemtic node for integer inputs',
            is_output_node=False, is_input_list=False,
            inputs=[
                io.Int.Input('a', default=0, extra_dict={'display': 'number'}),
                io.Int.Input('b', default=0, extra_dict={'display': 'number'}),
                io.Combo.Input('operation', options=['add', 'subtract', 'multiply', 'divide'], default='add'),
            ],
            outputs=[
                io.Float.Output(),
                io.Int.Output(),
            ],
        )

    @classmethod
    async def execute(cls, a=0, b=0, operation='add'):
        result = _LegacyArithemticInt().calculate(a=a, b=b, operation=operation)
        return io.NodeOutput(*result)

class ArithemticFloat(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='JSM-Arithemtic-Float', display_name='Arithmetic Float',
            category='utils', description='Base arithemtic node for float inputs',
            is_output_node=False, is_input_list=False,
            inputs=[
                io.Float.Input('a', default=0.0, extra_dict={'display': 'number'}),
                io.Float.Input('b', default=0.0, extra_dict={'display': 'number'}),
                io.Combo.Input('operation', options=['add', 'subtract', 'multiply', 'divide'], default='add'),
            ],
            outputs=[
                io.Float.Output(),
            ],
        )

    @classmethod
    async def execute(cls, a=0.0, b=0.0, operation='add'):
        result = _LegacyArithemticFloat().calculate(a=a, b=b, operation=operation)
        return io.NodeOutput(*result)

NODE_CLASS_MAPPINGS = {
    'JSM-Multiply-Int': MultiplyInt,
    'JSM-Multiply-Float': MultiplyFloat,
    'JSM-Arithemtic-Int': ArithemticInt,
    'JSM-Arithemtic-Float': ArithemticFloat,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    'JSM-Multiply-Int': 'Multiply Int',
    'JSM-Multiply-Float': 'Multiply Float',
    'JSM-Arithemtic-Int': 'Arithmetic Int',
    'JSM-Arithemtic-Float': 'Arithmetic Float',
}
