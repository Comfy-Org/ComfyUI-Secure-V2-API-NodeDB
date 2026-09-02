"""Secure Nodes 2.0 implementations for VideoHelperSuite's 40 nodes."""
from __future__ import annotations

import base64
import functools
import io as bytes_io
import math
import pathlib
import tempfile
import wave
from collections import Counter
from typing import Any

import av
import numpy as np
import torch
from PIL import Image, ImageOps

from . import _vhs_tensor
from ._image_ops import common_upscale
from ._secure_runtime import (
    SCHEMAS,
    bind_node,
    materialize,
    sdk,
)


def _ctx():
    return sdk.ctx()


def _input_name(value: str) -> str:
    name = str(value or "").strip().strip('"')
    for suffix in (" [input]", "[input]"):
        if name.endswith(suffix):
            name = name[: -len(suffix)].rstrip()
    name = name.replace("\\", "/")
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
        raise ValueError(
            "secure VHS loaders accept a relative name from ComfyUI's input "
            "catalogue; host paths and URLs are not filesystem authority"
        )
    return path.as_posix()


async def _asset_bytes(name: str) -> tuple[str, bytes]:
    logical = _input_name(name)
    asset = await _ctx().assets.resolve("input", logical)
    return logical, await _ctx().assets.read_bytes(asset)


async def _asset_file(name: str) -> tuple[str, pathlib.Path]:
    logical = _input_name(name)
    asset = await _ctx().assets.resolve("input", logical)
    size = int(await _ctx().assets.size(asset))
    if not 0 <= size <= 8 * 1024 * 1024 * 1024:
        raise ValueError("secure VHS media assets are limited to 8 GiB")
    suffix = pathlib.PurePosixPath(logical).suffix[:16]
    file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    path = pathlib.Path(file.name)
    try:
        offset = 0
        while offset < size:
            chunk = await _ctx().assets.read_range(
                asset, offset=offset,
                length=min(8 * 1024 * 1024, size - offset))
            if not chunk:
                raise IOError("asset ended before its declared size")
            file.write(chunk)
            offset += len(chunk)
        file.flush()
    except BaseException:
        file.close()
        path.unlink(missing_ok=True)
        raise
    file.close()
    return logical, path


def _audio_tensor(path: pathlib.Path, start: float = 0.0,
                  duration: float = 0.0) -> dict[str, Any]:
    chunks = []
    sample_rate = 44100
    with av.open(str(path)) as container:
        streams = [stream for stream in container.streams if stream.type == "audio"]
        if not streams:
            return {
                "waveform": torch.zeros((1, 1, 0), dtype=torch.float32),
                "sample_rate": sample_rate,
            }
        stream = streams[0]
        sample_rate = int(stream.rate or sample_rate)
        start = max(0.0, float(start))
        stop = start + float(duration) if duration and duration > 0 else None
        for frame in container.decode(stream):
            frame_time = float(frame.time or 0.0)
            frame_duration = float(frame.samples) / float(frame.sample_rate)
            if frame_time + frame_duration <= start:
                continue
            if stop is not None and frame_time >= stop:
                break
            array = frame.to_ndarray()
            channels = len(frame.layout.channels)
            if array.ndim == 1:
                array = array.reshape(channels, -1)
            elif not frame.format.is_planar:
                array = array.reshape(-1, channels).T
            if np.issubdtype(array.dtype, np.integer):
                info = np.iinfo(array.dtype)
                array = array.astype(np.float32) / float(max(abs(info.min), info.max))
            else:
                array = array.astype(np.float32, copy=False)
            chunks.append(torch.from_numpy(np.ascontiguousarray(array)))
    waveform = (
        torch.cat(chunks, dim=1).unsqueeze(0)
        if chunks else torch.zeros((1, 1, 0), dtype=torch.float32)
    )
    return {"waveform": waveform, "sample_rate": sample_rate}


def _target_size(width: int, height: int, custom_width: int,
                 custom_height: int, alignment: int = 1) -> tuple[int, int]:
    target_width = int(custom_width or 0)
    target_height = int(custom_height or 0)
    if target_width <= 0 and target_height <= 0:
        target_width, target_height = width, height
    elif target_width <= 0:
        target_width = max(1, round(width * target_height / height))
    elif target_height <= 0:
        target_height = max(1, round(height * target_width / width))
    step = max(1, int(alignment or 1))
    target_width = max(step, round(target_width / step) * step)
    target_height = max(step, round(target_height / step) * step)
    return target_width, target_height


