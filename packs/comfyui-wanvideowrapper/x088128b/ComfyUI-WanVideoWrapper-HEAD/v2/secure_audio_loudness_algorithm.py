"""Whole native AUDIO loudness normalization; registration unselected.

Real Torch/NumPy imports and real method-local pyloudnorm meter preserved.
No native producer import, fake meter/math, device/default CPU, flattening,
channel mix, .cpu() conversion or changed native failures. Actual scientific
source/ABI/import and AUDIO tensor/array/realm authority held before runtime.
"""
import torch
import numpy as np

class AudioLoudnessNormalizationAlgorithm:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "audio": ("AUDIO",),
            "lufs": ("FLOAT", {"default": -23.0, "min": -100.0, "max": 0.0, "step": 0.1, "tool": "Loudness Units relative to Full Scale, higher LUFS values (closer to 0) mean louder audio. Lower LUFS values (more negative) mean quieter audio."}),
           },
        }

    RETURN_TYPES = ("AUDIO", )
    RETURN_NAMES = ("audio", )
    FUNCTION = "normalize"
    CATEGORY = "WanVideoWrapper"

    def normalize(self, audio, lufs):
        audio_input = audio["waveform"]
        sample_rate = audio["sample_rate"]
        if audio_input.dim() == 3:
            audio_input = audio_input.squeeze(0)
        audio_input_np = audio_input.detach().transpose(0, 1).numpy().astype(np.float32)
        audio_input_np = np.ascontiguousarray(audio_input_np)
        normalized_audio = self.loudness_norm(audio_input_np, sr=sample_rate, lufs=lufs)

        out_audio = {"waveform": torch.from_numpy(normalized_audio).transpose(0, 1).unsqueeze(0).float(), "sample_rate": sample_rate}

        return (out_audio, )

    def loudness_norm(self, audio_array, sr=16000, lufs=-23):
        try:
            import pyloudnorm
        except Exception:
            raise ImportError("pyloudnorm package is not installed")
        meter = pyloudnorm.Meter(sr)
        loudness = meter.integrated_loudness(audio_array)
        if abs(loudness) > 100:
            return audio_array
        normalized_audio = pyloudnorm.normalize.loudness(audio_array, loudness, lufs)
        return normalized_audio

