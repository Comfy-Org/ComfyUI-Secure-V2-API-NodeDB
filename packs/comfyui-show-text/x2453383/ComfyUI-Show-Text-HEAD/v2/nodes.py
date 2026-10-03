"""Secure Nodes V2 backend for ComfyUI Show Text."""

from __future__ import annotations

from comfy_api.latest import io


MAX_TEXT_ITEMS = 1024
MAX_TEXT_ITEM_BYTES = 1_048_576
MAX_TEXT_TOTAL_BYTES = 4_194_304


def _validate_text_list(text: list[str]) -> list[str]:
    if not isinstance(text, list):
        raise TypeError("text must be a list")
    if len(text) > MAX_TEXT_ITEMS:
        raise ValueError(f"text exceeds the {MAX_TEXT_ITEMS}-item limit")

    total_bytes = 0
    for item in text:
        if not isinstance(item, str):
            raise TypeError("every text item must be a string")
        item_bytes = len(item.encode("utf-8"))
        if item_bytes > MAX_TEXT_ITEM_BYTES:
            raise ValueError(
                f"a text item exceeds the {MAX_TEXT_ITEM_BYTES}-byte limit"
            )
        total_bytes += item_bytes
        if total_bytes > MAX_TEXT_TOTAL_BYTES:
            raise ValueError(
                f"text exceeds the {MAX_TEXT_TOTAL_BYTES}-byte total limit"
            )
    return text


class ComfyUIShowText(io.ComfyNode):
    """Pass a list of strings through and publish it for the mounted display."""

    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ShowText",
            display_name="Show Text",
            category="utils",
            is_input_list=True,
            is_output_node=True,
            inputs=[io.String.Input("text", force_input=True)],
            outputs=[io.String.Output(is_output_list=True)],
        )

    @classmethod
    def execute(cls, text: list[str]) -> io.NodeOutput:
        text = _validate_text_list(text)
        return io.NodeOutput(text, ui={"text": text})


NODE_CLASS_MAPPINGS = {"ShowText": ComfyUIShowText}
