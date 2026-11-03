"""Secure Nodes V2: RES4LYF's image nodes Film Grain, Image Grain Add, Frames Slice, Frame Select, Image Repeat Tile
To Size and VAEEncodeAdvanced (upstream 057a913e).

- Film Grain and Image Grain Add run upstream's own classes (images.py:307-371 and :375-443, copied verbatim into
  res4lyf_core/images.py) on the exact input pixels. Like upstream, they draw their grain from torch's global random
  generator, which upstream never seeds. Here that is the guest's generator, not the host's (see
  SECURE_CONVERSION.md). Given the same generator state, both versions give the same image.
- Frames Slice (images.py:557-581: ``frames[start:stop].clone()``) selects the same frames on the host
  (``image.select_batch``), so its pixels never enter the guest. An empty slice is refused by name: a V2 IMAGE cannot
  be empty. Frame Select (images.py:530-554: ``frames[select]``) selects its one frame the same way.
- Image Repeat Tile To Size (images.py:258-300) runs upstream's body on the exact input pixels: tile, then crop or
  resize with upstream's image_resize.
- VAEEncodeAdvanced is upstream's main() (helper_sigma_preview_image_preproc.py:234-317) line for line, with
  upstream's own image_resize (images.py:152-254, verbatim; its "lanczos" is Core's comfy.utils.lanczos, verbatim in
  res4lyf_core/_comfy/utils.py). The VAE encode runs on the host through ``vae.encode``, which is Core's
  ``vae.encode(pixels)``. One upstream line is not reproduced: main() seeds torch's process-wide generator with 42
  (lines 257-258). Core's image VAEs encode deterministically, so the latents are the same; the seeding's side
  effect on later users of the host's global generator is not (see SECURE_CONVERSION.md).
"""
from __future__ import annotations

from typing import Any

import torch
import torch.nn.functional as F

from comfy_api.latest import io, sdk

from ._secure_runtime import schema_for
from .res4lyf_core import images
from .res4lyf_core._comfy._refuse import OutOfEnvelope

IMAGE_BATCH_MAX = 4096  # the most images one V2 IMAGE holds (sdk.ImageRef.from_value)


class FilmGrainV2(io.ComfyNode):
    """images.py:307-371 (Film_Grain.main), verbatim, in the guest."""
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("Film Grain")

    @classmethod
    async def execute(cls, image: Any = None, density: float = 1.0, intensity: float = 1.0, highlights: float = 1.0,
                      supersample_factor: int = 4, repeats: int = 1) -> io.NodeOutput:
        pixels = await image.raw()
        if pixels.shape[0] * repeats > IMAGE_BATCH_MAX:
            raise OutOfEnvelope(f"RES4LYF/Film Grain: {pixels.shape[0]} images x {repeats} repeats is more than the "
                                f"{IMAGE_BATCH_MAX} images a V2 IMAGE holds")
        (result,) = images.Film_Grain().main(image=pixels, density=density, intensity=intensity,
                                             highlights=highlights, supersample_factor=supersample_factor,
                                             repeats=repeats)
        return io.NodeOutput(await sdk.ImageRef.from_value(result))


class ImageGrainAddV2(io.ComfyNode):
    """images.py:375-443 (Image_Grain_Add.main), verbatim, in the guest."""
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("Image Grain Add")

    @classmethod
    async def execute(cls, image: Any = None, weight: float = 0.5) -> io.NodeOutput:
        pixels = await image.raw()
        (result,) = images.Image_Grain_Add().main(image=pixels, weight=weight)
        return io.NodeOutput(await sdk.ImageRef.from_value(result))


class FramesSliceV2(io.ComfyNode):
    """images.py:557-581 (Frames_Slice.main: ``frames[start:stop].clone()``), as a host-side batch selection."""
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("Frames Slice")

    @classmethod
    async def execute(cls, frames: Any = None, start: int = 0, stop: int = 1) -> io.NodeOutput:
        batch = await frames.batch_size()
        indices = list(range(batch))[start:stop]  # the frames upstream's frames[start:stop] keeps, in order
        if not indices:
            raise OutOfEnvelope(f"RES4LYF/Frames Slice: frames[{start}:{stop}] of a {batch}-frame batch is empty, "
                                "and a V2 IMAGE cannot be empty")
        return io.NodeOutput(await frames.select_batch(indices))


class FrameSelectV2(io.ComfyNode):
    """images.py:530-554 (Frame_Select.main: ``frames[select].unsqueeze(0).clone()``), as a host-side batch
    selection."""
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("Frame Select")

    @classmethod
    async def execute(cls, frames: Any = None, select: int = 0) -> io.NodeOutput:
        batch = await frames.batch_size()
        if not 0 <= select < batch:  # upstream's frames[select] raises the same IndexError
            raise IndexError(f"index {select} is out of bounds for dimension 0 with size {batch}")
        return io.NodeOutput(await frames.select_batch([select]))


