"""Secure V2 implementations for ControlAltAI's pinned 22-node surface.

Image, mask, preview, and texture algorithms remain pack-owned and run only in
the explicitly permissioned raw-compute realm. Host-owned models, sampling,
conditioning, and ControlNet objects remain opaque refs.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from ._secure_runtime import SCHEMAS, bind_node, sdk


_EMPTY_BBOX = {
    "x1": 0.0,
    "y1": 0.0,
    "x2": 0.0,
    "y2": 0.0,
    "active": False,
}
_UNION_TYPES = {
    "canny": 0,
    "tile": 1,
    "depth": 2,
    "blur": 3,
    "pose": 4,
    "gray": 5,
    "low quality": 6,
}


def _pil_to_tensor(image: Image.Image) -> torch.Tensor:
    value = np.array(image, copy=True).astype(np.float32) / 255.0
    if value.ndim == 2:
        value = value[..., None]
    return torch.from_numpy(value).unsqueeze(0)


def _image_to_pil(value: torch.Tensor) -> Image.Image:
    if value.ndim != 4 or value.shape[0] != 1:
        raise ValueError("this pack's PIL image operations require one BHWC image")
    array = (value[0].detach().cpu().numpy() * 255).astype(np.uint8)
    if array.shape[-1] == 1:
        array = array[..., 0]
    return Image.fromarray(array)


def _mask_2d(value: torch.Tensor, *, name: str = "mask") -> torch.Tensor:
    if value.ndim == 4 and value.shape[0] == 1 and value.shape[-1] == 1:
        value = value[0, ..., 0]
    elif value.ndim == 3 and value.shape[0] == 1:
        value = value[0]
    if value.ndim != 2:
        raise ValueError(f"{name} must be HW or single-batch BHW")
    return value


async def _raw_image(ref: sdk.ImageRef, *, name: str = "image") -> torch.Tensor:
    if not isinstance(ref, sdk.ImageRef) or ref.kind != "IMAGE":
        raise TypeError(f"{name} must be an IMAGE ref")
    value = await ref.raw()
    if not isinstance(value, torch.Tensor) or value.ndim != 4:
        raise ValueError(f"{name} must resolve to a BHWC tensor")
    return value


async def _raw_mask(ref: sdk.TensorRef, *, name: str = "mask") -> torch.Tensor:
    if not isinstance(ref, sdk.TensorRef) or ref.kind not in {"MASK", "IMAGE"}:
        raise TypeError(f"{name} must be a MASK ref")
    return _mask_2d(await ref.raw(), name=name)


def _bbox(value: Any, *, active_required: bool = False) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("bbox must be a mapping")
    required = {"x1", "y1", "x2", "y2", "active"}
    if set(value) != required:
        raise ValueError("bbox must have the exact x1/y1/x2/y2/active shape")
    result = dict(value)
    if type(result["active"]) is not bool:
        raise TypeError("bbox active must be a boolean")
    for key in ("x1", "y1", "x2", "y2"):
        item = result[key]
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise TypeError(f"bbox {key} must be numeric")
        item = float(item)
        if not math.isfinite(item) or not 0.0 <= item <= 1.0:
            raise ValueError(f"bbox {key} must be within [0, 1]")
        result[key] = item
    if result["active"] or active_required:
        if result["x1"] >= result["x2"] or result["y1"] >= result["y2"]:
            raise ValueError("active bbox coordinates must be ordered")
    return result


def _empty_bbox() -> dict[str, Any]:
    return dict(_EMPTY_BBOX)


def _preview_grid(width: int, height: int, footer: str = "") -> torch.Tensor:
    canvas = Image.new("RGB", (1024, 1024), (0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    for x in range(0, 1024, 50):
        draw.line([(x, 0), (x, 1024)], fill="#333333")
    for y in range(0, 1024, 50):
        draw.line([(0, y), (1024, y)], fill="#333333")
    preview_width = 800
    preview_height = int(preview_width * height / width)
    if preview_height > 800:
        preview_height = 800
        preview_width = int(preview_height * width / height)
    left = (1024 - preview_width) // 2
    top = (1024 - preview_height) // 2
    draw.rectangle(
        [(left, top), (left + preview_width, top + preview_height)],
        outline="red",
        width=4,
    )
    font = ImageFont.load_default()
    center_y = top + preview_height // 2
    draw.text((512, center_y), f"{width}x{height}", fill="red", anchor="mm", font=font)
    if footer:
        draw.text((512, center_y + 30), footer, fill="red", anchor="mm", font=font)
    return _pil_to_tensor(canvas)


async def _boolean_basic(boolean):
    return (boolean,)


async def _boolean_reverse(boolean):
    return (not boolean,)


async def _choose_upscale_model(upscale_model_1, upscale_model_2, use_model_1):
    return (upscale_model_1 if use_model_1 else upscale_model_2,)


async def _integer_settings(setting):
    return (2 if setting else 1,)


async def _integer_settings_advanced(setting_1, setting_2, setting_3):
    if setting_3:
        return (3,)
    if setting_2:
        return (2,)
    return (1,)


async def _text_bridge(text_input="", passthrough_text=""):
    return (passthrough_text if passthrough_text and not text_input else text_input,)


async def _two_way_switch(
    selection_setting=1, input_1=None, input_2=None,
):
    if selection_setting == 2:
        return (input_2 if input_2 is not None else input_1,)
    return (input_1 if input_1 is not None else input_2,)


async def _three_way_switch(
    selection_setting=1, input_1=None, input_2=None, input_3=None,
):
    if selection_setting == 2:
        return (input_2 if input_2 is not None else
                input_1 if input_1 is not None else input_3,)
    if selection_setting == 3:
        return (input_3 if input_3 is not None else
                input_1 if input_1 is not None else input_2,)
    return (input_1 if input_1 is not None else
            input_2 if input_2 is not None else input_3,)


_two_way_switch.validate_inputs = lambda **_kwargs: True
_three_way_switch.validate_inputs = lambda **_kwargs: True


async def _get_image_size_ratio(image):
    if not isinstance(image, sdk.ImageRef):
        raise TypeError("image must be an IMAGE ref")
    height, width = await image.spatial_shape()
    divisor = math.gcd(width, height)
    return width, height, f"{width // divisor}:{height // divisor}"


async def _flux_resolution(
    megapixel, aspect_ratio, divisible_by, custom_ratio,
    custom_aspect_ratio=None,
):
    megapixel_value = float(megapixel)
    round_to = int(divisible_by)
    numeric_ratio = (
        custom_aspect_ratio if custom_ratio and custom_aspect_ratio
        else str(aspect_ratio).split(" ", 1)[0]
    )
    parts = str(numeric_ratio).split(":")
    if len(parts) != 2:
        raise ValueError("aspect ratio must be WIDTH:HEIGHT")
    width_ratio, height_ratio = map(int, parts)
    if width_ratio <= 0 or height_ratio <= 0:
        raise ValueError("aspect-ratio components must be positive")
    dimension = (
        megapixel_value * 1_000_000 / (width_ratio * height_ratio)
    ) ** 0.5
    width = round(int(dimension * width_ratio) / round_to) * round_to
    height = round(int(dimension * height_ratio) / round_to) * round_to
    if width <= 0 or height <= 0 or width * height > 67_108_864:
        raise ValueError("calculated preview dimensions are out of bounds")
    resolution = f"{width} x {height}"
    preview = _preview_grid(width, height, str(numeric_ratio))
    return width, height, resolution, preview


_HIDREAM_DIMENSIONS = {
    "1:1 (Perfect Square)": (1024, 1024),
    "3:4 (Standard Portrait)": (880, 1168),
    "2:3 (Classic Portrait)": (832, 1248),
    "9:16 (Widescreen Portrait)": (768, 1360),
    "4:3 (Standard Landscape)": (1168, 880),
    "3:2 (Classic Landscape)": (1248, 832),
    "16:9 (Widescreen Landscape)": (1360, 768),
}


async def _hidream_resolution(resolution):
    width, height = _HIDREAM_DIMENSIONS[resolution]
    text = f"{width} x {height}"
    return width, height, text, _preview_grid(width, height)


async def _noise_plus_blend(
    image, noise_scale=0.05, blend_opacity=15, mask=None,
):
    base = _image_to_pil(await _raw_image(image)).convert("RGB")
    width, height = base.size
    noise_array = np.random.normal(
        128, 128 * float(noise_scale), (height, width, 3)
    ).astype(np.uint8)
    noise = Image.fromarray(noise_array).convert("RGB")
    noise_blended = ImageChops.soft_light(base, noise)
    blended = Image.blend(base, noise_blended, float(blend_opacity) / 100.0)
    if mask is not None:
        mask_value = await _raw_mask(mask)
        mask_image = Image.fromarray(
            (mask_value.detach().cpu().numpy() * 255).astype(np.uint8)
        ).convert("L").resize(base.size)
        blended = Image.composite(
            base, blended, ImageChops.invert(mask_image)
        )
    return _pil_to_tensor(blended), _pil_to_tensor(noise)


def _safe_noise_resize(
    array: np.ndarray, target_height: int, target_width: int,
) -> np.ndarray:
    maximum = array.max()
    if maximum == 0:
        return np.zeros((target_height, target_width), dtype=np.float32)
    image = Image.fromarray((array * 255 / maximum).astype(np.uint8))
    image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
    return np.array(image).astype(np.float32) / 255.0 * maximum


def _texture_noise(
    width: int, height: int, noise_scale: float,
    texture_type: str, frequency: float,
) -> np.ndarray:
    if texture_type == "Film Grain":
        base = [
            np.random.normal(128, 64 * noise_scale, (height, width))
            for _ in range(3)
        ]
        large_h = max(4, int(height / (4 * frequency)))
        large_w = max(4, int(width / (4 * frequency)))
        large = [
            _safe_noise_resize(
                np.random.normal(0, 30 * noise_scale, (large_h, large_w)),
                height,
                width,
            )
            for _ in range(3)
        ]
        combined = [np.clip(a * 0.7 + b * 0.3, 0, 255)
                    for a, b in zip(base, large, strict=True)]
    elif texture_type == "Skin Pore":
        scale = noise_scale * 0.6
        base = [
            np.random.normal(128, spread * scale, (height, width))
            for spread in (32, 28, 24)
        ]
        fine_h = max(4, int(height * frequency * 1.5))
        fine_w = max(4, int(width * frequency * 1.5))
        fine = [
            _safe_noise_resize(
                np.random.normal(0, spread * scale, (fine_h, fine_w)),
                height,
                width,
            )
            for spread in (20, 18, 16)
        ]
        combined = [np.clip(a + b * 0.8, 0, 255)
                    for a, b in zip(base, fine, strict=True)]
    elif texture_type == "Natural":
        combined = [
            np.random.normal(128, spread * noise_scale, (height, width))
            for spread in (48, 44, 40)
        ]
        for layer_frequency, weight in zip(
            (frequency * 2, frequency, frequency / 3),
            (0.5, 0.3, 0.2),
            strict=True,
        ):
            layer_h = max(4, int(height * layer_frequency))
            layer_w = max(4, int(width * layer_frequency))
            for channel, spread in enumerate((30, 28, 26)):
                layer = np.random.normal(
                    0, spread * noise_scale * weight, (layer_h, layer_w)
                )
                combined[channel] += (
                    _safe_noise_resize(layer, height, width) * weight
                )
        combined = [np.clip(item, 0, 255) for item in combined]
    else:
        base = [
            np.random.normal(128, spread * noise_scale, (height, width))
            for spread in (40, 38, 36)
        ]
        fine_h = max(4, int(height * frequency * 2.5))
        fine_w = max(4, int(width * frequency * 2.5))
        fine = [
            _safe_noise_resize(
                np.random.normal(0, spread * noise_scale, (fine_h, fine_w)),
                height,
                width,
            )
            for spread in (25, 23, 21)
        ]
        combined = [np.clip(a + b * 0.7, 0, 255)
                    for a, b in zip(base, fine, strict=True)]
    return np.stack(combined, axis=2)


async def _perturbation_texture(
    image, noise_scale=0.5, texture_strength=50,
    texture_type="Skin Pore", frequency=1.0,
    perturbation_factor=0.15, use_mask=False, mask=None, seed=-1,
):
    base = _image_to_pil(await _raw_image(image)).convert("RGB")
    if int(seed) >= 0:
        np.random.seed(int(seed))
    width, height = base.size
    base_array = np.array(base).astype(np.float32) / 255.0
    noise = _texture_noise(
        width, height, float(noise_scale), str(texture_type), float(frequency)
    )
    normalized = (noise.astype(np.float32) - 128.0) / 128.0
    effective = float(perturbation_factor) * (int(texture_strength) / 100.0)
    result = np.clip(base_array + normalized * effective, 0, 1)
    layer = np.clip(
        base_array + normalized * float(perturbation_factor) * 2.0, 0, 1
    )
    textured = Image.fromarray((result * 255).astype(np.uint8))
    texture_layer = Image.fromarray((layer * 255).astype(np.uint8))
    if use_mask and mask is not None:
        mask_value = await _raw_mask(mask)
        mask_image = Image.fromarray(
            (mask_value.detach().cpu().numpy() * 255).astype(np.uint8)
        ).convert("L").resize(base.size)
        textured = Image.composite(
            base, textured, ImageChops.invert(mask_image)
        )
    return _pil_to_tensor(textured), _pil_to_tensor(texture_layer)


def _mask_from_bbox(bbox: dict[str, Any], width: int, height: int) -> torch.Tensor:
    mask = torch.zeros((height, width), dtype=torch.float32)
    if bbox["active"]:
        x1 = int(bbox["x1"] * width)
        y1 = int(bbox["y1"] * height)
        x2 = int(bbox["x2"] * width)
        y2 = int(bbox["y2"] * height)
        mask[y1:y2, x1:x2] = 1.0
    return mask


def _region_previews(
    masks: list[torch.Tensor], bboxes: list[dict[str, Any]], count: int,
) -> tuple[torch.Tensor, torch.Tensor]:
    height, width = masks[0].shape
    region_array = np.zeros((height, width, 3), dtype=np.uint8)
    bbox_image = Image.new("RGB", (width, height), (0, 0, 0))
    bbox_draw = ImageDraw.Draw(bbox_image)
    colors = [(255, 0, 0), (0, 255, 0), (255, 255, 0)]
    active = []
    for index in range(count):
        if bboxes[index]["active"]:
            mask = masks[index].detach().cpu().numpy() > 0.5
            if mask.any():
                active.append((index, mask, bboxes[index]))
    for index, mask, bbox in sorted(active, reverse=True):
        region_array[mask] = colors[index]
        x1 = int(bbox["x1"] * width)
        y1 = int(bbox["y1"] * height)
        x2 = int(bbox["x2"] * width)
        y2 = int(bbox["y2"] * height)
        bbox_draw.rectangle([x1, y1, x2, y2], outline=colors[index], width=2)
    return (
        _pil_to_tensor(Image.fromarray(region_array)),
        _pil_to_tensor(bbox_image),
    )


async def _region_mask_generator(width, height, number_of_regions, **kwargs):
    width = int(width)
    height = int(height)
    count = int(number_of_regions)
    if (
        width <= 0 or height <= 0 or width * height > 67_108_864
        or not 1 <= count <= 3
    ):
        raise ValueError("region canvas or count is out of bounds")
    bboxes: list[dict[str, Any]] = []
    masks: list[torch.Tensor] = []
    for index in range(3):
        if index >= count:
            bbox = _empty_bbox()
        else:
            bbox = _bbox({
                "x1": kwargs[f"region{index + 1}_x1"],
                "y1": kwargs[f"region{index + 1}_y1"],
                "x2": kwargs[f"region{index + 1}_x2"],
                "y2": kwargs[f"region{index + 1}_y2"],
                "active": True,
            })
        bboxes.append(bbox)
        masks.append(_mask_from_bbox(bbox, width, height))
    region_preview, bbox_preview = _region_previews(masks, bboxes, count)
    return (
        region_preview,
        bbox_preview,
        *masks,
        count,
        *bboxes,
    )


def _gaussian_blur(mask: torch.Tensor, radius: int) -> torch.Tensor:
    if radius <= 0:
        return mask
    kernel_size = 2 * radius + 1
    sigma = radius / 3.0
    value = mask.unsqueeze(0).unsqueeze(0) if mask.ndim == 2 else mask
    kernel = torch.exp(
        torch.linspace(-radius, radius, kernel_size, device=value.device)
        .pow(2)
        .div(-2 * sigma ** 2)
    )
    kernel = kernel / kernel.sum()
    horizontal = kernel.view(1, 1, 1, -1)
    vertical = kernel.view(1, 1, -1, 1)
    value = F.pad(value, (radius, radius, 0, 0), mode="reflect")
    value = F.conv2d(value, horizontal)
    value = F.pad(value, (0, 0, radius, radius), mode="reflect")
    return F.conv2d(value, vertical).squeeze()


def _feather_mask(
    mask: torch.Tensor, bbox: dict[str, Any], radius: int,
) -> torch.Tensor:
    if radius <= 0 or not bbox["active"]:
        return mask
    height, width = mask.shape
    x1 = int(bbox["x1"] * width)
    y1 = int(bbox["y1"] * height)
    x2 = int(bbox["x2"] * width)
    y2 = int(bbox["y2"] * height)
    inner = torch.zeros_like(mask)
    inner[y1 + radius:y2 - radius, x1 + radius:x2 - radius] = 1.0
    edge = mask - inner
    if not edge.any():
        return mask
    blurred = _gaussian_blur(mask, radius)
    result = mask.clone()
    result[edge > 0] = blurred[edge > 0]
    return result


def _processed_preview(
    masks: list[torch.Tensor], bboxes: list[dict[str, Any]], count: int,
) -> torch.Tensor:
    height, width = masks[0].shape
    preview = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    colors = [(255, 0, 0), (0, 255, 0), (255, 255, 0)]
    active = []
    for index in range(count):
        if bboxes[index]["active"]:
            active.append((index, masks[index].detach().cpu().numpy() > 0.5))
    for index, mask in sorted(active, reverse=True):
        color = np.zeros((height, width, 4), dtype=np.uint8)
        color[..., :3] = colors[index]
        color[..., 3] = (mask * 255).astype(np.uint8)
        preview = Image.alpha_composite(preview, Image.fromarray(color, "RGBA"))
    return _pil_to_tensor(preview.convert("RGB"))


async def _region_mask_processor(
    mask1, bbox1, blur_radius, threshold, feather_edges,
    number_of_regions, mask2=None, bbox2=None, mask3=None, bbox3=None,
):
    first = await _raw_mask(mask1, name="mask1")
    pairs = [(mask1, bbox1), (mask2, bbox2), (mask3, bbox3)]
    count = int(number_of_regions)
    radius = int(blur_radius)
    if not 1 <= count <= 3 or not 0 <= radius <= 32:
        raise ValueError("region count or blur radius is out of bounds")
    masks: list[torch.Tensor] = []
    bboxes: list[dict[str, Any]] = []
    active_count = 0
    for index, (mask_ref, bbox_value) in enumerate(pairs):
        if index >= count or mask_ref is None or bbox_value is None:
            masks.append(torch.zeros_like(first))
            bboxes.append(_empty_bbox())
            continue
        mask = first if index == 0 else await _raw_mask(
            mask_ref, name=f"mask{index + 1}"
        )
        if mask.shape != first.shape:
            raise ValueError("all region masks must have the same shape")
        bbox = _bbox(bbox_value)
        processed = (mask > float(threshold)).float()
        if bbox["active"] and radius > 0:
            try:
                processed = (
                    _feather_mask(processed, bbox, radius)
                    if feather_edges else _gaussian_blur(processed, radius)
                )
            except (RuntimeError, ValueError):
                # The pinned node leaves undersized masks unchanged when its
                # reflect-padding kernel cannot fit.
                pass
        if bbox["active"]:
            active_count += 1
        masks.append(processed)
        bboxes.append(bbox)
    preview = _processed_preview(masks, bboxes, count)
    return (
        masks[0], bboxes[0], masks[1], bboxes[1], masks[2], bboxes[2],
        preview, active_count,
    )


def _region_dimensions(
    bbox: dict[str, Any], width: int, height: int,
) -> tuple[int, int]:
    if not bbox["active"]:
        return 0, 0
    return (
        int(bbox["x2"] * width) - int(bbox["x1"] * width),
        int(bbox["y2"] * height) - int(bbox["y1"] * height),
    )


def _bbox_overlap(
    first: dict[str, Any], second: dict[str, Any],
    width: int, height: int,
) -> tuple[tuple[int, int], float]:
    if not first["active"] or not second["active"]:
        return (0, 0), 0.0
    x1a = int(first["x1"] * width)
    y1a = int(first["y1"] * height)
    x2a = int(first["x2"] * width)
    y2a = int(first["y2"] * height)
    x1b = int(second["x1"] * width)
    y1b = int(second["y1"] * height)
    x2b = int(second["x2"] * width)
    y2b = int(second["y2"] * height)
    left, top = max(x1a, x1b), max(y1a, y1b)
    right, bottom = min(x2a, x2b), min(y2a, y2b)
    if right <= left or bottom <= top:
        return (0, 0), 0.0
    overlap_width, overlap_height = right - left, bottom - top
    area_a = (x2a - x1a) * (y2a - y1a)
    area_b = (x2b - x1b) * (y2b - y1b)
    smaller = min(area_a, area_b)
    return (
        (overlap_width, overlap_height),
        0.0 if smaller <= 0 else overlap_width * overlap_height / smaller,
    )


def _validation_preview(
    bboxes: list[dict[str, Any]], count: int, is_valid: bool,
    messages: list[str], width: int, height: int,
) -> torch.Tensor:
    preview = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(preview)
    valid_colors = [(0, 255, 0), (0, 200, 0), (0, 150, 0)]
    invalid_colors = [(255, 0, 0), (200, 0, 0), (150, 0, 0)]
    font = ImageFont.load_default()
    for index, bbox in enumerate(bboxes[:count]):
        if not bbox["active"]:
            continue
        x1 = int(bbox["x1"] * width)
        y1 = int(bbox["y1"] * height)
        x2 = int(bbox["x2"] * width)
        y2 = int(bbox["y2"] * height)
        color = valid_colors[index] if is_valid else invalid_colors[index]
        draw.rectangle([x1, y1, x2, y2], outline=color, width=4)
        label = f"R{index + 1}: {x2 - x1}x{y2 - y1}"
        draw.text((x1 + 10, y1 + 10), label, fill=color, font=font)
        if not is_valid and index < len(messages):
            draw.text((x1 + 10, y1 + 24), messages[index], fill=color, font=font)
    return _pil_to_tensor(preview)


async def _region_mask_validator(
    mask1, bbox1, number_of_regions, min_region_size, max_overlap,
    mask2=None, bbox2=None, mask3=None, bbox3=None,
):
    first = await _raw_mask(mask1, name="mask1")
    height, width = first.shape
    count = int(number_of_regions)
    if not 1 <= count <= 3:
        raise ValueError("number_of_regions must be in [1, 3]")
    pairs = [(mask1, bbox1), (mask2, bbox2), (mask3, bbox3)]
    regions: list[tuple[torch.Tensor, dict[str, Any]]] = []
    messages: list[str] = []
    valid_count = 0
    is_valid = True
    for index, (mask_ref, bbox_value) in enumerate(pairs):
        if index >= count or mask_ref is None or bbox_value is None:
            regions.append((torch.zeros_like(first), _empty_bbox()))
            continue
        mask = first if index == 0 else await _raw_mask(
            mask_ref, name=f"mask{index + 1}"
        )
        if mask.shape != first.shape:
            raise ValueError("all region masks must have the same shape")
        bbox = _bbox(bbox_value)
        region_width, region_height = _region_dimensions(bbox, width, height)
        if region_width < int(min_region_size) or region_height < int(min_region_size):
            messages.append(
                f"Region {index + 1} too small: {region_width}x{region_height} "
                f"pixels (minimum: {int(min_region_size)}x{int(min_region_size)})"
            )
            bbox = dict(bbox, active=False)
            is_valid = False
        elif bbox["active"]:
            valid_count += 1
        regions.append((mask, bbox))

    if valid_count > 1:
        for first_index in range(3):
            for second_index in range(first_index + 1, 3):
                first_bbox = regions[first_index][1]
                second_bbox = regions[second_index][1]
                dimensions, overlap = _bbox_overlap(
                    first_bbox, second_bbox, width, height
                )
                if overlap > float(max_overlap):
                    messages.append(
                        f"Excessive overlap ({dimensions[0]}x{dimensions[1]} "
                        f"pixels, {overlap:.1%}) between regions "
                        f"{first_index + 1} and {second_index + 1}"
                    )
                    is_valid = False
    message = "All regions valid" if is_valid else "\n".join(messages)
    preview = _validation_preview(
        [item[1] for item in regions], count, is_valid,
        messages, width, height,
    )
    return (
        regions[0][0], regions[0][1],
        regions[1][0], regions[1][1],
        regions[2][0], regions[2][1],
        valid_count, is_valid, message, preview,
    )


def _conditioned_preview(
    masks: list[torch.Tensor], bboxes: list[dict[str, Any]], count: int,
) -> torch.Tensor:
    height, width = masks[0].shape
    preview = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(preview)
    colors = [(255, 0, 0), (0, 255, 0), (255, 255, 0)]
    for index in range(count):
        bbox = bboxes[index]
        if not bbox["active"]:
            continue
        draw.rectangle(
            [
                int(bbox["x1"] * width),
                int(bbox["y1"] * height),
                int(bbox["x2"] * width),
                int(bbox["y2"] * height),
            ],
            outline=colors[index],
            width=4,
        )
    return _pil_to_tensor(preview)


def _empty_region() -> dict[str, Any]:
    return {
        "conditioning": None,
        "mask": None,
        "bbox": [0.0, 0.0, 0.0, 0.0],
        "is_active": False,
        "strength": 1.0,
    }


async def _region_mask_conditioning(
    mask1, bbox1, conditioning1, number_of_regions, strength1,
    mask2=None, bbox2=None, conditioning2=None, strength2=1.0,
    mask3=None, bbox3=None, conditioning3=None, strength3=1.0,
):
    first = await _raw_mask(mask1, name="mask1")
    count = int(number_of_regions)
    if not 1 <= count <= 3:
        raise ValueError("number_of_regions must be in [1, 3]")
    entries = [
        (mask1, bbox1, conditioning1, strength1),
        (mask2, bbox2, conditioning2, strength2),
        (mask3, bbox3, conditioning3, strength3),
    ]
    regions: list[dict[str, Any]] = []
    preview_masks: list[torch.Tensor] = []
    preview_bboxes: list[dict[str, Any]] = []
    active_count = 0
    for index, (mask_ref, bbox_value, conditioning, strength) in enumerate(entries):
        if index >= count:
            regions.append(_empty_region())
            continue
        if mask_ref is None or bbox_value is None or conditioning is None:
            regions.append(_empty_region())
            preview_masks.append(torch.zeros_like(first))
            preview_bboxes.append(_empty_bbox())
            continue
        if not isinstance(conditioning, sdk.CondRef):
            raise TypeError(f"conditioning{index + 1} must be a CONDITIONING ref")
        mask_value = first if index == 0 else await _raw_mask(
            mask_ref, name=f"mask{index + 1}"
        )
        if mask_value.shape != first.shape:
            raise ValueError("all region masks must have the same shape")
        bbox = _bbox(bbox_value, active_required=True)
        strength_value = float(strength)
        if not math.isfinite(strength_value) or not 0.0 <= strength_value <= 10.0:
            raise ValueError("region strength must be within [0, 10]")
        regions.append({
            "conditioning": conditioning,
            "mask": mask_ref,
            "bbox": [bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"]],
            "is_active": True,
            "strength": strength_value,
        })
        preview_masks.append(mask_value)
        preview_bboxes.append(bbox)
        active_count += 1
    while len(preview_masks) < count:
        preview_masks.append(torch.zeros_like(first))
        preview_bboxes.append(_empty_bbox())
    preview = _conditioned_preview(preview_masks, preview_bboxes, count)
    return regions[0], regions[1], regions[2], active_count, preview


async def _region_overlay(image, region_preview, opacity):
    base = await _raw_image(image)
    preview = await _raw_image(region_preview, name="region_preview")
    if preview.shape[1:3] != base.shape[1:3]:
        preview = F.interpolate(
            preview.movedim(-1, 1),
            size=base.shape[1:3],
            mode="bilinear",
            align_corners=False,
        ).movedim(1, -1)
    if preview.shape[0] == 1 and base.shape[0] > 1:
        preview = preview.expand(base.shape[0], -1, -1, -1)
    if preview.shape != base.shape:
        raise ValueError("region preview must match the image batch and channels")
    byte_preview = (preview * 255).byte().cpu().numpy()
    color_sum = np.sum(byte_preview, axis=-1)
    maximum = np.max(byte_preview, axis=-1)
    minimum = np.min(byte_preview, axis=-1)
    mask = torch.from_numpy(
        (color_sum > 50) & (maximum > 30) & ((maximum - minimum) > 10)
    ).to(base.device)[..., None]
    result = torch.where(
        mask,
        (1.0 - float(opacity)) * base + float(opacity) * preview,
        base,
    )
    return (result,)


async def _flux_sampler(
    model, conditioning, latent_image, sampler_name, scheduler,
    steps, denoise, noise_seed,
):
    if not isinstance(model, sdk.ModelRef):
        raise TypeError("model must be a MODEL ref")
    if not isinstance(conditioning, sdk.CondRef):
        raise TypeError("conditioning must be a CONDITIONING ref")
    if not isinstance(latent_image, sdk.LatentRef):
        raise TypeError("latent_image must be a LATENT ref")
    # Flux uses CFG=1, so the negative branch has no influence. Passing the
    # same opaque ref avoids materializing or manufacturing host conditioning.
    sampled = await sdk.ctx().sample(
        latent=latent_image,
        steps=int(steps),
        model=model,
        positive=conditioning,
        negative=conditioning,
        cfg=1.0,
        seed=int(noise_seed),
        sampler_name=str(sampler_name),
        scheduler=str(scheduler),
        denoise=float(denoise),
        disable_noise=False,
        start_step=None,
        last_step=None,
        force_full_denoise=True,
    )
    return (sampled,)


async def _flux_union_controlnet(
    conditioning, control_net, image, union_controlnet_type,
    strength, start_percent, end_percent, vae,
):
    if float(strength) == 0.0:
        return conditioning, vae
    if not isinstance(conditioning, sdk.CondRef):
        raise TypeError("conditioning must be a CONDITIONING ref")
    if not isinstance(control_net, sdk.ControlNetRef):
        raise TypeError("control_net must be a CONTROL_NET ref")
    if not isinstance(image, sdk.ImageRef):
        raise TypeError("image must be an IMAGE ref")
    if not isinstance(vae, sdk.VaeRef):
        raise TypeError("vae must be a VAE ref")
    try:
        type_number = _UNION_TYPES[str(union_controlnet_type)]
    except KeyError as exc:
        raise ValueError("unknown Flux union ControlNet type") from exc
    typed = await control_net.with_union_type(type_number)
    positive, _negative = await typed.apply(
        conditioning,
        conditioning,
        image,
        strength=float(strength),
        start_percent=float(start_percent),
        end_percent=float(end_percent),
        vae=vae,
    )
    return positive, vae


async def _regional_mask(
    region: dict[str, Any], width: int, height: int, feather_radius: float,
) -> sdk.MaskRef:
    expected = {"conditioning", "mask", "bbox", "is_active", "strength"}
    if not isinstance(region, dict) or set(region) != expected:
        raise TypeError("REGION must have the exact secure region shape")
    if type(region["is_active"]) is not bool:
        raise TypeError("REGION is_active must be a boolean")
    bbox_value = region["bbox"]
    if (
        not isinstance(bbox_value, (list, tuple))
        or len(bbox_value) != 4
        or any(
            isinstance(item, bool)
            or not isinstance(item, (int, float))
            or not math.isfinite(float(item))
            or not 0.0 <= float(item) <= 1.0
            for item in bbox_value
        )
    ):
        raise TypeError("REGION bbox must be four normalized coordinates")
    x1, y1, x2, y2 = [float(item) for item in bbox_value]
    if x1 >= x2 or y1 >= y2:
        raise ValueError("REGION bbox coordinates must be ordered")
    mask_ref = region["mask"]
    if mask_ref is None:
        mask = _mask_from_bbox({
            "x1": x1, "y1": y1, "x2": x2, "y2": y2, "active": True,
        }, width, height)
    else:
        mask = await _raw_mask(mask_ref, name="REGION mask")
        if mask.shape != (height, width):
            mask = F.interpolate(
                mask[None, None].float(),
                size=(height, width),
                mode="bilinear",
                align_corners=False,
            )[0, 0]
    radius = float(feather_radius)
    if not math.isfinite(radius) or not 0.0 <= radius <= 100.0:
        raise ValueError("feather radius must be within [0, 100]")
    if radius > 0:
        image = Image.fromarray(
            (mask.detach().cpu().numpy() * 255).astype(np.uint8), mode="L"
        )
        image = image.filter(ImageFilter.GaussianBlur(radius=radius))
        mask = torch.from_numpy(
            np.array(image, copy=True).astype(np.float32) / 255.0
        )
    return await sdk.MaskRef._from_raw(mask)


async def _flux_attention_control(
    model, condition, latent_dimensions, region1, number_of_regions,
    enabled, feather_radius1=0.0, region2=None, feather_radius2=0.0,
    region3=None, feather_radius3=0.0,
):
    if not isinstance(model, sdk.ModelRef):
        raise TypeError("model must be a MODEL ref")
    if not isinstance(condition, sdk.CondRef):
        raise TypeError("condition must be a CONDITIONING ref")
    if not isinstance(latent_dimensions, sdk.LatentRef):
        raise TypeError("latent_dimensions must be a LATENT ref")
    if not enabled:
        return model, condition
    latent_height, latent_width = await latent_dimensions.spatial_shape()
    width, height = latent_width * 8, latent_height * 8
    count = int(number_of_regions)
    if not 1 <= count <= 3:
        raise ValueError("number_of_regions must be in [1, 3]")
    output = condition
    active = 0
    regions = [region1, region2, region3]
    feather = [feather_radius1, feather_radius2, feather_radius3]
    for index, region in enumerate(regions[:count]):
        if region is None:
            continue
        if not isinstance(region, dict) or not region.get("is_active"):
            continue
        regional_conditioning = region.get("conditioning")
        if not isinstance(regional_conditioning, sdk.CondRef):
            raise TypeError("active REGION conditioning must be a ref")
        strength = float(region.get("strength", 1.0))
        if not math.isfinite(strength) or not 0.0 <= strength <= 10.0:
            raise ValueError("REGION strength must be within [0, 10]")
        mask = await _regional_mask(region, width, height, feather[index])
        masked = await regional_conditioning.with_mask(
            mask,
            strength=strength,
            set_area_to_bounds=True,
        )
        output = await output.combine(masked)
        active += 1
    return (model, output if active else condition)


async def _flux_attention_cleanup(any_input):
    # V2 regional conditioning is execution-scoped and never replaces Flux's
    # process-global attention functions, so cleanup is deliberately a no-op.
    return (
        "Regional conditioning is execution-scoped; no global attention "
        "state requires cleanup.",
    )


_HANDLERS = {
    "BooleanBasic": (_boolean_basic, ()),
    "BooleanReverse": (_boolean_reverse, ()),
    "ChooseUpscaleModel": (_choose_upscale_model, ()),
    "FluxAttentionCleanup": (_flux_attention_cleanup, ()),
    "FluxAttentionControl": (_flux_attention_control, ("raw",)),
    "FluxResolutionNode": (_flux_resolution, ("raw",)),
    "FluxSampler": (_flux_sampler, ("sample",)),
    "FluxUnionControlNetApply": (_flux_union_controlnet, ()),
    "GetImageSizeRatio": (_get_image_size_ratio, ()),
    "HiDreamResolutionNode": (_hidream_resolution, ("raw",)),
    "IntegerSettings": (_integer_settings, ()),
    "IntegerSettingsAdvanced": (_integer_settings_advanced, ()),
    "NoisePlusBlend": (_noise_plus_blend, ("raw",)),
    "PerturbationTexture": (_perturbation_texture, ("raw",)),
    "RegionMaskConditioning": (_region_mask_conditioning, ("raw",)),
    "RegionMaskGenerator": (_region_mask_generator, ("raw",)),
    "RegionMaskProcessor": (_region_mask_processor, ("raw",)),
    "RegionMaskValidator": (_region_mask_validator, ("raw",)),
    "RegionOverlayVisualizer": (_region_overlay, ("raw",)),
    "TextBridge": (_text_bridge, ()),
    "ThreeWaySwitch": (_three_way_switch, ()),
    "TwoWaySwitch": (_two_way_switch, ()),
}


if set(_HANDLERS) != set(SCHEMAS):
    raise RuntimeError(
        f"ControlAltAI handler census differs from frozen schemas: "
        f"{set(SCHEMAS) ^ set(_HANDLERS)}"
    )


NODE_CLASS_MAPPINGS = {
    node_id: bind_node(node_id, handler, permissions=permissions)
    for node_id, (handler, permissions) in _HANDLERS.items()
}
NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: definition["schema"]["attrs"]["display_name"]
    for node_id, definition in SCHEMAS.items()
}


# Preserve import-level class names for workflows or tools that import the
# original modules directly; the authoritative registration remains the map.
for _node_id, _node_class in NODE_CLASS_MAPPINGS.items():
    globals()[SCHEMAS[_node_id]["class"]] = _node_class


__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    *[definition["class"] for definition in SCHEMAS.values()],
]
