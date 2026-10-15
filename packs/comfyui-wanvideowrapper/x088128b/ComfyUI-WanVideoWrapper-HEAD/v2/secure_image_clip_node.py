"""Original deprecated Wan image/CLIP adapter; inference qualification pending."""
import torch
from comfy_api.latest import io, sdk
from .secure_tensor_nodes import _bound_payload
from .secure_full_vae_nodes import rebuild_full_vae
from .secure_clip_vision_nodes import check_images, raw_image
from .secure_vision_algorithms import _encode_tokens
from .secure_wan_clip_preprocess import clip_preprocess
from .secure_wan_clip_resource import rebuild_wan_clip
from .secure_image_clip_algorithm import image_clip_latents


class WanVideoImageClipEncode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets', 'models', 'models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoImageClipEncode', display_name='WanVideo ImageClip Encode (Deprecated)',
            category='WanVideoWrapper', is_deprecated=True,
            inputs=[io.Custom('CLIP_VISION').Input('clip_vision'), io.Image.Input('image', tooltip='Image to encode'),
                io.Custom('WANVAE').Input('vae'),
                io.Int.Input('generation_width', default=832, min=64, max=8096, step=8, tooltip='Width of the image to encode'),
                io.Int.Input('generation_height', default=480, min=64, max=8096, step=8, tooltip='Height of the image to encode'),
                io.Int.Input('num_frames', default=81, min=1, max=10000, step=4, tooltip='Number of frames to encode'),
                io.Boolean.Input('force_offload', default=True, optional=True),
                io.Float.Input('noise_aug_strength', default=0.0, min=0.0, max=10.0, step=0.001, optional=True, tooltip='Strength of noise augmentation, helpful for I2V where some noise can add motion and give sharper results'),
                io.Float.Input('latent_strength', default=1.0, min=0.0, max=10.0, step=0.001, optional=True, tooltip='Additional latent multiplier, helpful for I2V where lower values allow for more motion'),
                io.Float.Input('clip_embed_strength', default=1.0, min=0.0, max=10.0, step=0.001, optional=True, tooltip='Additional clip embed multiplier'),
                io.Boolean.Input('adjust_resolution', default=True, optional=True, tooltip='Performs the same resolution adjustment as in the original code')],
            outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')])

    @classmethod
    async def execute(cls, clip_vision, vae, image, num_frames, generation_width, generation_height, force_offload=True, noise_aug_strength=0.0, latent_strength=1.0, clip_embed_strength=1.0, adjust_resolution=True):
        image = await raw_image(image)
        check_images(image, 0)
        if (any(type(value) is not int for value in (num_frames, generation_width, generation_height))
                or not 1 <= num_frames <= 64 or not 64 <= generation_width <= 512 or not 64 <= generation_height <= 512):
            raise ValueError('Deprecated Wan image encoding exceeds bounded CPU dimensions')
        if (num_frames+2*image.shape[0])*generation_width*generation_height*3*4*4 > 64*1024*1024:
            raise ValueError('Deprecated Wan projected image work exceeds 64 MiB')
        if isinstance(clip_vision, sdk.ClipVisionRef):
            clip_context = await _encode_tokens(clip_vision, image, last=True)
            if clip_embed_strength != 1.0:
                clip_context *= clip_embed_strength
            if force_offload:
                await clip_vision.offload()
        else:
            clip_model, _ = await rebuild_wan_clip(clip_vision)
            with torch.inference_mode():
                clip_context = clip_model.visual(clip_preprocess(image, size=224, crop=True).float())
                if clip_embed_strength != 1.0:
                    clip_context *= clip_embed_strength
            if force_offload:
                clip_model.model.to(torch.device('cpu'))
            del clip_model
        model, _ = await rebuild_full_vae(vae)
        with torch.inference_mode():
            result = image_clip_latents(clip_context, model, image, num_frames, generation_width,
                generation_height, force_offload, noise_aug_strength, latent_strength,
                clip_embed_strength, adjust_resolution)
        _bound_payload(result)
        return io.NodeOutput(await sdk.ValueRef.from_value(result))


NODE_CLASS_MAPPINGS = {'WanVideoImageClipEncode': WanVideoImageClipEncode}
