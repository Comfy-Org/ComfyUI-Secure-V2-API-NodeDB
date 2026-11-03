"""Secure Nodes V2: wlsh_nodes' image scaling nodes (upstream wallish77/wlsh_nodes 97807467).

- Image Scale by Shortside (wlsh_nodes.py:854-880) runs the original's body on the exact input pixels, with Core's
  comfy.utils.common_upscale copied verbatim in _core_utils.py.
- Upscale by Factor with Model (wlsh_nodes.py:916-954) runs the original's body. Core's comfy.utils.tiled_scale
  (verbatim in _core_utils.py) tiles the image exactly as the original asks (192-pixel tiles, overlap 8). Each tile
  goes to the host's upscale model untiled, which is the original's own `upscale_model(tile)` call; the model and its
  weights stay on the host. The original's clamp and Core's common_upscale then run on the result.
"""
from __future__ import annotations

import asyncio
from typing import Any

import torch

from comfy_api.latest import io, sdk

from . import _core_utils
from ._secure_runtime import schema_for


class ImageScaleByShortsideV2(io.ComfyNode):
    """wlsh_nodes.py:854-880 (WLSH_Image_Scale_By_Shortside.upscale)."""
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("Image Scale by Shortside (WLSH)")

    @classmethod
    async def execute(cls, original: Any = None, upscale_method: str = "nearest-exact",
                      shortside: int = 512) -> io.NodeOutput:
        original = await original.raw()
        old_width = original.shape[2]
        old_height = original.shape[1]
        old_shortside = min(old_width, old_height)
        factor = shortside / max(1, old_shortside)
        new_width = int(old_width * factor)
        new_height = int(old_height * factor)
        samples = original.movedim(-1, 1)
        s = _core_utils.common_upscale(samples, new_width, new_height, upscale_method, crop="disabled")
        s = s.movedim(1, -1)
        return io.NodeOutput(await sdk.ImageRef.from_value(s), new_width, new_height)


class _HostUpscaleModel:
    """The original's `upscale_model(a)` for one tile (BCHW), run by the host's upscale model untiled. Called from the
    worker thread that runs tiled_scale; each call hops to the node's event loop. The first tile's result is kept, so
    finding the model's scale costs no extra evaluation."""

    def __init__(self, ref, loop):
        self.ref, self.loop, self.first = ref, loop, None

    async def _run(self, tile):
        image = await sdk.ImageRef.from_value(tile.movedim(-3, -1))
        out = await self.ref.upscale(image)
        return (await out.raw()).movedim(-1, -3)

    def scale_of(self, tile) -> int:
        out = asyncio.run_coroutine_threadsafe(self._run(tile), self.loop).result()
        scale = out.shape[-1] // tile.shape[-1]
        if out.shape[-1] != scale * tile.shape[-1] or out.shape[-2] != scale * tile.shape[-2] or scale < 1:
            raise ValueError(f"wlsh_nodes/Upscale by Factor with Model: the model maps {tuple(tile.shape[-2:])} to "
                             f"{tuple(out.shape[-2:])}, which is not one integer scale")
        self.first = (tile, out)
        return scale

    def __call__(self, tile):
        if self.first is not None and self.first[0].shape == tile.shape and torch.equal(self.first[0], tile):
            return self.first[1]
        return asyncio.run_coroutine_threadsafe(self._run(tile), self.loop).result()


class UpscaleByFactorWithModelV2(io.ComfyNode):
    """wlsh_nodes.py:916-954 (WLSH_Upscale_By_Factor_With_Model.upscale)."""
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("Upscale by Factor with Model (WLSH)")

    @classmethod
    async def execute(cls, upscale_model: Any = None, image: Any = None, upscale_method: str = "nearest-exact",
                      factor: float = 2.0) -> io.NodeOutput:
        image = await image.raw()
        model = _HostUpscaleModel(upscale_model, asyncio.get_running_loop())
        # upscale image using upscaling model
        in_img = image.movedim(-1, -3)
        # the first tile tiled_scale cuts (image 0 at position 0, 0): its result gives upscale_model.scale
        first_tile = in_img[:1].narrow(2, 0, min(128 + 64, in_img.shape[2]))
        first_tile = first_tile.narrow(3, 0, min(128 + 64, in_img.shape[3]))
        scale = await asyncio.to_thread(model.scale_of, first_tile)
        s = await asyncio.to_thread(
            _core_utils.tiled_scale, in_img, lambda a: model(a), tile_x=128 + 64, tile_y=128 + 64, overlap=8,
            upscale_amount=scale)
        upscaled = torch.clamp(s.movedim(-3, -1), min=0, max=1.0)

        # get dimensions of orginal image
        old_width = image.shape[2]
        old_height = image.shape[1]

        # scale dimensions by provided factor
        new_width = int(old_width * factor)
        new_height = int(old_height * factor)

        # apply simple scaling to image
        samples = upscaled.movedim(-1, 1)
        s = _core_utils.common_upscale(samples, new_width, new_height, upscale_method, crop="disabled")
        s = s.movedim(1, -1)

        return io.NodeOutput(await sdk.ImageRef.from_value(s))


CONVERTED = {
    "Image Scale by Shortside (WLSH)": ImageScaleByShortsideV2,
    "Upscale by Factor with Model (WLSH)": UpscaleByFactorWithModelV2,
}

__all__ = ["CONVERTED"]
