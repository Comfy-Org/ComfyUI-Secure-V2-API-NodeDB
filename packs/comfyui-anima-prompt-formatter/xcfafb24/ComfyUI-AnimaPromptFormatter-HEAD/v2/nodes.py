"""Secure Nodes V2 implementation of Anima Prompt Formatter."""

from __future__ import annotations

from comfy_api.latest import ComfyExtension, io

MAX_TEXT_CHARACTERS = 1_048_576


def format_prompt(prompt: str | None) -> str:
    """Apply the pinned pack's exact newline/comma normalization rules."""
    if not prompt:
        return ""
    if not isinstance(prompt, str):
        raise TypeError("text must be a string")
    if len(prompt) > MAX_TEXT_CHARACTERS:
        raise ValueError(f"text exceeds the {MAX_TEXT_CHARACTERS}-character limit")
    text = prompt.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    cleaned_tags = [tag.strip() for tag in text.split(",")]
    return ", ".join(tag for tag in cleaned_tags if tag)


class AnimaPromptFormatter(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="AnimaPromptFormatter",
            display_name="Anima Prompt Formatter",
            category="prompt/formatter",
            inputs=[
                io.String.Input(
                    "text",
                    multiline=True,
                    default="",
                    extra_dict={"display": "prompt"},
                ),
            ],
            outputs=[
                io.String.Output("formatted_text", display_name="formatted_text"),
            ],
        )

    @classmethod
    def execute(cls, text: str) -> io.NodeOutput:
        return io.NodeOutput(format_prompt(text))


NODE_CLASS_MAPPINGS = {"AnimaPromptFormatter": AnimaPromptFormatter}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AnimaPromptFormatter": "Anima Prompt Formatter",
}


class AnimaPromptFormatterExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [AnimaPromptFormatter]


async def comfy_entrypoint() -> AnimaPromptFormatterExtension:
    return AnimaPromptFormatterExtension()


__all__ = [
    "MAX_TEXT_CHARACTERS",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "AnimaPromptFormatter",
    "AnimaPromptFormatterExtension",
    "comfy_entrypoint",
    "format_prompt",
]
