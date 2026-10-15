"""Original Wan Animate algorithm; only CPU cache-policy calls adapted.

All temporal/mask/resize/conditioning math and original failure behavior stay
in this pack. The public wrapper replaces the output live VAE with its recipe.
"""
import gc
import logging
import math
import torch
from ._wan_resize import common_upscale
device = offload_device = torch.device('cpu')
log = logging.getLogger(__name__)

def animate_embeds(vae, width, height, num_frames, force_offload, frame_window_size, colormatch, pose_strength, face_strength, ref_images=None, pose_images=None, face_images=None, clip_embeds=None, tiled_vae=False, bg_images=None, mask=None, start_ref_image=None):
    W = width // 16 * 16
    H = height // 16 * 16
    lat_h = H // vae.upsampling_factor
    lat_w = W // vae.upsampling_factor
    num_refs = ref_images.shape[0] if ref_images is not None else 0
    num_frames = (num_frames - 1) // 4 * 4 + 1
    looping = num_frames > frame_window_size or start_ref_image is not None
    if num_frames < frame_window_size:
        frame_window_size = num_frames
    target_shape = (16, (num_frames - 1) // 4 + 1 + num_refs, lat_h, lat_w)
    latent_window_size = (frame_window_size - 1) // 4
    if not looping:
        num_frames = num_frames + num_refs * 4
    else:
        latent_window_size = latent_window_size + 1
    gc.collect()
    vae.to(device)
    pose_latents = ref_latent = None
    if pose_images is not None:
        pose_images = pose_images[..., :3]
        if pose_images.shape[1] != H or pose_images.shape[2] != W:
            resized_pose_images = common_upscale(pose_images.movedim(-1, 1), W, H, 'lanczos', 'disabled').movedim(0, 1)
        else:
            resized_pose_images = pose_images.permute(3, 0, 1, 2)
        resized_pose_images = resized_pose_images * 2 - 1
        if not looping:
            pose_latents = vae.encode([resized_pose_images.to(device, vae.dtype)], device, tiled=tiled_vae)
            pose_latents = pose_latents.to(offload_device)
            if pose_latents.shape[2] < latent_window_size:
                log.info(f'WanAnimate: Padding pose latents from {pose_latents.shape} to length {latent_window_size}')
                pad_len = latent_window_size - pose_latents.shape[2]
                pad = torch.zeros(pose_latents.shape[0], pose_latents.shape[1], pad_len, pose_latents.shape[3], pose_latents.shape[4], device=pose_latents.device, dtype=pose_latents.dtype)
                pose_latents = torch.cat([pose_latents, pad], dim=2)
            del resized_pose_images
        else:
            resized_pose_images = resized_pose_images.to(offload_device, dtype=vae.dtype)
    bg_latents = None
    if bg_images is not None:
        if bg_images.shape[1] != H or bg_images.shape[2] != W:
            resized_bg_images = common_upscale(bg_images.movedim(-1, 1), W, H, 'lanczos', 'disabled').movedim(0, 1)
        else:
            resized_bg_images = bg_images.permute(3, 0, 1, 2)
        resized_bg_images = resized_bg_images[:3] * 2 - 1
    if not looping:
        if bg_images is None:
            resized_bg_images = torch.zeros(3, num_frames - num_refs, H, W, device=device, dtype=vae.dtype)
        bg_latents = vae.encode([resized_bg_images.to(device, vae.dtype)], device, tiled=tiled_vae)[0].to(offload_device)
        del resized_bg_images
    elif bg_images is not None:
        resized_bg_images = resized_bg_images.to(offload_device, dtype=vae.dtype)
    if ref_images is not None:
        if ref_images.shape[1] != H or ref_images.shape[2] != W:
            resized_ref_images = common_upscale(ref_images.movedim(-1, 1), W, H, 'lanczos', 'disabled').movedim(0, 1)
        else:
            resized_ref_images = ref_images.permute(3, 0, 1, 2)
        resized_ref_images = resized_ref_images[:3] * 2 - 1
        ref_latent = vae.encode([resized_ref_images.to(device, vae.dtype)], device, tiled=tiled_vae)[0]
        msk = torch.zeros(4, 1, lat_h, lat_w, device=device, dtype=vae.dtype)
        msk[:, :num_refs] = 1
        ref_latent_masked = torch.cat([msk, ref_latent], dim=0).to(offload_device)
        if mask is None:
            bg_mask = torch.zeros(1, num_frames, lat_h, lat_w, device=offload_device, dtype=vae.dtype)
        else:
            bg_mask = 1 - mask[:num_frames]
            if bg_mask.shape[0] < num_frames and (not looping):
                bg_mask = torch.cat([bg_mask, bg_mask[-1:].repeat(num_frames - bg_mask.shape[0], 1, 1)], dim=0)
            bg_mask = common_upscale(bg_mask.unsqueeze(1), lat_w, lat_h, 'nearest', 'disabled').squeeze(1)
            bg_mask = bg_mask.unsqueeze(-1).permute(3, 0, 1, 2).to(offload_device, vae.dtype)
        if bg_images is None and looping:
            bg_mask[:, :num_refs] = 1
        bg_mask_mask_repeated = torch.repeat_interleave(bg_mask[:, 0:1], repeats=4, dim=1)
        bg_mask = torch.cat([bg_mask_mask_repeated, bg_mask[:, 1:]], dim=1)
        bg_mask = bg_mask.view(1, bg_mask.shape[1] // 4, 4, lat_h, lat_w)
        bg_mask = bg_mask.movedim(1, 2)[0]
        if not looping:
            bg_latents_masked = torch.cat([bg_mask[:, :bg_latents.shape[1]], bg_latents], dim=0)
            del bg_mask, bg_latents
            ref_latent = torch.cat([ref_latent_masked, bg_latents_masked], dim=1)
        else:
            ref_latent = ref_latent_masked
    if face_images is not None:
        face_images = face_images[..., :3]
        if face_images.shape[1] != 512 or face_images.shape[2] != 512:
            resized_face_images = common_upscale(face_images.movedim(-1, 1), 512, 512, 'lanczos', 'center').movedim(0, 1)
        else:
            resized_face_images = face_images.permute(3, 0, 1, 2)
        resized_face_images = (resized_face_images * 2 - 1).unsqueeze(0)
        resized_face_images = resized_face_images.to(offload_device, dtype=vae.dtype)
    if start_ref_image is not None:
        if start_ref_image.shape[1] != H or start_ref_image.shape[2] != W:
            resized_start_ref_image = common_upscale(start_ref_image.movedim(-1, 1), W, H, 'lanczos', 'disabled').movedim(0, 1)
        else:
            resized_start_ref_image = start_ref_image.permute(3, 0, 1, 2)
        resized_start_ref_image = resized_start_ref_image[:3] * 2 - 1
    seq_len = math.ceil(target_shape[2] * target_shape[3] / 4 * target_shape[1])
    if force_offload:
        vae.model.to(offload_device)
        gc.collect()
    image_embeds = {'clip_context': clip_embeds.get('clip_embeds', None) if clip_embeds is not None else None, 'negative_clip_context': clip_embeds.get('negative_clip_embeds', None) if clip_embeds is not None else None, 'max_seq_len': seq_len, 'pose_latents': pose_latents, 'pose_images': resized_pose_images if pose_images is not None and looping else None, 'bg_images': resized_bg_images if bg_images is not None and looping else None, 'ref_masks': bg_mask if mask is not None and looping else None, 'is_masked': mask is not None, 'ref_latent': ref_latent, 'ref_image': resized_ref_images if ref_images is not None else None, 'start_ref_image': resized_start_ref_image if start_ref_image is not None else None, 'face_pixels': resized_face_images if face_images is not None else None, 'num_frames': num_frames, 'target_shape': target_shape, 'frame_window_size': frame_window_size, 'lat_h': lat_h, 'lat_w': lat_w, 'vae': vae, 'colormatch': colormatch, 'looping': looping, 'pose_strength': pose_strength, 'face_strength': face_strength}
    return image_embeds
