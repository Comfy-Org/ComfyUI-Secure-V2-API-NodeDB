"""Secure Nodes V2 wrapper for comfyui-image-blender."""

from __future__ import annotations

import torch

from comfy_api.latest import ComfyExtension, io

from .blend_modes.index import blend_functions
from .blend_modes_enum import BlendModes


MAX_BATCH = 256
MAX_DIMENSION = 16_384
MAX_PIXELS = 67_108_864


def _validate_image_bounds(image: torch.Tensor, name: str) -> None:
    if not isinstance(image, torch.Tensor):
        raise TypeError(f"{name} must be a tensor")
    if image.dim() != 4:
        raise ValueError(f"{name} must use BHWC layout")
    batch, height, width, _channels = image.shape
    if batch < 1 or batch > MAX_BATCH:
        raise ValueError(f"{name} batch exceeds the {MAX_BATCH}-image limit")
    if height < 1 or width < 1 or height > MAX_DIMENSION or width > MAX_DIMENSION:
        raise ValueError(f"{name} dimensions exceed the {MAX_DIMENSION}-pixel limit")
    if batch * height * width > MAX_PIXELS:
        raise ValueError(f"{name} exceeds the {MAX_PIXELS}-pixel limit")


class ImageBlender(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ImageBlender",
            display_name="ImageBlender",
            category="ImageBlender",
            inputs=[
                io.Image.Input("base_image"),
                io.Image.Input("blend_image"),
                io.Float.Input(
                    "strength", default=1.0, min=0.0, max=1.0, step=0.01,
                ),
                io.Combo.Input(
                    "blend_mode",
                    options=[mode.value for mode in BlendModes],
                    default=BlendModes.MIX_NORMAL.value,
                ),
                io.Mask.Input("mask", optional=True),
            ],
            outputs=[io.Image.Output()],
        )

    @classmethod
    def execute(
        cls,
        base_image: torch.Tensor,
        blend_image: torch.Tensor,
        strength: float,
        blend_mode: str,
        mask: torch.Tensor | None = None,
    ) -> io.NodeOutput:
        assert base_image.shape == blend_image.shape, (
            "Base and blend images must have the same shape"
        )
        assert base_image.shape[-1] == 3, "Input images must have 3 channels (RGB)"
        _validate_image_bounds(base_image, "base_image")
        _validate_image_bounds(blend_image, "blend_image")

        blend_function = blend_functions.get(BlendModes(blend_mode), lambda x, y: x)
        result = blend_function(base_image, blend_image)

        if mask is not None:
            if mask.dim() == 3:
                mask = mask.unsqueeze(-1).expand(
                    -1, -1, -1, base_image.shape[-1],
                )
            if mask.size() == base_image.size():
                result = result * mask + base_image * (1 - mask)

        result = result * strength + base_image * (1 - strength)
        return io.NodeOutput(torch.clamp(result, 0, 1))


NODE_CLASS_MAPPINGS = {"ImageBlender": ImageBlender}


class ImageBlenderExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [ImageBlender]


async def comfy_entrypoint() -> ImageBlenderExtension:
    return ImageBlenderExtension()
