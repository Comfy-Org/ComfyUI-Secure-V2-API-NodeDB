"""Complete original Ovi encode/decode math in a bounded CPU source domain.

Trained qualification and full state transport remain open gates. The ordered
vae+mmaudio menu uses the public frontend catalogue API; actual host/browser and
validation-snapshot resolution semantics still require qualification. Only digest recipes cross the MMAUDIOVAE graph boundary.
"""
import math
import torch
from comfy_api.latest import io
from ._wan_catalogue import valid_catalogue_name
from .secure_tensor_nodes import _bound_payload, MAX_PAYLOAD_BYTES
from .secure_ovi_runtime import load_ovi, rebuild_ovi, soft_empty_cache

device = torch.device('cpu')
offload_device = torch.device('cpu')
MAX_AUDIO_SECONDS = 30


def _preflight_audio(audio):
    _bound_payload(audio)
    if not isinstance(audio, dict):
        return
    waveform, sample_rate = audio.get('waveform'), audio.get('sample_rate')
    if isinstance(waveform, torch.Tensor) and type(sample_rate) is int and sample_rate > 0:
        if waveform.ndim and waveform.shape[-1] > MAX_AUDIO_SECONDS*sample_rate:
            raise ValueError('Ovi source domain currently admits at most 30 seconds of audio')
        projected = math.ceil(waveform.numel()*16000/sample_rate)*max(4, waveform.element_size())
        if projected > MAX_PAYLOAD_BYTES:
            raise ValueError('Ovi projected resampled audio exceeds 64 MiB')


def _preflight_latents(samples):
    _bound_payload(samples)
    if not isinstance(samples, dict):
        return
    value = samples.get('latent_ovi_audio')
    if isinstance(value, torch.Tensor) and value.ndim >= 2 and value.shape[-2] == 20:
        # Original VAE decoder upsamples once by 2; BigVGAN rates multiply
        # to 256. This accounts for output samples without allocating them.
        if value.shape[-1]*512 > MAX_AUDIO_SECONDS*16000:
            raise ValueError('Ovi source domain currently admits at most 30 seconds of decoded audio')
        output_bytes = math.prod(value.shape[:-2])*value.shape[-1]*512*4
        if output_bytes > MAX_PAYLOAD_BYTES:
            raise ValueError('Ovi decoded audio output exceeds 64 MiB')


class OviMMAudioVAELoader(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='OviMMAudioVAELoader', display_name='Ovi MMAudio VAE Loader', category='WanVideoWrapper/Ovi', description='Loads MMAudio VAE for Ovi audio generation',
            inputs=[io.Combo.Input('vae', options=[], tooltip='MMAudio VAE 16k (v1-16.pth) model from models/vae or models/mmaudio'), io.Combo.Input('vocoder', options=[], tooltip='BigVGAN vocoder (best_netG.pt) from models/vae or models/mmaudio'), io.Combo.Input('precision', options=['bf16', 'fp16', 'fp32'], default='bf16')],
            outputs=[io.Custom('MMAUDIOVAE').Output(display_name='mmaudio_vae')])

    @classmethod
    def validate_inputs(cls, input_types=None, **kwargs):
        return True if all(kwargs.get(key) is None or valid_catalogue_name(kwargs[key]) for key in ('vae', 'vocoder')) else 'Ovi requires confined model catalogue names'

    @classmethod
    async def execute(cls, vae, vocoder, precision):
        materialized, recipe = await load_ovi(vae, vocoder, precision)
        del materialized
        return io.NodeOutput(recipe)


class WanVideoDecodeOviAudio(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoDecodeOviAudio', display_name='WanVideo Decode Ovi Audio', category='WanVideoWrapper/Ovi',
            inputs=[io.Custom('MMAUDIOVAE').Input('mmaudio_vae'), io.Latent.Input('samples')],
            outputs=[io.Audio.Output(display_name='audio')])

    @classmethod
    async def execute(cls, mmaudio_vae, samples):
        soft_empty_cache()
        audio_latents = samples.get('latent_ovi_audio', None)
        if audio_latents is None:
            raise ValueError('No Ovi audio latents found in input samples')
        _preflight_latents(samples)
        mmaudio_vae = await rebuild_ovi(mmaudio_vae)
        mmaudio_vae.to(device)
        waveform = mmaudio_vae.wrapped_decode(audio_latents.to(device=device, dtype=mmaudio_vae.dtype))
        audio = {'waveform': waveform.cpu().float(), 'sample_rate': 16000}
        mmaudio_vae.to(offload_device)
        soft_empty_cache()
        _bound_payload(audio)
        return io.NodeOutput(audio)

class WanVideoEncodeOviAudio(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoEncodeOviAudio', display_name='WanVideo Encode Ovi Audio', category='WanVideoWrapper/Ovi',
            inputs=[io.Custom('MMAUDIOVAE').Input('mmaudio_vae'), io.Audio.Input('audio')],
            outputs=[io.Latent.Output(display_name='samples')])

    @classmethod
    async def execute(cls, mmaudio_vae, audio):
        _preflight_audio(audio)
        mmaudio_vae = await rebuild_ovi(mmaudio_vae)
        import torchaudio
        mmaudio_vae.to(device)
        waveform = audio.get('waveform', None)
        sample_rate = audio.get('sample_rate', None)
        if sample_rate != 16000:
            waveform = torchaudio.functional.resample(waveform, sample_rate, 16000)
        waveform = waveform.to(device=device, dtype=mmaudio_vae.dtype)[0][0].unsqueeze(0)
        samples = mmaudio_vae.wrapped_encode(waveform)
        mmaudio_vae.to(offload_device)
        soft_empty_cache()
        _bound_payload({'latent_ovi_audio': samples})
        return io.NodeOutput({'latent_ovi_audio': samples})

NODE_CLASS_MAPPINGS = {'OviMMAudioVAELoader': OviMMAudioVAELoader, 'WanVideoDecodeOviAudio': WanVideoDecodeOviAudio, 'WanVideoEncodeOviAudio': WanVideoEncodeOviAudio}
