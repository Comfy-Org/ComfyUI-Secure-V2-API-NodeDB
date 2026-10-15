"""Pack-local explicit workload admission, never a host/profile quota grant."""
from contextvars import ContextVar
from contextlib import contextmanager
import math
import numpy as np
import torch
from pydub.silence import detect_silence as _native_detect_silence

MAX_BYTES = 32 * 1024 * 1024
MAX_TEXT_BYTES = 65536
MAX_ITEMS = 4096
MAX_SAMPLE_WORK = 268435456
_work = ContextVar("handy_silence_work", default=None)

def value_work(value, depth=0, _budget=None):
    if _budget is None:
        _budget = {"bytes": 0, "text": 0, "items": 0}
    if depth > 8:
        raise ValueError("structured value depth budget exceeded")
    if isinstance(value, np.ndarray):
        if (type(value) is not np.ndarray or value.dtype.kind not in "biufc"
                or value.dtype.hasobject or value.dtype.fields is not None
                or not 1 <= value.dtype.itemsize <= 32):
            raise TypeError("plain numeric ndarray profile required")
        if value.ndim > 4:
            raise ValueError("dense array rank budget exceeded")
        # Logical bytes, not backing allocation: broadcast/strided views must
        # not make the advertised 32MiB projection budget disappear.
        size = int(value.nbytes)
        if size > MAX_BYTES:
            raise ValueError("array byte budget exceeded")
        _budget["bytes"] += size
        if _budget["bytes"] > MAX_BYTES:
            raise ValueError("aggregate byte budget exceeded")
        return size
    if isinstance(value, np.generic):
        if (value.dtype.kind not in "biufc" or value.dtype.hasobject
                or value.dtype.fields is not None or not 1 <= value.dtype.itemsize <= 32):
            raise TypeError("numeric numpy scalar profile required")
        if value.dtype.kind in "iu":
            excessive = abs(int(value)) > 1000000
        else:
            magnitude = np.abs(value)
            # Compare in a dtype that represents the policy ceiling instead
            # of casting 1e6 to float16 (inf), without narrowing longdouble.
            ceiling = np.array(1000000, dtype=np.result_type(magnitude.dtype, np.float64))
            excessive = bool(magnitude > ceiling)
        if not bool(np.isfinite(value)) or excessive:
            raise ValueError("finite bounded numpy scalar required")
        size = int(value.dtype.itemsize)
        _budget["bytes"] += size
        if _budget["bytes"] > MAX_BYTES:
            raise ValueError("aggregate byte budget exceeded")
        return size
    if isinstance(value, torch.Tensor):
        if value.layout != torch.strided or value.ndim > 4:
            raise ValueError("dense tensor rank budget exceeded")
        size = value.numel() * value.element_size()
        if size > MAX_BYTES:
            raise ValueError("tensor byte budget exceeded")
        _budget["bytes"] += size
        if _budget["bytes"] > MAX_BYTES:
            raise ValueError("aggregate byte budget exceeded")
        return size
    if type(value) is str:
        size = len(value.encode("utf-8"))
        if size > MAX_TEXT_BYTES:
            raise ValueError("text byte budget exceeded")
        _budget["text"] += size
        _budget["bytes"] += size
        if _budget["text"] > MAX_TEXT_BYTES:
            raise ValueError("aggregate text byte budget exceeded")
        if _budget["bytes"] > MAX_BYTES:
            raise ValueError("aggregate byte budget exceeded")
        return size
    if type(value) in (int, float):
        if not math.isfinite(value) or abs(value) > 1000000:
            raise ValueError("finite bounded scalar required")
        return 0
    if type(value) in (dict, list, tuple):
        _budget["items"] += len(value)
        if _budget["items"] > MAX_ITEMS:
            raise ValueError("structured item budget exceeded")
        if type(value) is dict:
            for key in value:
                if type(key) not in (str, int, float, bool, type(None)) and not isinstance(key, np.generic):
                    raise TypeError("unsupported mapping key")
                value_work(key, depth + 1, _budget)
        total = sum(value_work(item, depth + 1, _budget) for item in
                    (value.values() if type(value) is dict else value))
        if total > MAX_BYTES:
            raise ValueError("aggregate byte budget exceeded")
        return total
    # Public opaque refs/None/bool are not inspected or raw-recovered here.
    return 0

def projected(shape, item_size=8, copies=1):
    if not all(type(n) is int and 0 <= n <= 1000000 for n in shape):
        raise ValueError("projected shape budget exceeded")
    size = math.prod(shape) * item_size * copies
    if size > MAX_BYTES:
        raise ValueError("projected temporary/output byte budget exceeded")
    return size

def audio(value):
    if type(value) is not dict or not isinstance(value.get("waveform"), torch.Tensor):
        raise TypeError("AUDIO requires a waveform tensor mapping")
    wave = value["waveform"]
    rate = value.get("sample_rate")
    if type(rate) is not int or not 8000 <= rate <= 192000:
        raise ValueError("audio rate profile refused")
    if wave.ndim != 3 or wave.shape[0] > 8 or wave.shape[1] > 8:
        raise ValueError("audio batch/channel profile refused")
    value_work(value)
    return wave, rate

