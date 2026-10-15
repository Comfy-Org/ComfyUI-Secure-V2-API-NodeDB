"""Pinned LongCat avatar continuation; learned VAE branch is separately gated.

The node retains the original audio slicing, padding and latent operations.
CPU is the admitted raw compute device in this conversion. A WANVAE recipe is
reconstructed only for the original prev_images+vae re-encoding branch.
"""
import logging
import math
import torch
from comfy_api.latest import io
from .secure_tensor_nodes import _bound_payload, MAX_PAYLOAD_BYTES, MAX_TENSOR_ELEMENTS

log = logging.getLogger(__name__)
device = torch.device('cpu')
offload_device = torch.device('cpu')


def _preflight(prev_latents, audio_embeds, num_frames, overlap, frames_processed, ref_latent, samples, prev_images):
    _bound_payload((prev_latents, audio_embeds, ref_latent, samples, prev_images))
    if not isinstance(audio_embeds, dict):
        return
    features = audio_embeds.get('audio_features')
    if not isinstance(features, (list, tuple)) or not features:
        return
    if not all(isinstance(value, torch.Tensor) and value.ndim == 3 and value.shape == features[0].shape for value in features):
        return
    if not isinstance(num_frames, int) or not isinstance(frames_processed, int):
        return
    humans = len(features)
    time, groups, channels = features[0].shape
    dtype = features[0].dtype
    for value in features[1:]:
        dtype = torch.promote_types(dtype, value.dtype)
    size = dtype.itemsize
    deficit = max(0, frames_processed + num_frames - time)
    source = humans * time * groups * channels
    padded = humans * (time + deficit) * groups * channels
    window = humans * max(0, num_frames) * 5 * groups * channels
    # Stack, pad and concat, indexed window and published output. Conservative
    # for mirror padding, which deliberately keeps the original short mirror.
    elements = max(source, padded, window)
    total = (source * 2 + padded * 2 + window * 3) * size
    for value in (prev_latents, ref_latent, samples):
        tensor = value.get('samples') if isinstance(value, dict) else None
        if isinstance(tensor, torch.Tensor):
            total += 3 * tensor.numel() * tensor.element_size()
    if isinstance(prev_images, torch.Tensor):
        total += 4 * prev_images.numel() * prev_images.element_size()
    if elements > MAX_TENSOR_ELEMENTS or total > MAX_PAYLOAD_BYTES:
        raise ValueError('Wan LongCat continuation exceeds tensor/64 MiB bounds')


