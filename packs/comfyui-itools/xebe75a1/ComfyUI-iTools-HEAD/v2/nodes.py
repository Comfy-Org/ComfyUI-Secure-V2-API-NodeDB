"""Secure V2 implementations for the pinned ComfyUI-iTools node surface.

The text, image, crop, paint, grid, and styling algorithms remain pack code.
Host authority is limited to typed refs plus the asset, output, model, sample,
and preview brokers.
"""
from __future__ import annotations

import base64
import hashlib
import io as bytes_io
import json
import math
import random
import re
import time
from typing import Any

import numpy as np
import torch
import yaml
from PIL import Image, ImageColor, ImageDraw, ImageEnhance, ImageFont, ImageOps, ImageSequence

from comfy_api.latest import io, sdk

from ._secure_runtime import SCHEMAS, bind_node
from .backend.checker_board import ChessPattern, ChessTensor


_MAX_TEXT = 1_048_576
_MAX_DATA_URL = 24 * 1024 * 1024
_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")
_ASSET_FOLDERS = {"input", "output", "temp"}
_STYLE_FOLDERS = ("itools_styles", "itools_more_styles")
_BACKGROUND_WEIGHT = sdk.HuggingFaceWeight(
    repo_id="briaai/RMBG-2.0",
    filename="model.safetensors",
    folder="background_removal",
    revision="5df4c9c76d8170882c34f6986e848ee07fd0ba43",
    sha256="566ed80c3d95f87ada6864d4cbe2290a1c5eb1c7bb0b123e984f60f76b02c3a7",
    on_demand=True,
)


def _ctx():
    return sdk.ctx()


def _bounded_text(value: Any, label: str = "text") -> str:
    result = str(value or "")
    if len(result.encode("utf-8")) > _MAX_TEXT:
        raise ValueError(f"{label} exceeds 1 MiB")
    return result


def _safe_name(value: Any, *, suffix: str | None = None) -> str:
    name = str(value or "").replace("\\", "/").strip().lstrip("/")
    if not name or name.startswith("../") or "/../" in f"/{name}/":
        raise ValueError("asset name must be a confined logical name")
    if ":" in name.split("/", 1)[0]:
        raise ValueError("host paths are not accepted; use a managed asset name")
    if suffix is not None and not name.lower().endswith(suffix.lower()):
        raise ValueError(f"asset must end in {suffix}")
    return name


def _folder_selector(value: Any, *, default: str = "input") -> tuple[str, str]:
    text = str(value or default).replace("\\", "/").strip().strip('"')
    if text in _ASSET_FOLDERS:
        return text, ""
    first, separator, rest = text.partition("/")
    if first in _ASSET_FOLDERS:
        return first, _safe_name(rest) if rest else ""
    if text.startswith(("/", "~")) or ":" in first:
        raise PermissionError(
            "iTools V2 confines directory access to input/, output/, or temp/"
        )
    return default, _safe_name(text) if text else ""


def _file_selector(value: Any, *, default_folder: str = "input") -> tuple[str, str]:
    folder, name = _folder_selector(value, default=default_folder)
    if not name:
        raise ValueError("a logical filename is required")
    return folder, name


def _pil_to_tensor(image: Image.Image) -> torch.Tensor:
    array = np.asarray(image, dtype=np.float32) / 255.0
    if array.ndim == 2:
        array = array[..., None]
    return torch.from_numpy(np.array(array, copy=True)).unsqueeze(0)


def _pil_to_mask(image: Image.Image) -> torch.Tensor:
    array = np.asarray(image, dtype=np.float32) / 255.0
    return torch.from_numpy(np.array(array, copy=True)).unsqueeze(0)


def _tensor_to_pils(value: torch.Tensor) -> list[Image.Image]:
    tensor = torch.as_tensor(value).detach().cpu().float()
    if tensor.ndim == 3:
        tensor = tensor.unsqueeze(0)
    if tensor.ndim != 4 or tensor.shape[0] < 1 or tensor.shape[-1] < 1:
        raise ValueError("image must be a non-empty BHWC tensor")
    result = []
    for frame in tensor:
        array = (frame.clamp(0, 1).numpy() * 255.0).round().astype(np.uint8)
        if array.shape[-1] == 1:
            array = array[..., 0]
        elif array.shape[-1] > 4:
            array = array[..., :4]
        result.append(Image.fromarray(array))
    return result