_LOAD_FORMATS = {
    "None": {},
    "AnimateDiff": {"target_rate": 8, "dim": (8, 0, 512, 512)},
    "Mochi": {"target_rate": 24, "dim": (16, 0, 848, 480), "frames": (6, 1)},
    "LTXV": {"target_rate": 24, "dim": (32, 0, 768, 512), "frames": (8, 1)},
    "Hunyuan": {"target_rate": 24, "dim": (16, 0, 848, 480), "frames": (4, 1)},
    "Cosmos": {"target_rate": 24, "dim": (16, 0, 1280, 704), "frames": (8, 1)},
    "Wan": {"target_rate": 16, "dim": (8, 0, 832, 480), "frames": (4, 1)},
    "H3": {"target_rate": 24, "dim": (32, 0, 1344, 768), "frames": (17, 5)},
}


def _decode_video(
    path: pathlib.Path,
    *,
    force_rate: float = 0,
    custom_width: int = 0,
    custom_height: int = 0,
    frame_load_cap: int = 0,
    skip_first_frames: int = 0,
    select_every_nth: int = 1,
    start_time: float | None = None,
    rgba: bool = False,
    alignment: int = 1,
) -> tuple[torch.Tensor, dict[str, Any]]:
    decoded = []
    timestamps = []
    with av.open(str(path)) as container:
        streams = [stream for stream in container.streams if stream.type == "video"]
        if not streams:
            raise ValueError("input contains no video stream")
        stream = streams[0]
        source_fps = float(stream.average_rate or stream.base_rate or 1.0)
        source_width = int(stream.width)
        source_height = int(stream.height)
        source_count = int(stream.frames or 0)
        source_duration = (
            float(stream.duration * stream.time_base)
            if stream.duration is not None else
            float(container.duration or 0) / float(av.time_base)
        )
        start = max(0.0, float(start_time or 0.0))
        decoded_total = 0
        for source_index, frame in enumerate(container.decode(stream)):
            decoded_total += 1
            timestamp = float(
                frame.time if frame.time is not None
                else source_index / max(source_fps, 1e-9)
            )
            if timestamp + 1e-9 < start:
                continue
            decoded.append(frame.to_ndarray(format="rgba" if rgba else "rgb24"))
            timestamps.append(timestamp)
    if not decoded:
        raise ValueError("no frames matched the requested VHS load window")

    target_fps = float(force_rate or 0) or source_fps
    if force_rate:
        end = source_duration if source_duration > start else (
            timestamps[-1] + 1.0 / max(source_fps, 1e-9))
        target_count = max(1, math.floor(
            max(0.0, end - start) * target_fps + 1e-6))
        target_times = start + np.arange(target_count) / target_fps
        indices = np.searchsorted(
            np.asarray(timestamps), target_times, side="right") - 1
        indices = np.clip(indices, 0, len(decoded) - 1).tolist()
    else:
        indices = list(range(len(decoded)))
    every = max(1, int(select_every_nth or 1))
    if start_time is None:
        indices = indices[max(0, int(skip_first_frames or 0))::every]
    cap = max(0, int(frame_load_cap or 0))
    if cap:
        indices = indices[:cap]
    if not indices:
        raise ValueError("no frames matched the requested VHS load window")
    images = torch.stack([
        torch.from_numpy(decoded[index].astype(np.float32) / 255.0)
        for index in indices
    ])
    new_width, new_height = _target_size(
        source_width, source_height, custom_width, custom_height, alignment)
    if images.shape[2] != new_width or images.shape[1] != new_height:
        images = common_upscale(
            images.movedim(-1, 1),
            new_width,
            new_height,
            "lanczos",
            "center",
        ).movedim(1, -1)
    loaded_fps = target_fps / every if start_time is None else target_fps
    info = {
        "source_fps": source_fps,
        "source_frame_count": source_count or decoded_total,
        "source_duration": source_duration,
        "source_width": source_width,
        "source_height": source_height,
        "loaded_fps": loaded_fps,
        "loaded_frame_count": len(images),
        "loaded_duration": len(images) / max(loaded_fps, 1e-9),
        "loaded_width": int(images.shape[2]),
        "loaded_height": int(images.shape[1]),
    }
    return images, info


