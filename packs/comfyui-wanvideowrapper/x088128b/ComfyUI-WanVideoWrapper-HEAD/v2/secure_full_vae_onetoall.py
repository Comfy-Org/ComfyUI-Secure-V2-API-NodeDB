"""Original OneToAll reference conditioning through the full VAE recipe.

Staged source only; converted numerical qualification is still required.
"""
from comfy_api.latest import io
from .secure_tensor_nodes import _bound_payload
from .secure_full_vae_nodes import rebuild_full_vae
from .secure_full_vae_encode import _image


class WanVideoAddOneToAllReferenceEmbeds(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets', 'models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoAddOneToAllReferenceEmbeds',
            display_name='WanVideo Add OneToAll Reference Embeds', category='WanVideoWrapper',
            inputs=[io.Custom('WANVIDIMAGE_EMBEDS').Input('embeds'),
                    io.Custom('WANVAE').Input('vae', tooltip='VAE model'),
                    io.Image.Input('ref_image'),
                    io.Float.Input('strength', default=1.0, min=0.0, max=10.0, step=0.01, tooltip='Strength of the reference embedding'),
                    io.Float.Input('start_percent', default=0.0, min=0.0, max=1.0, step=0.01, tooltip='Start percentage of the embedding application'),
                    io.Float.Input('end_percent', default=1.0, min=0.0, max=1.0, step=0.01, tooltip='End percentage of the embedding application'),
                    io.Mask.Input('ref_mask', optional=True)],
            outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')])

    @classmethod
    async def execute(cls, embeds, vae, ref_image, strength, start_percent, end_percent, ref_mask=None):
        import torch
        _bound_payload(embeds)
        _image(ref_image, ref_mask)
        model, _ = await rebuild_full_vae(vae)
        with torch.inference_mode():
            updated = dict(embeds)
            ref_latent = ref_latent_empty = None
            ref_image_in = (ref_image[..., :3].permute(3, 0, 1, 2) * 2 - 1).to(torch.device('cpu'), model.dtype)
            ref_latent = model.encode([ref_image_in], torch.device('cpu'), tiled=False)
            ref_mask_in = None
            if ref_mask is not None:
                ref_mask_in = (ref_mask.unsqueeze(0).repeat(3, 1, 1, 1) * 2 - 1.).to(torch.device('cpu'), model.dtype)
            else:
                ref_mask_in = torch.zeros_like(ref_image_in)-1
            ref_mask_latent = model.encode([ref_mask_in], torch.device('cpu'), tiled=False)

            if ref_mask is not None and not torch.all(ref_mask == 0):
                ref_latent_empty = model.encode([torch.zeros_like(ref_image_in)-1], torch.device('cpu'), tiled=False)
            else:
                ref_latent_empty = ref_mask_latent

            updated.setdefault('one_to_all_embeds', {})
            updated['one_to_all_embeds']['ref_latent_pos'] = torch.cat([ref_latent, ref_latent_empty], dim=1)
            updated['one_to_all_embeds']['ref_latent_neg'] = torch.cat([ref_latent_empty, ref_latent_empty], dim=1)
            updated['one_to_all_embeds']['ref_strength'] = strength
            updated['one_to_all_embeds']['ref_start_percent'] = start_percent
            updated['one_to_all_embeds']['ref_end_percent'] = end_percent
        _bound_payload(updated)
        return io.NodeOutput(updated)


NODE_CLASS_MAPPINGS = {'WanVideoAddOneToAllReferenceEmbeds': WanVideoAddOneToAllReferenceEmbeds}
