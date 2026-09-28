"""Pack-owned LTX guide math; no ComfyUI host imports."""
from __future__ import annotations

import torch


def conditioning_set_values(conditioning, values):
    result = []
    for entry in conditioning:
        updated = [entry[0], entry[1].copy()]
        updated[1].update(values)
        result.append(updated)
    return result


def conditioning_get_any_value(conditioning, key, default=None):
    for entry in conditioning:
        if key in entry[1]:
            return entry[1][key]
    return default


def get_noise_mask(latent):
    mask = latent.get("noise_mask")
    if mask is not None:
        return mask.clone()
    samples = latent["samples"]
    return torch.ones(
        (samples.shape[0], 1, samples.shape[2], 1, 1),
        dtype=torch.float32,
        device=samples.device,
    )


def get_keyframe_idxs(conditioning, latent_shape=None):
    indexes = conditioning_get_any_value(conditioning, "keyframe_idxs")
    if indexes is None:
        return None, 0
    if latent_shape is not None and len(latent_shape) == 5:
        return indexes, indexes.shape[2] // (latent_shape[-2] * latent_shape[-1])
    entries = conditioning_get_any_value(conditioning, "guide_attention_entries")
    if entries:
        return indexes, sum(entry["latent_shape"][0] for entry in entries)
    return indexes, torch.unique(indexes[:, 0, :, 0]).shape[0]


def latent_to_pixel_coords(latent_coords, scale_factors, causal_fix=False):
    shape = [1] * latent_coords.ndim
    shape[1] = -1
    result = latent_coords * torch.tensor(scale_factors, device=latent_coords.device).view(*shape)
    if causal_fix:
        result[:, 0] = (result[:, 0] + 1 - scale_factors[0]).clamp(min=0)
    return result


def _latent_coords(latent):
    batch, _, frames, height, width = latent.shape
    grid = torch.meshgrid(
        torch.arange(frames, device=latent.device),
        torch.arange(height, device=latent.device),
        torch.arange(width, device=latent.device),
        indexing="ij",
    )
    start = torch.stack(grid, dim=0)
    end = start + torch.ones((3, 1, 1, 1), device=latent.device, dtype=start.dtype)
    start = start.unsqueeze(0).repeat(batch, 1, 1, 1, 1).reshape(batch, 3, -1)
    end = end.unsqueeze(0).repeat(batch, 1, 1, 1, 1).reshape(batch, 3, -1)
    return torch.stack((start, end), dim=-1)


class GuideOps:
    @classmethod
    def get_latent_index(cls, conditioning, latent_length, guide_length, frame_idx, scale_factors, latent_shape=None):
        stride = scale_factors[0]
        _, keyframe_count = get_keyframe_idxs(conditioning, latent_shape)
        source_length = latent_length - keyframe_count
        if frame_idx < 0:
            frame_idx = max((source_length - 1) * stride + 1 + frame_idx, 0)
        if guide_length > 1 and frame_idx != 0:
            frame_idx = (frame_idx - 1) // stride * stride + 1
        return frame_idx, (frame_idx + stride - 1) // stride

    @classmethod
    def add_keyframe_index(cls, conditioning, frame_idx, guide, scale_factors, latent_downscale_factor=1, causal_fix=None):
        indexes, _ = get_keyframe_idxs(conditioning)
        if causal_fix is None:
            causal_fix = frame_idx == 0 or guide.shape[2] == 1
        coords = latent_to_pixel_coords(_latent_coords(guide), scale_factors, causal_fix)
        coords[:, 0] += frame_idx
        offset = (latent_downscale_factor - 1) * torch.tensor(scale_factors[1:], device=coords.device).view(1, -1, 1, 1)
        coords[:, 1:, :, 1:] += offset.to(coords.dtype)
        if indexes is not None:
            coords = torch.cat([indexes, coords], dim=2)
        return conditioning_set_values(conditioning, {"keyframe_idxs": coords})

    @classmethod
    def append_keyframe(cls, positive, negative, frame_idx, latent_image, noise_mask, guide, strength, scale_factors, guide_mask=None, in_channels=128, latent_downscale_factor=1, causal_fix=None):
        if latent_image.shape[1] != in_channels or guide.shape[1] != in_channels:
            raise ValueError("Adding guide to a combined AV latent is not supported")
        positive = cls.add_keyframe_index(positive, frame_idx, guide, scale_factors, latent_downscale_factor, causal_fix)
        negative = cls.add_keyframe_index(negative, frame_idx, guide, scale_factors, latent_downscale_factor, causal_fix)
        if guide_mask is None:
            mask = torch.full(
                (noise_mask.shape[0], 1, guide.shape[2], noise_mask.shape[3], noise_mask.shape[4]),
                max(0.0, 1.0 - strength),
                dtype=noise_mask.dtype,
                device=noise_mask.device,
            )
        else:
            target_h = max(noise_mask.shape[3], guide_mask.shape[3])
            target_w = max(noise_mask.shape[4], guide_mask.shape[4])
            if noise_mask.shape[3] == 1 or noise_mask.shape[4] == 1:
                noise_mask = noise_mask.expand(-1, -1, -1, target_h, target_w)
            if guide_mask.shape[3] == 1 or guide_mask.shape[4] == 1:
                guide_mask = guide_mask.expand(-1, -1, -1, target_h, target_w)
            mask = guide_mask - strength
        if latent_image.shape[1] > guide.shape[1]:
            guide = torch.nn.functional.pad(guide, (0, 0, 0, 0, 0, 0, 0, latent_image.shape[1] - guide.shape[1]))
        return positive, negative, torch.cat([latent_image, guide], dim=2), torch.cat([noise_mask, mask], dim=2)


def append_guide_attention_entry(positive, negative, pre_filter_count, latent_shape, strength=1.0, attention_mask=None):
    entry = {
        "pre_filter_count": pre_filter_count,
        "strength": strength,
        "pixel_mask": attention_mask.unsqueeze(0).unsqueeze(0) if attention_mask is not None else None,
        "latent_shape": latent_shape,
    }
    results = []
    for conditioning in (positive, negative):
        existing = conditioning_get_any_value(conditioning, "guide_attention_entries", [])
        results.append(conditioning_set_values(conditioning, {"guide_attention_entries": [*existing, entry]}))
    return results[0], results[1]
