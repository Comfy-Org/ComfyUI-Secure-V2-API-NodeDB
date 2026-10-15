"""Owned Whisper loader and complete LongCat avatar Whisper extraction.

Learned Whisper execution and its checkpoint remain qualification gates.
"""
import logging
import torch
import torch.nn.functional as F
from comfy_api.latest import io
from ._wan_catalogue import valid_catalogue_name
from .secure_tensor_nodes import _bound_payload, MAX_PAYLOAD_BYTES
from .secure_whisper_runtime import load_whisper, rebuild_whisper

log = logging.getLogger(__name__)
device = torch.device('cpu')
offload_device = torch.device('cpu')


def _preflight(audio_1, audio_2, audio_3, audio_4, masks, num_frames):
    _bound_payload((audio_1, audio_2, audio_3, audio_4, masks))
    speakers = sum(value is not None for value in (audio_1, audio_2, audio_3, audio_4))
    if isinstance(num_frames, int) and max(0, num_frames) * max(1, speakers)**2 * 5 * 1280 * 4 > MAX_PAYLOAD_BYTES:
        raise ValueError('Whisper audio embedding output exceeds 64 MiB')


class WhisperModelLoader(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WhisperModelLoader', display_name='Whisper Model Loader', category='WanVideoWrapper',
            inputs=[io.Combo.Input('model', options=[], tooltip="These models are loaded from the 'ComfyUI/models/audio_encoders' folder",
                       remote=io.RemoteOptions(route='/models/audio_encoders', refresh_button=True, control_after_refresh='first')),
                    io.Combo.Input('base_precision', options=['fp32', 'bf16', 'fp16'], default='fp16'),
                    io.Combo.Input('load_device', options=['main_device', 'offload_device'], default='main_device',
                        tooltip='Initial device to load the model to, NOT recommended with the larger models unless you have 48GB+ VRAM')],
            outputs=[io.Custom('WHISPERMODEL').Output(display_name='whisper_model')])

    @classmethod
    def validate_inputs(cls, input_types=None, **kwargs):
        name = kwargs.get('model')
        return True if name is None or valid_catalogue_name(name) else 'Whisper requires a confined audio encoder catalogue name'

    @classmethod
    async def execute(cls, model, base_precision, load_device):
        materialized, recipe = await load_whisper(model, base_precision, load_device)
        del materialized
        return io.NodeOutput(recipe)


