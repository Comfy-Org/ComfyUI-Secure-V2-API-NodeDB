"""Authority-free Secure Nodes V2 backend for ComfyUI Text Randomizer."""

from __future__ import annotations

import random
import re

from comfy_api.latest import io


CATEGORY = "randomizer"
MAX_TEXT_BYTES = 1_048_576
MAX_REPLACEMENT_PASSES = 4096
SEED_MAX = 0xFFFFFFFFFFFFFFFF
_INNER_CHOICE = re.compile(r"\[([^\[\]]+)\]")


def _bounded_text(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if len(value.encode("utf-8")) > MAX_TEXT_BYTES:
        raise ValueError(f"{name} exceeds the {MAX_TEXT_BYTES}-byte limit")
    return value


def _seed(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("seed must be an integer")
    if not 0 <= value <= SEED_MAX:
        raise ValueError(f"seed must be between 0 and {SEED_MAX}")
    return value


def _randomize(text: str, seed: int) -> str:
    """Preserve the upstream innermost-first replacement and RNG sequence."""

    text = _bounded_text(text, "text")
    rng = random.Random(_seed(seed))
    passes = 0
    while "[" in text:
        replaced, count = _INNER_CHOICE.subn(
            lambda match: rng.choice(match.group(1).split("|")), text
        )
        if count == 0:
            raise ValueError("text contains an unmatched opening bracket")
        text = replaced
        passes += 1
        if passes > MAX_REPLACEMENT_PASSES:
            raise ValueError("text contains too many nested choices")
    return text


class RandomizeText(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="RandomizeText",
            display_name="Text randomizer",
            category=CATEGORY,
            inputs=[
                io.String.Input("text", multiline=True),
                io.Int.Input("seed", default=0, min=0, max=SEED_MAX),
            ],
            outputs=[io.String.Output("text")],
        )

    @classmethod
    def execute(cls, text: str, seed: int) -> io.NodeOutput:
        return io.NodeOutput(_randomize(text, seed))


class RandomizeTextWithCheck(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="RandomizeTextWithCheck",
            display_name="Text randomizer with check",
            category=CATEGORY,
            inputs=[
                io.String.Input("text", multiline=True),
                io.Int.Input("seed", default=0, min=0, max=SEED_MAX),
                io.String.Input("info_text", multiline=True, optional=True),
            ],
            outputs=[io.String.Output("text")],
        )

    @classmethod
    def execute(
        cls, text: str, seed: int, info_text: str | None = None
    ) -> io.NodeOutput:
        if info_text is not None:
            _bounded_text(info_text, "info_text")
        return io.NodeOutput(_randomize(text, seed))


class ConcatText(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ConcatText",
            display_name="Concatenate text",
            category=CATEGORY,
            inputs=[
                io.String.Input("text1", multiline=True, force_input=True),
                io.String.Input("text2", multiline=True, force_input=True),
            ],
            outputs=[io.String.Output("text")],
        )

    @classmethod
    def execute(cls, text1: str, text2: str) -> io.NodeOutput:
        text1 = _bounded_text(text1, "text1")
        text2 = _bounded_text(text2, "text2")
        result = f"{text1}, {text2}"
        if len(result.encode("utf-8")) > MAX_TEXT_BYTES:
            raise ValueError(f"concatenated text exceeds the {MAX_TEXT_BYTES}-byte limit")
        return io.NodeOutput(result)


class RandomTextChoice(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="RandomTextChoice",
            display_name="Get one text or another at random",
            category=CATEGORY,
            inputs=[
                io.String.Input("text1", multiline=True, force_input=True),
                io.String.Input("text2", multiline=True, force_input=True),
                io.Int.Input("seed", default=0, min=0, max=SEED_MAX),
            ],
            outputs=[io.String.Output("text")],
        )

    @classmethod
    def execute(cls, text1: str, text2: str, seed: int) -> io.NodeOutput:
        text1 = _bounded_text(text1, "text1")
        text2 = _bounded_text(text2, "text2")
        return io.NodeOutput(random.Random(_seed(seed)).choice([text1, text2]))


class ShowText(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ShowText",
            display_name="Show text",
            category=CATEGORY,
            is_output_node=True,
            inputs=[
                io.String.Input("text", force_input=True, dynamic_prompts=True),
                io.String.Input("preview", multiline=True, optional=True),
            ],
            outputs=[],
        )

    @classmethod
    def execute(cls, text: str, preview: str | None = None) -> io.NodeOutput:
        text = _bounded_text(text, "text")
        if preview is not None:
            _bounded_text(preview, "preview")
        return io.NodeOutput(ui={"text": text})


NODE_CLASS_MAPPINGS = {
    "RandomizeText": RandomizeText,
    "RandomizeTextWithCheck": RandomizeTextWithCheck,
    "RandomTextChoice": RandomTextChoice,
    "ConcatText": ConcatText,
    "ShowText": ShowText,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RandomizeText": "Text randomizer",
    "RandomizeTextWithCheck": "Text randomizer with check",
    "RandomTextChoice": "Get one text or another at random",
    "ConcatText": "Concatenate text",
    "ShowText": "Show text",
}
