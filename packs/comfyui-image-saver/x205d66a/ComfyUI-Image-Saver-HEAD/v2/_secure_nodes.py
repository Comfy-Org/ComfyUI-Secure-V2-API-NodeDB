"""Secure Nodes V2 implementations for the pinned Image Saver pack.

Filename templates, collision numbering, metadata formatting, Civitai matching,
CSV sampling, and image-generation algorithms remain pack code.  Host-owned
models, files, output writes, graph data, and Civitai HTTP are reached only
through narrow V2 capabilities.
"""
from __future__ import annotations

import csv
import io as string_io
import json
import math
import posixpath
import random
import re
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any

import numpy as np
import torch
from PIL import Image as PILImage
from PIL import ImageDraw

from ._secure_runtime import SCHEMAS, bind_node, io, sdk


MAX_RESOLUTION = 16384
MAX_HASH_LENGTH = 16
MAX_CSV_BYTES = 16 * 1024 * 1024
MODEL_EXTENSIONS = {
    ".bin", ".ckpt", ".gguf", ".pkl", ".pt", ".pt2", ".pth",
    ".safetensors", ".sft",
}

CIVITAI_SAMPLER_MAP = {
    "euler_ancestral": "Euler a",
    "euler": "Euler",
    "lms": "LMS",
    "heun": "Heun",
    "dpm_2": "DPM2",
    "dpm_2_ancestral": "DPM2 a",
    "dpmpp_2s_ancestral": "DPM++ 2S a",
    "dpmpp_2m": "DPM++ 2M",
    "dpmpp_sde": "DPM++ SDE",
    "dpmpp_2m_sde": "DPM++ 2M SDE",
    "dpmpp_3m_sde": "DPM++ 3M SDE",
    "dpm_fast": "DPM fast",
    "dpm_adaptive": "DPM adaptive",
    "ddim": "DDIM",
    "plms": "PLMS",
    "uni_pc_bh2": "UniPC",
    "uni_pc": "UniPC",
    "lcm": "LCM",
}

_LANDSCAPE_RESOLUTIONS = {
    "1:1": [(512, 512), (768, 768), (1024, 1024), (1280, 1280), (1536, 1536)],
    "9:7": [(576, 448), (864, 672), (1152, 896), (1440, 1120), (1728, 1344)],
    "4:3": [(576, 432), (864, 648), (1152, 864), (1472, 1104), (1728, 1296)],
    "3:2": [(624, 416), (936, 624), (1248, 832), (1536, 1024), (1872, 1248)],
    "16:9": [(640, 360), (1024, 576), (1280, 720), (1536, 864), (2048, 1152)],
    "21:9": [(672, 288), (1008, 432), (1344, 576), (1680, 720), (2016, 864)],
}
_SIZE_INDEX = {
    "XXS (512)": 0,
    "XS (768)": 1,
    "S (1024)": 2,
    "M (1280)": 3,
    "L (1536)": 4,
}

_RE_MANUAL_HASH = re.compile(
    r"^\s*([^:]+?)(?:\s*:\s*([^\s:][^:]*?))?\s*$"
)
_RE_MANUAL_HASH_WEIGHTS = re.compile(
    r"^\s*([^:]+?)(?:\s*:\s*([^\s:][^:]*?))?"
    r"(?:\s*:\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)))?\s*$"
)
_EMBEDDING = r"embedding:([^,\s\(\)\:]+)"
_LORA = r"<lora:([^>:]+)(?::([^>]+))?>"


def _ctx():
    return sdk.ctx()


