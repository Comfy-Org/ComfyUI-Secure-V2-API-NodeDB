"""Permission-free scalar, string, random, trigonometry, and logic nodes."""
from __future__ import annotations

import math
import re
import sys

from comfy_api.latest import io


_FLOAT_LIMIT = sys.float_info.max
_INT_LIMIT = sys.maxsize

TREE_MAIN = "Derfuu_Nodes"
TREE_VARIABLE = TREE_MAIN + "/Variables"
TREE_MATH = TREE_MAIN + "/Math"
TREE_FUNCTIONS = TREE_MAIN + "/Functions"
TREE_CONVERTERS = TREE_FUNCTIONS + "/Converters"
TREE_STRINGS = TREE_FUNCTIONS + "/String Operations"
TREE_TRIGONOMETRY = TREE_MATH + "/Trigonometry"


def _float(
    name: str,
    *,
    default: float = 1,
    minimum: float = -_FLOAT_LIMIT,
    maximum: float = _FLOAT_LIMIT,
    step: float = 0.01,
) -> io.Float.Input:
    return io.Float.Input(
        name,
        default=default,
        min=minimum,
        max=maximum,
        step=step,
        force_input=False,
    )


def _int(
    name: str,
    *,
    default: int = 1,
    minimum: int = -_INT_LIMIT,
    maximum: int = _INT_LIMIT,
    step: int = 1,
) -> io.Int.Input:
    return io.Int.Input(
        name,
        default=default,
        min=minimum,
        max=maximum,
        step=step,
        force_input=False,
    )


def _string(
    name: str,
    *,
    default: str = "",
    multiline: bool = False,
    dynamic_prompts: bool = False,
) -> io.String.Input:
    return io.String.Input(
        name,
        default=default,
        multiline=multiline,
        dynamic_prompts=dynamic_prompts,
        force_input=False,
    )


def _combo(name: str, options: list, *, default=None) -> io.Combo.Input:
    return io.Combo.Input(
        name,
        options=options,
        default=default,
        extra_dict={"forceInput": False},
    )


def _any(name: str, *, optional: bool = False) -> io.AnyType.Input:
    return io.AnyType.Input(
        name,
        optional=optional,
        extra_dict={"forceInput": False},
    )


def _output(kind, index: int, display_name: str):
    return kind.Output(f"output_{index}", display_name=display_name)


class FloatNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_Float",
            display_name="Float",
            category=TREE_VARIABLE,
            inputs=[_float("Value")],
            outputs=[_output(io.Float, 0, "FLOAT")],
        )

    @classmethod
    async def execute(cls, Value):
        return io.NodeOutput(Value)


class IntegerNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_Integer",
            display_name="Integer",
            category=TREE_VARIABLE,
            inputs=[_float("Value", step=1)],
            outputs=[_output(io.Int, 0, "INT")],
        )

    @classmethod
    async def execute(cls, Value: float):
        return io.NodeOutput(int(Value))


class StringNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_Text",
            display_name="Text",
            category=TREE_VARIABLE,
            inputs=[_string("Text")],
            outputs=[_output(io.String, 0, "STRING")],
        )

    @classmethod
    async def execute(cls, Text: str):
        return io.NodeOutput(Text)


class MultilineStringNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_Text_Box",
            display_name="Text Box",
            category=TREE_VARIABLE,
            inputs=[_string("Text", multiline=True)],
            outputs=[_output(io.String, 0, "STRING")],
        )

    @classmethod
    async def execute(cls, Text: str):
        return io.NodeOutput(Text)


class AsDynamicPromptsStringNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_DynamicPrompts_Text_Box",
            display_name="DynamicPrompts Text Box",
            category=TREE_VARIABLE,
            inputs=[_string(
                "Text", multiline=True, dynamic_prompts=True
            )],
            outputs=[_output(io.String, 0, "STRING")],
        )

    @classmethod
    async def execute(cls, Text: str):
        return io.NodeOutput(Text)


class StringConcat(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_String_Concatenate",
            display_name="String Concatenate",
            category=TREE_STRINGS,
            inputs=[
                _string("Prepend"),
                _string("Append"),
                _string("Delimiter", default=", "),
            ],
            outputs=[_output(io.String, 0, "TEXT")],
        )

    @classmethod
    async def execute(cls, Prepend, Append, Delimiter):
        return io.NodeOutput(f"{Prepend}{Delimiter}{Append}")


def _decode_pattern(pattern: str) -> str:
    return pattern.encode().decode("unicode_escape")


class StringReplace(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_String_Replace",
            display_name="String Replace",
            category=TREE_STRINGS,
            inputs=[
                _string("Text"),
                _string("Pattern"),
                _string("Replace_With"),
                _combo("Mode", ["Strict", "RegEx"]),
            ],
            outputs=[_output(io.String, 0, "TEXT")],
        )

    @classmethod
    async def execute(cls, Text, Pattern, Replace_With, Mode):
        pattern = _decode_pattern(Pattern)
        output = Text
        if Mode == "Strict":
            output = Text.replace(pattern, Replace_With)
        elif Mode == "RegEx":
            output = re.sub(
                pattern, Replace_With, output, flags=re.MULTILINE
            )
        return io.NodeOutput(output)


