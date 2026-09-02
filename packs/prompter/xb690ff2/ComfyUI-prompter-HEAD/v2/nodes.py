"""Permission-free Prompt Saver & Loader execution node."""
from __future__ import annotations

from comfy_api.latest import io


_NEW_PROMPT = "[New Prompt]"


class PromptSaverNode(io.ComfyNode):
    """Pass prompt text through; the user's prompt library is frontend state."""

    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="PromptSaverNode",
            display_name="Prompt Saver & Loader",
            category="utils",
            inputs=[
                io.Combo.Input(
                    "selected_title",
                    options=[_NEW_PROMPT],
                    default=_NEW_PROMPT,
                    extra_dict={"comboSearch": True},
                ),
                io.Boolean.Input("auto_save", default=True),
                io.String.Input("title_name", default=""),
                io.String.Input("prompt_text", default="", multiline=True),
            ],
            outputs=[io.String.Output("prompt")],
        )

    @classmethod
    async def execute(
        cls,
        selected_title: str,
        auto_save: bool,
        title_name: str,
        prompt_text: str,
    ) -> io.NodeOutput:
        del selected_title, auto_save, title_name
        return io.NodeOutput(prompt_text)


__all__ = ["PromptSaverNode"]
