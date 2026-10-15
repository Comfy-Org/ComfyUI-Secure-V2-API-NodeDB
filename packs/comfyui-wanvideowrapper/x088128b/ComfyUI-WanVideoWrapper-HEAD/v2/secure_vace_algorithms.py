"""Complete pinned native VACE conditioning algorithm, inactive in registry.

The factory captures required genuine private device/offload inputs per
algorithm instance, replacing only source ambient globals. All four native
methods and self calls are retained, not delegated to a legacy class.
Real Torch/core ProgressBar/common_upscale and native VAE remain dependencies;
no runtime/model handle, callback bridge or provider facade is introduced.
"""
import math
import torch
import torch.nn.functional as F
from comfy.utils import ProgressBar, common_upscale
from .secure_cache_logging import log

VAE_STRIDE = (4, 8, 8)

def create_vace_conditioning(*, device, offload_device):
    """Create the actual algorithm with explicit native device bindings.

    This captures actual selected device values without probing, defaulting,
    admitting or loading a model. Keep the object realm-owned; supply the real
    native VAE to process. Recreate on a changed admitted device generation.
    """
    class VACEConditioning:
        def process(self, vae, width, height, num_frames, strength, vace_start_percent, vace_end_percent, input_frames=None, ref_images=None, input_masks=None, prev_vace_embeds=None, tiled_vae=False):
            width = (width // 16) * 16
            height = (height // 16) * 16
    
            target_shape = (16, (num_frames - 1) // VAE_STRIDE[0] + 1,
                            height // VAE_STRIDE[1],
                            width // VAE_STRIDE[2])
            # vace context encode
            if input_frames is None:
                input_frames = torch.zeros((1, 3, num_frames, height, width), device=device, dtype=vae.dtype)
            else:
                input_frames = input_frames.clone()[:num_frames, :, :, :3]
                input_frames = common_upscale(input_frames.movedim(-1, 1), width, height, "lanczos", "disabled").movedim(1, -1)
                input_frames = input_frames.to(vae.dtype).to(device).unsqueeze(0).permute(0, 4, 1, 2, 3) # B, C, T, H, W
                input_frames = input_frames * 2 - 1
            if input_masks is None:
                input_masks = torch.ones_like(input_frames, device=device)
            else:
                log.info(f"input_masks shape: {input_masks.shape}")
                input_masks = input_masks[:num_frames]
                input_masks = common_upscale(input_masks.clone().unsqueeze(1), width, height, "nearest-exact", "disabled").squeeze(1)
                input_masks = input_masks.to(vae.dtype).to(device)
                input_masks = input_masks.unsqueeze(-1).unsqueeze(0).permute(0, 4, 1, 2, 3).repeat(1, 3, 1, 1, 1) # B, C, T, H, W
    
            if ref_images is not None:
                ref_images = ref_images.clone()[..., :3]
                # Create padded image
                if ref_images.shape[0] > 1:
                    ref_images = torch.cat([ref_images[i] for i in range(ref_images.shape[0])], dim=1).unsqueeze(0)
                
                B, H, W, C = ref_images.shape
                current_aspect = W / H
                target_aspect = width / height
                if current_aspect > target_aspect:
                    # Image is wider than target, pad height
                    new_h = int(W / target_aspect)
                    pad_h = (new_h - H) // 2
                    padded = torch.ones(ref_images.shape[0], new_h, W, ref_images.shape[3], device=ref_images.device, dtype=ref_images.dtype)
                    padded[:, pad_h:pad_h+H, :, :] = ref_images
                    ref_images = padded
                elif current_aspect < target_aspect:
                    # Image is taller than target, pad width
                    new_w = int(H * target_aspect)
                    pad_w = (new_w - W) // 2
                    padded = torch.ones(ref_images.shape[0], H, new_w, ref_images.shape[3], device=ref_images.device, dtype=ref_images.dtype)
                    padded[:, :, pad_w:pad_w+W, :] = ref_images
                    ref_images = padded
                ref_images = common_upscale(ref_images.movedim(-1, 1), width, height, "lanczos", "center").movedim(1, -1)
                
                ref_images = ref_images.to(vae.dtype).to(device).unsqueeze(0).permute(0, 4, 1, 2, 3).unsqueeze(0)
                ref_images = ref_images * 2 - 1
    
            vae = vae.to(device)
            z0 = self.vace_encode_frames(vae, input_frames, ref_images, masks=input_masks, tiled_vae=tiled_vae)
            
            m0 = self.vace_encode_masks(input_masks, ref_images)
            z = self.vace_latent(z0, m0)
            vae.to(offload_device)
    
            vace_input = {
                "vace_context": z,
                "vace_scale": strength,
                "has_ref": ref_images is not None,
                "num_frames": num_frames,
                "target_shape": target_shape,
                "vace_start_percent": vace_start_percent,
                "vace_end_percent": vace_end_percent,
                "vace_seq_len": math.ceil((z[0].shape[2] * z[0].shape[3]) / 4 * z[0].shape[1]),
                "additional_vace_inputs": [],
            }
    
            if prev_vace_embeds is not None:
                if "additional_vace_inputs" in prev_vace_embeds and prev_vace_embeds["additional_vace_inputs"]:
                    vace_input["additional_vace_inputs"] = prev_vace_embeds["additional_vace_inputs"].copy()
                vace_input["additional_vace_inputs"].append(prev_vace_embeds)
        
            return (vace_input,)

        def vace_encode_frames(self, vae, frames, ref_images, masks=None, tiled_vae=False):
            if ref_images is None:
                ref_images = [None] * len(frames)
            else:
                assert len(frames) == len(ref_images)
    
            pbar = ProgressBar(len(frames))
            if masks is None:
                latents = vae.encode(frames, device=device, tiled=tiled_vae)
            else:
                inactive = [i * (1 - m) + 0 * m for i, m in zip(frames, masks)]
                reactive = [i * m + 0 * (1 - m) for i, m in zip(frames, masks)]
                del frames
                inactive = vae.encode(inactive, device=device, tiled=tiled_vae)
                reactive = vae.encode(reactive, device=device, tiled=tiled_vae)
                latents = [torch.cat((u, c), dim=0) for u, c in zip(inactive, reactive)]
                del inactive, reactive
            
            
            cat_latents = []
            for latent, refs in zip(latents, ref_images):
                if refs is not None:
                    if masks is None:
                        ref_latent = vae.encode(refs, device=device, tiled=tiled_vae)
                    else:
                        ref_latent = vae.encode(refs, device=device, tiled=tiled_vae)
                        ref_latent = [torch.cat((u, torch.zeros_like(u)), dim=0) for u in ref_latent]
                    assert all([x.shape[1] == 1 for x in ref_latent])
                    latent = torch.cat([*ref_latent, latent], dim=1)
                cat_latents.append(latent)
                pbar.update(1)
            return cat_latents

        def vace_encode_masks(self, masks, ref_images=None):
            if ref_images is None:
                ref_images = [None] * len(masks)
            else:
                assert len(masks) == len(ref_images)
    
            result_masks = []
            pbar = ProgressBar(len(masks))
            for mask, refs in zip(masks, ref_images):
                _c, depth, height, width = mask.shape
                new_depth = int((depth + 3) // VAE_STRIDE[0])
                height = 2 * (int(height) // (VAE_STRIDE[1] * 2))
                width = 2 * (int(width) // (VAE_STRIDE[2] * 2))
    
                # reshape
                mask = mask[0, :, :, :]
                mask = mask.view(
                    depth, height, VAE_STRIDE[1], width, VAE_STRIDE[1]
                )  # depth, height, 8, width, 8
                mask = mask.permute(2, 4, 0, 1, 3)  # 8, 8, depth, height, width
                mask = mask.reshape(
                    VAE_STRIDE[1] * VAE_STRIDE[2], depth, height, width
                )  # 8*8, depth, height, width
    
                # interpolation
                mask = F.interpolate(mask.unsqueeze(0), size=(new_depth, height, width), mode='nearest-exact').squeeze(0)
    
                if refs is not None:
                    length = len(refs)
                    mask_pad = torch.zeros_like(mask[:, :length, :, :])
                    mask = torch.cat((mask_pad, mask), dim=1)
                result_masks.append(mask)
                pbar.update(1)
            return result_masks

        def vace_latent(self, z, m):
            return [torch.cat([zz, mm], dim=0) for zz, mm in zip(z, m)]

    return VACEConditioning()
