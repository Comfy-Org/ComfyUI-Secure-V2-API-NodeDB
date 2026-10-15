"""Complete pinned main Wan video encoder; scientific source only.

Real TAEHV class import, native WanVAE instances and Torch/core dependencies
require actual installed/preimport/model/device admission. Device/offload are
mandatory lifted native bindings, not default CPU, a provider facade or grant.
No node activation or runtime selection occurs in this module.
"""
import torch
from comfy.utils import common_upscale
from comfy import model_management as mm
from .taehv import TAEHV
from .secure_cache_logging import log
from .secure_reference_noise import add_noise_to_reference_video

def encode_video_latents(vae, image, enable_vae_tiling, tile_x, tile_y,
                         tile_stride_x, tile_stride_y, noise_aug_strength=0.0,
                         latent_strength=1.0, mask=None, *, device, offload_device):
    vae.to(device)
    image = image.clone()
    B, H, W, C = image.shape
    if W % 16 != 0 or H % 16 != 0:
        new_height = (H // 16) * 16
        new_width = (W // 16) * 16
        log.warning(f"Image size {W}x{H} is not divisible by 16, resizing to {new_width}x{new_height}")
        image = common_upscale(image.movedim(-1, 1), new_width, new_height, "lanczos", "disabled").movedim(1, -1)
    if image.shape[-1] == 4:
        image = image[..., :3]
    image = image.to(vae.dtype).to(device).unsqueeze(0).permute(0, 4, 1, 2, 3) # B, C, T, H, W        
    if noise_aug_strength > 0.0:
        image = add_noise_to_reference_video(image, ratio=noise_aug_strength)
    if isinstance(vae, TAEHV):
        latents = vae.encode_video(image.permute(0, 2, 1, 3, 4), parallel=False)# B, T, C, H, W
        latents = latents.permute(0, 2, 1, 3, 4)
    else:
        latents = vae.encode(image * 2.0 - 1.0, device=device, tiled=enable_vae_tiling, tile_size=(tile_x//vae.upsampling_factor, tile_y//vae.upsampling_factor), tile_stride=(tile_stride_x//vae.upsampling_factor, tile_stride_y//vae.upsampling_factor))
        vae.to(offload_device)
    if latent_strength != 1.0:
        latents *= latent_strength
    latents = latents.cpu()
    log.info(f"WanVideoEncode: Encoded latents shape {latents.shape}")
    mm.soft_empty_cache()
    return ({"samples": latents, "noise_mask": mask},)

