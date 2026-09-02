"""Secure, sandboxed implementations of the three Prompt Stash nodes."""
from __future__ import annotations

import hashlib
from typing import Any

from comfy_api.latest import io, sdk


_INTERACTION_KIND = "prompt-await"
_INTERACTION_VARIANT = "prompt-stash-passthrough-v1"
_INTERACTION_TIMEOUT = 540.0
_MAX_EDITED_TEXT = 1_000_000


def _selected_text(
    use_input_text: bool,
    text: str | None,
    prompt_text: str,
) -> str:
    if use_input_text and text is not None:
        return str(text)
    return str(prompt_text)


def _fingerprint(
    _cls: type, *, use_input_text: bool = False, text: str | None = "",
    prompt_text: str = "", **_kwargs: Any,
) -> str:
    """Match the pinned node's active-input cache fingerprint."""
    digest = hashlib.sha256()
    digest.update(str(bool(use_input_text)).encode())
    digest.update(str(prompt_text).encode())
    if use_input_text and text is not None:
        digest.update(str(text).encode())
    return digest.hexdigest()


def _lazy_text(
    _cls: type, *, use_input_text: bool = False, **_kwargs: Any,
) -> list[str]:
    return ["text"] if use_input_text else []


class PromptStashSaver(io.ComfyNode):
    """Choose prompt-box or linked text; the library stays frontend-owned."""

    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="PromptStashSaver",
            display_name="Prompt Stash Saver",
            category="utils",
            inputs=[
                io.Boolean.Input(
                    "use_input_text", optional=True, default=False,
                    label_on="Use Input", label_off="Use Prompt",
                ),
                io.String.Input(
                    "text", optional=True, default="", force_input=True,
                    lazy=True, tooltip="Optional input text",
                ),
                io.String.Input(
                    "prompt_text", optional=True, default="", multiline=True,
                    placeholder="Enter prompt text",
                ),
                io.String.Input(
                    "save_as_key", optional=True, default="",
                    placeholder="Enter key to save as",
                ),
                io.Combo.Input(
                    "load_saved", options=["None"], optional=True,
                    default="None",
                ),
                io.Combo.Input(
                    "prompt_lists", options=["default"], optional=True,
                    default="default",
                ),
            ],
            outputs=[io.String.Output("text")],
        )

    @classmethod
    async def execute(
        cls,
        use_input_text: bool = False,
        text: str | None = "",
        prompt_text: str = "",
        save_as_key: str = "",
        load_saved: str = "None",
        prompt_lists: str = "default",
    ) -> io.NodeOutput:
        del save_as_key, load_saved, prompt_lists
        output = _selected_text(use_input_text, text, prompt_text)
        return io.NodeOutput(
            output,
            ui={"prompt_stash": {
                "text": output,
                "adopt_input": bool(use_input_text and text is not None),
            }},
        )

    fingerprint_inputs = classmethod(_fingerprint)
    check_lazy_status = classmethod(_lazy_text)

    @classmethod
    def validate_inputs(
        cls, load_saved: str = "None", prompt_lists: str = "default",
        **_kwargs: Any,
    ) -> bool:
        del load_saved, prompt_lists
        # Those combos are frontend library state, not execution policy.
        return True


class PromptStashPassthrough(io.ComfyNode):
    """Choose text and optionally wait for an invocation-scoped edit."""

    SDK_REFS = True
    SDK_PERMISSIONS = ("ui.interact",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="PromptStashPassthrough",
            display_name="Prompt Stash Passthrough",
            category="utils",
            inputs=[
                io.Boolean.Input(
                    "use_input_text", optional=True, default=False,
                    label_on="Use Input", label_off="Use Prompt",
                ),
                io.String.Input(
                    "text", optional=True, default="", force_input=True,
                    lazy=True, tooltip="Optional input text",
                ),
                io.String.Input(
                    "prompt_text", optional=True, default="", multiline=True,
                    placeholder="Enter prompt text",
                ),
                io.Boolean.Input(
                    "pause_to_edit", optional=True, default=False,
                    label_on="Yes", label_off="No",
                ),
            ],
            outputs=[io.String.Output("text")],
        )

    @classmethod
    async def execute(
        cls,
        use_input_text: bool = False,
        text: str | None = "",
        prompt_text: str = "",
        pause_to_edit: bool = False,
    ) -> io.NodeOutput:
        output = _selected_text(use_input_text, text, prompt_text)
        if pause_to_edit:
            response = await sdk.ctx().interact.request(
                _INTERACTION_KIND,
                {
                    "variant": _INTERACTION_VARIANT,
                    "text": output,
                    "title": "Prompt Stash Passthrough",
                },
                timeout=_INTERACTION_TIMEOUT,
            )
            if not isinstance(response, dict):
                raise TypeError("Prompt Stash response must be an object")
            if response.get("action") != "continue":
                raise ValueError("Prompt Stash response action must be 'continue'")
            edited = response.get("text")
            if not isinstance(edited, str):
                raise TypeError("Prompt Stash response text must be a string")
            if len(edited) > _MAX_EDITED_TEXT:
                raise ValueError("Prompt Stash response text exceeds the limit")
            output = edited

        return io.NodeOutput(
            output,
            ui={"prompt_stash": {
                "text": output,
                "adopt_input": bool(
                    (use_input_text and text is not None) or pause_to_edit
                ),
            }},
        )

    fingerprint_inputs = classmethod(_fingerprint)
    check_lazy_status = classmethod(_lazy_text)


class PromptStashManager(io.ComfyNode):
    """Frontend library controls; execution intentionally has no side effect."""

    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="PromptStashManager",
            display_name="Prompt Stash Manager",
            category="utils",
            inputs=[
                io.String.Input(
                    "new_list_name", optional=True, default="",
                    placeholder="Enter new list name",
                ),
            ],
            outputs=[],
        )

    @classmethod
    async def execute(cls, new_list_name: str = "") -> io.NodeOutput:
        del new_list_name
        return io.NodeOutput()


__all__ = ["PromptStashSaver", "PromptStashPassthrough", "PromptStashManager"]
