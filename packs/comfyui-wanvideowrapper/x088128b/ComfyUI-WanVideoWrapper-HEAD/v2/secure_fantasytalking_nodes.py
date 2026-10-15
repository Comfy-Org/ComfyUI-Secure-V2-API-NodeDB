"""Original downloaded Wav2Vec and complete FantasyTalking embedding math.

Two original repository bundles are pinned. Weights, temporary bundle capacity,
SDK construction and learned output qualification remain separate open gates.
"""
import math
import torch
from comfy_api.latest import io
from .secure_tensor_nodes import _bound_payload, MAX_PAYLOAD_BYTES
from .secure_download_wav2vec_runtime import load_downloaded_wav2vec, rebuild_fantasy_wav2vec, required_weights
from .secure_audio_projection_runtime import rebuild_fantasytalking


def soft_empty_cache():
    # Exact original Core soft_empty_cache's CPU-mode early return.
    return None


def _preflight(audio):
    _bound_payload(audio)
    if isinstance(audio, dict):
        waveform, sample_rate = audio.get('waveform'), audio.get('sample_rate')
        if isinstance(waveform, torch.Tensor) and type(sample_rate) is int and sample_rate > 0:
            if waveform.ndim and waveform.shape[-1] > 30*sample_rate:
                raise ValueError('FantasyTalking source domain currently admits at most 30 seconds of audio')
            if math.ceil(waveform.numel()*16000/sample_rate)*max(4, waveform.element_size()) > MAX_PAYLOAD_BYTES:
                raise ValueError('FantasyTalking resampled audio exceeds 64 MiB')


class DownloadAndLoadWav2VecModel(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets', 'models.download')
    SDK_REQUIRED_WEIGHTS = required_weights()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='DownloadAndLoadWav2VecModel', display_name='(Down)load Wav2Vec Model', category='WanVideoWrapper',
            inputs=[io.Combo.Input('model', options=['TencentGameMate/chinese-wav2vec2-base', 'facebook/wav2vec2-base-960h']),
                    io.Combo.Input('base_precision', options=['fp32', 'bf16', 'fp16'], default='fp16'),
                    io.Combo.Input('load_device', options=['main_device', 'offload_device'], default='main_device', tooltip='Initial device to load the model to, NOT recommended with the larger models unless you have 48GB+ VRAM')],
            outputs=[io.Custom('WAV2VECMODEL').Output(display_name='wav2vec_model')])

    @classmethod
    async def execute(cls, model, base_precision, load_device):
        materialized, recipe = await load_downloaded_wav2vec(model, base_precision, load_device)
        del materialized
        return io.NodeOutput(recipe)


class FantasyTalkingWav2VecEmbeds(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='FantasyTalkingWav2VecEmbeds', display_name='FantasyTalking Wav2Vec Embeds', category='WanVideoWrapper',
            inputs=[io.Custom('WAV2VECMODEL').Input('wav2vec_model'),
                    io.Custom('FANTASYTALKINGMODEL').Input('fantasytalking_model'),
                    io.Audio.Input('audio'),
                    io.Int.Input('num_frames', default=81, min=1, max=1000, step=1),
                    io.Float.Input('fps', default=23.0, min=1.0, max=60.0, step=0.1),
                    io.Float.Input('audio_scale', default=1.0, min=0.0, max=100.0, step=0.1, tooltip='Strength of the audio conditioning'),
                    io.Float.Input('audio_cfg_scale', default=1.0, min=0.0, max=100.0, step=0.1, tooltip='When not 1.0, an extra model pass without audio conditioning is done: slower inference but more motion is allowed')],
            outputs=[io.Custom('FANTASYTALKING_EMBEDS').Output(display_name='fantasytalking_embeds')])

    @classmethod
    async def execute(cls, wav2vec_model, fantasytalking_model, fps, num_frames, audio_scale, audio_cfg_scale, audio):
        import torchaudio
        device = torch.device('cpu')
        offload_device = torch.device('cpu')
        _preflight(audio)
        wav2vec_model = await rebuild_fantasy_wav2vec(wav2vec_model)
        dtype = wav2vec_model['dtype']
        wav2vec = wav2vec_model['model']
        wav2vec_processor = wav2vec_model['processor']
        fantasytalking_model = await rebuild_fantasytalking(fantasytalking_model)
        audio_proj_model = fantasytalking_model['proj_model']
        sr = 16000
        audio_input = audio['waveform']
        sample_rate = audio['sample_rate']
        if sample_rate != sr:
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
        print('audio_segment.shape', audio_segment.shape)
        input_values = wav2vec_processor(audio_segment.numpy(), sampling_rate=sr, return_tensors='pt').input_values.to(dtype).to(device)
        wav2vec.to(device)
        audio_features = wav2vec(input_values).last_hidden_state
        wav2vec.to(offload_device)
        audio_proj_model.proj_model.to(device)
        audio_proj_fea = audio_proj_model.get_proj_fea(audio_features)
        pos_idx_ranges = audio_proj_model.split_audio_sequence(audio_proj_fea.size(1), num_frames=num_frames)
        audio_proj_split, audio_context_lens = audio_proj_model.split_tensor_with_padding(audio_proj_fea, pos_idx_ranges, expand_length=4)
        audio_proj_model.proj_model.to(offload_device)
        soft_empty_cache()
        out = {'audio_proj': audio_proj_split, 'audio_context_lens': audio_context_lens, 'audio_scale': audio_scale, 'audio_cfg_scale': audio_cfg_scale}
        _bound_payload(out)
        return io.NodeOutput(out)

NODE_CLASS_MAPPINGS = {'DownloadAndLoadWav2VecModel': DownloadAndLoadWav2VecModel, 'FantasyTalkingWav2VecEmbeds': FantasyTalkingWav2VecEmbeds}
