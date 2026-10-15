"""Native SCAIL and StoryMem conditioning through the owned full VAE recipe.

Candidate source only: original-model numerical qualification remains required.
"""
import logging
from comfy_api.latest import io
from .secure_tensor_nodes import _bound_payload
from .secure_full_vae_nodes import rebuild_full_vae
from .secure_full_vae_encode import _image, WanVideoEncodeLatentBatch

log = logging.getLogger(__name__)


def _scail_inputs(image_name, image_tooltip=None):
    options = {'tooltip': image_tooltip} if image_tooltip else {}
    return [io.Custom('WANVIDIMAGE_EMBEDS').Input('embeds'),
            io.Custom('WANVAE').Input('vae', tooltip='VAE model'),
            io.Image.Input(image_name, **options)]


class WanVideoAddSCAILReferenceEmbeds(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets', 'models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoAddSCAILReferenceEmbeds',
                         display_name='WanVideo Add SCAIL Reference Embeds', category='WanVideoWrapper',
                         inputs=[*_scail_inputs('ref_image'),
                                 io.Float.Input('strength', default=1.0, min=0.0, max=10.0, step=0.01, tooltip='Strength of the reference embedding'),
                                 io.Float.Input('start_percent', default=0.0, min=0.0, max=1.0, step=0.01, tooltip='Start percentage of the embedding application'),
                                 io.Float.Input('end_percent', default=1.0, min=0.0, max=1.0, step=0.01, tooltip='End percentage of the embedding application'),
                                 io.Custom('WANVIDIMAGE_CLIPEMBEDS').Input('clip_embeds', optional=True, tooltip='Clip vision encoded image')],
                         outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')])

    @classmethod
    async def execute(cls, embeds, vae, ref_image, strength, start_percent, end_percent, clip_embeds=None):
        import torch
        _bound_payload({'embeds': embeds, 'clip_embeds': clip_embeds})
        _image(ref_image)
        model, _ = await rebuild_full_vae(vae)
        updated = dict(embeds)
        with torch.inference_mode():
            ref_image_in = (ref_image[..., :3].permute(3, 0, 1, 2) * 2 - 1).to('cpu', model.dtype)
            ref_latent = model.encode([ref_image_in], torch.device('cpu'), tiled=False)[0]
            log.info(f"SCAIL ref_latent shape: {ref_latent.shape}")
            ref_mask = torch.ones_like(ref_latent[:4])
            ref_latent = torch.cat([ref_latent, ref_mask], dim=0)
            updated.setdefault('scail_embeds', {})
            updated['scail_embeds']['ref_latent_pos'] = ref_latent * strength
            updated['scail_embeds']['ref_latent_neg'] = torch.zeros_like(ref_latent)
            updated['scail_embeds']['ref_start_percent'] = start_percent
            updated['scail_embeds']['ref_end_percent'] = end_percent
            updated['clip_context'] = clip_embeds.get('clip_embeds', None) if clip_embeds is not None else None
        _bound_payload(updated)
        return io.NodeOutput(updated)


class WanVideoAddSCAILPoseEmbeds(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets', 'models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoAddSCAILPoseEmbeds',
                         display_name='WanVideo Add SCAIL Pose Embeds', category='WanVideoWrapper',
                         inputs=[*_scail_inputs('pose_images', 'Pose images for the entire video'),
                                 io.Float.Input('strength', default=1.0, min=0.0, max=10.0, step=0.01, tooltip='Strength of the pose control'),
                                 io.Float.Input('start_percent', default=0.0, min=0.0, max=1.0, step=0.01, tooltip='Start percentage of the pose control application'),
                                 io.Float.Input('end_percent', default=1.0, min=0.0, max=1.0, step=0.01, tooltip='End percentage of the pose control application')],
                         outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')])

    @classmethod
    async def execute(cls, embeds, vae, pose_images, strength, start_percent=0.0, end_percent=1.0):
        import torch
        _bound_payload(embeds)
        _image(pose_images)
        model, _ = await rebuild_full_vae(vae)
        updated = dict(embeds)
        with torch.inference_mode():
            pose_images_in = (pose_images[..., :3].permute(3, 0, 1, 2) * 2 - 1).to('cpu', model.dtype)
            pose_latent = model.encode([pose_images_in], torch.device('cpu'), tiled=False)[0]
            pose_mask = torch.ones_like(pose_latent[:4])
            pose_latent = torch.cat([pose_latent, pose_mask], dim=0)
            log.info(f"SCAIL pose_latent shape: {pose_latent.shape}")
            updated.setdefault('scail_embeds', {})
            updated['scail_embeds']['pose_latent'] = pose_latent
            updated['scail_embeds']['pose_strength'] = strength
            updated['scail_embeds']['pose_start_percent'] = start_percent
            updated['scail_embeds']['pose_end_percent'] = end_percent
        _bound_payload(updated)
        return io.NodeOutput(updated)


class WanVideoAddStoryMemLatents(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets', 'models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoAddStoryMemLatents',
                         display_name='WanVideo Add StoryMem Latents', category='WanVideoWrapper',
                         inputs=[io.Custom('WANVAE').Input('vae'),
                                 io.Custom('WANVIDIMAGE_EMBEDS').Input('embeds'),
                                 io.Image.Input('memory_images'),
                                 io.Boolean.Input('rope_negative_offset', default=False, tooltip='Use positive RoPE frequency offset for the memory latents'),
                                 io.Int.Input('rope_negative_offset_frames', default=5, min=0, max=100, step=1, tooltip='RoPE frequency offset for the memory latents')],
                         outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')])

    @classmethod
    async def execute(cls, vae, embeds, memory_images, rope_negative_offset, rope_negative_offset_frames):
        _bound_payload(embeds)
        updated = dict(embeds)
        encoded = await WanVideoEncodeLatentBatch.execute(vae, memory_images)
        story_mem_latents, = encoded.result
        updated['story_mem_latents'] = story_mem_latents['samples'].squeeze(2).permute(1, 0, 2, 3)
        updated['rope_negative_offset_frames'] = rope_negative_offset_frames if rope_negative_offset else 0
        _bound_payload(updated)
        return io.NodeOutput(updated)


NODE_CLASS_MAPPINGS = {cls.__name__: cls for cls in (
    WanVideoAddSCAILReferenceEmbeds, WanVideoAddSCAILPoseEmbeds, WanVideoAddStoryMemLatents)}
