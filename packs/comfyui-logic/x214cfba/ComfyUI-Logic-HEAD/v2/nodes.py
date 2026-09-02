from comfy_api.latest import io

# Upstream declared its wildcard sockets with a hand-rolled ``AlwaysEqualProxy``
# -- a ``str`` subclass whose ``__eq__`` always returns True, so ComfyUI's type
# check passes for anything. V2 ships that wire type as ``io.AnyType``, so the
# shim is gone and the sockets behave identically.
#
# ``IfExecuteNode`` is absent here because it is absent upstream: it is
# commented out of the pinned NODE_CLASS_MAPPINGS. Worth recording that it is
# also the one node in this pack that could NOT have been converted -- it reads
# the host's global ``nodes.NODE_CLASS_MAPPINGS`` and instantiates an arbitrary
# node class by name, which is host-registry introspection rather than
# dataflow. Nothing is being quietly dropped: it was never registered.

COMPARE_FUNCTIONS = {
    "a == b": lambda a, b: a == b,
    "a != b": lambda a, b: a != b,
    "a < b": lambda a, b: a < b,
    "a > b": lambda a, b: a > b,
    "a <= b": lambda a, b: a <= b,
    "a >= b": lambda a, b: a >= b,
}


class String(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="String-🔬",
            display_name="String",
            category="Logic",
            inputs=[io.String.Input("value", default="", multiline=True)],
            outputs=[io.String.Output(display_name="STRING")],
        )

    @classmethod
    def execute(cls, value) -> io.NodeOutput:
        return io.NodeOutput(value)


class Int(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Int-🔬",
            display_name="Int",
            category="Logic",
            inputs=[io.Int.Input("value", default=0)],
            outputs=[io.Int.Output(display_name="INT")],
        )

    @classmethod
    def execute(cls, value) -> io.NodeOutput:
        return io.NodeOutput(value)


class Float(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Float-🔬",
            display_name="Float",
            category="Logic",
            inputs=[io.Float.Input("value", default=0, step=0.01)],
            outputs=[io.Float.Output(display_name="FLOAT")],
        )

    @classmethod
    def execute(cls, value) -> io.NodeOutput:
        return io.NodeOutput(value)


class Bool(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Bool-🔬",
            display_name="Bool",
            category="Logic",
            inputs=[io.Boolean.Input("value", default=False)],
            outputs=[io.Boolean.Output(display_name="BOOLEAN")],
        )

    @classmethod
    def execute(cls, value) -> io.NodeOutput:
        return io.NodeOutput(value)


class Compare(io.ComfyNode):
    """This nodes compares the two inputs and outputs the result of the comparison."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Compare-🔬",
            display_name="Compare",
            category="Logic",
            description=(
                "This nodes compares the two inputs and outputs the result of "
                "the comparison."
            ),
            inputs=[
                # Upstream wrote ``{"default": 0}`` on these wildcard sockets.
                # A wildcard type has no widget, so the socket is link-only and
                # the default was never rendered or used. io.AnyType has no
                # ``default`` for that reason; dropping it changes nothing a
                # user could observe.
                io.AnyType.Input("a"),
                io.AnyType.Input("b"),
                io.Combo.Input(
                    "comparison",
                    options=list(COMPARE_FUNCTIONS.keys()),
                    default="a == b"),
            ],
            outputs=[io.Boolean.Output(display_name="BOOLEAN")],
        )

    @classmethod
    def execute(cls, a, b, comparison) -> io.NodeOutput:
        return io.NodeOutput(COMPARE_FUNCTIONS[comparison](a, b))


class IfExecute(io.ComfyNode):
    """Returns IF_TRUE if ANY is True, otherwise IF_FALSE.

    Despite the upstream class name, this node executes nothing: both branches
    are already-computed inputs and it selects between them. The name is kept
    because the node id and display name are what workflows reference.
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="If ANY return A else B-🔬",
            display_name="If ANY return A else B",
            category="Logic",
            description=(
                "This node executes IF_TRUE if ANY is True, otherwise it "
                "executes IF_FALSE."
            ),
            inputs=[
                io.AnyType.Input("ANY"),
                io.AnyType.Input("IF_TRUE"),
                io.AnyType.Input("IF_FALSE"),
            ],
            outputs=[io.AnyType.Output(
                display_name="?",
                tooltip="Based on the value of ANY, either IF_TRUE or "
                        "IF_FALSE will be returned.")],
        )

    @classmethod
    def execute(cls, ANY, IF_TRUE, IF_FALSE) -> io.NodeOutput:
        return io.NodeOutput(IF_TRUE if ANY else IF_FALSE)


class DebugPrint(io.ComfyNode):
    """This node prints the input to the console.

    ``print`` is kept rather than redirected to the UI channel: the guest's
    stdout is captured by the transport and surfaced with the execution, so
    the value still reaches the operator, and the node's contract (an output
    node returning nothing) is unchanged.
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DebugPrint-🔬",
            display_name="DebugPrint",
            category="Logic",
            description="This node prints the input to the console.",
            inputs=[io.AnyType.Input("ANY")],
            outputs=[],
            is_output_node=True,
        )

    @classmethod
    def execute(cls, ANY) -> io.NodeOutput:
        print(ANY)
        return io.NodeOutput()


NODE_CLASS_MAPPINGS = {
    "Compare-🔬": Compare,
    "Int-🔬": Int,
    "Float-🔬": Float,
    "Bool-🔬": Bool,
    "String-🔬": String,
    "If ANY return A else B-🔬": IfExecute,
    "DebugPrint-🔬": DebugPrint,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Compare-🔬": "Compare",
    "Int-🔬": "Int",
    "Float-🔬": "Float",
    "Bool-🔬": "Bool",
    "String-🔬": "String",
    "If ANY return A else B-🔬": "If ANY return A else B",
    "DebugPrint-🔬": "DebugPrint",
}
