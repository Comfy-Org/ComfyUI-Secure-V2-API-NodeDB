"""Complete pinned WanVideoDecode scientific algorithm.

Actual Torch/core model management and native WanVAE or exact TAEHV instance
must be provisioned and admitted before import/execution. Devices are required
native bindings lifted from nodes.py globals, not a string mapping/default,
public compute route, replacement model or permission grant. No activation.
"""
import torch
from comfy import model_management as mm
from .secure_decode_validation import validate_decode_tiles

def decode_video(vae, samples, enable_vae_tiling, tile_x, tile_y,
                 tile_stride_x, tile_stride_y, normalization="default", *,
                 device, offload_device):
    mm.soft_empty_cache()
    video = samples.get("video", None)
    if video is not None:
        video.clamp_(-1.0, 1.0)
        video.add_(1.0).div_(2.0)
        return video.cpu().float(),
    latents = samples["samples"].clone()
    end_image = samples.get("end_image", None)
    has_ref = samples.get("has_ref", False)
    drop_last = samples.get("drop_last", False)
    is_looped = samples.get("looped", False)
    flashvsr_LQ_images = samples.get("flashvsr_LQ_images", None)
    vae.to(device)
    latents = latents.to(device = device, dtype = vae.dtype)
    mm.soft_empty_cache()
    if has_ref:
        latents = latents[:, :, 1:]
    if drop_last:
        latents = latents[:, :, :-1]
    if type(vae).__name__ == "TAEHV":
        images = vae.decode_video(latents.permute(0, 2, 1, 3, 4), cond=flashvsr_LQ_images.to(vae.dtype) if flashvsr_LQ_images is not None else None)[0].permute(1, 0, 2, 3)
        images = torch.clamp(images, 0.0, 1.0)
        images = images.permute(1, 2, 3, 0).cpu().float()
        return (images,)
    else:
        images = vae.decode(latents, device=device, end_=(end_image is not None), tiled=enable_vae_tiling, tile_size=(tile_x//8, tile_y//8), tile_stride=(tile_stride_x//8, tile_stride_y//8))[0]
    images = images.cpu().float()
    if normalization != "none":
        if normalization == "minmax":
            images.sub_(images.min()).div_(images.max() - images.min())
        else:
            images.clamp_(-1.0, 1.0)
            images.add_(1.0).div_(2.0)
    if is_looped:
        temp_latents = torch.cat([latents[:, :, -3:]] + [latents[:, :, :2]], dim=2)
        temp_images = vae.decode(temp_latents, device=device, end_=(end_image is not None), tiled=enable_vae_tiling, tile_size=(tile_x//vae.upsampling_factor, tile_y//vae.upsampling_factor), tile_stride=(tile_stride_x//vae.upsampling_factor, tile_stride_y//vae.upsampling_factor))[0]
        temp_images = temp_images.cpu().float()
        temp_images = (temp_images - temp_images.min()) / (temp_images.max() - temp_images.min())
        images = torch.cat([temp_images[:, 9:].to(images), images[:, 5:]], dim=1)
    if end_image is not None: 
        images = images[:, 0:-1]
    vae.to(offload_device)
    mm.soft_empty_cache()
    images.clamp_(0.0, 1.0)
    return (images.permute(1, 2, 3, 0),)

