"""Secure raw-compute bindings for the five Images Grid nodes."""
from __future__ import annotations

from typing import Any, Callable

import torch

from comfy_api.latest import io, sdk

from .grid import (
    annotation_descriptor,
    annotation_from_descriptor,
    create_images_grid_by_columns,
    create_images_grid_by_rows,
    pillow_to_tensor,
    tensor_to_pillow,
)


CATEGORY = "ImagesGrid"
GRID_ANNOTATION = io.Custom("GRID_ANNOTATION")
_MAX_BATCH = 4_096
_MAX_AXIS = 16_384
_MAX_OUTPUT_BYTES = 512 * 1024 * 1024


def _validate_image_batch(images: torch.Tensor) -> None:
    if not isinstance(images, torch.Tensor) or images.ndim != 4:
        raise TypeError("images must be a four-dimensional BHWC tensor")
    batch, height, width, channels = images.shape
    if (
        not 1 <= batch <= _MAX_BATCH
        or not 1 <= height <= _MAX_AXIS
        or not 1 <= width <= _MAX_AXIS
        or channels not in (1, 3, 4)
    ):
        raise ValueError("images have an unsupported batch or spatial shape")


def _bounded_grid_shape(
    images: torch.Tensor, gap: int, maximum: int, *, by_columns: bool,
) -> None:
    batch, height, width, _ = images.shape
    if not 0 <= gap <= _MAX_AXIS or not 1 <= maximum <= _MAX_BATCH:
        raise ValueError("grid gap or row/column count is outside its bound")
    columns = maximum if by_columns else (batch + maximum - 1) // maximum
    rows = (batch + maximum - 1) // maximum if by_columns else maximum
    output_width = width * columns + (columns - 1) * gap
    output_height = height * rows + (rows - 1) * gap
    if output_width > _MAX_AXIS or output_height > _MAX_AXIS:
        raise ValueError("grid output exceeds the bounded spatial axes")
    if output_width * output_height * 3 * 4 > _MAX_OUTPUT_BYTES:
        raise ValueError("grid output exceeds the bounded in-memory size")


class LatentCombine(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="LatentCombine",
            category=CATEGORY,
            inputs=[
                io.Latent.Input("latent_1"),
                io.Latent.Input("latent_2"),
            ],
            outputs=[io.Latent.Output("output_0", display_name="LATENT")],
        )

    @classmethod
    async def execute(
        cls, latent_1: sdk.LatentRef, latent_2: sdk.LatentRef,
    ) -> io.NodeOutput:
        first = await latent_1.value()
        second = await latent_2.value()
        samples = torch.cat((first["samples"], second["samples"]), 0)
        if samples.shape[0] > _MAX_BATCH or samples.numel() * samples.element_size() > _MAX_OUTPUT_BYTES:
            raise ValueError("combined latent exceeds the bounded output size")
        return io.NodeOutput(await sdk.LatentRef.from_value({"samples": samples}))


class ImageCombine(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ImageCombine",
            category=CATEGORY,
            inputs=[io.Image.Input("image_1"), io.Image.Input("image_2")],
            outputs=[io.Image.Output("output_0", display_name="IMAGE")],
        )

    @classmethod
    async def execute(
        cls, image_1: sdk.ImageRef, image_2: sdk.ImageRef,
    ) -> io.NodeOutput:
        first = await image_1.raw()
        second = await image_2.raw()
        _validate_image_batch(first)
        _validate_image_batch(second)
        result = torch.cat((first, second), 0)
        if result.shape[0] > _MAX_BATCH or result.numel() * result.element_size() > _MAX_OUTPUT_BYTES:
            raise ValueError("combined image exceeds the bounded output size")
        return io.NodeOutput(await sdk.ImageRef._from_raw(result))


class GridAnnotation(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="GridAnnotation",
            category=CATEGORY,
            inputs=[
                io.String.Input("column_texts", multiline=True),
                io.String.Input("row_texts", multiline=True),
                io.Int.Input("font_size", default=50, min=1, max=512, step=1),
            ],
            outputs=[GRID_ANNOTATION.Output("output_0", display_name="GRID_ANNOTATION")],
        )

    @classmethod
    async def execute(
        cls, column_texts: str, row_texts: str, font_size: int,
    ) -> io.NodeOutput:
        if len(column_texts) + len(row_texts) > 1_048_576:
            raise ValueError("annotation text exceeds the bounded size")
        return io.NodeOutput(
            annotation_descriptor(column_texts, row_texts, int(font_size)),
        )


class _ImagesGridBase(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    async def _execute_grid(
        cls,
        function: Callable[..., Any],
        images: sdk.ImageRef,
        gap: int,
        maximum: int,
        annotation: dict[str, Any] | None,
        *,
        by_columns: bool,
    ) -> io.NodeOutput:
        raw = await images.raw()
        _validate_image_batch(raw)
        _bounded_grid_shape(raw, int(gap), int(maximum), by_columns=by_columns)
        parsed = None if annotation is None else annotation_from_descriptor(annotation)
        pillow_images = [tensor_to_pillow(image) for image in raw]
        kwargs = {
            "images": pillow_images,
            "gap": int(gap),
            "annotation": parsed,
            "max_columns" if by_columns else "max_rows": int(maximum),
        }
        result = pillow_to_tensor(function(**kwargs))
        if result.numel() * result.element_size() > _MAX_OUTPUT_BYTES:
            raise ValueError("grid output exceeds the bounded in-memory size")
        return io.NodeOutput(await sdk.ImageRef._from_raw(result))


class ImagesGridByColumns(_ImagesGridBase):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ImagesGridByColumns",
            category=CATEGORY,
            inputs=[
                io.Image.Input("images"),
                io.Int.Input("gap", default=0, min=0, max=_MAX_AXIS, step=1),
                io.Int.Input("max_columns", default=1, min=1, max=_MAX_BATCH, step=1),
                GRID_ANNOTATION.Input("annotation", optional=True),
            ],
            outputs=[io.Image.Output("output_0", display_name="IMAGE")],
        )

    @classmethod
    async def execute(
        cls,
        images: sdk.ImageRef,
        gap: int,
        max_columns: int,
        annotation: dict[str, Any] | None = None,
    ) -> io.NodeOutput:
        return await cls._execute_grid(
            create_images_grid_by_columns,
            images,
            gap,
            max_columns,
            annotation,
            by_columns=True,
        )


class ImagesGridByRows(_ImagesGridBase):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ImagesGridByRows",
            category=CATEGORY,
            inputs=[
                io.Image.Input("images"),
                io.Int.Input("gap", default=0, min=0, max=_MAX_AXIS, step=1),
                io.Int.Input("max_rows", default=1, min=1, max=_MAX_BATCH, step=1),
                GRID_ANNOTATION.Input("annotation", optional=True),
            ],
            outputs=[io.Image.Output("output_0", display_name="IMAGE")],
        )

    @classmethod
    async def execute(
        cls,
        images: sdk.ImageRef,
        gap: int,
        max_rows: int,
        annotation: dict[str, Any] | None = None,
    ) -> io.NodeOutput:
        return await cls._execute_grid(
            create_images_grid_by_rows,
            images,
            gap,
            max_rows,
            annotation,
            by_columns=False,
        )


NODE_CLASS_MAPPINGS = {
    "LatentCombine": LatentCombine,
    "ImagesGridByColumns": ImagesGridByColumns,
    "ImagesGridByRows": ImagesGridByRows,
    "ImageCombine": ImageCombine,
    "GridAnnotation": GridAnnotation,
}

NODE_DISPLAY_NAME_MAPPINGS: dict[str, str] = {}


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
