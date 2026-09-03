"""Secure V2 implementations for ComfyUI LoRA Auto Trigger Words.

Tag parsing, selector formatting, stack construction, and cache policy remain
pack code.  The host supplies only confined LoRA assets, opaque LoRA
application, pack-scoped storage, and the bounded Civitai vendor projection.
"""
from __future__ import annotations

import json
import math
import posixpath
from itertools import islice
from typing import Any

from comfy_api.latest import sdk

from ._secure_runtime import bind_node


_MAX_HEADER = 16 * 1024 * 1024
_MAX_TAGS = 2048
_MAX_TAG_BYTES = 512
_MAX_TAG_JSON_BYTES = 900 * 1024
_CACHE_PREFIX = "civitai-trained-words-v1:"


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
    parts = name.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("LoRA name must not contain traversal components")
    return "/".join(parts)


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
        if encoded_total + addition > _MAX_TAG_JSON_BYTES:
            break
        result.append(item)
        encoded_total += addition
    return result


async def _metadata_tags(asset) -> list[str]:
    size = await _ctx().assets.size(asset)
    if size < 9:
        raise BufferError("Invalid safetensors header size")
    prefix = await _ctx().assets.read_range(asset, 0, 8)
    if len(prefix) != 8:
        raise BufferError("Invalid safetensors header size")
    header_size = int.from_bytes(prefix, "little", signed=False)
    if not 0 < header_size <= _MAX_HEADER or header_size > size - 8:
        raise BufferError("Invalid safetensors header size")
    header = await _ctx().assets.read_range(asset, 8, header_size)
    if len(header) != header_size:
        raise BufferError("Invalid safetensors header")
    try:
        document = json.loads(header.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BufferError("Invalid safetensors header") from error
    metadata = document.get("__metadata__") if isinstance(document, dict) else None
    if not isinstance(metadata, dict):
        return []
    frequency = metadata.get("ss_tag_frequency")
    if not isinstance(frequency, str):
        return []
    try:
        datasets = json.loads(frequency)
    except json.JSONDecodeError as error:
        raise ValueError("Invalid ss_tag_frequency metadata") from error
    if not isinstance(datasets, dict):
        return []

    totals: dict[str, float] = {}
    for dataset in islice(datasets.values(), _MAX_TAGS):
        if not isinstance(dataset, dict):
            continue
        for raw_tag, raw_count in islice(dataset.items(), _MAX_TAGS):
            tag = str(raw_tag).strip()
            if len(tag.encode("utf-8")) > _MAX_TAG_BYTES:
                continue
            if isinstance(raw_count, bool) or not isinstance(raw_count, (int, float)):
                continue
            count = float(raw_count)
            if not math.isfinite(count):
                continue
            totals[tag] = totals.get(tag, 0.0) + count
            if len(totals) >= _MAX_TAGS:
                break
        if len(totals) >= _MAX_TAGS:
            break
    return _bounded_tags(
        [tag for tag, _count in sorted(
            totals.items(), key=lambda item: item[1], reverse=True
        )]
    )


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


async def _civitai_tags(digest: str, force_fetch: bool) -> list[str]:
    key = _CACHE_PREFIX + digest.lower()
    if not force_fetch:
        cached = await _ctx().storage.get(key)
        if cached is not None:
            try:
                decoded = json.loads(cached)
            except (TypeError, json.JSONDecodeError):
                decoded = None
            if isinstance(decoded, list):
                return _bounded_tags(decoded)

    try:
        info = await _ctx().integrations.call("civitai", "model_version_by_hash", hash_value=digest, refresh=bool(force_fetch))
        words = _bounded_tags(
            info.get("trainedWords", []) if isinstance(info, dict) else []
        )
    except Exception as error:
        # Vendor outages mean "no public tags", as in the original pack.  A
        # missing capability is different: it must remain visibly fail-closed.
        if _is_authority_error(error):
            raise
        words = []
    await _ctx().storage.set(key, json.dumps(words, separators=(",", ":")))
    return words


async def _lora_tags(lora_name: Any, force_fetch: Any):
    name = _safe_lora_name(lora_name)
    asset = await _ctx().assets.resolve("loras", name)
    metadata = await _metadata_tags(asset)
    digest = await _ctx().assets.digest(asset, algorithm="sha256")
    civitai = await _civitai_tags(digest, bool(force_fetch))
    return name, asset, civitai, metadata


def _append_name_if_empty(tags: list[str], lora_name: str, enabled: Any) -> list[str]:
    result = list(tags)
    if enabled and not result:
        result.append(posixpath.splitext(posixpath.basename(lora_name))[0])
    return result


async def _loader(
    model,
    lora_name,
    strength_model,
    strength_clip,
    force_fetch,
    append_loraname_if_empty,
    clip=None,
    override_lora_name="",
    **_kwargs,
):
    selected = override_lora_name if override_lora_name != "" else lora_name
    name, asset, civitai, metadata = await _lora_tags(selected, force_fetch)
    civitai = _append_name_if_empty(
        civitai, name, append_loraname_if_empty
    )
    metadata = _append_name_if_empty(
        metadata, name, append_loraname_if_empty
    )
    clip_strength = 0.0 if clip is None else float(strength_clip)
    model_lora, clip_lora = await model.apply_lora(
        asset,
        clip,
        float(strength_model),
        clip_strength,
    )
    return model_lora, clip_lora, civitai, metadata, name


async def _stacked_loader(
    lora_name,
    lora_weight,
    force_fetch,
    append_loraname_if_empty,
    lora_stack=None,
    override_lora_name="",
    **_kwargs,
):
    selected = override_lora_name if override_lora_name != "" else lora_name
    name, _asset, civitai, metadata = await _lora_tags(selected, force_fetch)
    civitai = _append_name_if_empty(
        civitai, name, append_loraname_if_empty
    )
    metadata = _append_name_if_empty(
        metadata, name, append_loraname_if_empty
    )
    weight = float(lora_weight)
    stack = [(name, weight, weight)]
    if lora_stack is not None:
        stack.extend(list(lora_stack))
    return civitai, metadata, stack, name


async def _tags_only(
    lora_name,
    force_fetch,
    append_loraname_if_empty,
    override_lora_name="",
    **_kwargs,
):
    selected = override_lora_name if override_lora_name != "" else lora_name
    name, _asset, civitai, metadata = await _lora_tags(selected, force_fetch)
    return (
        _append_name_if_empty(civitai, name, append_loraname_if_empty),
        _append_name_if_empty(metadata, name, append_loraname_if_empty),
    )


def _randomizer(text_1, text_2, seed, lora_1=None, lora_2=None, **_kwargs):
    if int(seed) % 2 == 0:
        return text_1, [] if lora_1 is None else lora_1
    return text_2, [] if lora_2 is None else lora_2


def _fusion_text(text_1, text_2, **_kwargs):
    return (text_1 + text_2,)


def _text_input(text, prefix="", suffix="", **_kwargs):
    return (prefix + text + suffix,)


def _parse_selector(selector: str, tags_list: list[Any]) -> str:
    if len(tags_list) == 0:
        return ""
    output: dict[int, Any] = {}
    for range_index in selector.split(","):
        if range_index.count(":") == 0:
            if range_index.strip() == "":
                continue
            index = int(range_index)
            if abs(index) > len(tags_list) - 1:
                continue
            output[index] = tags_list[index]
        if range_index.count(":") == 1:
            indexes = range_index.split(":")
            start = 0 if indexes[0] == "" else int(indexes[0])
            end = len(tags_list) if indexes[1] == "" else int(indexes[1])
            if start < 0:
                start = len(tags_list) + start
            if end < 0:
                end = len(tags_list) + end
            start, end = min(start, len(tags_list)), min(end, len(tags_list))
            start, end = max(start, 0), max(end, 0)
            for index in range(start, end):
                output[index] = tags_list[index]
    return ", ".join(str(item) for item in output.values())


def _tags_selector(
    tags_list,
    selector,
    weight,
    ensure_comma,
    prefix="",
    suffix="",
    **_kwargs,
):
    tags = list(tags_list)
    if float(weight) != 1.0:
        tags = [f"({tag}:{weight})" for tag in tags]
    output = _parse_selector(str(selector), tags)
    if ensure_comma:
        stripped_prefix = prefix.strip()
        stripped_suffix = suffix.strip()
        if (
            stripped_prefix != ""
            and not stripped_prefix.endswith(",")
            and output != ""
            and not output.startswith(",")
        ):
            prefix = stripped_prefix + ", "
        if (
            output != ""
            and not output.endswith(",")
            and stripped_suffix != ""
            and not stripped_suffix.startswith(",")
        ):
            suffix = ", " + stripped_suffix
    return (prefix + output + suffix,)


def _tags_formatter(tags_list, **_kwargs):
    return ("".join(f'{index} : "{tag}"\n' for index, tag in enumerate(tags_list)),)


def _lora_list_name(lora_name, **_kwargs):
    return (lora_name,)


_LORA_PERMISSIONS = ("assets", "integrations.civitai", "storage")

NODE_CLASS_MAPPINGS = {
    "LoraLoaderVanilla": bind_node(
        "LoraLoaderVanilla", _loader, permissions=_LORA_PERMISSIONS
    ),
    "LoraLoaderStackedVanilla": bind_node(
        "LoraLoaderStackedVanilla", _stacked_loader, permissions=_LORA_PERMISSIONS
    ),
    "LoraLoaderAdvanced": bind_node(
        "LoraLoaderAdvanced", _loader, permissions=_LORA_PERMISSIONS
    ),
    "LoraLoaderStackedAdvanced": bind_node(
        "LoraLoaderStackedAdvanced", _stacked_loader, permissions=_LORA_PERMISSIONS
    ),
    "LoraTagsOnly": bind_node(
        "LoraTagsOnly", _tags_only, permissions=_LORA_PERMISSIONS
    ),
    "Randomizer": bind_node("Randomizer", _randomizer),
    "FusionText": bind_node("FusionText", _fusion_text),
    "TextInputBasic": bind_node("TextInputBasic", _text_input),
    "TagsSelector": bind_node("TagsSelector", _tags_selector),
    "TagsFormater": bind_node("TagsFormater", _tags_formatter),
    "LoraListNames": bind_node("LoraListNames", _lora_list_name),
}

NODE_DISPLAY_NAME_MAPPINGS = {node_id: node_id for node_id in NODE_CLASS_MAPPINGS}


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
