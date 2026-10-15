"""Pack algorithms over closed managed INPUT labels; no path/network recovery."""
import hashlib
import io as bytesio
import json
import math
import unicodedata
import numpy as np
import torch
from PIL import Image, ImageOps
from pydub.silence import detect_nonsilent
from comfy_api.latest import sdk
from . import _limits, _pcm
from ._speaker_algorithms import TKLocateSpeakersUsingSilenceBreaks

def logical_name(value):
    if type(value) is not str or len(value.encode("utf-8")) > 1024:
        raise ValueError("bounded managed INPUT label required")
    if value.startswith("/") or "\\" in value or ":" in value or any(unicodedata.category(c) == "Cc" for c in value):
        raise ValueError("OS/absolute/invalid path refused")
    if any(part in ("", ".", "..") for part in value.split("/")):
        raise ValueError("managed label traversal refused")
    return value

async def managed_bytes(name, maximum, missing=False):
    name = logical_name(name)
    assets = sdk.ctx().assets
    if missing and not await assets.exists("input", name):
        return None
    try:
        ref = await assets.resolve("input", name)
        size = await assets.size(ref)
        if size > maximum:
            raise ValueError("managed asset byte budget exceeded")
        # The public range broker caps each request at16MiB. Read one sentinel
        # beyond smaller profiles; at the cap check a separate one-byte tail.
        value = await assets.read_range(ref, offset=0, length=min(maximum + 1, 16 * 1024 * 1024))
        if size == 16 * 1024 * 1024 and await assets.read_range(ref, offset=size, length=1):
            raise ValueError("managed asset changed or byte budget exceeded")
    except FileNotFoundError:
        if missing:
            return None
        raise
    if len(value) != size or len(value) > maximum:
        raise ValueError("managed asset changed or byte budget exceeded")
    return value

def segments(value):
    if type(value) is not list or len(value) > 4096:
        raise ValueError("speaker segment count budget exceeded")
    for item in value:
        if type(item) is not dict or set(item) != {"start", "end", "speaker"}:
            raise ValueError("speaker segment shape refused")
        if type(item["speaker"]) is not int or item["speaker"] not in (0, 1):
            raise ValueError("closed speaker ID required")
        for key in ("start", "end"):
            number = item[key]
            if type(number) not in (int, float) or not math.isfinite(number) or not 0 <= number <= 10000:
                raise ValueError("finite bounded speaker times required")
    # Preserve source ordered/reversed/zero-length semantics; no sort/clamp here.
    return value

def carrier(text):
    _limits.value_work(text)
    if type(text) is not str:
        raise TypeError("workflow speaker_times must be STRING")
    return segments(json.loads(text))

def label_segments(text):
    _limits.value_work(text)
    rows, current_speaker = [], 0
    # Native open() universal newline behavior, not arbitrary str.splitlines().
    with bytesio.StringIO(text.replace("\r\n", "\n").replace("\r", "\n")) as stream:
        for line in stream:
            parts = line.strip().split("\t")
            if len(parts) < 2:
                continue
            start, end = float(parts[0]), float(parts[1])
            label = parts[2] if len(parts) > 2 else ""
            speaker = 0 if "1" in label else 1 if "2" in label else current_speaker
            rows.append({"start": start, "end": end, "speaker": speaker})
            if len(rows) > 4096:
                raise ValueError("label line budget exceeded")
            current_speaker = 1 if speaker == 0 else 0
    return segments(rows)

def silence_segments(audio, threshold_ms):
    duration = len(audio) / 1000.0
    mono = audio.set_channels(1) if audio.channels > 1 else audio
    mono = mono.set_frame_rate(16000)
    chunks = detect_nonsilent(mono, min_silence_len=100, silence_thresh=-40)
    if not chunks:
        return [], duration
    current_start, current_end = chunks[0]
    speaker, rows = 0, []
    for start, end in chunks[1:]:
        rows.append({"start": float(current_start / 1000.0),
                     "end": float(current_end / 1000.0), "speaker": speaker})
        if start - current_end >= threshold_ms:
            speaker = 1 if speaker == 0 else 0
        current_start, current_end = start, end
    rows.append({"start": float(current_start / 1000.0), "end": float(current_end / 1000.0), "speaker": speaker})
    return rows, duration

