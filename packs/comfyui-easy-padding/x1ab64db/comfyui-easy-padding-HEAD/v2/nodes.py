"""Bounded pack-owned Pillow padding; no ambient host authority."""

from __future__ import annotations

import torch
from comfy_api.latest import ComfyExtension, io

from .algorithm import AddPadding as _LegacyPadding

MAX_BATCH = 64
MAX_DIMENSION = 8192
MAX_PIXELS = 16_777_216


def _validate(image, left, top, right, bottom, color, transparent):
    if not isinstance(image, torch.Tensor):
        raise TypeError("image must be a tensor")
    if image.ndim != 4 or image.shape[-1] not in (3, 4):
        raise ValueError("image must be BHWC RGB or RGBA")
    batch, height, width, _channels = image.shape
    if not 1 <= batch <= MAX_BATCH:
        raise ValueError("image batch is outside the secure bound")
    if not 2 <= height <= MAX_DIMENSION or not 2 <= width <= MAX_DIMENSION:
        raise ValueError("image dimensions are outside the secure bound")
    if batch * height * width > MAX_PIXELS:
        raise ValueError("input image exceeds the secure pixel bound")
    if not image.dtype.is_floating_point:
        raise TypeError("image must have floating dtype")
    if not torch.isfinite(image).all():
        raise ValueError("image must be finite")
    for name, value in zip(
        ("left", "top", "right", "bottom"), (left, top, right, bottom)
    ):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{name} must be an integer")
        if not 0 <= value <= 4096:
            raise ValueError(f"{name} must be in [0, 4096]")
    output_width, output_height = width + left + right, height + top + bottom
    if output_width > MAX_DIMENSION or output_height > MAX_DIMENSION:
        raise ValueError("padded image dimensions exceed the secure bound")
    if batch * output_height * output_width > MAX_PIXELS:
        raise ValueError("padded image exceeds the secure pixel bound")
    if not isinstance(color, str) or len(color) > 64:
        raise ValueError("color must be a bounded string")
    if not isinstance(transparent, bool):
        raise TypeError("transparent must be a boolean")


class AddPadding(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="comfyui-easy-padding",
            display_name="ComfyUI Easy Padding",
            category="ComfyUI Easy Padding",
            inputs=[
                io.Image.Input("image"),
                *[
                    io.Int.Input(name, default=0, step=1, min=0, max=4096)
                    for name in ("left", "top", "right", "bottom")
                ],
                io.String.Input("color", default="#ffffff"),
                io.Boolean.Input("transparent", default=False),
            ],
            outputs=[io.Image.Output(), io.Mask.Output()],
        )

    @classmethod
    def execute(cls, image, left, top, right, bottom, color, transparent):
        _validate(image, left, top, right, bottom, color, transparent)
        return io.NodeOutput(
            *_LegacyPadding().resize(
                image, left, top, right, bottom, color, transparent
            )
        )


NODE_CLASS_MAPPINGS = {"comfyui-easy-padding": AddPadding}
NODE_DISPLAY_NAME_MAPPINGS = {"comfyui-easy-padding": "ComfyUI Easy Padding"}


class EasyPaddingExtension(ComfyExtension):
    async def get_node_list(self):
        return [AddPadding]


async def comfy_entrypoint():
    return EasyPaddingExtension()
