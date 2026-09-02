from __future__ import annotations

import torch
from einops import rearrange

from ._tensor_utils import conditioning_set_values


def latent_to_pixel_coords(latent_coords, scale_factors, causal_fix=False):
    shape = [1] * latent_coords.ndim
    shape[1] = -1
    pixel_coords = latent_coords * torch.tensor(
        scale_factors, device=latent_coords.device
    ).view(*shape)
    if causal_fix:
        pixel_coords[:, 0, ...] = (
            pixel_coords[:, 0, ...] + 1 - scale_factors[0]
        ).clamp(min=0)
    return pixel_coords


class SymmetricPatchifier:
    def __init__(self, patch_size, start_end=False):
        self._patch_size = (1, patch_size, patch_size)
        self.start_end = start_end

    @property
    def patch_size(self):
        return self._patch_size

    def get_latent_coords(
        self, latent_num_frames, latent_height, latent_width, batch_size, device
    ):
        sample_coords = torch.meshgrid(
            torch.arange(
                0, latent_num_frames, self._patch_size[0], device=device
            ),
            torch.arange(0, latent_height, self._patch_size[1], device=device),
            torch.arange(0, latent_width, self._patch_size[2], device=device),
            indexing="ij",
        )
        start = torch.stack(sample_coords, dim=0)
        delta = torch.tensor(
            self._patch_size, device=start.device, dtype=start.dtype
        )[:, None, None, None]
        end = start + delta
        start = start.unsqueeze(0).repeat(batch_size, 1, 1, 1, 1)
        start = rearrange(start, "b c f h w -> b c (f h w)", b=batch_size)
        if not self.start_end:
            return start
        end = end.unsqueeze(0).repeat(batch_size, 1, 1, 1, 1)
        end = rearrange(end, "b c f h w -> b c (f h w)", b=batch_size)
        return torch.stack((start, end), dim=-1)

    def patchify(self, latents):
        batch, _, frames, height, width = latents.shape
        latent_coords = self.get_latent_coords(
            frames, height, width, batch, latents.device
        )
        latents = rearrange(
            latents,
            "b c (f p1) (h p2) (w p3) -> b (f h w) (c p1 p2 p3)",
            p1=self._patch_size[0],
            p2=self._patch_size[1],
            p3=self._patch_size[2],
        )
        return latents, latent_coords


def append_guide_attention_entry(
    positive,
    negative,
    pre_filter_count,
    latent_shape,
    strength=1.0,
    attention_mask=None,
):
    new_entry = {
        "pre_filter_count": pre_filter_count,
        "strength": strength,
        "pixel_mask": (
            attention_mask.unsqueeze(0).unsqueeze(0)
            if attention_mask is not None
            else None
        ),
        "latent_shape": latent_shape,
    }
    results = []
    for conditioning in (positive, negative):
        existing = []
        for entry in conditioning:
            found = entry[1].get("guide_attention_entries")
            if found is not None:
                existing = found
                break
        results.append(conditioning_set_values(
            conditioning,
            {"guide_attention_entries": [*existing, new_entry]},
        ))
    return results[0], results[1]


def conditioning_get_any_value(conditioning, key, default=None):
    for entry in conditioning:
        if key in entry[1]:
            return entry[1][key]
    return default


def get_noise_mask(latent):
    noise_mask = latent.get("noise_mask")
    latent_image = latent["samples"]
    if noise_mask is None:
        batch_size, _, latent_length, _, _ = latent_image.shape
        return torch.ones(
            (batch_size, 1, latent_length, 1, 1),
            dtype=torch.float32,
            device=latent_image.device,
        )
    return noise_mask.clone()


def get_keyframe_idxs(conditioning, latent_shape=None):
    keyframe_idxs = conditioning_get_any_value(
        conditioning, "keyframe_idxs"
    )
    if keyframe_idxs is None:
        return None, 0
    if latent_shape is not None and len(latent_shape) == 5:
        tokens_per_frame = latent_shape[-2] * latent_shape[-1]
        return keyframe_idxs, keyframe_idxs.shape[2] // tokens_per_frame
    entries = conditioning_get_any_value(
        conditioning, "guide_attention_entries"
    )
    if entries:
        return keyframe_idxs, sum(
            entry["latent_shape"][0] for entry in entries
        )
    return keyframe_idxs, torch.unique(keyframe_idxs[:, 0, :, 0]).shape[0]