def _decode_data_url(value: Any) -> Image.Image:
    text = str(value or "")
    if len(text) > _MAX_DATA_URL:
        raise ValueError("embedded image exceeds 24 MiB")
    encoded = text.split(",", 1)[1] if "," in text else text
    try:
        data = base64.b64decode(encoded, validate=True)
    except Exception as error:
        raise ValueError("invalid embedded image data") from error
    if len(data) > 16 * 1024 * 1024:
        raise ValueError("decoded image exceeds 16 MiB")
    with Image.open(bytes_io.BytesIO(data)) as image:
        image.load()
        return image.copy()


async def _asset_bytes(folder: str, name: str) -> bytes:
    ref = await _ctx().assets.resolve(folder, _safe_name(name))
    size = await _ctx().assets.size(ref)
    if size > 64 * 1024 * 1024:
        raise ValueError("asset exceeds 64 MiB")
    return await _ctx().assets.read_bytes(ref)


def _json_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def _extract_prompt(info: dict[str, Any]) -> str:
    workflow = _json_value(info.get("workflow", {}))
    if not isinstance(workflow, dict):
        prompt = _json_value(info.get("prompt", {}))
        workflow = prompt if isinstance(prompt, dict) else {}
    nodes = workflow.get("nodes", [])
    if not isinstance(nodes, list) or len(nodes) > 4096:
        return "This image does not have an assigned workflow"
    fields: list[str] = []
    positions = {
        "easy positive": (0,),
        "easy showAnything": (0,),
        "iToolsPromptStyler": (0,),
        "iToolsPromptStylerExtra": (0,),
        "CLIPTextEncode": (0,),
        "CLIPTextEncodeSDXL": (6,),
        "ShowText|pysssss": (0,),
        "SDXLPromptStyler": (0, 1),
        "Eff. Loader SDXL": (7,),
    }
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_type = str(node.get("type", ""))
        widgets = node.get("widgets_values", [])
        if node_type not in positions or not isinstance(widgets, list):
            continue
        for index in positions[node_type]:
            if index < len(widgets) and widgets[index] not in ("", None):
                fields.append(f"{len(fields) + 1}_{node_type}: {widgets[index]}")
    return "\n".join(fields) if fields else "This image does not have an assigned workflow"


def _frames_and_masks(data: bytes) -> tuple[torch.Tensor, torch.Tensor, str]:
    with Image.open(bytes_io.BytesIO(data)) as source:
        source.load() if getattr(source, "n_frames", 1) == 1 else None
        prompt = _extract_prompt(dict(source.info))
        images: list[torch.Tensor] = []
        masks: list[torch.Tensor] = []
        expected: tuple[int, int] | None = None
        excluded = source.format == "MPO"
        for frame in ImageSequence.Iterator(source):
            frame = ImageOps.exif_transpose(frame)
            rgb = frame.convert("RGB")
            if expected is None:
                expected = rgb.size
            if rgb.size != expected:
                continue
            images.append(_pil_to_tensor(rgb))
            if "A" in frame.getbands():
                alpha = frame.getchannel("A")
                masks.append(1.0 - _pil_to_mask(alpha))
            else:
                masks.append(torch.zeros((1, rgb.height, rgb.width), dtype=torch.float32))
            if excluded:
                break
    if not images:
        raise ValueError("image asset contains no compatible frames")
    return torch.cat(images), torch.cat(masks), prompt


async def _load_image_plus(image, **_kwargs):
    name = _safe_name(image)
    data = await _asset_bytes("input", name)
    images, masks, prompt = _frames_and_masks(data)
    return images, masks, prompt, name.rsplit("/", 1)[-1].rsplit(".", 1)[0]


async def _load_image_fingerprint(image, **_kwargs):
    ref = await _ctx().assets.resolve("input", _safe_name(image))
    return await _ctx().assets.digest(ref)


async def _validate_input_image(image, **_kwargs):
    try:
        return await _ctx().assets.exists("input", _safe_name(image)) or "Invalid input image"
    except (TypeError, ValueError):
        return "Invalid input image"


_load_image_plus.fingerprint_inputs = _load_image_fingerprint
_load_image_plus.validate_inputs = _validate_input_image


