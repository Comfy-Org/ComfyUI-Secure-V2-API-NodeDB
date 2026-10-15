"""Original Mocha reference conditioning through the bounded full VAE recipe.

Unpromoted candidate; original native and shared numerical gates required.
"""
import gc
import torch
from comfy_api.latest import io
from .secure_tensor_nodes import _bound_payload
from .secure_full_vae_nodes import rebuild_full_vae
from .secure_full_vae_encode import _image

device = offload_device = torch.device('cpu')

def _mocha_boundary(input_video,mask,ref1,ref2):
    _bound_payload({'video':input_video,'mask':mask,'ref1':ref1,'ref2':ref2})
    images=[input_video,ref1]+([ref2] if ref2 is not None else [])
    for value in images:
        _image(value)
    if not 64<=input_video.shape[1]<=512 or not 64<=input_video.shape[2]<=512:
        raise ValueError('Mocha output dimensions exceed bounded CPU domain')
    if (not isinstance(mask,torch.Tensor) or mask.device.type!='cpu' or mask.layout!=torch.strided
            or mask.ndim!=3 or not 1<=mask.shape[0]<=64 or not all(1<=n<=512 for n in mask.shape[1:])):
        raise ValueError('Mocha requires bounded dense CPU THW masks')
    if sum(v.numel()*max(4,v.element_size())*4 for v in images)>64*1024*1024:
        raise ValueError('Mocha projected working images exceed 64 MiB')

class MochaEmbeds(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw','assets','models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='MochaEmbeds',display_name='Mocha Embeds',category='WanVideoWrapper',
            description='Input for MoCha model: https://github.com/Orange-3DV-Team/MoCha',
            inputs=[io.Custom('WANVAE').Input('vae'),
                io.Boolean.Input('force_offload', default=True),
                io.Image.Input('input_video', tooltip='Input video to encode'),
                io.Mask.Input('mask', tooltip='mask'),
                io.Image.Input('ref1', tooltip='Image to encode'),
                io.Image.Input('ref2', tooltip='Image to encode', optional=True),
                io.Boolean.Input('tiled_vae', default=False, tooltip='Use tiled VAE encoding for reduced memory use', optional=True)],outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')])

    @classmethod
    async def execute(cls, vae, force_offload, input_video, mask, ref1, ref2=None, tiled_vae=False):
        _mocha_boundary(input_video,mask,ref1,ref2)
        vae, _ = await rebuild_full_vae(vae)
        with torch.inference_mode():
            W = input_video.shape[2]
            H = input_video.shape[1]
            F = input_video.shape[0]
            lat_h = H // vae.upsampling_factor
            lat_w = W // vae.upsampling_factor
            F = (F - 1) // 4 * 4 + 1
            input_video = input_video.clone()[:F]
            gc.collect()
            vae.to(device)
            input_video = input_video.clone()[..., :3].to(device, vae.dtype).unsqueeze(0).permute(0, 4, 1, 2, 3)
            ref1 = ref1.clone()[..., :3].to(device, vae.dtype).unsqueeze(0).permute(0, 4, 1, 2, 3)
            if ref2 is not None:
                ref2 = ref2.clone()[..., :3].to(device, vae.dtype).unsqueeze(0).permute(0, 4, 1, 2, 3)
            latents = vae.encode(input_video * 2.0 - 1.0, device, tiled=tiled_vae)
            ref_latents = vae.encode(ref1 * 2.0 - 1.0, device, tiled=tiled_vae)
            num_refs = 1
            if ref2 is not None:
                ref2_latents = vae.encode(ref2 * 2.0 - 1.0, device, tiled=tiled_vae)
                ref_latents = torch.cat([ref_latents, ref2_latents], dim=2)
                num_refs = 2
            input_latent_mask = torch.nn.functional.interpolate(mask.unsqueeze(1).to(vae.dtype), size=(lat_h, lat_w), mode='nearest').unsqueeze(1)
            input_latent_mask = input_latent_mask.repeat(1, 16, 1, 1, 1).to(device, vae.dtype)
            input_latent_mask[input_latent_mask <= 0.5] = 0
            input_latent_mask[input_latent_mask > 0.5] = 1
            input_latent_mask[input_latent_mask == 0] = -1
            mocha_embeds = torch.cat([latents, input_latent_mask, ref_latents], dim=2)
            mocha_embeds = mocha_embeds[0]
            target_shape = (16, (F - 1) // 4 + 1, lat_h, lat_w)
            seq_len = (target_shape[1] * 2 + 1 + num_refs) * (target_shape[2] * target_shape[3] // 4)
            if force_offload:
                vae.model.to(offload_device)
                gc.collect()
            image_embeds = {'seq_len': seq_len, 'mocha_embeds': mocha_embeds, 'num_frames': F, 'target_shape': target_shape, 'mocha_num_refs': num_refs}
        _bound_payload(image_embeds)
        return io.NodeOutput(image_embeds)

NODE_CLASS_MAPPINGS = {'MochaEmbeds':MochaEmbeds}
