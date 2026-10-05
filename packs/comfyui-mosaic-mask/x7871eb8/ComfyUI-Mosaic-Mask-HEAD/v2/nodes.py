"""Secure Nodes V2 implementation of ComfyUI-Mosaic-Mask."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import torch
from comfy_api.latest import ComfyExtension, io

GRID_DIR = Path(__file__).with_name("grids")
TEMPLATE_SIZES = range(5, 21)
MAX_BATCH = 64
MAX_DIMENSION = 8_192
MAX_CHANNELS = 16
MAX_PIXELS = 33_554_432


def _load_templates() -> tuple[tuple[int, np.ndarray], ...]:
    templates = []
    for size in TEMPLATE_SIZES:
        path = GRID_DIR / f"pattern{size}x{size}.png"
        template = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if template is None:
            raise FileNotFoundError(f"Unable to load mosaic template: {path}")
        templates.append((size, template))
    return tuple(templates)


TEMPLATES = _load_templates()


def _bounded_int(name: str, value: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be in [{minimum}, {maximum}]")
    return value


def _bounded_float(name: str, value: float, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    value = float(value)
    if not np.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be finite and in [{minimum}, {maximum}]")
    return value


def _validate_image(image: torch.Tensor) -> torch.Tensor:
    if not isinstance(image, torch.Tensor):
        raise TypeError("MosaicMask expected an IMAGE tensor")
    if image.ndim != 4 or image.shape[-1] < 3:
        raise ValueError(
            "Expected IMAGE with shape [batch, height, width, channels], "
            f"got {tuple(image.shape)}"
        )
    batch, height, width, channels = (int(value) for value in image.shape)
    if not 1 <= batch <= MAX_BATCH:
        raise ValueError(f"IMAGE batch must be in [1, {MAX_BATCH}]")
    if not 1 <= height <= MAX_DIMENSION or not 1 <= width <= MAX_DIMENSION:
        raise ValueError(f"IMAGE dimensions must be in [1, {MAX_DIMENSION}]")
    if channels > MAX_CHANNELS:
        raise ValueError(f"IMAGE channels must be in [3, {MAX_CHANNELS}]")
    if batch * height * width > MAX_PIXELS:
        raise ValueError("IMAGE exceeds the pixel limit")
    if not image.dtype.is_floating_point:
        raise TypeError("IMAGE must use a floating-point dtype")
    return image


def keep_largest_components(mask: np.ndarray, top_n: int = 1) -> np.ndarray:
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask, connectivity=8
    )
    component_count = num_labels - 1
    if component_count <= top_n:
        return mask

    areas = stats[1:, cv2.CC_STAT_AREA]
    kept_labels = np.argpartition(areas, -top_n)[-top_n:] + 1
    return np.isin(labels, kept_labels).astype(np.uint8)


def detect_mosaic(
    image: np.ndarray,
    top_n: int,
    kernel_size: int,
    threshold: float,
    min_grid_size: int,
    max_grid_size: int,
) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    gray = cv2.Canny(gray, 10, 20)
    gray = cv2.GaussianBlur(255 - gray, (3, 3), 0)

    height, width = gray.shape
    coverage = np.zeros((height + 1, width + 1), dtype=np.int32)
    for size, template in TEMPLATES:
        if not min_grid_size <= size <= max_grid_size:
            continue
        template_height, template_width = template.shape
        if template_height > height or template_width > width:
            continue

        matches = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
        ys, xs = np.where(matches >= threshold)
        if not len(xs):
            continue

        np.add.at(coverage, (ys, xs), 1)
        np.add.at(coverage, (ys + template_height, xs), -1)
        np.add.at(coverage, (ys, xs + template_width), -1)
        np.add.at(coverage, (ys + template_height, xs + template_width), 1)

    mask = (coverage.cumsum(0).cumsum(1)[:-1, :-1] > 0).astype(np.uint8)
    if kernel_size > 1:
        mask = cv2.dilate(
            mask,
            np.ones((kernel_size, kernel_size), np.uint8),
            iterations=1,
        )
    return keep_largest_components(mask, top_n)


class MosaicMask(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="MosaicMask",
            display_name="MosaicMask",
            category="Mosaic Masking",
            inputs=[
                io.Image.Input("image"),
                io.Int.Input("top_n", default=1, min=1, max=10, step=1),
                io.Int.Input("kernel_size", default=3, min=0, max=100, step=1),
                io.Float.Input(
                    "threshold",
                    default=0.3,
                    min=0.0,
                    max=1.0,
                    step=0.01,
                    optional=True,
                ),
                io.Int.Input(
                    "min_grid_size",
                    default=10,
                    min=5,
                    max=20,
                    step=1,
                    optional=True,
                ),
                io.Int.Input(
                    "max_grid_size",
                    default=20,
                    min=5,
                    max=20,
                    step=1,
                    optional=True,
                ),
            ],
            outputs=[io.Mask.Output("mosaic_mask")],
        )

    @classmethod
    def execute(
        cls,
        image: torch.Tensor,
        top_n: int,
        kernel_size: int,
        threshold: float = 0.3,
        min_grid_size: int = 10,
        max_grid_size: int = 20,
    ) -> io.NodeOutput:
        image = _validate_image(image)
        top_n = _bounded_int("top_n", top_n, 1, 10)
        kernel_size = _bounded_int("kernel_size", kernel_size, 0, 100)
        threshold = _bounded_float("threshold", threshold, 0.0, 1.0)
        min_grid_size = _bounded_int("min_grid_size", min_grid_size, 5, 20)
        max_grid_size = _bounded_int("max_grid_size", max_grid_size, 5, 20)
        if min_grid_size > max_grid_size:
            raise ValueError("min_grid_size cannot exceed max_grid_size")

        images = image.detach().to(device="cpu", dtype=torch.float32).numpy()
        images = np.clip(images[..., :3] * 255.0, 0, 255).astype(np.uint8)
        masks = np.stack(
            [
                detect_mosaic(
                    image_np,
                    top_n,
                    kernel_size,
                    threshold,
                    min_grid_size,
                    max_grid_size,
                )
                for image_np in images
            ]
        )
        output = torch.from_numpy(masks).to(device=image.device, dtype=torch.float32)
        return io.NodeOutput(output)


NODE_CLASS_MAPPINGS = {"MosaicMask": MosaicMask}
NODE_DISPLAY_NAME_MAPPINGS = {"MosaicMask": "MosaicMask"}


class MosaicMaskExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [MosaicMask]


async def comfy_entrypoint() -> MosaicMaskExtension:
    return MosaicMaskExtension()


__all__ = [
    "MAX_BATCH",
    "MAX_CHANNELS",
    "MAX_DIMENSION",
    "MAX_PIXELS",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "TEMPLATES",
    "MosaicMask",
    "MosaicMaskExtension",
    "comfy_entrypoint",
    "detect_mosaic",
    "keep_largest_components",
]
