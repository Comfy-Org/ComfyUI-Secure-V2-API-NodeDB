"""Pinned ATI concat math with explicit, typed model facts.

This module owns tensor math only. It neither registers a MODEL node nor
implements or assumes the new public scoped callback API. The supplied
latent normalization operation must be the actual model's operation; its
host/guest binding remains a separate integration requirement.

resize_to_batch_size is retained verbatim from Core comfy/utils.py, under
the existing Core license beside _wan_resize.py. No Core module is imported.
"""
from collections.abc import Callable
import math
import numpy as np
import torch

from ._wan_resize import common_upscale
from .ATI.motion import process_tracks
from .ATI.motion_patch import patch_motion
from .secure_ati_visual_nodes import pad_pts, parse_json_tracks


def prepare_ati_tracks(tracks, width: int, height: int) -> torch.Tensor:
    tracks_data = parse_json_tracks(tracks)
    arrs = []
    for track in tracks_data:
        pts = pad_pts(track)
        arrs.append(pts)
    tracks_np = np.stack(arrs, axis=0)
    return process_tracks(tracks_np, (width, height)).unsqueeze(0)


def resize_to_batch_size(tensor, batch_size):
    in_batch_size = tensor.shape[0]
    if in_batch_size == batch_size:
        return tensor

    if batch_size <= 1:
        return tensor[:batch_size]

    output = torch.empty([batch_size] + list(tensor.shape)[1:], dtype=tensor.dtype, device=tensor.device)
    if batch_size < in_batch_size:
        scale = (in_batch_size - 1) / (batch_size - 1)
        for i in range(batch_size):
            output[i] = tensor[min(round(i * scale), in_batch_size - 1)]
    else:
        scale = in_batch_size / batch_size
        for i in range(batch_size):
            output[i] = tensor[min(math.floor((i + 0.5) * scale), in_batch_size - 1)]

    return output


def ati_concat_conditioning(tracks: torch.Tensor, temperature: float, topk: int, *,
                           patch_input_channels: int, image_to_video: bool,
                           process_latent_in: Callable[[torch.Tensor], torch.Tensor], **kwargs):
    noise = kwargs.get("noise", None)
    extra_channels = patch_input_channels - noise.shape[1]
    if extra_channels == 0:
        return None

    image = kwargs.get("concat_latent_image", None)
    device = kwargs["device"]

    if image is None:
        shape_image = list(noise.shape)
        shape_image[1] = extra_channels
        image = torch.zeros(shape_image, dtype=noise.dtype, layout=noise.layout, device=noise.device)
    else:
        image = common_upscale(image.to(device), noise.shape[-1], noise.shape[-2], "bilinear", "center")
        for i in range(0, image.shape[1], 16):
            image[:, i: i + 16] = process_latent_in(image[:, i: i + 16])
        image = resize_to_batch_size(image, noise.shape[0])

    if not image_to_video or extra_channels == image.shape[1]:
        return image

    if image.shape[1] > (extra_channels - 4):
        image = image[:, :(extra_channels - 4)]

    mask = kwargs.get("concat_mask", kwargs.get("denoise_mask", None))
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
