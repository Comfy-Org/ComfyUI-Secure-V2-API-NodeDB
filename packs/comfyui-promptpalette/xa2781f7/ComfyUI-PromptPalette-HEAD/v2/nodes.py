"""Secure Nodes V2 backend for Prompt Palette."""

from __future__ import annotations

from comfy_api.latest import io


DELIMITERS = ("comma", "space", "none")
MAX_TEXT_BYTES = 1_048_576


def _bounded_text(value: str | None, name: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if len(value.encode("utf-8")) > MAX_TEXT_BYTES:
        raise ValueError(f"{name} exceeds the {MAX_TEXT_BYTES}-byte limit")
    return value


def process_prompt(
    text: str,
    delimiter: str,
    line_break: bool,
    prefix: str | None = None,
) -> str:
    """Preserve the pinned pack's line filtering and formatting behavior."""
    text = _bounded_text(text, "text")
    prefix = _bounded_text(prefix, "prefix")
    if delimiter not in DELIMITERS:
        raise ValueError("delimiter must be comma, space, or none")
    if not isinstance(line_break, bool):
        raise TypeError("line_break must be a boolean")

    filtered_lines: list[str] = []
    for line in text.split("\n"):
        if not line.strip() or line.strip().startswith("//"):
            continue
        if "//" in line:
            line = line.split("//")[0].rstrip()
        if delimiter == "comma":
            line += ", "
        elif delimiter == "space":
            line += " "
        filtered_lines.append(line)

    result = ("\n" if line_break else "").join(filtered_lines)
    if prefix:
        if result:
            return prefix + ("\n" if line_break else "") + result
        return prefix
    return result


class PromptPalette(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="PromptPalette",
            display_name="Prompt Palette",
            category="utils",
            inputs=[
                io.String.Input("text", default="", multiline=True),
                io.Combo.Input(
                    "delimiter", options=list(DELIMITERS), default="comma"
                ),
                io.Boolean.Input("line_break", default=True),
                io.String.Input("prefix", optional=True, force_input=True),
            ],
            outputs=[io.String.Output()],
        )

    @classmethod
    def execute(
        cls,
        text: str,
        delimiter: str,
        line_break: bool,
        prefix: str | None = None,
    ) -> io.NodeOutput:
        return io.NodeOutput(process_prompt(text, delimiter, line_break, prefix))


NODE_CLASS_MAPPINGS = {"PromptPalette": PromptPalette}
