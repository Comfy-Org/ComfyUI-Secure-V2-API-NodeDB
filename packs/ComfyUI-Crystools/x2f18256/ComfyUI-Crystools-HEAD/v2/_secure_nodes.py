"""Secure Nodes 2.0 implementations for the pinned Crystools snapshot."""
from __future__ import annotations

import hashlib
import io as bytes_io
import json
import math
from pathlib import PurePosixPath
from typing import Any

import numpy as np
import torch
from PIL import ExifTags, Image, ImageOps

from ._secure_runtime import SCHEMAS, bind_node, materialize, sdk


_MAX_JSON_BYTES = 16 * 1024 * 1024
_MAX_IMAGE_BYTES = 256 * 1024 * 1024
_MAX_IMAGE_PIXELS = 67_108_864
_PREVIEW_CACHE: dict[str, tuple[dict[str, Any], dict[str, Any], str]] = {}


def _ctx():
    return sdk.ctx()


def _one(value: Any) -> tuple[Any]:
    return (value,)


def _safe_asset_name(value: Any, *, extension: str | None = None) -> str:
    name = str(value or "").replace("\\", "/").strip()
    path = PurePosixPath(name)
    if (
        not name
        or path.is_absolute()
        or any(part in ("", ".", "..") for part in path.parts)
        or "://" in name
        or ":" in path.parts[0]
    ):
        raise ValueError("asset names must stay inside the managed input folder")
    if extension is not None and path.suffix.lower() != extension:
        raise ValueError(f"selected asset must use the {extension} extension")
    return path.as_posix()


def _descriptor(folder: str, name: str) -> dict[str, str]:
    path = PurePosixPath(name)
    parent = path.parent.as_posix()
    return {
        "filename": path.name,
        "subfolder": "" if parent == "." else parent,
        "type": folder,
    }


def _logical_name(value: dict[str, Any]) -> str:
    filename = _safe_asset_name(value.get("filename"))
    subfolder = str(value.get("subfolder") or "").replace("\\", "/")
    return _safe_asset_name(
        f"{subfolder}/{filename}" if subfolder else filename
    )


