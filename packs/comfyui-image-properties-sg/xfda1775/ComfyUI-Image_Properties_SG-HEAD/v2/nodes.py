"""Secure Nodes V2 implementation of Image Properties SG."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
import json
import math
import re
from typing import Any

import numpy as np
import torch
from PIL import Image, ImageOps, UnidentifiedImageError

from comfy_api.latest import io, sdk


_MAX_IMAGE_BYTES = 64 * 1024 * 1024
_MAX_IMAGE_PIXELS = 67_108_864
_MAX_BATCH = 4096
_STANDARD_RATIOS = (
    (1.0, "1:1"),
    (1.25, "5:4"),
    (1.33333, "4:3"),
    (1.5, "3:2"),
    (1.6, "16:10"),
    (1.66667, "5:3"),
    (1.77778, "16:9"),
    (1.88889, "17:9"),
    (2.0, "2:1"),
    (2.33333, "21:9"),
    (2.35, "2.35:1"),
    (2.39, "2.39:1"),
    (2.4, "12:5"),
)
_PROPERTIES = ["None", "Basic", "Metadata", "Both"]
_FORMATS = [
    "PNG (lossless, larger files)",
    "JPEG (lossy, smaller files)",
    "WEBP (modern, good compression)",
    "BMP (uncompressed, largest)",
    "TIFF (flexible, lossless, limited support)",
]
_JPEG_SUBSAMPLING = [
    "4:4:4 (No subsampling, best quality)",
    "4:2:2 (Moderate subsampling)",
    "4:2:0 (Maximum subsampling, smaller files)",
    "Auto (based on quality)",
]
_TIFF_COMPRESSION = [
    "none (uncompressed, largest)",
    "lzw (lossless, good compression)",
    "tiff_deflate (lossless, better compression)",
    "jpeg (lossy, smallest)",
    "packbits (lossless, basic)",
]


def _checked_image(value: Any, name: str = "image") -> torch.Tensor:
    if not isinstance(value, torch.Tensor):
        raise TypeError(f"{name} must resolve to a tensor")
    if value.ndim != 4 or int(value.shape[-1]) not in (1, 3, 4):
        raise ValueError(f"{name} must be a BHWC image tensor")
    batch, height, width, _channels = map(int, value.shape)
    if not 1 <= batch <= _MAX_BATCH:
        raise ValueError(f"{name} batch must be in [1, {_MAX_BATCH}]")
    if height < 1 or width < 1 or height * width > _MAX_IMAGE_PIXELS:
        raise ValueError(f"{name} exceeds {_MAX_IMAGE_PIXELS} pixels")
    return value


def _closest_ratio(decimal_ratio: float) -> str | None:
    difference, label = min(
        ((abs(value - decimal_ratio), label)
         for value, label in _STANDARD_RATIOS),
        key=lambda item: item[0],
    )
    return label if difference <= 0.05 else None


def _properties(
    tensor: torch.Tensor,
    *,
    size_label: str = "tensor",
    file_size_bytes: int | None = None,
) -> tuple[int, int, int, float, float, float, list[str]]:
    tensor = _checked_image(tensor)
    batch, height, width, channels = map(int, tensor.shape)
    resolution = float(width * height / 1_000_000)
    divisor = math.gcd(width, height)
    width_ratio = float(width // divisor)
    height_ratio = float(height // divisor)
    decimal = width / height
    closest = _closest_ratio(decimal)
    line1 = f"{width}x{height} | {resolution:.2f}MP "
    if closest and closest != f"{int(width_ratio)}:{int(height_ratio)}":
        line2 = (
            f"Ratio: {int(width_ratio)}:{int(height_ratio)} or "
            f"{decimal:.2f}:1 or ~{closest}"
        )
    else:
        line2 = (
            f"Ratio: {int(width_ratio)}:{int(height_ratio)} or "
            f"{decimal:.2f}:1"
        )
    if file_size_bytes is not None:
        line3 = f"File Size: {float(file_size_bytes) / (1024 * 1024):.2f}MB"
    else:
        size_mb = float(width * height * channels * 4 * batch / (1024 * 1024))
        if batch > 1:
            # Preserve the published node's display calculation exactly.
            line3 = f"Batch: {batch} images | Total Tensor: {size_mb * batch:.2f}MB"
        else:
            line3 = f"Tensor Size: {size_mb:.2f}MB"
    return (
        batch, width, height, width_ratio, height_ratio, resolution,
        [line1, line2, line3],
    )


def _json_object(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or len(value) > 2 * 1024 * 1024:
        return None
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _model_name(prompt: Any = None, workflow: Any = None, parameters: Any = None) -> str:
    prompt_data = _json_object(prompt)
    if prompt_data:
        for node_data in prompt_data.values():
            if not isinstance(node_data, dict):
                continue
            class_type = str(node_data.get("class_type", ""))
            inputs = node_data.get("inputs")
            if not isinstance(inputs, dict):
                continue
            if "CheckpointLoader" in class_type and "ckpt_name" in inputs:
                return str(inputs["ckpt_name"])
            if "UNETLoader" in class_type and "unet_name" in inputs:
                return f"{inputs['unet_name']} (UNET)"
            if "Loader" in class_type:
                if "ckpt_name" in inputs:
                    return str(inputs["ckpt_name"])
                if "unet_name" in inputs:
                    return f"{inputs['unet_name']} (UNET)"
                if "model_name" in inputs:
                    return str(inputs["model_name"])
    workflow_data = _json_object(workflow)
    nodes = workflow_data.get("nodes") if workflow_data else None
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_type = str(node.get("type", ""))
            values = node.get("widgets_values")
            if ("Checkpoint" in node_type or "Loader" in node_type) and isinstance(values, list) and values:
                return str(values[0])
    if isinstance(parameters, str) and len(parameters) <= 2 * 1024 * 1024:
        match = re.search(r"Model:\s*([^,\n]+)", parameters)
        if match:
            return match.group(1).strip()
    return "N/A"


def _generation_params(prompt: Any = None, parameters: Any = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "seed": "N/A",
        "steps": "N/A",
        "cfg": "N/A",
        "sampler": "N/A",
        "scheduler": "N/A",
    }
    prompt_data = _json_object(prompt)
    if prompt_data:
        for node_data in prompt_data.values():
            if not isinstance(node_data, dict):
                continue
            class_type = str(node_data.get("class_type", ""))
            inputs = node_data.get("inputs")
            if not isinstance(inputs, dict):
                continue
            if class_type == "KSampler":
                result.update({
                    "seed": inputs.get("seed", "N/A"),
                    "steps": inputs.get("steps", "N/A"),
                    "cfg": inputs.get("cfg", "N/A"),
                    "sampler": inputs.get("sampler_name", "N/A"),
                    "scheduler": inputs.get("scheduler", "N/A"),
                })
                return result
            if "seed" in inputs or "noise_seed" in inputs:
                result["seed"] = inputs.get("seed", inputs.get("noise_seed", result["seed"]))
            for source, target in (
                ("steps", "steps"),
                ("cfg", "cfg"),
                ("sampler_name", "sampler"),
                ("scheduler", "scheduler"),
            ):
                if source in inputs:
                    result[target] = inputs[source]
    if isinstance(parameters, str) and len(parameters) <= 2 * 1024 * 1024:
        patterns = {
            "seed": (r"Seed:\s*(\d+)", int),
            "steps": (r"Steps:\s*(\d+)", int),
            "cfg": (r"CFG scale:\s*([\d.]+)", float),
            "sampler": (r"Sampler:\s*([^,\n]+)", str),
            "scheduler": (r"Schedule type:\s*([^,\n]+)", str),
        }
        for key, (pattern, convert) in patterns.items():
            if result[key] != "N/A":
                continue
            match = re.search(pattern, parameters)
            if match:
                value = match.group(1).strip()
                result[key] = convert(value)
    return result


def _metadata_lines(prompt: Any = None, workflow: Any = None, parameters: Any = None) -> tuple[str, list[str], dict[str, Any]]:
    model = _model_name(prompt, workflow, parameters)
    values = _generation_params(prompt, parameters)
    lines = [
        f"Model: {model}",
        f"Seed: {values['seed']} | Steps: {values['steps']} | CFG: {values['cfg']}",
        f"Sampler: {values['sampler']} | Scheduler: {values['scheduler']}",
    ]
    return model, lines, values


def _parse_filename(value: str, now: datetime | None = None) -> str:
    current = now or datetime.now()

    def render(match: re.Match[str], conversions: dict[str, str]) -> str:
        format_string = match.group(1)
        for source, target in conversions.items():
            format_string = format_string.replace(source, target)
        return current.strftime(format_string)

    value = re.sub(
        r"%date:([^%]+)%",
        lambda match: render(match, {
            "yyyy": "%Y", "yy": "%y", "MM": "%m", "dd": "%d",
            "HH": "%H", "hh": "%H", "mm": "%M", "ss": "%S",
        }),
        str(value),
    )
    value = re.sub(
        r"%time:([^%]+)%",
        lambda match: render(match, {
            "HH": "%H", "hh": "%H", "mm": "%M", "ss": "%S",
        }),
        value,
    )
    return (
        value.replace("%date%", current.strftime("%Y-%m-%d"))
        .replace("%time%", current.strftime("%H-%M-%S"))
        .replace("%timestamp%", str(int(current.timestamp())))
    )


class ViewImagePropertiesSG(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ViewImagePropertiesSG",
            display_name="View Image Properties-SG",
            category="image/analysis",
            inputs=[io.Image.Input("image")],
            outputs=[
                io.Image.Output("image"),
                io.Int.Output("batch_count"),
                io.Int.Output("width"),
                io.Int.Output("height"),
                io.Float.Output("width_ratio"),
                io.Float.Output("height_ratio"),
                io.Float.Output("Resolution_in_MP"),
            ],
            is_output_node=True,
        )

    @classmethod
    async def execute(cls, image: sdk.ImageRef) -> io.NodeOutput:
        tensor = _checked_image(await image.raw())
        batch, width, height, wr, hr, resolution, lines = _properties(tensor)
        return io.NodeOutput(
            image, batch, width, height, wr, hr, resolution,
            ui={"text": lines},
        )


class LoadImageandviewPropertiesSG(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets", "raw")

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="LoadImageandviewPropertiesSG",
            display_name="Load Image and view Properties-SG",
            category="image/analysis",
            inputs=[
                io.Combo.Input(
                    "image",
                    options=[],
                    upload=io.UploadType.image,
                    image_folder=io.FolderType.input,
                ),
            ],
            outputs=[
                io.Image.Output("image"),
                io.Mask.Output("mask"),
                io.Int.Output("width"),
                io.Int.Output("height"),
                io.Float.Output("width_ratio"),
                io.Float.Output("height_ratio"),
                io.Float.Output("Resolution_in_MP"),
            ],
            is_output_node=True,
        )

    @classmethod
    async def validate_inputs(cls, image: str) -> bool | str:
        try:
            await sdk.ctx().assets.resolve("input", str(image))
        except Exception:
            return f"Invalid image file: {image}"
        return True

    @classmethod
    async def fingerprint_inputs(cls, image: str) -> str:
        asset = await sdk.ctx().assets.resolve("input", str(image))
        return await sdk.ctx().assets.digest(asset)

    @classmethod
    async def execute(cls, image: str) -> io.NodeOutput:
        assets = sdk.ctx().assets
        asset = await assets.resolve("input", str(image))
        size = int(await assets.size(asset))
        if not 1 <= size <= _MAX_IMAGE_BYTES:
            raise ValueError("input image must be between 1 byte and 64 MiB")
        data = await assets.read_bytes(asset)
        if len(data) != size:
            raise ValueError("input image changed while it was read")
        try:
            with Image.open(BytesIO(data)) as source:
                if source.width * source.height > _MAX_IMAGE_PIXELS:
                    raise ValueError("input image exceeds 67108864 pixels")
                info = dict(source.info or {})
                loaded = ImageOps.exif_transpose(source)
                if loaded.mode == "I":
                    loaded = loaded.point(lambda value: value * (1 / 255))
                original = loaded.copy()
                rgb = loaded.convert("RGB")
        except (UnidentifiedImageError, OSError, SyntaxError) as error:
            raise ValueError("input asset is not a readable image") from error
        pixels = torch.from_numpy(
            np.asarray(rgb, dtype=np.float32) / 255.0,
        ).unsqueeze(0)
        if "A" in original.getbands():
            alpha = np.asarray(original.getchannel("A"), dtype=np.float32) / 255.0
            mask_tensor = 1.0 - torch.from_numpy(alpha.copy())
        else:
            mask_tensor = torch.zeros(
                (rgb.height, rgb.width), dtype=torch.float32, device="cpu",
            )
        image_ref = await sdk.ImageRef._from_raw(pixels)
        mask_ref = await sdk.MaskRef._from_raw(mask_tensor)
        _batch, width, height, wr, hr, resolution, basic = _properties(
            pixels, file_size_bytes=size,
        )
        model, metadata, _values = _metadata_lines(
            info.get("prompt"), info.get("workflow"), info.get("parameters"),
        )
        del model
        return io.NodeOutput(
            image_ref, mask_ref, width, height, wr, hr, resolution,
            ui={"text": [*basic, "", *metadata]},
        )


class PreviewImageandviewPropertiesSG(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw", "ui")

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="PreviewImageandviewPropertiesSG",
            display_name="Preview Image and view Properties-SG",
            category="image",
            inputs=[io.Image.Input("images")],
            outputs=[
                io.Image.Output("image"),
                io.Int.Output("batch_count"),
                io.Int.Output("width"),
                io.Int.Output("height"),
                io.Float.Output("width_ratio"),
                io.Float.Output("height_ratio"),
                io.Float.Output("Resolution_in_MP"),
            ],
            is_output_node=True,
        )

    @classmethod
    async def execute(cls, images: sdk.ImageRef) -> io.NodeOutput:
        tensor = _checked_image(await images.raw(), "images")
        batch, width, height, wr, hr, resolution, lines = _properties(tensor)
        preview = await sdk.ctx().ui.preview_images(images)
        return io.NodeOutput(
            images, batch, width, height, wr, hr, resolution,
            ui={**preview, "text": lines},
        )


class SaveImageFormatQualityPropertiesSG(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw", "output", "ui")

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SaveImageFormatQualityPropertiesSG",
            display_name="Save Image Format Quality Properties-SG",
            category="image",
            inputs=[
                io.Image.Input("images"),
                io.String.Input("filename_prefix", default="ComfyUI"),
                io.Combo.Input(
                    "Properties",
                    options=_PROPERTIES,
                    default="Both",
                    tooltip=(
                        "Display options:\n"
                        "• None: Hides all information\n"
                        "• Basic: Shows resolution, aspect ratio, and size\n"
                        "• Metadata: Shows model, seed, steps, CFG, sampler, scheduler\n"
                        "• Both: Shows all information"
                    ),
                ),
                io.Combo.Input(
                    "format",
                    options=_FORMATS,
                    default="PNG (lossless, larger files)",
                    tooltip=" ❗WARNING❗\nOnly PNG saves comfyUI workflow and metadata",
                ),
                io.Int.Input(
                    "png_compress_level", default=9, min=0, max=9, step=1,
                    optional=True,
                ),
                io.Int.Input(
                    "jpeg_quality", default=95, min=1, max=100, step=1,
                    optional=True,
                ),
                io.Boolean.Input("jpeg_optimize", default=True, optional=True),
                io.Combo.Input(
                    "jpeg_subsampling",
                    options=_JPEG_SUBSAMPLING,
                    default="Auto (based on quality)",
                    optional=True,
                ),
                io.Int.Input(
                    "webp_quality", default=90, min=1, max=100, step=1,
                    optional=True,
                ),
                io.Int.Input(
                    "webp_method", default=4, min=0, max=6, step=1,
                    optional=True,
                ),
                io.Boolean.Input("webp_lossless", default=False, optional=True),
                io.Combo.Input(
                    "tiff_compression",
                    options=_TIFF_COMPRESSION,
                    default="tiff_deflate (lossless, better compression)",
                    optional=True,
                ),
                io.Int.Input(
                    "tiff_jpeg_quality", default=90, min=1, max=100, step=1,
                    optional=True,
                ),
            ],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
            is_output_node=True,
        )

    @classmethod
    async def execute(
        cls,
        images: sdk.ImageRef,
        filename_prefix: str = "ComfyUI",
        Properties: str = "Both",
        format: str = "PNG (lossless, larger files)",
        png_compress_level: int = 9,
        jpeg_quality: int = 95,
        jpeg_optimize: bool = True,
        jpeg_subsampling: str = "Auto (based on quality)",
        webp_quality: int = 90,
        webp_method: int = 4,
        webp_lossless: bool = False,
        tiff_compression: str = "tiff_deflate (lossless, better compression)",
        tiff_jpeg_quality: int = 90,
        prompt: Any = None,
        extra_pnginfo: Any = None,
    ) -> io.NodeOutput:
        del extra_pnginfo
        tensor = _checked_image(await images.raw(), "images")
        _batch, _width, _height, _wr, _hr, _resolution, basic = _properties(
            tensor, file_size_bytes=0,
        )
        model, metadata, generation = _metadata_lines(prompt)
        if Properties == "None":
            display = []
        elif Properties == "Basic":
            display = basic
        elif Properties == "Metadata":
            display = metadata
        else:
            display = [*basic, "", *metadata]

        format_map = {
            _FORMATS[0]: "png",
            _FORMATS[1]: "jpeg",
            _FORMATS[2]: "webp",
            _FORMATS[3]: "bmp",
            _FORMATS[4]: "tiff",
        }
        image_format = format_map.get(format)
        if image_format is None:
            raise ValueError("unsupported image format choice")
        subsampling_map = {
            _JPEG_SUBSAMPLING[0]: "4:4:4",
            _JPEG_SUBSAMPLING[1]: "4:2:2",
            _JPEG_SUBSAMPLING[2]: "4:2:0",
            _JPEG_SUBSAMPLING[3]: "auto",
        }
        compression_map = {
            _TIFF_COMPRESSION[0]: "none",
            _TIFF_COMPRESSION[1]: "lzw",
            _TIFF_COMPRESSION[2]: "deflate",
            _TIFF_COMPRESSION[3]: "jpeg",
            _TIFF_COMPRESSION[4]: "packbits",
        }
        if jpeg_subsampling not in subsampling_map:
            raise ValueError("unsupported JPEG subsampling choice")
        if tiff_compression not in compression_map:
            raise ValueError("unsupported TIFF compression choice")
        quality = (
            int(jpeg_quality) if image_format == "jpeg"
            else int(webp_quality) if image_format == "webp"
            else int(tiff_jpeg_quality)
        )
        extra_metadata = None
        if image_format == "png":
            extra_metadata = {
                "parameters": {
                    "model_name": model,
                    "seed": generation["seed"],
                    "steps": generation["steps"],
                    "cfg": generation["cfg"],
                    "sampler": generation["sampler"],
                    "scheduler": generation["scheduler"],
                },
            }
        saved = await sdk.ctx().output.save_images(
            images,
            filename_prefix=_parse_filename(filename_prefix),
            compress_level=int(png_compress_level),
            save_metadata=image_format == "png",
            extra_metadata=extra_metadata,
            image_format=image_format,
            quality=quality,
            lossless=bool(webp_lossless),
            optimize=bool(jpeg_optimize) if image_format == "jpeg" else False,
            jpeg_subsampling=subsampling_map[jpeg_subsampling],
            webp_method=int(webp_method),
            tiff_compression=compression_map[tiff_compression],
        )
        shown = (
            await sdk.ctx().ui.preview_images(images)
            if image_format in {"bmp", "tiff"}
            else saved
        )
        return io.NodeOutput(ui={**shown, "text": display})


ALL_NODE_CLASSES = [
    ViewImagePropertiesSG,
    LoadImageandviewPropertiesSG,
    PreviewImageandviewPropertiesSG,
    SaveImageFormatQualityPropertiesSG,
]
