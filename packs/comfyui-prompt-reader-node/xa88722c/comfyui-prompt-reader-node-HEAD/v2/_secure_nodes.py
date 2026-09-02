"""Secure V2 implementation of the pinned SD Prompt Reader nodes."""
from __future__ import annotations

import io as pyio
import json
import posixpath
import re
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any

import numpy as np
import torch
from PIL import Image, ImageOps

from ._secure_runtime import SCHEMAS, bind_node, sdk
from .stable_diffusion_prompt_reader.sd_prompt_reader.image_data_reader import (
    ImageDataReader,
)


_SUPPORTED_FORMATS = frozenset({".png", ".jpg", ".jpeg", ".webp"})
_ASPECT_RATIO_MAP = {
    "1:1": (512, 512),
    "4:3": (576, 448),
    "3:4": (448, 576),
    "3:2": (608, 416),
    "2:3": (416, 608),
    "16:9": (672, 384),
    "9:16": (384, 672),
    "21:9": (768, 320),
    "9:21": (320, 768),
}
_MODEL_SCALING_FACTOR = {
    "SDv1 512px": 1.0,
    "SDv2 768px": 1.5,
    "SDXL 1024px": 2.0,
}
_FORMAT_ERROR = (
    "No data detected or unsupported format. Please see the README for more "
    "details.\nhttps://github.com/receyuki/comfyui-prompt-reader-node"
    "#supported-formats"
)
_COMFY_ERROR = (
    "The workflow is overly complex, or unsupported custom nodes have been "
    "used. Please see the README for more details.\n"
    "https://github.com/receyuki/comfyui-prompt-reader-node#prompt-reader-node"
)
_TI_PATTERN = re.compile(
    r"(?:\(|\s|,)?embedding:([^\s:,()]+)(?:\.(?:pt|safetensors))?"
    r"(?::\d+(?:\.\d+)?)?(?:\)|,|\s)?"
)


def _ctx():
    return sdk.ctx()


