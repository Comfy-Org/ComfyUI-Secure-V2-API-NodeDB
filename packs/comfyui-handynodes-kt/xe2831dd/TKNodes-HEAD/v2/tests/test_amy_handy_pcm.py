"""Closed PCM dependency profile; no current Torchaudio decoder pass inferred."""
import io
import itertools
from pathlib import Path
import struct
import subprocess
import wave
import pytest
import torch
import test_amy_handy_v3 as proof

pcm = __import__(proof.pack.__name__ + "._pcm", fromlist=["decode"])

def wav_bytes(width, channels, rate):
    values = [0, 1, -1, (1 << (width * 8 - 2)) - 1, -(1 << (width * 8 - 2))]
    encoded = b"".join((bytes([value + 128]) if width == 1 else value.to_bytes(width, "little", signed=True))
                       * channels for value in values)
    stream = io.BytesIO()
    with wave.open(stream, "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(width)
        output.setframerate(rate)
        output.writeframes(encoded)
    return stream.getvalue(), values

@pytest.mark.parametrize("width,channels,rate", list(itertools.product((1, 2, 3, 4), (1, 2), pcm.RATES)))
def test_exact_admitted_pcm_decode_without_subprocess(width, channels, rate, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("PCM must never launch decoder process")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    import pydub.audio_segment
    monkeypatch.setattr(pydub.audio_segment, "subprocess", subprocess)
    payload, values = wav_bytes(width, channels, rate)
    decoded = pcm.decode(payload)
    # PyDub expands signed24 to signed32 by prepending the sign byte. Keep
    # that exact specified backend representation, not a Torchaudio claim.
    expected = [value * 256 + (255 if value < 0 else 0) if width == 3 else value
                for value in values for _ in range(channels)]
    assert list(decoded.get_array_of_samples()) == expected
    assert decoded.channels == channels and decoded.frame_rate == rate
    assert decoded.sample_width == (4 if width == 3 else width)

@pytest.mark.parametrize("payload", [b"", b"RIFFbad", b"fLaC" + b"x" * 30, b"x" * (pcm.MAX_WAV_BYTES + 1)])
def test_non_pcm_or_oversized_refused_before_decoder(payload, monkeypatch):
    monkeypatch.setattr(pcm.AudioSegment, "from_file", lambda *a, **k: pytest.fail("decoder entered"))
    with pytest.raises((ValueError, wave.Error)):
        pcm.decode(payload)

def test_truncated_pcm_refused_before_decoder(monkeypatch):
    payload, _ = wav_bytes(2, 2, 16000)
    monkeypatch.setattr(pcm.AudioSegment, "from_file", lambda *a, **k: pytest.fail("decoder entered"))
    with pytest.raises(ValueError, match="truncated"):
        pcm.decode(payload[:-2])

def test_pinned_breather_encoding_and_independent_exact_float32():
    import hashlib
    payload = (proof.V2 / "assets/breather.wav").read_bytes()
    assert hashlib.sha256(payload).hexdigest() == "2b69a2d6f6e441d08e183e472c36cdb9d18a24b7bf1f9d6dd71e2d4219e6d040"
    with wave.open(io.BytesIO(payload)) as source:
        assert source.getparams()[:4] == (2, 2, 48000, 47807)
        raw = source.readframes(47807)
    expected = torch.tensor(struct.unpack("<" + "h" * (len(raw) // 2), raw), dtype=torch.float32).reshape(-1, 2).T / 32768
    actual, rate = pcm.tensor(payload)
    assert rate == 48000 and actual.dtype == torch.float32
    assert torch.equal(actual, expected)
