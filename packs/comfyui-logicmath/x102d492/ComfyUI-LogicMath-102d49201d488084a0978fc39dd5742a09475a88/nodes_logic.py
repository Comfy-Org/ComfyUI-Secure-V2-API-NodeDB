from typing import Any
from comfy_api.latest import io

class LogicIF(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="LogicIF",
            display_name="IF",
            category="utils/logic",
            inputs=[
                io.Boolean.Input("if_condition"),
                io.AnyType.Input("when_true"),
                io.AnyType.Input("when_false", optional=True)
            ],
            outputs=[io.AnyType.Output(display_name="result")],
        )

    @classmethod
    def execute(cls, if_condition: bool, when_true: Any, when_false: Any = None) -> io.NodeOutput:
        if if_condition:
            return io.NodeOutput(when_true)
        else:
            return io.NodeOutput(when_false)


class LogicAND(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        autogrow_template = io.Autogrow.TemplatePrefix(
            io.Boolean.Input("input"),
            prefix="input",
            min=2,
            max=10
        )
        return io.Schema(
            node_id="LogicAND",
            display_name="AND",
            category="utils/logic",
            inputs=[
                io.Autogrow.Input("inputs", template=autogrow_template)
            ],
            outputs=[io.Boolean.Output()],
        )

    @classmethod
    def execute(cls, inputs: io.Autogrow.Type) -> io.NodeOutput:
        values = list(inputs.values())
        result = all(values)
        return io.NodeOutput(result)


class LogicOR(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        autogrow_template = io.Autogrow.TemplatePrefix(
            io.Boolean.Input("input"),
            prefix="input",
            min=2,
            max=10
        )
        return io.Schema(
            node_id="LogicOR",
            display_name="OR",
            category="utils/logic",
            inputs=[
                io.Autogrow.Input("inputs", template=autogrow_template)
            ],
            outputs=[io.Boolean.Output()],
        )

    @classmethod
    def execute(cls, inputs: io.Autogrow.Type) -> io.NodeOutput:
        values = list(inputs.values())
        result = any(values)
        return io.NodeOutput(result)


class LogicNOT(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="LogicNOT",
            display_name="NOT",
            category="utils/logic",
            inputs=[io.Boolean.Input("input")],
            outputs=[io.Boolean.Output()],
        )

    @classmethod
    def execute(cls, input: bool) -> io.NodeOutput:
        return io.NodeOutput(not input)


class LogicXOR(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        autogrow_template = io.Autogrow.TemplatePrefix(
            io.Boolean.Input("input"),
            prefix="input",
            min=2,
            max=10
        )
        return io.Schema(
            node_id="LogicXOR",
            display_name="XOR",
            category="utils/logic",
            inputs=[
                io.Autogrow.Input("inputs", template=autogrow_template)
            ],
            outputs=[io.Boolean.Output()],
        )

    @classmethod
    def execute(cls, inputs: io.Autogrow.Type) -> io.NodeOutput:
        values = list(inputs.values())
        # XOR for multiple inputs: True if odd number of True inputs
        result = values[0]
        for val in values[1:]:
            result = result != val
        return io.NodeOutput(result)