async def _encode_with_vae(images: torch.Tensor, vae):
    if vae is None:
        return await sdk.ImageRef._from_raw(images)
    image_ref = await sdk.ImageRef._from_raw(images[..., :3])
    return await vae.encode(image_ref)


async def _load_video_common(
    *,
    video,
    force_rate=0,
    custom_width=0,
    custom_height=0,
    frame_load_cap=0,
    skip_first_frames=0,
    select_every_nth=1,
    start_time=None,
    vae=None,
    rgba=False,
    format="None",
    **_kwargs,
):
    format_name = str(format or "None")
    if format_name not in _LOAD_FORMATS:
        raise ValueError(f"unknown VHS load format {format_name!r}")
    format_options = _LOAD_FORMATS[format_name]
    if not force_rate and "target_rate" in format_options:
        force_rate = format_options["target_rate"]
    dimensions = format_options.get("dim", ())
    if not custom_width and not custom_height and len(dimensions) >= 4:
        custom_width, custom_height = dimensions[2], dimensions[3]
    alignment = (
        int(dimensions[0]) if dimensions else (8 if vae is not None else 1))
    _logical, path = await _asset_file(video)
    try:
        images, info = _decode_video(
            path,
            force_rate=force_rate,
            custom_width=custom_width,
            custom_height=custom_height,
            frame_load_cap=frame_load_cap,
            skip_first_frames=skip_first_frames,
            select_every_nth=select_every_nth,
            start_time=start_time,
            rgba=rgba,
            alignment=alignment,
        )
        frame_rule = format_options.get("frames")
        if frame_rule:
            divisor, remainder = map(int, frame_rule[:2])
            usable = (len(images) - remainder) // divisor * divisor + remainder
            if usable <= 0:
                raise ValueError(
                    f"{format_name} needs a frame count congruent to "
                    f"{remainder} modulo {divisor}")
            images = images[:usable]
            info["loaded_frame_count"] = len(images)
            info["loaded_duration"] = len(images) / max(
                float(info["loaded_fps"]), 1e-9)
        audio = _audio_tensor(
            path,
            start=float(start_time or 0.0),
            duration=info["loaded_duration"],
        )
    finally:
        path.unlink(missing_ok=True)
    return await _encode_with_vae(images, vae), audio, info


async def _load_video_standard(**kwargs):
    value, audio, info = await _load_video_common(**kwargs)
    return value, info["loaded_frame_count"], audio, info


async def _load_video_ffmpeg(**kwargs):
    value, audio, info = await _load_video_common(rgba=True, **kwargs)
    if isinstance(value, sdk.LatentRef):
        return value, None, audio, info
    pixels = await value.raw()
    if pixels.shape[-1] == 4:
        image = await sdk.ImageRef._from_raw(pixels[..., :3])
        return image, 1.0 - pixels[..., 3], audio, info
    return value, torch.zeros((len(pixels), 64, 64)), audio, info


async def _load_image_path(*, image, custom_width=0, custom_height=0,
                           vae=None, **_kwargs):
    logical, data = await _asset_bytes(image)
    with Image.open(bytes_io.BytesIO(data)) as source:
        source = ImageOps.exif_transpose(source)
        has_alpha = "A" in source.getbands()
        source = source.convert("RGBA" if has_alpha else "RGB")
        width, height = _target_size(
            source.width, source.height, custom_width, custom_height)
        if source.size != (width, height):
            source = source.resize((width, height), Image.Resampling.LANCZOS)
        array = torch.from_numpy(np.asarray(source).copy()).float().div_(255.0)
    images = array[..., :3].unsqueeze(0)
    mask = (
        (1.0 - array[..., 3]).unsqueeze(0)
        if has_alpha else torch.zeros((1, 64, 64), dtype=torch.float32)
    )
    return await _encode_with_vae(images, vae), mask


async def _load_audio(*, audio_file=None, audio=None, seek_seconds=0,
                      start_time=0, duration=0, **_kwargs):
    _logical, path = await _asset_file(
        audio_file if audio_file is not None else audio)
    try:
        value = _audio_tensor(
            path,
            start=float(seek_seconds or start_time or 0),
            duration=float(duration or 0),
        )
    finally:
        path.unlink(missing_ok=True)
    loaded = value["waveform"].shape[-1] / value["sample_rate"]
    return value, loaded