async def _prompt_source(file_path: Any) -> tuple[str, str]:
    text = str(file_path or "prompts.txt").strip().strip('"')
    if text == "prompts.txt":
        if await _ctx().assets.exists("output", "itools/prompts.txt"):
            return "output", "itools/prompts.txt"
        return "itools_examples", "prompts.txt"
    folder, name = _file_selector(text)
    return folder, name


async def _prompt_loader(file_path, seed, fallback="Yes", **_kwargs):
    folder, name = await _prompt_source(file_path)
    data = await _asset_bytes(folder, name)
    lines = [line.strip() for line in data.decode("utf-8").splitlines() if line.strip()]
    count = len(lines)
    if count == 0:
        return "", 0
    index = int(seed)
    if not 0 <= index < count:
        if fallback == "Yes":
            index %= count
        else:
            return "", count
    return lines[index].replace('\\"', '"').replace("\\'", "'"), count


async def _prompt_loader_fingerprint(file_path, **_kwargs):
    folder, name = await _prompt_source(file_path)
    ref = await _ctx().assets.resolve(folder, name)
    return await _ctx().assets.digest(ref)


_prompt_loader.fingerprint_inputs = _prompt_loader_fingerprint


async def _prompt_saver(prompt, file_path="prompts.txt", **_kwargs):
    text = _bounded_text(prompt, "prompt")
    if not text:
        return ()
    target = str(file_path or "prompts.txt").strip().strip('"')
    if target == "prompts.txt":
        folder, name = "output", "itools/prompts.txt"
    else:
        folder, name = _file_selector(target, default_folder="output")
        if folder == "input":
            raise PermissionError("prompt files may be appended only under output/ or temp/")
    await _ctx().output.write_text(
        text, filename=name, folder=folder, mode="append", insert_newline=True
    )
    return ()


def _clean_text(text: Any) -> str:
    value = re.sub(r",+", ",", str(text or ""))
    value = re.sub(r"\s+,", ",", value)
    value = re.sub(r",(\S)", r", \1", value)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\.,|,\.", ".", value)
    return value.strip().replace(" .", ".")


async def _style_data(file_name: Any) -> list[dict[str, str]]:
    name = _safe_name(file_name, suffix=".yaml")
    data = None
    for folder in _STYLE_FOLDERS:
        if await _ctx().assets.exists(folder, name):
            data = await _asset_bytes(folder, name)
            break
    if data is None:
        raise FileNotFoundError(f"unknown iTools style file {name!r}")
    parsed = yaml.safe_load(data.decode("utf-8"))
    if not isinstance(parsed, list) or len(parsed) > 10_000:
        raise ValueError("style file must contain a bounded YAML list")
    result = []
    for item in parsed:
        if not isinstance(item, dict) or "name" not in item:
            continue
        entry = {
            "name": _bounded_text(item.get("name", ""), "style name"),
            "prompt": _bounded_text(item.get("prompt", ""), "style prompt"),
            "negative_prompt": _bounded_text(
                item.get("negative_prompt", ""), "negative style prompt"
            ),
        }
        result.append(entry)
    return result


def _choose_template(data: list[dict[str, str]], name: str) -> dict[str, str]:
    requested = str(name)
    if requested == "random":
        candidates = [x for x in data if x["name"] not in {"none", "random"}]
        if not candidates:
            raise ValueError("style file has no selectable templates")
        return random.choice(candidates)
    for item in data:
        if item["name"] == requested:
            return item
    if requested == "none":
        return {"name": "none", "prompt": "", "negative_prompt": ""}
    raise ValueError(f"No template found with name {requested!r}")


async def _prompt_styler(
    text_positive, text_negative, style_file, template_name, **_kwargs
):
    positive = _bounded_text(text_positive, "positive prompt")
    negative = _bounded_text(text_negative, "negative prompt")
    file_name = _safe_name(style_file, suffix=".yaml")
    selected = _choose_template(await _style_data(file_name), str(template_name))
    if selected["name"] == "none":
        return _clean_text(positive), _clean_text(negative), f"({file_name[:-5]}:none)"
    style_prompt = selected["prompt"]
    positive = (
        style_prompt.replace("{prompt}", positive)
        if "{prompt}" in style_prompt
        else f"{positive}, {style_prompt}"
    )
    style_negative = selected["negative_prompt"]
    if style_negative:
        negative = f"{style_negative}, {negative}" if negative else style_negative
    return (
        _clean_text(positive),
        _clean_text(negative),
        f"({file_name[:-5]}:{selected['name']})",
    )


