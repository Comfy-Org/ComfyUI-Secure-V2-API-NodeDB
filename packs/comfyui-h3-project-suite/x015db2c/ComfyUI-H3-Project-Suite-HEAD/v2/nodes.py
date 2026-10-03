"""Secure Nodes V2 implementation of the H3 continuation nodes.

The continuation policy and all tensor arithmetic remain pack-owned.  Core
objects stay behind typed refs; the only model-specific host operation is the
native, validated MiniMax H3 guide-conditioning vocabulary.
"""
from __future__ import annotations

import math

import torch
import torch.nn.functional as F

from comfy_api.latest import io, sdk


FPS = 24
AUDIO_HZ = 40.0
FRAME_RESCALE = 5.0 / 3.0
FRAME_PER_TOKEN = (1, 4, 4, 4, 4)
VIDEO_RUN_GRID = (124, 107, 90, 73, 56, 39, 22, 5, 1)
CONTEXT_LENGTHS = [1, 5, 22, 39, 56]
MAX_AUDIO_STRETCH = 0.005


class NestedTensor:
    """Portable guest representation reconstructed as core NestedTensor."""

    is_nested = True

    def __init__(self, tensors):
        self.tensors = list(tensors)

    @property
    def shape(self):
        return self.tensors[0].shape

    @property
    def dtype(self):
        return self.tensors[0].dtype

    def unbind(self):
        return self.tensors


def _pixel_frames(latent_t: int) -> int:
    return sum(FRAME_PER_TOKEN[k % 5] for k in range(int(latent_t)))


def _step_offsets(latent_t: int) -> list[int]:
    result, offset = [], 0
    for index in range(int(latent_t)):
        result.append(offset)
        offset += FRAME_PER_TOKEN[index % 5]
    return result


def _streams(value: dict) -> list[torch.Tensor]:
    if not isinstance(value, dict) or "samples" not in value:
        raise ValueError("h3_suite: expected a LATENT with samples")
    samples = value["samples"]
    if getattr(samples, "is_nested", False) and hasattr(samples, "unbind"):
        parts = list(samples.unbind())
    elif isinstance(samples, (tuple, list)):
        parts = list(samples)
    else:
        parts = [samples]
    if not parts or any(not isinstance(part, torch.Tensor) for part in parts):
        raise ValueError("h3_suite: latent contains invalid streams")
    return parts


def _video(parts: list[torch.Tensor]) -> torch.Tensor:
    value = parts[0]
    if value.ndim == 4:
        value = value.unsqueeze(0)
    if value.ndim != 5:
        raise ValueError("h3_suite: expected video latent [B,C,T,H,W]")
    return value


def _audio(parts: list[torch.Tensor]) -> torch.Tensor:
    if len(parts) < 2:
        raise ValueError("h3_suite: the H3 latent has no audio stream")
    value = parts[1]
    if value.ndim == 3:
        value = value.unsqueeze(0)
    if value.ndim != 4:
        raise ValueError("h3_suite: expected audio latent [B,C,2,T]")
    return value


async def _latent(samples: torch.Tensor, **fields) -> sdk.LatentRef:
    return await sdk.LatentRef.from_value({"samples": samples, **fields})


async def _audio_ref(waveform: torch.Tensor, sample_rate: int) -> sdk.AudioRef:
    return await sdk.AudioRef.from_value({
        "waveform": waveform,
        "sample_rate": int(sample_rate),
    })


def _resample(waveform: torch.Tensor, old_rate: int, new_rate: int) -> torch.Tensor:
    if old_rate == new_rate:
        return waveform
    length = max(1, int(round(waveform.shape[-1] * new_rate / old_rate)))
    original_shape = waveform.shape
    flat = waveform.reshape(-1, 1, original_shape[-1])
    result = F.interpolate(flat, size=length, mode="linear", align_corners=False)
    return result.reshape(original_shape[:-1] + (length,))


