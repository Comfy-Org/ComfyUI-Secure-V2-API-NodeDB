"""Original LongVie2 dual control through the owned full VAE recipe.

Staged source only; native and converted numerical qualification are separate.
"""
from comfy_api.latest import io
from .secure_tensor_nodes import _bound_payload
from .secure_full_vae_nodes import rebuild_full_vae
from .secure_full_vae_encode import _image


class WanVideoAddDualControlEmbeds(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets', 'models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoAddDualControlEmbeds',
            display_name='WanVideo Add Dual Control Embeds', category='WanVideoWrapper',
            inputs=[io.Custom('WANVIDIMAGE_EMBEDS').Input('embeds'),
                    io.Custom('WANVAE').Input('vae', tooltip='VAE model'),
                    io.Float.Input('strength', default=1.0, min=0.0, max=10.0, step=0.01, tooltip='Strength of the reference embedding'),
                    io.Float.Input('start_percent', default=0.0, min=0.0, max=1.0, step=0.01, tooltip='Start percentage of the embedding application'),
                    io.Float.Input('end_percent', default=1.0, min=0.0, max=1.0, step=0.01, tooltip='End percentage of the embedding application'),
                    io.Float.Input('first_frame_noise_level', default=0.925926, min=0.0, max=1.0, step=0.000001, tooltip='Noise level for the first frame when using previous frames'),
                    io.Image.Input('dense', optional=True, tooltip='Dense control signal (depth) video input'),
                    io.Image.Input('sparse', optional=True, tooltip='Sparse control signal (tracks) video input'),
                    io.Image.Input('prev_images', optional=True, tooltip='Previous frames for temporal consistency, default is 8 frames')],
            outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')])

    @classmethod
    async def execute(cls, embeds, vae, strength, start_percent, end_percent, first_frame_noise_level,
                      dense=None, sparse=None, prev_images=None):
        import torch
        _bound_payload({'embeds': embeds, 'dense': dense, 'sparse': sparse, 'prev_images': prev_images})
        updated = dict(embeds)
        updated.setdefault('dual_control', {})

        if dense is None and sparse is None:
            raise ValueError('At least one of dense or sparse inputs must be provided.')

        for image in (dense, sparse, prev_images):
            if image is not None:
                _image(image)
        model, _ = await rebuild_full_vae(vae)
        with torch.inference_mode():
            num_frames = dense.shape[0] if dense is not None else sparse.shape[0]
            height = dense.shape[1] if dense is not None else sparse.shape[1]
            width = dense.shape[2] if dense is not None else sparse.shape[2]
            msk = torch.ones(1, num_frames, height//8, width//8, device=torch.device('cpu'))
            msk[:, 1:] = 0
            msk = torch.concat([torch.repeat_interleave(msk[:, 0:1], repeats=4, dim=1), msk[:, 1:]], dim=1)
            msk = msk.view(1, msk.shape[1] // 4, 4, height//8, width//8)
            msk = msk.transpose(1, 2)

            dense_input_latent = sparse_input_latent = None
            if dense is not None:
                dense_images = 1 - dense[..., :3]
                dense_images = dense_images.permute(3, 0, 1, 2) * 2 - 1
                dense_video_latent = model.encode([dense_images.to(torch.device('cpu'), model.dtype)], torch.device('cpu'), tiled=False)
                dense_first = (dense_images[:, :1]).to(torch.device('cpu'), model.dtype)
                vae_input_dense = torch.cat([dense_first, torch.zeros(3, num_frames-1, height, width, device=torch.device('cpu'), dtype=model.dtype)], dim=1)
                dense_concat_latent = model.encode([vae_input_dense], torch.device('cpu'), tiled=False)
                dense_concat_latent = torch.cat([msk, dense_concat_latent], dim=1)
                dense_input_latent = torch.cat([dense_video_latent, dense_concat_latent], dim=1)
            if sparse is not None:
                sparse_images = sparse[..., :3].permute(3, 0, 1, 2) * 2 - 1
                sparse_video_latent = model.encode([sparse_images.to(torch.device('cpu'), model.dtype)], torch.device('cpu'), tiled=False)
                sparse_first = (sparse_images[:, :1]).to(torch.device('cpu'), model.dtype)
                vae_input_sparse = torch.cat([sparse_first, torch.zeros(3, num_frames-1, height, width, device=torch.device('cpu'), dtype=model.dtype)], dim=1)
                sparse_concat_latent = model.encode([vae_input_sparse], torch.device('cpu'), tiled=False)
                sparse_concat_latent = torch.cat([msk, sparse_concat_latent], dim=1)
                sparse_input_latent = torch.cat([sparse_video_latent, sparse_concat_latent], dim=1)

            if prev_images is not None:
                prev_images = prev_images[..., :3].permute(3, 0, 1, 2) * 2 - 1
                prev_video_latent = model.encode([prev_images.to(torch.device('cpu'), model.dtype)], torch.device('cpu'), tiled=False)
                updated['dual_control']['prev_latent'] = prev_video_latent[0]

            updated['dual_control']['dense_input_latent'] = dense_input_latent
            updated['dual_control']['sparse_input_latent'] = sparse_input_latent
            updated['dual_control']['strength'] = strength
            updated['dual_control']['start_percent'] = start_percent
            updated['dual_control']['end_percent'] = end_percent
            updated['dual_control']['first_frame_noise_level'] = first_frame_noise_level
        _bound_payload(updated)
        return io.NodeOutput(updated)


NODE_CLASS_MAPPINGS = {'WanVideoAddDualControlEmbeds': WanVideoAddDualControlEmbeds}