async def _load_images(*, directory, image_load_cap=0, skip_first_images=0,
                       select_every_nth=1, meta_batch=None, **_kwargs):
    prefix = _input_name(directory).rstrip("/") + "/"
    names = [
        name for name in await _ctx().assets.list("input", prefix=prefix)
        if pathlib.PurePosixPath(name).suffix.lower()
        in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff"}
    ]
    names = names[max(0, int(skip_first_images or 0))::max(1, int(select_every_nth or 1))]
    if image_load_cap:
        names = names[:int(image_load_cap)]
    # A legacy BatchManager split this list across workflow requeues only to
    # lower peak memory.  Secure execution has no cross-dispatch generator
    # state, so consume the complete selection in this dispatch; truncating to
    # the first chunk would silently change the requested animation.
    if not names:
        raise FileNotFoundError(f"no input images were found under {prefix!r}")

    decoded = []
    sizes = Counter()
    has_alpha = False
    for name in names:
        _logical, data = await _asset_bytes(name)
        with Image.open(bytes_io.BytesIO(data)) as source:
            source = ImageOps.exif_transpose(source)
            has_alpha = has_alpha or "A" in source.getbands()
            source = source.convert("RGBA")
            sizes[source.size] += 1
            decoded.append(source.copy())
    target = sizes.most_common(1)[0][0]
    tensors = []
    for source in decoded:
        if source.size != target:
            source = source.resize(target, Image.Resampling.LANCZOS)
        tensors.append(torch.from_numpy(np.asarray(source).copy()).float().div_(255.0))
    batch = torch.stack(tensors)
    images = batch[..., :3]
    masks = (
        1.0 - batch[..., 3]
        if has_alpha else torch.zeros((len(batch), 64, 64), dtype=torch.float32)
    )
    return images, masks, len(images)


