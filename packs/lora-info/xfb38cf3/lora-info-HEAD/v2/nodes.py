"""Secure V2 implementation of jitcoder's LoRA information node.

Formatting and cache policy remain pack code.  The host supplies only a
confined LoRA catalogue entry, its digest, tenant-scoped storage, and the
fixed, bounded CivitAI model-version projection.
"""
from __future__ import annotations

import json
from typing import Any

from comfy_api.latest import io, sdk


_CACHE_PREFIX = "lora-info:civitai-version-v1:"
_MAX_TEXT_BYTES = 1024 * 1024


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


def _bounded_text(value: Any, *, maximum: int = 4096) -> str:
    if not isinstance(value, str) or "\x00" in value:
        return ""
    encoded = value.encode("utf-8")
    if len(encoded) > maximum:
        return encoded[:maximum].decode("utf-8", errors="ignore")
    return value


def _display_value(value: Any) -> str:
    if isinstance(value, str):
        return _bounded_text(value, maximum=64 * 1024)
    # The upstream node formats public CivitAI metadata with an f-string.  The
    # host has already depth/item/size bounded this JSON value, so Python's
    # normal display form is safe here and preserves that exact behavior.
    return _bounded_text(str(value), maximum=64 * 1024)


def _bounded_words(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    total = 0
    for word in value[:2048]:
        text = _bounded_text(word, maximum=512)
        if not text:
            continue
        size = len(text.encode("utf-8"))
        if total + size > _MAX_TEXT_BYTES:
            break
        result.append(text)
        total += size
    return result


def _is_authority_error(error: Exception) -> bool:
    remote_type = str(getattr(error, "remote_type", type(error).__name__))
    remote_message = str(getattr(error, "remote_message", error))
    return (
        remote_type in {"PermissionError", "AuthorizationError"}
        or "PermissionError" in remote_message
        or (
            "capability " in remote_message
            and "not granted" in remote_message
        )
    )


def _project_info(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        value = {}
    images = []
    raw_images = value.get("images")
    if isinstance(raw_images, list):
        for item in raw_images[:32]:
            if not isinstance(item, dict):
                continue
            url = _bounded_text(item.get("url"), maximum=2048)
            meta = item.get("meta")
            if not isinstance(meta, dict):
                meta = {}
            images.append({
                "url": url,
                "meta": dict(list(meta.items())[:64]),
            })
    return {
        "modelId": value.get("modelId"),
        "trainedWords": _bounded_words(value.get("trainedWords")),
        "baseModel": _bounded_text(value.get("baseModel"), maximum=512),
        "images": images,
    }


def _format_info(info: dict[str, Any]):
    words = _bounded_words(info.get("trainedWords"))
    trigger_words = ",".join(words)
    base_model = _bounded_text(info.get("baseModel"), maximum=512)
    output = ""
    model_id = info.get("modelId")
    if isinstance(model_id, int) and not isinstance(model_id, bool):
        output += f"URL: https://civitai.com/models/{model_id}\n"
    if trigger_words:
        output += f"Triggers: {trigger_words}\n"
    if base_model:
        output += f"Base Model: {base_model}\n"

    example_prompt = None
    images = info.get("images")
    if isinstance(images, list) and images:
        output += "\nExamples:\n"
        for image in images[:32]:
            if not isinstance(image, dict):
                continue
            output += f"\nOutput: {_bounded_text(image.get('url'), maximum=2048)}\n"
            meta = image.get("meta")
            if isinstance(meta, dict):
                for key, value in list(meta.items())[:64]:
                    key_text = _bounded_text(key, maximum=128)
                    value_text = _display_value(value)
                    if not key_text:
                        continue
                    if example_prompt is None and key_text == "prompt":
                        example_prompt = value_text
                    output += f"{key_text}: {value_text}\n"
            output += "\n"
            if len(output.encode("utf-8")) > _MAX_TEXT_BYTES:
                output = output.encode("utf-8")[:_MAX_TEXT_BYTES].decode(
                    "utf-8", errors="ignore"
                )
                break
    return output, trigger_words, example_prompt, base_model


async def _get_lora_info(lora_name: Any):
    name = _safe_lora_name(lora_name)
    asset = await _ctx().assets.resolve("loras", name)
    digest = await _ctx().assets.digest(asset, algorithm="sha256")
    cache_key = _CACHE_PREFIX + digest.lower()
    cached = await _ctx().storage.get(cache_key)
    info = None
    if cached is not None:
        try:
            decoded = json.loads(cached)
        except (TypeError, json.JSONDecodeError):
            decoded = None
        if isinstance(decoded, dict):
            info = _project_info(decoded)

    if info is None:
        try:
            fetched = await _ctx().integrations.civitai.model_version_by_hash(
                digest
            )
        except Exception as error:
            if _is_authority_error(error):
                raise
            fetched = {}
        info = _project_info(fetched)
        await _ctx().storage.set(
            cache_key,
            json.dumps(info, ensure_ascii=True, separators=(",", ":")),
        )
    return _format_info(info)


class LoraInfo(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets", "integrations.civitai", "storage")
    SDK_REQUIRED_WEIGHTS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="LoraInfo",
            display_name="Lora Info",
            category="jitcoder",
            inputs=[
                io.Combo.Input(
                    "lora_name",
                    options=[],
                    remote=io.RemoteOptions(
                        route="/models/loras",
                        refresh_button=True,
                    ),
                ),
            ],
            outputs=[
                io.String.Output("lora_name", display_name="lora_name"),
                io.String.Output(
                    "trigger_words", display_name="trigger_words"
                ),
                io.String.Output(
                    "example_prompt", display_name="example_prompt"
                ),
            ],
            is_output_node=True,
        )

    @classmethod
    async def execute(cls, lora_name: str) -> io.NodeOutput:
        output, trigger_words, example_prompt, base_model = (
            await _get_lora_info(lora_name)
        )
        return io.NodeOutput(
            lora_name,
            trigger_words,
            example_prompt,
            ui={"text": [output], "model": [base_model]},
        )


NODE_CLASS_MAPPINGS = {"LoraInfo": LoraInfo}
NODE_DISPLAY_NAME_MAPPINGS = {"LoraInfo": "Lora Info"}

__all__ = ["LoraInfo", "NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
