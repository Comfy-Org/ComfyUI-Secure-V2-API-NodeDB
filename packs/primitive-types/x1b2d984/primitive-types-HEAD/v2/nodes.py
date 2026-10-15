"""Scalar passthroughs with no host authority or durable pack state."""

import math

from comfy_api.latest import ComfyExtension, io

ABS_MAX = 1_125_899_906_842_624
MAX_TEXT_BYTES = 65_536
CATEGORY = "utils/Primitive Types"


class Int(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="int",
            display_name="int",
            category=CATEGORY,
            inputs=[
                io.Int.Input(
                    "value",
                    default=0,
                    min=-ABS_MAX,
                    max=ABS_MAX,
                    step=1,
                    display_mode=io.NumberDisplay.number,
                )
            ],
            outputs=[io.Int.Output()],
        )

    @classmethod
    def execute(cls, value):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("value must be an integer")
        if not -ABS_MAX <= value <= ABS_MAX:
            raise ValueError("value exceeds schema bounds")
        return io.NodeOutput(value)


class Float(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="float",
            display_name="float",
            category=CATEGORY,
            inputs=[
                io.Float.Input(
                    "value",
                    default=0,
                    min=-ABS_MAX,
                    max=ABS_MAX,
                    step=1,
                    display_mode=io.NumberDisplay.number,
                )
            ],
            outputs=[io.Float.Output()],
        )

    @classmethod
    def execute(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("value must be a number")
        if not -ABS_MAX <= value <= ABS_MAX or not math.isfinite(value):
            raise ValueError("value must be finite and within schema bounds")
        return io.NodeOutput(value)


def _text(text):
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
        raise ValueError("text exceeds 64 KiB UTF-8")
    return io.NodeOutput(text)


class String(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="string",
            display_name="string",
            category=CATEGORY,
            inputs=[io.String.Input("text", default="", multiline=False)],
            outputs=[io.String.Output()],
        )

    @classmethod
    def execute(cls, text):
        return _text(text)


class StringMultiline(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="string_multiline",
            display_name="string (multiline)",
            category=CATEGORY,
            inputs=[io.String.Input("text", default="", multiline=True)],
            outputs=[io.String.Output()],
        )

    @classmethod
    def execute(cls, text):
        return _text(text)


NODE_CLASS_MAPPINGS = {
    "int": Int,
    "float": Float,
    "string": String,
    "string_multiline": StringMultiline,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "int": "int",
    "float": "float",
    "string": "string",
    "string_multiline": "string (multiline)",
}


class PrimitiveTypesExtension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint():
    return PrimitiveTypesExtension()