async def _video_combine(*, images, frame_rate, loop_count=0,
                         filename_prefix="AnimateDiff", format="video/h264-mp4",
                         pingpong=False, save_output=True, audio=None,
                         vae=None, meta_batch=None, **kwargs):
    if isinstance(images, sdk.LatentRef):
        if vae is None:
            raise ValueError("Video Combine needs a VAE when images is LATENT")
        images = await vae.decode(images)
    elif not isinstance(images, sdk.ImageRef):
        images = await sdk.ImageRef._from_raw(await materialize(images))

    if pingpong:
        pixels = await images.raw()
        if len(pixels) > 2:
            pixels = torch.cat((pixels, pixels[1:-1].flip(0)), dim=0)
        images = await sdk.ImageRef._from_raw(pixels)
    fps = float(frame_rate)

    if bool(kwargs.get("trim_to_audio", False)) and audio is not None:
        audio_value = await materialize(audio)
        duration = (
            audio_value["waveform"].shape[-1]
            / float(audio_value["sample_rate"])
        )
        pixels = await images.raw()
        frame_count = max(1, min(len(pixels), math.floor(duration * fps)))
        images = await sdk.ImageRef._from_raw(pixels[:frame_count])

    requested_format = str(format)
    if requested_format in ("image/gif", "image/webp", "video/ffmpeg-gif"):
        animation_format = "webp" if requested_format == "image/webp" else "gif"
        display = await _ctx().output.save_animation(
            images,
            fps=fps,
            filename_prefix=filename_prefix,
            format=animation_format,
            loop_count=int(loop_count),
            lossless=bool(kwargs.get("lossless", True)),
            quality=int(kwargs.get("quality", 90)),
            save_output=bool(save_output),
        )
    elif requested_format in ("video/8bit-png", "video/16bit-png"):
        display = await _ctx().output.save_image_sequence(
            images,
            filename_prefix=filename_prefix,
            format="png",
            bit_depth=16 if requested_format == "video/16bit-png" else 8,
            save_output=bool(save_output),
        )
    else:
        profiles = {
            "video/h264-mp4": ("mp4", "h264"),
            "video/h265-mp4": ("mp4", "hevc"),
            "video/nvenc_h264-mp4": ("mp4", "h264_nvenc"),
            "video/nvenc_hevc-mp4": ("mp4", "hevc_nvenc"),
            "video/nvenc_av1-mp4": ("mp4", "av1_nvenc"),
            "video/av1-webm": ("webm", "av1"),
            "video/webm": ("webm", "vp9"),
            "video/ProRes": ("mov", "prores"),
            "video/ffv1-mkv": ("mkv", "ffv1"),
        }
        if requested_format not in profiles:
            raise ValueError(f"unknown Video Combine format {requested_format!r}")
        container, codec = profiles[requested_format]
        encoder_options = {}
        if "pix_fmt" in kwargs:
            encoder_options["pixel_format"] = str(kwargs["pix_fmt"])
        if "crf" in kwargs:
            encoder_options["crf"] = int(kwargs["crf"])
        if "bitrate" in kwargs:
            multiplier = 1000 if bool(kwargs.get("megabit", True)) else 1
            encoder_options["bitrate_kbps"] = int(kwargs["bitrate"]) * multiplier
        if codec == "prores":
            profile = str(kwargs.get("profile", "hq"))
            encoder_options["profile"] = profile
            encoder_options.setdefault(
                "pixel_format",
                "yuva444p10le" if profile in ("4444", "4444xq")
                else "yuv422p10le",
            )
        elif codec == "ffv1":
            encoder_options.update({
                "level": int(kwargs.get("level", 3)),
                "coder": int(kwargs.get("coder", 1)),
                "context": int(kwargs.get("context", 1)),
                "gop_size": int(kwargs.get("gop_size", 1)),
                "slices": int(kwargs.get("slices", 16)),
                "slice_crc": str(kwargs.get("slicecrc", "1")) != "0",
            })
            encoder_options.setdefault(
                "pixel_format", str(kwargs.get("pix_fmt", "rgba64le")))
        input_depth = str(kwargs.get("input_color_depth", "8bit"))
        display = await _ctx().output.save_video(
            images,
            audio=audio,
            fps=fps,
            filename_prefix=filename_prefix,
            format=container,
            codec=codec,
            encoder_options=encoder_options,
            loop_count=int(loop_count),
            bit_depth=16 if input_depth == "16bit" else 8,
            save_output=bool(save_output),
            save_metadata=bool(kwargs.get("save_metadata", True)),
        )
    items = list(display.get("images", ()))
    preview = dict(items[0]) if items else {}
    preview.update({"format": requested_format, "frame_rate": fps})
    filename = str(display.get("pattern") or preview.get(
        "filename", filename_prefix))
    subfolder = str(preview.get("subfolder", ""))
    if subfolder and not filename.startswith(subfolder + "/"):
        filename = f"{subfolder}/{filename}"
    # The trusted writers produce only final artifacts: no metadata utility
    # PNG and no silent audio-less intermediate.  This preserves the useful
    # result while making PruneOutputs unnecessary for secure-combine output.
    filenames = (bool(save_output), [filename])
    return {"ui": {"gifs": [preview]}, "result": (filenames,)}


async def _vae_decode_batched(*, samples, vae, per_batch):
    value = await materialize(samples)
    decoded = []
    total = len(value["samples"])
    for start in range(0, total, int(per_batch)):
        batch = {
            key: item[start:start + int(per_batch)]
            if isinstance(item, torch.Tensor) and len(item) == total else item
            for key, item in value.items()
        }
        image = await vae.decode(await sdk.LatentRef.from_value(batch))
        decoded.append(await image.raw())
        await _ctx().progress.update(min(start + int(per_batch), total), total)
    return (torch.cat(decoded),)


async def _vae_encode_batched(*, pixels, vae, per_batch):
    value = await materialize(pixels)
    encoded = []
    total = len(value)
    for start in range(0, total, int(per_batch)):
        image = await sdk.ImageRef._from_raw(
            value[start:start + int(per_batch), :, :, :3])
        latent = await vae.encode(image)
        encoded.append((await latent.value())["samples"])
        await _ctx().progress.update(min(start + int(per_batch), total), total)
    return ({"samples": torch.cat(encoded)},)


def _tensor_handler(node_id: str, node_class: type):
    method = SCHEMAS[node_id]["method"]

    async def execute(**kwargs):
        values = {key: await materialize(value) for key, value in kwargs.items()}
        return getattr(node_class(), method)(**values)

    return execute