class H3Context(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="H3Context",
            display_name="H3 Context",
            category="conditioning/minimax",
            description="Pin the previous H3 clip's tail as native video/audio guides.",
            inputs=[
                io.Conditioning.Input("conditioning"),
                io.Latent.Input("latent"),
                io.Combo.Input("context_length", options=CONTEXT_LENGTHS, default=22),
                io.Combo.Input("encode_mode", options=["video", "frames"], default="video"),
                io.Combo.Input("anchor_mode", options=["head", "before"], default="head"),
                io.Combo.Input("crop", options=["disabled", "center"], default="disabled"),
                io.Int.Input("audio_context_length", default=22, min=0, max=240),
                io.Combo.Input("audio_mode", options=["timeline", "ref"], default="timeline"),
                io.Combo.Input("video_source", options=["latent", "frames"], default="latent"),
                io.Boolean.Input("seed_head", default=True),
                io.Float.Input("head_hold", default=1.0, min=0.0, max=1.0, step=0.05),
                io.Boolean.Input("hold_framing", default=False),
                io.Vae.Input("vae", optional=True),
                io.Boolean.Input("enabled", optional=True, force_input=True),
                io.Image.Input("context_frames", optional=True),
                io.Latent.Input("context_latent", optional=True),
                io.Vae.Input("audio_vae", optional=True),
                io.Audio.Input("context_audio", optional=True),
                io.Latent.Input("anchor_latent", optional=True),
            ],
            outputs=[
                io.Conditioning.Output("conditioning"),
                io.Int.Output("trim_frames"),
                io.Latent.Output("latent"),
            ],
        )

    @classmethod
    async def execute(
        cls, conditioning, latent, context_length, encode_mode, anchor_mode,
        crop, audio_context_length=22, audio_mode="timeline",
        video_source="latent", seed_head=True, head_hold=1.0,
        hold_framing=False, vae=None, enabled=True, context_frames=None,
        context_latent=None, audio_vae=None, context_audio=None,
        anchor_latent=None,
    ):
        target_value = await latent.value()
        target_parts = _streams(target_value)
        target_video = _video(target_parts)
        frame_count = _pixel_frames(target_video.shape[2])

        audio_references = []
        if anchor_latent is not None:
            anchor_audio = _audio(_streams(await anchor_latent.value()))
            if anchor_audio.shape[-1] > 8:
                audio_references.append(await _latent(
                    anchor_audio[..., :min(anchor_audio.shape[-1], 400)].contiguous()))

        if enabled is False:
            if audio_references:
                conditioning = await conditioning.with_minimax_h3_guides(
                    frame_count=frame_count,
                    audio_references=audio_references)
            return io.NodeOutput(conditioning, 0, latent)

        pin_context = None
        pin_start = 0
        if video_source == "latent":
            if context_latent is None:
                raise ValueError("h3_suite: latent video source needs context_latent")
            context_parts = _streams(await context_latent.value())
            pin_context = _video(context_parts)
            if pin_context.shape[3:] != target_video.shape[3:]:
                raise ValueError("h3_suite: context and target latent sizes differ")
            total = int(pin_context.shape[2])
            runs = []
            start = (total // 5) * 5
            if start == total:
                start -= 5
            while start >= 0:
                covered = _pixel_frames(total - start)
                runs.append((covered, start))
                if covered > max(int(context_length), 39):
                    break
                start -= 5
            usable = [(count, start) for count, start in runs
                      if 0 < count <= int(context_length)]
            if not usable:
                raise ValueError("h3_suite: no phase-aligned latent tail fits")
            span, pin_start = max(usable)
            blocks = [pin_context[:, :, k:k + 1].contiguous()
                      for k in range(pin_start, total)]
            offsets = _step_offsets(len(blocks))
            used_frames = span
        else:
            if vae is None or context_frames is None:
                raise ValueError("h3_suite: frame source needs vae and context_frames")
            available = await context_frames.batch_size()
            used_frames = min(int(context_length), available)
            if encode_mode == "video":
                used_frames = next(item for item in VIDEO_RUN_GRID
                                   if item <= used_frames)
            if used_frames >= frame_count:
                raise ValueError("h3_suite: pinned run must be shorter than target")
            selected = await context_frames.select_batch(
                list(range(available - used_frames, available)))
            selected = await selected.resize(
                int(target_video.shape[4]) * 16,
                int(target_video.shape[3]) * 16,
                "lanczos", crop)
            if encode_mode == "video":
                encoded = await vae.encode(selected)
                encoded_video = _video(_streams(await encoded.value()))
                blocks = [encoded_video[:, :, k:k + 1].contiguous()
                          for k in range(encoded_video.shape[2])]
                offsets = _step_offsets(len(blocks))
                span = _pixel_frames(len(blocks))
                if span != used_frames:
                    raise RuntimeError("h3_suite: the VAE temporal grid changed")
            else:
                blocks, offsets = [], []
                for index in range(used_frames):
                    frame = await selected.select_batch([index])
                    encoded = await vae.encode(frame)
                    blocks.append(_video(_streams(await encoded.value())))
                    offsets.append(index)
                span = used_frames

        indices = [offset - span if anchor_mode == "before" else offset
                   for offset in offsets]
        video_guides = [
            (float(position), await _latent(block))
            for position, block in zip(indices, blocks)
        ]
        if hold_framing:
            video_guides.append((
                float(span if anchor_mode == "head" else 0),
                await _latent(blocks[-1]),
            ))

        audio_guides = []
        if context_latent is not None or context_audio is not None:
            audio_frames = int(audio_context_length) or span
            if context_latent is not None:
                context_parts = _streams(await context_latent.value())
                context_video = _video(context_parts)
                context_audio_latent = _audio(context_parts)
                total_steps = int(context_audio_latent.shape[-1])
                prior_frames = _pixel_frames(context_video.shape[2])
                overhang = total_steps - FRAME_RESCALE * prior_frames
                if not -0.5 < overhang < 0.5:
                    overhang = 0.0
                steps = min(total_steps, max(1, round(audio_frames / FPS * AUDIO_HZ)))
                audio_tensor = context_audio_latent[..., -steps:].contiguous()
                audio_latent = await _latent(audio_tensor)
            else:
                if audio_vae is None:
                    raise ValueError("h3_suite: context_audio needs audio_vae")
                audio_value = await context_audio.value()
                waveform = audio_value["waveform"]
                rate = int(audio_value["sample_rate"])
                vae_rate = await audio_vae.audio_sample_rate() or 32000
                waveform = _resample(waveform, rate, vae_rate)
                rate = vae_rate
                want = min(waveform.shape[-1], round(audio_frames / FPS * rate))
                tail = waveform[..., -want:].contiguous()
                audio_latent = await audio_vae.encode_audio(
                    await _audio_ref(tail, rate))
                steps = int(_streams(await audio_latent.value())[0].shape[-1])
                overhang = 0.0
            if audio_mode == "timeline":
                end = float(span if anchor_mode == "head" else 0)
                end += overhang / FRAME_RESCALE
                start = end - steps * (FPS / AUDIO_HZ)
                audio_guides.append((start, audio_latent))
            else:
                audio_references.append(audio_latent)

        conditioned = await conditioning.with_minimax_h3_guides(
            frame_count=frame_count,
            video_guides=video_guides,
            audio_guides=audio_guides,
            audio_references=audio_references,
        )

        output_latent = latent
        if seed_head and video_source == "latent":
            target = target_video.clone()
            steps = len(blocks)
            target[:, :, :steps] = pin_context[:, :, pin_start:pin_start + steps]
            target_parts[0] = target
            mask = torch.ones((target.shape[0], 1, target.shape[2],
                               target.shape[3], target.shape[4]))
            mask[:, :, :steps] = 1.0 - float(head_hold)
            output_latent = await sdk.LatentRef.from_value({
                **target_value,
                "samples": NestedTensor(target_parts),
                "noise_mask": mask,
            })
        trim = span if anchor_mode == "head" else 0
        return io.NodeOutput(conditioned, trim, output_latent)


def _cfr_indices(count: int, source_fps: float) -> list[int]:
    if source_fps <= 0 or count <= 0:
        raise ValueError("h3_suite: source footage and fps must be non-empty")
    if abs(source_fps - FPS) < 1e-6:
        return list(range(count))
    output_count = max(1, round(count * FPS / source_fps))
    return [min(max(round((index + 0.5) / FPS * source_fps - 0.5), 0), count - 1)
            for index in range(output_count)]


class H3ImportSource(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="H3ImportSource", display_name="H3 Import Source",
            category="MiniMax H3",
            description="Conform external footage to H3's 24 fps and 17k+5 grid.",
            inputs=[
                io.Image.Input("images"),
                io.Float.Input("source_fps", default=24.0, min=1.0, max=240.0, step=0.001),
                io.Int.Input("width", default=928, min=16, max=4096, step=16),
                io.Int.Input("height", default=928, min=16, max=4096, step=16),
                io.Combo.Input("crop", options=["disabled", "center"], default="center"),
                io.Combo.Input("keep", options=["tail", "head", "center"], default="tail"),
                io.Vae.Input("vae"),
                io.Audio.Input("audio", optional=True),
                io.Vae.Input("audio_vae", optional=True),
            ],
            outputs=[io.Latent.Output("latent"), io.Image.Output("images"),
                     io.Audio.Output("audio"), io.String.Output("report")],
        )

    @classmethod
    async def execute(cls, images, source_fps, width, height, crop, keep, vae,
                      audio=None, audio_vae=None):
        count = await images.batch_size()
        mapped = _cfr_indices(count, float(source_fps))
        keep_count = 5 + ((len(mapped) - 5) // 17) * 17 if len(mapped) >= 5 else 0
        if keep_count < 5:
            raise ValueError("h3_suite: source is too short for H3")
        dropped = len(mapped) - keep_count
        start = 0 if keep == "head" else dropped // 2 if keep == "center" else dropped
        picked = mapped[start:start + keep_count]
        frames = await images.select_batch(picked)
        frames = await frames.resize(int(width), int(height), "lanczos", crop)
        video_latent = await vae.encode(await frames.rgb())
        parts = _streams(await video_latent.value())

        audio_out = None
        note = ""
        if audio is not None:
            if audio_vae is None:
                raise ValueError("h3_suite: audio input needs audio_vae")
            value = await audio.value()
            waveform = value["waveform"]
            rate = int(value["sample_rate"])
            vae_rate = await audio_vae.audio_sample_rate() or 32000
            waveform = _resample(waveform, rate, vae_rate)
            rate = vae_rate
            want = round(keep_count / FPS * rate)
            if waveform.shape[-1] < want and (want - waveform.shape[-1]) / want > MAX_AUDIO_STRETCH:
                raise ValueError("h3_suite: source audio is too short for the video")
            if waveform.shape[-1] > want:
                waveform = waveform[..., -want:]
                note = " Audio tail was trimmed to match."
            elif waveform.shape[-1] < want:
                waveform = F.pad(waveform, (0, want - waveform.shape[-1]))
                note = " Audio was zero-padded to match."
            audio_out = await _audio_ref(waveform, rate)
            encoded_audio = await audio_vae.encode_audio(audio_out)
            parts.append(_streams(await encoded_audio.value())[0])

        latent = await sdk.LatentRef.from_value({
            "samples": NestedTensor(parts) if len(parts) > 1 else parts[0],
        })
        report = (f"{count} frames at {source_fps:g} fps -> {len(mapped)} at 24 fps. "
                  f"Kept {keep_count} frames ({keep_count / FPS:.2f}s); "
                  f"dropped {dropped}.{note}")
        return io.NodeOutput(latent, frames, audio_out, report)


class H3ContextTrim(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="H3ContextTrim", display_name="H3 Context Trim",
            category="conditioning/minimax",
            description="Trim pinned head frames and keep audio sample-locked.",
            inputs=[io.Image.Input("images"),
                    io.Int.Input("trim_frames", default=0, min=0, max=4096),
                    io.Audio.Input("audio", optional=True),
                    io.Float.Input("fps", default=24.0, min=1.0, max=240.0, step=0.001, optional=True),
                    io.Boolean.Input("match_tail", default=True, optional=True)],
            outputs=[io.Image.Output("images"), io.Audio.Output("audio")],
        )

    @classmethod
    async def execute(cls, images, trim_frames, audio=None, fps=24.0, match_tail=True):
        total = await images.batch_size()
        count = max(0, int(trim_frames))
        if count >= total:
            raise ValueError("h3_suite: trim would remove every frame")
        output_images = images if count == 0 else await images.select_batch(
            list(range(count, total)))
        output_audio = audio
        if audio is not None:
            value = await audio.value()
            waveform = value["waveform"]
            rate = int(value["sample_rate"])
            cut = round(count / float(fps) * rate)
            if cut >= waveform.shape[-1]:
                raise ValueError("h3_suite: trim would remove all audio")
            waveform = waveform[..., cut:]
            if match_tail:
                wanted = round((total - count) / float(fps) * rate)
                waveform = (waveform[..., :wanted] if waveform.shape[-1] >= wanted
                            else F.pad(waveform, (0, wanted - waveform.shape[-1])))
            output_audio = await _audio_ref(waveform, rate)
        return io.NodeOutput(output_images, output_audio)


class H3ContextSaveLatent(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw", "output", "storage")

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="H3ContextSaveLatent", display_name="H3 Context Save Latent",
            category="conditioning/minimax", is_output_node=True,
            inputs=[io.Latent.Input("latent"),
                    io.String.Input("filename_prefix", default="h3_context/clip"),
                    io.Int.Input("clip_index", default=0, min=0, max=9999)],
            outputs=[io.String.Output("latent_path")],
        )

    @classmethod
    async def execute(cls, latent, filename_prefix, clip_index=0):
        parts = _streams(await latent.value())
        video, audio = _video(parts), _audio(parts)
        state = await sdk.ValueRef.from_value({"video": video, "audio": audio})
        prefix = str(filename_prefix).replace("\\", "/").strip("/")
        if not prefix or ".." in prefix.split("/"):
            raise ValueError("h3_suite: unsafe latent prefix")
        saved = await sdk.ctx().output.save_state_dict(
            state, prefix, metadata={"format": "h3_motion_context_av_v2"})
        key = f"h3-context:{prefix}:{int(clip_index)}"
        await sdk.ctx().storage.set(key, saved)
        return io.NodeOutput(saved)


class H3ContextLoadLatent(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw", "assets", "storage")

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="H3ContextLoadLatent", display_name="H3 Context Load Latent",
            category="conditioning/minimax", not_idempotent=True,
            inputs=[io.String.Input("latent_path", default="h3_context"),
                    io.Int.Input("clip_index", default=0, min=0, max=9999)],
            outputs=[io.Latent.Output("latent")],
        )

    @classmethod
    async def execute(cls, latent_path, clip_index=0):
        prefix = str(latent_path).replace("\\", "/").strip("/")
        if not prefix or ".." in prefix.split("/"):
            raise ValueError("h3_suite: unsafe latent name")
        stored = await sdk.ctx().storage.get(
            f"h3-context:{prefix}:{int(clip_index)}")
        logical_name = stored or prefix
        asset = await sdk.ctx().assets.resolve("output", logical_name)
        data = await sdk.ctx().assets.load_state_dict(asset)
        if not isinstance(data, dict) or "video" not in data or "audio" not in data:
            raise ValueError("h3_suite: saved state is not an H3 AV latent")
        return io.NodeOutput(await sdk.LatentRef.from_value({
            "samples": NestedTensor([data["video"], data["audio"]]),
        }))


NODE_CLASS_MAPPINGS = {
    "H3Context": H3Context,
    "H3ImportSource": H3ImportSource,
    "H3ContextTrim": H3ContextTrim,
    "H3ContextSaveLatent": H3ContextSaveLatent,
    "H3ContextLoadLatent": H3ContextLoadLatent,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3Context": "H3 Context",
    "H3ImportSource": "H3 Import Source",
    "H3ContextTrim": "H3 Context Trim",
    "H3ContextSaveLatent": "H3 Context Save Latent",
    "H3ContextLoadLatent": "H3 Context Load Latent",
}