def resample_work(wave, original, target):
    common = math.gcd(original, target)
    orig, new = original // common, target // common
    width = math.ceil(6 * orig / (min(orig, new) * 0.99))
    # Exact torchaudio default sinc kernel shape, with conservative fp64 reserve.
    projected((new, 2 * width + orig), copies=2)
    projected((*wave.shape[:-1], math.ceil(wave.shape[-1] * target / original)),
              wave.element_size(), copies=3)

def preflight(node_id, kwargs):
    value_work(kwargs)
    audios = []
    for value in kwargs.values():
        if type(value) is dict and "waveform" in value:
            audios.append(audio(value))
    if node_id == "TKMergeAudioList":
        clips = kwargs["audio_list"]
        audios = [audio(item) for item in clips]
        if audios:
            first = audios[0][0]
            projected((*first.shape[:-1], sum(w.shape[-1] for w, _ in audios)),
                      first.element_size(), copies=3)
            projected((audios[0][1] // 10,), copies=2)
    if node_id in ("TKAudioFuse", "TKVideoAudioFuse") and audios:
        target = max(rate for _, rate in audios)
        for wave, rate in audios:
            resample_work(wave, rate, target)
        wave = audios[0][0]
        longest = max(math.ceil(w.shape[-1] * target / r) for w, r in audios)
        projected((*wave.shape[:-1], longest), 8, copies=8)
    if node_id in ("TKSmartAudioChunker", "TKSmartVideoChunker"):
        chunk, variation = kwargs["chunk_secs"], kwargs["variation"]
        if type(chunk) is not int or type(variation) is not int:
            raise TypeError("chunk duration and variation must be integers")
        if not 1 <= chunk <= 600 or not 0 <= variation < chunk:
            raise ValueError("non-progressing/excessive silence chunk workload refused")
        wave, rate = audio(kwargs["audio"])
        if wave.shape[0] * wave.shape[-1] > rate * 60:
            raise ValueError("silence analysis duration budget exceeded")
    if node_id == "TKSmartVideoChunker":
        video = kwargs["video"]
        source_fps, target_fps = kwargs["source_fps"], kwargs["target_fps"]
        if not 1 <= source_fps <= 240 or not 1 <= target_fps <= 240:
            raise ValueError("video rate profile refused")
        frames = max(1, int(round(video.shape[0] * target_fps / source_fps)))
        projected((frames, *video.shape[1:]), video.element_size(), copies=3)
        wave, rate = audio(kwargs["audio"])
        projected((*wave.shape[:-1], math.ceil(frames / target_fps * rate)),
                  wave.element_size(), copies=3)
    if node_id == "TKAudioToFPSMatcher":
        wave, rate = audio(kwargs["audio"])
        fps = kwargs["video_fps"]
        if not 1 <= fps <= 240:
            raise ValueError("video rate profile refused")
        projected((*wave.shape[:-1], math.ceil(kwargs["video"].shape[0] / fps * rate)),
                  wave.element_size(), copies=3)
    if node_id == "TKSpeakerAudioTrackExtractor":
        wave, rate = audio(kwargs["fullaudio"])
        projected((*wave.shape[:-1], wave.shape[-1] + math.ceil(1.5 * rate)),
                  wave.element_size(), copies=3)
        if kwargs.get("addBreathNoise") and kwargs.get("padAudioForLtx"):
            resample_work(wave[..., :48000], 48000, rate)
    if node_id == "TKTransitionDetector":
        image = kwargs["images"]
        width = kwargs["analysis_width"]
        if type(width) is not int or not 1 <= width <= 640:
            raise ValueError("analysis width profile refused")
        height = max(1, int(image.shape[1] * width / image.shape[2]))
        projected((image.shape[0], height, width), copies=3)
        if image.shape[0] > 4096 or kwargs["max_segment_seconds"] <= 0:
            raise ValueError("transition analysis workload refused")
    for value in kwargs.values():
        if isinstance(value, torch.Tensor):
            projected(tuple(value.shape), value.element_size(), copies=4)

@contextmanager
def scope():
    token = _work.set(0)
    try:
        yield
    finally:
        _work.reset(token)

def detect_silence(segment, min_silence_len=1000, silence_thresh=-16, seek_step=1):
    work = _work.get()
    if work is None:
        raise RuntimeError("silence work scope required")
    windows = max(0, len(segment) - min_silence_len + 1)
    charged = windows * math.ceil(min_silence_len * segment.frame_rate / 1000) * segment.channels
    if work + charged > MAX_SAMPLE_WORK:
        raise ValueError("cumulative silence RMS sample-work budget exceeded")
    _work.set(work + charged)
    return _native_detect_silence(segment, min_silence_len, silence_thresh, seek_step)