async def _video_info(video_info, **_kwargs):
    value = await materialize(video_info)
    keys = ("fps", "frame_count", "duration", "width", "height")
    return tuple(value[f"source_{key}"] for key in keys) + tuple(
        value[f"loaded_{key}"] for key in keys)


async def _video_info_source(video_info, **_kwargs):
    value = await materialize(video_info)
    return tuple(value[f"source_{key}"] for key in (
        "fps", "frame_count", "duration", "width", "height"))


async def _video_info_loaded(video_info, **_kwargs):
    value = await materialize(video_info)
    return tuple(value[f"loaded_{key}"] for key in (
        "fps", "frame_count", "duration", "width", "height"))


async def _select_filename(filenames, index, **_kwargs):
    value = await materialize(filenames)
    return (value[1][int(index)],)


async def _unbatch(batched, **_kwargs):
    inputs = list(batched)
    if not inputs:
        raise ValueError("Unbatch needs at least one input batch")
    values = [await materialize(value) for value in inputs]
    if isinstance(values[0], torch.Tensor):
        result = torch.cat(values)
        if isinstance(inputs[0], sdk.ImageRef):
            result = await sdk.ImageRef._from_raw(result)
        elif isinstance(inputs[0], sdk.MaskRef):
            result = await sdk.MaskRef._from_raw(result)
        return (result,)
    if isinstance(values[0], dict):
        result = values[0].copy()
        if "samples" in result:
            result["samples"] = torch.cat([item["samples"] for item in values])
        if "waveform" in result:
            result["waveform"] = torch.cat([item["waveform"] for item in values])
        result.pop("batch_index", None)
        if isinstance(inputs[0], sdk.LatentRef):
            result = await sdk.LatentRef.from_value(result)
        elif isinstance(inputs[0], sdk.AudioRef):
            result = await sdk.AudioRef.from_value(result)
        return (result,)
    return (functools.reduce(lambda left, right: left + right, values),)


async def _batch_manager(frames_per_batch, **_kwargs):
    return ({"frames_per_batch": int(frames_per_batch)},)


async def _audio_to_legacy(audio, **_kwargs):
    value = await materialize(audio)
    waveform = value["waveform"].detach().cpu().clamp(-1, 1)
    pcm = (waveform.squeeze(0).transpose(0, 1).numpy() * 32767).astype(np.int16)
    output = bytes_io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(pcm.shape[1])
        writer.setsampwidth(2)
        writer.setframerate(int(value["sample_rate"]))
        writer.writeframes(pcm.tobytes())
    return ({"wav_base64": base64.b64encode(output.getvalue()).decode("ascii")},)


async def _legacy_to_audio(vhs_audio, **_kwargs):
    value = await materialize(vhs_audio)
    data = base64.b64decode(value["wav_base64"], validate=True)
    with wave.open(bytes_io.BytesIO(data), "rb") as reader:
        channels = reader.getnchannels()
        rate = reader.getframerate()
        pcm = np.frombuffer(reader.readframes(reader.getnframes()), dtype=np.int16)
    waveform = torch.from_numpy(pcm.copy()).reshape(-1, channels).T.float()
    waveform = waveform.div_(32767.0).unsqueeze(0)
    return ({"waveform": waveform, "sample_rate": rate},)


async def _prune_outputs(*, filenames, options, **_kwargs):
    value = await materialize(filenames)
    files = list(value[1]) if isinstance(value, (tuple, list)) and len(value) > 1 else []
    if len(files) > 1:
        raise RuntimeError(
            "Prune Outputs cannot delete a graph-supplied list of paths from "
            "shared output storage. Secure Video Combine writes no utility or "
            "intermediate artifacts, so its output is already pruned."
        )
    if str(options) not in ("Intermediate", "Intermediate and Utility"):
        raise ValueError("unknown Prune Outputs option")
    return ()


async def _select_latest(filename_prefix, filename_postfix, **_kwargs):
    prefix = str(filename_prefix or "").replace("\\", "/")
    if prefix.startswith("output/"):
        prefix = prefix[len("output/"):]
    latest = await _ctx().assets.latest(
        "output", prefix=prefix, suffix=str(filename_postfix or ""))
    if latest is None:
        raise FileNotFoundError(
            f"no output file matches prefix {prefix!r} and "
            f"suffix {str(filename_postfix or '')!r}")
    return (latest,)


