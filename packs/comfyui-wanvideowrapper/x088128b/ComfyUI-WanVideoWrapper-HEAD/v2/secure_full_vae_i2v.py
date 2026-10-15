"""Original image-to-video VAE math, bounded raw CPU adapter.

Unpromoted candidate; native and shared numerical qualification required.
"""
import gc
import torch
from comfy_api.latest import io
from .secure_tensor_nodes import _bound_payload
from .secure_full_vae_nodes import rebuild_full_vae
from .secure_full_vae_encode import _image, add_noise_to_reference_video
from ._wan_resize import common_upscale

device = offload_device = torch.device('cpu')
PATCH_SIZE = (1, 2, 2)

def _i2v_boundary(width, height, num_frames, images, masks, extra_latents, payloads):
    _bound_payload({'images':images,'masks':masks,'extra':extra_latents,'payloads':payloads})
    if any(type(v) is not int for v in (width,height,num_frames)):
        raise ValueError('Wan I2V requires integer dimensions')
    if not 64 <= width <= 512 or not 64 <= height <= 512 or not 1 <= num_frames <= 64:
        raise ValueError('Wan I2V exceeds bounded CPU output dimensions')
    for value in images:
        if value is not None:
            _image(value)
    if masks is not None and (not isinstance(masks,torch.Tensor) or masks.device.type != 'cpu'
            or masks.layout != torch.strided or masks.ndim != 3 or not 1 <= masks.shape[0] <= 64
            or not all(1 <= n <= 512 for n in masks.shape[1:])):
        raise ValueError('Wan I2V requires bounded dense CPU THW masks')
    if extra_latents is not None:
        value = extra_latents.get('samples') if isinstance(extra_latents,dict) else None
        if (not isinstance(value,torch.Tensor) or value.device.type != 'cpu' or value.layout != torch.strided
                or value.ndim != 5 or value.shape[0] != 1 or value.shape[1] != 16
                or not 1 <= value.shape[2] <= 16 or tuple(value.shape[3:]) != (height//8,width//8)):
            raise ValueError('Wan I2V extra latents require bounded matching 1,16,T,H/8,W/8 CPU samples')
    if (num_frames+8)*width*height*3*4*4 > 64*1024*1024:
        raise ValueError('Wan I2V projected image working set exceeds 64 MiB')

class WanVideoImageToVideoEncode(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw','assets','models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoImageToVideoEncode',display_name='WanVideo ImageToVideo Encode',
            category='WanVideoWrapper',inputs=[io.Int.Input('width', default=832, min=64, max=8096, step=8, tooltip='Width of the image to encode'),
                io.Int.Input('height', default=480, min=64, max=8096, step=8, tooltip='Height of the image to encode'),
                io.Int.Input('num_frames', default=81, min=1, max=10000, step=4, tooltip='Number of frames to encode'),
                io.Float.Input('noise_aug_strength', default=0.0, min=0.0, max=10.0, step=0.001, tooltip='Strength of noise augmentation, helpful for I2V where some noise can add motion and give sharper results'),
                io.Float.Input('start_latent_strength', default=1.0, min=0.0, max=10.0, step=0.001, tooltip='Additional latent multiplier, helpful for I2V where lower values allow for more motion'),
                io.Float.Input('end_latent_strength', default=1.0, min=0.0, max=10.0, step=0.001, tooltip='Additional latent multiplier, helpful for I2V where lower values allow for more motion'),
                io.Boolean.Input('force_offload', default=True),
                io.Custom('WANVAE').Input('vae', optional=True),
                io.Custom('WANVIDIMAGE_CLIPEMBEDS').Input('clip_embeds', tooltip='Clip vision encoded image', optional=True),
                io.Image.Input('start_image', tooltip='Image to encode', optional=True),
                io.Image.Input('end_image', tooltip='end frame', optional=True),
                io.Custom('WANVIDIMAGE_EMBEDS').Input('control_embeds', tooltip='Control signal for the Fun -model', optional=True),
                io.Boolean.Input('fun_or_fl2v_model', default=True, tooltip='Enable when using official FLF2V or Fun model', optional=True),
                io.Mask.Input('temporal_mask', tooltip='mask', optional=True),
                io.Latent.Input('extra_latents', tooltip='Extra latents to add to the input front, used for Skyreels A2 reference images', optional=True),
                io.Boolean.Input('tiled_vae', default=False, tooltip='Use tiled VAE encoding for reduced memory use', optional=True),
                io.Custom('ADD_COND_LATENTS').Input('add_cond_latents', advanced=True, tooltip='Additional cond latents WIP', optional=True),
                io.Float.Input('augment_empty_frames', default=0.0, min=0.0, max=10.0, step=0.01, tooltip='EXPERIMENTAL: Augment empty frames with the difference to the start image to force more motion', optional=True),
                io.Image.Input('empty_frame_pad_image', tooltip='Use this image to pad empty frames instead of gray, used with SVI-shot and SVI 2.0 LoRAs', optional=True)],
            outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')])

    @classmethod
    async def execute(cls, width, height, num_frames, force_offload, noise_aug_strength, start_latent_strength, end_latent_strength, start_image=None, end_image=None, control_embeds=None, fun_or_fl2v_model=False, temporal_mask=None, extra_latents=None, clip_embeds=None, tiled_vae=False, add_cond_latents=None, vae=None, augment_empty_frames=0.0, empty_frame_pad_image=None):
        _i2v_boundary(width,height,num_frames,(start_image,end_image,empty_frame_pad_image),
                      temporal_mask,extra_latents,(control_embeds,clip_embeds,add_cond_latents))
        if vae is not None:
            vae, _ = await rebuild_full_vae(vae)
        with torch.inference_mode():
            if vae is None:
                raise ValueError('VAE is required for image encoding.')
            H = height
            W = width
            lat_h = H // vae.upsampling_factor
            lat_w = W // vae.upsampling_factor
            num_frames = (num_frames - 1) // 4 * 4 + 1
            two_ref_images = start_image is not None and end_image is not None
            if start_image is None and end_image is not None:
                fun_or_fl2v_model = True
            base_frames = num_frames + (1 if two_ref_images and (not fun_or_fl2v_model) else 0)
            if temporal_mask is None:
                mask = torch.zeros(1, base_frames, lat_h, lat_w, device=device, dtype=vae.dtype)
                if start_image is not None:
                    mask[:, 0:start_image.shape[0]] = 1
                if end_image is not None:
                    mask[:, -end_image.shape[0]:] = 1
            else:
                mask = common_upscale(temporal_mask.unsqueeze(1).to(device), lat_w, lat_h, 'nearest', 'disabled').squeeze(1)
                if mask.shape[0] > base_frames:
                    mask = mask[:base_frames]
                elif mask.shape[0] < base_frames:
                    mask = torch.cat([mask, torch.zeros(base_frames - mask.shape[0], lat_h, lat_w, device=device)])
                mask = mask.unsqueeze(0).to(device, vae.dtype)
            pixel_mask = mask.clone()
            start_mask_repeated = torch.repeat_interleave(mask[:, 0:1], repeats=4, dim=1)
            if end_image is not None and (not fun_or_fl2v_model):
                end_mask_repeated = torch.repeat_interleave(mask[:, -1:], repeats=4, dim=1)
                mask = torch.cat([start_mask_repeated, mask[:, 1:-1], end_mask_repeated], dim=1)
            else:
                mask = torch.cat([start_mask_repeated, mask[:, 1:]], dim=1)
            mask = mask.view(1, mask.shape[1] // 4, 4, lat_h, lat_w)
            mask = mask.movedim(1, 2)[0]
            if start_image is not None:
                start_image = start_image[..., :3]
                if start_image.shape[1] != H or start_image.shape[2] != W:
                    resized_start_image = common_upscale(start_image.movedim(-1, 1), W, H, 'lanczos', 'disabled').movedim(0, 1)
                else:
                    resized_start_image = start_image.permute(3, 0, 1, 2)
                resized_start_image = resized_start_image * 2 - 1
                if noise_aug_strength > 0.0:
                    resized_start_image = add_noise_to_reference_video(resized_start_image, ratio=noise_aug_strength)
            if end_image is not None:
                end_image = end_image[..., :3]
                if end_image.shape[1] != H or end_image.shape[2] != W:
                    resized_end_image = common_upscale(end_image.movedim(-1, 1), W, H, 'lanczos', 'disabled').movedim(0, 1)
                else:
                    resized_end_image = end_image.permute(3, 0, 1, 2)
                resized_end_image = resized_end_image * 2 - 1
                if noise_aug_strength > 0.0:
                    resized_end_image = add_noise_to_reference_video(resized_end_image, ratio=noise_aug_strength)
            if start_image is not None and end_image is None:
                zero_frames = torch.zeros(3, num_frames - start_image.shape[0], H, W, device=device, dtype=vae.dtype)
                concatenated = torch.cat([resized_start_image.to(device, dtype=vae.dtype), zero_frames], dim=1)
                del resized_start_image, zero_frames
            elif start_image is None and end_image is not None:
                zero_frames = torch.zeros(3, num_frames - end_image.shape[0], H, W, device=device, dtype=vae.dtype)
                concatenated = torch.cat([zero_frames, resized_end_image.to(device, dtype=vae.dtype)], dim=1)
                del zero_frames
            elif start_image is None and end_image is None:
                concatenated = torch.zeros(3, num_frames, H, W, device=device, dtype=vae.dtype)
            else:
                if fun_or_fl2v_model:
                    zero_frames = torch.zeros(3, num_frames - (start_image.shape[0] + end_image.shape[0]), H, W, device=device, dtype=vae.dtype)
                else:
                    zero_frames = torch.zeros(3, num_frames - 1, H, W, device=device, dtype=vae.dtype)
                concatenated = torch.cat([resized_start_image.to(device, dtype=vae.dtype), zero_frames, resized_end_image.to(device, dtype=vae.dtype)], dim=1)
                del resized_start_image, zero_frames
            if empty_frame_pad_image is not None:
                pad_img = empty_frame_pad_image.clone()[..., :3]
                if pad_img.shape[1] != H or pad_img.shape[2] != W:
                    pad_img = common_upscale(pad_img.movedim(-1, 1), W, H, 'lanczos', 'disabled').movedim(1, -1)
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
            gc.collect()
            vae.to(device)
            y = vae.encode([concatenated], device, end_=end_image is not None and (not fun_or_fl2v_model), tiled=tiled_vae)[0]
            del concatenated
            has_ref = False
            if extra_latents is not None:
                samples = extra_latents['samples'].squeeze(0)
                y = torch.cat([samples, y], dim=1)
                mask = torch.cat([torch.ones_like(mask[:, 0:samples.shape[1]]), mask], dim=1)
                num_frames += samples.shape[1] * 4
                has_ref = True
            y[:, :1] *= start_latent_strength
            y[:, -1:] *= end_latent_strength
            if augment_empty_frames > 0.0:
                frame_is_empty = (mask[0].mean(dim=(-2, -1)) < 0.5).view(1, -1, 1, 1)
                y = y[:, :1] + (y - y[:, :1]) * ((augment_empty_frames + 1) * frame_is_empty + ~frame_is_empty)
            patches_per_frame = lat_h * lat_w // (PATCH_SIZE[1] * PATCH_SIZE[2])
            frames_per_stride = (num_frames - 1) // 4 + (2 if end_image is not None and (not fun_or_fl2v_model) else 1)
            max_seq_len = frames_per_stride * patches_per_frame
            if add_cond_latents is not None:
                add_cond_latents['ref_latent_neg'] = vae.encode(torch.zeros(1, 3, 1, H, W, device=device, dtype=vae.dtype), device)
            if force_offload:
                vae.model.to(offload_device)
                gc.collect()
            image_embeds = {'image_embeds': y.cpu(), 'clip_context': clip_embeds.get('clip_embeds', None) if clip_embeds is not None else None, 'negative_clip_context': clip_embeds.get('negative_clip_embeds', None) if clip_embeds is not None else None, 'max_seq_len': max_seq_len, 'num_frames': num_frames, 'lat_h': lat_h, 'lat_w': lat_w, 'control_embeds': control_embeds['control_embeds'] if control_embeds is not None else None, 'end_image': resized_end_image if end_image is not None else None, 'fun_or_fl2v_model': fun_or_fl2v_model, 'has_ref': has_ref, 'add_cond_latents': add_cond_latents, 'mask': mask.cpu()}
        _bound_payload(image_embeds)
        return io.NodeOutput(image_embeds)

NODE_CLASS_MAPPINGS = {'WanVideoImageToVideoEncode':WanVideoImageToVideoEncode}
