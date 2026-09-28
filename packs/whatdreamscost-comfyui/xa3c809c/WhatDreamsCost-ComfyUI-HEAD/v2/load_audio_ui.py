"""Secure V2 implementation of Load Audio UI."""
from __future__ import annotations

import pathlib
import tempfile

import av
import torch

from comfy_api.latest import io, sdk


def _logical_name(value: str) -> str:
    name = str(value or "").strip().strip('"').replace("\\", "/")
    for suffix in (" [input]", "[input]"):
        if name.endswith(suffix):
            name = name[: -len(suffix)].rstrip()
    if name.startswith("input/"):
        name = name[6:]
    path = pathlib.PurePosixPath(name)
    if (
        not name
        or path.is_absolute()
        or any(part in ("", ".", "..") for part in path.parts)
        or "://" in name
        or ":" in path.parts[0]
    ):
        raise ValueError("audio must name an asset from ComfyUI's input catalogue")
    return path.as_posix()


async def _asset_file(name: str) -> tuple[str, pathlib.Path]:
    logical = _logical_name(name)
    asset = await sdk.ctx().assets.resolve("input", logical)
    size = int(await sdk.ctx().assets.size(asset))
    if not 0 <= size <= 8 * 1024 * 1024 * 1024:
        raise ValueError("audio assets are limited to 8 GiB")
    temp = tempfile.NamedTemporaryFile(suffix=pathlib.PurePosixPath(logical).suffix[:16], delete=False)
    path = pathlib.Path(temp.name)
    try:
        offset = 0
        while offset < size:
            chunk = await sdk.ctx().assets.read_range(asset, offset=offset, length=min(8 * 1024 * 1024, size - offset))
            if not chunk:
                raise IOError("audio asset ended before its declared size")
            temp.write(chunk)
            offset += len(chunk)
        temp.flush()
    except BaseException:
        temp.close()
        path.unlink(missing_ok=True)
        raise
    temp.close()
    return logical, path


def _f32_pcm(waveform: torch.Tensor) -> torch.Tensor:
    if waveform.dtype.is_floating_point:
        return waveform
    if waveform.dtype == torch.int16:
        return waveform.float() / 2**15
    if waveform.dtype == torch.int32:
        return waveform.float() / 2**31
    raise ValueError(f"Unsupported wav dtype: {waveform.dtype}")


def _decode(path: pathlib.Path) -> tuple[torch.Tensor, int]:
    with av.open(str(path)) as container:
        streams = list(container.streams.audio)
        if not streams:
            raise ValueError("No audio stream found in the file")
        stream = streams[0]
        sample_rate = int(stream.codec_context.sample_rate or 44100)
        channels = int(stream.channels or 1)
        frames = []
        for frame in container.decode(streams=stream.index):
            value = torch.from_numpy(frame.to_ndarray())
            if value.shape[0] != channels:
                value = value.view(-1, channels).t()
            frames.append(value)
    if not frames:
        raise ValueError("No audio frames decoded")
    return _f32_pcm(torch.cat(frames, dim=1)), sample_rate


class LoadAudioUI(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets", "raw")

    @classmethod
    def define_schema(cls) -> io.Schema:
        audio = io.Combo.Input(
            "audio",
            options=[],
            default="none",
            remote=io.RemoteOptions(
                route="/secure-nodes/assets/input?kind=audio,video",
                refresh_button=True,
            ),
        )
        audio.extra_dict = {"audio_upload": True}
        return io.Schema(
            node_id="LoadAudioUI",
            display_name="Load Audio UI",
            category="WhatDreamsCost",
            inputs=[
                audio,
                io.Float.Input("start_time", default=0.0, min=0.0, max=100000.0, step=0.01),
                io.Float.Input("end_time", default=0.0, min=0.0, max=100000.0, step=0.01),
                io.Float.Input("duration", default=0.0, min=0.0, max=100000.0, step=0.01),
                io.Custom("AUDIO_UI").Input("audioUI", optional=True),
            ],
            outputs=[
                io.Audio.Output("audio", display_name="audio"),
                io.Float.Output("duration", display_name="duration"),
                io.String.Output("filename", display_name="filename"),
            ],
        )

    @classmethod
    async def execute(cls, audio, start_time, end_time, duration, audioUI=None):
        logical = ""
        path = None
        try:
            if audio and audio != "none":
                logical, path = await _asset_file(audio)
                waveform, sample_rate = _decode(path)
            else:
                raise FileNotFoundError("no audio selected")
        except Exception:
            sample_rate = 44100
            waveform = torch.zeros((2, 44100), dtype=torch.float32)
            logical = ""
        finally:
            if path is not None:
                path.unlink(missing_ok=True)

        start_frame = min(int(float(start_time) * sample_rate), waveform.shape[1])
        end_frame = min(int(float(end_time) * sample_rate), waveform.shape[1]) if end_time > 0 else waveform.shape[1]
        start_frame = min(start_frame, end_frame)
        trimmed = waveform[:, start_frame:end_frame]
        if trimmed.shape[1] == 0:
            trimmed = torch.zeros((waveform.shape[0], 1), dtype=waveform.dtype)
        value = {"waveform": trimmed.unsqueeze(0), "sample_rate": sample_rate}
        return io.NodeOutput(
            await sdk.AudioRef.from_value(value),
            float(trimmed.shape[1] / sample_rate),
            pathlib.PurePosixPath(logical).name if logical else "",
        )


NODE_CLASS_MAPPINGS = {"LoadAudioUI": LoadAudioUI}