class WanVideoLongCatAvatarExtendEmbeds(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets', 'models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoLongCatAvatarExtendEmbeds', display_name='WanVideo LongCat Avatar Extend Embeds', category='WanVideoWrapper', inputs=[io.Latent.Input('prev_latents', tooltip="Full previous latents to be used to continue generation, continuation frames are selected based on 'overlap' parameter"), io.Custom('MULTITALK_EMBEDS').Input('audio_embeds', tooltip='Full length audio embeddings'), io.Int.Input('num_frames', default=93, min=1, max=256, step=1, tooltip='Number of new frames to generate'), io.Int.Input('overlap', default=13, min=0, max=16, step=1, tooltip='Number of overlapping frames from previous latents for video continuation, set to 0 for T2V'), io.Int.Input('frames_processed', default=0, min=0, max=10000, step=1, tooltip='Number of frames already processed in the video, used to select audio features'), io.Combo.Input('if_not_enough_audio', ['pad_with_start', 'mirror_from_end'], default='pad_with_start', tooltip='What to do if there are not enough frames in pose_images for the window'), io.Int.Input('ref_frame_index', default=10, min=0, max=1000, step=1, tooltip='Values between 0 - 24 ensures better consistency, while selecting other ranges (e.g., -10 or 30) helps reduce repeated actions'), io.Int.Input('ref_mask_frame_range', default=3, min=0, max=20, step=1, tooltip='Larger range can further help mitigate repeated actions, but excessively large values may introduce artifacts'), io.Latent.Input('ref_latent', optional=True, tooltip='Reference latent used for consistency, generally should be either the init image, or first latent from first generation'), io.Latent.Input('samples', optional=True, tooltip="For the sampler 'samples' input, used for slicing samples per window for vid2vid"), io.Custom('IMAGE').Input('prev_images', optional=True, tooltip="LongCat-Avatar-1.5: decoded frames from the previous segment. When provided together with `vae`, the trailing `overlap` frames are re-encoded through the VAE and used as the overlap conditioning (matches v1.5's use_vcond=False behavior). Leave disconnected for v1.0."), io.Custom('WANVAE').Input('vae', optional=True, tooltip='LongCat-Avatar-1.5: VAE used to re-encode `prev_images` for the overlap region. Only used when `prev_images` is also provided.')], outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds', tooltip='Embeds for WanVideo LongCat Avatar generation'), io.Latent.Output(display_name='samples_slice', tooltip='Sliced latent samples for the new frames')])

    @classmethod
    async def execute(cls, prev_latents, audio_embeds, num_frames, overlap, if_not_enough_audio, frames_processed, ref_frame_index, ref_mask_frame_range, ref_latent=None, samples=None, prev_images=None, vae=None) -> io.NodeOutput:
        _preflight(prev_latents, audio_embeds, num_frames, overlap, frames_processed, ref_latent, samples, prev_images)
        new_audio_embed = audio_embeds.copy()
        audio_features = torch.stack(new_audio_embed['audio_features'])
        num_audio_features = audio_features.shape[1]
        if audio_features.shape[1] < frames_processed + num_frames:
            deficit = frames_processed + num_frames - audio_features.shape[1]
            if if_not_enough_audio == 'pad_with_start':
                pad = audio_features[:, :1].repeat(1, deficit, 1, 1)
                audio_features = torch.cat([audio_features, pad], dim=1)
            elif if_not_enough_audio == 'mirror_from_end':
                to_add = audio_features[:, -deficit:, :].flip(dims=[1])
                audio_features = torch.cat([audio_features, to_add], dim=1)
            log.warning(f"Not enough audio features, padded with strategy '{if_not_enough_audio}' from {num_audio_features} to {audio_features.shape[1]} frames")
        ref_target_masks = new_audio_embed.get('ref_target_masks', None)
        if ref_target_masks is not None:
            new_audio_embed['ref_target_masks'] = ref_target_masks[:, frames_processed:frames_processed + num_frames, :]
        prev_samples = prev_latents['samples'].clone()
        if overlap != 0:
            latent_overlap = (overlap - 1) // 4 + 1
            if prev_images is not None and vae is not None:
                from .secure_full_vae_nodes import rebuild_full_vae
                vae, _ = await rebuild_full_vae(vae)
                img = prev_images[-overlap:]
                if img.shape[-1] == 4:
                    img = img[..., :3]
                img = img.to(vae.dtype).to(device) * 2.0 - 1.0
                img = img.permute(3, 0, 1, 2).unsqueeze(0).contiguous()
                vae.to(device)
                prev_samples = vae.encode(img, device=device).to(prev_samples)
                vae.to(offload_device)
                log.info(f'Re-encoded {overlap} overlap frames -> latent shape {tuple(prev_samples.shape)}')
            else:
                prev_samples = prev_samples[:, :, -latent_overlap:]
        ref_sample = None
        if ref_latent is not None:
            ref_sample = ref_latent['samples'][0, :, :1].clone()
            log.info(f'Previous latents shape: {prev_samples.shape}, using last {latent_overlap} latent frames for overlap.')
        new_latent_frames = (num_frames - 1) // 4 + 1
        target_shape = (16, new_latent_frames, prev_samples.shape[-2], prev_samples.shape[-1])
        audio_stride = new_audio_embed.get('audio_stride', 2)
        indices = torch.arange(2 * 2 + 1) - 2
        if frames_processed == 0:
            audio_start_idx = 0
        else:
            audio_start_idx = (frames_processed - overlap) * audio_stride
        audio_end_idx = audio_start_idx + num_frames * audio_stride
        log.info(f'Extracting audio embeddings from index {audio_start_idx} to {audio_end_idx}')
        audio_embs = []
        for human_idx in range(len(audio_features)):
            center_indices = torch.arange(audio_start_idx, audio_end_idx, audio_stride).unsqueeze(1) + indices.unsqueeze(0)
            center_indices = torch.clamp(center_indices, min=0, max=audio_features[human_idx].shape[0] - 1)
            audio_emb = audio_features[human_idx][center_indices].unsqueeze(0).to(device)
            audio_embs.append(audio_emb)
        audio_emb = torch.cat(audio_embs, dim=0)
        new_audio_embed['audio_features'] = None
        new_audio_embed['audio_emb_slice'] = audio_emb
        longcat_avatar_options = {'longcat_ref_latent': ref_sample, 'ref_frame_index': ref_frame_index, 'ref_mask_frame_range': ref_mask_frame_range}
        embeds = {'target_shape': target_shape, 'num_frames': num_frames, 'extra_latents': [{'samples': prev_samples, 'index': 0}] if overlap != 0 else None, 'multitalk_embeds': new_audio_embed, 'longcat_avatar_options': longcat_avatar_options}
        samples_slice = None
        if samples is not None:
            latent_start_index = (frames_processed - 1) // 4 + 1 if frames_processed > 0 else 0
            latent_end_index = latent_start_index + new_latent_frames
            samples_slice = samples.copy()
            samples_slice['samples'] = samples['samples'][:, :, latent_start_index:latent_end_index].clone()
        return io.NodeOutput(embeds, samples_slice)

NODE_CLASS_MAPPINGS = {'WanVideoLongCatAvatarExtendEmbeds': WanVideoLongCatAvatarExtendEmbeds}