def _styler_fingerprint(template_name=None, **_kwargs):
    return float("nan") if template_name == "random" else False


_prompt_styler.fingerprint_inputs = _styler_fingerprint


async def _template_parts(file_name: str, template_name: str):
    file_name = _safe_name(file_name, suffix=".yaml")
    selected = _choose_template(await _style_data(file_name), str(template_name))
    return selected["prompt"], selected["negative_prompt"], selected["name"], file_name


async def _prompt_styler_extra(
    text_positive,
    text_negative,
    base_file,
    base_style,
    second_file,
    second_style,
    third_file,
    third_style,
    fourth_file,
    fourth_style,
    **_kwargs,
):
    positive = _bounded_text(text_positive, "positive prompt")
    negative = _bounded_text(text_negative, "negative prompt")
    base = await _template_parts(base_file, base_style)
    extras = [
        await _template_parts(second_file, second_style),
        await _template_parts(third_file, third_style),
        await _template_parts(fourth_file, fourth_style),
    ]
    base_prompt, base_negative, _, _ = base
    if "{prompt}" in base_prompt:
        base_prompt = base_prompt.replace("{prompt}", positive)
    elif base_prompt:
        base_prompt = f"{positive}. {base_prompt}"
    else:
        base_prompt = positive
    extra_prompts = [p.replace("of {prompt}", "").replace("{prompt}", "") for p, *_ in extras]
    total_positive = ",".join([base_prompt, *extra_prompts])
    negatives = [base_negative, *(item[1] for item in extras)]
    total_negative = ",".join([negative, *negatives]) if base_negative else ",".join([negative, *negatives[1:]])

    def used(item):
        _, _, template, file_name = item
        return "" if template == "none" else f"({file_name[:-5]}:{template})"

    return _clean_text(total_positive), _clean_text(total_negative), used(base) + "".join(map(used, extras))


def _extra_fingerprint(**kwargs):
    names = ("base_style", "second_style", "third_style", "fourth_style")
    return float("nan") if any(kwargs.get(name) == "random" for name in names) else False


_prompt_styler_extra.fingerprint_inputs = _extra_fingerprint


async def _font() -> bytes:
    return await _asset_bytes("itools_resources", "Inconsolata.otf")


async def _add_overlay(image, text, font_size, background_color, overlay_mode, **_kwargs):
    frames = _tensor_to_pils(await image.raw())
    size = max(10, min(int(font_size), 1000))
    font = ImageFont.truetype(bytes_io.BytesIO(await _font()), size)
    try:
        color = ImageColor.getcolor(str(background_color), "RGBA")
    except ValueError:
        color = ImageColor.getcolor("#000000AA", "RGBA")
    outputs = []
    for source in frames:
        source = source.convert("RGBA")
        measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        lines: list[str] = []
        line: list[str] = []
        for word in _bounded_text(text).split():
            candidate = " ".join([*line, word])
            if line and measure.textbbox((0, 0), candidate, font=font)[2] > source.width:
                lines.append(" ".join(line))
                line = [word]
            else:
                line.append(word)
        if line or not lines:
            lines.append(" ".join(line))
        heights = [max(1, measure.textbbox((0, 0), value or " ", font=font)[3]) for value in lines]
        bar_height = sum(heights) + 5
        canvas_height = source.height if bool(overlay_mode) else source.height + bar_height
        canvas = Image.new("RGBA", (source.width, canvas_height))
        canvas.alpha_composite(source, (0, 0))
        y0 = source.height - bar_height if bool(overlay_mode) else source.height
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((0, y0, source.width, y0 + bar_height), fill=color)
        y = y0
        for value, height in zip(lines, heights, strict=True):
            draw.text((0, y), value, font=font, fill=(255, 255, 255, 255))
            y += height
        outputs.append(_pil_to_tensor(canvas.convert("RGB")))
    return (torch.cat(outputs),)