class GuideOps:
    PATCHIFIER = SymmetricPatchifier(1, start_end=True)

    @classmethod
    def get_latent_index(
        cls,
        conditioning,
        latent_length,
        guide_length,
        frame_idx,
        scale_factors,
        latent_shape=None,
    ):
        time_scale_factor, _, _ = scale_factors
        _, num_keyframes = get_keyframe_idxs(conditioning, latent_shape)
        latent_count = latent_length - num_keyframes
        if frame_idx < 0:
            frame_idx = max(
                (latent_count - 1) * time_scale_factor + 1 + frame_idx, 0
            )
        if guide_length > 1 and frame_idx != 0:
            frame_idx = (
                (frame_idx - 1) // time_scale_factor * time_scale_factor + 1
            )
        latent_idx = (
            frame_idx + time_scale_factor - 1
        ) // time_scale_factor
        return frame_idx, latent_idx

    @classmethod
    def add_keyframe_index(
        cls,
        conditioning,
        frame_idx,
        guiding_latent,
        scale_factors,
        latent_downscale_factor=1,
        causal_fix=None,
    ):
        keyframe_idxs, _ = get_keyframe_idxs(conditioning)
        _, latent_coords = cls.PATCHIFIER.patchify(guiding_latent)
        if causal_fix is None:
            causal_fix = frame_idx == 0 or guiding_latent.shape[2] == 1
        pixel_coords = latent_to_pixel_coords(
            latent_coords, scale_factors, causal_fix=causal_fix
        )
        pixel_coords[:, 0] += frame_idx
        spatial_end_offset = (
            (latent_downscale_factor - 1)
            * torch.tensor(scale_factors[1:], device=pixel_coords.device)
            .view(1, -1, 1, 1)
        )
        pixel_coords[:, 1:, :, 1:] += spatial_end_offset.to(
            pixel_coords.dtype
        )
        if keyframe_idxs is None:
            keyframe_idxs = pixel_coords
        else:
            keyframe_idxs = torch.cat(
                [keyframe_idxs, pixel_coords], dim=2
            )
        return conditioning_set_values(
            conditioning, {"keyframe_idxs": keyframe_idxs}
        )

    @classmethod
    def append_keyframe(
        cls,
        positive,
        negative,
        frame_idx,
        latent_image,
        noise_mask,
        guiding_latent,
        strength,
        scale_factors,
        guide_mask=None,
        in_channels=128,
        latent_downscale_factor=1,
        causal_fix=None,
    ):
        if (latent_image.shape[1] != in_channels
                or guiding_latent.shape[1] != in_channels):
            raise ValueError(
                "Adding guide to a combined AV latent is not supported."
            )
        positive = cls.add_keyframe_index(
            positive,
            frame_idx,
            guiding_latent,
            scale_factors,
            latent_downscale_factor,
            causal_fix=causal_fix,
        )
        negative = cls.add_keyframe_index(
            negative,
            frame_idx,
            guiding_latent,
            scale_factors,
            latent_downscale_factor,
            causal_fix=causal_fix,
        )
        if guide_mask is not None:
            target_height = max(noise_mask.shape[3], guide_mask.shape[3])
            target_width = max(noise_mask.shape[4], guide_mask.shape[4])
            if noise_mask.shape[3] == 1 or noise_mask.shape[4] == 1:
                noise_mask = noise_mask.expand(
                    -1, -1, -1, target_height, target_width
                )
            if guide_mask.shape[3] == 1 or guide_mask.shape[4] == 1:
                guide_mask = guide_mask.expand(
                    -1, -1, -1, target_height, target_width
                )
            mask = guide_mask - strength
        else:
            mask = torch.full(
                (
                    noise_mask.shape[0],
                    1,
                    guiding_latent.shape[2],
                    noise_mask.shape[3],
                    noise_mask.shape[4],
                ),
                max(0.0, 1.0 - strength),
                dtype=noise_mask.dtype,
                device=noise_mask.device,
            )
        if latent_image.shape[1] > guiding_latent.shape[1]:
            pad_length = latent_image.shape[1] - guiding_latent.shape[1]
            guiding_latent = torch.nn.functional.pad(
                guiding_latent,
                pad=(0, 0, 0, 0, 0, 0, 0, pad_length),
                value=0,
            )
        return (
            positive,
            negative,
            torch.cat([latent_image, guiding_latent], dim=2),
            torch.cat([noise_mask, mask], dim=2),
        )
