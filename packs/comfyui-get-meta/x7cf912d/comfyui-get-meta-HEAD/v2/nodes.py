"""Secure Nodes V2 implementations for comfyui-get-meta.

The legacy extension sent an arbitrary host path to a pack-owned HTTP route.
This conversion instead discovers only the image producer already connected to
the current node, resolves its selected logical name inside the managed input
catalogue, and parses the asset bytes in the confined guest.
"""
from __future__ import annotations

import io as bytes_io
import builtins
import json
import math
import re
from pathlib import PurePosixPath
from typing import Any

from PIL import Image

from ._secure_runtime import bind_node, sdk


_MAX_IMAGE_BYTES = 64 * 1024 * 1024
_MAX_IMAGE_PIXELS = 67_108_864
_MAX_METADATA_TEXT = 4 * 1024 * 1024
_MAX_METADATA_NODES = 4096
_IMAGE_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff",
}
_PATH_QUERIES = {
    "PATH", "REL_PATH", "ABS_PATH", "FULL_NAME", "DIR_NAME", "FILE_NAME",
    "EXT_NAME", "WIDTH", "HEIGHT",
}


def _ctx():
    return sdk.ctx()


def _safe_asset_name(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("the connected image loader must select an input asset name")
    name = re.sub(r"\s+\[input\]\s*$", "", value, flags=re.IGNORECASE)
    name = name.replace("\\", "/").strip()
    path = PurePosixPath(name)
    if (
        not name
        or "\x00" in name
        or path.is_absolute()
        or any(part in ("", ".", "..") for part in path.parts)
        or "://" in name
        or ":" in path.parts[0]
    ):
        raise ValueError("selected image must stay inside the managed input catalogue")
    if path.suffix.lower() not in _IMAGE_SUFFIXES:
        raise ValueError("selected input asset is not a supported image")
    return path.as_posix()


async def _selected_asset_name() -> str | None:
    try:
        values = await _ctx().graph.widget_values(linked_input="image")
    except KeyError:
        return None
    if not isinstance(values, dict):
        return None
    for key in ("image", "image_path"):
        value = values.get(key)
        if isinstance(value, str):
            return _safe_asset_name(value)
    return None


def _reject_json_constant(name: str):
    raise ValueError(f"non-finite JSON value {name}")


def _json_value(value: Any) -> Any:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    if not isinstance(value, str):
        return value if isinstance(value, (dict, list)) else {}
    if len(value.encode("utf-8", errors="ignore")) > _MAX_METADATA_TEXT:
        raise ValueError("embedded metadata JSON exceeds 4 MiB")
    try:
        parsed = json.loads(
            value,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, RecursionError, ValueError):
        return {}
    return parsed if isinstance(parsed, (dict, list)) else {}


def _webp_json(info: dict[str, Any]) -> tuple[Any, Any]:
    raw = info.get("exif")
    if not isinstance(raw, (bytes, str)):
        return {}, {}
    text = raw.decode("utf-8", errors="ignore") if isinstance(raw, bytes) else raw
    if len(text.encode("utf-8", errors="ignore")) > _MAX_METADATA_TEXT * 2:
        raise ValueError("embedded WebP metadata exceeds 8 MiB")
    workflow_match = re.search(
        r"workflow:(.+?)(?:[^}]*?)prompt:", text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    prompt_match = re.search(
        r"prompt:(.+?)(?:[^}]*?)$", text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return (
        _json_value(workflow_match.group(1)) if workflow_match else {},
        _json_value(prompt_match.group(1)) if prompt_match else {},
    )


def _metadata_value(info: dict[str, Any], name: str) -> Any:
    for key, value in info.items():
        if str(key).casefold() == name.casefold():
            return _json_value(value)
    return {}


def _node_sort_key(value: dict[str, Any]):
    node_id = value.get("id")
    try:
        return 0, int(node_id)
    except (TypeError, ValueError):
        return 1, str(node_id)


def _parse_nodes(workflow: Any, prompt: Any) -> list[dict[str, Any]]:
    workflow_nodes = (
        workflow.get("nodes", []) if isinstance(workflow, dict) else []
    )
    if not isinstance(workflow_nodes, list):
        workflow_nodes = []
    if len(workflow_nodes) > _MAX_METADATA_NODES:
        raise ValueError("embedded workflow exceeds 4096 nodes")
    by_id = {
        str(node.get("id")): node
        for node in workflow_nodes
        if isinstance(node, dict) and node.get("id") is not None
    }
    result: list[dict[str, Any]] = []

    for node in workflow_nodes:
        if not isinstance(node, dict) or node.get("type") != "Note":
            continue
        values = node.get("widgets_values")
        text = values[0] if isinstance(values, list) and values else ""
        result.append({
            "id": node.get("id"),
            "title": node.get("title"),
            "type": "Note",
            "values": {"text": text},
        })

    if isinstance(prompt, dict):
        if len(prompt) > _MAX_METADATA_NODES:
            raise ValueError("embedded prompt exceeds 4096 nodes")
        for key, value in prompt.items():
            if not isinstance(value, dict):
                continue
            node = by_id.get(str(key), {})
            node_type = str(value.get("class_type") or node.get("type") or "")
            title = node.get("title")
            properties = node.get("properties")
            search_name = (
                properties.get("Node name for S&R")
                if isinstance(properties, dict) else None
            )
            aliases = [item for item in (search_name,) if isinstance(item, str)]
            try:
                node_id: Any = int(key)
            except (TypeError, ValueError):
                node_id = str(key)
            inputs = value.get("inputs", {})
            result.append({
                "id": node_id,
                "title": title,
                "type": node_type,
                "aliases": aliases,
                "values": inputs if isinstance(inputs, dict) else {},
            })

    result.sort(key=_node_sort_key)
    return result


async def _read_selected_metadata() -> dict[str, Any] | None:
    name = await _selected_asset_name()
    if name is None:
        return None
    ref = await _ctx().assets.resolve("input", name)
    size = await _ctx().assets.size(ref)
    if size <= 0 or size > _MAX_IMAGE_BYTES:
        raise ValueError("selected image must be between 1 byte and 64 MiB")
    data = await _ctx().assets.read_bytes(ref)
    if len(data) != size:
        raise ValueError("selected image changed while its metadata was read")

    try:
        with Image.open(bytes_io.BytesIO(data)) as image:
            width, height = int(image.width), int(image.height)
            if width <= 0 or height <= 0 or width * height > _MAX_IMAGE_PIXELS:
                raise ValueError("selected image exceeds 67108864 pixels")
            info = dict(image.info or {})
            image_format = str(image.format or "").upper()
    except (OSError, SyntaxError, Image.DecompressionBombError) as error:
        raise ValueError("selected input asset is not a readable image") from error

    workflow = _metadata_value(info, "workflow")
    prompt = _metadata_value(info, "prompt")
    if image_format == "WEBP" and not workflow and not prompt:
        workflow, prompt = _webp_json(info)

    path = PurePosixPath(name)
    parent = path.parent.as_posix()
    return {
        "logical_name": name,
        "full_name": path.name,
        "file_name": path.stem,
        "ext_name": path.suffix.lstrip("."),
        "dir_name": "" if parent == "." else parent,
        "width": width,
        "height": height,
        "format": image_format,
        "workflow": workflow if isinstance(workflow, (dict, list)) else {},
        "prompt": prompt if isinstance(prompt, (dict, list)) else {},
        "nodes": _parse_nodes(workflow, prompt),
    }


def _match_node(node: dict[str, Any], selector: str) -> bool:
    match = re.fullmatch(r"#([0-9]+)", selector)
    if match:
        return str(node.get("id")) == match.group(1)
    if node.get("title") == selector or node.get("type") == selector:
        return True
    return selector in node.get("aliases", ())


def _find_node(nodes: list[dict[str, Any]], selector: str):
    index = 0
    match = re.search(r"\[([0-9]+)\]$", selector)
    if match:
        index = int(match.group(1))
        selector = selector[:match.start()]
    matches = [node for node in nodes if _match_node(node, selector)]
    return matches[index] if index < len(matches) else None


def _query_value(metadata: dict[str, Any], query: Any, fallback: Any) -> Any:
    query = str(query or "")
    if query in _PATH_QUERIES:
        if query == "ABS_PATH":
            raise ValueError(
                "ABS_PATH is unavailable: Secure Nodes never exposes host paths"
            )
        values = {
            "PATH": metadata["logical_name"],
            "REL_PATH": metadata["logical_name"],
            "FULL_NAME": metadata["full_name"],
            "DIR_NAME": metadata["dir_name"],
            "FILE_NAME": metadata["file_name"],
            "EXT_NAME": metadata["ext_name"],
            "WIDTH": metadata["width"],
            "HEIGHT": metadata["height"],
        }
        return values[query]

    selector, separator, widget = query.rpartition(".")
    if not separator or not selector or not widget:
        return fallback
    target = _find_node(metadata["nodes"], selector)
    if target is None:
        return fallback
    values = target.get("values")
    if not isinstance(values, dict) or widget not in values:
        return fallback
    value = values[widget]
    return fallback if isinstance(value, (dict, list)) else value


def _values_text(nodes: list[dict[str, Any]]) -> str:
    entries: list[list[Any]] = []
    for node in nodes:
        values = node.get("values")
        if not isinstance(values, dict):
            continue
        for key, value in values.items():
            if isinstance(value, (dict, list)):
                continue
            if isinstance(value, str):
                value = re.sub(r"\s+", " ", value)
            entries.append([f"#{node.get('id')}.{key}", value])
    if not entries:
        return ""
    width = max(len(item[0]) for item in entries) + 1
    return "\n".join(f"{key.ljust(width)}: {value}" for key, value in entries)


def _result(node_id: str, value: Any, metadata: dict[str, Any] | None):
    asset = metadata.get("logical_name") if metadata else None
    return {
        "result": (value,),
        "ui": {"get_meta": [{
            "node_type": node_id,
            "asset": asset,
            "value": value,
        }]},
    }


async def _workflow(workflow="", **_kwargs):
    metadata = await _read_selected_metadata()
    value = workflow if metadata is None else json.dumps(
        metadata["workflow"], indent=2, ensure_ascii=False,
    )
    return _result("GetWorkflowFromImage", value, metadata)


async def _prompt(prompt="", **_kwargs):
    metadata = await _read_selected_metadata()
    value = prompt if metadata is None else json.dumps(
        metadata["prompt"], indent=2, ensure_ascii=False,
    )
    return _result("GetPromptFromImage", value, metadata)


async def _values(nodes="", **_kwargs):
    metadata = await _read_selected_metadata()
    value = nodes if metadata is None else _values_text(metadata["nodes"])
    return _result("GetValuesFromImage", value, metadata)


async def _scalar(node_id: str, query: Any, fallback: Any, convert):
    metadata = await _read_selected_metadata()
    raw = fallback if metadata is None else _query_value(metadata, query, fallback)
    try:
        value = convert(raw)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"metadata value for {query!r} cannot be converted") from error
    return _result(node_id, value, metadata)


async def _boolean(query="", boolean=False, **_kwargs):
    return await _scalar("GetBooleanFromImage", query, boolean, bool)


async def _integer(query="", int=0, **_kwargs):
    return await _scalar("GetIntFromImage", query, int, builtins.int)


async def _float(query="", float=0.0, **_kwargs):
    return await _scalar("GetFloatFromImage", query, float, builtins.float)


async def _string(query="", string="", **_kwargs):
    return await _scalar("GetStringFromImage", query, string, str)


async def _combo(query="", combo="", **_kwargs):
    return await _scalar("GetComboFromImage", query, combo, lambda value: value)


def _always_changed(**_kwargs):
    return math.nan


for _handler in (
    _boolean, _integer, _float, _string, _combo, _values, _workflow, _prompt,
):
    _handler.fingerprint_inputs = _always_changed


_PERMISSIONS = ("assets", "graph")
NODE_CLASS_MAPPINGS = {
    "GetBooleanFromImage": bind_node(
        "GetBooleanFromImage", _boolean, permissions=_PERMISSIONS,
    ),
    "GetIntFromImage": bind_node(
        "GetIntFromImage", _integer, permissions=_PERMISSIONS,
    ),
    "GetFloatFromImage": bind_node(
        "GetFloatFromImage", _float, permissions=_PERMISSIONS,
    ),
    "GetStringFromImage": bind_node(
        "GetStringFromImage", _string, permissions=_PERMISSIONS,
    ),
    "GetComboFromImage": bind_node(
        "GetComboFromImage", _combo, permissions=_PERMISSIONS,
    ),
    "GetValuesFromImage": bind_node(
        "GetValuesFromImage", _values, permissions=_PERMISSIONS,
    ),
    "GetWorkflowFromImage": bind_node(
        "GetWorkflowFromImage", _workflow, permissions=_PERMISSIONS,
    ),
    "GetPromptFromImage": bind_node(
        "GetPromptFromImage", _prompt, permissions=_PERMISSIONS,
    ),
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "GetBooleanFromImage": "Get Boolean from Image",
    "GetIntFromImage": "Get Int from Image",
    "GetFloatFromImage": "Get Float from Image",
    "GetStringFromImage": "Get String from Image",
    "GetComboFromImage": "Get Combo from Image",
    "GetValuesFromImage": "Get Values from Image",
    "GetWorkflowFromImage": "Get Workflow from Image",
    "GetPromptFromImage": "Get Prompt from Image",
}


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