async def _directory_images(directory: Any) -> list[tuple[str, bytes]]:
    folder, prefix = _folder_selector(directory, default="output")
    names = await _ctx().assets.list(folder, prefix=prefix, recursive=False)
    selected = sorted(name for name in names if name.lower().endswith(_IMAGE_SUFFIXES))
    return [(name, await _asset_bytes(folder, name)) for name in selected]


async def _load_images(images_directory, start_index, load_limit, output_mode="list", **_kwargs):
    records = await _directory_images(images_directory)
    start = max(0, int(start_index))
    limit = max(0, min(int(load_limit), 200))
    selected = records[start : start + limit]
    images = []
    names = []
    for name, data in selected:
        frames, _, _ = _frames_and_masks(data)
        images.append(frames)
        names.append(name.rsplit("/", 1)[-1].rsplit(".", 1)[0])
    if str(output_mode) == "batch" and images:
        shape = tuple(images[0].shape[1:])
        if any(tuple(value.shape[1:]) != shape for value in images):
            raise ValueError("batch mode requires all loaded images to have equal dimensions")
        images = [torch.cat(images)]
    return images, names, len(images) if str(output_mode) == "list" else len(selected)


async def _grid_filler(images, width, height, rows, cols, gaps, background_color, fill_direction, **_kwargs):
    def first(value):
        return value[0] if isinstance(value, (list, tuple)) and value else value

    image_refs = images if isinstance(images, (list, tuple)) else [images]
    sources: list[Image.Image] = []
    for ref in image_refs:
        if ref is None:
            continue
        sources.extend(_tensor_to_pils(await ref.raw()))
    if not sources:
        raise ValueError("Grid Filler needs at least one image")
    canvas_width = max(1, min(int(first(width)), 8192))
    canvas_height = max(1, min(int(first(height)), 8192))
    row_count = max(1, min(int(first(rows)), 10))
    col_count = max(1, min(int(first(cols)), 10))
    gap = max(0.0, min(float(first(gaps)), 50.0)) / 100.0
    direction = str(first(fill_direction) or "rows")
    try:
        color = ImageColor.getrgb(str(first(background_color)))
    except ValueError:
        color = (0, 0, 0)
    canvas = Image.new("RGB", (canvas_width, canvas_height), color)
    cell_width = canvas_width / col_count
    cell_height = canvas_height / row_count
    capacity = row_count * col_count
    sequence = [sources[0]] * capacity if len(sources) == 1 else sources[:capacity]
    for index, source in enumerate(sequence):
        if direction == "cols":
            col, row = divmod(index, row_count)
        else:
            row, col = divmod(index, col_count)
        if row >= row_count or col >= col_count:
            break
        available_w = max(1, int(cell_width * (1.0 - gap)))
        available_h = max(1, int(cell_height * (1.0 - gap)))
        image = source.convert("RGB").copy()
        image.thumbnail((available_w, available_h), Image.Resampling.LANCZOS)
        x = int(col * cell_width + (cell_width - image.width) / 2)
        y = int(row * cell_height + (cell_height - image.height) / 2)
        canvas.paste(image, (x, y))
    return (_pil_to_tensor(canvas),)


def _line_loader(lines, seed, fallback="Yes", **_kwargs):
    values = _bounded_text(lines, "lines").splitlines()
    count = len(values)
    index = int(seed)
    if 0 <= index < count:
        value = values[index]
    elif fallback == "Yes" and count:
        value = values[index % count]
    else:
        value = ""
    return value, count


def _text_replacer(text_in, match, replace, **_kwargs):
    return (_bounded_text(text_in).replace(_bounded_text(match), _bounded_text(replace)),)


def _regex_node(text_in, regex_pattern, pattern_picker, replace_match, replace_non_match, **_kwargs):
    text = _bounded_text(text_in)
    pattern = _bounded_text(regex_pattern, "regex pattern")
    if len(pattern) > 4096:
        raise ValueError("regex pattern exceeds 4096 characters")
    replace_match = _bounded_text(replace_match)
    replace_non_match = _bounded_text(replace_non_match)
    compiled = re.compile(pattern)
    if not replace_match and not replace_non_match:
        matches = compiled.findall(text)
        result = "".join("".join(item) if isinstance(item, tuple) else item for item in matches)
    elif replace_match and not replace_non_match:
        result = compiled.sub(replace_match, text)
    else:
        parts = []
        last_end = 0
        for match in compiled.finditer(text):
            start, end = match.span()
            if last_end < start or not replace_match:
                parts.append(replace_non_match)
            parts.append(replace_match if replace_match else text[start:end])
            last_end = end
        if last_end < len(text) or (not replace_match and not list(compiled.finditer(text))):
            parts.append(replace_non_match)
        result = "".join(parts)
    return (result.strip(),)


