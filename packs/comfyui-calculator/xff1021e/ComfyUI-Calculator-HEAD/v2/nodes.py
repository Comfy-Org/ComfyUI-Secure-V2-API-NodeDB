"""Secure Nodes V2 calculator registration."""

from __future__ import annotations

from comfy_api.latest import io


class Calculator(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Calculator",
            display_name="Calculator 🧮",
            category="Calculator 🧮",
            inputs=[],
            outputs=[],
        )

    @classmethod
    def execute(cls) -> io.NodeOutput:
        return io.NodeOutput()


NODE_CLASS_MAPPINGS = {"Calculator": Calculator}
NODE_DISPLAY_NAME_MAPPINGS = {"Calculator": "Calculator 🧮"}
