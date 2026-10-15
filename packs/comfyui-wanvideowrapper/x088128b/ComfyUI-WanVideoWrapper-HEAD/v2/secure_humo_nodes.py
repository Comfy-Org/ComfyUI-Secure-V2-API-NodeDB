"""Complete original HuMo conditioning with owned public model resources.

Learned Whisper/VAE execution needs separately scheduled qualification.
Original default dimensions pass separate boundary and internal-work budgets.
"""
import logging
import math
import torch
import torch.nn.functional as F
from comfy_api.latest import io
from .secure_tensor_nodes import _bound_payload
from .secure_whisper_runtime import rebuild_whisper
from .secure_full_vae_nodes import rebuild_full_vae
from .secure_full_vae_encode import WanVideoEncodeLatentBatch
from ._wan_resize import common_upscale

log = logging.getLogger(__name__)
device = torch.device('cpu')
offload_device = torch.device('cpu')


def _preflight(num_frames, width, height, reference_images, audio, vae=None, whisper_model=None):
    _bound_payload((reference_images, audio))
    from .secure_humo_limits import projected_humo_bytes
    references = reference_images.shape[0] if isinstance(reference_images, torch.Tensor) and reference_images.ndim == 4 else 0
    audio_samples = audio_rate = None
    if isinstance(audio, dict):
        waveform = audio.get('waveform')
        if isinstance(waveform, torch.Tensor) and waveform.ndim >= 1:
            audio_samples, audio_rate = waveform.shape[-1], audio.get('sample_rate')
    projected_humo_bytes(num_frames, width, height, references, audio_samples, audio_rate,
        vae.get('precision', 'fp32') if isinstance(vae, dict) else 'fp32',
        whisper_model.get('base_precision', 'fp32') if isinstance(whisper_model, dict) else 'fp32')


def linear_interpolation_fps(features, input_fps, output_fps, output_len=None):
    features = features.transpose(1, 2)
    seq_len = features.shape[2] / float(input_fps)
    if output_len is None:
        output_len = int(seq_len * output_fps)
    output_features = F.interpolate(features, size=output_len, align_corners=True, mode='linear')
    return output_features.transpose(1, 2)