class LongCatAvatarWhisperEmbeds(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='LongCatAvatarWhisperEmbeds', display_name='LongCat Avatar Whisper Embeds (v1.5)', category='WanVideoWrapper',
            inputs=[io.Custom('WHISPERMODEL').Input('whisper_model'), io.Audio.Input('audio_1'),
                io.Boolean.Input('normalize_loudness', default=True, tooltip='Normalize audio loudness to -23 LUFS before encoding (matches the v1.5 reference pipeline)'),
                io.Int.Input('num_frames', default=93, min=1, max=10000, step=1, tooltip='Total frame count to generate; bounds how much audio is consumed'),
                io.Float.Input('fps', default=25.0, min=1.0, max=60.0, step=0.1, tooltip='Target video fps. LongCat-Video-Avatar-1.5 is trained at 25 fps.'),
                io.Float.Input('audio_scale', default=1.0, min=0.0, max=100.0, step=0.01, tooltip='Strength of the audio conditioning'),
                io.Float.Input('audio_cfg_scale', default=1.0, min=0.0, max=100.0, step=0.01, tooltip='When not 1.0, an extra model pass without audio conditioning is done'),
                io.Combo.Input('multi_audio_type', options=['para', 'add'], default='para', tooltip="'para' overlays speakers in parallel (equal length); 'add' concatenates speakers sequentially with silence padding"),
                io.Audio.Input('audio_2', optional=True), io.Audio.Input('audio_3', optional=True), io.Audio.Input('audio_4', optional=True),
                io.Mask.Input('ref_target_masks', optional=True, tooltip='Per-speaker semantic mask(s) in pixel space, one per speaker')],
            outputs=[io.Custom('MULTITALK_EMBEDS').Output(display_name='multitalk_embeds'),
                     io.Audio.Output(display_name='audio'), io.Int.Output(display_name='num_frames')])

    @classmethod
    async def execute(cls, whisper_model, audio_1, normalize_loudness, num_frames, fps, audio_scale, audio_cfg_scale, multi_audio_type, audio_2=None, audio_3=None, audio_4=None, ref_target_masks=None):
        _preflight(audio_1, audio_2, audio_3, audio_4, ref_target_masks, num_frames)
        whisper_model = await rebuild_whisper(whisper_model)
        import torchaudio
        import numpy as np
        from .secure_whisper_runtime import loudness_norm
        model = whisper_model['model']
        feature_extractor = whisper_model['feature_extractor']
        dtype = whisper_model['dtype']
        sr = 16000
        MEL_CHUNK = 750 * 640
        ENC_CHUNK = 3000
        ENC_FPS = 50

        def linear_interp(features, output_len):
            features = features.transpose(1, 2)
            out = F.interpolate(features, size=output_len, align_corners=True, mode='linear')
            return out.transpose(1, 2)
        audio_inputs = [a for a in [audio_1, audio_2, audio_3, audio_4] if a is not None]
        audio_features_list = []
        seq_lengths = []
        audio_outputs = []
        end_time = num_frames / float(fps)
        end_sample = int(end_time * sr)
        for audio in audio_inputs:
            audio_input = audio['waveform']
            sample_rate = audio['sample_rate']
            if sample_rate != sr:
                audio_input = torchaudio.functional.resample(audio_input, sample_rate, sr)
            audio_input = audio_input[0][0]
            audio_segment = audio_input[:end_sample].cpu().numpy().astype(np.float32)
            if normalize_loudness:
                audio_segment = loudness_norm(audio_segment, sr=sr)
            audio_duration = len(audio_segment) / sr
            video_length = int(audio_duration * fps)
            if video_length < 1:
                continue
            mel_chunks = []
            for i in range(0, len(audio_segment), MEL_CHUNK):
                mel = feature_extractor(audio_segment[i:i + MEL_CHUNK], sampling_rate=sr, return_tensors='pt').input_features
                mel_chunks.append(mel)
            mel_features = torch.cat(mel_chunks, dim=-1).to(device=device, dtype=dtype)
            model.to(device)
            enc_chunks = []
            with torch.no_grad():
                for i in range(0, mel_features.shape[-1], ENC_CHUNK):
                    chunk = mel_features[:, :, i:i + ENC_CHUNK]
                    chunk_hs = model.encoder(chunk, output_hidden_states=True).hidden_states
                    enc_chunks.append(torch.stack(chunk_hs, dim=2))
            model.to(offload_device)
            audio_prompts = torch.cat(enc_chunks, dim=1)
            audio_prompts = audio_prompts[:, :video_length * 2]
            feat0 = linear_interp(audio_prompts[:, :, 0:8].mean(dim=2), video_length)
            feat1 = linear_interp(audio_prompts[:, :, 8:16].mean(dim=2), video_length)
            feat2 = linear_interp(audio_prompts[:, :, 16:24].mean(dim=2), video_length)
            feat3 = linear_interp(audio_prompts[:, :, 24:32].mean(dim=2), video_length)
            feat4 = linear_interp(audio_prompts[:, :, 32], video_length)
            audio_emb = torch.stack([feat0, feat1, feat2, feat3, feat4], dim=2)[0]
            audio_features_list.append(audio_emb.cpu().detach())
            seq_lengths.append(audio_emb.shape[0])
            waveform_tensor = torch.from_numpy(audio_segment).float().unsqueeze(0).unsqueeze(0)
            audio_outputs.append({'waveform': waveform_tensor, 'sample_rate': sr})
        if len(audio_features_list) == 0:
            raise RuntimeError('No valid Whisper audio embeddings extracted, please check inputs')
        if len(audio_features_list) > 1:
            if multi_audio_type == 'para':
                max_len = max(seq_lengths)
                padded = []
                for emb in audio_features_list:
                    if emb.shape[0] < max_len:
                        pad = torch.zeros(max_len - emb.shape[0], *emb.shape[1:], dtype=emb.dtype)
                        emb = torch.cat([emb, pad], dim=0)
                    padded.append(emb)
                audio_features_list = padded
            else:
                total_len = sum(seq_lengths)
                full_list = []
                offset = 0
                for emb, length in zip(audio_features_list, seq_lengths):
                    full = torch.zeros(total_len, *emb.shape[1:], dtype=emb.dtype)
                    full[offset:offset + length] = emb
                    full_list.append(full)
                    offset += length
                audio_features_list = full_list
        multitalk_embeds = {'audio_features': audio_features_list, 'audio_scale': audio_scale, 'audio_cfg_scale': audio_cfg_scale, 'ref_target_masks': ref_target_masks, 'audio_stride': 1, 'audio_encoder_type': 'whisper'}
        if len(audio_outputs) == 1:
            out_audio = audio_outputs[0]
        elif multi_audio_type == 'para':
            max_len = max((a['waveform'].shape[-1] for a in audio_outputs))
            mixed = torch.zeros(1, 1, max_len, dtype=audio_outputs[0]['waveform'].dtype)
            for a in audio_outputs:
                w = a['waveform']
                if w.shape[-1] < max_len:
                    w = F.pad(w, (0, max_len - w.shape[-1]))
                mixed += w
            out_audio = {'waveform': mixed, 'sample_rate': sr}
        else:
            total_len = sum((a['waveform'].shape[-1] for a in audio_outputs))
            mixed = torch.zeros(1, 1, total_len, dtype=audio_outputs[0]['waveform'].dtype)
            offset = 0
            for a in audio_outputs:
                w = a['waveform']
                mixed[:, :, offset:offset + w.shape[-1]] += w
                offset += w.shape[-1]
            out_audio = {'waveform': mixed, 'sample_rate': sr}
        return io.NodeOutput(multitalk_embeds, out_audio, num_frames)

NODE_CLASS_MAPPINGS = {'WhisperModelLoader': WhisperModelLoader, 'LongCatAvatarWhisperEmbeds': LongCatAvatarWhisperEmbeds}
