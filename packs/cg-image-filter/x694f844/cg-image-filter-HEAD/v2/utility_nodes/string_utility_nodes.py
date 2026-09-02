"""String/list conversions retained as ordinary guest-side algorithms."""
from __future__ import annotations

from typing import Any

from comfy_api.latest import io

from .._secure_runtime import materialize


class StringToStringList(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="StringToStringList",
            display_name="String to String List",
            category="image_filter/helpers",
            inputs=[
                io.String.Input("string"),
                io.String.Input("split", default=",", tooltip="Split on this substring (or linebreak)"),
            ],
            outputs=[io.String.Output("string_list", is_output_list=True)],
        )

    @classmethod
    async def execute(cls, string, split):
        separator = "\n" if split == "linebreak" else split
        return io.NodeOutput([part.strip() for part in string.split(separator)])


class SplitByCommas(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Split String by Commas",
            display_name="Split String on character",
            category="image_filter/helpers",
            description="Split the input string and strips whitespace.",
            inputs=[
                io.String.Input("string"),
                io.String.Input("split", default=",", tooltip="Split on this substring (or linebreak)"),
            ],
            outputs=[
                io.String.Output("string1", display_name="string"),
                io.String.Output("string2", display_name="string"),
                io.String.Output("string3", display_name="string"),
                io.String.Output("string4", display_name="string"),
                io.String.Output("string5", display_name="string"),
                io.String.Output("all_as_list", display_name="all", is_output_list=True),
            ],
        )

    @classmethod
    async def execute(cls, string, split):
        separator = "\n" if split == "linebreak" else split
        bits = [part.strip() for part in string.split(separator)]
        five = (bits + [""] * 5)[:5]
        return io.NodeOutput(*five, bits)


class AnyListToString(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Any List to String",
            display_name="Any List to String",
            category="image_filter/helpers",
            inputs=[io.AnyType.Input("anything"), io.String.Input("join", default="")],
            outputs=[io.String.Output("string")],
            is_input_list=True,
        )

    @classmethod
    async def execute(cls, anything: list[Any], join: list[str]):
        values = await materialize(anything)
        separator = join[0] if join else ""
        return io.NodeOutput(separator.join(str(value) for value in values))


class StringToInt(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="cg_String to Int",
            display_name="String to Int",
            category="image_filter/helpers",
            inputs=[io.String.Input("string"), io.Int.Input("default")],
            outputs=[io.Int.Output("int")],
        )

    @classmethod
    async def execute(cls, string: str, default: int):
        try:
            value = int(string.strip())
        except (TypeError, ValueError):
            value = default
        return io.NodeOutput(value)


class StringToFloat(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="cg_String to Float",
            display_name="String to Float",
            category="image_filter/helpers",
            inputs=[io.String.Input("string"), io.Float.Input("default")],
            outputs=[io.Float.Output("float")],
        )

    @classmethod
    async def execute(cls, string: str, default: float):
        try:
            value = float(string.strip())
        except (TypeError, ValueError):
            value = default
        return io.NodeOutput(value)