class HuMoEmbeds(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets', 'models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='HuMoEmbeds', display_name='HuMo Embeds', category='WanVideoWrapper',
            inputs=[io.Int.Input('num_frames', default=81, min=-1, max=10000, step=1, tooltip='The total frame count to generate.'),
                io.Int.Input('width', default=832, min=64, max=4096, step=16),
                io.Int.Input('height', default=480, min=64, max=4096, step=16),
                io.Float.Input('audio_scale', default=1.0, min=0.0, max=100.0, step=0.01, tooltip='Strength of the audio conditioning'),
                io.Float.Input('audio_cfg_scale', default=1.0, min=0.0, max=100.0, step=0.01, tooltip='When not 1.0, an extra model pass without audio conditioning is done: slower inference but more motion is allowed'),
                io.Float.Input('audio_start_percent', default=0.0, min=0.0, max=1.0, step=0.01, tooltip='The percent of the video to start applying audio conditioning'),
                io.Float.Input('audio_end_percent', default=1.0, min=0.0, max=1.0, step=0.01, tooltip='The percent of the video to stop applying audio conditioning'),
                io.Custom('WHISPERMODEL').Input('whisper_model', optional=True),
                io.Custom('WANVAE').Input('vae', optional=True),
                io.Image.Input('reference_images', optional=True, tooltip='reference images for the humo model'),
                io.Audio.Input('audio', optional=True),
                io.Boolean.Input('tiled_vae', optional=True, default=False, tooltip='Use tiled VAE encoding for reduced memory use')],
            outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')])

    @classmethod
    async def execute(cls, num_frames, width, height, audio_scale, audio_cfg_scale, audio_start_percent, audio_end_percent, whisper_model=None, vae=None, reference_images=None, audio=None, tiled_vae=False):
        if reference_images is not None and vae is None:
            raise ValueError('VAE is required when reference images are provided')
        if whisper_model is None and audio is not None:
            raise ValueError('Whisper model is required when audio is provided')
        _preflight(num_frames, width, height, reference_images, audio, vae, whisper_model)
        if whisper_model is not None:
            whisper_model = await rebuild_whisper(whisper_model)
        model = whisper_model['model']
        feature_extractor = whisper_model['feature_extractor']
        dtype = whisper_model['dtype']
        sampling_rate = 16000
        if audio is not None:
            import torchaudio
            audio_input = audio['waveform'][0]
            sample_rate = audio['sample_rate']
            if sample_rate != sampling_rate:
                audio_input = torchaudio.functional.resample(audio_input, sample_rate, sampling_rate)
            if audio_input.shape[1] == 2:
                audio_input = audio_input.mean(dim=0, keepdim=False)
            else:
                audio_input = audio_input[0]
            model.to(device)
            audio_len = len(audio_input) // 640
            audio_features = []
            window = 750 * 640
            for i in range(0, len(audio_input), window):
                audio_feature = feature_extractor(audio_input[i:i + window], sampling_rate=sampling_rate, return_tensors='pt').input_features
                audio_features.append(audio_feature)
            audio_features = torch.cat(audio_features, dim=-1).to(device, dtype)
            window = 3000
            audio_prompts = []
            for i in range(0, audio_features.shape[-1], window):
                audio_prompt = model.encoder(audio_features[:, :, i:i + window], output_hidden_states=True).hidden_states
                audio_prompt = torch.stack(audio_prompt, dim=2)
                audio_prompts.append(audio_prompt)
            model.to(offload_device)
            audio_prompts = torch.cat(audio_prompts, dim=1)
            audio_prompts = audio_prompts[:, :audio_len * 2]
            feat0 = linear_interpolation_fps(audio_prompts[:, :, 0:8].mean(dim=2), 50, 25)
            feat1 = linear_interpolation_fps(audio_prompts[:, :, 8:16].mean(dim=2), 50, 25)
            feat2 = linear_interpolation_fps(audio_prompts[:, :, 16:24].mean(dim=2), 50, 25)
            feat3 = linear_interpolation_fps(audio_prompts[:, :, 24:32].mean(dim=2), 50, 25)
            feat4 = linear_interpolation_fps(audio_prompts[:, :, 32], 50, 25)
            audio_emb = torch.stack([feat0, feat1, feat2, feat3, feat4], dim=2)[0]
        else:
            audio_emb = torch.zeros(num_frames, 5, 1280, device=device)
            audio_len = num_frames
        pixel_frame_num = num_frames if num_frames != -1 else audio_len
        pixel_frame_num = 4 * ((pixel_frame_num - 1) // 4) + 1
        latent_frame_num = (pixel_frame_num - 1) // 4 + 1
        log.info(f'HuMo set to generate {pixel_frame_num} frames')
        num_refs = 0
        if reference_images is not None:
            if reference_images.shape[1] != height or reference_images.shape[2] != width:
                reference_images_in = common_upscale(reference_images.movedim(-1, 1), width, height, 'lanczos', 'disabled').movedim(1, -1)
            else:
                reference_images_in = reference_images
            samples, = (await WanVideoEncodeLatentBatch.execute(vae, reference_images_in, tiled_vae, None, None, None, None)).result
            samples = samples['samples'].transpose(0, 2).squeeze(0)
            num_refs = samples.shape[1]
        if vae is not None:
            vae, _ = await rebuild_full_vae(vae)
        vae.to(device)
        zero_frames = torch.zeros(1, 3, pixel_frame_num + 4 * num_refs, height, width, device=device, dtype=vae.dtype)
        zero_latents = vae.encode(zero_frames, device=device, tiled=tiled_vae)[0].to(offload_device)
        vae.to(offload_device)
        target_shape = (16, latent_frame_num + num_refs, height // 8, width // 8)
        mask = torch.ones(4, target_shape[1], target_shape[2], target_shape[3], device=offload_device, dtype=vae.dtype)
        if reference_images is not None:
            mask[:, :-num_refs] = 0
            image_cond = torch.cat([zero_latents[:, :target_shape[1] - num_refs], samples], dim=1)
        else:
            image_cond = zero_latents
            mask = torch.zeros_like(mask)
        image_cond = torch.cat([mask, image_cond], dim=0)
        image_cond_neg = torch.cat([mask, zero_latents], dim=0)
        embeds = {'humo_audio_emb': audio_emb, 'humo_audio_emb_neg': torch.zeros_like(audio_emb, dtype=audio_emb.dtype, device=audio_emb.device), 'humo_image_cond': image_cond, 'humo_image_cond_neg': image_cond_neg, 'humo_reference_count': num_refs, 'target_shape': target_shape, 'num_frames': pixel_frame_num, 'humo_audio_scale': audio_scale, 'humo_audio_cfg_scale': audio_cfg_scale, 'humo_start_percent': audio_start_percent, 'humo_end_percent': audio_end_percent}
        return io.NodeOutput(embeds)

NODE_CLASS_MAPPINGS = {'HuMoEmbeds': HuMoEmbeds}
