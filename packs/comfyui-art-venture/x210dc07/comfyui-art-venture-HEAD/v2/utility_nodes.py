"""Secure Nodes V2: comfyui-art-venture's utility nodes, ported exactly (bodies from upstream 210dc072,
modules/utility_nodes.py and modules/utils.py).

Each class serves the original's frozen schema and computes what the original computes, in the guest:
- images and masks arrive as tensor refs and are materialized exactly (``raw()``);
- PIL work runs on the guest's CPU with the original's conversions (utils.py:177-190);
- core's bicubic upscale is torch's interpolate, which core's common_upscale calls for "bicubic" with crop
  disabled (comfy/utils.py:1120-1152).
Paths the port cannot take exactly are refused by name.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import torch
from PIL import Image, ImageFilter

from comfy_api.latest import io, sdk

from ._secure_runtime import schema_for

PREFIX = "comfyui-art-venture"


# --- modules/utils.py:177-190 -----------------------------------------------------------------------------------
def pil2numpy(image: Image.Image):
    return np.array(image).astype(np.float32) / 255.0


def numpy2pil(image: np.ndarray, mode=None):
    return Image.fromarray(np.clip(255.0 * image, 0, 255).astype(np.uint8), mode)


def pil2tensor(image: Image.Image):
    return torch.from_numpy(pil2numpy(image)).unsqueeze(0)


def tensor2pil(image: torch.Tensor, mode=None):
    return numpy2pil(image.cpu().numpy().squeeze(), mode=mode)


class _FrozenSchema:
    """Schema-less mixin (not a node class): each node serves the original's frozen schema for its NODE_ID."""
    NODE_ID = ""

    @classmethod
    def define_schema(cls):
        return schema_for(cls.NODE_ID)


class StringToIntV2(_FrozenSchema, io.ComfyNode):
    NODE_ID = "StringToInt"
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    async def execute(cls, string: str = "0") -> io.NodeOutput:
        return io.NodeOutput(int(string))


class BooleanPrimitiveV2(_FrozenSchema, io.ComfyNode):
    NODE_ID = "BooleanPrimitive"
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    async def execute(cls, value: bool = False, reverse: bool = False) -> io.NodeOutput:
        if reverse:
            value = not value
        return io.NodeOutput(value, str(value))


class SeedSelectorV2(_FrozenSchema, io.ComfyNode):
    NODE_ID = "SeedSelector"
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    async def execute(cls, mode: bool = True, seed: int = 0, fixed_seed: int = 0) -> io.NodeOutput:
        return io.NodeOutput(fixed_seed if not mode else seed)


def sdxl_aspect_ratio(aspect_ratio):
    """utility_nodes.py:684-714 (UtilSDXLAspectRatioSelector.get_aspect_ratio)."""
    width, height = 1024, 1024

    if aspect_ratio == "1:1":
        width, height = 1024, 1024
    elif aspect_ratio == "2:3":
        width, height = 832, 1216
    elif aspect_ratio == "3:4":
        width, height = 896, 1152
    elif aspect_ratio == "5:8":
        width, height = 768, 1216
    elif aspect_ratio == "9:16":
        width, height = 768, 1344
    elif aspect_ratio == "9:19":
        width, height = 704, 1472
    elif aspect_ratio == "9:21":
        width, height = 640, 1536
    elif aspect_ratio == "3:2":
        width, height = 1216, 832
    elif aspect_ratio == "4:3":
        width, height = 1152, 896
    elif aspect_ratio == "8:5":
        width, height = 1216, 768
    elif aspect_ratio == "16:9":
        width, height = 1344, 768
    elif aspect_ratio == "19:9":
        width, height = 1472, 704
    elif aspect_ratio == "21:9":
        width, height = 1536, 640

    return (aspect_ratio, width, height)


class SDXLAspectRatioSelectorV2(_FrozenSchema, io.ComfyNode):
    NODE_ID = "SDXLAspectRatioSelector"
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    async def execute(cls, aspect_ratio: str = "1:1") -> io.NodeOutput:
        return io.NodeOutput(*sdxl_aspect_ratio(aspect_ratio))