async def _ksampler(
    model, seed, steps, cfg, sampler_name, scheduler, positive, negative, latent_image, denoise=1.0, **_kwargs
):
    started = time.monotonic()
    output = await _ctx().sample(
        latent=latent_image,
        steps=int(steps),
        model=model,
        positive=positive,
        negative=negative,
        cfg=float(cfg),
        seed=int(seed),
        sampler_name=str(sampler_name),
        scheduler=str(scheduler),
        denoise=float(denoise),
    )
    elapsed = time.monotonic() - started
    info = (
        f"time:{elapsed:.3f}s seed:{int(seed)} steps:{int(steps)} "
        f"cfg:{float(cfg):g} sampler:{sampler_name} scheduler:{scheduler} "
    )
    return output, info


async def _vae_preview(samples, vae, **_kwargs):
    images = await vae.decode(samples)
    ui_result = await _ctx().ui.preview_images(images)
    return {"ui": ui_result, "result": (images,)}


def _checkerboard(width, height, rows, cols, pattern, is_colored, seed, **_kwargs):
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(int(seed))
        generated = ChessTensor(
            width=int(width),
            height=int(height),
            rows=int(rows),
            cols=int(cols),
            pattern=ChessPattern.from_string(str(pattern)),
            colored=bool(is_colored),
        )
    image = _pil_to_tensor(generated.pil_img.convert("RGB"))
    return image, image[..., 0]


async def _load_random_image(images_directory, seed, **_kwargs):
    records = await _directory_images(images_directory)
    if not records:
        raise ValueError("No valid images found in the managed directory")
    name, data = records[int(seed) % len(records)]
    images, _, _ = _frames_and_masks(data)
    return images, name.rsplit("/", 1)[-1].rsplit(".", 1)[0]


def _preview_text(text, **_kwargs):
    values = text if isinstance(text, list) else [text]
    clean = [_bounded_text(value) for value in values]
    return {"ui": {"text": clean}, "result": (clean,)}


async def _preview_image(images, **_kwargs):
    ui_result = await _ctx().ui.preview_images(images)
    return {"ui": ui_result, "result": (images,)}


async def _compare_image(A, B, **_kwargs):
    left = await _ctx().ui.preview_images(A)
    right = await _ctx().ui.preview_images(B)
    combined = dict(left)
    combined["images"] = [*left.get("images", []), *right.get("images", [])]
    return {"ui": combined, "result": (A,)}


def _prompt_record(text, timeline_data="", **_kwargs):
    value = _bounded_text(text)
    return {"ui": {"text": [value]}, "result": (value,)}


