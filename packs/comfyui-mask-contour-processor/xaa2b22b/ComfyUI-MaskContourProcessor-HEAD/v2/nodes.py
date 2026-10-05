"""Secure Nodes V2 wrapper for ComfyUI-MaskContourProcessor."""

from __future__ import annotations

import math

import numpy as np
import torch
from comfy_api.latest import ComfyExtension, io
from PIL import Image, ImageFilter

from .algorithm import MaskContourProcessor as _LegacyMaskContourProcessor

MAX_BATCH = 64
MAX_DIMENSION = 8_192
MAX_PIXELS = 16_777_216
_GEOMETRY_EPSILON = 1e-9


def _bounded_float(name: str, value: float, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise ValueError(f"{name} must be finite and in [{minimum}, {maximum}]")
    return result


def _bounded_int(name: str, value: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be in [{minimum}, {maximum}]")
    return value


def _mask(value: torch.Tensor) -> torch.Tensor:
    if not isinstance(value, torch.Tensor):
        raise TypeError("mask must be a tensor")
    if value.ndim != 3:
        raise ValueError("mask must use BHW layout")
    batch, height, width = (int(item) for item in value.shape)
    if not 1 <= batch <= MAX_BATCH:
        raise ValueError(f"mask batch must be in [1, {MAX_BATCH}]")
    if not 1 <= height <= MAX_DIMENSION or not 1 <= width <= MAX_DIMENSION:
        raise ValueError(f"mask dimensions must be in [1, {MAX_DIMENSION}]")
    if batch * height * width > MAX_PIXELS:
        raise ValueError(f"mask exceeds the {MAX_PIXELS}-pixel limit")
    if not value.dtype.is_floating_point:
        raise TypeError("mask must use a floating-point dtype")
    if not torch.isfinite(value).all():
        raise ValueError("mask must contain only finite values")
    return value


def _blur_original(mask: np.ndarray, blur_amount: float) -> torch.Tensor:
    """Return the legacy final blur without attempting undefined contour geometry."""
    image = Image.fromarray(
        (np.clip(mask, 0, 1) * 255).astype(np.uint8), mode="L"
    ).filter(ImageFilter.GaussianBlur(blur_amount))
    return torch.from_numpy(np.array(image) / 255.0)


def _supports_legacy_geometry(
    processor: _LegacyMaskContourProcessor,
    mask: np.ndarray,
    line_count: int,
) -> bool:
    """Reject contours that make the pinned implementation divide by zero."""
    center = processor.calculate_mask_centroid(mask)
    points = processor.detect_edge_points(mask, center)
    if not points:
        return False

    lengths = [
        math.hypot(
            points[(index + 1) % len(points)][0] - point[0],
            points[(index + 1) % len(points)][1] - point[1],
        )
        for index, point in enumerate(points)
    ]
    if sum(lengths) <= _GEOMETRY_EPSILON or any(
        length <= _GEOMETRY_EPSILON for length in lengths
    ):
        return False

    selected = processor.redistribute_points(points, line_count)
    directions: list[tuple[float, float]] = []
    for point in selected:
        dx = point[0] - center[0]
        dy = point[1] - center[1]
        length = math.hypot(dx, dy)
        if length <= _GEOMETRY_EPSILON:
            return False
        directions.append((dx / length, dy / length))

    for index, direction in enumerate(directions):
        following = directions[(index + 1) % len(directions)]
        if (
            math.hypot(direction[0] + following[0], direction[1] + following[1])
            <= _GEOMETRY_EPSILON
        ):
            return False
    return True


class MaskContourProcessor(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="MaskContourProcessor",
            display_name="Mask Contour Processor",
            category="mask",
            inputs=[
                io.Mask.Input("mask"),
                io.Float.Input("line_length", default=0.5, min=0.0, max=3.0, step=0.01),
                io.Int.Input("line_count", default=16, min=1, max=40, step=1),
                io.Float.Input(
                    "line_width", default=0.015, min=0.0, max=0.1, step=0.001
                ),
                io.Float.Input("blur_amount", default=2.0, min=0.0, max=50.0, step=0.1),
            ],
            outputs=[io.Mask.Output()],
        )

    @classmethod
    def execute(
        cls,
        mask: torch.Tensor,
        line_length: float,
        line_count: int,
        line_width: float,
        blur_amount: float,
    ) -> io.NodeOutput:
        mask = _mask(mask)
        line_length = _bounded_float("line_length", line_length, 0.0, 3.0)
        line_count = _bounded_int("line_count", line_count, 1, 40)
        line_width = _bounded_float("line_width", line_width, 0.0, 0.1)
        blur_amount = _bounded_float("blur_amount", blur_amount, 0.0, 50.0)

        processor = _LegacyMaskContourProcessor()
        outputs = []
        for item in mask:
            array = item.detach().cpu().numpy()
            if _supports_legacy_geometry(processor, array, line_count):
                result = processor.process_mask(
                    item.unsqueeze(0),
                    line_length,
                    line_count,
                    line_width,
                    blur_amount,
                )[0][0]
            else:
                result = _blur_original(array, blur_amount)
            outputs.append(result)
        return io.NodeOutput(torch.stack(outputs))


NODE_CLASS_MAPPINGS = {"MaskContourProcessor": MaskContourProcessor}
NODE_DISPLAY_NAME_MAPPINGS = {
    "MaskContourProcessor": "Mask Contour Processor",
}


class MaskContourProcessorExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [MaskContourProcessor]


async def comfy_entrypoint() -> MaskContourProcessorExtension:
    return MaskContourProcessorExtension()


__all__ = [
    "MAX_BATCH",
    "MAX_DIMENSION",
    "MAX_PIXELS",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "MaskContourProcessor",
    "MaskContourProcessorExtension",
    "comfy_entrypoint",
]
