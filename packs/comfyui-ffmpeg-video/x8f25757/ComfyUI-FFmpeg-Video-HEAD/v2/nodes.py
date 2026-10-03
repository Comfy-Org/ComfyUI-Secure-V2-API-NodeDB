"""Secure Nodes V2 conversion of ComfyUI-FFmpeg-Video.

The pack keeps its media algorithms in the guest. Encoded VIDEO bytes cross
the boundary through ``VideoRef.encoded_source``; host paths and executables
do not. Final encoding is delegated to the bounded output broker.
"""

from __future__ import annotations

import io as bytes_io
import math
from typing import Any

import av
import numpy as np
import torch
from comfy_api.latest import io, sdk
from PIL import Image
from torch.nn import functional

_MAX_DECODED_PIXELS = 512 * 1024 * 1024
_MAX_FRAMES = 100_000
_POSITIONS = ["center", "top", "bottom", "left", "right"]
_METHODS = ["nearest-exact", "bilinear", "area", "bicubic", "lanczos"]
_MODES = [
    "stretch",
    "resize",
    "crop",
    "total_pixels",
    "pad",
    "pad_edge",
    "pad_edge_pixel",
    "pillarbox_blur",
]


def _float_rate(value: Any, default: float = 30.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        result = default
    return result if math.isfinite(result) and result > 0 else default


async def _encoded_source(video: sdk.VideoRef) -> tuple[bytes, float, float]:
    if not isinstance(video, sdk.VideoRef):
        raise TypeError("video must be a VIDEO ref")
    payload = await (await video.encoded_source()).value()
    data = payload.get("data")
    if isinstance(data, torch.Tensor):
        content = data.detach().cpu().contiguous().numpy().tobytes()
    elif isinstance(data, (bytes, bytearray, memoryview)):
        content = bytes(data)
    else:
        raise TypeError("encoded VIDEO data must be bytes or a uint8 tensor")
    if not content:
        raise ValueError("encoded VIDEO source is empty")
    return (
        content,
        max(0.0, float(payload.get("start_time", 0.0))),
        max(0.0, float(payload.get("duration", 0.0))),
    )


def _audio_array(frame: av.AudioFrame) -> np.ndarray:
    array = np.asarray(frame.to_ndarray())
    if array.ndim == 1:
        array = array[None, :]
    if array.dtype.kind in "iu":
        info = np.iinfo(array.dtype)
        scale = float(max(abs(info.min), info.max))
        array = array.astype(np.float32) / scale
    else:
        array = array.astype(np.float32, copy=False)
    return np.ascontiguousarray(array)


def _decode_audio(content: bytes) -> dict[str, Any] | None:
    with av.open(bytes_io.BytesIO(content), mode="r") as container:
        if not container.streams.audio:
            return None
        stream = container.streams.audio[0]
        sample_rate = int(stream.codec_context.sample_rate or stream.rate or 44_100)
        layout = stream.layout.name if stream.layout else "stereo"
        resampler = av.AudioResampler(format="fltp", layout=layout, rate=sample_rate)
        chunks: list[np.ndarray] = []
        for frame in container.decode(stream):
            for converted in resampler.resample(frame):
                chunks.append(_audio_array(converted))
        for converted in resampler.resample(None):
            chunks.append(_audio_array(converted))
    if not chunks:
        return None
    waveform = torch.from_numpy(np.concatenate(chunks, axis=1)).unsqueeze(0)
    return {"waveform": waveform, "sample_rate": sample_rate}


def _trim_audio(
    audio: dict[str, Any] | None, start: float, duration: float
) -> dict[str, Any] | None:
    if audio is None:
        return None
    waveform = torch.as_tensor(audio["waveform"]).detach().cpu().float()
    sample_rate = int(audio["sample_rate"])
    first = min(waveform.shape[-1], max(0, round(start * sample_rate)))
    last = waveform.shape[-1]
    if duration > 0:
        last = min(last, first + max(1, round(duration * sample_rate)))
    return {
        "waveform": waveform[..., first:last].contiguous(),
        "sample_rate": sample_rate,
    }


async def _decode_video(
    video: sdk.VideoRef,
) -> tuple[torch.Tensor, dict[str, Any] | None, float]:
    content, trim_start, trim_duration = await _encoded_source(video)
    frames: list[torch.Tensor] = []
    with av.open(bytes_io.BytesIO(content), mode="r") as container:
        if not container.streams.video:
            raise ValueError("VIDEO contains no video stream")
        stream = container.streams.video[0]
        fps = _float_rate(
            stream.average_rate or stream.guessed_rate or stream.base_rate
        )
        width = int(stream.codec_context.width)
        height = int(stream.codec_context.height)
        if width < 1 or height < 1:
            raise ValueError("VIDEO has invalid dimensions")
        for frame in container.decode(stream):
            if len(frames) >= _MAX_FRAMES:
                raise ValueError(f"VIDEO exceeds {_MAX_FRAMES} decoded frames")
            array = frame.to_ndarray(format="rgb24")
            frames.append(torch.from_numpy(np.asarray(array).copy()))
            if len(frames) * width * height > _MAX_DECODED_PIXELS:
                raise ValueError("VIDEO exceeds the secure decoded-pixel limit")
    if not frames:
        raise ValueError("VIDEO contains no decodable frames")
    pixels = torch.stack(frames).float().div_(255.0)
    first = min(len(pixels), max(0, round(trim_start * fps)))
    last = len(pixels)
    if trim_duration > 0:
        last = min(last, first + max(1, round(trim_duration * fps)))
    pixels = pixels[first:last].contiguous()
    if not len(pixels):
        raise ValueError("the active VIDEO trim window contains no frames")
    audio = _trim_audio(_decode_audio(content), trim_start, trim_duration)
    return pixels, audio, fps


async def _audio_value(audio: Any) -> dict[str, Any]:
    value = await audio.value() if isinstance(audio, sdk.AudioRef) else audio
    if (
        not isinstance(value, dict)
        or "waveform" not in value
        or "sample_rate" not in value
    ):
        raise TypeError("audio must contain waveform and sample_rate")
    waveform = torch.as_tensor(value["waveform"]).detach().cpu().float()
    if waveform.ndim != 3 or waveform.shape[0] < 1 or not 1 <= waveform.shape[1] <= 8:
        raise ValueError("audio waveform must have shape [batch, channels, samples]")
    sample_rate = int(value["sample_rate"])
    if not 8_000 <= sample_rate <= 192_000:
        raise ValueError("audio sample rate must be in [8000, 192000]")
    return {"waveform": waveform[:1].contiguous(), "sample_rate": sample_rate}


def _resample_audio(
    audio: dict[str, Any], sample_rate: int, channels: int
) -> torch.Tensor:
    waveform = torch.as_tensor(audio["waveform"]).detach().cpu().float()[:1]
    source_rate = int(audio["sample_rate"])
    if source_rate != sample_rate:
        size = max(1, round(waveform.shape[-1] * sample_rate / source_rate))
        waveform = functional.interpolate(
            waveform, size=size, mode="linear", align_corners=False
        )
    if waveform.shape[1] == 1 and channels > 1:
        waveform = waveform.expand(-1, channels, -1)
    elif waveform.shape[1] < channels:
        missing = channels - waveform.shape[1]
        waveform = torch.cat(
            [waveform, waveform[:, -1:].expand(-1, missing, -1)], dim=1
        )
    elif waveform.shape[1] > channels:
        waveform = waveform[:, :channels]
    return waveform.contiguous()


def _silence(seconds: float, sample_rate: int, channels: int) -> torch.Tensor:
    return torch.zeros(1, channels, max(1, round(seconds * sample_rate)))


async def _make_video(
    frames: torch.Tensor,
    audio: dict[str, Any] | None,
    fps: float,
    prefix: str,
) -> sdk.VideoRef:
    images = await sdk.ImageRef._from_raw(frames.detach().cpu().float().clamp(0, 1))
    audio_ref = None if audio is None else await sdk.AudioRef.from_value(audio)
    ui_value = await sdk.ctx().output.save_video(
        images,
        audio=audio_ref,
        fps=float(fps),
        filename_prefix=prefix,
        format="mp4",
        codec="h264",
        encoder_options={"pixel_format": "yuv420p", "crf": 18, "preset": "medium"},
        save_output=False,
        save_metadata=False,
        audio_codec="aac",
        audio_bitrate_kbps=192,
    )
    records = ui_value.get("videos") or ui_value.get("images") or []
    if len(records) != 1:
        raise RuntimeError("the media broker did not return one video artifact")
    record = records[0]
    logical = "/".join(
        part
        for part in (str(record.get("subfolder") or ""), str(record["filename"]))
        if part
    )
    folder = str(record.get("type") or "temp")
    asset = await sdk.ctx().assets.resolve(folder, logical)
    return await sdk.ctx().assets.load_video(asset)


def _nearest_frames(
    frames: torch.Tensor, source_fps: float, target_fps: float
) -> torch.Tensor:
    if abs(source_fps - target_fps) <= 0.01:
        return frames
    count = max(1, round(len(frames) * target_fps / source_fps))
    positions = torch.arange(count).mul(source_fps / target_fps).round().long()
    return frames[positions.clamp_max(len(frames) - 1)]


def _even_floor(value: float, divisor: int) -> int:
    divisor = max(2, int(divisor or 0))
    result = int(value)
    result -= result % divisor
    return max(divisor, result)


def _offsets(canvas_w: int, canvas_h: int, inner_w: int, inner_h: int, position: str):
    dx, dy = canvas_w - inner_w, canvas_h - inner_h
    if position == "top":
        left, top = dx // 2, 0
    elif position == "bottom":
        left, top = dx // 2, dy
    elif position == "left":
        left, top = 0, dy // 2
    elif position == "right":
        left, top = dx, dy // 2
    else:
        left, top = dx // 2, dy // 2
    left -= left % 2
    top -= top % 2
    return left, dx - left, top, dy - top


def _parse_color(value: str) -> torch.Tensor:
    names = {
        "black": (0, 0, 0),
        "white": (255, 255, 255),
        "red": (255, 0, 0),
        "green": (0, 128, 0),
        "blue": (0, 0, 255),
        "yellow": (255, 255, 0),
        "cyan": (0, 255, 255),
        "magenta": (255, 0, 255),
        "gray": (128, 128, 128),
        "grey": (128, 128, 128),
        "silver": (192, 192, 192),
        "orange": (255, 165, 0),
        "purple": (128, 0, 128),
        "pink": (255, 192, 203),
    }
    text = str(value or "").strip().lower()
    if text in names:
        values = names[text]
    elif text.startswith(("#", "0x")):
        raw = text[2:] if text.startswith("0x") else text[1:]
        if len(raw) == 3:
            raw = "".join(ch * 2 for ch in raw)
        if len(raw) != 6:
            raise ValueError(f"Cannot parse pad_color: {value!r}")
        values = tuple(int(raw[index : index + 2], 16) for index in (0, 2, 4))
    else:
        parts = [
            part.strip() for part in text.replace(";", ",").split(",") if part.strip()
        ]
        if len(parts) == 1:
            parts *= 3
        if len(parts) != 3:
            raise ValueError(f"Cannot parse pad_color: {value!r}")
        parsed = [float(part) for part in parts]
        if max(parsed) <= 1:
            parsed = [channel * 255 for channel in parsed]
        values = tuple(max(0, min(255, round(channel))) for channel in parsed)
    return torch.tensor(values, dtype=torch.float32).div_(255.0)


def _scale(frames: torch.Tensor, width: int, height: int, method: str) -> torch.Tensor:
    if (frames.shape[2], frames.shape[1]) == (width, height):
        return frames
    if method == "lanczos":
        output = []
        for frame in frames:
            array = frame.mul(255).round().byte().numpy()
            resized = Image.fromarray(array).resize(
                (width, height), Image.Resampling.LANCZOS
            )
            output.append(
                torch.from_numpy(np.asarray(resized).copy()).float().div_(255.0)
            )
        return torch.stack(output)
    nchw = frames.movedim(-1, 1)
    kwargs = {"size": (height, width), "mode": method}
    if method in {"bilinear", "bicubic"}:
        kwargs["align_corners"] = False
        kwargs["antialias"] = True
    return functional.interpolate(nchw, **kwargs).movedim(1, -1).clamp(0, 1)


def _resize_frames(
    frames: torch.Tensor,
    width: int,
    height: int,
    method: str,
    mode: str,
    pad_color: str,
    position: str,
    divisible_by: int,
) -> torch.Tensor:
    source_h, source_w = map(int, frames.shape[1:3])
    div = max(2, int(divisible_by or 0))
    if mode == "stretch":
        return _scale(
            frames,
            _even_floor(width or source_w, div),
            _even_floor(height or source_h, div),
            method,
        )
    if mode == "crop":
        out_w = _even_floor(width or source_w, div)
        out_h = _even_floor(height or source_h, div)
        source_ratio, target_ratio = source_w / source_h, out_w / out_h
        if source_ratio > target_ratio:
            crop_w, crop_h = round(source_h * target_ratio), source_h
        else:
            crop_w, crop_h = source_w, round(source_w / target_ratio)
        crop_w = max(2, min(source_w, crop_w - crop_w % 2))
        crop_h = max(2, min(source_h, crop_h - crop_h % 2))
        left, _, top, _ = _offsets(source_w, source_h, crop_w, crop_h, position)
        return _scale(
            frames[:, top : top + crop_h, left : left + crop_w], out_w, out_h, method
        )
    if mode == "total_pixels":
        area = max(1, int(width or 0) * int(height or 0))
        ratio = source_w / source_h
        raw_w, raw_h = math.sqrt(area * ratio), math.sqrt(area / ratio)
    elif width <= 0 and height <= 0:
        raw_w, raw_h = source_w, source_h
    elif width <= 0:
        raw_w, raw_h = source_w * height / source_h, height
    elif height <= 0:
        raw_w, raw_h = width, source_h * width / source_w
    else:
        ratio = min(width / source_w, height / source_h)
        raw_w, raw_h = source_w * ratio, source_h * ratio
    inner_w, inner_h = _even_floor(raw_w, div), _even_floor(raw_h, div)
    inner = _scale(frames, inner_w, inner_h, method)
    if mode == "resize" or mode == "total_pixels":
        return inner
    canvas_w = max(inner_w, int(width) if width > 0 else inner_w)
    canvas_h = max(inner_h, int(height) if height > 0 else inner_h)
    left, right, top, bottom = _offsets(canvas_w, canvas_h, inner_w, inner_h, position)
    if (inner_w + left + right) % div:
        right += div - ((inner_w + left + right) % div)
    if (inner_h + top + bottom) % div:
        bottom += div - ((inner_h + top + bottom) % div)
    out_w, out_h = inner_w + left + right, inner_h + top + bottom
    if not any((left, right, top, bottom)):
        return inner
    if mode == "pad_edge_pixel":
        return functional.pad(
            inner.movedim(-1, 1), (left, right, top, bottom), mode="replicate"
        ).movedim(1, -1)
    if mode == "pillarbox_blur":
        cover_ratio = max(out_w / source_w, out_h / source_h)
        cover = _scale(
            frames,
            math.ceil(source_w * cover_ratio),
            math.ceil(source_h * cover_ratio),
            "bilinear",
        )
        x = max(0, (cover.shape[2] - out_w) // 2)
        y = max(0, (cover.shape[1] - out_h) // 2)
        background = cover[:, y : y + out_h, x : x + out_w].movedim(-1, 1)
        background = functional.avg_pool2d(
            background, kernel_size=15, stride=1, padding=7
        )
        luma = background.mean(dim=1, keepdim=True)
        background = ((background * 0.8 + luma * 0.2) * 0.35).movedim(1, -1)
        background[:, top : top + inner_h, left : left + inner_w] = inner
        return background
    canvas = torch.empty(len(frames), out_h, out_w, 3, dtype=frames.dtype)
    if mode == "pad":
        canvas[:] = _parse_color(pad_color)
    elif mode == "pad_edge":
        canvas.zero_()
        if top:
            canvas[:, :top, left : left + inner_w] = inner[:, :1].mean(
                dim=2, keepdim=True
            )
        if bottom:
            canvas[:, top + inner_h :, left : left + inner_w] = inner[:, -1:].mean(
                dim=2, keepdim=True
            )
        if left:
            canvas[:, :, :left] = inner[:, :, :1].mean(dim=1, keepdim=True)
        if right:
            canvas[:, :, left + inner_w :] = inner[:, :, -1:].mean(dim=1, keepdim=True)
    else:
        raise ValueError(f"unknown resize mode {mode!r}")
    canvas[:, top : top + inner_h, left : left + inner_w] = inner
    return canvas


class VideoConcat(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw", "output", "assets")

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="VideoConcat",
            display_name="Video Concat (FFmpeg)",
            category="FFmpeg Video",
            description="Concatenate two videos with matching audio and optional overlap.",
            inputs=[
                io.Video.Input(
                    "source_video", tooltip="The first (source) video to concatenate."
                ),
                io.Video.Input(
                    "extend_video", tooltip="The second (extend) video to append."
                ),
                io.Int.Input("overlap", default=15, min=0, max=10000, step=1),
                io.Combo.Input(
                    "overlap_type",
                    options=["linear_crossfade", "cut_source", "cut_extend"],
                ),
                io.Combo.Input(
                    "audio_sample_rate", options=["source_video", "extend_video"]
                ),
            ],
            outputs=[io.Video.Output("video")],
        )

    @classmethod
    async def execute(
        cls, source_video, extend_video, overlap, overlap_type, audio_sample_rate
    ):
        source, source_audio, source_fps = await _decode_video(source_video)
        extend, extend_audio, extend_fps = await _decode_video(extend_video)
        if source.shape[1:3] != extend.shape[1:3]:
            raise ValueError(
                f"Resolution mismatch — source is {source.shape[2]}x{source.shape[1]}, "
                f"extend is {extend.shape[2]}x{extend.shape[1]}. Both videos must have the same resolution."
            )
        extend = _nearest_frames(extend, extend_fps, source_fps)
        overlap = int(overlap)
        if overlap and overlap >= len(source):
            raise ValueError("overlap exceeds source duration")
        if overlap_type == "cut_extend" and overlap >= len(extend):
            raise ValueError("overlap exceeds extend duration")
        if overlap == 0:
            frames = torch.cat([source, extend])
        elif overlap_type == "cut_source":
            frames = torch.cat([source[:-overlap], extend])
        elif overlap_type == "cut_extend":
            frames = torch.cat([source, extend[overlap:]])
        else:
            alpha = torch.linspace(0, 1, overlap + 2)[1:-1, None, None, None]
            blend = source[-overlap:] * (1 - alpha) + extend[:overlap] * alpha
            frames = torch.cat([source[:-overlap], blend, extend[overlap:]])

        audio = None
        if source_audio is not None or extend_audio is not None:
            selected = (
                source_audio if audio_sample_rate == "source_video" else extend_audio
            )
            selected = selected or source_audio or extend_audio
            sample_rate = int(selected["sample_rate"])
            channels = max(
                2,
                0 if source_audio is None else source_audio["waveform"].shape[1],
                0 if extend_audio is None else extend_audio["waveform"].shape[1],
            )
            first = (
                _silence(len(source) / source_fps, sample_rate, channels)
                if source_audio is None
                else _resample_audio(source_audio, sample_rate, channels)
            )
            second = (
                _silence(len(extend) / source_fps, sample_rate, channels)
                if extend_audio is None
                else _resample_audio(extend_audio, sample_rate, channels)
            )
            samples = round(overlap / source_fps * sample_rate)
            if overlap == 0:
                waveform = torch.cat([first, second], -1)
            elif overlap_type == "cut_source":
                waveform = torch.cat([first[..., :-samples], second], -1)
            elif overlap_type == "cut_extend":
                waveform = torch.cat([first, second[..., samples:]], -1)
            else:
                ramp = torch.linspace(0, 1, samples + 2)[1:-1]
                mixed = (
                    first[..., -samples:] * (1 - ramp) + second[..., :samples] * ramp
                )
                waveform = torch.cat(
                    [first[..., :-samples], mixed, second[..., samples:]], -1
                )
            audio = {"waveform": waveform.contiguous(), "sample_rate": sample_rate}
        return io.NodeOutput(
            await _make_video(frames, audio, source_fps, "ffmpeg-video/concat")
        )


class VideoAddAudio(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw", "output", "assets")

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="VideoAddAudio",
            display_name="Video Add Audio (FFmpeg)",
            category="FFmpeg Video",
            description="Add or replace a video's audio with start or end alignment.",
            inputs=[
                io.Video.Input("video", tooltip="The target video."),
                io.Combo.Input("align", options=["start", "end"]),
                io.Audio.Input("audio", optional=True),
                io.String.Input(
                    "audio_file",
                    default="",
                    optional=True,
                    tooltip="Logical name of an uploaded audio file, used when AUDIO is disconnected.",
                ),
            ],
            outputs=[io.Video.Output("video")],
        )

    @classmethod
    async def execute(cls, video, align, audio=None, audio_file=""):
        frames, _old_audio, fps = await _decode_video(video)
        if audio is not None:
            replacement = await _audio_value(audio)
        elif str(audio_file).strip():
            asset = await sdk.ctx().assets.resolve("input", str(audio_file).strip())
            replacement = _decode_audio(await sdk.ctx().assets.read_bytes(asset))
            if replacement is None:
                raise ValueError("the selected input file contains no audio stream")
        else:
            raise ValueError(
                "No audio input provided. Connect AUDIO or select an uploaded audio file."
            )
        rate = int(replacement["sample_rate"])
        waveform = torch.as_tensor(replacement["waveform"]).detach().cpu().float()[:1]
        wanted = max(1, round(len(frames) / fps * rate))
        if waveform.shape[-1] > wanted:
            waveform = (
                waveform[..., :wanted] if align == "start" else waveform[..., -wanted:]
            )
        elif align == "end" and waveform.shape[-1] < wanted:
            waveform = functional.pad(waveform, (wanted - waveform.shape[-1], 0))
        replacement = {"waveform": waveform.contiguous(), "sample_rate": rate}
        return io.NodeOutput(
            await _make_video(frames, replacement, fps, "ffmpeg-video/audio")
        )


class VideoExtractSegment(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="VideoExtractSegment",
            display_name="Video Extract Segment (FFmpeg)",
            category="FFmpeg Video",
            description="Extract a frame-accurate image batch and corresponding audio.",
            inputs=[
                io.Video.Input("video", tooltip="The source video to extract from."),
                io.Int.Input("start_frame", default=0, min=0, step=1),
                io.Int.Input("length", default=30, min=1, step=1),
            ],
            outputs=[io.Image.Output("images"), io.Audio.Output("audio")],
        )

    @classmethod
    async def execute(cls, video, start_frame, length):
        frames, audio, fps = await _decode_video(video)
        start = int(start_frame)
        if start >= len(frames):
            raise ValueError(
                f"start_frame ({start}) exceeds video frame count ({len(frames)})."
            )
        length = min(int(length), len(frames) - start)
        images = await sdk.ImageRef._from_raw(
            frames[start : start + length].contiguous()
        )
        duration = length / fps
        sample_rate = 44_100 if audio is None else int(audio["sample_rate"])
        channels = 2 if audio is None else int(audio["waveform"].shape[1])
        if audio is None:
            waveform = _silence(duration, sample_rate, channels)
        else:
            first = round(start / fps * sample_rate)
            wanted = max(1, round(duration * sample_rate))
            waveform = audio["waveform"][..., first : first + wanted]
            if waveform.shape[-1] < wanted:
                waveform = functional.pad(waveform, (0, wanted - waveform.shape[-1]))
        audio_ref = await sdk.AudioRef.from_value(
            {"waveform": waveform.contiguous(), "sample_rate": sample_rate}
        )
        return io.NodeOutput(images, audio_ref)


class VideoInfo(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="VideoInfo",
            display_name="Video Info (FFmpeg)",
            category="FFmpeg Video",
            description="Inspect technical video and audio metadata.",
            inputs=[io.Video.Input("video")],
            outputs=[
                io.Int.Output("width"),
                io.Int.Output("height"),
                io.Float.Output("fps"),
                io.Float.Output("duration"),
                io.Int.Output("frame_count"),
                io.String.Output("video_codec"),
                io.Int.Output("video_bitrate_kbps"),
                io.Int.Output("audio_channels"),
                io.Int.Output("audio_sample_rate"),
                io.Int.Output("audio_bit_depth"),
                io.String.Output("audio_codec"),
                io.Int.Output("audio_bitrate_kbps"),
            ],
        )

    @classmethod
    async def execute(cls, video):
        content, _trim_start, trim_duration = await _encoded_source(video)
        with av.open(bytes_io.BytesIO(content), mode="r") as container:
            if not container.streams.video:
                raise ValueError("VIDEO contains no video stream")
            stream = container.streams.video[0]
            audio = container.streams.audio[0] if container.streams.audio else None
            fps = _float_rate(
                stream.average_rate or stream.guessed_rate or stream.base_rate
            )
            duration = trim_duration or (
                float(stream.duration * stream.time_base)
                if stream.duration is not None
                else float(container.duration or 0) / av.time_base
            )
            frame_count = (
                max(0, round(duration * fps))
                if trim_duration
                else int(stream.frames or round(duration * fps))
            )
            video_rate = int((stream.bit_rate or container.bit_rate or 0) / 1000)
            codec = stream.codec_context.name or "unknown"
            if audio is None:
                audio_values = (0, 0, 0, "", 0)
            else:
                audio_codec = audio.codec_context.name or "unknown"
                raw_bits = int(
                    getattr(audio.codec_context, "bits_per_raw_sample", 0) or 0
                )
                bit_depth = raw_bits or (
                    16 if audio_codec in {"aac", "mp3", "opus", "vorbis"} else 0
                )
                audio_values = (
                    int(audio.codec_context.channels),
                    int(audio.codec_context.sample_rate or 0),
                    bit_depth,
                    audio_codec,
                    int((audio.bit_rate or 0) / 1000),
                )
            return io.NodeOutput(
                int(stream.codec_context.width),
                int(stream.codec_context.height),
                fps,
                duration,
                frame_count,
                codec,
                video_rate,
                *audio_values,
            )


class VideoResize(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw", "output", "assets")

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="VideoResize",
            display_name="Video Resize (FFmpeg)",
            category="FFmpeg Video",
            description="Resize a video while preserving its audio and trim window.",
            inputs=[
                io.Video.Input("video"),
                io.Int.Input("width", default=512, min=0, max=16384, step=1),
                io.Int.Input("height", default=512, min=0, max=16384, step=1),
                io.Combo.Input("upscale_method", options=_METHODS, default="lanczos"),
                io.Combo.Input("keep_proportion", options=_MODES, default="resize"),
                io.String.Input("pad_color", default="0, 0, 0"),
                io.Combo.Input("crop_position", options=_POSITIONS, default="center"),
                io.Int.Input("divisible_by", default=2, min=0, max=512, step=1),
            ],
            outputs=[io.Video.Output("video")],
        )

    @classmethod
    async def execute(
        cls,
        video,
        width,
        height,
        upscale_method,
        keep_proportion,
        pad_color,
        crop_position,
        divisible_by,
    ):
        frames, audio, fps = await _decode_video(video)
        resized = _resize_frames(
            frames,
            int(width),
            int(height),
            str(upscale_method),
            str(keep_proportion),
            str(pad_color),
            str(crop_position),
            int(divisible_by),
        )
        return io.NodeOutput(
            await _make_video(resized, audio, fps, "ffmpeg-video/resize")
        )


NODE_CLASS_MAPPINGS = {
    "VideoConcat": VideoConcat,
    "VideoAddAudio": VideoAddAudio,
    "VideoExtractSegment": VideoExtractSegment,
    "VideoInfo": VideoInfo,
    "VideoResize": VideoResize,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VideoConcat": "Video Concat (FFmpeg)",
    "VideoAddAudio": "Video Add Audio (FFmpeg)",
    "VideoExtractSegment": "Video Extract Segment (FFmpeg)",
    "VideoInfo": "Video Info (FFmpeg)",
    "VideoResize": "Video Resize (FFmpeg)",
}