def _format_bytes(size: int) -> str:
    value = float(size)
    for unit in ("bytes", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or unit == "TB":
            precision = 0 if unit == "bytes" else 2
            return f"{value:.{precision}f} {unit}"
        value /= 1024.0
    raise AssertionError("unreachable")


def _json_safe(value: Any, *, depth: int = 0) -> Any:
    if depth > 24:
        return "<maximum depth reached>"
    if value is None or isinstance(value, (bool, int, float, str)):
        if isinstance(value, float) and not math.isfinite(value):
            return str(value)
        return value
    if isinstance(value, bytes):
        return f"<{len(value)} binary bytes>"
    if isinstance(value, dict):
        return {
            str(key): _json_safe(item, depth=depth + 1)
            for key, item in list(value.items())[:4096]
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(item, depth=depth + 1) for item in value[:4096]]
    if isinstance(value, sdk.Ref):
        return f"<{value.kind} ref>"
    return str(value)


def _parse_json_text(value: Any, *, field: str) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError as error:
            raise ValueError(f"{field} must contain valid JSON") from error
    if isinstance(value, (dict, list, int, float, bool)) or value is None:
        return value
    raise TypeError(f"{field} must be JSON-compatible")


def _image_metadata(
    data: bytes,
    *,
    name: str,
    folder: str,
) -> tuple[Image.Image, dict[str, Any]]:
    if len(data) > _MAX_IMAGE_BYTES:
        raise ValueError("image asset exceeds 256 MiB")
    with Image.open(bytes_io.BytesIO(data)) as source:
        if source.width * source.height > _MAX_IMAGE_PIXELS:
            raise ValueError("image asset exceeds 67108864 pixels")
        source.load()
        image_format = str(source.format or "").upper()
        info = dict(source.info)
        exif = source.getexif()
        image = ImageOps.exif_transpose(source).copy()

    metadata: dict[str, Any] = {
        "fileinfo": {
            **_descriptor(folder, name),
            "logical_name": name,
            "resolution": f"{image.width}x{image.height}",
            "date": None,
            "size": _format_bytes(len(data)),
            "format": image_format,
        }
    }
    for key, value in info.items():
        key = str(key)
        if key in {"icc_profile", "exif"} or isinstance(value, bytes):
            continue
        if key in {"prompt", "workflow"} and isinstance(value, str):
            try:
                metadata[key] = _json_safe(json.loads(value))
            except json.JSONDecodeError:
                metadata[key] = value
            continue
        if isinstance(value, str):
            try:
                metadata[key] = _json_safe(json.loads(value))
            except json.JSONDecodeError:
                metadata[key] = value
        else:
            metadata[key] = _json_safe(value)

    if exif:
        exif_values = {}
        for tag_id, value in exif.items():
            tag = ExifTags.TAGS.get(tag_id, tag_id)
            exif_values[str(tag)] = _json_safe(value)
        if exif_values:
            metadata["EXIF"] = exif_values
    return image, metadata


def _preview_text(metadata: dict[str, Any], title: str) -> str:
    info = metadata.get("fileinfo") if isinstance(metadata, dict) else None
    if not isinstance(info, dict):
        return f"{title}\nSource: Empty"
    return "\n".join((
        title,
        f"File: {info.get('logical_name', info.get('filename', ''))}",
        f"Resolution: {info.get('resolution', '')}",
        f"Size: {info.get('size', '')}",
    ))


async def _asset_metadata(folder: str, name: str):
    ref = await _ctx().assets.resolve(folder, name)
    size = await _ctx().assets.size(ref)
    if size > _MAX_IMAGE_BYTES:
        raise ValueError("image asset exceeds 256 MiB")
    return _image_metadata(
        await _ctx().assets.read_bytes(ref), name=name, folder=folder
    )


async def _identity(**kwargs):
    return _one(next(iter(kwargs.values())))


async def _switch_from_any(any, boolean=True, **_kwargs):
    return (any, None) if bool(boolean) else (None, any)


async def _switch(on_true=None, on_false=None, boolean=True, **_kwargs):
    return _one(on_true if bool(boolean) else on_false)


def _switch_lazy(on_true=None, on_false=None, boolean=True, **_kwargs):
    selected = "on_true" if bool(boolean) else "on_false"
    value = on_true if selected == "on_true" else on_false
    return [selected] if value is None else []


async def _list_any(**kwargs):
    values = [kwargs.get(f"any_{index}") for index in range(1, 9)]
    return _one([[value for value in values if value is not None]])


async def _list_string(delimiter="", **kwargs):
    values = [kwargs.get(f"string_{index}") for index in range(1, 9)]
    values = [str(value) for value in values if value not in (None, "")]
    return str(delimiter).join(values), [values]


async def _pipe_to(CPipeAny=None, **kwargs):
    source = list(CPipeAny or (None,) * 6)
    if len(source) != 6:
        raise ValueError("Crystools pipe must contain exactly six values")
    for index in range(6):
        value = kwargs.get(f"any_{index + 1}")
        if value is not None:
            source[index] = value
    return _one(source)


async def _pipe_from(CPipeAny=None, **_kwargs):
    source = list(CPipeAny or ())
    if len(source) != 6:
        raise ValueError("Crystools pipe must contain exactly six values")
    return tuple([source, *source])


async def _display_value(value: Any) -> str:
    if isinstance(value, sdk.ValueRef):
        value = await value.value()
    elif isinstance(value, sdk.TensorRef):
        return f"<{value.kind} ref>"
    if isinstance(value, str):
        return value
    try:
        return json.dumps(_json_safe(value), ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


async def _show_any(any_value=None, console=None, display=None, prefix=None,
                    **_kwargs):
    values = list(any_value or ())
    console_enabled = bool((console or [False])[0])
    display_enabled = bool((display or [True])[0])
    prefix_value = str((prefix or [""])[0] or "")
    text = "".join([await _display_value(value) for value in values])
    if console_enabled:
        print(f"{prefix_value}: {text}" if prefix_value else text)
    shown = text if display_enabled else "inactive"
    return {"ui": {"text": [console_enabled, display_enabled, prefix_value, shown]}}


async def _show_json(any_value=None, **_kwargs):
    values = list(any_value or ())
    text = "inactive" if not values else await _display_value(values[0])
    if values and isinstance(values[0], (dict, list)):
        text = json.dumps(_json_safe(values[0]), indent=2, ensure_ascii=False)
    return {"ui": {"text": [text]}, "result": (text,)}


async def _get_resolution(image, **_kwargs):
    if not isinstance(image, sdk.ImageRef):
        image = await sdk.ImageRef._from_raw(await materialize(image))
    height, width = await image.spatial_shape()
    return {"ui": {"text": [f"{width}x{height}"]}, "result": (width, height)}


async def _load_image(image, **_kwargs):
    name = _safe_asset_name(image)
    pil_image, metadata = await _asset_metadata("input", name)
    rgb = np.asarray(pil_image.convert("RGB"), dtype=np.float32) / 255.0
    pixels = torch.from_numpy(rgb.copy()).unsqueeze(0)
    if "A" in pil_image.getbands():
        alpha = np.asarray(pil_image.getchannel("A"), dtype=np.float32) / 255.0
        mask = 1.0 - torch.from_numpy(alpha.copy()).unsqueeze(0)
    else:
        mask = torch.zeros((1, pil_image.height, pil_image.width), dtype=torch.float32)
    prompt = metadata.get("prompt", {})
    return pixels, mask, prompt, metadata


async def _load_image_fingerprint(image, **_kwargs):
    name = _safe_asset_name(image)
    ref = await _ctx().assets.resolve("input", name)
    return hashlib.sha256(await _ctx().assets.read_bytes(ref)).hexdigest()


_load_image.fingerprint_inputs = _load_image_fingerprint


async def _preview_from_image(image=None, **_kwargs):
    node_id = str(await _ctx().graph.current_node_id())
    if image is None:
        cached = _PREVIEW_CACHE.get(node_id)
        if cached is None:
            return {"ui": {"text": ["Source: Empty"], "images": []},
                    "result": ({},)}
        metadata, ui, text = cached
        return {"ui": {**ui, "text": ["Source: Image link - CACHED\n" + text]},
                "result": (metadata,)}

    preview = await _ctx().ui.preview_images(image)
    images = list(preview.get("images", []))
    if not images:
        raise RuntimeError("preview broker did not return an image")
    item = images[0]
    name = _logical_name(item)
    _pil, metadata = await _asset_metadata(str(item.get("type", "temp")), name)
    text = _preview_text(metadata, "Source: Image link")
    ui = {"images": images}
    _PREVIEW_CACHE[node_id] = (metadata, ui, text)
    return {"ui": {**ui, "text": [text]}, "result": (metadata,)}


async def _preview_from_metadata(metadata_raw=None, **_kwargs):
    node_id = str(await _ctx().graph.current_node_id())
    if not isinstance(metadata_raw, dict) or not metadata_raw:
        cached = _PREVIEW_CACHE.get(node_id)
        if cached is None:
            return {"ui": {"text": ["Source: Empty"], "images": []},
                    "result": ({},)}
        metadata, ui, text = cached
        return {"ui": {**ui, "text": ["Source: Metadata RAW - CACHED\n" + text]},
                "result": (metadata,)}

    metadata = _json_safe(metadata_raw)
    info = metadata.get("fileinfo", {})
    images = []
    if isinstance(info, dict):
        folder = str(info.get("type", "input"))
        if folder in {"input", "output", "temp"}:
            name = info.get("logical_name")
            if not name and info.get("filename"):
                name = _logical_name(info)
            if name:
                name = _safe_asset_name(name)
                await _ctx().assets.resolve(folder, name)
                images.append(_descriptor(folder, name))
    text = _preview_text(metadata, "Source: Metadata RAW")
    ui = {"images": images}
    _PREVIEW_CACHE[node_id] = (metadata, ui, text)
    return {"ui": {**ui, "text": [text]}, "result": (metadata,)}


async def _save_image(
    image,
    filename_prefix="ComfyUI",
    with_workflow=True,
    metadata_extra=None,
    **_kwargs,
):
    extra: dict[str, Any] = {}
    if metadata_extra not in (None, "", "undefined"):
        try:
            parsed = _parse_json_text(metadata_extra, field="metadata_extra")
            extra = parsed if isinstance(parsed, dict) else {"extra": parsed}
        except ValueError:
            extra = {"extra": str(metadata_extra)}
    saved = await _ctx().output.save_images(
        image,
        filename_prefix=str(filename_prefix),
        save_metadata=bool(with_workflow),
        extra_metadata=_json_safe(extra),
    )
    images = list(saved.get("images", []))
    if not images:
        raise RuntimeError("output broker did not return an image")
    item = images[0]
    name = _logical_name(item)
    _pil, metadata = await _asset_metadata("output", name)
    return {"ui": {"images": images, "text": [_preview_text(
        metadata, "Source: Saved image")]}, "result": (metadata,)}


def _diff_json(old: Any, new: Any, path: str = "root") -> dict[str, Any]:
    added: list[str] = []
    removed: list[str] = []
    changed: dict[str, dict[str, Any]] = {}

    def visit(left: Any, right: Any, current: str) -> None:
        if isinstance(left, dict) and isinstance(right, dict):
            left_keys, right_keys = set(left), set(right)
            added.extend(f"{current}[{key!r}]" for key in sorted(right_keys - left_keys))
            removed.extend(f"{current}[{key!r}]" for key in sorted(left_keys - right_keys))
            for key in sorted(left_keys & right_keys):
                visit(left[key], right[key], f"{current}[{key!r}]")
            return
        if isinstance(left, list) and isinstance(right, list):
            for index in range(min(len(left), len(right))):
                visit(left[index], right[index], f"{current}[{index}]")
            added.extend(
                f"{current}[{index}]" for index in range(len(left), len(right))
            )
            removed.extend(
                f"{current}[{index}]" for index in range(len(right), len(left))
            )
            return
        if left != right:
            changed[current] = {
                "old_value": _json_safe(left),
                "new_value": _json_safe(right),
            }

    visit(old, new, path)
    result: dict[str, Any] = {}
    if changed:
        result["values_changed"] = changed
    if added:
        result["dictionary_item_added"] = added
    if removed:
        result["dictionary_item_removed"] = removed
    return result


async def _json_compare(json_old, json_new, **_kwargs):
    old = _parse_json_text(json_old, field="json_old")
    new = _parse_json_text(json_new, field="json_new")
    return _one(json.dumps(_diff_json(old, new), indent=2, ensure_ascii=False))


async def _metadata_compare(what, metadata_raw_old, metadata_raw_new, **_kwargs):
    if not isinstance(metadata_raw_old, dict) or not isinstance(metadata_raw_new, dict):
        raise TypeError("metadata comparator inputs must be metadata mappings")
    keys = {"Prompt": "prompt", "Workflow": "workflow", "Fileinfo": "fileinfo"}
    key = keys.get(str(what), "fileinfo")
    diff = json.dumps(
        _diff_json(metadata_raw_old.get(key, {}), metadata_raw_new.get(key, {})),
        indent=2,
        ensure_ascii=False,
    )
    return {"ui": {"text": [diff]}, "result": (diff,)}


async def _metadata_extract(metadata_raw=None, **_kwargs):
    metadata = metadata_raw if isinstance(metadata_raw, dict) else {}
    prompt = metadata.get("prompt", {})
    workflow = metadata.get("workflow", {})
    fileinfo = metadata.get("fileinfo", {})
    properties = []
    csv = ['"key"\t"value"']
    for key, value in metadata.items():
        encoded = json.dumps(_json_safe(value), ensure_ascii=False)
        properties.append(f'"{key}"={encoded}')
        csv.append(f'"{key}"\t{json.dumps(encoded)}')
    return (
        json.dumps(prompt, indent=2, ensure_ascii=False),
        json.dumps(workflow, indent=2, ensure_ascii=False),
        json.dumps(fileinfo, indent=2, ensure_ascii=False),
        json.dumps(_json_safe(metadata), indent=2, ensure_ascii=False),
        "\n".join(properties) + ("\n" if properties else ""),
        "\n".join(csv) + ("\n" if len(csv) > 1 else ""),
    )


def _nested_value(data: Any, key: str, default: Any) -> Any:
    value = data
    for part in str(key).split("."):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                return default
        if not isinstance(value, dict) or part not in value:
            return default
        value = value[part]
    return value


async def _json_extract(json=None, key="", default=None, **_kwargs):
    data = _parse_json_text(json, field="json")
    value = _nested_value(data, str(key), default) if key else default
    string = str(value)
    try:
        integer = int(value)
    except (TypeError, ValueError, OverflowError):
        integer = 0
    try:
        floating = float(value)
    except (TypeError, ValueError, OverflowError):
        floating = 0.0
    if isinstance(value, str):
        boolean = value.strip().lower() in {"1", "true", "yes", "on"}
    else:
        boolean = bool(value)
    found = value is not default
    text = (
        f"Key found, return value: {value!r}"
        if found else f"Key not found, return default value: {value!r}"
    )
    return {"ui": {"text": [text]},
            "result": (value, string, integer, floating, boolean)}


async def _read_json(path_to_json="", **_kwargs):
    if not str(path_to_json or "").strip():
        return {"ui": {"text": [""]}, "result": ({},)}
    name = _safe_asset_name(path_to_json, extension=".json")
    ref = await _ctx().assets.resolve("input", name)
    if await _ctx().assets.size(ref) > _MAX_JSON_BYTES:
        raise ValueError("JSON input exceeds 16 MiB")
    data = await _ctx().assets.read_bytes(ref)
    try:
        parsed = json.loads(data.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise ValueError("JSON input must be UTF-8") from error
    except json.JSONDecodeError as error:
        raise ValueError("selected file does not contain valid JSON") from error
    text = json.dumps(_json_safe(parsed), indent=2, ensure_ascii=False)
    return {"ui": {"text": [text]}, "result": (parsed,)}


async def _read_json_fingerprint(path_to_json="", **_kwargs):
    if not str(path_to_json or "").strip():
        return "empty"
    name = _safe_asset_name(path_to_json, extension=".json")
    ref = await _ctx().assets.resolve("input", name)
    return hashlib.sha256(await _ctx().assets.read_bytes(ref)).hexdigest()


_read_json.fingerprint_inputs = _read_json_fingerprint


async def _system_stats(latent, **_kwargs):
    stats = await _ctx().system.stats()
    system = stats.get("system", {})
    lines = []
    if system.get("ram_total") is not None:
        used = int(system["ram_total"]) - int(system.get("ram_free", 0))
        lines.append(
            f"Used RAM: {_format_bytes(used)} / "
            f"Total RAM: {_format_bytes(int(system['ram_total']))}"
        )
    for index, device in enumerate(stats.get("devices", [])):
        total = int(device.get("vram_total", 0) or 0)
        free = int(device.get("vram_free", 0) or 0)
        if total:
            lines.append(
                f"Device {index} {device.get('name', '')}: "
                f"{_format_bytes(total - free)} / {_format_bytes(total)}"
            )
    if not lines:
        lines.append("System resource statistics are unavailable")
    text = "Samples Passthrough:\n" + "\n".join(lines)
    return {"ui": {"text": [text]}, "result": (latent,)}


_HANDLERS: dict[str, tuple[Any, tuple[str, ...]]] = {}


def _set(node_ids, handler, *permissions):
    for node_id in node_ids:
        _HANDLERS[node_id] = (handler, tuple(permissions))


_set({
    "Primitive boolean [Crystools]",
    "Primitive string [Crystools]",
    "Primitive string multiline [Crystools]",
    "Primitive integer [Crystools]",
    "Primitive float [Crystools]",
}, _identity)
_set({"Switch from any [Crystools]"}, _switch_from_any)
_set({
    "Switch any [Crystools]",
    "Switch string [Crystools]",
    "Switch conditioning [Crystools]",
    "Switch image [Crystools]",
    "Switch mask [Crystools]",
    "Switch latent [Crystools]",
}, _switch)
_set({"List of any [Crystools]"}, _list_any)
_set({"List of strings [Crystools]"}, _list_string)
_set({"Pipe to/edit any [Crystools]"}, _pipe_to)
_set({"Pipe from any [Crystools]"}, _pipe_from)
_set({"Show any [Crystools]"}, _show_any)
_set({"Show any to JSON [Crystools]"}, _show_json)
_set({"Get resolution [Crystools]"}, _get_resolution)
_set({"Load image with metadata [Crystools]"}, _load_image, "assets", "raw")
_set({"Preview from image [Crystools]"}, _preview_from_image,
     "assets", "ui", "graph")
_set({"Preview from metadata [Crystools]"}, _preview_from_metadata,
     "assets", "graph")
_set({"Save image with extra metadata [Crystools]"}, _save_image,
     "assets", "output")
_set({"JSON comparator [Crystools]"}, _json_compare)
_set({"Metadata comparator [Crystools]"}, _metadata_compare)
_set({"Metadata extractor [Crystools]"}, _metadata_extract)
_set({"JSON extractor [Crystools]"}, _json_extract)
_set({"Read JSON file [Crystools]"}, _read_json, "assets")
_set({"Stats system [Crystools]"}, _system_stats, "system.stats")


if set(_HANDLERS) != set(SCHEMAS):
    raise RuntimeError(
        "Crystools secure conversion coverage changed: "
        f"missing={sorted(set(SCHEMAS) - set(_HANDLERS))}, "
        f"extra={sorted(set(_HANDLERS) - set(SCHEMAS))}"
    )


_LAZY = {
    node_id: _switch_lazy
    for node_id in (
        "Switch any [Crystools]",
        "Switch string [Crystools]",
        "Switch conditioning [Crystools]",
        "Switch image [Crystools]",
        "Switch mask [Crystools]",
        "Switch latent [Crystools]",
    )
}


NODE_CLASS_MAPPINGS = {
    node_id: bind_node(
        node_id,
        handler,
        permissions=permissions,
        check_lazy_status=_LAZY.get(node_id),
    )
    for node_id, (handler, permissions) in _HANDLERS.items()
}
NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: SCHEMAS[node_id]["schema"]["attrs"]["display_name"]
    for node_id in NODE_CLASS_MAPPINGS
}


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