class ImageRepeatTileToSizeV2(io.ComfyNode):
    """images.py:258-300 (ImageRepeatTileToSize.main), line for line, on the exact input pixels."""
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("Image Repeat Tile To Size")

    @classmethod
    async def execute(cls, image: Any = None, width: int = 1024, height: int = 1024,
                      crop: bool = True) -> io.NodeOutput:
        method, interpolation, condition, multiple_of, keep_proportion = "stretch", "lanczos", "always", 0, False
        img = (await image.raw()).clone().detach()
        b, h, w, c = img.shape
        h_tgt = int(torch.ceil(torch.div(height, h)))
        w_tgt = int(torch.ceil(torch.div(width,  w)))
        img_tiled = torch.tile(img, (h_tgt, w_tgt, 1))
        if crop:
            img_tiled = img_tiled[:,:height, :width, :]
        else:
            img_tiled  = images.image_resize(img_tiled, width, height, method, interpolation, condition, multiple_of,
                                             keep_proportion)
        return io.NodeOutput(await sdk.ImageRef.from_value(img_tiled))


class VAEEncodeAdvancedV2(io.ComfyNode):
    """helper_sigma_preview_image_preproc.py:234-317 (VAEEncodeAdvanced.main), line for line."""
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("VAEEncodeAdvanced")

    @classmethod
    async def execute(cls, width: int = 1024, height: int = 1024, resize_to_input: str = "false",
                      image_1: Any = None, image_2: Any = None, mask: Any = None, invert_mask: bool = False,
                      method: str = "stretch", interpolation: str = "lanczos", mask_channel: str = "red",
                      latent: Any = None, latent_type: str = "16_channels", vae: Any = None) -> io.NodeOutput:
        condition, multiple_of, keep_proportion = "always", 0, False  # main()'s defaults; not inputs of the node
        ratio = 8  # latent compression factor

        # (upstream seeds torch's process-wide generator with 42 here; not reproduced, see the module docstring)

        image_1 = (await image_1.raw()).clone() if image_1 is not None else None
        image_2 = (await image_2.raw()).clone() if image_2 is not None else None
        mask_pixels = await mask.raw() if mask is not None else None
        latent_value = await latent.value() if latent is not None else None

        if latent_value is not None and resize_to_input == "latent":
            height, width = latent_value['samples'].shape[-2:]
            height, width = height * ratio, width * ratio
        elif image_1 is not None and resize_to_input == "image_1":
            height, width = image_1.shape[1:3]
        elif image_2 is not None and resize_to_input == "image_2":
            height, width = image_2.shape[1:3]
        elif mask_pixels is not None and resize_to_input == "mask":
            height, width = mask_pixels.shape[1:3]

        if latent_value is not None:
            c = latent_value['samples'].shape[1]  # noqa: F841  (upstream reads it and returns the input latent)
            empty_latent = latent
        else:
            if latent_type == "4_channels":
                c = 4
            else:
                c = 16
            if image_1 is not None:
                b = image_1.shape[0]
            elif image_2 is not None:
                b = image_2.shape[0]
            else:
                b = 1
            empty_latent = await sdk.LatentRef.from_value(
                {"samples": torch.zeros((b, c, height // ratio, width // ratio))})

        latent_1, latent_2 = None, None
        if image_1 is not None:
            image_1 = images.image_resize(image_1, width, height, method, interpolation, condition, multiple_of,
                                          keep_proportion)
            latent_1 = await vae.encode(await sdk.ImageRef.from_value(image_1[:, :, :, :3]))
        if image_2 is not None:
            image_2 = images.image_resize(image_2, width, height, method, interpolation, condition, multiple_of,
                                          keep_proportion)
            latent_2 = await vae.encode(await sdk.ImageRef.from_value(image_2[:, :, :, :3]))

        if mask_pixels is not None and mask_pixels.shape[-1] > 1:
            channels = ["red", "green", "blue", "alpha"]
            mask_pixels = mask_pixels[:, :, :, channels.index(mask_channel)]

        if mask_pixels is not None:
            mask_pixels = F.interpolate(mask_pixels.unsqueeze(0), size=(height, width), mode='bilinear',
                                        align_corners=False).squeeze(0)
            if invert_mask:
                mask_pixels = 1.0 - mask_pixels

        mask_out = await sdk.MaskRef._from_raw(mask_pixels) if mask_pixels is not None else None
        return io.NodeOutput(latent_1, latent_2, mask_out, empty_latent, width, height)


CONVERTED = {
    "Film Grain": FilmGrainV2,
    "Frame Select": FrameSelectV2,
    "Frames Slice": FramesSliceV2,
    "Image Grain Add": ImageGrainAddV2,
    "Image Repeat Tile To Size": ImageRepeatTileToSizeV2,
    "VAEEncodeAdvanced": VAEEncodeAdvancedV2,
}

__all__ = ["CONVERTED", "FilmGrainV2", "FrameSelectV2", "FramesSliceV2", "ImageGrainAddV2",
           "ImageRepeatTileToSizeV2", "VAEEncodeAdvancedV2"]
