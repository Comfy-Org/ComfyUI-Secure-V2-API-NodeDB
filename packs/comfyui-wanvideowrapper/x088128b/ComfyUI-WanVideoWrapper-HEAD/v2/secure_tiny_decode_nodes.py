"""Actual Wan decoder for digest-bound Tiny and full VAE recipes on the raw boundary.

Full WanVideoVAE recipe branch is a candidate pending qualification. Tiny behavior preserves
the pinned wrapper's early return, including its ignored tiling/normalization.
"""
from comfy_api.latest import io
from .secure_tiny_vae_nodes import rebuild_tiny_vae
from .secure_tensor_nodes import _bound_payload, MAX_PAYLOAD_BYTES


class WanVideoDecode(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets', 'models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoDecode', display_name='WanVideo Decode', category='WanVideoWrapper',
            inputs=[io.Custom('WANVAE').Input('vae'), io.Latent.Input('samples'),
                    io.Boolean.Input('enable_vae_tiling', default=False,
                        tooltip='Drastically reduces memory use but will introduce seams at tile stride boundaries. The location and number of seams is dictated by the tile stride size. The visibility of seams can be controlled by increasing the tile size. Seams become less obvious at 1.5x stride and are barely noticeable at 2x stride size. Which is to say if you use a stride width of 160, the seams are barely noticeable with a tile width of 320.'),
                    io.Int.Input('tile_x', default=272, min=40, max=2048, step=8, tooltip='Tile width in pixels. Smaller values use less VRAM but will make seams more obvious.'),
                    io.Int.Input('tile_y', default=272, min=40, max=2048, step=8, tooltip='Tile height in pixels. Smaller values use less VRAM but will make seams more obvious.'),
                    io.Int.Input('tile_stride_x', default=144, min=32, max=2040, step=8, tooltip='Tile stride width in pixels. Smaller values use less VRAM but will introduce more seams.'),
                    io.Int.Input('tile_stride_y', default=128, min=32, max=2040, step=8, tooltip='Tile stride height in pixels. Smaller values use less VRAM but will introduce more seams.'),
                    io.Combo.Input('normalization', options=['default', 'minmax', 'none'], optional=True, advanced=True)],
            outputs=[io.Image.Output(display_name='images')])

    @classmethod
    def validate_inputs(cls, tile_x, tile_y, tile_stride_x, tile_stride_y, **kwargs):
        if tile_x <= tile_stride_x:
            return 'Tile width must be larger than the tile stride width.'
        if tile_y <= tile_stride_y:
            return 'Tile height must be larger than the tile stride height.'
        return True

    @classmethod
    async def execute(cls, vae, samples, enable_vae_tiling, tile_x, tile_y, tile_stride_x, tile_stride_y, normalization='default'):
        import torch
        _bound_payload(samples)
        if not isinstance(samples, dict):
            raise TypeError('Wan decoder requires a plain raw latent dictionary')
        video = samples.get('video', None)
        if video is not None:
            if not isinstance(video, torch.Tensor) or video.device.type != 'cpu' or video.layout != torch.strided:
                raise ValueError('Wan video passthrough requires a dense CPU tensor')
            video.clamp_(-1.0, 1.0)
            video.add_(1.0).div_(2.0)
            return io.NodeOutput(video.cpu().float())
        latent = samples['samples']
        if not isinstance(latent, torch.Tensor) or latent.device.type != 'cpu' or latent.layout != torch.strided or latent.ndim != 5:
            raise ValueError('Wan Tiny decoder requires dense CPU BCTHW latent samples')
        b, c, t, h, w = latent.shape
        if min(b, c, t, h, w) < 1 or max(h, w) > 64 or t > 64 or b > 4:
            raise ValueError('Wan Tiny decoder exceeds bounded latent dimensions')
        if b * t * 4 * h * 8 * w * 8 * 3 * 4 > MAX_PAYLOAD_BYTES:
            raise ValueError('Wan Tiny projected decoded buffers exceed64MiB')
        if isinstance(vae, dict) and vae.get('format') == 'wan-full-vae-recipe-v1':
            from .secure_full_vae_nodes import full_decode
            if b * t * 4 * h * 16 * w * 16 * 3 * 4 > MAX_PAYLOAD_BYTES:
                raise ValueError('Wan full projected decoded buffers exceed64MiB')
            return await full_decode(vae, latent, samples, enable_vae_tiling, tile_x, tile_y, tile_stride_x, tile_stride_y, normalization)
        model, _, _ = await rebuild_tiny_vae(vae)
        if c != model.latent_channels:
            raise ValueError('Wan latent channels do not match the selected Tiny VAE')
        latents = latent.clone().to(device='cpu', dtype=model.dtype)
        if samples.get('has_ref', False):
            latents = latents[:, :, 1:]
        if samples.get('drop_last', False):
            latents = latents[:, :, :-1]
        if latents.shape[2] == 0:
            raise ValueError('Wan reference/drop flags leave no latent frames')
        flashvsr_LQ_images = samples.get('flashvsr_LQ_images', None)
        with torch.inference_mode():
            images = model.decode_video(latents.permute(0, 2, 1, 3, 4), cond=flashvsr_LQ_images.to(model.dtype) if flashvsr_LQ_images is not None else None)[0].permute(1, 0, 2, 3)
            images = torch.clamp(images, 0.0, 1.0)
            images = images.permute(1, 2, 3, 0).cpu().float()
        return io.NodeOutput(images)


NODE_CLASS_MAPPINGS = {'WanVideoDecode': WanVideoDecode}
