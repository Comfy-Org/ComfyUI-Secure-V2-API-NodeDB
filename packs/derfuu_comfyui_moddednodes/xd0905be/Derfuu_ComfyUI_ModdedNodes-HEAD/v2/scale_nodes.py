"""Pack-side image and latent scaling in the permissioned raw tier."""
from __future__ import annotations

import math
import sys

import torch

from comfy_api.latest import io, sdk

from ._image_ops import common_upscale


TREE_MAIN = "Derfuu_Nodes"
TREE_IMAGES = TREE_MAIN + "/Modded nodes/Image"
TREE_LATENTS = TREE_MAIN + "/Modded nodes/Latent"
SCALE_METHODS = [
    "nearest-exact",
    "bilinear",
    "bicubic",
    "bislerp",
    "area",
    "lanczos",
]
CROP_METHODS = ["disabled", "center"]
SIDES = ["Longest", "Shortest", "Width", "Height"]


def _float(name: str, *, default=1, minimum=None):
    limit = sys.float_info.max
    return io.Float.Input(
        name,
        default=default,
        min=-limit if minimum is None else minimum,
        max=limit,
        step=0.01,
        force_input=False,
    )


def _int(name: str, *, default=1):
    return io.Int.Input(
        name,
        default=default,
        min=-sys.maxsize,
        max=sys.maxsize,
        step=1,
        force_input=False,
    )


def _ref_input(kind, name: str):
    return kind.Input(name, extra_dict={"forceInput": False})


def _combo(name: str, options: list):
    return io.Combo.Input(
        name, options=options, extra_dict={"forceInput": False}
    )


def _target_for_side(
    source_width: int,
    source_height: int,
    side_length: int,
    side: str,
) -> tuple[float, float]:
    def determine(selected: str) -> tuple[float, float]:
        if selected == "Width":
            return side_length, (source_height / source_width) * side_length
        if selected == "Height":
            return (source_width / source_height) * side_length, side_length
        return 0, 0

    width = source_width
    height = source_height
    if side == "Longest":
        width, height = determine("Width" if width > height else "Height")
    elif side == "Shortest":
        width, height = determine("Width" if width < height else "Height")
    else:
        width, height = determine(side)
    return width, height


def _validate_resize(samples: torch.Tensor, width: int, height: int) -> None:
    if not isinstance(samples, torch.Tensor) or samples.ndim < 4:
        raise TypeError("scale input must contain a tensor with spatial axes")
    if not 1 <= width <= 16_384 or not 1 <= height <= 16_384:
        raise ValueError("scale dimensions must be in [1, 16384]")
    plane = max(1, int(samples.shape[-2]) * int(samples.shape[-1]))
    if samples.numel() // plane * width * height > 67_108_864:
        raise ValueError("scale output exceeds the bounded tensor size")


class ImageScale_Ratio(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_Image_scale_by_ratio",
            display_name="Image scale by ratio",
            category=TREE_IMAGES,
            inputs=[
                _ref_input(io.Image, "image"),
                _float("upscale_by"),
                _combo("upscale_method", SCALE_METHODS),
                _combo("crop", CROP_METHODS),
            ],
            outputs=[io.Image.Output("output_0", display_name="IMAGE")],
        )

    @classmethod
    async def execute(
        cls,
        image: sdk.ImageRef,
        upscale_method,
        upscale_by,
        crop,
    ):
        value = await image.raw()
        width = math.ceil(int(value.shape[-2]) * upscale_by)
        height = math.ceil(int(value.shape[-3]) * upscale_by)
        samples = value.movedim(-1, 1)
        _validate_resize(samples, width, height)
        output = common_upscale(
            samples, width, height, upscale_method, crop
        ).movedim(1, -1)
        return io.NodeOutput(await sdk.ImageRef._from_raw(output))


class ImageScale_Side(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_Image_scale_to_side",
            display_name="Image scale to side",
            category=TREE_IMAGES,
            inputs=[
                _ref_input(io.Image, "image"),
                _int("side_length"),
                _combo("side", SIDES),
                _combo("upscale_method", SCALE_METHODS),
                _combo("crop", CROP_METHODS),
            ],
            outputs=[io.Image.Output("output_0", display_name="IMAGE")],
        )

    @classmethod
    async def execute(
        cls,
        image: sdk.ImageRef,
        upscale_method,
        side_length,
        side,
        crop,
    ):
        value = await image.raw()
        source_width = int(value.shape[-2])
        source_height = int(value.shape[-3])
        width, height = _target_for_side(
            source_width, source_height, side_length, side
        )
        width = math.ceil(width)
        height = math.ceil(height)
        samples = value.movedim(-1, 1)
        _validate_resize(samples, width, height)
        output = common_upscale(
            samples, width, height, upscale_method, crop
        ).movedim(1, -1)
        return io.NodeOutput(await sdk.ImageRef._from_raw(output))


class LatentScale_Ratio(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_Latent_Scale_by_ratio",
            display_name="Latent Scale by ratio",
            category=TREE_LATENTS,
            inputs=[
                _ref_input(io.Latent, "latent"),
                _float("modifier", minimum=0),
                _combo("scale_method", SCALE_METHODS),
                _combo("crop", CROP_METHODS),
            ],
            outputs=[io.Latent.Output("output_0", display_name="LATENT")],
        )

    @classmethod
    async def execute(
        cls,
        latent: sdk.LatentRef,
        scale_method,
        crop,
        modifier,
    ):
        value = await latent.value()
        samples = value["samples"]
        source_width = int(samples.shape[-1])
        source_height = int(samples.shape[-2])
        scaled_width = source_width * modifier
        width = int(scaled_width + scaled_width % 8)
        scaled_height = source_height * modifier
        height = int(scaled_height + scaled_height % 8)
        _validate_resize(samples, width, height)
        output = dict(value)
        output["samples"] = common_upscale(
            samples, width, height, scale_method, crop
        )
        return io.NodeOutput(await sdk.LatentRef.from_value(output))


class LatentScale_Side(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_Latent_Scale_to_side",
            display_name="Latent Scale to side",
            category=TREE_LATENTS,
            inputs=[
                _ref_input(io.Latent, "latent"),
                _int("side_length", default=512),
                _combo("side", SIDES),
                _combo("scale_method", SCALE_METHODS),
                _combo("crop", CROP_METHODS),
            ],
            outputs=[io.Latent.Output("output_0", display_name="LATENT")],
        )

    @classmethod
    async def execute(
        cls,
        latent: sdk.LatentRef,
        side_length,
        side,
        scale_method,
        crop,
    ):
        value = await latent.value()
        samples = value["samples"]
        source_width = int(samples.shape[-1])
        source_height = int(samples.shape[-2])
        width, height = _target_for_side(
            source_width, source_height, side_length, side
        )
        width = math.ceil(width) // 8
        height = math.ceil(height) // 8
        _validate_resize(samples, width, height)
        output = dict(value)
        output["samples"] = common_upscale(
            samples, width, height, scale_method, crop
        )
        return io.NodeOutput(await sdk.LatentRef.from_value(output))


__all__ = [
    "ImageScale_Ratio",
    "ImageScale_Side",
    "LatentScale_Ratio",
    "LatentScale_Side",
]