def _logical_name(value: Any, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise TypeError("asset name must be a string")
    logical = value.replace("\\", "/")
    if ("\x00" in logical or logical.startswith("/")
            or (len(logical) > 1 and logical[1] == ":")
            or any(part == ".." for part in logical.split("/"))):
        raise ValueError("asset name must stay inside its managed catalogue")
    parts = [part for part in logical.split("/") if part not in ("", ".")]
    result = "/".join(parts)
    if not result and not allow_empty:
        raise ValueError("asset name cannot be empty")
    return result


def _output_path(value: Any, *, allow_empty: bool = True) -> str:
    logical = _logical_name(str(value), allow_empty=allow_empty)
    if len(logical.encode("utf-8")) > 768:
        raise ValueError("output path is too long")
    return logical


async def _asset_names(folder: str) -> list[str]:
    try:
        return [str(item) for item in await _ctx().assets.list(folder)]
    except FileNotFoundError:
        return []


def _match_asset(names: list[str], requested: str) -> str | None:
    if not requested:
        return None
    normalized = requested.replace("\\", "/")
    if normalized in names:
        return normalized
    path = PurePosixPath(normalized)
    for item in names:
        if PurePosixPath(item).name == path.name:
            return item
    for item in names:
        if PurePosixPath(item).stem == path.stem:
            return item
    return None


async def _asset_hash(folder: str, requested: str) -> tuple[str, str]:
    logical = _logical_name(requested)
    names = await _asset_names(folder)
    matched = _match_asset(names, logical)
    if matched is None:
        raise FileNotFoundError(
            f"no {folder} asset matching {requested!r}")
    ref = await _ctx().assets.resolve(folder, matched)
    return matched, (await _ctx().assets.digest(ref, algorithm="sha256"))[:10]


def _param(data: Any, index: int):
    try:
        values = data.strip("()").split(",")
    except AttributeError:
        return None
    return values[0] if len(values) == 1 else values[int(index)]


async def _reader(image: str, parameter_index: int = 0, **_hidden):
    logical = _logical_name(image)
    asset = await _ctx().assets.resolve("input", logical)
    payload = await _ctx().assets.read_bytes(asset)

    with Image.open(pyio.BytesIO(payload)) as source:
        oriented = ImageOps.exif_transpose(source)
        width, height = oriented.width, oriented.height
        rgb = np.asarray(oriented.convert("RGB"), dtype=np.float32) / 255.0
        image_value = torch.from_numpy(rgb.copy()).unsqueeze(0)
        if "A" in oriented.getbands():
            alpha = np.asarray(oriented.getchannel("A"), dtype=np.float32) / 255.0
            mask_value = 1.0 - torch.from_numpy(alpha.copy())
        else:
            mask_value = torch.zeros((64, 64), dtype=torch.float32)

    parsed = ImageDataReader(pyio.BytesIO(payload))
    status = parsed.status.name
    filename = PurePosixPath(logical).stem
    if status in {"COMFYUI_ERROR", "FORMAT_ERROR", "UNREAD"}:
        message = _COMFY_ERROR if status == "COMFYUI_ERROR" else _FORMAT_ERROR
        return {
            "ui": {"text": ("", "", message)},
            "result": (
                image_value, mask_value, "", "", 0, 0, 0.0,
                width, height, "", filename, "",
            ),
        }

    index = int(parameter_index)
    seed = int(_param(parsed.parameter.get("seed", 0), index) or 0)
    steps = int(_param(parsed.parameter.get("steps", 0), index) or 0)
    cfg = float(_param(parsed.parameter.get("cfg", 0), index) or 0)
    requested_model = str(_param(parsed.parameter.get("model", ""), index) or "")
    model = _match_asset(await _asset_names("checkpoints"), requested_model)
    model = requested_model if model is None else model
    return {
        "ui": {"text": (parsed.positive, parsed.negative, parsed.setting)},
        "result": (
            image_value,
            mask_value,
            parsed.positive,
            parsed.negative,
            seed,
            steps,
            cfg,
            int(parsed.width or 0),
            int(parsed.height or 0),
            model,
            filename,
            parsed.setting,
        ),
    }


def _render(template: str, variables: dict[str, Any]) -> str:
    result = str(template)
    for key, value in variables.items():
        result = result.replace(key, str(value))
    return result


def _formatted_time(pattern: str, now: datetime) -> str:
    try:
        return now.strftime(str(pattern))
    except Exception:
        return ""


def _source_filename(stem: str, extension: str) -> str:
    path = PurePosixPath(stem)
    return str(path.with_suffix(f"{path.suffix}.{extension}"))


def _unique_filename(
    stem: str, extension: str, subfolder: str, existing: set[str],
) -> str:
    candidate = _source_filename(stem, extension)
    index = 0
    while posixpath.join(subfolder, candidate) in existing:
        index += 1
        candidate = _source_filename(f"{stem}_{index}", extension)
    return candidate


async def _resource_metadata(
    model_name: str,
    vae_name: str,
    lora_name: Any,
    positive: str,
    negative: str,
    calculate_hash: bool,
) -> tuple[dict[str, str], str, str, str, str]:
    if not calculate_hash:
        return {}, "", "", "", ""
    hashes: dict[str, str] = {}
    model_hash_str = ""
    vae_hash_str = ""
    lora_hash_str = ""
    ti_hash_str = ""

    if model_name:
        _matched, digest = await _asset_hash("checkpoints", model_name)
        hashes["model"] = digest
        model_hash_str = f"Model hash: {digest}, "
    if vae_name:
        _matched, digest = await _asset_hash("vae", vae_name)
        hashes["vae"] = digest
        vae_hash_str = f"VAE hash: {digest}, "

    if lora_name:
        values = lora_name if isinstance(lora_name, list) else [lora_name]
        lora_hashes: dict[str, str] = {}
        for value in dict.fromkeys(str(item) for item in values):
            matched, digest = await _asset_hash("loras", value)
            stem = PurePosixPath(matched).stem
            lora_hashes[stem] = digest
            hashes[f"lora:{stem}"] = digest
        joined = ", ".join(f"{key}: {value}" for key, value in lora_hashes.items())
        lora_hash_str = f'Lora hashes: "{joined}", '

    ti_hashes: dict[str, str] = {}
    embeddings = await _asset_names("embeddings")
    for requested in _TI_PATTERN.findall(f"{positive}/n{negative}"):
        matched = _match_asset(embeddings, requested)
        if matched is None:
            continue
        ref = await _ctx().assets.resolve("embeddings", matched)
        digest = (await _ctx().assets.digest(ref, algorithm="sha256"))[:10]
        stem = PurePosixPath(matched).stem
        ti_hashes[stem] = digest
        hashes[f"embed:{stem}"] = digest
    if ti_hashes:
        joined = ", ".join(f"{key}: {value}" for key, value in ti_hashes.items())
        ti_hash_str = f'TI hashes: "{joined}", '
    return hashes, model_hash_str, vae_hash_str, lora_hash_str, ti_hash_str


async def _saver(
    images: sdk.ImageRef,
    filename: str = "ComfyUI_%time_%seed_%counter",
    path: str = "%date/",
    model_name: str = "",
    vae_name: str = "",
    seed: int = 0,
    steps: int = 0,
    cfg: float = 0.0,
    sampler_name: str = "",
    scheduler: str = "",
    lora_name=None,
    width: int = 1,
    height: int = 1,
    positive: str = "",
    negative: str = "",
    extension: str = "png",
    calculate_hash: bool = True,
    resource_hash: bool = True,
    lossless_webp: bool = True,
    jpg_webp_quality: int = 100,
    date_format: str = "%Y-%m-%d",
    time_format: str = "%H%M%S",
    save_metadata_file: bool = False,
    extra_info: str = "",
    **_hidden,
):
    extension = str(extension).lower()
    if extension not in {"png", "jpg", "jpeg", "webp"}:
        raise ValueError("extension must be png, jpg, jpeg, or webp")
    model_name = str(model_name or "")
    vae_name = str(vae_name or "")
    sampler_name = str(sampler_name or "")
    scheduler = str(scheduler or "")
    batch_size = await images.batch_size()
    image_height, image_width = await images.spatial_shape()
    save_width = image_width if int(width) == 0 else int(width)
    save_height = image_height if int(height) == 0 else int(height)

    hashes, model_hash, vae_hash, lora_hash, ti_hash = await _resource_metadata(
        model_name, vae_name, lora_name, str(positive), str(negative),
        bool(calculate_hash),
    )
    vae_text = f"VAE: {PurePosixPath(vae_name).stem}, " if vae_name else ""
    hashes_text = (
        f", Hashes: {json.dumps(hashes)}"
        if hashes and bool(resource_hash) else ""
    )
    extra_text = f", Extra info: {extra_info}" if extra_info else ""
    comment = (
        f"{positive}\nNegative prompt: {negative}\n"
        f"Steps: {int(steps)}, "
        f"Sampler: {sampler_name}{'' if scheduler == 'normal' else '_' + scheduler}, "
        f"CFG scale: {float(cfg)}, Seed: {int(seed)}, "
        f"Size: {save_width}x{save_height}, "
        f"{model_hash}Model: {PurePosixPath(model_name).stem}, "
        f"{vae_hash}{vae_text}{lora_hash}{ti_hash}Version: ComfyUI"
        f"{hashes_text}{extra_text}"
    )

    existing = set(await _asset_names("output"))
    now = datetime.now()
    variables = {
        "%date": _formatted_time(date_format, now),
        "%time": _formatted_time(time_format, now),
        "%seed": int(seed),
        "%steps": int(steps),
        "%cfg": float(cfg),
        "%width": save_width,
        "%height": save_height,
        "%extension": extension,
        "%model": PurePosixPath(model_name).stem,
        "%sampler": sampler_name,
        "%scheduler": scheduler,
        "%quality": int(jpg_webp_quality),
    }
    subfolder = _output_path(_render(path, variables), allow_empty=True)
    current_files = [
        item for item in existing
        if not subfolder or item == subfolder or item.startswith(subfolder + "/")
    ]
    counter = 1 + sum(
        PurePosixPath(item).suffix.lower() in _SUPPORTED_FORMATS
        for item in current_files
    )
    filenames: list[str] = []
    for _index in range(batch_size):
        variables["%counter"] = f"{counter:05}"
        stem = _output_path(_render(filename, variables), allow_empty=False)
        local = _unique_filename(stem, extension, subfolder, existing)
        logical = posixpath.join(subfolder, local) if subfolder else local
        logical = _output_path(logical, allow_empty=False)
        existing.add(logical)
        filenames.append(logical)
        counter += 1

    saved = await _ctx().output.save_images(
        images,
        filename_prefix="ComfyUI",
        subfolder=subfolder,
        compress_level=4,
        save_metadata=True,
        a1111_parameters=comment,
        image_format=extension,
        quality=int(jpg_webp_quality),
        filenames=filenames,
        lossless=bool(lossless_webp),
    )
    records = list(saved.get("images", []))
    if save_metadata_file:
        for logical in filenames:
            await _ctx().output.write_text(
                comment,
                str(PurePosixPath(logical).with_suffix(".txt")),
                folder="output",
                mode="new_only",
            )
    files = [str(item.get("filename", "")) for item in records]
    logical_paths = [
        posixpath.join(str(item.get("subfolder") or ""), str(item.get("filename") or ""))
        for item in records
    ]

    def unpack(values: list[str]):
        return values[0] if len(values) == 1 else values

    comments = [comment] * len(records)
    return {
        "ui": saved,
        "result": (unpack(files), unpack(logical_paths), unpack(comments)),
    }


async def _parameter_generator(
    ckpt_name: str,
    vae_name: str = "baked VAE",
    model_version: str = "SDv1 512px",
    config_name: str = "none",
    seed: int = -1,
    steps: int = 20,
    refiner_start: float = 0.8,
    cfg: float = 8.0,
    sampler_name: str = "euler",
    scheduler: str = "simple",
    positive_ascore: float = 6.0,
    negative_ascore: float = 6.0,
    aspect_ratio: str = "custom",
    width: int = 512,
    height: int = 512,
    batch_size: int = 1,
    **_kwargs,
):
    if model_version not in _MODEL_SCALING_FACTOR:
        raise ValueError(f"unknown model version {model_version!r}")
    selected_config = None if config_name == "none" else str(config_name)
    model, clip, vae = await _ctx().models.load_checkpoint(
        str(ckpt_name), config_name=selected_config)
    vae_name_real = ""
    vae_text = ""
    if vae_name != "baked VAE":
        vae = await _ctx().models.load_vae(str(vae_name))
        vae_name_real = str(vae_name)
        vae_text = f"VAE: {vae_name}, \n"

    aspect_value = str(aspect_ratio).split(" - ")[0]
    if aspect_value != "custom":
        if aspect_value not in _ASPECT_RATIO_MAP:
            raise ValueError(f"unknown aspect ratio {aspect_ratio!r}")
        scale = _MODEL_SCALING_FACTOR[model_version]
        width = int(_ASPECT_RATIO_MAP[aspect_value][0] * scale)
        height = int(_ASPECT_RATIO_MAP[aspect_value][1] * scale)
    base_steps = int(int(steps) * float(refiner_start))
    refiner_steps = int(steps) - base_steps
    ascore = (
        f"Positive aesthetic score: {float(positive_ascore)},\n"
        f"Negative aesthetic score: {float(negative_ascore)},\n"
        if model_version == "SDXL 1024px" else ""
    )
    parameters = (
        f"Model: {ckpt_name},\n{vae_text}Seed: {int(seed)},\n"
        f"Steps: {int(steps)},\nCFG scale: {float(cfg)},\n"
        f"Sampler: {sampler_name},\nScheduler: {scheduler},\n{ascore}"
        f"Size: {int(width)}x{int(height)},\nBatch size: {int(batch_size)}\n"
    )
    ui = (
        aspect_value, model_version, int(width), int(height), int(steps),
        float(refiner_start), base_steps, refiner_steps,
        _ASPECT_RATIO_MAP, _MODEL_SCALING_FACTOR,
    )
    return {
        "ui": {"text": ui},
        "result": (
            str(ckpt_name), vae_name_real, model, clip, vae, int(seed),
            int(steps), base_steps, float(cfg), str(sampler_name),
            str(scheduler), float(positive_ascore), float(negative_ascore),
            int(width), int(height), int(batch_size), parameters,
        ),
    }


async def _prompt_merger(text_g: str = "", text_l: str = ""):
    return (text_g + ("\n" + text_l if text_g and text_l else text_l),)


async def _type_converter(
    model_name: str = "", sampler_name: str = "", scheduler: str = "",
):
    return model_name, sampler_name, scheduler


async def _any_converter(any_type_input: Any = ""):
    return (any_type_input,)


async def _batch_loader(
    path: Any = "", image_load_limit: int = 0, start_index: int = 0,
    **_hidden,
):
    selected: list[str]
    if isinstance(path, list):
        selected = [_logical_name(item) for item in path]
    elif isinstance(path, str) and path.lstrip().startswith("["):
        decoded = json.loads(path)
        if not isinstance(decoded, list) or not all(
            isinstance(item, str) for item in decoded
        ):
            raise ValueError("selected batch must be a JSON array of asset names")
        selected = [_logical_name(item) for item in decoded]
    else:
        logical = _logical_name(path, allow_empty=True)
        names = await _ctx().assets.list(
            "input", prefix=logical, recursive=False)
        selected = [str(item) for item in names]
        if not selected and logical:
            await _ctx().assets.resolve("input", logical)
            selected = [logical]

    selected = sorted(
        item for item in selected
        if PurePosixPath(item).suffix.lower() in _SUPPORTED_FORMATS
    )
    for logical in selected:
        await _ctx().assets.resolve("input", logical)
    start = max(0, int(start_index))
    limit = max(0, int(image_load_limit))
    result = selected[start:start + limit] if limit else selected[start:]
    return {"ui": {"text": ("\n".join(result),)}, "result": (result,)}


_SETTING_PATTERN = re.compile(
    r'([^:,]+):\s*\(([^)]+)\)|([^:,]+):\s*"([^"]+)"|'
    r"([^:,]+):\s*([^,]+)"
)


def _parse_setting(settings: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for match in _SETTING_PATTERN.findall(settings):
        key_paren, value_paren, key_quotes, value_quotes, key_plain, value_plain = match
        if key_paren:
            result[key_paren.strip()] = tuple(
                value.strip() for value in value_paren.split(","))
        elif key_quotes:
            result[key_quotes.strip()] = value_quotes.strip()
        else:
            result[key_plain.strip()] = value_plain.strip()
    return result


async def _parameter_extractor(
    settings: str = "", parameter: str = "",
    value_type: str = "STRING", parameter_index: int = 0, **_hidden,
):
    setting = _parse_setting(settings)
    keys = list(setting)
    if not settings or not parameter or parameter == "parameters not loaded":
        return {"ui": {"text": (keys, "")}, "result": ("",)}
    value = setting.get(parameter)
    try:
        if isinstance(value, tuple):
            value = value[int(parameter_index)]
        if value_type == "INT":
            value = int(value)
        elif value_type == "FLOAT":
            value = float(value)
    except IndexError:
        return {
            "ui": {"text": (keys, "Parameter index out of range")},
            "result": ("",),
        }
    except (TypeError, ValueError):
        return {
            "ui": {"text": (
                keys,
                f"{parameter}: {value}\n{value} is not a valid number; "
                "it will be output as STRING",
            )},
            "result": (value,),
        }
    return {"ui": {"text": (keys, f"{parameter}: {value}")}, "result": (value,)}


async def _lora_loader(
    model: sdk.ModelRef,
    clip: sdk.ClipRef,
    lora_name: str,
    strength_model: float,
    strength_clip: float,
    last_lora=None,
):
    name = _logical_name(lora_name)
    if float(strength_model) == 0 and float(strength_clip) == 0:
        patched_model, patched_clip = model, clip
    else:
        asset = await _ctx().assets.resolve("loras", name)
        patched_model, patched_clip = await model.apply_lora(
            asset, clip, float(strength_model), float(strength_clip))
    previous = list(last_lora) if isinstance(last_lora, (list, tuple)) else []
    return patched_model, patched_clip, [*previous, name]


async def _lora_selector(lora_name: str, last_lora=None):
    name = _logical_name(lora_name)
    previous = list(last_lora) if isinstance(last_lora, (list, tuple)) else []
    return name, [*previous, name]


NODE_CLASS_MAPPINGS = {
    "SDPromptReader": bind_node(
        "SDPromptReader", _reader, permissions=("assets", "raw")),
    "SDPromptSaver": bind_node(
        "SDPromptSaver", _saver, permissions=("assets", "output")),
    "SDParameterGenerator": bind_node(
        "SDParameterGenerator", _parameter_generator,
        permissions=("models",)),
    "SDPromptMerger": bind_node("SDPromptMerger", _prompt_merger),
    "SDTypeConverter": bind_node("SDTypeConverter", _type_converter),
    "SDAnyConverter": bind_node(
        "SDAnyConverter", _any_converter, accept_all_inputs=True),
    "SDBatchLoader": bind_node(
        "SDBatchLoader", _batch_loader, permissions=("assets",)),
    "SDParameterExtractor": bind_node(
        "SDParameterExtractor", _parameter_extractor),
    "SDLoraLoader": bind_node(
        "SDLoraLoader", _lora_loader, permissions=("assets",)),
    "SDLoraSelector": bind_node("SDLoraSelector", _lora_selector),
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SDPromptReader": "SD Prompt Reader",
    "SDPromptSaver": "SD Prompt Saver",
    "SDParameterGenerator": "SD Parameter Generator",
    "SDPromptMerger": "SD Prompt Merger",
    "SDTypeConverter": "SD Type Converter",
    "SDAnyConverter": "SD Any Converter",
    "SDBatchLoader": "SD Batch Loader",
    "SDParameterExtractor": "SD Parameter Extractor",
    "SDLoraLoader": "SD Lora Loader",
    "SDLoraSelector": "SD Lora Selector",
}


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "SCHEMAS"]
