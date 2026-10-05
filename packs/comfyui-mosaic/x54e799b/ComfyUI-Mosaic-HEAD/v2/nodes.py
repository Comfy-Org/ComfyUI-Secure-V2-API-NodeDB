"""Secure Nodes V2 wrappers for ComfyUI-Mosaic."""

from __future__ import annotations

import math

import torch
from comfy_api.latest import ComfyExtension, io

from .algorithms import MosaicCreator as _LegacyMosaicCreator
from .algorithms import MosaicDetector as _LegacyMosaicDetector

MAX_BATCH = 64
MAX_DIMENSION = 8_192
MAX_PIXELS = 16_777_216
MOSAIC_TYPES = [
    "pixelation",
    "blur",
    "block_average",
    "squares",
    "circles",
    "hexagons",
    "gradient_horizontal",
    "gradient_vertical",
]
OVERLAY_COLORS = ["red", "green", "blue", "yellow", "cyan", "magenta", "white"]


def _bounded_int(name: str, value: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be in [{minimum}, {maximum}]")
    return value


def _bounded_float(name: str, value: float, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise ValueError(f"{name} must be finite and in [{minimum}, {maximum}]")
    return result


def _choice(name: str, value: str, choices: list[str]) -> str:
    if not isinstance(value, str) or value not in choices:
        raise ValueError(f"{name} must be one of {choices}")
    return value


def _image(value: torch.Tensor) -> torch.Tensor:
    if not isinstance(value, torch.Tensor):
        raise TypeError("image must be a tensor")
    if value.ndim != 4 or value.shape[-1] != 3:
        raise ValueError("image must use BHWC layout with exactly three RGB channels")
    batch, height, width, _channels = (int(item) for item in value.shape)
    if not 1 <= batch <= MAX_BATCH:
        raise ValueError(f"image batch must be in [1, {MAX_BATCH}]")
    if not 1 <= height <= MAX_DIMENSION or not 1 <= width <= MAX_DIMENSION:
        raise ValueError(f"image dimensions must be in [1, {MAX_DIMENSION}]")
    if batch * height * width > MAX_PIXELS:
        raise ValueError(f"image exceeds the {MAX_PIXELS}-pixel limit")
    if not value.dtype.is_floating_point:
        raise TypeError("image must use a floating-point dtype")
    if not torch.isfinite(value).all():
        raise ValueError("image must contain only finite values")
    return value


def _mask(value: torch.Tensor | None, image: torch.Tensor) -> torch.Tensor | None:
    if value is None:
        return None
    if not isinstance(value, torch.Tensor):
        raise TypeError("mask must be a tensor")
    if value.ndim != 3 or tuple(value.shape) != tuple(image.shape[:3]):
        raise ValueError(
            "mask must use BHW layout and match the image batch and dimensions"
        )
    if not value.dtype.is_floating_point:
        raise TypeError("mask must use a floating-point dtype")
    if not torch.isfinite(value).all():
        raise ValueError("mask must contain only finite values")
    return value


class MosaicCreator(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="MosaicCreator",
            display_name="Mosaic Creator",
            category="🧪AILab/🔦Mosaic",
            inputs=[
                io.Image.Input("image"),
                io.Combo.Input("mosaic_type", options=MOSAIC_TYPES),
                io.Int.Input("block_size", default=20, min=2, max=100, step=1),
                io.Float.Input(
                    "intensity",
                    default=1.0,
                    min=0.0,
                    max=1.0,
                    step=0.1,
                    display_mode=io.NumberDisplay.slider,
                ),
                io.Mask.Input("mask", optional=True),
                io.Boolean.Input("preserve_edges", default=False, optional=True),
            ],
            outputs=[io.Image.Output("image"), io.Mask.Output("processing_mask")],
        )

    @classmethod
    def execute(
        cls,
        image: torch.Tensor,
        mosaic_type: str,
        block_size: int,
        intensity: float,
        mask: torch.Tensor | None = None,
        preserve_edges: bool = False,
    ) -> io.NodeOutput:
        image = _image(image)
        mosaic_type = _choice("mosaic_type", mosaic_type, MOSAIC_TYPES)
        block_size = _bounded_int("block_size", block_size, 2, 100)
        intensity = _bounded_float("intensity", intensity, 0.0, 1.0)
        if not isinstance(preserve_edges, bool):
            raise TypeError("preserve_edges must be a boolean")
        mask = _mask(mask, image)
        result = _LegacyMosaicCreator().create_mosaic(
            image, mosaic_type, block_size, intensity, mask, preserve_edges
        )
        return io.NodeOutput(*result)


class MosaicDetector(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="MosaicDetector",
            display_name="Mosaic Detector",
            category="🧪AILab/🔦Mosaic",
            inputs=[
                io.Image.Input("image"),
                io.Int.Input("top_n", default=1, min=1, max=20, step=1),
                io.Int.Input("mask_expand", default=0, min=0, max=64, step=1),
                io.Int.Input("mask_blur", default=0, min=0, max=64, step=2),
                io.Boolean.Input("invert_mask", default=False),
                io.Combo.Input("overlay_color", options=OVERLAY_COLORS),
                io.Float.Input(
                    "overlay_opacity", default=0.5, min=0.0, max=1.0, step=0.1
                ),
            ],
            outputs=[
                io.Image.Output("image"),
                io.Image.Output("mask_overlay"),
                io.Mask.Output("mask"),
            ],
        )

    @classmethod
    def execute(
        cls,
        image: torch.Tensor,
        top_n: int,
        mask_expand: int,
        mask_blur: int,
        invert_mask: bool,
        overlay_color: str,
        overlay_opacity: float,
    ) -> io.NodeOutput:
        image = _image(image)
        top_n = _bounded_int("top_n", top_n, 1, 20)
        mask_expand = _bounded_int("mask_expand", mask_expand, 0, 64)
        mask_blur = _bounded_int("mask_blur", mask_blur, 0, 64)
        if not isinstance(invert_mask, bool):
            raise TypeError("invert_mask must be a boolean")
        overlay_color = _choice("overlay_color", overlay_color, OVERLAY_COLORS)
        overlay_opacity = _bounded_float("overlay_opacity", overlay_opacity, 0.0, 1.0)
        result = _LegacyMosaicDetector().detect_mosaic(
            image,
            top_n,
            mask_expand,
            mask_blur,
            invert_mask,
            overlay_color,
            overlay_opacity,
        )
        return io.NodeOutput(*result)


NODE_CLASS_MAPPINGS = {
    "MosaicCreator": MosaicCreator,
    "MosaicDetector": MosaicDetector,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "MosaicCreator": "Mosaic Creator",
    "MosaicDetector": "Mosaic Detector",
}


class MosaicExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [MosaicCreator, MosaicDetector]


async def comfy_entrypoint() -> MosaicExtension:
    return MosaicExtension()


__all__ = [
    "MAX_BATCH",
    "MAX_DIMENSION",
    "MAX_PIXELS",
    "MOSAIC_TYPES",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "OVERLAY_COLORS",
    "MosaicCreator",
    "MosaicDetector",
    "MosaicExtension",
    "comfy_entrypoint",
]