def _dynamic_value(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except ValueError:
            return {}
    return {}


def _instructor(**kwargs):
    data = _dynamic_value(kwargs.get("InstructorWidget"))
    return (_bounded_text(data.get("finalText", ""), "instruction"),)


async def _prompt_builder(**kwargs):
    data = _dynamic_value(kwargs.get("PromptBuilderWidget"))
    prompt = _bounded_text(data.get("prompt", ""), "prompt")
    negative = _bounded_text(data.get("negative", ""), "negative prompt")
    category = data.get("category")
    style = str(data.get("style", "none"))
    if style != "none" and category:
        positive, negative, _ = await _prompt_styler(prompt, negative, category, style)
        return {
            "ui": {"prompt": [positive], "negative": [negative], "style": ["none"]},
            "result": (positive, negative),
        }
    return {"ui": {"prompt": [prompt], "negative": [negative]}, "result": (prompt, negative)}


def _prompt_builder_fingerprint(**kwargs):
    data = _dynamic_value(kwargs.get("PromptBuilderWidget"))
    return float("nan") if data.get("style") == "random" else False


_prompt_builder.fingerprint_inputs = _prompt_builder_fingerprint


def _adjust_pil(image: Image.Image, state: dict[str, Any]) -> Image.Image:
    result = image.convert("RGB")
    brightness = float(state.get("brightness", 0)) / 100.0
    contrast = float(state.get("contrast", 100)) / 100.0
    saturation = float(state.get("saturation", 100)) / 100.0
    temperature = float(state.get("temperature", 0))
    gamma = max(float(state.get("gamma", 100)) / 100.0, 0.01)
    sharpness = float(state.get("sharpness", 100)) / 100.0
    hue = float(state.get("hue", 0))
    values = (brightness, contrast, saturation, temperature, gamma, sharpness, hue)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("image adjustment values must be finite")
    result = ImageEnhance.Brightness(result).enhance(max(0.0, 1.0 + brightness))
    result = ImageEnhance.Contrast(result).enhance(max(0.0, contrast))
    result = ImageEnhance.Color(result).enhance(max(0.0, saturation))
    if temperature:
        array = np.asarray(result, dtype=np.float32).copy()
        strength = max(-100.0, min(temperature, 100.0)) / 100.0
        array[..., 0] = np.clip(array[..., 0] * (1.0 + strength * 0.3), 0, 255)
        array[..., 2] = np.clip(array[..., 2] * (1.0 - strength * 0.3), 0, 255)
        result = Image.fromarray(array.astype(np.uint8))
    if gamma != 1.0:
        array = np.asarray(result, dtype=np.float32) / 255.0
        result = Image.fromarray((np.power(np.clip(array, 0, 1), 1.0 / gamma) * 255).astype(np.uint8))
    result = ImageEnhance.Sharpness(result).enhance(max(0.0, sharpness))
    if hue:
        hsv = np.asarray(result.convert("HSV"), dtype=np.uint8).copy()
        hsv[..., 0] = (hsv[..., 0].astype(np.int32) + round(hue / 360.0 * 255)) % 256
        result = Image.fromarray(hsv, "HSV").convert("RGB")
    return result


async def _image_adjust(image=None, widget_state="{}", **_kwargs):
    state = _dynamic_value(widget_state)
    sources: list[Image.Image]
    if image is not None:
        sources = _tensor_to_pils(await image.raw())
    else:
        embedded = state.get("processedImageData") or state.get("imageData")
        if embedded:
            sources = [_decode_data_url(embedded)]
        elif state.get("imagePath"):
            data = await _asset_bytes("input", _safe_name(state["imagePath"]))
            with Image.open(bytes_io.BytesIO(data)) as source:
                source.load()
                sources = [source.copy()]
        else:
            sources = [Image.new("RGB", (512, 512), (64, 64, 64))]
    return (torch.cat([_pil_to_tensor(_adjust_pil(source, state)) for source in sources]),)


async def _paint_node(**kwargs):
    state = _dynamic_value(kwargs.get("PaintWidget"))
    data_url = state.get("dataUrl") or state.get("data") or state.get("imageData")
    image = _decode_data_url(data_url).convert("RGBA") if data_url else Image.new("RGBA", (512, 512), "white")
    image_ref = await sdk.ImageRef._from_raw(_pil_to_tensor(image.convert("RGB")))
    if bool(state.get("removeBackground")):
        logical = await _ctx().models.download_huggingface_weights(
            _BACKGROUND_WEIGHT.repo_id,
            _BACKGROUND_WEIGHT.filename,
            _BACKGROUND_WEIGHT.folder,
            revision=_BACKGROUND_WEIGHT.revision,
            sha256=_BACKGROUND_WEIGHT.sha256,
        )
        remover = await _ctx().models.load_background_removal_model(logical)
        alpha_ref = await remover.mask(image_ref)
        pixels = torch.as_tensor(await image_ref.raw()).detach().cpu().float()[..., :3]
        alpha = torch.as_tensor(await alpha_ref.raw()).detach().cpu().float().clamp(0, 1)
        image_ref = await sdk.ImageRef._from_raw(torch.cat((pixels, alpha.unsqueeze(-1)), dim=-1))
    return (image_ref,)


async def _crop_image(image, resize_rule="grid", grid_step=64, **kwargs):
    crop = _dynamic_value(kwargs.get("crop"))
    embedded = crop.get("data") or crop.get("dataUrl") or crop.get("imageData")
    if embedded:
        output = _decode_data_url(embedded).convert("RGB")
    else:
        data = await _asset_bytes("input", _safe_name(image))
        with Image.open(bytes_io.BytesIO(data)) as source:
            source = ImageOps.exif_transpose(source).convert("RGB")
            box = crop.get("box")
            if isinstance(box, (list, tuple)) and len(box) == 4:
                left, top, right, bottom = map(int, box)
                left, top = max(0, left), max(0, top)
                right, bottom = min(source.width, right), min(source.height, bottom)
                if right <= left or bottom <= top:
                    raise ValueError("crop box is empty")
                output = source.crop((left, top, right, bottom))
            else:
                output = source.copy()
    return (_pil_to_tensor(output),)


async def _crop_fingerprint(image, crop=None, **_kwargs):
    dynamic = _dynamic_value(crop)
    embedded = dynamic.get("data") or dynamic.get("dataUrl") or dynamic.get("imageData")
    if embedded:
        return hashlib.sha256(str(embedded).encode("utf-8")).hexdigest()
    ref = await _ctx().assets.resolve("input", _safe_name(image))
    return await _ctx().assets.digest(ref)


async def _validate_crop(image, crop=None, **_kwargs):
    dynamic = _dynamic_value(crop)
    if dynamic.get("data") or dynamic.get("dataUrl") or dynamic.get("imageData"):
        return True
    return await _validate_input_image(image)


_crop_image.fingerprint_inputs = _crop_fingerprint
_crop_image.validate_inputs = _validate_crop


def _test_node(**kwargs):
    value = kwargs.get("Click", 0)
    if isinstance(value, dict):
        value = value.get("count", 0)
    count = int(value or 0)
    return str(count), count


def _dom_node(**kwargs):
    data = _dynamic_value(kwargs.get("CounterWidget"))
    return (f"{data.get('text', '')} {data.get('count', 0)}".strip(),)


_HANDLERS = {
    "iToolsLoadImagePlus": (_load_image_plus, ("assets", "raw")),
    "iToolsPromptLoader": (_prompt_loader, ("assets",)),
    "iToolsPromptSaver": (_prompt_saver, ("output",)),
    "iToolsPromptStyler": (_prompt_styler, ("assets",)),
    "iToolsAddOverlay": (_add_overlay, ("assets", "raw")),
    "iToolsLoadImages": (_load_images, ("assets", "raw")),
    "iToolsPromptStylerExtra": (_prompt_styler_extra, ("assets",)),
    "iToolsGridFiller": (_grid_filler, ("raw",)),
    "iToolsLineLoader": (_line_loader, ()),
    "iToolsTextReplacer": (_text_replacer, ()),
    "iToolsRegexNode": (_regex_node, ()),
    "iToolsKSampler": (_ksampler, ("sample",)),
    "iToolsVaePreview": (_vae_preview, ("ui",)),
    "iToolsCheckerBoard": (_checkerboard, ("raw",)),
    "iToolsLoadRandomImage": (_load_random_image, ("assets", "raw")),
    "iToolsPreviewText": (_preview_text, ()),
    "iToolsPreviewImage": (_preview_image, ("ui",)),
    "iToolsCompareImage": (_compare_image, ("ui",)),
    "iToolsPromptRecord": (_prompt_record, ()),
    "iToolsInstructorNode": (_instructor, ()),
    "iToolsPromptBuilder": (_prompt_builder, ("assets",)),
    "iToolsImageAdjust": (_image_adjust, ("assets", "raw")),
    "iToolsPaintNode": (_paint_node, ("models", "models.download", "raw")),
    "iToolsCropImage": (_crop_image, ("assets", "raw")),
    "iToolsTestNode": (_test_node, ()),
    "iToolsDomNode": (_dom_node, ()),
}

if set(_HANDLERS) != set(SCHEMAS):
    raise RuntimeError(
        f"iTools handler census mismatch: missing={set(SCHEMAS) - set(_HANDLERS)}, "
        f"extra={set(_HANDLERS) - set(SCHEMAS)}"
    )

NODE_CLASS_MAPPINGS = {
    node_id: bind_node(
        node_id,
        handler,
        permissions=permissions,
        required_weights=(_BACKGROUND_WEIGHT,) if node_id == "iToolsPaintNode" else (),
    )
    for node_id, (handler, permissions) in _HANDLERS.items()
}
NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: definition["schema"]["attrs"]["display_name"]
    for node_id, definition in SCHEMAS.items()
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