def _safe_logical(value: str, *, allow_empty: bool = True) -> str:
    value = str(value or "").replace("\\", "/")
    if "\x00" in value or value.startswith("/"):
        raise ValueError("output name must be relative")
    parts = [part for part in value.split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise ValueError("output name escapes the output directory")
    logical = "/".join(parts)
    if not logical and not allow_empty:
        raise ValueError("output name may not be empty")
    return logical


def _sanitize_filename(filename: str) -> str:
    sanitized = re.sub(r'[<>:"|?*\x00-\x1f]', "", filename)
    return sanitized.rstrip(". ")


def _basename(value: str) -> str:
    return PurePosixPath(str(value).replace("\\", "/")).name


def _remove_model_extension(value: str) -> str:
    filename = _basename(value)
    suffix = PurePosixPath(filename).suffix
    return filename[:-len(suffix)] if suffix.lower() in MODEL_EXTENSIONS else filename


def _timestamp(time_format: str, *, now: datetime | None = None) -> str:
    now = now or datetime.now()
    try:
        return now.strftime(time_format)
    except Exception:
        return now.strftime("%Y-%m-%d-%H%M%S")


def _custom_time(filename: str, now: datetime) -> str:
    def replace(match: re.Match[str]) -> str:
        try:
            return now.strftime(match.group(1))
        except Exception:
            return match.group(0)

    return re.sub(r"%time_format<([^>]*)>", replace, filename)


def _custom_counter(filename: str, counter: int) -> str:
    def replace(match: re.Match[str]) -> str:
        try:
            return ("{:0" + match.group(1) + "d}").format(counter)
        except Exception:
            return match.group(0)

    return re.sub(r"%counter<([0-9]+)>", replace, filename)


def _make_pathname(
    filename: str,
    metadata: dict[str, Any],
    counter: int,
    time_format: str,
    *,
    now: datetime | None = None,
) -> str:
    now = now or datetime.now()
    filename = _custom_time(str(filename), now)
    filename = _custom_counter(filename, int(counter))
    replacements = {
        "%date": _timestamp("%Y-%m-%d", now=now),
        "%time": _timestamp(str(time_format), now=now),
        "%model": _basename(metadata["modelname"]),
        "%width": str(metadata["width"]),
        "%height": str(metadata["height"]),
        "%seed": str(metadata["seed"]),
        "%counter": str(counter),
        "%sampler_name": str(metadata["sampler_name"]),
        "%steps": str(metadata["steps"]),
        "%cfg": str(metadata["cfg"]),
        "%scheduler_name": str(metadata["scheduler_name"]),
        "%basemodelname": _remove_model_extension(metadata["modelname"]),
        "%denoise": str(metadata["denoise"]),
        "%clip_skip": str(metadata["clip_skip"]),
        "%custom": str(metadata["custom"]),
    }
    for token, value in replacements.items():
        filename = filename.replace(token, value)
    directory, basename = posixpath.split(filename.replace("\\", "/"))
    return posixpath.join(directory, _sanitize_filename(basename))


def _make_filename(
    filename: str,
    metadata: dict[str, Any],
    counter: int,
    time_format: str,
    *,
    now: datetime | None = None,
) -> str:
    now = now or datetime.now()
    result = _make_pathname(
        filename, metadata, counter, time_format, now=now
    )
    return _timestamp(time_format, now=now) if result == "" else result


def _civitai_sampler_name(sampler_name: str, scheduler: str) -> str:
    if sampler_name in CIVITAI_SAMPLER_MAP:
        value = CIVITAI_SAMPLER_MAP[sampler_name]
        if scheduler == "karras":
            value += " Karras"
        elif scheduler == "exponential":
            value += " Exponential"
        return value
    return f"{sampler_name}_{scheduler}" if scheduler != "normal" else sampler_name


def _asset_match(names: list[str], requested: str) -> str | None:
    requested_path = PurePosixPath(str(requested).replace("\\", "/"))
    has_extension = requested_path.suffix.lower() in MODEL_EXTENSIONS
    if not has_extension:
        for name in names:
            path = PurePosixPath(name)
            if path.with_suffix("") == requested_path:
                return name
        for name in names:
            if PurePosixPath(name).stem == requested_path.name:
                return name
    else:
        for name in names:
            if PurePosixPath(name) == requested_path:
                return name
        for name in names:
            if PurePosixPath(name).name == requested_path.name:
                return name
    return None


async def _asset_resource(
    folders: tuple[str, ...], requested: str,
) -> dict[str, str] | None:
    if not requested:
        return None
    for folder in folders:
        names = await _ctx().assets.list(folder)
        matched = _asset_match(names, requested)
        if matched is None:
            continue
        ref = await _ctx().assets.resolve(folder, matched)
        digest = await _ctx().assets.digest(ref, algorithm="sha256")
        return {"folder": folder, "name": matched, "sha256": digest}
    return None


def _parse_parentheses(string: str) -> list[str]:
    result: list[str] = []
    current = ""
    level = 0
    for char in string:
        if char == "(":
            if level == 0:
                if current:
                    result.append(current)
                current = "("
            else:
                current += char
            level += 1
        elif char == ")":
            level -= 1
            if level == 0:
                result.append(current + ")")
                current = ""
            else:
                current += char
        else:
            current += char
    if current:
        result.append(current)
    return result


def _token_weights(string: str, current_weight: float) -> list[tuple[str, float]]:
    output: list[tuple[str, float]] = []
    for value in _parse_parentheses(string):
        weight = current_weight
        if len(value) >= 2 and value[-1] == ")" and value[0] == "(":
            value = value[1:-1]
            separator = value.rfind(":")
            weight *= 1.1
            if separator > 0:
                try:
                    weight = float(value[separator + 1:])
                    value = value[:separator]
                except Exception:
                    pass
            output.extend(_token_weights(value, weight))
        else:
            output.append((value, current_weight))
    return output


async def _prompt_resources(
    positive: str, negative: str,
) -> tuple[dict[str, tuple[dict[str, str], float, str]], dict[str, tuple[dict[str, str], float, str]]]:
    embeddings: dict[str, tuple[dict[str, str], float, str]] = {}
    loras: dict[str, tuple[dict[str, str], float, str]] = {}
    for prompt in (positive, negative):
        escaped = prompt.replace("\\)", "\0\1").replace("\\(", "\0\2")
        for text, weight in _token_weights(escaped, 1.0):
            text = text.replace("\0\1", ")").replace("\0\2", "(")
            for embedding in re.findall(
                _EMBEDDING, text, re.IGNORECASE | re.MULTILINE
            ):
                resource = await _asset_resource(("embeddings",), embedding)
                if resource is not None:
                    embeddings[f"embed:{embedding}"] = (
                        resource, weight, resource["sha256"][:10]
                    )
        for name, raw_weight in re.findall(
            _LORA, prompt, re.IGNORECASE | re.MULTILINE
        ):
            resource = await _asset_resource(("loras",), name)
            if resource is None:
                continue
            try:
                weight = float(raw_weight.split(":")[0])
            except (ValueError, TypeError):
                weight = 1.0
            loras[f"LORA:{name}"] = (
                resource, weight, resource["sha256"][:10]
            )
    return embeddings, loras


def _parse_manual_hashes(
    additional_hashes: str,
    existing_hashes: set[str],
    download_civitai_data: bool,
) -> dict[str, tuple[None, float | None, str]]:
    manual: dict[str, tuple[None, float | None, str]] = {}
    unnamed = 0
    entries = (
        additional_hashes.replace("\n", ",").split(",")
        if additional_hashes else []
    )
    expression = (
        _RE_MANUAL_HASH_WEIGHTS if download_civitai_data else _RE_MANUAL_HASH
    )
    for entry in entries:
        match = expression.search(entry)
        if match is None:
            continue
        groups = tuple(group for group in match.groups() if group)
        weight = None
        if download_civitai_data and len(groups) > 1:
            try:
                weight = float(groups[-1])
                groups = groups[:-1]
            except (ValueError, TypeError):
                pass
        name, hash_value = groups if len(groups) > 1 else (None, groups[0])
        if len(hash_value) > MAX_HASH_LENGTH:
            continue
        lowered = hash_value.lower()
        if any(lowered == value[2].lower() for value in manual.values()):
            continue
        if lowered in existing_hashes:
            continue
        if name is None:
            unnamed += 1
            name = f"manual{unnamed}"
        manual[name] = (None, weight, hash_value)
        if len(manual) >= 30:
            break
    return manual


async def _multiple_models(
    modelname: str, additional_hashes: str,
) -> tuple[str, str]:
    names = [item.strip() for item in modelname.split(",")]
    primary = names[0]
    for additional in names[1:]:
        resource = await _asset_resource(
            ("checkpoints", "diffusion_models"), additional
        )
        if resource is not None:
            if additional_hashes:
                additional_hashes += ","
            additional_hashes += f"{additional}:{resource['sha256'][:10]}"
    return primary, additional_hashes


async def _civitai_metadata(
    modelname: str,
    model_hash: str,
    loras: dict[str, tuple[Any, float, str]],
    embeddings: dict[str, tuple[Any, float, str]],
    manual: dict[str, tuple[Any, float | None, str]],
    download: bool,
) -> tuple[list[dict[str, Any]], dict[str, str], str | None]:
    entries = {modelname: (None, None, model_hash)} | loras | embeddings | manual
    resources: list[dict[str, Any]] = []
    hashes: dict[str, str] = {}
    model_fallback: str | None = None
    if download:
        for name, (_asset, weight, hash_value) in entries.items():
            info = None
            if hash_value:
                try:
                    info = await _ctx().integrations.call("civitai", "model_version_by_hash", hash_value=hash_value)
                except Exception:
                    info = None
            if isinstance(info, dict):
                model = info.get("model")
                resource: dict[str, Any] = {
                    "modelName": (
                        model.get("name", "") if isinstance(model, dict) else ""
                    ),
                    "versionName": info.get("name", ""),
                }
                if weight is not None:
                    resource["weight"] = weight
                if info.get("air"):
                    resource["air"] = info["air"]
                else:
                    resource["modelVersionId"] = info["id"]
                resources.append(resource)
            elif name == modelname:
                model_fallback = hash_value.upper()
            else:
                hashes[name] = hash_value.upper()
    else:
        hashes = (
            {key: value[2] for key, value in embeddings.items()}
            | {key: value[2] for key, value in loras.items()}
            | {key: value[2] for key, value in manual.items()}
            | {"model": model_hash}
        )
        model_fallback = model_hash
    return resources, hashes, model_fallback


def _clean_prompt(prompt: str) -> str:
    prompt = re.sub(_LORA, "", prompt)
    prompt = re.sub(
        _EMBEDDING,
        lambda match: PurePosixPath(match.group(1)).stem,
        prompt,
    )
    return re.sub(r"\b[A-Z]+\([^)]*\)", "", prompt)


async def _make_metadata(
    modelname: str = "",
    positive: str = "unknown",
    negative: str = "unknown",
    width: int = 512,
    height: int = 512,
    seed_value: int = 0,
    steps: int = 20,
    cfg: float = 7.0,
    sampler_name: str = "",
    scheduler_name: str = "normal",
    denoise: float = 1.0,
    clip_skip: int = 0,
    custom: str = "",
    additional_hashes: str = "",
    download_civitai_data: bool = True,
    easy_remix: bool = True,
) -> dict[str, Any]:
    modelname, additional_hashes = await _multiple_models(
        modelname, additional_hashes
    )
    model = await _asset_resource(
        ("checkpoints", "diffusion_models"), modelname
    )
    model_hash = "" if model is None else model["sha256"][:10]
    embeddings, loras = await _prompt_resources(positive, negative)
    existing = (
        {model_hash.lower()}
        | {value[2].lower() for value in loras.values()}
        | {value[2].lower() for value in embeddings.values()}
    )
    manual = _parse_manual_hashes(
        additional_hashes, existing, download_civitai_data
    )
    civitai_resources, hashes, add_model_hash = await _civitai_metadata(
        modelname,
        model_hash,
        loras,
        embeddings,
        manual,
        download_civitai_data,
    )
    if easy_remix:
        positive = _clean_prompt(positive)
        negative = _clean_prompt(negative)
    positive_params = positive.strip()
    negative_params = f"\nNegative prompt: {negative.strip()}"
    clip = f", Clip skip: {abs(clip_skip)}" if clip_skip != 0 else ""
    custom_value = f", {custom}" if custom else ""
    model_hash_value = (
        f", Model hash: {add_model_hash}" if add_model_hash else ""
    )
    hashes_value = (
        f", Hashes: {json.dumps(hashes, separators=(',', ':'))}"
        if hashes else ""
    )
    params = (
        f"{positive_params}{negative_params}\n"
        f"Steps: {steps}, Sampler: "
        f"{_civitai_sampler_name(sampler_name.replace('_gpu', ''), scheduler_name)}, "
        f"CFG scale: {cfg}, Seed: {seed_value}, Size: {width}x{height}"
        f"{clip}{custom_value}{model_hash_value}, "
        f"Model: {_remove_model_extension(modelname)}{hashes_value}, "
        "Version: ComfyUI"
    )
    if download_civitai_data and civitai_resources:
        params += (
            ", Civitai resources: "
            + json.dumps(civitai_resources, separators=(",", ":"))
        )

    all_resources = {modelname: (model, None, model_hash)} | loras | embeddings | manual
    hash_parts: list[str] = []
    for name, (_asset, weight, hash_value) in all_resources.items():
        if not hash_value:
            continue
        name_part = ""
        if name:
            clean = _remove_model_extension(name.split(":")[-1])
            name_part = f"{clean}:"
        weight_part = (
            f":{weight}"
            if weight is not None and download_civitai_data else ""
        )
        hash_parts.append(f"{name_part}{hash_value}{weight_part}")

    return {
        "modelname": modelname,
        "positive": positive,
        "negative": negative,
        "width": int(width),
        "height": int(height),
        "seed": int(seed_value),
        "steps": int(steps),
        "cfg": float(cfg),
        "sampler_name": sampler_name,
        "scheduler_name": scheduler_name,
        "denoise": float(denoise),
        "clip_skip": int(clip_skip),
        "custom": custom,
        "additional_hashes": additional_hashes,
        "a111_params": params,
        "final_hashes": ",".join(hash_parts),
    }


def _empty_metadata() -> dict[str, Any]:
    return {
        "modelname": "", "positive": "", "negative": "",
        "width": 512, "height": 512, "seed": 0, "steps": 20,
        "cfg": 7.0, "sampler_name": "", "scheduler_name": "normal",
        "denoise": 1.0, "clip_skip": 0, "custom": "",
        "additional_hashes": "", "a111_params": "", "final_hashes": "",
    }


def _format_batch_filename(
    filename_prefix: str, base_suffix: int | None, batch_index: int,
) -> str:
    if base_suffix is None:
        return filename_prefix
    return f"{filename_prefix}_{base_suffix + batch_index:02d}"


def _base_suffix(
    existing_files: list[str], filename_prefix: str,
    extension: str, batch_size: int, reserve_sidecars: bool = False,
) -> int | None:
    suffixes_to_reserve = (f".{extension.lower()}",) + (
        (".json",) if reserve_sidecars else ()
    )
    relevant = [
        PurePosixPath(name).name for name in existing_files
        if PurePosixPath(name).name.startswith(PurePosixPath(filename_prefix).name)
        and name.lower().endswith(suffixes_to_reserve)
    ]
    if batch_size == 1 and not relevant:
        return None
    suffixes: list[int] = []
    for filename in relevant:
        stem = PurePosixPath(filename).stem
        value = stem.split("_")[-1]
        if value.isdigit():
            suffixes.append(int(value))
    return max(suffixes) + 1 if suffixes else 1


async def _save_images(
    images: sdk.ImageRef,
    metadata: dict[str, Any],
    filename: str,
    path: str,
    extension: str,
    lossless_webp: bool,
    quality_jpeg_or_webp: int,
    optimize_png: bool,
    embed_workflow: bool,
    save_workflow_as_json: bool,
    show_preview: bool,
    counter: int,
    time_format: str,
) -> dict[str, Any]:
    now = datetime.now()
    subfolder = _safe_logical(
        _make_pathname(path, metadata, counter, time_format, now=now)
    )
    prefix = _safe_logical(
        _make_filename(filename, metadata, counter, time_format, now=now),
        allow_empty=False,
    )
    prefix_dir, prefix_name = posixpath.split(prefix)
    combined_folder = _safe_logical(posixpath.join(subfolder, prefix_dir))
    try:
        existing = await _ctx().assets.list(
            "output", prefix=combined_folder, recursive=False
        )
    except FileNotFoundError:
        existing = []
    batch_size = int(await images.batch_size())
    suffix = _base_suffix(
        existing, prefix_name, extension, batch_size,
        reserve_sidecars=save_workflow_as_json,
    )
    filenames = [
        f"{_format_batch_filename(prefix_name, suffix, index)}.{extension}"
        for index in range(batch_size)
    ]
    display = await _ctx().output.save_images(
        images,
        filename_prefix=prefix_name,
        subfolder=combined_folder,
        filenames=[
            posixpath.join(combined_folder, name)
            if combined_folder else name
            for name in filenames
        ],
        compress_level=4,
        save_metadata=bool(embed_workflow),
        extra_metadata=(
            {"parameters": metadata["a111_params"]}
            if metadata["a111_params"] else None
        ),
        image_format=extension,
        quality=int(quality_jpeg_or_webp),
        lossless=bool(lossless_webp),
        optimize=bool(optimize_png),
    )
    records = list(display.get("images", []))
    if save_workflow_as_json:
        for record in records:
            image_name = str(record["filename"])
            logical = posixpath.join(
                str(record.get("subfolder") or ""),
                str(PurePosixPath(image_name).with_suffix(".json")),
            )
            await _ctx().output.save_workflow_json(logical, mode="new_only")
    return {
        "result": (metadata["final_hashes"], metadata["a111_params"]),
        **({"ui": display} if show_preview else {}),
    }


# ---------------------------------------------------------------------------
# Loader, saver, metadata, and pipe handlers
# ---------------------------------------------------------------------------


async def _checkpoint_loader(ckpt_name: str, **_kwargs: Any):
    model, clip, vae = await _ctx().models.load_checkpoint(ckpt_name)
    return model, clip, vae, ckpt_name


async def _unet_loader(unet_name: str, weight_dtype: str):
    model = await _ctx().models.load_diffusion_model(
        unet_name, weight_dtype=weight_dtype
    )
    return model, unet_name


async def _metadata_handler(**kwargs: Any):
    metadata = await _make_metadata(**kwargs)
    return metadata, metadata["final_hashes"], metadata["a111_params"]


async def _image_saver(
    images: sdk.ImageRef,
    filename: str,
    path: str,
    extension: str,
    steps: int = 20,
    cfg: float = 7.0,
    modelname: str = "",
    sampler_name: str = "",
    scheduler_name: str = "normal",
    positive: str = "unknown",
    negative: str = "unknown",
    seed_value: int = 0,
    width: int = 512,
    height: int = 512,
    lossless_webp: bool = True,
    quality_jpeg_or_webp: int = 100,
    optimize_png: bool = False,
    counter: int = 0,
    denoise: float = 1.0,
    clip_skip: int = 0,
    time_format: str = "%Y-%m-%d-%H%M%S",
    save_workflow_as_json: bool = False,
    embed_workflow: bool = True,
    additional_hashes: str = "",
    download_civitai_data: bool = True,
    easy_remix: bool = True,
    show_preview: bool = True,
    custom: str = "",
) -> dict[str, Any]:
    metadata = await _make_metadata(
        modelname=modelname,
        positive=positive,
        negative=negative,
        width=width,
        height=height,
        seed_value=seed_value,
        steps=steps,
        cfg=cfg,
        sampler_name=sampler_name,
        scheduler_name=scheduler_name,
        denoise=denoise,
        clip_skip=clip_skip,
        custom=custom,
        additional_hashes=additional_hashes,
        download_civitai_data=download_civitai_data,
        easy_remix=easy_remix,
    )
    return await _save_images(
        images, metadata, filename, path, extension, lossless_webp,
        quality_jpeg_or_webp, optimize_png, embed_workflow,
        save_workflow_as_json, show_preview, counter, time_format,
    )


async def _image_saver_simple(
    images: sdk.ImageRef,
    filename: str,
    path: str,
    extension: str,
    lossless_webp: bool,
    quality_jpeg_or_webp: int,
    optimize_png: bool,
    embed_workflow: bool = True,
    save_workflow_as_json: bool = False,
    show_preview: bool = True,
    metadata: dict[str, Any] | None = None,
    counter: int = 0,
    time_format: str = "%Y-%m-%d-%H%M%S",
) -> dict[str, Any]:
    return await _save_images(
        images, metadata or _empty_metadata(), filename, path, extension,
        lossless_webp, quality_jpeg_or_webp, optimize_png, embed_workflow,
        save_workflow_as_json, show_preview, counter, time_format,
    )


async def _make_simple_config(**kwargs: Any):
    return (kwargs,)


async def _make_metadata_config(**kwargs: Any):
    if "seed" in kwargs:
        kwargs["seed_value"] = kwargs.pop("seed")
    return (kwargs,)


async def _make_pipe(
    simple_saver_config: dict[str, Any], metadata_config: dict[str, Any],
):
    return ({
        "metadata_config": metadata_config,
        "simple_saver_config": simple_saver_config,
    },)


def _string_edit(new_value: Any, original: Any) -> Any:
    if new_value is None or new_value == "[original]":
        return original
    if isinstance(new_value, str) and "[original]" in new_value:
        return new_value.replace(
            "[original]", "" if original is None else str(original)
        )
    return new_value


async def _edit_pipe(pipe: dict[str, Any], **kwargs: Any):
    metadata = dict(pipe["metadata_config"])
    saver = dict(pipe["simple_saver_config"])
    for key in ("filename", "path"):
        saver[key] = _string_edit(kwargs.get(key), saver.get(key))
    if kwargs.get("counter") is not None:
        saver["counter"] = kwargs["counter"]
    for key in (
        "modelname", "positive", "negative", "sampler_name",
        "scheduler_name", "additional_hashes", "custom",
    ):
        metadata[key] = _string_edit(kwargs.get(key), metadata.get(key))
    for key in ("width", "height", "steps", "cfg", "denoise", "clip_skip"):
        if kwargs.get(key) is not None:
            metadata[key] = kwargs[key]
    if kwargs.get("seed") is not None:
        metadata["seed_value"] = kwargs["seed"]
    return ({"metadata_config": metadata, "simple_saver_config": saver},)


_META_DEFAULTS = {
    "modelname": "", "positive": "unknown", "negative": "unknown",
    "width": 512, "height": 512, "seed_value": 0, "steps": 20,
    "cfg": 7.0, "sampler_name": "", "scheduler_name": "normal",
    "denoise": 1.0, "clip_skip": 0, "additional_hashes": "", "custom": "",
}


async def _read_pipe(pipe: dict[str, Any]):
    metadata = pipe["metadata_config"]
    saver = pipe["simple_saver_config"]
    keys = (
        "filename", "path", "counter", "modelname", "positive", "negative",
        "width", "height", "seed", "steps", "cfg", "sampler_name",
        "scheduler_name", "denoise", "clip_skip", "additional_hashes", "custom",
    )
    values: list[Any] = [pipe]
    for key in keys:
        if key in ("filename", "path"):
            values.append(saver.get(key, ""))
        elif key == "counter":
            values.append(saver.get(key, 0))
        else:
            metadata_key = "seed_value" if key == "seed" else key
            values.append(metadata.get(metadata_key, _META_DEFAULTS[metadata_key]))
    return tuple(values)


async def _save_from_pipe(
    pipe: dict[str, Any], images: sdk.ImageRef, show_preview: bool = True,
):
    metadata = await _make_metadata(**pipe["metadata_config"])
    result = await _image_saver_simple(
        images=images,
        metadata=metadata,
        show_preview=show_preview,
        **pipe["simple_saver_config"],
    )
    hashes, params = result["result"]
    result["result"] = (pipe, hashes, params)
    return result


# ---------------------------------------------------------------------------
# Literal, graph, conditioning, and image handlers
# ---------------------------------------------------------------------------


async def _one_value(**kwargs: Any):
    return (next(iter(kwargs.values())),)


async def _seed(seed: int, increment: int):
    return (seed + increment,)


async def _concat_conditioning(
    conditioning_to: sdk.CondRef,
    conditioning_from: sdk.CondRef | None = None,
):
    if conditioning_from is None:
        return (conditioning_to,)
    return (await conditioning_to.concat(conditioning_from),)


def _parse_rgb(value: str) -> tuple[int, int, int] | None:
    if not value or not value.strip():
        return None
    value = value.strip()
    try:
        candidate = value[1:] if value.startswith("#") else value
        if len(candidate) == 6 and all(
            char in "0123456789ABCDEFabcdef" for char in candidate
        ):
            return tuple(
                int(candidate[index:index + 2], 16) for index in (0, 2, 4)
            )  # type: ignore[return-value]
        if value.upper().startswith("RGB(") and value.endswith(")"):
            rgb = tuple(int(item.strip()) for item in value[4:-1].split(","))
            if len(rgb) == 3 and all(0 <= item <= 255 for item in rgb):
                return rgb  # type: ignore[return-value]
    except (ValueError, IndexError):
        pass
    return None


def _draw_shape(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    shape: str,
    color: tuple[int, int, int],
    rng: random.Random,
) -> None:
    factor = rng.uniform(0.4, 0.7)
    shape_width = int(width * factor)
    shape_height = int(height * factor)
    x = rng.randint(0, max(0, width - shape_width))
    y = rng.randint(0, max(0, height - shape_height))
    if shape == "circle":
        radius = min(shape_width, shape_height) // 2
        draw.ellipse([x, y, x + radius * 2, y + radius * 2], fill=color)
    elif shape == "oval":
        draw.ellipse([x, y, x + shape_width, y + shape_height], fill=color)
    elif shape == "square":
        side = min(shape_width, shape_height)
        draw.rectangle([x, y, x + side, y + side], fill=color)
    elif shape == "rectangle":
        draw.rectangle([x, y, x + shape_width, y + shape_height], fill=color)
    elif shape == "triangle":
        draw.polygon([
            (x + shape_width // 2, y),
            (x, y + shape_height),
            (x + shape_width, y + shape_height),
        ], fill=color)
    elif shape == "rhombus":
        draw.polygon([
            (x + shape_width // 2, y),
            (x + shape_width, y + shape_height // 2),
            (x + shape_width // 2, y + shape_height),
            (x, y + shape_height // 2),
        ], fill=color)
    elif shape in {"pentagon", "hexagon"}:
        sides = 5 if shape == "pentagon" else 6
        cx, cy = x + shape_width // 2, y + shape_height // 2
        radius = min(shape_width, shape_height) // 2
        offset = -math.pi / 2 if sides == 5 else 0
        draw.polygon([
            (
                cx + radius * math.cos(i * 2 * math.pi / sides + offset),
                cy + radius * math.sin(i * 2 * math.pi / sides + offset),
            )
            for i in range(sides)
        ], fill=color)


async def _random_shape(
    width: int,
    height: int,
    bg_color: str,
    fg_color: str,
    shape_type: str,
    seed: int,
    bg_color_override: str = "",
    fg_color_override: str = "",
):
    rng = random.Random(seed)
    colors = {
        "white": (255, 255, 255), "black": (0, 0, 0),
        "red": (255, 0, 0), "green": (0, 255, 0), "blue": (0, 0, 255),
        "yellow": (255, 255, 0), "cyan": (0, 255, 255),
        "magenta": (255, 0, 255),
    }

    def choose(override: str, selected: str, fallback: tuple[int, int, int]):
        parsed = _parse_rgb(override)
        if parsed is not None:
            return parsed
        if selected == "random":
            return tuple(rng.randint(0, 255) for _ in range(3))
        return colors.get(selected, fallback)

    background = choose(bg_color_override, bg_color, (255, 255, 255))
    foreground = choose(fg_color_override, fg_color, (0, 0, 0))
    image = PILImage.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(image)
    shape = (
        rng.choice([
            "circle", "oval", "triangle", "square", "rectangle",
            "rhombus", "pentagon", "hexagon",
        ])
        if shape_type == "random" else shape_type
    )
    _draw_shape(draw, width, height, shape, foreground, rng)
    tensor = torch.from_numpy(
        np.asarray(image).astype(np.float32) / 255.0
    ).unsqueeze(0)

    def color_string(rgb: tuple[int, int, int]) -> str:
        return (
            f"RGB({rgb[0]}, {rgb[1]}, {rgb[2]}) / "
            f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"
        )

    return tensor, color_string(background), color_string(foreground)


async def _empty_latent(
    aspect_ratio: str,
    orientation: str,
    size: str,
    batch_size: int,
    width_override: int = 0,
    height_override: int = 0,
):
    width, height = _LANDSCAPE_RESOLUTIONS[aspect_ratio][_SIZE_INDEX[size]]
    if orientation == "portrait" and width != height:
        width, height = height, width
    width = width_override if width_override > 0 else width
    height = height_override if height_override > 0 else height
    latent = await sdk.LatentRef.empty(
        width=width,
        height=height,
        batch_size=batch_size,
        channels=4,
        spatial_downscale_ratio=8,
    )
    return latent, width, height


async def _any_to_string(value: Any):
    return (str(value),)


async def _workflow_input(node_id: str, input_name: str):
    try:
        values = await _ctx().graph.widget_values(node_id=node_id)
    except (KeyError, ValueError):
        return (None,)
    return (values.get(input_name),)


async def _pair_name(**kwargs: Any):
    value = next(iter(kwargs.values()))
    return value, value


async def _input_parameters(
    seed: int, steps: int, cfg: float,
    sampler: str, scheduler: str, denoise: float,
):
    return seed, steps, cfg, sampler, scheduler, denoise


# ---------------------------------------------------------------------------
# Managed CSV tag pickers
# ---------------------------------------------------------------------------


def _process_tag(
    tag: str, replace_underscore: bool, escape_parens: bool = True,
) -> str:
    tag = tag.strip()
    if replace_underscore:
        tag = tag.replace("_", " ")
    if escape_parens:
        tag = tag.replace("(", "\\(").replace(")", "\\)")
    return tag


def _split_csv_field(
    value: str, replace_underscore: bool, escape_parens: bool = True,
) -> list[str]:
    return [
        _process_tag(tag, replace_underscore, escape_parens)
        for tag in value.split(",") if tag.strip()
    ]


def _normalize(value: str) -> str:
    return value.strip().lower().replace("_", " ")


def _parse_exclude(value: str) -> set[str]:
    return {_normalize(item) for item in value.split(",") if item.strip()}


def _weighted_sample(
    rng: random.Random, rows: list[dict[str, str]], weights: list[float], k: int,
) -> list[dict[str, str]]:
    rows = list(rows)
    weights = list(weights)
    selected: list[dict[str, str]] = []
    for _ in range(min(k, len(rows))):
        [chosen] = rng.choices(rows, weights=weights, k=1)
        index = rows.index(chosen)
        selected.append(chosen)
        rows.pop(index)
        weights.pop(index)
    return selected


def _sample_rows(
    rng: random.Random,
    rows: list[dict[str, str]],
    count: int,
    weight_by_count: bool,
) -> list[dict[str, str]]:
    if weight_by_count:
        weights = [max(float(row.get("count", 1) or 1), 1.0) for row in rows]
        return _weighted_sample(rng, rows, weights, count)
    return rng.sample(rows, min(count, len(rows)))


async def _csv_rows(file_path: str) -> list[dict[str, str]]:
    ref = await _ctx().assets.resolve("input", file_path)
    if await _ctx().assets.size(ref) > MAX_CSV_BYTES:
        raise ValueError("CSV input exceeds 16 MiB")
    data = await _ctx().assets.read_bytes(ref)
    text = data.decode("utf-8-sig")
    return list(csv.DictReader(string_io.StringIO(text, newline="")))


async def _random_tags(
    file_path: str, count: int, delimiter: str,
    replace_underscore: bool, escape_parens: bool, trailing_comma: bool,
    weight_by_count: bool, seed: int, exclude: str, filter: str,
):
    excluded = _parse_exclude(exclude)
    needle = _normalize(filter)
    rows = [
        row for row in await _csv_rows(file_path)
        if row.get("tag", "").strip()
        and (not needle or needle in _normalize(row["tag"]))
        and _normalize(row["tag"]) not in excluded
    ]
    selected = _sample_rows(random.Random(seed), rows, count, weight_by_count)
    result = delimiter.join(
        _process_tag(row["tag"], replace_underscore, escape_parens)
        for row in selected
    )
    return (result + ("," if trailing_comma else ""),)


async def _random_characters(
    file_path: str, count: int, delimiter: str,
    replace_underscore: bool, escape_parens: bool, trailing_comma: bool,
    weight_by_count: bool, seed: int, include_core_tags: bool,
    include_copyright: bool, exclude: str, filter: str,
):
    excluded = _parse_exclude(exclude)
    needle = _normalize(filter)
    rows = [
        row for row in await _csv_rows(file_path)
        if (not needle or needle in _normalize(row.get("character", "")))
        and _normalize(row.get("character", "")) not in excluded
    ]
    selected = _sample_rows(random.Random(seed), rows, count, weight_by_count)
    parts: list[str] = []
    for row in selected:
        parts.extend(_split_csv_field(
            row.get("trigger", ""), replace_underscore, escape_parens
        ))
        if include_core_tags:
            parts.extend(_split_csv_field(
                row.get("core_tags", ""), replace_underscore, escape_parens
            ))
        if include_copyright:
            parts.extend(_split_csv_field(
                row.get("copyright", ""), replace_underscore, escape_parens
            ))
    result = delimiter.join(parts)
    return (result + ("," if trailing_comma else ""),)


async def _random_artists(
    file_path: str, count: int, delimiter: str,
    replace_underscore: bool, escape_parens: bool, trailing_comma: bool,
    weight_by_count: bool, seed: int, prefix: str, exclude: str, filter: str,
):
    excluded = _parse_exclude(exclude)
    needle = _normalize(filter)
    rows = [
        row for row in await _csv_rows(file_path)
        if (not needle or needle in _normalize(row.get("artist", "")))
        and _normalize(row.get("artist", "")) not in excluded
    ]
    selected = _sample_rows(random.Random(seed), rows, count, weight_by_count)
    triggers = [
        prefix + _process_tag(
            row.get("trigger", ""), replace_underscore, escape_parens
        )
        for row in selected if row.get("trigger", "").strip()
    ]
    result = delimiter.join(triggers)
    return (result + ("," if trailing_comma else ""),)


# ---------------------------------------------------------------------------
# Civitai vendor node
# ---------------------------------------------------------------------------


_CIVITAI_HASH_CACHE: dict[tuple[str, str, str], str] = {}


async def _civitai_hash(username: str, model_name: str, version: str = ""):
    key = (username, model_name, version)
    if key in _CIVITAI_HASH_CACHE:
        return (_CIVITAI_HASH_CACHE[key],)
    try:
        data = await _ctx().integrations.call("civitai", "search_models", username=username, query=model_name, limit=20, nsfw=True)
        items = list(data.get("items", []))
        if not items:
            data = await _ctx().integrations.call("civitai", "search_models", username=username, query=None, limit=100, nsfw=True)
            items = list(data.get("items", []))
        if not items:
            return (f"No models found for user '{username}' with name '{model_name}'",)
        lowered = model_name.lower()
        chosen = next(
            (item for item in items if str(item.get("name", "")).lower() == lowered),
            None,
        )
        if chosen is None:
            chosen = next((
                item for item in items
                if lowered in str(item.get("name", "")).lower()
                or str(item.get("name", "")).lower().startswith(lowered)
            ), None)
        chosen = chosen or items[0]
        versions = list(chosen.get("modelVersions", []))
        if not versions:
            return ("No model versions found.",)
        selected = None
        if version:
            selected = next((
                item for item in versions
                if version.lower() in str(item.get("name", "")).lower()
            ), None)
        selected = selected or versions[0]
        details = await _ctx().integrations.call("civitai", "model_version", model_version_id=selected["id"])
        for file_info in details.get("files", []):
            hashes = file_info.get("hashes", {})
            value = hashes.get("AutoV3") if isinstance(hashes, dict) else None
            if value:
                if len(_CIVITAI_HASH_CACHE) >= 64:
                    _CIVITAI_HASH_CACHE.pop(next(iter(_CIVITAI_HASH_CACHE)))
                _CIVITAI_HASH_CACHE[key] = str(value)
                return (str(value),)
        return ("No AutoV3 hash found in version files.",)
    except Exception as error:
        return (f"Error: {error}",)


# ---------------------------------------------------------------------------
# Registration ledger: every pinned V1 node is represented exactly once.
# ---------------------------------------------------------------------------


NODE_CLASS_MAPPINGS = {
    "Checkpoint Loader with Name (Image Saver)": bind_node(
        "Checkpoint Loader with Name (Image Saver)", _checkpoint_loader,
        permissions=("models",),
    ),
    "UNet loader with Name (Image Saver)": bind_node(
        "UNet loader with Name (Image Saver)", _unet_loader,
        permissions=("models",),
    ),
    "Image Saver": bind_node(
        "Image Saver", _image_saver,
        permissions=("assets", "integrations.civitai", "output"),
    ),
    "Image Saver Simple": bind_node(
        "Image Saver Simple", _image_saver_simple,
        permissions=("assets", "output"),
    ),
    "Image Saver Metadata": bind_node(
        "Image Saver Metadata", _metadata_handler,
        permissions=("assets", "integrations.civitai"),
    ),
    "Make Image Saver Simple Config": bind_node(
        "Make Image Saver Simple Config", _make_simple_config,
    ),
    "Make Image Saver Metadata Config": bind_node(
        "Make Image Saver Metadata Config", _make_metadata_config,
    ),
    "Make Image Saver Pipe": bind_node(
        "Make Image Saver Pipe", _make_pipe,
    ),
    "Edit Image Saver Pipe": bind_node(
        "Edit Image Saver Pipe", _edit_pipe,
    ),
    "Read Image Saver Pipe": bind_node(
        "Read Image Saver Pipe", _read_pipe,
    ),
    "Image Saver (From Pipe)": bind_node(
        "Image Saver (From Pipe)", _save_from_pipe,
        permissions=("assets", "integrations.civitai", "output"),
    ),
    "Sampler Selector (Image Saver)": bind_node(
        "Sampler Selector (Image Saver)", _pair_name,
    ),
    "Scheduler Selector (Image Saver)": bind_node(
        "Scheduler Selector (Image Saver)", _pair_name,
    ),
    "Scheduler Selector (inspire) (Image Saver)": bind_node(
        "Scheduler Selector (inspire) (Image Saver)", _pair_name,
    ),
    "Scheduler Selector (Eff.) (Image Saver)": bind_node(
        "Scheduler Selector (Eff.) (Image Saver)", _pair_name,
    ),
    "Input Parameters (Image Saver)": bind_node(
        "Input Parameters (Image Saver)", _input_parameters,
    ),
    "Any to String (Image Saver)": bind_node(
        "Any to String (Image Saver)", _any_to_string,
        accept_all_inputs=True,
    ),
    "Workflow Input Value (Image Saver)": bind_node(
        "Workflow Input Value (Image Saver)", _workflow_input,
        permissions=("graph",),
    ),
    "Seed Generator (Image Saver)": bind_node(
        "Seed Generator (Image Saver)", _seed,
    ),
    "String Literal (Image Saver)": bind_node(
        "String Literal (Image Saver)", _one_value,
    ),
    "Width/Height Literal (Image Saver)": bind_node(
        "Width/Height Literal (Image Saver)", _one_value,
    ),
    "Cfg Literal (Image Saver)": bind_node(
        "Cfg Literal (Image Saver)", _one_value,
    ),
    "Int Literal (Image Saver)": bind_node(
        "Int Literal (Image Saver)", _one_value,
    ),
    "Float Literal (Image Saver)": bind_node(
        "Float Literal (Image Saver)", _one_value,
    ),
    "Conditioning Concat Optional (Image Saver)": bind_node(
        "Conditioning Concat Optional (Image Saver)", _concat_conditioning,
    ),
    "RandomShapeGenerator": bind_node(
        "RandomShapeGenerator", _random_shape, permissions=("raw",),
    ),
    "Empty Latent (Image Saver)": bind_node(
        "Empty Latent (Image Saver)", _empty_latent,
    ),
    "Civitai Hash Fetcher (Image Saver)": bind_node(
        "Civitai Hash Fetcher (Image Saver)", _civitai_hash,
        permissions=("integrations.civitai",),
    ),
    "Random Tag Picker (Image Saver)": bind_node(
        "Random Tag Picker (Image Saver)", _random_tags,
        permissions=("assets",),
    ),
    "Random Character Picker (Image Saver)": bind_node(
        "Random Character Picker (Image Saver)", _random_characters,
        permissions=("assets",),
    ),
    "Random Artist Picker (Image Saver)": bind_node(
        "Random Artist Picker (Image Saver)", _random_artists,
        permissions=("assets",),
    ),
}

NODE_DISPLAY_NAME_MAPPINGS: dict[str, str] = {}

assert set(NODE_CLASS_MAPPINGS) == set(SCHEMAS)


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