class AspectRatioSelectorV2(_FrozenSchema, io.ComfyNode):
    """utility_nodes.py:717-744."""
    NODE_ID = "AspectRatioSelector"
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    async def execute(cls, aspect_ratio: str = "1:1") -> io.NodeOutput:
        ratio, width, height = sdxl_aspect_ratio(aspect_ratio)

        scale_ratio = 768 / max(width, height)

        width = int(scale_ratio * width / 8) * 8
        height = int(scale_ratio * height / 8) * 8

        return io.NodeOutput(ratio, width, height)


def image_scale_down(images, width, height, crop):
    """utility_nodes.py:858-880 (UtilImageScaleDown.image_scale_down)."""
    if crop == "center":
        old_width = images.shape[2]
        old_height = images.shape[1]
        old_aspect = old_width / old_height
        new_aspect = width / height
        x = 0
        y = 0
        if old_aspect > new_aspect:
            x = round((old_width - old_width * (new_aspect / old_aspect)) / 2)
        elif old_aspect < new_aspect:
            y = round((old_height - old_height * (old_aspect / new_aspect)) / 2)
        s = images[:, y : old_height - y, x : old_width - x, :]
    else:
        s = images

    results = []
    for image in s:
        img = tensor2pil(image).convert("RGB")
        img = img.resize((width, height), Image.Resampling.LANCZOS)
        results.append(pil2tensor(img))

    return torch.cat(results, dim=0)


def image_scale_down_by(images, scale_by):
    """utility_nodes.py:900-905."""
    width = images.shape[2]
    height = images.shape[1]
    new_width = int(width * scale_by)
    new_height = int(height * scale_by)
    return image_scale_down(images, new_width, new_height, "center")


class ImageScaleDownByV2(_FrozenSchema, io.ComfyNode):
    NODE_ID = "ImageScaleDownBy"
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    async def execute(cls, images: Any = None, scale_by: float = 0.5) -> io.NodeOutput:
        tensor = await images.raw()
        return io.NodeOutput(await sdk.ImageRef.from_value(image_scale_down_by(tensor, scale_by)))


class ImageScaleDownToSizeV2(_FrozenSchema, io.ComfyNode):
    """utility_nodes.py:923-933."""
    NODE_ID = "ImageScaleDownToSize"
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    async def execute(cls, images: Any = None, size: int = 512, mode: bool = True) -> io.NodeOutput:
        tensor = await images.raw()
        width = tensor.shape[2]
        height = tensor.shape[1]

        if mode:
            scale_by = size / max(width, height)
        else:
            scale_by = size / min(width, height)

        scale_by = min(scale_by, 1.0)
        return io.NodeOutput(await sdk.ImageRef.from_value(image_scale_down_by(tensor, scale_by)))


class ImageScaleToMegapixelsV2(_FrozenSchema, io.ComfyNode):
    """utility_nodes.py:957-978 (UtilImageScaleToTotalPixels)."""
    NODE_ID = "ImageScaleToMegapixels"
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    async def execute(cls, images: Any = None, megapixels: float = 1.0, upscale_model_opt: Any = None) -> io.NodeOutput:
        tensor = await images.raw()
        width = tensor.shape[2]
        height = tensor.shape[1]
        scale_by = np.sqrt((megapixels * 1024 * 1024) / (width * height))

        if scale_by <= 1.0:
            return io.NodeOutput(await sdk.ImageRef.from_value(image_scale_down_by(tensor, scale_by)))

        width = round(tensor.shape[2] * scale_by)
        height = round(tensor.shape[1] * scale_by)
        if scale_by < 1.2 or upscale_model_opt is None:
            s = tensor.movedim(-1, 1)
            # comfy.utils.common_upscale(s, width, height, "bicubic", "disabled") for a 4-D batch
            s = torch.nn.functional.interpolate(s, size=(height, width), mode="bicubic")
            s = s.movedim(1, -1)
            return io.NodeOutput(await sdk.ImageRef.from_value(s))
        raise NotImplementedError(
            f"{PREFIX}/ImageScaleToMegapixels: upscaling with an upscale model (scale {float(scale_by):.3f} >= 1.2 "
            f"and upscale_model_opt connected) is not converted yet; see SECURE_CONVERSION.md")


