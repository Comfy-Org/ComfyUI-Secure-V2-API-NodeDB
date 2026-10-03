"""Secure Nodes V2 backend for Embedding Picker."""

from __future__ import annotations

import math
from pathlib import Path

from comfy_api.latest import io


MAX_TEXT_BYTES = 1_048_576
MAX_MODEL_NAME_BYTES = 4096


def _bounded_string(value: str, name: str, limit: int) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if len(value.encode("utf-8")) > limit:
        raise ValueError(f"{name} exceeds the {limit}-byte limit")
    return value


def format_embedding(
    text: str,
    embedding: str,
    emphasis: float,
    append: bool,
) -> str:
    """Match the pinned node's prompt formatting for valid widget inputs."""
    text = _bounded_string(text, "text", MAX_TEXT_BYTES)
    embedding = _bounded_string(embedding, "embedding", MAX_MODEL_NAME_BYTES)
    if isinstance(emphasis, bool) or not isinstance(emphasis, (int, float)):
        raise TypeError("emphasis must be a number")
    emphasis = float(emphasis)
    if not math.isfinite(emphasis) or not 0.0 <= emphasis <= 3.0:
        raise ValueError("emphasis must be between 0.0 and 3.0")
    if not isinstance(append, bool):
        raise TypeError("append must be a boolean")
    if emphasis < 0.05:
        return text

    token = "embedding:" + Path(embedding).stem
    emphasis_text = f"{emphasis:.3f}"
    if emphasis_text != "1.000":
        token = f"({token}:{emphasis_text})"
    return f"{text}, {token}" if append else f"{token}, {text}"


class EmbeddingPicker(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="EmbeddingPicker",
            display_name="Embedding Picker",
            category="utils",
            inputs=[
                # The secure frontend fills this closed catalogue through
                # comfy.models.list('embeddings') without exposing paths.
                io.Combo.Input("embedding", options=[]),
                io.Float.Input(
                    "emphasis", default=1.0, min=0.0, max=3.0, step=0.05
                ),
                io.Boolean.Input("append", default=False),
                io.String.Input("text", multiline=True),
            ],
            outputs=[io.String.Output("text")],
        )

    @classmethod
    def execute(
        cls,
        text: str,
        embedding: str,
        emphasis: float,
        append: bool,
    ) -> io.NodeOutput:
        return io.NodeOutput(format_embedding(text, embedding, emphasis, append))


NODE_CLASS_MAPPINGS = {"EmbeddingPicker": EmbeddingPicker}
