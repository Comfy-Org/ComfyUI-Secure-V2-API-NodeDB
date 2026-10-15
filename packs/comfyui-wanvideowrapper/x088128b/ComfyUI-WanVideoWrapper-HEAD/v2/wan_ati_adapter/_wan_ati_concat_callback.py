"""Pinned ATI concat math through public invocation-scoped tensor operations.

The synchronous math qualification remains frozen in _wan_ati_concat_math.
This companion changes only access to the three asynchronous public operations:
lazy image selection, actual model latent normalization, and lazy mask selection.
"""
import torch
from comfy_api.latest import sdk

from ._wan_ati_concat_math import resize_to_batch_size
from ._wan_resize import common_upscale
from .ATI.motion_patch import patch_motion


async def ati_concat_callback(invocation: sdk.ModelConcatInvocation, noise: torch.Tensor,
                              metadata: sdk.ModelConcatMetadata, *, tracks: torch.Tensor,
                              temperature: float, topk: int):
    extra_channels = metadata.patch_input_channels - noise.shape[1]
    if extra_channels == 0:
        return None

    image = await invocation.concat_latent_image()
    device = metadata.device

    if image is None:
        shape_image = list(noise.shape)
        shape_image[1] = extra_channels
        image = torch.zeros(shape_image, dtype=noise.dtype, layout=noise.layout, device=noise.device)
    else:
        image = common_upscale(image.to(device), noise.shape[-1], noise.shape[-2], "bilinear", "center")
        for i in range(0, image.shape[1], 16):
            image[:, i: i + 16] = await invocation.process_latent_in(image[:, i: i + 16])
        image = resize_to_batch_size(image, noise.shape[0])

    if not metadata.image_to_video or extra_channels == image.shape[1]:
        return image

    if image.shape[1] > (extra_channels - 4):
        image = image[:, :(extra_channels - 4)]

    mask = await invocation.concat_mask()
    if mask is None:
        mask = torch.zeros_like(noise)[:, :4]
    else:
        if mask.shape[1] != 4:
            mask = torch.mean(mask, dim=1, keepdim=True)
        mask = 1.0 - mask
        mask = common_upscale(mask.to(device), noise.shape[-1], noise.shape[-2], "bilinear", "center")
        if mask.shape[-3] < noise.shape[-3]:
            mask = torch.nn.functional.pad(mask, (0, 0, 0, 0, 0, noise.shape[-3] - mask.shape[-3]), mode='constant', value=0)
        if mask.shape[1] == 1:
            mask = mask.repeat(1, 4, 1, 1, 1)
        mask = resize_to_batch_size(mask, noise.shape[0])

    image_cond = torch.cat((mask, image), dim=1)
    image_cond_ati = patch_motion(tracks.to(image_cond.device, image_cond.dtype), image_cond[0],
                                  temperature=temperature, topk=topk)

    return image_cond_ati.unsqueeze(0)
