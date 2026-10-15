"""Native Wan image/video and independent image-batch encoding, raw CPU boundary."""
import logging
from comfy_api.latest import io
from .secure_tensor_nodes import _bound_payload
from .secure_full_vae_nodes import rebuild_full_vae
from .secure_tiny_vae_nodes import rebuild_tiny_vae
from ._wan_resize import common_upscale

log = logging.getLogger(__name__)


def _image(value, mask=None):
    import torch
    _bound_payload({'image': value, 'mask': mask})
    if not isinstance(value, torch.Tensor) or value.device.type != 'cpu' or value.layout != torch.strided or value.ndim != 4:
        raise ValueError('Wan encode requires dense CPU THWC image frames')
    t, h, w, c = value.shape
    if not 1 <= t <= 64 or not 16 <= h <= 1024 or not 16 <= w <= 1024 or c not in (3, 4):
        raise ValueError('Wan encode exceeds bounded RGB/RGBA frame dimensions')
    if value.numel() * max(4, value.element_size()) * 3 > 64 * 1024 * 1024:
        raise ValueError('Wan encode projected working images exceed 64 MiB')


def add_noise_to_reference_video(image, ratio=None):
    import torch
    sigma = torch.ones((image.shape[0],)).to(image.device, image.dtype) * ratio
    image_noise = torch.randn_like(image) * sigma[:, None, None, None]
    image_noise = torch.where(image == -1, torch.zeros_like(image), image_noise)
    image = image + image_noise
    return image


def _tiles():
    return [io.Boolean.Input('enable_vae_tiling', default=False, tooltip='Drastically reduces memory use but may introduce seams'),
            io.Int.Input('tile_x', default=272, min=64, max=2048, step=1, tooltip='Tile size in pixels, smaller values use less VRAM, may introduce more seams'),
            io.Int.Input('tile_y', default=272, min=64, max=2048, step=1, tooltip='Tile size in pixels, smaller values use less VRAM, may introduce more seams'),
            io.Int.Input('tile_stride_x', default=144, min=32, max=2048, step=32, tooltip='Tile stride in pixels, smaller values use less VRAM, may introduce more seams'),
            io.Int.Input('tile_stride_y', default=128, min=32, max=2048, step=32, tooltip='Tile stride in pixels, smaller values use less VRAM, may introduce more seams')]


class WanVideoEncode(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets', 'models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoEncode', display_name='WanVideo Encode', category='WanVideoWrapper',
                         inputs=[io.Custom('WANVAE').Input('vae'), io.Image.Input('image'), *_tiles(),
                                 io.Float.Input('noise_aug_strength', optional=True, default=0.0, min=0.0, max=10.0, step=0.001, tooltip='Strength of noise augmentation, helpful for leapfusion I2V where some noise can add motion and give sharper results'),
                                 io.Float.Input('latent_strength', optional=True, default=1.0, min=0.0, max=10.0, step=0.001, tooltip='Additional latent multiplier, helpful for leapfusion I2V where lower values allow for more motion'),
                                 io.Mask.Input('mask', optional=True)], outputs=[io.Latent.Output(display_name='samples')])

    @classmethod
    async def execute(cls, vae, image, enable_vae_tiling, tile_x, tile_y, tile_stride_x, tile_stride_y, noise_aug_strength=0.0, latent_strength=1.0, mask=None):
        import torch
        _image(image, mask)
        tiny = isinstance(vae, dict) and vae.get('format') == 'wan-tiny-vae-recipe-v1'
        if tiny:
            model, _, _ = await rebuild_tiny_vae(vae)
        else:
            model, _ = await rebuild_full_vae(vae)
        image = image.clone()
        b, h, w, c = image.shape
        if w % 16 != 0 or h % 16 != 0:
            image = common_upscale(image.movedim(-1, 1), (w//16)*16, (h//16)*16, 'lanczos', 'disabled').movedim(1, -1)
        if image.shape[-1] == 4:
            image = image[..., :3]
        image = image.to(model.dtype).to('cpu').unsqueeze(0).permute(0, 4, 1, 2, 3)
        with torch.inference_mode():
            if noise_aug_strength > 0.0:
                image = add_noise_to_reference_video(image, ratio=noise_aug_strength)
            if tiny:
                latents = model.encode_video(image.permute(0, 2, 1, 3, 4), parallel=False)
                latents = latents.permute(0, 2, 1, 3, 4)
            else:
                latents = model.encode(image * 2.0 - 1.0, device=torch.device('cpu'), tiled=enable_vae_tiling,
                                       tile_size=(tile_x//model.upsampling_factor, tile_y//model.upsampling_factor),
                                       tile_stride=(tile_stride_x//model.upsampling_factor, tile_stride_y//model.upsampling_factor))
            if latent_strength != 1.0:
                latents *= latent_strength
            latents = latents.cpu()
        return io.NodeOutput({'samples': latents, 'noise_mask': mask})


class WanVideoEncodeLatentBatch(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets', 'models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoEncodeLatentBatch', display_name='WanVideo Encode Latent Batch', category='WanVideoWrapper',
                         description='Encodes a batch of images individually to create a latent video batch where each video is a single frame, useful for I2V init purposes, for example as multiple context window inits',
                         inputs=[io.Custom('WANVAE').Input('vae'), io.Image.Input('images'), *_tiles()],
                         outputs=[io.Latent.Output(display_name='samples')])

    @classmethod
    async def execute(cls, vae, images, enable_vae_tiling=False, tile_x=272, tile_y=272, tile_stride_x=144, tile_stride_y=128, latent_strength=1.0):
        import torch
        _image(images)
        model, _ = await rebuild_full_vae(vae)
        images = images.clone()
        b, h, w, c = images.shape
        if w % 16 != 0 or h % 16 != 0:
            images = common_upscale(images.movedim(-1, 1), (w//16)*16, (h//16)*16, 'lanczos', 'disabled').movedim(1, -1)
        if images.shape[-1] == 4:
            images = images[..., :3]
        images = images.to(model.dtype).to('cpu') * 2.0 - 1.0
        latent_list = []
        with torch.inference_mode():
            for img in images:
                if enable_vae_tiling and tile_x is not None:
                    latent = model.encode(img.unsqueeze(0).unsqueeze(0).permute(0, 4, 1, 2, 3), device=torch.device('cpu'), tiled=enable_vae_tiling,
                                          tile_size=(tile_x//model.upsampling_factor, tile_y//model.upsampling_factor),
                                          tile_stride=(tile_stride_x//model.upsampling_factor, tile_stride_y//model.upsampling_factor))
                else:
                    latent = model.encode(img.unsqueeze(0).unsqueeze(0).permute(0, 4, 1, 2, 3), device=torch.device('cpu'), tiled=enable_vae_tiling)
                if latent_strength != 1.0:
                    latent *= latent_strength
                latent_list.append(latent.squeeze(0).cpu())
            latents_out = torch.stack(latent_list, dim=0)
        return io.NodeOutput({'samples': latents_out})


NODE_CLASS_MAPPINGS = {'WanVideoEncode': WanVideoEncode, 'WanVideoEncodeLatentBatch': WanVideoEncodeLatentBatch}
