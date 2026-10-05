"""Secure ImageAutosize nodes using bounded raw-tensor execution."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

from comfy_api.latest import ComfyExtension, io, sdk


SCALE_METHODS = ["nearest-exact", "bilinear", "area", "bicubic", "lanczos"]
CONSTRAINT_PRIORITIES = ["min_size", "max_size"]
CROP_MODES = [
    "none", "pad", "center", "top", "bottom", "left", "right",
    "top_left", "top_right", "bottom_left", "bottom_right",
]
AUTOSIZE_TRANSFORM = io.Custom("AUTOSIZE_TRANSFORM")

MAX_DIMENSION = 16_384
MAX_ELEMENTS = 268_435_456
MAX_BATCH = 4096


@dataclass(frozen=True)
class AutosizeTransform:
    original_width: int
    original_height: int
    target_width: int
    target_height: int
    resize_width: int
    resize_height: int
    offset_x: int
    offset_y: int
    crop_mode: str


def _calculate_target_dimensions(
    width: int,
    height: int,
    max_size: int,
    min_size: int,
    constraint_priority: str,
    divisible_by: int,
) -> tuple[int, int]:
    max_scale = max_size / max(width, height)
    min_scale = min_size / min(width, height)
    scale = max(max_scale, min_scale) if constraint_priority == "min_size" else min(
        min_scale, max_scale)
    target_width = max(
        divisible_by, round(width * scale / divisible_by) * divisible_by)
    target_height = max(
        divisible_by, round(height * scale / divisible_by) * divisible_by)
    _validate_dimensions(target_width, target_height, "target")
    return target_width, target_height


def _get_crop_origin(
    width: int,
    height: int,
    target_width: int,
    target_height: int,
    crop_mode: str,
) -> tuple[int, int]:
    if crop_mode in ("left", "top_left", "bottom_left"):
        x = 0
    elif crop_mode in ("right", "top_right", "bottom_right"):
        x = width - target_width
    else:
        x = (width - target_width) // 2

    if crop_mode in ("top", "top_left", "top_right"):
        y = 0
    elif crop_mode in ("bottom", "bottom_left", "bottom_right"):
        y = height - target_height
    else:
        y = (height - target_height) // 2
    return x, y


def _validate_dimensions(width: int, height: int, label: str) -> None:
    if not 1 <= width <= MAX_DIMENSION or not 1 <= height <= MAX_DIMENSION:
        raise ValueError(f"{label} dimensions must be in [1, {MAX_DIMENSION}]")
    if width * height > MAX_ELEMENTS:
        raise ValueError(f"{label} dimensions exceed the pixel limit")


def _validate_raw(value: Any) -> tuple[torch.Tensor, bool]:
    if not isinstance(value, torch.Tensor):
        raise TypeError("image or mask must materialize as a tensor")
    if value.ndim == 4:
        if value.shape[-1] not in (1, 3, 4):
            raise ValueError("IMAGE must have 1, 3, or 4 channels")
        is_image = True
        height, width = int(value.shape[-3]), int(value.shape[-2])
    elif value.ndim == 3:
        is_image = False
        height, width = int(value.shape[-2]), int(value.shape[-1])
    else:
        raise ValueError("input must be a BHWC IMAGE or BHW MASK")
    if not 1 <= int(value.shape[0]) <= MAX_BATCH:
        raise ValueError(f"batch size must be in [1, {MAX_BATCH}]")
    _validate_dimensions(width, height, "input")
    if value.numel() > MAX_ELEMENTS:
        raise ValueError("input tensor is too large")
    return value, is_image


def _to_samples(value: torch.Tensor, is_image: bool) -> torch.Tensor:
    return value.movedim(-1, 1) if is_image else value.unsqueeze(1)


def _from_samples(samples: torch.Tensor, is_image: bool) -> torch.Tensor:
    return samples.movedim(1, -1) if is_image else samples.squeeze(1)


def _lanczos(samples: torch.Tensor, width: int, height: int) -> torch.Tensor:
    source = samples.squeeze(1) if samples.shape[1] == 1 else samples.movedim(1, -1)
    images = [
        Image.fromarray(np.clip(255.0 * item.detach().cpu().numpy(), 0, 255).astype(np.uint8))
        for item in source
    ]
    resized = [
        item.resize((width, height), resample=Image.Resampling.LANCZOS)
        for item in images
    ]
    tensors = []
    for item in resized:
        array = np.asarray(item).astype(np.float32) / 255.0
        tensor = torch.from_numpy(array.copy())
        tensors.append(tensor.movedim(-1, 0) if tensor.ndim == 3 else tensor)
    return torch.stack(tensors).to(samples.device, samples.dtype)


def _resize_samples(
    samples: torch.Tensor,
    width: int,
    height: int,
    interpolation_mode: str,
) -> torch.Tensor:
    if interpolation_mode not in SCALE_METHODS:
        raise ValueError(f"unsupported interpolation mode {interpolation_mode!r}")
    _validate_dimensions(width, height, "resize")
    if samples.shape[-1] == width and samples.shape[-2] == height:
        return samples
    if samples.shape[0] * samples.shape[1] * width * height > MAX_ELEMENTS:
        raise ValueError("resized tensor is too large")
    if interpolation_mode == "lanczos":
        return _lanczos(samples, width, height)
    return F.interpolate(samples, size=(height, width), mode=interpolation_mode)


def _decode_transform(value: Any) -> AutosizeTransform:
    if isinstance(value, AutosizeTransform):
        transform = value
    elif isinstance(value, Mapping):
        expected = tuple(AutosizeTransform.__dataclass_fields__)
        if set(value) != set(expected):
            raise ValueError("autosize transform has invalid fields")
        integers = {}
        for field in expected[:-1]:
            item = value[field]
            if isinstance(item, bool) or not isinstance(item, int):
                raise TypeError(f"autosize transform {field} must be an integer")
            integers[field] = item
        crop_mode = value["crop_mode"]
        if not isinstance(crop_mode, str):
            raise TypeError("autosize transform crop_mode must be a string")
        transform = AutosizeTransform(**integers, crop_mode=crop_mode)
    else:
        raise TypeError("autosize transform must be a plain object")

    if transform.crop_mode not in CROP_MODES:
        raise ValueError("autosize transform has an invalid crop mode")
    for label, width, height in (
        ("source", transform.original_width, transform.original_height),
        ("target", transform.target_width, transform.target_height),
        ("resize", transform.resize_width, transform.resize_height),
    ):
        _validate_dimensions(width, height, label)
    if transform.offset_x < 0 or transform.offset_y < 0:
        raise ValueError("autosize transform offsets cannot be negative")
    if transform.crop_mode == "pad":
        if (
            transform.offset_x + transform.resize_width > transform.target_width
            or transform.offset_y + transform.resize_height > transform.target_height
        ):
            raise ValueError("autosize padding exceeds its target canvas")
    elif transform.crop_mode != "none":
        if (
            transform.offset_x + transform.target_width > transform.resize_width
            or transform.offset_y + transform.target_height > transform.resize_height
        ):
            raise ValueError("autosize crop exceeds the resized tensor")
    return transform


def _apply_transform(
    value: torch.Tensor,
    is_image: bool,
    transform: AutosizeTransform,
    interpolation_mode: str,
) -> torch.Tensor:
    samples = _to_samples(value, is_image)
    if (
        samples.shape[-1] != transform.original_width
        or samples.shape[-2] != transform.original_height
    ):
        raise ValueError(
            "Autosize transform input dimensions must match its source dimensions. "
            f"Expected {(transform.original_width, transform.original_height)}, got "
            f"{(samples.shape[-1], samples.shape[-2])}."
        )
    samples = _resize_samples(
        samples, transform.resize_width, transform.resize_height,
        interpolation_mode)
    if transform.crop_mode == "pad":
        pad_right = (
            transform.target_width - transform.resize_width - transform.offset_x)
        pad_bottom = (
            transform.target_height - transform.resize_height - transform.offset_y)
        padding = (transform.offset_x, pad_right, transform.offset_y, pad_bottom)
        if any(padding):
            samples = F.pad(
                samples,
                padding,
                mode="replicate" if is_image else "constant",
            )
    elif transform.crop_mode != "none":
        samples = samples[
            :,
            :,
            transform.offset_y:transform.offset_y + transform.target_height,
            transform.offset_x:transform.offset_x + transform.target_width,
        ]
    result = _from_samples(samples, is_image)
    _validate_raw(result)
    return result


async def _materialize(ref: sdk.TensorRef) -> tuple[torch.Tensor, bool]:
    return _validate_raw(await ref.raw())


async def _wrap(value: torch.Tensor, is_image: bool):
    ref_type = sdk.ImageRef if is_image else sdk.MaskRef
    return await ref_type._from_raw(value)


class ImageAutosize(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        image_type = io.MatchType.Template("image_type", [io.Image, io.Mask])
        return io.Schema(
            node_id="ImageAutosize",
            display_name="Image/Mask Autosize",
            category="image",
            description=(
                "Automatically resizes an image or mask for diffusion workflows."),
            search_aliases=[
                "autosize", "image mask autosize", "auto resize",
                "resize to multiple", "resize image", "resize mask",
            ],
            inputs=[
                io.MatchType.Input(
                    "image", template=image_type,
                    tooltip="The image or mask to resize."),
                io.Int.Input(
                    "max_size", default=1280, min=1, max=8192, step=1,
                    tooltip=(
                        "Longer-dimension target used to calculate one candidate "
                        "resize scale.")),
                io.Int.Input(
                    "min_size", default=512, min=1, max=4096, step=1,
                    tooltip=(
                        "Shorter-dimension target used to calculate one candidate "
                        "resize scale.")),
                io.Int.Input(
                    "divisible_by", default=32, min=1, max=8192, step=1,
                    tooltip=(
                        "Rounds both output dimensions to the nearest multiple of "
                        "this value.")),
                io.Combo.Input(
                    "interpolation_mode", options=SCALE_METHODS,
                    default="lanczos",
                    tooltip="Interpolation algorithm used for resizing."),
                io.Combo.Input(
                    "crop_mode", options=CROP_MODES, default="center",
                    tooltip=(
                        "Anchored modes preserve aspect ratio by cropping. Pad "
                        "preserves aspect ratio with reversible padding. None "
                        "stretches to the output dimensions.")),
                io.Combo.Input(
                    "constraint_priority", options=CONSTRAINT_PRIORITIES,
                    default="min_size",
                    tooltip=(
                        "Chooses the candidate scale. min_size uses the larger "
                        "scale; max_size uses the smaller scale. Divisibility "
                        "rounding runs afterward.")),
            ],
            outputs=[
                io.MatchType.Output(template=image_type, display_name="resized"),
                io.Int.Output(display_name="width"),
                io.Int.Output(display_name="height"),
                io.Float.Output(display_name="scale_x"),
                io.Float.Output(display_name="scale_y"),
                AUTOSIZE_TRANSFORM.Output(display_name="transform"),
            ],
        )

    @classmethod
    async def execute(
        cls,
        image: sdk.TensorRef,
        max_size: int,
        min_size: int,
        constraint_priority: str,
        divisible_by: int,
        interpolation_mode: str,
        crop_mode: str,
    ) -> io.NodeOutput:
        if constraint_priority not in CONSTRAINT_PRIORITIES:
            raise ValueError("unknown constraint priority")
        if crop_mode not in CROP_MODES:
            raise ValueError("unknown crop mode")
        value, is_image = await _materialize(image)
        samples = _to_samples(value, is_image)
        height, width = (int(samples.shape[-2]), int(samples.shape[-1]))
        target_width, target_height = _calculate_target_dimensions(
            width, height, max_size, min_size, constraint_priority,
            divisible_by)

        resize_width = target_width
        resize_height = target_height
        if crop_mode == "pad":
            scale = min(target_width / width, target_height / height)
            resize_width = min(target_width, max(1, round(width * scale)))
            resize_height = min(target_height, max(1, round(height * scale)))
        elif crop_mode != "none":
            scale = max(target_width / width, target_height / height)
            resize_width = max(target_width, round(width * scale))
            resize_height = max(target_height, round(height * scale))
        _validate_dimensions(resize_width, resize_height, "resize")

        x = 0
        y = 0
        if crop_mode == "pad":
            x = (target_width - resize_width) // 2
            y = (target_height - resize_height) // 2
        elif crop_mode != "none":
            x, y = _get_crop_origin(
                resize_width, resize_height, target_width, target_height,
                crop_mode)
        transform = AutosizeTransform(
            original_width=width,
            original_height=height,
            target_width=target_width,
            target_height=target_height,
            resize_width=resize_width,
            resize_height=resize_height,
            offset_x=x,
            offset_y=y,
            crop_mode=crop_mode,
        )
        output = _apply_transform(
            value, is_image, transform, interpolation_mode)
        return io.NodeOutput(
            await _wrap(output, is_image),
            target_width,
            target_height,
            resize_width / width,
            resize_height / height,
            asdict(transform),
        )


class ImageAutosizeApplyTransform(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        image_type = io.MatchType.Template("image_type", [io.Image, io.Mask])
        return io.Schema(
            node_id="ImageAutosizeApplyTransform",
            display_name="Apply Autosize Transform",
            category="image",
            inputs=[
                io.MatchType.Input("image", template=image_type),
                AUTOSIZE_TRANSFORM.Input("transform"),
                io.Combo.Input(
                    "interpolation_mode", options=SCALE_METHODS,
                    default="nearest-exact"),
            ],
            outputs=[
                io.MatchType.Output(template=image_type, display_name="resized")],
        )

    @classmethod
    async def execute(
        cls,
        image: sdk.TensorRef,
        transform: Mapping[str, Any],
        interpolation_mode: str,
    ) -> io.NodeOutput:
        value, is_image = await _materialize(image)
        decoded = _decode_transform(transform)
        output = _apply_transform(
            value, is_image, decoded, interpolation_mode)
        return io.NodeOutput(await _wrap(output, is_image))


class ImageAutosizeRestore(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        image_type = io.MatchType.Template("image_type", [io.Image, io.Mask])
        return io.Schema(
            node_id="ImageAutosizeRestore",
            display_name="Restore Autosized Image/Mask",
            category="image",
            inputs=[
                io.MatchType.Input("image", template=image_type),
                AUTOSIZE_TRANSFORM.Input("transform"),
                io.Combo.Input(
                    "interpolation_mode", options=SCALE_METHODS,
                    default="lanczos"),
            ],
            outputs=[
                io.MatchType.Output(template=image_type, display_name="restored")],
        )

    @classmethod
    async def execute(
        cls,
        image: sdk.TensorRef,
        transform: Mapping[str, Any],
        interpolation_mode: str,
    ) -> io.NodeOutput:
        decoded = _decode_transform(transform)
        if decoded.crop_mode != "pad":
            raise ValueError(
                "Restore Autosized Image/Mask requires an Autosize transform "
                "using pad mode.")
        value, is_image = await _materialize(image)
        samples = _to_samples(value, is_image)
        if (
            samples.shape[-1] != decoded.target_width
            or samples.shape[-2] != decoded.target_height
        ):
            raise ValueError(
                "Autosized input dimensions must match the transform output "
                f"dimensions. Expected "
                f"{(decoded.target_width, decoded.target_height)}, got "
                f"{(samples.shape[-1], samples.shape[-2])}."
            )
        samples = samples[
            :,
            :,
            decoded.offset_y:decoded.offset_y + decoded.resize_height,
            decoded.offset_x:decoded.offset_x + decoded.resize_width,
        ]
        samples = _resize_samples(
            samples,
            decoded.original_width,
            decoded.original_height,
            interpolation_mode,
        )
        output = _from_samples(samples, is_image)
        _validate_raw(output)
        return io.NodeOutput(await _wrap(output, is_image))


NODE_CLASS_MAPPINGS = {
    "ImageAutosize": ImageAutosize,
    "ImageAutosizeApplyTransform": ImageAutosizeApplyTransform,
    "ImageAutosizeRestore": ImageAutosizeRestore,
}


class ImageAutosizeExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint() -> ImageAutosizeExtension:
    return ImageAutosizeExtension()
