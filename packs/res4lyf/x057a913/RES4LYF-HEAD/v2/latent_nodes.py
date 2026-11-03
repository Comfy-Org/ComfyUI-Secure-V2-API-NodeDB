"""Secure Nodes V2: RES4LYF's latent nodes LatentUpscaleWithVAE and EmptyLatentImageCustom (057a913e).

LatentUpscaleWithVAE (helper_sigma_preview_image_preproc.py:618-691):

The original decodes the latent, or, when the latent carries a RES4LYF sampler's state, that sampler's final denoised
estimate; resizes the pixels with its own image_resize (stretch, lanczos); encodes them; and returns a copy of the
input latent with the new samples (in the input samples' dtype and device) and, in the carried state, the new latent
as the denoised estimate. V2 does the same:
- the V2 sampler's chain marker (latent_chain.py) stands in for state_info, and the decode reads its "denoised"
  tensor, which equals the original's state_info['denoised'] bit for bit (tests/v2_parity.py);
- decode and encode run on the host with Core's vae.decode and vae.encode. vae.decode_tensor applies the original's
  5-D -> 4-D reshape; the resize runs in the guest with upstream's image_resize (res4lyf_core/images.py, whose
  lanczos is Core's, copied verbatim).
Known differences (SECURE_CONVERSION.md):
- the original seeds torch's process-wide generator with 42 first (:653-654); V2 does not;
- lanczos returns channels-first memory, which the original hands to vae.encode, while V2's pixels cross to the host
  contiguous: equal pixels, last-bit latent differences (the documented LAYOUT_ROUNDING class);
- with state_info the original also decodes, resizes and re-encodes the loop's data_prev_ history into its output
  state (:662-680); only unsample/resample read it, which V2 refuses, so V2 carries no history.
"""
from __future__ import annotations

from typing import Any

import torch

from comfy_api.latest import io, sdk

from ._secure_runtime import schema_for
from .latent_chain import CHAIN_KEY
from .res4lyf_core import images
from .res4lyf_core._comfy._refuse import OutOfEnvelope

PREFIX = "RES4LYF/LatentUpscaleWithVAE"


def _refuse(reason: str):
    raise OutOfEnvelope(f"{PREFIX}: {reason} is outside the V2 reduced envelope; refused instead of approximated "
                        f"(see SECURE_CONVERSION.md)")


class LatentUpscaleWithVAEV2(io.ComfyNode):
    """helper_sigma_preview_image_preproc.py:618-691 (LatentUpscaleWithVAE.main)."""
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("LatentUpscaleWithVAE")

    @classmethod
    async def execute(cls, latent: Any, width: int = 1024, height: int = 1024, vae: Any = None) -> io.NodeOutput:
        method, interpolation, condition, multiple_of, keep_proportion = "stretch", "lanczos", "always", 0, False

        # (upstream seeds torch's process-wide generator with 42 here; not reproduced, see the module docstring)

        latent_value = await latent.value()
        if "state_info" in latent_value:
            _refuse("a latent carrying an unconverted RES4LYF sampler's state_info")
        chain = latent_value.get(CHAIN_KEY)
        if chain is not None and not isinstance(chain, dict):
            _refuse("a chain marker without the sampler's denoised estimate (from an earlier V2 version)")

        if chain is not None:
            denoised = chain["denoised"]  # KeyError when the loop ran no step, as latent['state_info']['denoised']
            source = await sdk.LatentRef.from_value({"samples": denoised})
        else:
            source = latent
        decoded = await vae.decode_tensor(source)
        pixels = await decoded.raw()

        pixels = images.image_resize(pixels, width, height, method, interpolation, condition, multiple_of,
                                     keep_proportion)
        encoded = await vae.encode(await sdk.ImageRef.from_value(pixels[:, :, :, :3]))
        latent_tensor = (await encoded.value())["samples"]

        latent_out = dict(latent_value)
        if chain is not None:
            latent_out[CHAIN_KEY] = dict(chain)
            latent_out[CHAIN_KEY]["denoised"] = latent_tensor

        latent_out["samples"] = latent_tensor.to(latent_value["samples"])

        return io.NodeOutput(await sdk.LatentRef.from_value(latent_out))


class EmptyLatentImageCustomV2(io.ComfyNode):
    """nodes_latents.py:1907-1969 (EmptyLatentImageCustom.generate), line for line: zeros of the chosen shape and
    precision. The original allocates them on core's intermediate device (the CPU unless the host runs GPU-only);
    a V2 latent is the host's copy of the guest's zeros (SECURE_CONVERSION.md)."""
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("EmptyLatentImageCustom")

    @classmethod
    async def execute(cls, width: int = 24, height: int = 24, batch_size: int = 1, channels: str = '4',
                      mode: str = 'default', compression: int = 42, precision: str = 'fp32') -> io.NodeOutput:
        c = int(channels)
        ratio = 1
        match mode:
            case "sdxl":
                ratio = 8
            case "cascade_b":
                ratio = 4
            case "cascade_c":
                ratio = compression
            case "exact":
                ratio = 1
        dtype = torch.float32
        match precision:
            case "fp16":
                dtype = torch.float16
            case "fp32":
                dtype = torch.float32
            case "fp64":
                dtype = torch.float64
        latent = torch.zeros([batch_size,
                              c,
                              height // ratio,
                              width // ratio],
                             dtype=dtype)
        return io.NodeOutput(await sdk.LatentRef.from_value({"samples": latent}))


CONVERTED = {
    "EmptyLatentImageCustom": EmptyLatentImageCustomV2,
    "LatentUpscaleWithVAE": LatentUpscaleWithVAEV2,
}

__all__ = ["CONVERTED", "EmptyLatentImageCustomV2", "LatentUpscaleWithVAEV2"]
