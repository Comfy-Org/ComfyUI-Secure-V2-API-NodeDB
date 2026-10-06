"""Bounded, pack-local Secure Nodes V2 image grid operations."""

from __future__ import annotations

import torch
from comfy_api.latest import ComfyExtension, io

from .even_algorithm import EvenImageResizer as _LegacyEvenImageResizer
from .grid_algorithm import GridImageSplitter as _LegacyGridImageSplitter

MAX_BATCH = 64
MAX_DIMENSION = 8192
MAX_INPUT_PIXELS = 16_777_216
MAX_OUTPUT_PIXELS = 67_108_864
SPLIT_METHODS = ["uniform", "edge_detection"]


def _image(image: torch.Tensor) -> torch.Tensor:
    if not isinstance(image, torch.Tensor):
        raise TypeError("image must be a tensor")
    if image.ndim == 3:
        image = image.unsqueeze(0)
    if image.ndim != 4 or image.shape[-1] != 3:
        raise ValueError("image must use BHWC or HWC RGB layout")
    batch, height, width, _channels = image.shape
    if not 1 <= batch <= MAX_BATCH:
        raise ValueError("image batch exceeds the supported bounds")
    if not 2 <= height <= MAX_DIMENSION or not 2 <= width <= MAX_DIMENSION:
        raise ValueError("image dimensions exceed the supported bounds")
    if batch * height * width > MAX_INPUT_PIXELS:
        raise ValueError("image exceeds the input pixel bound")
    if not image.dtype.is_floating_point:
        raise TypeError("image must use a floating-point dtype")
    if not torch.isfinite(image).all():
        raise ValueError("image must contain finite values")
    return image


def _grid_count(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if not 1 <= value <= 10:
        raise ValueError(f"{name} must be in [1, 10]")
    return value


class GridImageSplitter(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="GridImageSplitter",
            category="image/processing",
            inputs=[
                io.Image.Input("image"),
                io.Int.Input("rows", default=2, min=1, max=10),
                io.Int.Input("cols", default=3, min=1, max=10),
                io.Combo.Input("row_split_method", options=SPLIT_METHODS),
                io.Combo.Input("col_split_method", options=SPLIT_METHODS),
            ],
            outputs=[io.Image.Output(), io.Image.Output()],
        )

    @classmethod
    def execute(
        cls,
        image: torch.Tensor,
        rows: int,
        cols: int,
        row_split_method: str,
        col_split_method: str,
    ) -> io.NodeOutput:
        image = _image(image)
        rows = _grid_count("rows", rows)
        cols = _grid_count("cols", cols)
        for name, method in (
            ("row_split_method", row_split_method),
            ("col_split_method", col_split_method),
        ):
            if not isinstance(method, str) or method not in SPLIT_METHODS:
                raise ValueError(f"{name} must be a supported split method")
        height, width = image.shape[1:3]
        if height < rows * 2 or width < cols * 2:
            raise ValueError("image is too small for this grid")
        if rows * cols * height * width > MAX_OUTPUT_PIXELS:
            raise ValueError("grid exceeds the conservative output pixel bound")
        outputs = _LegacyGridImageSplitter().split_image(
            image, rows, cols, row_split_method, col_split_method
        )
        return io.NodeOutput(*outputs)


class EvenImageResizer(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="EvenImageResizer",
            category="image/processing",
            inputs=[io.Image.Input("image")],
            outputs=[io.Image.Output()],
        )

    @classmethod
    def execute(cls, image: torch.Tensor) -> io.NodeOutput:
        return io.NodeOutput(*_LegacyEvenImageResizer().resize_to_even(_image(image)))


NODE_CLASS_MAPPINGS = {
    "GridImageSplitter": GridImageSplitter,
    "EvenImageResizer": EvenImageResizer,
}


class AutoSplitGridExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [GridImageSplitter, EvenImageResizer]


async def comfy_entrypoint() -> AutoSplitGridExtension:
    return AutoSplitGridExtension()
