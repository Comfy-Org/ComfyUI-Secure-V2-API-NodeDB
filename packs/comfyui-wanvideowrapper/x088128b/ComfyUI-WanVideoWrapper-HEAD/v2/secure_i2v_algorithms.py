"""Complete pinned WanVideoImageToVideoEncode conditioning algorithm.

Requires real native WanVAE/Torch/core dependencies and admitted device/import
authority. Private required devices lift only native globals; no default CPU,
generic encoder/TAEHV fallback, tensor/provider facade or node activation.
Native dictionary mutation and result tensor metadata remain source-exact;
actual typed outer publication/ownership still require qualified consumers.
"""
import gc
import torch
from comfy.utils import common_upscale
from comfy import model_management as mm
from .secure_cache_logging import log
from .secure_reference_noise import add_noise_to_reference_video

PATCH_SIZE = (1, 2, 2)

def image_to_video_conditioning(width, height, num_frames, force_offload,
                                noise_aug_strength, start_latent_strength,
                                end_latent_strength, start_image=None,
                                end_image=None, control_embeds=None,
                                fun_or_fl2v_model=False, temporal_mask=None,
                                extra_latents=None, clip_embeds=None,
                                tiled_vae=False, add_cond_latents=None,
                                vae=None, augment_empty_frames=0.0,
                                empty_frame_pad_image=None, *, device,
                                offload_device):
    if vae is None:
        raise ValueError("VAE is required for image encoding.")
    H = height
    W = width
    lat_h = H // vae.upsampling_factor
    lat_w = W // vae.upsampling_factor
    num_frames = ((num_frames - 1) // 4) * 4 + 1
    two_ref_images = start_image is not None and end_image is not None
    if start_image is None and end_image is not None:
        fun_or_fl2v_model = True # end image alone only works with this option
    base_frames = num_frames + (1 if two_ref_images and not fun_or_fl2v_model else 0)
    if temporal_mask is None:
        mask = torch.zeros(1, base_frames, lat_h, lat_w, device=device, dtype=vae.dtype)
        if start_image is not None:
            mask[:, 0:start_image.shape[0]] = 1  # First frame
        if end_image is not None:
            mask[:, -end_image.shape[0]:] = 1  # End frame if exists
    else:
        mask = common_upscale(temporal_mask.unsqueeze(1).to(device), lat_w, lat_h, "nearest", "disabled").squeeze(1)
        if mask.shape[0] > base_frames:
            mask = mask[:base_frames]
        elif mask.shape[0] < base_frames:
            mask = torch.cat([mask, torch.zeros(base_frames - mask.shape[0], lat_h, lat_w, device=device)])
        mask = mask.unsqueeze(0).to(device, vae.dtype)
    pixel_mask = mask.clone()
    # Repeat first frame and optionally end frame
    start_mask_repeated = torch.repeat_interleave(mask[:, 0:1], repeats=4, dim=1) # T, C, H, W
    if end_image is not None and not fun_or_fl2v_model:
        end_mask_repeated = torch.repeat_interleave(mask[:, -1:], repeats=4, dim=1) # T, C, H, W
        mask = torch.cat([start_mask_repeated, mask[:, 1:-1], end_mask_repeated], dim=1)
    else:
        mask = torch.cat([start_mask_repeated, mask[:, 1:]], dim=1)
    # Reshape mask into groups of 4 frames
    mask = mask.view(1, mask.shape[1] // 4, 4, lat_h, lat_w) # 1, T, C, H, W
    mask = mask.movedim(1, 2)[0]# C, T, H, W
    # Resize and rearrange the input image dimensions
    if start_image is not None:
        start_image = start_image[..., :3]
        if start_image.shape[1] != H or start_image.shape[2] != W:
            resized_start_image = common_upscale(start_image.movedim(-1, 1), W, H, "lanczos", "disabled").movedim(0, 1)
        else:
            resized_start_image = start_image.permute(3, 0, 1, 2) # C, T, H, W
        resized_start_image = resized_start_image * 2 - 1
        if noise_aug_strength > 0.0:
            resized_start_image = add_noise_to_reference_video(resized_start_image, ratio=noise_aug_strength)
    if end_image is not None:
        end_image = end_image[..., :3]
        if end_image.shape[1] != H or end_image.shape[2] != W:
            resized_end_image = common_upscale(end_image.movedim(-1, 1), W, H, "lanczos", "disabled").movedim(0, 1)
        else:
            resized_end_image = end_image.permute(3, 0, 1, 2) # C, T, H, W
        resized_end_image = resized_end_image * 2 - 1
        if noise_aug_strength > 0.0:
            resized_end_image = add_noise_to_reference_video(resized_end_image, ratio=noise_aug_strength)
    # Concatenate image with zero frames and encode
    if start_image is not None and end_image is None:
        zero_frames = torch.zeros(3, num_frames-start_image.shape[0], H, W, device=device, dtype=vae.dtype)
        concatenated = torch.cat([resized_start_image.to(device, dtype=vae.dtype), zero_frames], dim=1)
        del resized_start_image, zero_frames
    elif start_image is None and end_image is not None:
        zero_frames = torch.zeros(3, num_frames-end_image.shape[0], H, W, device=device, dtype=vae.dtype)
        concatenated = torch.cat([zero_frames, resized_end_image.to(device, dtype=vae.dtype)], dim=1)
        del zero_frames
    elif start_image is None and end_image is None:
        concatenated = torch.zeros(3, num_frames, H, W, device=device, dtype=vae.dtype)
    else:
        if fun_or_fl2v_model:
            zero_frames = torch.zeros(3, num_frames-(start_image.shape[0]+end_image.shape[0]), H, W, device=device, dtype=vae.dtype)
        else:
            zero_frames = torch.zeros(3, num_frames-1, H, W, device=device, dtype=vae.dtype)
        concatenated = torch.cat([resized_start_image.to(device, dtype=vae.dtype), zero_frames, resized_end_image.to(device, dtype=vae.dtype)], dim=1)
        del resized_start_image, zero_frames
    if empty_frame_pad_image is not None:
        pad_img = empty_frame_pad_image.clone()[..., :3]
        if pad_img.shape[1] != H or pad_img.shape[2] != W:
            pad_img = common_upscale(pad_img.movedim(-1, 1), W, H, "lanczos", "disabled").movedim(1, -1)
        pad_img = (pad_img.movedim(-1, 0) * 2 - 1).to(device, dtype=vae.dtype)
        num_pad_frames = pad_img.shape[1]
        num_target_frames = concatenated.shape[1]
        if num_pad_frames < num_target_frames:
            pad_img = torch.cat([pad_img, pad_img[:, -1:].expand(-1, num_target_frames - num_pad_frames, -1, -1)], dim=1)
        else:
            pad_img = pad_img[:, :num_target_frames]
        frame_is_empty = (pixel_mask[0].mean(dim=(-2, -1)) < 0.5)[:concatenated.shape[1]].clone()
        if start_image is not None:
            frame_is_empty[:start_image.shape[0]] = False
        if end_image is not None:
            frame_is_empty[-end_image.shape[0]:] = False
        concatenated[:, frame_is_empty] = pad_img[:, frame_is_empty]
    mm.soft_empty_cache()
    gc.collect()
    vae.to(device)
    y = vae.encode([concatenated], device, end_=(end_image is not None and not fun_or_fl2v_model),tiled=tiled_vae)[0]
    del concatenated
    has_ref = False
    if extra_latents is not None:
        samples = extra_latents["samples"].squeeze(0)
        y = torch.cat([samples, y], dim=1)
        mask = torch.cat([torch.ones_like(mask[:, 0:samples.shape[1]]), mask], dim=1)
        num_frames += samples.shape[1] * 4
        has_ref = True
    y[:, :1] *= start_latent_strength
    y[:, -1:] *= end_latent_strength
    if augment_empty_frames > 0.0:
        frame_is_empty = (mask[0].mean(dim=(-2, -1)) < 0.5).view(1, -1, 1, 1)
        y = y[:, :1] + (y - y[:, :1]) * ((augment_empty_frames+1) * frame_is_empty + ~frame_is_empty)
    # Calculate maximum sequence length
    patches_per_frame = lat_h * lat_w // (PATCH_SIZE[1] * PATCH_SIZE[2])
    frames_per_stride = (num_frames - 1) // 4 + (2 if end_image is not None and not fun_or_fl2v_model else 1)
    max_seq_len = frames_per_stride * patches_per_frame
    if add_cond_latents is not None:
        add_cond_latents["ref_latent_neg"] = vae.encode(torch.zeros(1, 3, 1, H, W, device=device, dtype=vae.dtype), device)
    if force_offload:
        vae.model.to(offload_device)
        mm.soft_empty_cache()
        gc.collect()
    image_embeds = {
        "image_embeds": y.cpu(),
        "clip_context": clip_embeds.get("clip_embeds", None) if clip_embeds is not None else None,
        "negative_clip_context": clip_embeds.get("negative_clip_embeds", None) if clip_embeds is not None else None,
        "max_seq_len": max_seq_len,
        "num_frames": num_frames,
        "lat_h": lat_h,
        "lat_w": lat_w,
        "control_embeds": control_embeds["control_embeds"] if control_embeds is not None else None,
        "end_image": resized_end_image if end_image is not None else None,
        "fun_or_fl2v_model": fun_or_fl2v_model,
        "has_ref": has_ref,
        "add_cond_latents": add_cond_latents,
        "mask": mask.cpu()
    }
    return (image_embeds,)

