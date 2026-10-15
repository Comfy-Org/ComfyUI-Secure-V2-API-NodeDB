"""Complete original MultiTalk Wav2Vec processing with public model recipes.

Trained Wav2Vec qualification and shared execution remain explicit gates.
"""
import logging
import math
import numpy as np
import scipy.signal as ss
import torch
from comfy_api.latest import io
from ._wan_catalogue import valid_catalogue_name
from .secure_tensor_nodes import _bound_payload, MAX_PAYLOAD_BYTES
from .secure_whisper_runtime import loudness_norm
from .secure_wav2vec_runtime import load_tencent_wav2vec, rebuild_wav2vec

log = logging.getLogger(__name__)


def _preflight(audio_1, audio_2, audio_3, audio_4, masks, num_frames, fps):
    _bound_payload((audio_1, audio_2, audio_3, audio_4, masks))
    speakers = sum(value is not None for value in (audio_1, audio_2, audio_3, audio_4))
    if isinstance(num_frames, int) and max(0, num_frames) * max(1, speakers)**2 * 12 * 768 * 4 > MAX_PAYLOAD_BYTES:
        raise ValueError('MultiTalk audio embedding output exceeds 64 MiB')
    projected = 0
    for audio in (audio_1, audio_2, audio_3, audio_4):
        if not isinstance(audio, dict):
            continue
        waveform, sample_rate = audio.get('waveform'), audio.get('sample_rate')
        if isinstance(waveform, torch.Tensor) and type(sample_rate) is int and sample_rate > 0:
            projected += math.ceil(waveform.numel()*16000/sample_rate)*max(8, waveform.element_size())
    if projected > MAX_PAYLOAD_BYTES:
        raise ValueError('MultiTalk projected resampled audio exceeds 64 MiB')


def _add_noise_floor(audio, noise_db=-45):
    noise_amp = 10 ** (noise_db / 20)
    noise = np.random.randn(len(audio)) * noise_amp
    return audio + noise

def _smooth_transients(audio, sr=16000):
    b, a = ss.butter(3, 3000 / (sr / 2))
    return ss.lfilter(b, a, audio)


class Wav2VecModelLoader(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Wav2VecModelLoader', display_name='Wav2vec2 Model Loader', category='WanVideoWrapper',
            inputs=[io.Combo.Input('model', options=[], tooltip="These models are loaded from the 'ComfyUI/models/wav2vec2' -folder", remote=io.RemoteOptions(route='/models/wav2vec2', refresh_button=True, control_after_refresh='first')),
                    io.Combo.Input('base_precision', options=['fp32', 'bf16', 'fp16'], default='fp16'),
                    io.Combo.Input('load_device', options=['main_device', 'offload_device'], default='main_device', tooltip='Initial device to load the model to, NOT recommended with the larger models unless you have 48GB+ VRAM')],
            outputs=[io.Custom('WAV2VECMODEL').Output(display_name='wav2vec_model')])

    @classmethod
    def validate_inputs(cls, input_types=None, **kwargs):
        name = kwargs.get('model')
        return True if name is None or valid_catalogue_name(name) else 'Wav2Vec requires a confined wav2vec2 catalogue name'

    @classmethod
    async def execute(cls, model, base_precision, load_device):
        materialized, recipe = await load_tencent_wav2vec(model, base_precision, load_device)
        del materialized
        return io.NodeOutput(recipe)


