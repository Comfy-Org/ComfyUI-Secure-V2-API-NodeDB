"""Bounded raw-compute wrapper for the pinned AutoTrimBG algorithm."""

from __future__ import annotations

import torch
from comfy_api.latest import ComfyExtension, io, sdk

from .algorithm import RonLayersTrimBgUltraV2 as _LegacyTrim

NODE_ID = "RonLayers/TrimBg: RonLayersTrimBgUltraV2"
MAX_DIMENSION = 8192
MAX_PIXELS = 16_777_216
MAX_MASK_BATCH = 64


def _inputs(image: torch.Tensor, mask: torch.Tensor, padding: int):
    if not isinstance(image, torch.Tensor):
        raise TypeError("image must be a tensor")
    if image.ndim != 4 or image.shape[0] != 1 or image.shape[-1] not in (3, 4):
        raise ValueError("image must be one BHWC RGB or RGBA image")
    height, width = image.shape[1:3]
    if not 2 <= height <= MAX_DIMENSION or not 2 <= width <= MAX_DIMENSION:
        raise ValueError("image dimensions exceed the supported bounds")
    if height * width > MAX_PIXELS:
        raise ValueError("image exceeds the pixel bound")
    if not image.dtype.is_floating_point:
        raise TypeError("image must use a floating-point dtype")
    if not torch.isfinite(image).all():
        raise ValueError("image must contain finite values")
    if not isinstance(mask, torch.Tensor):
        raise TypeError("mask must be a tensor")
    if mask.ndim == 2:
        mask = mask.unsqueeze(0)
    if mask.ndim != 3 or tuple(mask.shape[1:]) != (height, width):
        raise ValueError("mask must use HW or BHW layout matching the image")
    if not 1 <= mask.shape[0] <= MAX_MASK_BATCH:
        raise ValueError("mask batch exceeds the supported bounds")
    if mask.numel() > MAX_PIXELS:
        raise ValueError("mask exceeds the pixel bound")
    if not mask.dtype.is_floating_point:
        raise TypeError("mask must use a floating-point dtype")
    if not torch.isfinite(mask).all():
        raise ValueError("mask must contain finite values")
    if isinstance(padding, bool) or not isinstance(padding, int):
        raise TypeError("padding must be an integer")
    if not 0 <= padding <= 1000:
        raise ValueError("padding must be in [0, 1000]")
    return image, mask, padding


class RonLayersTrimBgUltraV2(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id=NODE_ID,
            display_name=NODE_ID,
            category="RonLayers/TrimBg",
            inputs=[
                io.Image.Input("image"),
                io.Mask.Input("mask"),
                io.Int.Input("padding", default=0, min=0, max=1000, step=1),
            ],
            outputs=[
                io.Image.Output("croped_image"),
                io.Mask.Output("croped_mask"),
                io.Custom("BOX").Output("crop_box"),
                io.Image.Output("box_preview"),
            ],
        )

    @classmethod
    async def execute(
        cls, image: torch.Tensor, mask: torch.Tensor, padding: int
    ) -> io.NodeOutput:
        image, mask, padding = _inputs(image, mask, padding)
        cropped_image, cropped_mask, box, preview = _LegacyTrim().trim_and_crop_by_mask(
            image, mask, padding
        )
        if box is not None:
            box = await sdk.ValueRef.from_value(box)
        return io.NodeOutput(cropped_image, cropped_mask, box, preview)


NODE_CLASS_MAPPINGS = {NODE_ID: RonLayersTrimBgUltraV2}
NODE_DISPLAY_NAME_MAPPINGS = {NODE_ID: NODE_ID}


class AutoTrimExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [RonLayersTrimBgUltraV2]


async def comfy_entrypoint() -> AutoTrimExtension:
    return AutoTrimExtension()