class ImageGaussianBlurV2(_FrozenSchema, io.ComfyNode):
    """utility_nodes.py:1027-1034."""
    NODE_ID = "ImageGaussianBlur"
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    async def execute(cls, images: Any = None, radius: int = 1) -> io.NodeOutput:
        tensor = await images.raw()
        blured_images = []
        for image in tensor:
            img = tensor2pil(image)
            img = img.filter(ImageFilter.GaussianBlur(radius=radius))
            blured_images.append(pil2tensor(img))

        return io.NodeOutput(await sdk.ImageRef.from_value(torch.cat(blured_images, dim=0)))


class ImageApplyChannelV2(_FrozenSchema, io.ComfyNode):
    """utility_nodes.py:1082-1102."""
    NODE_ID = "ImageApplyChannel"
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    async def execute(cls, images: Any = None, channel_data: Any = None, channel: str = "R") -> io.NodeOutput:
        tensor = await images.raw()
        channel_data = await channel_data.raw()
        merged_images = []

        for image in tensor:
            image = image.cpu().clone()

            if channel == "A":
                if image.shape[2] < 4:
                    image = torch.cat([image, torch.ones((image.shape[0], image.shape[1], 1))], dim=2)

                image[:, :, 3] = channel_data
            elif channel == "R":
                image[:, :, 0] = channel_data
            elif channel == "G":
                image[:, :, 1] = channel_data
            else:
                image[:, :, 2] = channel_data

            merged_images.append(image)

        return io.NodeOutput(await sdk.ImageRef.from_value(torch.stack(merged_images)))


class CheckpointNameSelectorV2(_FrozenSchema, io.ComfyNode):
    """utility_nodes.py:1186-1205. The host fills the checkpoint menu from its own folder."""
    NODE_ID = "CheckpointNameSelector"
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def fingerprint_inputs(cls, *args, **kwargs):
        return torch.rand(1).item()  # the original's IS_CHANGED, verbatim: every run counts as changed

    @classmethod
    async def execute(cls, ckpt_name: str = "") -> io.NodeOutput:
        return io.NodeOutput(ckpt_name, ckpt_name)


class RandomIntV2(_FrozenSchema, io.ComfyNode):
    """utility_nodes.py:455-475, verbatim: torch's global RNG, which upstream leaves unseeded. The value differs from
    run to run in both versions; given the same RNG state the two return the same value."""
    NODE_ID = "RandomInt"
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def fingerprint_inputs(cls, *args, **kwargs):
        return torch.rand(1).item()

    @classmethod
    async def execute(cls, min: int = 0, max: int = 100) -> io.NodeOutput:
        num = torch.randint(min, max, (1,)).item()
        return io.NodeOutput(num, str(num))


class RandomFloatV2(_FrozenSchema, io.ComfyNode):
    """utility_nodes.py:478-498, verbatim (see RandomIntV2)."""
    NODE_ID = "RandomFloat"
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def fingerprint_inputs(cls, *args, **kwargs):
        return torch.rand(1).item()

    @classmethod
    async def execute(cls, min: float = 0.0, max: float = 1.0) -> io.NodeOutput:
        num = torch.rand(1).item() * (max - min) + min
        return io.NodeOutput(num, str(num))


CONVERTED = {cls.NODE_ID: cls for cls in (
    StringToIntV2, BooleanPrimitiveV2, SeedSelectorV2, SDXLAspectRatioSelectorV2, AspectRatioSelectorV2,
    ImageScaleDownByV2, ImageScaleDownToSizeV2, ImageScaleToMegapixelsV2, ImageGaussianBlurV2, ImageApplyChannelV2,
    CheckpointNameSelectorV2, RandomIntV2, RandomFloatV2)}

__all__ = ["CONVERTED"]
