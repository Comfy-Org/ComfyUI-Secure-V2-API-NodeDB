"""Closed admitted WAV/PCM bytes; never a filename or decoder subprocess."""
import io
import wave
import numpy as np
import torch
from pydub import AudioSegment

MAX_WAV_BYTES = 4 * 1024 * 1024
RATES = (8000, 16000, 44100, 48000)

def decode(payload):
    if type(payload) is not bytes or len(payload) > MAX_WAV_BYTES:
        raise ValueError("WAV byte profile refused")
    if payload[:4] != b"RIFF" or payload[8:12] != b"WAVE":
        raise ValueError("WAV PCM required")
    with wave.open(io.BytesIO(payload), "rb") as wav:
        channels, width, rate, frames, compression, _ = wav.getparams()
        if compression != "NONE" or channels not in (1, 2) or width not in (1, 2, 3, 4) or rate not in RATES:
            raise ValueError("WAV PCM encoding profile refused")
        if frames > rate * 10 or frames * channels * width > MAX_WAV_BYTES:
            raise ValueError("WAV duration/sample profile refused")
        if len(wav.readframes(frames)) != frames * channels * width:
            raise ValueError("truncated PCM frames")
    # Validated PCM goes through PyDub's direct WAV branch; subprocess tests
    # cover the supported exact width/channel/rate matrix and malformed refusal.
    return AudioSegment.from_file(io.BytesIO(payload), format="wav")

def tensor(payload):
    audio = decode(payload)
    samples = np.array(audio.get_array_of_samples())
    samples = samples.reshape(-1, audio.channels).transpose(1, 0).copy()
    waveform = torch.from_numpy(samples).to(torch.float32) / float(1 << (audio.sample_width * 8 - 1))
    return waveform, audio.frame_rate