class SearchInText(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_Search_In_Text",
            display_name="Search In Text",
            category=TREE_STRINGS,
            inputs=[
                _string("Text"),
                _string("Pattern"),
                io.Boolean.Input(
                    "ConsiderRegister",
                    default=False,
                    extra_dict={"force": False},
                ),
                _combo("Mode", ["Strict", "RegEx"]),
            ],
            outputs=[
                _output(io.Boolean, 0, "BOOLEAN"),
                _output(io.Int, 1, "OCCURRENCES"),
            ],
        )

    @classmethod
    async def execute(cls, Text, Pattern, ConsiderRegister, Mode):
        pattern = _decode_pattern(Pattern)
        if not ConsiderRegister:
            Text = Text.lower()
            pattern = pattern.lower()
        output = None
        occurrences = 0
        if Mode == "Strict":
            # The V1 loop never advanced for an empty pattern. Treating it as
            # absent preserves the useful search intent without a guest DoS.
            if pattern:
                while pattern in Text:
                    output = True
                    occurrences += 1
                    Text = Text.replace(pattern, "", 1)
        elif Mode == "RegEx":
            occurrences = len(re.findall(pattern, Text))
            output = bool(occurrences)
        return io.NodeOutput(output, occurrences)


class RandomValue(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_Random",
            display_name="Random",
            category=TREE_FUNCTIONS,
            inputs=[
                _float("Value_A", default=0),
                _float("Value_B", default=1),
                _int("seed", default=0, minimum=0, maximum=2**32 - 1),
            ],
            outputs=[_output(io.Float, 0, "FLOAT")],
        )

    @classmethod
    async def execute(cls, Value_A, Value_B, seed):
        # RandomState is NumPy's legacy MT19937 stream, exactly the stream used
        # by `numpy.random.seed(seed); numpy.random.uniform(...)` in V1, but it
        # does not mutate another node's process-global generator.
        import numpy as np

        value = np.random.RandomState(int(seed)).uniform(Value_A, Value_B)
        return io.NodeOutput(float(value))


class Int2Float(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_Int_to_Float",
            display_name="Int to Float",
            category=TREE_CONVERTERS,
            inputs=[_int("Value")],
            outputs=[_output(io.Float, 0, "FLOAT")],
        )

    @classmethod
    async def execute(cls, Value):
        return io.NodeOutput(float(Value))


class CeilNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_Ceil",
            display_name="Ceil",
            category=TREE_CONVERTERS,
            inputs=[_float("Value")],
            outputs=[_output(io.Int, 0, "INT")],
        )

    @classmethod
    async def execute(cls, Value):
        return io.NodeOutput(int(math.ceil(Value)))


class FloorNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_Floor",
            display_name="Floor",
            category=TREE_CONVERTERS,
            inputs=[_float("Value")],
            outputs=[_output(io.Int, 0, "INT")],
        )

    @classmethod
    async def execute(cls, Value):
        return io.NodeOutput(int(math.floor(Value)))


class ABSNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_Absolute_value",
            display_name="Absolute value",
            category=TREE_CONVERTERS,
            inputs=[
                _float("Value"),
                io.Combo.Input("negative_out", options=[False, True]),
            ],
            outputs=[_output(io.Float, 0, "FLOAT")],
        )

    @classmethod
    async def execute(cls, Value, negative_out):
        # V1 exposed `negative_out` in INPUT_TYPES but named the function
        # parameter `Get_negative`, making normal keyword dispatch fail. Keep
        # the public schema and implement its documented behavior.
        return io.NodeOutput(-abs(Value) if negative_out else abs(Value))


class SumNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_Sum",
            display_name="Sum",
            category=TREE_MATH,
            inputs=[_float("Value_A"), _float("Value_B")],
            outputs=[_output(io.Float, 0, "FLOAT")],
        )

    @classmethod
    async def execute(cls, Value_A, Value_B):
        return io.NodeOutput(float(Value_A + Value_B))


class SubtractNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_Subtract",
            display_name="Subtract",
            category=TREE_MATH,
            inputs=[_float("Value_A"), _float("Value_B")],
            outputs=[_output(io.Float, 0, "FLOAT")],
        )

    @classmethod
    async def execute(cls, Value_A, Value_B):
        return io.NodeOutput(float(Value_A - Value_B))


class MultiplyNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_Multiply",
            display_name="Multiply",
            category=TREE_MATH,
            inputs=[_float("Value_A"), _float("Value_B")],
            outputs=[_output(io.Float, 0, "FLOAT")],
        )

    @classmethod
    async def execute(cls, Value_A, Value_B):
        return io.NodeOutput(float(Value_A * Value_B))


class DivideNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_Divide",
            display_name="Divide",
            category=TREE_MATH,
            inputs=[_float("Numerator"), _float("Denominator")],
            outputs=[_output(io.Float, 0, "FLOAT")],
        )

    @classmethod
    async def execute(cls, Numerator, Denominator):
        return io.NodeOutput(float(Numerator / Denominator))


class PowNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_Power",
            display_name="Power",
            category=TREE_MATH,
            inputs=[_float("Value"), _float("Exponent")],
            outputs=[_output(io.Float, 0, "FLOAT")],
        )

    @classmethod
    async def execute(cls, Value, Exponent):
        return io.NodeOutput(math.pow(Value, Exponent))


class SquareRootNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_Square_root",
            display_name="Square root",
            category=TREE_MATH,
            inputs=[_float("Value")],
            outputs=[
                _output(io.Float, 0, "FLOAT"),
                _output(io.Float, 1, "FLOAT"),
            ],
        )

    @classmethod
    async def execute(cls, Value):
        value = math.sqrt(Value)
        return io.NodeOutput(value, -value)


class SinNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_Sinus",
            display_name="Sinus",
            category=TREE_TRIGONOMETRY,
            inputs=[
                _float("value"),
                _combo("type_", ["RAD", "DEG"]),
                _combo("arcSin", [False, True]),
            ],
            outputs=[_output(io.Float, 0, "FLOAT")],
        )

    @classmethod
    async def execute(cls, value, type_="RAD", arcSin=False):
        if type_ == "DEG":
            value = math.radians(value)
        value = math.asin(value) if arcSin else math.sin(value)
        return io.NodeOutput(value)


class CosNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_Cosines",
            display_name="Cosines",
            category=TREE_TRIGONOMETRY,
            inputs=[
                _float("value"),
                _combo("type_", ["RAD", "DEG"]),
                _combo("arcCos", [False, True]),
            ],
            outputs=[_output(io.Float, 0, "FLOAT")],
        )

    @classmethod
    async def execute(cls, value, type_="RAD", arcCos=False):
        if type_ == "DEG":
            value = math.radians(value)
        value = math.acos(value) if arcCos else math.cos(value)
        return io.NodeOutput(value)


class tgNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_Tangent",
            display_name="Tangent",
            category=TREE_TRIGONOMETRY,
            inputs=[
                _float("value"),
                _combo("type_", ["RAD", "DEG"]),
                _combo("arcTan", [False, True]),
            ],
            outputs=[_output(io.Float, 0, "FLOAT")],
        )

    @classmethod
    async def execute(cls, value, type_="RAD", arcTan=False):
        if type_ == "DEG":
            value = math.radians(value)
        value = math.atan(value) if arcTan else math.tan(value)
        return io.NodeOutput(value)


class LogicNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_Logic_node",
            display_name="Logic node",
            category=TREE_FUNCTIONS,
            inputs=[
                _combo("Operation", [
                    "A > B",
                    "A < B",
                    "A = B",
                    "A AND B",
                    "A OR B",
                    "A XOR B",
                ]),
                _any("CompareValue_A"),
                _any("CompareValue_B", optional=True),
                _any("OnTrue", optional=True),
                _any("OnFalse", optional=True),
            ],
            outputs=[_output(io.AnyType, 0, "*")],
        )

    @classmethod
    async def execute(
        cls,
        CompareValue_A,
        CompareValue_B=False,
        OnTrue=False,
        OnFalse=False,
        Operation="A AND B",
    ):
        if Operation == "A > B":
            value = OnTrue if CompareValue_A > CompareValue_B else OnFalse
        elif Operation == "A < B":
            value = OnTrue if CompareValue_A < CompareValue_B else OnFalse
        elif Operation == "A = B":
            value = OnTrue if CompareValue_A == CompareValue_B else OnFalse
        elif Operation == "A AND B":
            value = OnTrue if CompareValue_A and CompareValue_B else OnFalse
        elif Operation == "A OR B":
            value = OnTrue if CompareValue_A or CompareValue_B else OnFalse
        elif Operation == "A XOR B":
            value = (
                OnTrue
                if not (CompareValue_A and CompareValue_B)
                and (CompareValue_A or CompareValue_B)
                else OnFalse
            )
        else:
            value = None
        return io.NodeOutput(value)


__all__ = [
    "ABSNode",
    "AsDynamicPromptsStringNode",
    "CeilNode",
    "CosNode",
    "DivideNode",
    "FloatNode",
    "FloorNode",
    "Int2Float",
    "IntegerNode",
    "LogicNode",
    "MultilineStringNode",
    "MultiplyNode",
    "PowNode",
    "RandomValue",
    "SearchInText",
    "SinNode",
    "SquareRootNode",
    "StringConcat",
    "StringNode",
    "StringReplace",
    "SubtractNode",
    "SumNode",
    "tgNode",
]
