"""Secure Nodes V2 backend for Multi-Scene Prompt Editor."""

from __future__ import annotations

import json
from typing import Any

from comfy_api.latest import io


MAX_SCENES = 32
MAX_COMMON_PROMPT_BYTES = 262_144
MAX_SCENES_JSON_BYTES = 2_097_152


def _bounded_text(value: str, name: str, limit: int) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if len(value.encode("utf-8")) > limit:
        raise ValueError(f"{name} exceeds the {limit}-byte limit")
    return value


def _parse_scenes(value: str) -> list[Any]:
    value = _bounded_text(value, "scenes_json", MAX_SCENES_JSON_BYTES)
    try:
        scenes = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        # Preserve the pinned implementation's malformed-JSON fallback.
        return [""]
    if not isinstance(scenes, list):
        raise ValueError("scenes_json must contain a JSON array")
    if len(scenes) > MAX_SCENES:
        raise ValueError(f"scenes_json exceeds the {MAX_SCENES}-scene limit")
    return scenes


class MultiScenePrompt(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="MultiScenePrompt",
            display_name="Multi-Scene Prompt Editor",
            category="prompt",
            inputs=[
                io.String.Input(
                    "common_prompt",
                    default="",
                    multiline=True,
                    placeholder="公用提示词",
                ),
                io.String.Input(
                    "scenes_json",
                    default='[""]',
                    placeholder="",
                ),
            ],
            hidden=[io.Hidden.unique_id],
            outputs=[
                io.String.Output("scene_prompts"),
                io.String.Output("common_prompt"),
                io.Int.Output("scene_count"),
            ],
        )

    @classmethod
    def execute(
        cls,
        common_prompt: str,
        scenes_json: str,
        unique_id: str | None = None,
    ) -> io.NodeOutput:
        del unique_id
        common_prompt = _bounded_text(
            common_prompt,
            "common_prompt",
            MAX_COMMON_PROMPT_BYTES,
        )
        scenes = _parse_scenes(scenes_json)
        combined = [f"{common_prompt}{scene}" for scene in scenes]
        return io.NodeOutput(
            json.dumps(combined, ensure_ascii=False),
            common_prompt,
            len(scenes),
        )


NODE_CLASS_MAPPINGS = {"MultiScenePrompt": MultiScenePrompt}