_TENSOR_NODES = {
    "VHS_SplitLatents": _vhs_tensor.SplitLatents,
    "VHS_SplitImages": _vhs_tensor.SplitImages,
    "VHS_SplitMasks": _vhs_tensor.SplitMasks,
    "VHS_MergeLatents": _vhs_tensor.MergeLatents,
    "VHS_MergeImages": _vhs_tensor.MergeImages,
    "VHS_MergeMasks": _vhs_tensor.MergeMasks,
    "VHS_GetLatentCount": _vhs_tensor.GetLatentCount,
    "VHS_GetImageCount": _vhs_tensor.GetImageCount,
    "VHS_GetMaskCount": _vhs_tensor.GetMaskCount,
    "VHS_DuplicateLatents": _vhs_tensor.RepeatLatents,
    "VHS_DuplicateImages": _vhs_tensor.RepeatImages,
    "VHS_DuplicateMasks": _vhs_tensor.RepeatMasks,
    "VHS_SelectEveryNthLatent": _vhs_tensor.SelectEveryNthLatent,
    "VHS_SelectEveryNthImage": _vhs_tensor.SelectEveryNthImage,
    "VHS_SelectEveryNthMask": _vhs_tensor.SelectEveryNthMask,
    "VHS_SelectLatents": _vhs_tensor.SelectLatents,
    "VHS_SelectImages": _vhs_tensor.SelectImages,
    "VHS_SelectMasks": _vhs_tensor.SelectMasks,
}

_HANDLERS = {
    "VHS_VideoCombine": (_video_combine, ("output", "raw", "ui")),
    "VHS_LoadVideo": (_load_video_standard, ("assets", "raw")),
    "VHS_LoadVideoPath": (_load_video_standard, ("assets", "raw")),
    "VHS_LoadVideoFFmpeg": (_load_video_ffmpeg, ("assets", "raw")),
    "VHS_LoadVideoFFmpegPath": (_load_video_ffmpeg, ("assets", "raw")),
    "VHS_LoadImagePath": (_load_image_path, ("assets", "raw")),
    "VHS_LoadImages": (_load_images, ("assets", "raw")),
    "VHS_LoadImagesPath": (_load_images, ("assets", "raw")),
    "VHS_LoadAudio": (_load_audio, ("assets", "raw")),
    "VHS_LoadAudioUpload": (_load_audio, ("assets", "raw")),
    "VHS_AudioToVHSAudio": (_audio_to_legacy, ("raw",)),
    "VHS_VHSAudioToAudio": (_legacy_to_audio, ("raw",)),
    "VHS_PruneOutputs": (_prune_outputs, ()),
    "VHS_BatchManager": (_batch_manager, ()),
    "VHS_VideoInfo": (_video_info, ("raw",)),
    "VHS_VideoInfoSource": (_video_info_source, ("raw",)),
    "VHS_VideoInfoLoaded": (_video_info_loaded, ("raw",)),
    "VHS_SelectFilename": (_select_filename, ("raw",)),
    "VHS_VAEEncodeBatched": (_vae_encode_batched, ("raw",)),
    "VHS_VAEDecodeBatched": (_vae_decode_batched, ("raw",)),
    "VHS_Unbatch": (_unbatch, ("raw",)),
    "VHS_SelectLatest": (_select_latest, ("assets",)),
}
for _node_id, _node_class in _TENSOR_NODES.items():
    _HANDLERS[_node_id] = (_tensor_handler(_node_id, _node_class), ("raw",))

if set(_HANDLERS) != set(SCHEMAS):
    raise RuntimeError(
        "VideoHelperSuite secure conversion coverage changed: "
        f"missing={sorted(set(SCHEMAS) - set(_HANDLERS))}, "
        f"extra={sorted(set(_HANDLERS) - set(SCHEMAS))}"
    )

NODE_CLASS_MAPPINGS = {
    node_id: bind_node(node_id, handler, permissions=permissions)
    for node_id, (handler, permissions) in _HANDLERS.items()
}
NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: SCHEMAS[node_id]["schema"]["attrs"]["display_name"]
    for node_id in NODE_CLASS_MAPPINGS
}


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
