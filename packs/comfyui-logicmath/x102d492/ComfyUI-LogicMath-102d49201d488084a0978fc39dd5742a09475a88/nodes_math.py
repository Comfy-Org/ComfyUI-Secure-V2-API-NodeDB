import math
from typing import Any
from comfy_api.latest import io

def get_math_template():
    return io.MatchType.Template("math", allowed_types=[io.Int, io.Float])

class MathAdd(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        template = get_math_template()
        autogrow_template = io.Autogrow.TemplatePrefix(
            io.MatchType.Input("operand", template=template),
            prefix="operand",
            min=2,
            max=10
        )
        return io.Schema(
            node_id="MathAdd",
            display_name="Add",
            category="utils/math",
            inputs=[
                io.Autogrow.Input("operands", template=autogrow_template)
            ],
            outputs=[
                io.MatchType.Output(template=template)
            ],
        )

    @classmethod
    def execute(cls, operands: io.Autogrow.Type) -> io.NodeOutput:
        values = list(operands.values())
        result = values[0]
        for value in values[1:]:
            result = result + value
        return io.NodeOutput(result)


class MathSubtract(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        template = get_math_template()
        autogrow_template = io.Autogrow.TemplatePrefix(
            io.MatchType.Input("operand", template=template),
            prefix="operand",
            min=2,
            max=10
        )
        return io.Schema(
            node_id="MathSubtract",
            display_name="Subtract",
            category="utils/math",
            inputs=[
                io.Autogrow.Input("operands", template=autogrow_template)
            ],
            outputs=[
                io.MatchType.Output(template=template)
            ],
        )

    @classmethod
    def execute(cls, operands: io.Autogrow.Type) -> io.NodeOutput:
        values = list(operands.values())
        result = values[0]
        for value in values[1:]:
            result = result - value
        return io.NodeOutput(result)


class MathMultiply(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        template = get_math_template()
        autogrow_template = io.Autogrow.TemplatePrefix(
            io.MatchType.Input("operand", template=template),
            prefix="operand",
            min=2,
            max=10
        )
        return io.Schema(
            node_id="MathMultiply",
            display_name="Multiply",
            category="utils/math",
            inputs=[
                io.Autogrow.Input("operands", template=autogrow_template)
            ],
            outputs=[
                io.MatchType.Output(template=template)
            ],
        )

    @classmethod
    def execute(cls, operands: io.Autogrow.Type) -> io.NodeOutput:
        values = list(operands.values())
        result = values[0]
        for value in values[1:]:
            result = result * value
        return io.NodeOutput(result)


class MathDivide(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        template = get_math_template()
        autogrow_template = io.Autogrow.TemplatePrefix(
            io.MatchType.Input("operand", template=template),
            prefix="operand",
            min=2,
            max=10
        )
        return io.Schema(
            node_id="MathDivide",
            display_name="Divide",
            category="utils/math",
            inputs=[
                io.Autogrow.Input("operands", template=autogrow_template),
                io.Boolean.Input("handle_zero", default=True)
            ],
            outputs=[
                io.MatchType.Output(template=template)
            ],
        )

    @classmethod
    def validate_inputs(cls, operands: io.Autogrow.Type, handle_zero: bool) -> bool | str:
        if not handle_zero:
            values = list(operands.values())
            for value in values[1:]:
                if value == 0:
                    return "Division by zero is not allowed"
        return True

    @classmethod
    def execute(cls, operands: io.Autogrow.Type, handle_zero: bool) -> io.NodeOutput:
        values = list(operands.values())
        result = values[0]
        for value in values[1:]:
            if value == 0:
                if handle_zero:
                    return io.NodeOutput(0)
                else:
                    raise ValueError("Division by zero is not allowed")
            result = result / value
        return io.NodeOutput(result)


class MathPower(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        template = get_math_template()
        return io.Schema(
            node_id="MathPower",
            display_name="Power",
            category="utils/math",
            inputs=[
                io.MatchType.Input("base", template=template),
                io.MatchType.Input("exponent", template=template)
            ],
            outputs=[
                io.MatchType.Output(template=template)
            ],
        )

    @classmethod
    def execute(cls, base: Any, exponent: Any) -> io.NodeOutput:
        return io.NodeOutput(base ** exponent)


class MathFloor(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        template = get_math_template()
        return io.Schema(
            node_id="MathFloor",
            display_name="Floor",
            category="utils/math",
            inputs=[io.MatchType.Input("value", template=template)],
            outputs=[io.Int.Output(display_name="result")],
        )

    @classmethod
    def execute(cls, value: Any) -> io.NodeOutput:
        return io.NodeOutput(math.floor(value))


class MathCeil(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        template = get_math_template()
        return io.Schema(
            node_id="MathCeil",
            display_name="Ceil",
            category="utils/math",
            inputs=[io.MatchType.Input("value", template=template)],
            outputs=[io.Int.Output(display_name="result")],
        )

    @classmethod
    def execute(cls, value: Any) -> io.NodeOutput:
        return io.NodeOutput(math.ceil(value))


class MathRound(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        template = get_math_template()
        return io.Schema(
            node_id="MathRound",
            display_name="Round",
            category="utils/math",
            inputs=[
                io.MatchType.Input("value", template=template),
                io.Int.Input("decimals", default=0, min=0, max=10)
            ],
            outputs=[io.MatchType.Output(template=template)],
        )

    @classmethod
    def execute(cls, value: Any, decimals: int) -> io.NodeOutput:
        return io.NodeOutput(round(value, decimals))


class MathModulo(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        template = get_math_template()
        return io.Schema(
            node_id="MathModulo",
            display_name="Modulo",
            category="utils/math",
            inputs=[
                io.MatchType.Input("value_a", template=template),
                io.MatchType.Input("value_b", template=template)
            ],
            outputs=[io.MatchType.Output(template=template)],
        )

    @classmethod
    def execute(cls, value_a: Any, value_b: Any) -> io.NodeOutput:
        if value_b == 0:
            return io.NodeOutput(0)
        return io.NodeOutput(value_a % value_b)


class MathAbs(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        template = get_math_template()
        return io.Schema(
            node_id="MathAbs",
            display_name="Absolute",
            category="utils/math",
            inputs=[io.MatchType.Input("value", template=template)],
            outputs=[io.MatchType.Output(template=template)],
        )

    @classmethod
    def execute(cls, value: Any) -> io.NodeOutput:
        return io.NodeOutput(abs(value))


class MathSqrt(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        template = get_math_template()
        return io.Schema(
            node_id="MathSqrt",
            display_name="Square Root",
            category="utils/math",
            inputs=[io.MatchType.Input("value", template=template)],
            outputs=[io.Float.Output(display_name="result")],
        )

    @classmethod
    def execute(cls, value: Any) -> io.NodeOutput:
        if value < 0:
            return io.NodeOutput(0.0)
        return io.NodeOutput(math.sqrt(value))


class MathSin(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        template = get_math_template()
        return io.Schema(
            node_id="MathSin",
            display_name="Sine",
            category="utils/math/trigonometry",
            inputs=[
                io.MatchType.Input("angle", template=template),
                io.Combo.Input("unit", options=["Radians", "Degrees"], default="Radians")
            ],
            outputs=[io.Float.Output(display_name="result")],
        )

    @classmethod
    def execute(cls, angle: Any, unit: str) -> io.NodeOutput:
        if unit == "Degrees":
            angle = math.radians(angle)
        return io.NodeOutput(math.sin(angle))


class MathCos(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        template = get_math_template()
        return io.Schema(
            node_id="MathCos",
            display_name="Cosine",
            category="utils/math/trigonometry",
            inputs=[
                io.MatchType.Input("angle", template=template),
                io.Combo.Input("unit", options=["Radians", "Degrees"], default="Radians")
            ],
            outputs=[io.Float.Output(display_name="result")],
        )

    @classmethod
    def execute(cls, angle: Any, unit: str) -> io.NodeOutput:
        if unit == "Degrees":
            angle = math.radians(angle)
        return io.NodeOutput(math.cos(angle))


class MathTan(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        template = get_math_template()
        return io.Schema(
            node_id="MathTan",
            display_name="Tangent",
            category="utils/math/trigonometry",
            inputs=[
                io.MatchType.Input("angle", template=template),
                io.Combo.Input("unit", options=["Radians", "Degrees"], default="Radians")
            ],
            outputs=[io.Float.Output(display_name="result")],
        )

    @classmethod
    def execute(cls, angle: Any, unit: str) -> io.NodeOutput:
        if unit == "Degrees":
            angle = math.radians(angle)
        return io.NodeOutput(math.tan(angle))


class MathMin(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        template = get_math_template()
        autogrow_template = io.Autogrow.TemplatePrefix(
            io.MatchType.Input("value", template=template),
            prefix="value",
            min=2,
            max=10
        )
        return io.Schema(
            node_id="MathMin",
            display_name="Minimum",
            category="utils/math",
            inputs=[
                io.Autogrow.Input("values", template=autogrow_template)
            ],
            outputs=[
                io.MatchType.Output(template=template)
            ],
        )

    @classmethod
    def execute(cls, values: io.Autogrow.Type) -> io.NodeOutput:
        return io.NodeOutput(min(values.values()))


class MathMax(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        template = get_math_template()
        autogrow_template = io.Autogrow.TemplatePrefix(
            io.MatchType.Input("value", template=template),
            prefix="value",
            min=2,
            max=10
        )
        return io.Schema(
            node_id="MathMax",
            display_name="Maximum",
            category="utils/math",
            inputs=[
                io.Autogrow.Input("values", template=autogrow_template)
            ],
            outputs=[
                io.MatchType.Output(template=template)
            ],
        )

    @classmethod
    def execute(cls, values: io.Autogrow.Type) -> io.NodeOutput:
        return io.NodeOutput(max(values.values()))


class MathClamp(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        template = get_math_template()
        return io.Schema(
            node_id="MathClamp",
            display_name="Clamp",
            category="utils/math",
            inputs=[
                io.MatchType.Input("value", template=template),
                io.MatchType.Input("min_value", template=template),
                io.MatchType.Input("max_value", template=template)
            ],
            outputs=[io.MatchType.Output(template=template)],
        )

    @classmethod
    def execute(cls, value: Any, min_value: Any, max_value: Any) -> io.NodeOutput:
        return io.NodeOutput(max(min(value, max_value), min_value))


class MathNumberConvert(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MathNumberConvert",
            display_name="Number Convert",
            category="utils/math",
            inputs=[io.MatchType.Input("number_value", template=get_math_template())],
            outputs=[
                io.Int.Output(id="result_int", display_name="result_int"),
                io.Float.Output(id="result_float", display_name="result_float")
            ],
        )

    @classmethod
    def execute(cls, number_value: Any) -> io.NodeOutput:
        return io.NodeOutput(int(number_value), float(number_value))


class StringToNumber(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="StringToNumber",
            display_name="String To Number",
            category="utils/math",
            inputs=[
                io.String.Input("string", multiline=False),
                io.MatchType.Input("default_value", template=get_math_template(), optional=True)
            ],
            outputs=[io.MatchType.Output(template=get_math_template(), display_name="result")],
        )

    @classmethod
    def execute(cls, string: str, default_value: Any = 0) -> io.NodeOutput:
        try:
            if '.' in string:
                return io.NodeOutput(float(string))
            else:
                return io.NodeOutput(int(string))
        except (ValueError, TypeError):
            return io.NodeOutput(default_value)


class NumberToString(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="NumberToString",
            display_name="Number To String",
            category="utils/math",
            inputs=[io.MatchType.Input("number", template=get_math_template())],
            outputs=[io.String.Output(display_name="result")],
        )

    @classmethod
    def execute(cls, number: Any) -> io.NodeOutput:
        return io.NodeOutput(str(number))


class MathCompare(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        template = get_math_template()
        return io.Schema(
            node_id="MathCompare",
            display_name="Compare",
            category="utils/math",
            inputs=[
                io.MatchType.Input("value_a", template=template),
                io.MatchType.Input("value_b", template=template),
                io.Combo.Input("comparison", options=["Equal", "Not Equal", "Greater Than", "Less Than", "Greater Than or Equal", "Less Than or Equal"], default="Equal")
            ],
            outputs=[io.Boolean.Output(display_name="result")],
        )

    @classmethod
    def execute(cls, value_a: Any, value_b: Any, comparison: str) -> io.NodeOutput:
        if comparison == "Equal":
            res = value_a == value_b
        elif comparison == "Not Equal":
            res = value_a != value_b
        elif comparison == "Greater Than":
            res = value_a > value_b
        elif comparison == "Less Than":
            res = value_a < value_b
        elif comparison == "Greater Than or Equal":
            res = value_a >= value_b
        elif comparison == "Less Than or Equal":
            res = value_a <= value_b
        else:
            res = False
        return io.NodeOutput(res)


class MathOperation(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MathOperation",
            display_name="Math Operation (Example)",
            category="utils/math",
            inputs=[
                io.AnyType.Input("value_a"),
                io.AnyType.Input("value_b"),
                io.Combo.Input("operation", options=["Add", "Subtract", "Multiply", "Divide"], default="Add")
            ],
            outputs=[io.AnyType.Output(display_name="result")],
        )

    @classmethod
    def execute(cls, value_a: Any, value_b: Any, operation: str) -> io.NodeOutput:
        if operation == "Add":
            res = value_a + value_b
        elif operation == "Subtract":
            res = value_a - value_b
        elif operation == "Multiply":
            res = value_a * value_b
        elif operation == "Divide":
            res = value_a / value_b
        else:
            res = 0
        return io.NodeOutput(res)

class MathAspectRatio(io.ComfyNode):
    """Calculates the simplified aspect ratio integers from width and height."""

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MathAspectRatio",
            display_name="Aspect Ratio",
            category="utils/math",
            inputs=[
                io.Int.Input("width", default=1920, min=1),
                io.Int.Input("height", default=1080, min=1)
            ],
            outputs=[
                io.Int.Output(id="ratio_width", display_name="ratio_width"),
                io.Int.Output(id="ratio_height", display_name="ratio_height")
            ],
        )

    @classmethod
    def execute(cls, width: int, height: int) -> io.NodeOutput:
        gcd = math.gcd(width, height)
        return io.NodeOutput(width // gcd, height // gcd)