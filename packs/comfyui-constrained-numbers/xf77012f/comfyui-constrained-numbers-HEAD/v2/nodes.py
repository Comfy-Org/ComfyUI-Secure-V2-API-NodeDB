"""Public scalar boundaries; complete native clamps remain unchanged."""
from comfy_api.latest import io, sdk
from . import _native


class ConstrainedNonnegativeIntNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Constrained Int (n>=0)', display_name='Int (n>=0)', category='constrained_numbers',
            inputs=[io.Int.Input('value', default=0, min=0, max=9000000000000000, step=1, display_mode=io.NumberDisplay.number)], outputs=[io.Int.Output(display_name='INT')])

    @classmethod
    async def execute(cls, value):
        value = await value.value() if isinstance(value, sdk.ValueRef) else value
        return io.NodeOutput(*_native.ConstrainedNonnegativeIntNode().clamp(value))

class ConstrainedPositiveIntNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Constrained Int (n>0)', display_name='Int (n>0)', category='constrained_numbers',
            inputs=[io.Int.Input('value', default=1, min=1, max=9000000000000000, step=1, display_mode=io.NumberDisplay.number)], outputs=[io.Int.Output(display_name='INT')])

    @classmethod
    async def execute(cls, value):
        value = await value.value() if isinstance(value, sdk.ValueRef) else value
        return io.NodeOutput(*_native.ConstrainedPositiveIntNode().clamp(value))

class ConstrainedNonnegativeInt4nNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Constrained Int (4n>=0)', display_name='Int (4n>=0)', category='constrained_numbers',
            inputs=[io.Int.Input('value', default=0, min=0, max=9000000000000000, step=4, display_mode=io.NumberDisplay.number)], outputs=[io.Int.Output(display_name='INT')])

    @classmethod
    async def execute(cls, value):
        value = await value.value() if isinstance(value, sdk.ValueRef) else value
        return io.NodeOutput(*_native.ConstrainedNonnegativeInt4nNode().clamp(value))

class ConstrainedPositiveInt4nNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Constrained Int (4n>0)', display_name='Int (4n>0)', category='constrained_numbers',
            inputs=[io.Int.Input('value', default=4, min=4, max=9000000000000000, step=4, display_mode=io.NumberDisplay.number)], outputs=[io.Int.Output(display_name='INT')])

    @classmethod
    async def execute(cls, value):
        value = await value.value() if isinstance(value, sdk.ValueRef) else value
        return io.NodeOutput(*_native.ConstrainedPositiveInt4nNode().clamp(value))

class ConstrainedPositiveInt4np1Node(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Constrained Int (4n+1>0)', display_name='Int (4n+1>0)', category='constrained_numbers',
            inputs=[io.Int.Input('value', default=1, min=1, max=9000000000000001, step=4, display_mode=io.NumberDisplay.number)], outputs=[io.Int.Output(display_name='INT')])

    @classmethod
    async def execute(cls, value):
        value = await value.value() if isinstance(value, sdk.ValueRef) else value
        return io.NodeOutput(*_native.ConstrainedPositiveInt4np1Node().clamp(value))

class ConstrainedPositiveInt4np2Node(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Constrained Int (4n+2>0)', display_name='Int (4n+2>0)', category='constrained_numbers',
            inputs=[io.Int.Input('value', default=2, min=2, max=9000000000000002, step=4, display_mode=io.NumberDisplay.number)], outputs=[io.Int.Output(display_name='INT')])

    @classmethod
    async def execute(cls, value):
        value = await value.value() if isinstance(value, sdk.ValueRef) else value
        return io.NodeOutput(*_native.ConstrainedPositiveInt4np2Node().clamp(value))

class ConstrainedPositiveInt4np3Node(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Constrained Int (4n+3>0)', display_name='Int (4n+3>0)', category='constrained_numbers',
            inputs=[io.Int.Input('value', default=3, min=3, max=9000000000000003, step=4, display_mode=io.NumberDisplay.number)], outputs=[io.Int.Output(display_name='INT')])

    @classmethod
    async def execute(cls, value):
        value = await value.value() if isinstance(value, sdk.ValueRef) else value
        return io.NodeOutput(*_native.ConstrainedPositiveInt4np3Node().clamp(value))

class ConstrainedPositiveInt8np1Node(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Constrained Int (8n+1>0)', display_name='Int (8n+1>0)', category='constrained_numbers',
            inputs=[io.Int.Input('value', default=1, min=1, max=9000000000000001, step=8, display_mode=io.NumberDisplay.number)], outputs=[io.Int.Output(display_name='INT')])

    @classmethod
    async def execute(cls, value):
        value = await value.value() if isinstance(value, sdk.ValueRef) else value
        return io.NodeOutput(*_native.ConstrainedPositiveInt8np1Node().clamp(value))

