"""Stand-ins for ``comfy.utils``. Only refused paths reference these from the vendored loop:
- latent resizing (resample/unsample state, tiling, guides);
- packed multi-stream latents (video+audio).
One function is real: ``lanczos``, copied verbatim from Core 6257422b (comfy/utils.py:1110-1118), which the vendored
images.image_resize calls for its "lanczos" interpolation (tests/test_res4lyf_images.py checks the copy).
"""
import numpy as np
import torch
from PIL import Image

from ._refuse import refuse

PROGRESS_BAR_ENABLED = False


def lanczos(samples, width, height):
    #the below API is strict and expects grayscale to be squeezed
    if samples.ndim == 4:
        samples = samples.squeeze(1) if samples.shape[1] == 1 else samples.movedim(1, -1)
    images = [Image.fromarray(np.clip(255. * image.cpu().numpy(), 0, 255).astype(np.uint8)) for image in samples]
    images = [image.resize((width, height), resample=Image.Resampling.LANCZOS) for image in images]
    images = [torch.from_numpy(t).movedim(-1, 0) if (t := np.array(image).astype(np.float32) / 255.0).ndim == 3 else torch.from_numpy(t) for image in images]
    result = torch.stack(images)
    return result.to(samples.device, samples.dtype)


def common_upscale(*_args, **_kwargs):
    refuse("latent resizing (comfy.utils.common_upscale: resample/unsample state, tiling or guides)")


def pack_latents(*_args, **_kwargs):
    refuse("packed multi-stream latents (comfy.utils.pack_latents)")


def unpack_latents(*_args, **_kwargs):
    refuse("packed multi-stream latents (comfy.utils.unpack_latents)")
