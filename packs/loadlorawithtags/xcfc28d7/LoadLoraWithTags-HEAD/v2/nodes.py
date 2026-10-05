"""Secure Nodes V2 implementation of LoadLoraWithTags."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from comfy_api.latest import ComfyExtension, io, sdk

_CACHE_PREFIX = "lora-tags-by-name-v1:"
_MAX_TAGS = 2_048
_MAX_TAG_BYTES = 512
_MAX_CACHE_BYTES = 900 * 1_024


def _ctx():
    return sdk.ctx()


def _safe_lora_name(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("LoRA name must be a string")
    name = value.replace("\\", "/")
    if (
        not name
        or name.startswith(("/", "~/"))
        or "\x00" in name
        or ":" in name.split("/", 1)[0]
    ):
        raise ValueError("LoRA name must be a confined catalogue name")
    if any(part in {"", ".", ".."} for part in name.split("/")):
        raise ValueError("LoRA name must not contain traversal components")
    return name


def _cache_key(name: str) -> str:
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()
    return _CACHE_PREFIX + digest


def _bounded_tags(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    result: list[str] = []
    encoded_total = 2
    for item in value[:_MAX_TAGS]:
        if not isinstance(item, str) or "\x00" in item:
            continue
        if len(item.encode("utf-8")) > _MAX_TAG_BYTES:
            continue
        encoded = json.dumps(item, ensure_ascii=True).encode("utf-8")
        addition = len(encoded) + (1 if result else 0)
        if encoded_total + addition > _MAX_CACHE_BYTES:
            break
        result.append(item)
        encoded_total += addition
    return result


def _decode_cached_tags(value: Any) -> list[str] | None:
    if not isinstance(value, str) or len(value.encode("utf-8")) > _MAX_CACHE_BYTES:
        return None
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(decoded, list):
        return None
    return _bounded_tags(decoded)


def _is_authority_error(error: Exception) -> bool:
    remote_type = str(getattr(error, "remote_type", type(error).__name__))
    remote_message = str(getattr(error, "remote_message", error))
    return (
        remote_type in {"PermissionError", "AuthorizationError"}
        or "PermissionError" in remote_message
        or ("capability " in remote_message and "not granted" in remote_message)
    )


async def _fetch_tags(asset, *, force_fetch: bool) -> list[str]:
    digest = await _ctx().assets.digest(asset, algorithm="sha256")
    try:
        info = await _ctx().integrations.call(
            "civitai",
            "model_version_by_hash",
            hash_value=digest,
            refresh=force_fetch,
        )
    except Exception as error:
        if _is_authority_error(error):
            raise
        return []
    if not isinstance(info, dict):
        return []
    return _bounded_tags(info.get("trainedWords"))


class LoraLoaderTagsQuery(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets", "integrations.civitai", "storage")
    SDK_REQUIRED_WEIGHTS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="LoraLoaderTagsQuery",
            display_name="LoraLoaderTagsQuery",
            category="loaders",
            inputs=[
                io.Model.Input("model"),
                io.Clip.Input("clip"),
                io.Combo.Input(
                    "lora_name",
                    options=[],
                    remote=io.RemoteOptions(
                        route="/models/loras",
                        refresh_button=True,
                    ),
                ),
                io.Float.Input(
                    "strength_model",
                    default=1.0,
                    min=-10.0,
                    max=10.0,
                    step=0.1,
                ),
                io.Float.Input(
                    "strength_clip",
                    default=1.0,
                    min=-10.0,
                    max=10.0,
                    step=0.1,
                ),
                io.Boolean.Input("query_tags", default=True),
                io.Boolean.Input("tags_out", default=True),
                io.Boolean.Input("print_tags", default=False),
                io.Boolean.Input("bypass", default=False),
                io.Boolean.Input("force_fetch", default=False),
                io.String.Input(
                    "opt_prompt",
                    optional=True,
                    force_input=True,
                ),
            ],
            outputs=[
                io.Model.Output("output_0", display_name="MODEL"),
                io.Clip.Output("output_1", display_name="CLIP"),
                io.String.Output("output_2", display_name="STRING"),
            ],
        )

    @classmethod
    async def execute(
        cls,
        model: sdk.ModelRef,
        clip: sdk.ClipRef,
        lora_name: str,
        strength_model: float,
        strength_clip: float,
        query_tags: bool,
        tags_out: bool,
        print_tags: bool,
        bypass: bool,
        force_fetch: bool,
        opt_prompt: str | None = None,
    ) -> io.NodeOutput:
        if (strength_model == 0 and strength_clip == 0) or bypass:
            return io.NodeOutput(
                model, clip, opt_prompt if opt_prompt is not None else ""
            )

        name = _safe_lora_name(lora_name)
        asset = await _ctx().assets.resolve("loras", name)
        key = _cache_key(name)
        tags = _decode_cached_tags(await _ctx().storage.get(key))
        if tags is None:
            tags = []

        output_tags = ", ".join(tags)
        if (query_tags and output_tags == "") or force_fetch:
            tags = await _fetch_tags(asset, force_fetch=bool(force_fetch))
            await _ctx().storage.set(
                key,
                json.dumps(tags, ensure_ascii=True, separators=(",", ":")),
            )
            output_tags = ", ".join(tags)

        if print_tags and output_tags:
            print("trainedWords:", output_tags)

        model_lora, clip_lora = await model.apply_lora(
            asset,
            clip,
            float(strength_model),
            float(strength_clip),
        )
        if opt_prompt is not None:
            output_tags = opt_prompt + ", " + output_tags if tags_out else opt_prompt
        return io.NodeOutput(model_lora, clip_lora, output_tags)


NODE_CLASS_MAPPINGS = {"LoraLoaderTagsQuery": LoraLoaderTagsQuery}
NODE_DISPLAY_NAME_MAPPINGS = {"LoraLoaderTagsQuery": "LoraLoaderTagsQuery"}


class LoadLoraWithTagsExtension(ComfyExtension):
    async def get_node_list(self):
        return [LoraLoaderTagsQuery]


async def comfy_entrypoint() -> LoadLoraWithTagsExtension:
    return LoadLoraWithTagsExtension()


__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "LoadLoraWithTagsExtension",
    "LoraLoaderTagsQuery",
    "comfy_entrypoint",
]