class ConstrainedNonnegativeInt16nNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Constrained Int (16n>=0)', display_name='Int (16n>=0)', category='constrained_numbers',
            inputs=[io.Int.Input('value', default=0, min=0, max=9000000000000000, step=16, display_mode=io.NumberDisplay.number)], outputs=[io.Int.Output(display_name='INT')])

    @classmethod
    async def execute(cls, value):
        value = await value.value() if isinstance(value, sdk.ValueRef) else value
        return io.NodeOutput(*_native.ConstrainedNonnegativeInt16nNode().clamp(value))

class ConstrainedPositiveInt16nNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Constrained Int (16n>0)', display_name='Int (16n>0)', category='constrained_numbers',
            inputs=[io.Int.Input('value', default=16, min=16, max=9000000000000000, step=16, display_mode=io.NumberDisplay.number)], outputs=[io.Int.Output(display_name='INT')])

    @classmethod
    async def execute(cls, value):
        value = await value.value() if isinstance(value, sdk.ValueRef) else value
        return io.NodeOutput(*_native.ConstrainedPositiveInt16nNode().clamp(value))

class ConstrainedNonnegativeInt32nNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Constrained Int (32n>=0)', display_name='Int (32n>=0)', category='constrained_numbers',
            inputs=[io.Int.Input('value', default=0, min=0, max=9000000000000000, step=32, display_mode=io.NumberDisplay.number)], outputs=[io.Int.Output(display_name='INT')])

    @classmethod
    async def execute(cls, value):
        value = await value.value() if isinstance(value, sdk.ValueRef) else value
        return io.NodeOutput(*_native.ConstrainedNonnegativeInt32nNode().clamp(value))

class ConstrainedPositiveInt32nNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Constrained Int (32n>0)', display_name='Int (32n>0)', category='constrained_numbers',
            inputs=[io.Int.Input('value', default=32, min=32, max=9000000000000000, step=32, display_mode=io.NumberDisplay.number)], outputs=[io.Int.Output(display_name='INT')])

    @classmethod
    async def execute(cls, value):
        value = await value.value() if isinstance(value, sdk.ValueRef) else value
        return io.NodeOutput(*_native.ConstrainedPositiveInt32nNode().clamp(value))

class ConstrainedFloat0to1Node(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Constrained Float (0.0 to 1.0)', display_name='Float ∈ [0.0, 1.0]', category='constrained_numbers',
            inputs=[io.Float.Input('value', default=1.0, min=0.0, max=1.0, step=0.05, round=False, display_mode=io.NumberDisplay.number)], outputs=[io.Float.Output(display_name='FLOAT')])

    @classmethod
    async def execute(cls, value):
        value = await value.value() if isinstance(value, sdk.ValueRef) else value
        return io.NodeOutput(*_native.ConstrainedFloat0to1Node().clamp(value))

NODE_CLASS_MAPPINGS = {
    "Constrained Int (n>=0)": ConstrainedNonnegativeIntNode,
    "Constrained Int (n>0)": ConstrainedPositiveIntNode,
    "Constrained Int (4n>=0)": ConstrainedNonnegativeInt4nNode,
    "Constrained Int (4n>0)": ConstrainedPositiveInt4nNode,
    "Constrained Int (4n+1>0)": ConstrainedPositiveInt4np1Node,
    "Constrained Int (4n+2>0)": ConstrainedPositiveInt4np2Node,
    "Constrained Int (4n+3>0)": ConstrainedPositiveInt4np3Node,
    "Constrained Int (8n+1>0)": ConstrainedPositiveInt8np1Node,
    "Constrained Int (16n>=0)": ConstrainedNonnegativeInt16nNode,
    "Constrained Int (16n>0)": ConstrainedPositiveInt16nNode,
    "Constrained Int (32n>=0)": ConstrainedNonnegativeInt32nNode,
    "Constrained Int (32n>0)": ConstrainedPositiveInt32nNode,
    "Constrained Float (0.0 to 1.0)": ConstrainedFloat0to1Node
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Constrained Int (n>=0)": "Int (n>=0)",
    "Constrained Int (n>0)": "Int (n>0)",
    "Constrained Int (4n>=0)": "Int (4n>=0)",
    "Constrained Int (4n>0)": "Int (4n>0)",
    "Constrained Int (4n+1>0)": "Int (4n+1>0)",
    "Constrained Int (4n+2>0)": "Int (4n+2>0)",
    "Constrained Int (4n+3>0)": "Int (4n+3>0)",
    "Constrained Int (8n+1>0)": "Int (8n+1>0)",
    "Constrained Int (16n>=0)": "Int (16n>=0)",
    "Constrained Int (16n>0)": "Int (16n>0)",
    "Constrained Int (32n>=0)": "Int (32n>=0)",
    "Constrained Int (32n>0)": "Int (32n>0)",
    "Constrained Float (0.0 to 1.0)": "Float ∈ [0.0, 1.0]"
}
