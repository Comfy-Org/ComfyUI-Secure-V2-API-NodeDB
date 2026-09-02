"""Secure Nodes V2 entrypoint for the pinned Audio General snapshot."""

from .nodes import (
    AudioBassTreble,
    AudioConcatenate,
    AudioInfo,
    AudioMix,
    AudioPitch,
    AudioSampleRate,
    AudioSpeed,
    AudioTrimSilenceRosa,
    AudioTrimSilenceVAD,
)


WEB_DIRECTORY = "./js"

NODE_CLASS_MAPPINGS = {
    "AudioInfo": AudioInfo,
    "AudioSampleRate": AudioSampleRate,
    "AudioPitch": AudioPitch,
    "AudioMix": AudioMix,
    "AudioConcat": AudioConcatenate,
    "AudioTrimSilenceVAD": AudioTrimSilenceVAD,
    "AudioTrimSilenceRosa": AudioTrimSilenceRosa,
    "AudioBassTreble": AudioBassTreble,
    "AudioSpeed": AudioSpeed,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AudioInfo": "Audio Info",
    "AudioSampleRate": "Audio Pitch (Sample Rate)",
    "AudioPitch": "Audio Pitch",
    "AudioMix": "Audio Mix",
    "AudioConcat": "Audio Concatenate",
    "AudioTrimSilenceVAD": "Audio Trim Silence (Voice Activity)",
    "AudioTrimSilenceRosa": "Audio Trim Silence (dB)",
    "AudioBassTreble": "Audio Bass/Treble",
    "AudioSpeed": "Audio Speed",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