class MultiTalkWav2VecEmbeds(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='MultiTalkWav2VecEmbeds', display_name='Multi/InfiniteTalk Wav2vec2 Embeds', category='WanVideoWrapper',
            inputs=[io.Custom('WAV2VECMODEL').Input('wav2vec_model'),
                    io.Audio.Input('audio_1'),
                    io.Boolean.Input('normalize_loudness', default=True, tooltip='Normalize the audio loudness to -23 LUFS'),
                    io.Int.Input('num_frames', default=81, min=1, max=10000, step=1, tooltip='The total frame count to generate.'),
                    io.Float.Input('fps', default=25.0, min=1.0, max=60.0, step=0.1),
                    io.Float.Input('audio_scale', default=1.0, min=0.0, max=100.0, step=0.01, tooltip='Strength of the audio conditioning'),
                    io.Float.Input('audio_cfg_scale', default=1.0, min=0.0, max=100.0, step=0.01, tooltip='When not 1.0, an extra model pass without audio conditioning is done: slower inference but more motion is allowed'),
                    io.Combo.Input('multi_audio_type', options=['para', 'add'], default='para', tooltip="'para' overlay speakers in parallel, 'add' concatenate sequentially"),
                    io.Audio.Input('audio_2', optional=True),
                    io.Audio.Input('audio_3', optional=True),
                    io.Audio.Input('audio_4', optional=True),
                    io.Mask.Input('ref_target_masks', optional=True, tooltip='Per-speaker semantic mask(s) in pixel space. Supply one mask per speaker (plus optional background) to guide mouth assignment'),
                    io.Boolean.Input('add_noise_floor', optional=True, default=False, tooltip='Add a low-level noise floor to the audio to reduce silent gaps'),
                    io.Boolean.Input('smooth_transients', optional=True, default=False, tooltip='Apply a low-pass filter to the audio to smooth out transients')],
            outputs=[io.Custom('MULTITALK_EMBEDS').Output(display_name='multitalk_embeds'), io.Audio.Output(display_name='audio'), io.Int.Output(display_name='num_frames')])

    @classmethod
    async def execute(cls, wav2vec_model, normalize_loudness, fps, num_frames, audio_1, audio_scale, audio_cfg_scale, multi_audio_type, audio_2=None, audio_3=None, audio_4=None, ref_target_masks=None, add_noise_floor=False, smooth_transients=False):
        model_type = wav2vec_model['model_type']
        if not 'tencent' in model_type.lower():
            raise ValueError('Only tencent wav2vec2 models supported by MultiTalk')
        _preflight(audio_1, audio_2, audio_3, audio_4, ref_target_masks, num_frames, fps)
        wav2vec_model = await rebuild_wav2vec(wav2vec_model)
        import torchaudio
        import numpy as np
        from einops import rearrange
        device = torch.device('cpu')
        offload_device = torch.device('cpu')
        dtype = wav2vec_model['dtype']
        wav2vec2 = wav2vec_model['model']
        wav2vec2_feature_extractor = wav2vec_model['feature_extractor']
        sr = 16000
        audio_inputs = [audio_1, audio_2, audio_3, audio_4]
        audio_inputs = [a for a in audio_inputs if a is not None]
        multitalk_audio_features = []
        seq_lengths = []
        audio_outputs = []
        for audio in audio_inputs:
            audio_input = audio['waveform']
            sample_rate = audio['sample_rate']
            if sample_rate != 16000:
                audio_input = torchaudio.functional.resample(audio_input, sample_rate, sr)
            audio_input = audio_input[0][0]
            start_time = 0
            end_time = num_frames / fps
            start_sample = int(start_time * sr)
            end_sample = int(end_time * sr)
            try:
                audio_segment = audio_input[start_sample:end_sample]
            except Exception:
                audio_segment = audio_input
            audio_segment = audio_segment.numpy()
            if normalize_loudness:
                audio_segment = loudness_norm(audio_segment, sr=sr)
            if add_noise_floor:
                audio_segment = _add_noise_floor(audio_segment, noise_db=-45)
            if smooth_transients:
                audio_segment = _smooth_transients(audio_segment, sr=sr)
            audio_feature = np.squeeze(wav2vec2_feature_extractor(audio_segment, sampling_rate=sr).input_values)
            audio_feature = torch.from_numpy(audio_feature).float().to(device=device)
            audio_feature = audio_feature.unsqueeze(0)
            audio_duration = len(audio_segment) / sr
            video_length = audio_duration * fps
            wav2vec2.to(device)
            embeddings = wav2vec2(audio_feature.to(dtype), seq_len=int(video_length), output_hidden_states=True)
            wav2vec2.to(offload_device)
            if len(embeddings) == 0:
                print('Fail to extract audio embedding for one speaker')
                continue
            audio_emb = torch.stack(embeddings.hidden_states[1:], dim=1).squeeze(0)
            audio_emb = rearrange(audio_emb, 'b s d -> s b d')
            multitalk_audio_features.append(audio_emb.cpu().detach())
            seq_lengths.append(audio_emb.shape[0])
            waveform_tensor = torch.from_numpy(audio_segment).float().cpu().unsqueeze(0).unsqueeze(0)
            audio_outputs.append({'waveform': waveform_tensor, 'sample_rate': sr})
        log.info('[MultiTalk] --- Raw speaker lengths (samples) ---')
        for idx, ao in enumerate(audio_outputs):
            log.info(f'  speaker {idx + 1}: {ao['waveform'].shape[-1]} samples (shape: {ao['waveform'].shape})')
        if len(multitalk_audio_features) > 1:
            if multi_audio_type == 'para':
                max_len = max(seq_lengths)
                padded = []
                for emb in multitalk_audio_features:
                    if emb.shape[0] < max_len:
                        pad = torch.zeros(max_len - emb.shape[0], *emb.shape[1:], dtype=emb.dtype)
                        emb = torch.cat([emb, pad], dim=0)
                    padded.append(emb)
                multitalk_audio_features = padded
            elif multi_audio_type == 'add':
                total_len = sum(seq_lengths)
                full_list = []
                offset = 0
                for emb, length in zip(multitalk_audio_features, seq_lengths):
                    full = torch.zeros(total_len, *emb.shape[1:], dtype=emb.dtype)
                    full[offset:offset + length] = emb
                    full_list.append(full)
                    offset += length
                multitalk_audio_features = full_list
        if len(multitalk_audio_features) == 0:
            raise RuntimeError('No valid audio embeddings extracted, please check inputs')
        multitalk_embeds = {'audio_features': multitalk_audio_features, 'audio_scale': audio_scale, 'audio_cfg_scale': audio_cfg_scale, 'ref_target_masks': ref_target_masks}
        if len(audio_outputs) == 1:
            out_audio = audio_outputs[0]
        elif multi_audio_type == 'para':
            max_len = max([a['waveform'].shape[-1] for a in audio_outputs])
            mixed = torch.zeros(1, 1, max_len, dtype=audio_outputs[0]['waveform'].dtype)
            for a in audio_outputs:
                w = a['waveform']
                if w.shape[-1] < max_len:
                    w = torch.nn.functional.pad(w, (0, max_len - w.shape[-1]))
                mixed += w
            out_audio = {'waveform': mixed, 'sample_rate': sr}
        else:
            total_len = sum([a['waveform'].shape[-1] for a in audio_outputs])
            mixed = torch.zeros(1, 1, total_len, dtype=audio_outputs[0]['waveform'].dtype)
            offset = 0
            for a in audio_outputs:
                w = a['waveform']
                mixed[:, :, offset:offset + w.shape[-1]] += w
                offset += w.shape[-1]
            out_audio = {'waveform': mixed, 'sample_rate': sr}
        actual_num_frames = num_frames
        if len(audio_outputs) > 0:
            if multi_audio_type == 'para':
                max_audio_duration = max([ao['waveform'].shape[-1] / sr for ao in audio_outputs])
                actual_frames_from_audio = int(max_audio_duration * fps)
            else:
                total_audio_duration = sum([ao['waveform'].shape[-1] / sr for ao in audio_outputs])
                actual_frames_from_audio = int(total_audio_duration * fps)
            actual_num_frames = min(num_frames, actual_frames_from_audio)
            if actual_frames_from_audio < num_frames:
                log.info(f'[MultiTalk] Audio duration ({actual_frames_from_audio} frames) is shorter than requested ({num_frames} frames). Using {actual_num_frames} frames.')
        total_samples_raw = sum([ao['waveform'].shape[-1] for ao in audio_outputs])
        log.info(f'[MultiTalk] total raw duration = {total_samples_raw / sr:.3f}s')
        log.info(f'[MultiTalk] multi_audio_type={multi_audio_type} | final waveform shape={out_audio['waveform'].shape} | length={out_audio['waveform'].shape[-1]} samples | seconds={out_audio['waveform'].shape[-1] / sr:.3f}s (expected {('sum' if multi_audio_type == 'add' else 'max')} of raw)')
        return io.NodeOutput(multitalk_embeds, out_audio, actual_num_frames)

NODE_CLASS_MAPPINGS = {'Wav2VecModelLoader': Wav2VecModelLoader, 'MultiTalkWav2VecEmbeds': MultiTalkWav2VecEmbeds}