async def detect_speakers(request):
    body = request["body"]
    if type(body) is not str or len(body.encode("utf-8")) > 65536:
        raise ValueError("route request byte budget exceeded")
    data = json.loads(body)
    name = logical_name(data.get("audio"))
    threshold = data.get("silence_threshold", 1.0)
    if type(threshold) not in (int, float) or not math.isfinite(threshold) or not 0 <= threshold <= 600:
        raise ValueError("silence threshold profile refused")
    threshold_ms = int(threshold * 1000)
    payload = await managed_bytes(name, _pcm.MAX_WAV_BYTES)
    audio = _pcm.decode(payload)
    stem = name.rsplit("/", 1)[-1].rsplit(".", 1)[0] + ".txt"
    sibling = name.rsplit("/", 1)[0] + "/" + stem if "/" in name else stem
    authored = "handy-labels/" + stem
    labels = await managed_bytes(sibling, 65536, missing=True)
    if labels is None:
        labels = await managed_bytes(authored, 65536, missing=True)
    if labels is not None:
        rows, duration = label_segments(labels.decode("utf-8")), len(audio) / 1000.0
    else:
        rows, duration = silence_segments(audio, threshold_ms)
    rows = TKLocateSpeakersUsingSilenceBreaks().merge_small_consecutive_segments(segments(rows))
    result = {"speaker_times": rows, "duration": duration, "silence_threshold": threshold_ms}
    return {"status": 200, "body": json.dumps(result), "content_type": "application/json"}

def locate(kwargs):
    _limits.preflight("TKLocateSpeakersUsingSilenceBreaks", kwargs)
    state = kwargs.get("track_state", "DataUnchanged")
    if state not in ("DataUnchanged", "DataChange"):
        raise ValueError("unknown speaker track_state")
    native = TKLocateSpeakersUsingSilenceBreaks()
    # Instance-owned carrier, never shared class/global/KV state.
    native.autoSegmentsFromAudio = carrier(kwargs.get("speaker_times", "[]")) if state == "DataUnchanged" else []
    result = native.calculatTracksBySilence(**kwargs)
    segments(result["ui"]["speaker_times"])
    _limits.value_work(result)
    return result

async def load_image(name):
    if not name:
        return None
    payload = await managed_bytes(name, 16 * 1024 * 1024, missing=True)
    if payload is None:
        return None
    with Image.open(bytesio.BytesIO(payload)) as image:
        # Full decoded float32 plus transpose/uint8/copy work preflight.
        _limits.projected((image.height, image.width, 3), 4, copies=4)
        image = ImageOps.exif_transpose(image)
        if image.mode == "I":
            image = image.point(lambda pixel: pixel * (1 / 255))
        array = np.array(image.convert("RGB")).astype(np.float32) / 255.0
    return torch.from_numpy(array)[None, ]

async def collect(node_id, kwargs):
    _limits.value_work(kwargs)
    prompts = node_id == "TKMultiImagePrompt"
    results = list(kwargs.get("image_prompt_list") or []) if prompts else []
    for slot in range(1, 5 if prompts else 13):
        name = kwargs.get("image_" + str(slot))
        image = await load_image(name)
        if image is None:
            continue
        row = {"image": image, "filename": name, "slot": slot}
        if prompts:
            row["prompt"] = kwargs.get("prompt_" + str(slot), "")
        results.append(row)
        _limits.value_work(results)
    return (results,)

async def fingerprint(node_id, kwargs):
    _limits.value_work(kwargs)
    digest = hashlib.sha256()
    prompts = node_id == "TKMultiImagePrompt"
    for slot in range(1, 5 if prompts else 13):
        name = kwargs.get("image_" + str(slot))
        if name:
            payload = await managed_bytes(name, 16 * 1024 * 1024, missing=True)
            if payload is not None:
                digest.update(payload)
        if prompts:
            digest.update((kwargs.get("prompt_" + str(slot), "") or "").encode("utf-8"))
    chain = kwargs.get("image_prompt_list")
    if prompts and chain:
        digest.update(str(len(chain)).encode("utf-8"))
        for row in chain:
            digest.update((row.get("filename") or "").encode("utf-8"))
            digest.update((row.get("prompt") or "").encode("utf-8"))
    return digest.hexdigest()
