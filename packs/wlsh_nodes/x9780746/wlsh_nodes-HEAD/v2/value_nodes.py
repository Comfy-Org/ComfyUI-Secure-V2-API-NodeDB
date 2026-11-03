"""Secure Nodes V2: wlsh_nodes' number, text and empty-latent nodes (upstream wallish77/wlsh_nodes 97807467).

Each class serves the original's frozen schema (_secure_runtime.schema_for) and computes exactly what the original
computes (bodies copied from wlsh_nodes.py; the line ranges are on each class), in the same types. The empty latents
are the original's CPU float32 zeros, handed over as a LATENT value.
"""
from __future__ import annotations

import numpy as np
import torch

from comfy_api.latest import io, sdk

from ._secure_runtime import schema_for


class SDXLStepsV2(io.ComfyNode):
    """wlsh_nodes.py:225-246 (WLSH_SDXL_Steps.set_steps)."""
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("SDXL Steps (WLSH)")

    @classmethod
    async def execute(cls, precondition: int = 3, base: int = 12, total: int = 20) -> io.NodeOutput:
        return io.NodeOutput(precondition, base, total)


class MultiplyIntegerV2(io.ComfyNode):
    """wlsh_nodes.py:248-268 (WLSH_Int_Multiply.multiply)."""
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("Multiply Integer (WLSH)")

    @classmethod
    async def execute(cls, number: int = 2, multiplier: int = 2) -> io.NodeOutput:
        result = number * multiplier
        return io.NodeOutput(int(result))


class SDXLResolutionsV2(io.ComfyNode):
    """wlsh_nodes.py:443-472 (WLSH_SDXL_Resolutions.get_resolutions)."""
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("SDXL Resolutions (WLSH)")

    @classmethod
    async def execute(cls, resolution: str = "1024x1024|1:1", direction: str = "landscape") -> io.NodeOutput:
        pixels = resolution.split('|')[0]
        width, height = pixels.split('x')
        width = int(width)
        height = int(height)
        if (direction == "portrait"):
            width, height = height, width
        return io.NodeOutput(width, height)


class ResolutionsByRatioV2(io.ComfyNode):
    """wlsh_nodes.py:474-498 (WLSH_Resolutions_by_Ratio.get_resolutions)."""
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("Resolutions by Ratio (WLSH)")

    @classmethod
    async def execute(cls, aspect: str = "1:1", direction: str = "landscape", shortside: int = 512) -> io.NodeOutput:
        x, y = aspect.split(':')
        x = int(x)
        y = int(y)
        ratio = x / y
        width = int(shortside * ratio)
        width = (width + 63) & (-64)
        height = shortside
        if (direction == "portrait"):
            width, height = height, width
        return io.NodeOutput(width, height)


class SimpleStringCombineV2(io.ComfyNode):
    """wlsh_nodes.py:375-413 (WLSH_String_Append.concat_string); an unlinked input_string is "", as there."""
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("Simple String Combine (WLSH)")

    @classmethod
    async def execute(cls, placement: str = "after", separator: str = "comma", addition: str = "",
                      input_string: str = "") -> io.NodeOutput:
        sep = {"comma": ', ', "space": ' ', "newline": '\n', "none": ''}

        if (input_string is None):
            return io.NodeOutput(addition)

        if (placement == "after"):
            new_string = input_string + sep[separator] + addition
        else:
            new_string = addition + sep[separator] + input_string

        return io.NodeOutput(new_string)


async def _empty_latent(width: int, height: int, batch_size: int) -> io.NodeOutput:
    """The tail all four empty-latent nodes share (e.g. wlsh_nodes.py:516-519)."""
    adj_width = width // 8
    adj_height = height // 8
    latent = torch.zeros([batch_size, 4, adj_height, adj_width])
    return io.NodeOutput(await sdk.LatentRef.from_value({"samples": latent}), adj_width * 8, adj_height * 8)


class EmptyLatentBySizeV2(io.ComfyNode):
    """wlsh_nodes.py:500-519 (WLSH_Empty_Latent_Image_By_Resolution.generate)."""
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("Empty Latent by Size (WLSH)")

    @classmethod
    async def execute(cls, width: int = 512, height: int = 512, batch_size: int = 1) -> io.NodeOutput:
        return await _empty_latent(width, height, batch_size)


class EmptyLatentByRatioV2(io.ComfyNode):
    """wlsh_nodes.py:522-554 (WLSH_Empty_Latent_Image_By_Ratio.generate)."""
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("Empty Latent by Ratio (WLSH)")

    @classmethod
    async def execute(cls, aspect: str = "1:1", direction: str = "landscape", shortside: int = 512,
                      batch_size: int = 1) -> io.NodeOutput:
        x, y = aspect.split(':')
        x = int(x)
        y = int(y)
        ratio = x / y
        width = int(shortside * ratio)
        width = (width + 63) & (-64)
        height = shortside
        if (direction == "portrait"):
            width, height = height, width
        return await _empty_latent(width, height, batch_size)


class EmptyLatentByPixelsV2(io.ComfyNode):
    """wlsh_nodes.py:556-593 (WLSH_Empty_Latent_Image_By_Pixels.generate)."""
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("Empty Latent by Pixels (WLSH)")

    @classmethod
    async def execute(cls, aspect: str = "1:1", direction: str = "landscape", megapixels: float = 1.0,
                      batch_size: int = 1) -> io.NodeOutput:
        x, y = aspect.split(':')
        x = int(x)
        y = int(y)
        ratio = x / y

        total = int(megapixels * 1024 * 1024)

        width = int(np.sqrt(ratio * total))
        width = (width + 63) & (-64)
        height = int(np.sqrt(1 / ratio * total))
        height = (height + 63) & (-64)
        if (direction == "portrait"):
            width, height = height, width
        return await _empty_latent(width, height, batch_size)


class SDXLQuickEmptyLatentV2(io.ComfyNode):
    """wlsh_nodes.py:595-623 (WLSH_SDXL_Quick_Empty_Latent.generate)."""
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("SDXL Quick Empty Latent (WLSH)")

    @classmethod
    async def execute(cls, resolution: str = "1024x1024|1:1", direction: str = "landscape",
                      batch_size: int = 1) -> io.NodeOutput:
        pixels = resolution.split('|')[0]
        width, height = pixels.split('x')
        width = int(width)
        height = int(height)
        if (direction == "portrait"):
            width, height = height, width
        return await _empty_latent(width, height, batch_size)


CONVERTED = {
    "Empty Latent by Pixels (WLSH)": EmptyLatentByPixelsV2,
    "Empty Latent by Ratio (WLSH)": EmptyLatentByRatioV2,
    "Empty Latent by Size (WLSH)": EmptyLatentBySizeV2,
    "Multiply Integer (WLSH)": MultiplyIntegerV2,
    "Resolutions by Ratio (WLSH)": ResolutionsByRatioV2,
    "SDXL Quick Empty Latent (WLSH)": SDXLQuickEmptyLatentV2,
    "SDXL Resolutions (WLSH)": SDXLResolutionsV2,
    "SDXL Steps (WLSH)": SDXLStepsV2,
    "Simple String Combine (WLSH)": SimpleStringCombineV2,
}

__all__ = ["CONVERTED"]
