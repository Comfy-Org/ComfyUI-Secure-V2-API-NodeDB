"""Secure implementations for the LTX Director node family.

The pack-owned timeline and tensor algorithms stay in the guest. Host-owned
models, encoders, VAEs, weights and assets are used only through V2 refs.
"""
from __future__ import annotations

import base64
import io as bytes_io
import json
import math
import pathlib

import av
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

from comfy_api.latest import io, sdk

from ._ltx_utils import (
    GuideOps,
    append_guide_attention_entry,
    conditioning_get_any_value,
    conditioning_set_values,
    get_noise_mask,
)
from .load_audio_ui import _asset_file


GuideData = io.Custom("GUIDE_DATA")
MotionGuideData = io.Custom("MOTION_GUIDE_DATA")


async def _value(value):
    if isinstance(value, sdk.ValueRef):
        return await value.value()
    return value


def _resize_image(tensor, target_w, target_h, method, divisible_by):
    def snap(value, divisor):
        return max(divisor, value // divisor * divisor)

    width, height = snap(int(target_w), divisible_by), snap(int(target_h), divisible_by)
    count, source_h, source_w, channels = tensor.shape
    if (source_h, source_w) == (height, width):
        return tensor
    source = tensor.permute(0, 3, 1, 2)
    if method == "stretch to fit":
        result = F.interpolate(source, size=(height, width), mode="bilinear", align_corners=False)
    elif method == "maintain aspect ratio":
        ratio = min(width / source_w, height / source_h)
        new_w, new_h = snap(int(source_w * ratio), divisible_by), snap(int(source_h * ratio), divisible_by)
        result = F.interpolate(source, size=(new_h, new_w), mode="bilinear", align_corners=False)
    elif method in ("pad", "pad green"):
        ratio = min(width / source_w, height / source_h)
        new_w, new_h = snap(int(source_w * ratio), divisible_by), snap(int(source_h * ratio), divisible_by)
        inner = F.interpolate(source, size=(new_h, new_w), mode="bilinear", align_corners=False)
        left, top = (width - new_w) // 2, (height - new_h) // 2
        if method == "pad green":
            result = torch.zeros((count, channels, height, width), dtype=source.dtype, device=source.device)
            result[:, 0] = 102 / 255
            result[:, 1] = 1
            result[:, :, top:top + new_h, left:left + new_w] = inner
        else:
            result = F.pad(inner, (left, width - new_w - left, top, height - new_h - top))
    elif method == "crop":
        ratio = max(width / source_w, height / source_h)
        new_w, new_h = int(source_w * ratio), int(source_h * ratio)
        inner = F.interpolate(source, size=(new_h, new_w), mode="bilinear", align_corners=False)
        left, top = (new_w - width) // 2, (new_h - height) // 2
        result = inner[:, :, top:top + height, left:left + width]
    else:
        result = F.interpolate(source, size=(height, width), mode="bilinear", align_corners=False)
    return result.permute(0, 2, 3, 1)


def _compress_image(tensor, crf):
    if not crf:
        return tensor
    count, height, width, _ = tensor.shape
    height, width = height // 2 * 2, width // 2 * 2
    frames = (tensor[:, :height, :width] * 255).byte().cpu().numpy()
    try:
        buffer = bytes_io.BytesIO()
        with av.open(buffer, mode="w", format="mp4") as container:
            stream = container.add_stream("libx264", rate=24)
            stream.width, stream.height, stream.pix_fmt = width, height, "yuv420p"
            stream.options = {"crf": str(crf), "preset": "ultrafast"}
            for item in frames:
                for packet in stream.encode(av.VideoFrame.from_ndarray(item, format="rgb24")):
                    container.mux(packet)
            for packet in stream.encode(None):
                container.mux(packet)
        buffer.seek(0)
        with av.open(buffer, mode="r") as source:
            decoded = [frame.to_ndarray(format="rgb24") for frame in source.decode(video=0)]
        if decoded:
            output = tensor.clone()
            values = torch.from_numpy(np.stack(decoded).astype(np.float32) / 255).to(tensor.device, tensor.dtype)
            output[: min(count, len(values)), :height, :width] = values[:count]
            return output
    except Exception:
        pass
    return tensor


async def _image_segment(segment):
    name = segment.get("imageFile")
    if name:
        asset = await sdk.ctx().assets.resolve("input", str(name))
        payload = await sdk.ctx().assets.read_bytes(asset)
    else:
        encoded = str(segment.get("imageB64") or "")
        if not encoded or encoded.startswith("/view?"):
            return torch.zeros((1, 512, 512, 3), dtype=torch.float32)
        payload = base64.b64decode(encoded.split(",", 1)[-1])
    with Image.open(bytes_io.BytesIO(payload)) as image:
        array = np.array(image.convert("RGB"), dtype=np.float32) / 255
    return torch.from_numpy(array).unsqueeze(0)


def _resample_frames(frames, source_fps, target_fps, target_count, mode="nearest"):
    count = int(frames.shape[0])
    target_count = max(1, int(round(float(target_count))))
    if count <= 1:
        return frames.repeat(target_count, 1, 1, 1) if count == 1 else frames
    if target_count == count and abs(float(target_fps) - float(source_fps)) < 1e-6:
        return frames
    positions = torch.linspace(0, count - 1, target_count, device=frames.device)
    if mode == "nearest":
        return frames.index_select(0, positions.round().long().clamp(0, count - 1))
    lower = positions.floor().long().clamp(0, count - 1)
    upper = positions.ceil().long().clamp(0, count - 1)
    ratio = (positions - lower.to(positions.dtype)).view(-1, 1, 1, 1)
    first = frames.index_select(0, lower).float()
    second = frames.index_select(0, upper).float()
    return (first * (1.0 - ratio) + second * ratio).to(frames.dtype)


async def _video_segment(segment, frame_rate):
    logical, path = await _asset_file(str(segment.get("imageFile") or segment.get("videoFile") or ""))
    frame_count = max(1, int(segment.get("length", 1)))
    try:
        if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
            with Image.open(path) as image:
                array = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
            return torch.from_numpy(array).unsqueeze(0).repeat(frame_count, 1, 1, 1)

        frames = []
        target_fps = max(1.0, float(frame_rate))
        start = max(0.0, float(segment.get("trimStart", 0)) / target_fps)
        duration = max(0.0, float(frame_count) / target_fps)
        end = start + duration if duration > 0 else None
        with av.open(str(path)) as container:
            stream = container.streams.video[0]
            stream.thread_type = "AUTO"
            try:
                source_fps = float(stream.average_rate or stream.base_rate)
            except Exception:
                source_fps = target_fps
            if source_fps <= 0:
                source_fps = target_fps
            if stream.time_base:
                container.seek(int(max(0, start - 0.5) / float(stream.time_base)), stream=stream, backward=True)
            decoded_count = 0
            for frame in container.decode(stream):
                if frame.time is not None:
                    timestamp = float(frame.time)
                elif frame.pts is not None and stream.time_base is not None:
                    timestamp = float(frame.pts * stream.time_base)
                else:
                    timestamp = decoded_count / source_fps
                decoded_count += 1
                if timestamp < start - 0.01:
                    continue
                if end is not None and timestamp >= end:
                    break
                frames.append(frame.to_ndarray(format="rgb24"))
    finally:
        path.unlink(missing_ok=True)
    if not frames:
        raise ValueError(f"No frames decoded for motion guide segment: {logical}")
    values = torch.from_numpy(np.asarray(frames, dtype=np.float32) / 255)
    return _resample_frames(
        values, source_fps, target_fps, frame_count,
        str(segment.get("resampleMode", "nearest")),
    )


async def _video_dimensions(name):
    _, path = await _asset_file(str(name))
    try:
        if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
            with Image.open(path) as image:
                return int(image.width), int(image.height)
        with av.open(str(path)) as container:
            stream = container.streams.video[0]
            return int(stream.width or stream.codec_context.width), int(stream.height or stream.codec_context.height)
    finally:
        path.unlink(missing_ok=True)


async def _combined_audio(timeline, start_frame, duration_frames, frame_rate, override_audio=False):
    sample_rate = 44100
    total = max(1, math.ceil(duration_frames / frame_rate * sample_rate))
    output = torch.zeros((2, total), dtype=torch.float32)
    try:
        data = json.loads(timeline) if timeline else {}
    except Exception:
        data = {}
    retake = data.get("retakeMode") and data.get("retakeVideo")
    if retake:
        source = data["retakeVideo"]
        segments = [{"videoFile": source.get("imageFile") or source.get("fileName"), "start": 0, "length": source.get("videoDurationFrames", duration_frames), "trimStart": 0}]
        override_audio = True
    else:
        segments = data.get("motionSegments" if override_audio else "audioSegments", [])
    for segment in segments:
        file_key = "videoFile" if override_audio else "audioFile"
        buffer = None
        path = None
        try:
            if segment.get(file_key):
                _, path = await _asset_file(str(segment[file_key]))
                buffer = bytes_io.BytesIO(path.read_bytes())
            elif not override_audio and segment.get("audioB64"):
                buffer = bytes_io.BytesIO(base64.b64decode(str(segment["audioB64"]).split(",", 1)[-1]))
            if buffer is None:
                continue
            blocks = []
            with av.open(buffer) as container:
                streams = list(container.streams.audio)
                if not streams:
                    continue
                resampler = av.AudioResampler(format="fltp", layout="stereo", rate=sample_rate)
                for frame in container.decode(streams[0]):
                    blocks.extend(torch.from_numpy(item.to_ndarray()) for item in resampler.resample(frame))
                blocks.extend(torch.from_numpy(item.to_ndarray()) for item in resampler.resample(None))
            if not blocks:
                continue
            waveform = torch.cat(blocks, dim=1)
            trim = float(segment.get("trimStart", 0))
            length = float(segment.get("length", 1))
            start = float(segment.get("start", 0))
            if start + length <= start_frame:
                continue
            offset = max(0, start_frame - start)
            trim += offset
            length = max(1, length - offset)
            start = max(0, start - start_frame)
            source_start = int(trim / frame_rate * sample_rate)
            source_end = min(waveform.shape[1], source_start + int(length / frame_rate * sample_rate))
            target_start = int(start / frame_rate * sample_rate)
            count = min(source_end - source_start, output.shape[1] - target_start)
            if count > 0:
                output[:, target_start:target_start + count] += waveform[:, source_start:source_start + count]
        finally:
            if path is not None:
                path.unlink(missing_ok=True)
    return {"waveform": output.unsqueeze(0), "sample_rate": sample_rate}


async def _token_ranges(clip, global_prompt, local_prompts):
    full = global_prompt
    starts, ends = [], []

    async def count(text):
        described = await clip.describe_tokens(await clip.tokenize(text))
        totals = []
        for chunks in described.values():
            totals.append(sum(1 for chunk in chunks for item in chunk if not item.get("special")))
        if not totals:
            raise ValueError("CLIP tokenizer did not expose a describable component")
        return max(totals)

    previous = await count(global_prompt)
    for prompt in local_prompts:
        full += " " + prompt
        current = await count(full)
        if current <= previous:
            raise ValueError(f"Local prompt produced no tokens: {prompt!r}")
        starts.append(previous)
        ends.append(current)
        previous = current
    return full, starts, ends


class LTXDirector(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets", "raw")

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="LTXDirector",
            display_name="LTX Director",
            category="WhatDreamsCost",
            description="WYSIWYG prompt, image, audio, and motion timeline for LTX video generation.",
            inputs=[
                io.Model.Input("model"),
                io.Clip.Input("clip"),
                io.Vae.Input("audio_vae", optional=True, tooltip="Optional Audio VAE."),
                io.Latent.Input("optional_latent", optional=True),
                io.String.Input("global_prompt", multiline=True, default="", force_input=True, optional=True),
                io.Float.Input("start_second", default=0.0, min=0.0, max=1000.0, step=0.01),
                io.Float.Input("end_second", default=5.0, min=0.0, max=1000.0, step=0.01),
                io.Float.Input("duration_seconds", default=5.0, min=0.1, max=1000.0, step=0.01),
                io.Int.Input("start_frame", default=0, min=0, max=10000, step=1),
                io.Int.Input("end_frame", default=120, min=1, max=10000, step=1),
                io.Int.Input("duration_frames", default=120, min=1, max=10000, step=1),
                io.String.Input("timeline_data", default=""),
                io.Boolean.Input("use_custom_audio", default=False, optional=True),
                io.Boolean.Input("use_custom_motion", default=True, optional=True),
                io.Boolean.Input("inpaint_audio", default=True, optional=True),
                io.String.Input("local_prompts", multiline=True, default=""),
                io.String.Input("segment_lengths", default=""),
                io.Float.Input("epsilon", default=0.001, min=0.0001, max=0.99, step=0.0001),
                io.Float.Input("frame_rate", default=24, min=1, max=240, step=1, optional=True),
                io.Combo.Input("display_mode", options=["frames", "seconds"], default="seconds", optional=True),
                io.String.Input("guide_strength", default=""),
                io.Int.Input("custom_width", default=0, min=0, max=8192, step=1, optional=True),
                io.Int.Input("custom_height", default=0, min=0, max=8192, step=1, optional=True),
                io.Combo.Input("resize_method", options=["maintain aspect ratio", "stretch to fit", "pad", "pad green", "crop"], default="maintain aspect ratio", optional=True),
                io.Int.Input("divisible_by", default=32, min=1, max=256, step=1, optional=True),
                io.Int.Input("img_compression", default=18, min=0, max=100, step=1, optional=True),
                io.Boolean.Input("override_audio", default=False, optional=True),
            ],
            outputs=[
                io.Model.Output("model", display_name="model"),
                io.Conditioning.Output("positive", display_name="positive"),
                io.Latent.Output("video_latent", display_name="video_latent"),
                io.Latent.Output("audio_latent", display_name="audio_latent"),
                GuideData.Output("guide_data", display_name="guide_data"),
                MotionGuideData.Output("motion_guide_data", display_name="motion_guide_data"),
                io.Float.Output("frame_rate", display_name="frame_rate"),
                io.Audio.Output("combined_audio", display_name="combined_audio"),
            ],
        )

    @classmethod
    async def execute(
        cls, model, clip, start_second, end_second, duration_seconds,
        start_frame, end_frame, duration_frames, timeline_data,
        local_prompts, segment_lengths, global_prompt="", guide_strength="",
        epsilon=0.001, frame_rate=24, display_mode="seconds",
        custom_width=768, custom_height=512,
        resize_method="maintain aspect ratio", divisible_by=32,
        img_compression=0, audio_vae=None, optional_latent=None,
        use_custom_audio=False, inpaint_audio=True, use_custom_motion=True,
        override_audio=False,
    ):
        try:
            timeline = json.loads(timeline_data) if timeline_data else {}
        except Exception:
            timeline = {}
        retake_active = bool(timeline.get("retakeMode") and timeline.get("retakeVideo"))
        if not global_prompt:
            global_prompt = str(timeline.get("retake_global_prompt" if retake_active else "global_prompt", ""))

        guide_data = {"images": [], "insert_frames": [], "strengths": [], "frame_rate": frame_rate}
        derived_w, derived_h = int(custom_width), int(custom_height)
        strengths = [float(value.strip()) for value in str(guide_strength).split(",") if value.strip()]
        segments = [
            value for value in timeline.get("segments", [])
            if value.get("type", "image") in ("image", "video")
            and (value.get("imageFile") or value.get("imageB64"))
            and int(value.get("start", 0)) < start_frame + duration_frames
            and int(value.get("start", 0)) + int(value.get("length", 1)) > start_frame
        ]
        segments.sort(key=lambda value: value.get("start", 0))
        for index, source in enumerate(segments):
            segment = dict(source)
            segment_start = int(segment.get("start", 0))
            offset = max(0, start_frame - segment_start)
            if segment.get("type") == "video":
                if offset:
                    segment["trimStart"] = float(segment.get("trimStart", 0)) + offset
                    segment["length"] = max(1, int(segment.get("length", 1)) - offset)
                tensor = await _video_segment(segment, float(frame_rate))
            else:
                tensor = await _image_segment(segment)
            source_h, source_w = tensor.shape[1:3]
            snap = lambda value: max(divisible_by, int(value) // divisible_by * divisible_by)
            if custom_width > 0 and custom_height > 0:
                tensor = _resize_image(tensor, custom_width, custom_height, resize_method, divisible_by)
            elif custom_width > 0:
                target_w = snap(custom_width)
                tensor = _resize_image(tensor, target_w, snap(source_h * target_w / source_w), "stretch to fit", divisible_by)
            elif custom_height > 0:
                target_h = snap(custom_height)
                tensor = _resize_image(tensor, snap(source_w * target_h / source_h), target_h, "stretch to fit", divisible_by)
            else:
                tensor = _resize_image(tensor, source_w, source_h, "maintain aspect ratio", divisible_by)
            tensor = _compress_image(tensor, int(img_compression))
            if index == 0:
                derived_h, derived_w = tensor.shape[1:3]
            insert = segment_start + int(segment.get("length", 1)) - 1 if segment.get("isEndFrame") else segment_start
            guide_data["images"].append(tensor)
            guide_data["insert_frames"].append(max(0, insert - start_frame))
            guide_data["strengths"].append(strengths[index] if index < len(strengths) else 1.0)

        if not guide_data["images"] and optional_latent is None:
            width, height = derived_w or 768, derived_h or 512
            video_name = ""
            retake_video = timeline.get("retakeVideo") or {}
            if timeline.get("retakeMode") and isinstance(retake_video, dict):
                video_name = str(retake_video.get("imageFile") or "")
            if not video_name:
                video_name = next(
                    (str(item.get("videoFile")) for item in timeline.get("motionSegments", []) if item.get("videoFile")),
                    "",
                )
            if video_name:
                try:
                    width, height = await _video_dimensions(video_name)
                except Exception:
                    pass
            dummy = _resize_image(torch.zeros((1, height, width, 3)), width, height, resize_method, divisible_by)
            guide_data["images"].append(dummy)
            guide_data["insert_frames"].append(0)
            guide_data["strengths"].append(0.0)
            derived_h, derived_w = dummy.shape[1:3]

        ltxv_length = math.ceil((duration_frames - 1) / 8) * 8 + 1
        if optional_latent is None:
            width, height = max(32, derived_w // 32 * 32), max(32, derived_h // 32 * 32)
            samples = torch.zeros((1, 128, (ltxv_length - 1) // 8 + 1, height // 32, width // 32))
            latent_ref = await sdk.LatentRef.from_value({"samples": samples})
        else:
            latent_ref = optional_latent

        prompts = [value.strip() for value in str(local_prompts).split("|")]
        if len(prompts) <= 1:
            local = prompts[0] if prompts and prompts[0] else ""
            active = f"{global_prompt.strip()}, {local}" if global_prompt.strip() and local else (local or global_prompt.strip())
            conditioning = await clip.encode(active)
            patched = model
        else:
            prompts = [value or (global_prompt.strip() or "video") for value in prompts]
            full_prompt, starts, ends = await _token_ranges(clip, global_prompt, prompts)
            lengths = [int(float(value.strip())) for value in str(segment_lengths).split(",") if value.strip()]
            if not lengths:
                latent_frames = (await latent_ref.value())["samples"].shape[2]
                lengths = [math.ceil(latent_frames / len(prompts)) * 8] * len(prompts)
            if len(lengths) != len(prompts):
                raise ValueError("segment_lengths must match the number of local prompts")
            conditioning = await clip.encode(full_prompt)
            patched = await model.patch(
                "prompt_relay", latent=latent_ref, token_starts=starts,
                token_ends=ends, pixel_lengths=lengths, epsilon=float(epsilon),
            )

        audio_value = await _combined_audio(timeline_data, int(start_frame), int(ltxv_length), float(frame_rate), bool(override_audio))
        audio_ref = await sdk.AudioRef.from_value(audio_value)
        if audio_vae is None:
            audio_latent_ref = await sdk.LatentRef.from_value({})
        elif use_custom_audio or override_audio or retake_active:
            audio_latent_ref = await audio_vae.encode_audio(audio_ref)
            audio_latent_value = await audio_latent_ref.value()
            latent_samples = audio_latent_value["samples"]
            batch, _, frames, height = latent_samples.shape
            if retake_active:
                gap_mask = torch.zeros((batch, frames, height), dtype=torch.float32, device=latent_samples.device)
                retake_start = float(timeline.get("retakeStart", 0))
                retake_length = float(timeline.get("retakeLength", 0))
                overlap_start = max(float(start_frame), retake_start)
                overlap_end = min(float(start_frame + ltxv_length), retake_start + retake_length)
                if overlap_end > overlap_start:
                    start_index = int((overlap_start - start_frame) / ltxv_length * frames)
                    end_index = int((overlap_end - start_frame) / ltxv_length * frames)
                    gap_mask[:, max(0, min(frames, start_index)):max(0, min(frames, end_index)), :] = 1.0
            else:
                gap_mask = torch.ones((batch, frames, height), dtype=torch.float32, device=latent_samples.device)
                segment_key = "motionSegments" if override_audio else "audioSegments"
                file_key = "videoFile" if override_audio else "audioFile"
                for segment in timeline.get(segment_key, []):
                    if not segment.get(file_key):
                        continue
                    segment_start = float(segment.get("start", 0))
                    segment_length = float(segment.get("length", 1))
                    if segment_start + segment_length <= start_frame or segment_start >= start_frame + ltxv_length:
                        continue
                    offset = max(0.0, start_frame - segment_start)
                    segment_length = max(1.0, segment_length - offset)
                    segment_start = max(0.0, segment_start - start_frame)
                    start_index = int(segment_start / ltxv_length * frames)
                    end_index = int((segment_start + segment_length) / ltxv_length * frames)
                    gap_mask[:, max(0, min(frames, start_index)):max(0, min(frames, end_index)), :] = 0.0
            if not inpaint_audio:
                gap_mask.zero_()
            audio_latent_value["noise_mask"] = gap_mask
            audio_latent_ref = await sdk.LatentRef.from_value(audio_latent_value)
        else:
            audio_latent_ref = await audio_vae.empty_audio_latent(ltxv_length, float(frame_rate))

        motion = {"segments": [], "frame_rate": float(frame_rate), "duration_frames": int(duration_frames), "resize_method": resize_method}
        if use_custom_motion:
            for source in timeline.get("motionSegments", []):
                segment_start, length = int(source.get("start", 0)), int(source.get("length", 1))
                if segment_start >= start_frame + duration_frames or segment_start + length <= start_frame or not source.get("videoFile"):
                    continue
                offset = max(0, start_frame - segment_start)
                new_start = max(0, segment_start - start_frame)
                clipped = min(length - offset, duration_frames - new_start)
                if clipped > 0:
                    clean = dict(source)
                    clean.update(start=new_start, length=clipped, trimStart=float(source.get("trimStart", 0)) + offset)
                    motion["segments"].append(clean)
        guide_data.update(timeline_data=timeline_data, start_frame=start_frame, duration_frames=duration_frames, resize_method=resize_method)
        return io.NodeOutput(
            patched, conditioning, latent_ref, audio_latent_ref,
            await sdk.ValueRef.from_value(guide_data),
            await sdk.ValueRef.from_value(motion), float(frame_rate), audio_ref,
        )


def _bislerp(samples, width, height):
    def slerp(first, second, ratio):
        channels = first.shape[-1]
        first_norm = torch.norm(first, dim=-1, keepdim=True)
        second_norm = torch.norm(second, dim=-1, keepdim=True)
        first_unit = first / first_norm
        second_unit = second / second_norm
        first_unit[first_norm.expand(-1, channels) == 0.0] = 0.0
        second_unit[second_norm.expand(-1, channels) == 0.0] = 0.0
        dot = (first_unit * second_unit).sum(1)
        omega = torch.acos(dot)
        sine = torch.sin(omega)
        result = (
            (torch.sin((1.0 - ratio.squeeze(1)) * omega) / sine).unsqueeze(1) * first_unit
            + (torch.sin(ratio.squeeze(1) * omega) / sine).unsqueeze(1) * second_unit
        )
        result *= (first_norm * (1.0 - ratio) + second_norm * ratio).expand(-1, channels)
        result[dot > 1 - 1e-5] = first[dot > 1 - 1e-5]
        result[dot < 1e-5 - 1] = (first * (1.0 - ratio) + second * ratio)[dot < 1e-5 - 1]
        return result

    def coordinates(old_length, new_length, device):
        first = torch.arange(old_length, dtype=torch.float32, device=device).reshape((1, 1, 1, -1))
        first = F.interpolate(first, size=(1, new_length), mode="bilinear")
        ratios = first - first.floor()
        first = first.to(torch.int64)
        second = torch.arange(old_length, dtype=torch.float32, device=device).reshape((1, 1, 1, -1)) + 1
        second[:, :, :, -1] -= 1
        second = F.interpolate(second, size=(1, new_length), mode="bilinear").to(torch.int64)
        return ratios, first, second

    original_dtype = samples.dtype
    samples = samples.float()
    batch, channels, old_height, old_width = samples.shape
    ratios, first, second = coordinates(old_width, width, samples.device)
    first = first.expand((batch, channels, old_height, -1))
    second = second.expand((batch, channels, old_height, -1))
    ratios = ratios.expand((batch, 1, old_height, -1))
    result = slerp(
        samples.gather(-1, first).movedim(1, -1).reshape((-1, channels)),
        samples.gather(-1, second).movedim(1, -1).reshape((-1, channels)),
        ratios.movedim(1, -1).reshape((-1, 1)),
    ).reshape(batch, old_height, width, channels).movedim(-1, 1)
    ratios, first, second = coordinates(old_height, height, samples.device)
    first = first.reshape((1, 1, -1, 1)).expand((batch, channels, -1, width))
    second = second.reshape((1, 1, -1, 1)).expand((batch, channels, -1, width))
    ratios = ratios.reshape((1, 1, -1, 1)).expand((batch, 1, -1, width))
    result = slerp(
        result.gather(-2, first).movedim(1, -1).reshape((-1, channels)),
        result.gather(-2, second).movedim(1, -1).reshape((-1, channels)),
        ratios.movedim(1, -1).reshape((-1, 1)),
    ).reshape(batch, height, width, channels).movedim(-1, 1)
    return result.to(original_dtype)


def _scale_5d_spatial(value, width, height, method):
    batch, channels, frames, old_h, old_w = value.shape
    source = value.permute(0, 2, 1, 3, 4).reshape(batch * frames, channels, old_h, old_w)
    if method == "bislerp":
        result = _bislerp(source, width, height)
        return result.reshape(batch, frames, channels, height, width).permute(0, 2, 1, 3, 4)
    mode = method
    kwargs = {"size": (height, width), "mode": mode}
    if mode in ("bilinear", "bicubic"):
        kwargs["align_corners"] = False
    result = F.interpolate(source, **kwargs)
    return result.reshape(batch, frames, channels, height, width).permute(0, 2, 1, 3, 4)


async def _encode_guide(vae, images, latent_width, latent_height, scale_factors, tiled=False, tile_size=256, tile_overlap=64, downscale=1.0, resize_method="crop"):
    time_scale, width_scale, height_scale = scale_factors
    keep = (images.shape[0] - 1) // time_scale * time_scale + 1
    images = images[:keep]
    target_w = max(8, int(latent_width * width_scale / downscale))
    target_h = max(8, int(latent_height * height_scale / downscale))
    if resize_method == "maintain aspect ratio":
        resize_method = "pad"
    pixels = _resize_image(images, target_w, target_h, resize_method, 1)[..., :3]
    ref = await sdk.ImageRef._from_raw(pixels)
    encoded = await (vae.encode_tiled(ref, tile_x=tile_size, tile_y=tile_size, overlap=tile_overlap) if tiled else vae.encode(ref))
    return pixels, (await encoded.value())["samples"]


class LTXDirectorGuide(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets", "raw")

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="LTXDirectorGuide",
            display_name="LTX Director Guide",
            category="WhatDreamsCost",
            inputs=[
                io.Conditioning.Input("positive"), io.Conditioning.Input("negative"),
                io.Vae.Input("vae"), io.Latent.Input("latent"), GuideData.Input("guide_data"),
                MotionGuideData.Input("motion_guide_data", optional=True),
                io.Model.Input("model", optional=True),
                io.Combo.Input("ic_lora_name", options=[], default="None", optional=True, remote=io.RemoteOptions(route="/models/loras", refresh_button=True)),
                io.Float.Input("ic_lora_strength", default=1.0, min=-100.0, max=100.0, step=0.01, optional=True),
                io.Float.Input("scale_by", default=1.0, min=0.01, max=8.0, step=0.01, optional=True),
                io.Combo.Input("upscale_method", options=["nearest-exact", "bilinear", "area", "bicubic", "bislerp"], default="bicubic", optional=True),
                io.Float.Input("image_attention_strength", default=1.0, min=0.0, max=1.0, step=0.01, optional=True),
                io.Combo.Input("crop", options=["disabled", "center"], default="center", optional=True),
                io.Boolean.Input("auto_snap_ic_grid", default=True, optional=True),
                io.Boolean.Input("use_tiled_encode", default=False, optional=True),
                io.Int.Input("tile_size", default=256, min=64, max=512, step=32, optional=True),
                io.Int.Input("tile_overlap", default=64, min=16, max=256, step=16, optional=True),
                io.Boolean.Input("retake_mode", default=False, optional=True),
            ],
            outputs=[
                io.Conditioning.Output("positive", display_name="positive"),
                io.Conditioning.Output("negative", display_name="negative"),
                io.Latent.Output("latent", display_name="latent"),
                io.Model.Output("model", display_name="model"),
                io.Float.Output("latent_downscale_factor", display_name="latent_downscale_factor"),
            ],
        )

    @classmethod
    async def execute(
        cls, positive, negative, vae, latent, guide_data,
        motion_guide_data=None, model=None, ic_lora_name="None",
        ic_lora_strength=1.0, scale_by=1.0, upscale_method="bicubic",
        image_attention_strength=1.0, crop="center", auto_snap_ic_grid=True,
        use_tiled_encode=False, tile_size=256, tile_overlap=64,
        retake_mode=False,
    ):
        positive_value, negative_value = await positive.value(), await negative.value()
        latent_value = await latent.value()
        guide = await _value(guide_data) or {}
        motion = await _value(motion_guide_data) if motion_guide_data is not None else {}
        motion = motion or {}
        active_resize = guide.get("resize_method") or motion.get("resize_method") or ("crop" if crop == "center" else "stretch to fit")

        downscale = 1.0
        patched_model = model
        lora_active = model is not None and ic_lora_name != "None"
        if lora_active:
            asset = await sdk.ctx().assets.resolve("loras", str(ic_lora_name))
            metadata = await sdk.ctx().assets.metadata(asset)
            try:
                downscale = float(metadata["reference_downscale_factor"])
            except Exception:
                downscale = 1.0
            patched_model, _ = await model.apply_lora(asset, None, float(ic_lora_strength), 0.0)

        scale_factors = await vae.downscale_index_formula()
        if scale_factors is None:
            raise ValueError("this VAE does not publish its downscale formula")
        latent_image = latent_value["samples"].clone()
        noise_mask = get_noise_mask(latent_value)
        initial_length = int(latent_image.shape[2])

        if scale_by != 1.0:
            target_w = max(1, round(latent_image.shape[-1] * scale_by))
            target_h = max(1, round(latent_image.shape[-2] * scale_by))
            latent_image = _scale_5d_spatial(latent_image, target_w, target_h, upscale_method)
            if noise_mask.shape[-2] > 1 or noise_mask.shape[-1] > 1:
                noise_mask = _scale_5d_spatial(noise_mask, target_w, target_h, upscale_method)
        if auto_snap_ic_grid and lora_active:
            factor = max(1, round(downscale))
            target_w = math.ceil(latent_image.shape[-1] / factor) * factor
            target_h = math.ceil(latent_image.shape[-2] / factor) * factor
            if (target_h, target_w) != latent_image.shape[-2:]:
                latent_image = _scale_5d_spatial(latent_image, target_w, target_h, upscale_method)
                if noise_mask.shape[-2] > 1 or noise_mask.shape[-1] > 1:
                    noise_mask = _scale_5d_spatial(noise_mask, target_w, target_h, upscale_method)

        _, _, latent_length, latent_height, latent_width = latent_image.shape
        try:
            timeline = json.loads(guide.get("timeline_data", "{}"))
        except Exception:
            timeline = {}
        is_retake = bool(retake_mode or timeline.get("retakeMode", False))
        is_empty = bool(latent_image.abs().max().item() < 1e-5)
        frame_rate = float(motion.get("frame_rate", guide.get("frame_rate", 24)))
        time_scale = scale_factors[0]

        if is_retake:
            retake_start = int(timeline.get("retakeStart", 0))
            retake_length = int(timeline.get("retakeLength", 0))
            strength = float(timeline.get("retakeStrength", 1.0))
            generation_start = int(guide.get("start_frame", 0))
            relative = max(0, retake_start - generation_start)
            latent_start = min(relative // time_scale, latent_length)
            latent_end = min(math.ceil((relative + retake_length) / time_scale), latent_length)
            need_base = is_empty or latent_start > 0 or latent_end < latent_length
            retake_video = timeline.get("retakeVideo") or {}
            video_name = retake_video.get("imageFile", "") if isinstance(retake_video, dict) else ""
            if need_base and not video_name:
                raise ValueError("Retake Mode needs a base video selected on the timeline")
            if need_base:
                frames = await _video_segment({"imageFile": video_name, "trimStart": generation_start, "length": (latent_length - 1) * time_scale + 1}, frame_rate)
                _, encoded = await _encode_guide(vae, frames, latent_width, latent_height, scale_factors, use_tiled_encode, tile_size, tile_overlap, 1.0, active_resize)
                paste = min(encoded.shape[2], latent_length)
                if is_empty:
                    latent_image[:, :, :paste] = encoded[:, :, :paste]
                else:
                    if latent_start:
                        latent_image[:, :, :latent_start] = encoded[:, :, :latent_start]
                    if latent_end < paste:
                        latent_image[:, :, latent_end:paste] = encoded[:, :, latent_end:paste]
            noise_mask = torch.zeros_like(noise_mask)
            if latent_end > latent_start:
                noise_mask[:, :, latent_start:latent_end] = strength
        else:
            images = guide.get("images", [])
            insert_frames = guide.get("insert_frames", [])
            strengths = guide.get("strengths", [])
            for index, image in enumerate(images):
                strength = float(strengths[index] if index < len(strengths) else 1.0)
                if strength <= 0:
                    continue
                frame_index = int(insert_frames[index] if index < len(insert_frames) else 0)
                pixels, encoded = await _encode_guide(vae, image, latent_width, latent_height, scale_factors)
                frame_index, latent_index = GuideOps.get_latent_index(positive_value, latent_length, len(pixels), frame_index, scale_factors)
                if latent_index >= latent_length:
                    continue
                encoded = encoded[:, :, :latent_length - latent_index]
                token_count = encoded.shape[2] * encoded.shape[3] * encoded.shape[4]
                latent_shape = list(encoded.shape[2:])
                positive_value, negative_value, latent_image, noise_mask = GuideOps.append_keyframe(positive_value, negative_value, frame_index, latent_image, noise_mask, encoded, strength, scale_factors)
                if lora_active:
                    positive_value, negative_value = append_guide_attention_entry(positive_value, negative_value, token_count, latent_shape, image_attention_strength)

            for segment in motion.get("segments", []):
                if not segment.get("videoFile") or int(segment.get("length", 1)) <= 0 or float(segment.get("videoStrength", 1.0)) <= 0:
                    continue
                frame_index = int(segment.get("start", 0))
                frames = await _video_segment(segment, frame_rate)
                causal_fix = frame_index == 0 or len(frames) == 1
                encode_frames = frames if causal_fix else torch.cat([frames[:1], frames])
                _, encoded = await _encode_guide(vae, encode_frames, latent_width, latent_height, scale_factors, use_tiled_encode, tile_size, tile_overlap, downscale, active_resize)
                if not causal_fix:
                    encoded = encoded[:, :, 1:]
                latent_index = (frame_index + time_scale - 1) // time_scale if frame_index > 0 else 0
                if frame_index > 0 and encoded.shape[2] > 1:
                    encoded = encoded[:, :, 1:]
                    frame_index += time_scale
                    latent_index += 1
                if latent_index >= latent_length:
                    continue
                encoded = encoded[:, :, :latent_length - latent_index]
                batch, _, count, height, width = encoded.shape
                guide_mask = torch.ones((batch, 1, count, height, width), dtype=encoded.dtype, device=encoded.device)
                if int(segment.get("start", 0)) > 0:
                    for ramp_index, ramp in enumerate((0.25, 0.65)):
                        if ramp_index < count:
                            guide_mask[:, :, ramp_index] = 1 + float(segment.get("videoStrength", 1.0)) * (1 - ramp)
                factor = max(1, round(downscale))
                if factor > 1:
                    dilated = torch.zeros((batch, encoded.shape[1], count, height * factor, width * factor), dtype=encoded.dtype, device=encoded.device)
                    dilated[..., ::factor, ::factor] = encoded
                    dilated_mask = torch.full((batch, 1, count, height * factor, width * factor), -1.0, dtype=encoded.dtype, device=encoded.device)
                    dilated_mask[..., ::factor, ::factor] = guide_mask
                    encoded, guide_mask = dilated, dilated_mask
                token_count = encoded.shape[2] * encoded.shape[3] * encoded.shape[4]
                original_shape = list(encoded.shape[2:])
                positive_value, negative_value, latent_image, noise_mask = GuideOps.append_keyframe(positive_value, negative_value, frame_index, latent_image, noise_mask, encoded, float(segment.get("videoStrength", 1.0)), scale_factors, guide_mask=guide_mask, latent_downscale_factor=downscale, causal_fix=causal_fix)
                if lora_active:
                    attention = float(segment.get("videoAttentionStrength", 0.65))
                    positive_value, negative_value = append_guide_attention_entry(positive_value, negative_value, token_count, original_shape, attention)

        crop_frames = max(0, int(latent_image.shape[2]) - initial_length)
        values = {"nghtdrp_guide_crop_latent_frames": crop_frames}
        positive_value = conditioning_set_values(positive_value, values)
        negative_value = conditioning_set_values(negative_value, values)
        return io.NodeOutput(
            await sdk.CondRef.from_value(positive_value),
            await sdk.CondRef.from_value(negative_value),
            await sdk.LatentRef.from_value({"samples": latent_image, "noise_mask": noise_mask}),
            patched_model, float(downscale),
        )


class LTXDirectorCropGuides(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="LTXDirectorCropGuides",
            display_name="LTX Director Crop Guides",
            category="WhatDreamsCost",
            inputs=[
                io.Conditioning.Input("positive"),
                io.Conditioning.Input("negative"),
                io.Latent.Input("latent"),
            ],
            outputs=[
                io.Conditioning.Output("positive", display_name="positive"),
                io.Conditioning.Output("negative", display_name="negative"),
                io.Latent.Output("latent", display_name="latent"),
            ],
        )

    @classmethod
    async def execute(cls, positive, negative, latent):
        positive_value = await positive.value()
        negative_value = await negative.value()
        latent_value = await latent.value()
        latent_image = latent_value["samples"].clone()
        noise_mask = get_noise_mask(latent_value)

        crop_value = conditioning_get_any_value(
            positive_value, "nghtdrp_guide_crop_latent_frames", None
        )
        if crop_value is None:
            indexes = conditioning_get_any_value(positive_value, "keyframe_idxs", None)
            crop_frames = 0 if indexes is None else int(torch.unique(indexes[:, 0, :, 0]).shape[0])
        else:
            try:
                crop_frames = max(0, int(crop_value))
            except Exception:
                crop_frames = 0

        crop_frames = min(crop_frames, max(0, latent_image.shape[2] - 1))
        if crop_frames:
            latent_image = latent_image[:, :, :-crop_frames]
            noise_mask = noise_mask[:, :, :-crop_frames]

        clear = {
            "keyframe_idxs": None,
            "guide_attention_entries": None,
            "nghtdrp_guide_crop_latent_frames": None,
        }
        positive_value = conditioning_set_values(positive_value, clear)
        negative_value = conditioning_set_values(negative_value, clear)
        return io.NodeOutput(
            await sdk.CondRef.from_value(positive_value),
            await sdk.CondRef.from_value(negative_value),
            await sdk.LatentRef.from_value({"samples": latent_image, "noise_mask": noise_mask}),
        )


NODE_CLASS_MAPPINGS = {
    "LTXDirector": LTXDirector,
    "LTXDirectorGuide": LTXDirectorGuide,
    "LTXDirectorCropGuides": LTXDirectorCropGuides,
}
