"""Pinned Wan latent-batch and StoryMem scientific algorithms.

This is real pack-owned computation, not a legacy node wrapper. Torch,
common_upscale and model_management must be provisioned/admitted as genuine
native dependencies before import. VAE must be the actual selected native Wan
instance. Keyword-only devices bind native source globals from the same trusted
selection; there is no string-device default, provider facade or public grant.

No node activation: registered count and whole-pack status are unchanged.
"""
import torch
from comfy.utils import common_upscale
from comfy import model_management as mm
from .secure_cache_logging import log

def encode_latent_batch(vae, images, enable_vae_tiling=False, tile_x=272,
                        tile_y=272, tile_stride_x=144, tile_stride_y=128,
                        latent_strength=1.0, *, device, offload_device):
    vae.to(device)
    images = images.clone()
    B, H, W, C = images.shape
    if W % 16 != 0 or H % 16 != 0:
        new_height = (H // 16) * 16
        new_width = (W // 16) * 16
        log.warning(f"Image size {W}x{H} is not divisible by 16, resizing to {new_width}x{new_height}")
        images = common_upscale(images.movedim(-1, 1), new_width, new_height, "lanczos", "disabled").movedim(1, -1)
    if images.shape[-1] == 4:
        images = images[..., :3]
    images = images.to(vae.dtype).to(device) * 2.0 - 1.0
    latent_list = []
    for img in images:
        if enable_vae_tiling and tile_x is not None:
            latent = vae.encode(img.unsqueeze(0).unsqueeze(0).permute(0, 4, 1, 2, 3), device=device, tiled=enable_vae_tiling, tile_size=(tile_x//vae.upsampling_factor, tile_y//vae.upsampling_factor), tile_stride=(tile_stride_x//vae.upsampling_factor, tile_stride_y//vae.upsampling_factor))
        else:
            latent = vae.encode(img.unsqueeze(0).unsqueeze(0).permute(0, 4, 1, 2, 3), device=device, tiled=enable_vae_tiling)
        if latent_strength != 1.0:
            latent *= latent_strength
        latent_list.append(latent.squeeze(0).cpu())
    latents_out = torch.stack(latent_list, dim=0)
    log.info(f"WanVideoEncode: Encoded latents shape {latents_out.shape}")
    vae.to(offload_device)
    mm.soft_empty_cache()
    return ({"samples": latents_out},)


def add_story_mem_latents(vae, embeds, memory_images, rope_negative_offset,
                          rope_negative_offset_frames, *, device, offload_device):
    updated = dict(embeds)
    story_mem_latents, = encode_latent_batch(vae, memory_images, device=device, offload_device=offload_device)
    updated["story_mem_latents"] = story_mem_latents["samples"].squeeze(2).permute(1, 0, 2, 3)  # [C, T, H, W]
    updated["rope_negative_offset_frames"] = rope_negative_offset_frames if rope_negative_offset else 0
    return (updated,)

