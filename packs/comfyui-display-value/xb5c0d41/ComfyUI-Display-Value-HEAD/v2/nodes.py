"""Secure Nodes V2 backend for ComfyUI Display Value."""

from __future__ import annotations

import json
from typing import Any

from comfy_api.latest import ComfyExtension, io


MAX_VALUE_CHARS = 1_048_576


def format_value(value: Any) -> str:
    """Preserve the pinned formatter while bounding its display payload."""
    if isinstance(value, list):
        value = value[0]
    if isinstance(value, (str, int, float, bool)):
        result = str(value)
    elif value is not None:
        try:
            result = json.dumps(value)
        except Exception:
            try:
                result = str(value)
            except Exception:
                result = "source exists, but could not be serialized."
    else:
        result = "None"
    if len(result) > MAX_VALUE_CHARS:
        raise ValueError(f"formatted value exceeds {MAX_VALUE_CHARS} characters")
    return result


class DisplayValue(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DisplayValue",
            display_name="Display Value",
            category="utils",
            is_input_list=True,
            is_output_node=True,
            inputs=[io.AnyType.Input("value")],
            outputs=[io.String.Output(is_output_list=True)],
        )

    @classmethod
    def execute(cls, value: Any = None) -> io.NodeOutput:
        value_string = format_value(value)
        return io.NodeOutput([value_string], ui={"value": [value_string]})


NODE_CLASS_MAPPINGS = {"DisplayValue": DisplayValue}


class DisplayValueExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [DisplayValue]


async def comfy_entrypoint() -> DisplayValueExtension:
    return DisplayValueExtension()
