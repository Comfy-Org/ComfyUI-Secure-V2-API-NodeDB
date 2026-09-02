from __future__ import annotations

from typing import Any

import torch
import torch.nn.functional as F
from comfy_api.latest import sdk


_WAN21_MEAN = (
    -0.7571, -0.7089, -0.9113, 0.1075, -0.1745, 0.9653, -0.1517,
    1.5508, 0.4134, -0.0715, 0.5517, -0.3632, -0.1922, -0.9497,
    0.2503, -0.2921,
)
_WAN21_STD = (
    2.8184, 1.4541, 2.3275, 2.6558, 1.2196, 1.7708, 2.6052,
    2.0743, 3.2687, 2.1526, 2.8652, 1.5579, 1.6382, 1.1253,
    2.8251, 1.9160,
)


async def image_value(value: Any) -> torch.Tensor | None:
    if value is None:
        return None
    if isinstance(value, torch.Tensor):
        return value
    return await value.raw()


async def latent_value(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    return await value.value()


async def conditioning_value(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return await value.value()


async def encode_tensor(vae: Any, pixels: torch.Tensor) -> torch.Tensor:
    image = await sdk.ImageRef._from_raw(pixels)
    encoded = await vae.encode(image)
    value = await encoded.value()
    return value["samples"]


async def latent_layout(vae: Any) -> tuple[int, int, int | None]:
    layout = await vae.latent_layout()
    return (
        int(layout["channels"]),
        int(layout["spatial_compression"]),
        None if layout.get("temporal_compression") is None
        else int(layout["temporal_compression"]),
    )


async def output_conditioning(value: list[Any]):
    return await sdk.CondRef.from_value(value)


async def output_latent(samples: torch.Tensor):
    return await sdk.LatentRef.from_value({"samples": samples})


async def output_image(images: torch.Tensor):
    return await sdk.ImageRef._from_raw(images)


def common_upscale(
    samples: torch.Tensor,
    width: int,
    height: int,
    upscale_method: str,
    crop: str,
) -> torch.Tensor:
    old_width = samples.shape[-1]
    old_height = samples.shape[-2]
    source = samples
    if crop == "center":
        old_aspect = old_width / old_height
        new_aspect = width / height
        x = y = 0
        if old_aspect > new_aspect:
            x = round(
                (old_width - old_width * (new_aspect / old_aspect)) / 2
            )
        elif old_aspect < new_aspect:
            y = round(
                (old_height - old_height * (old_aspect / new_aspect)) / 2
            )
        source = samples.narrow(
            -2, y, old_height - y * 2
        ).narrow(-1, x, old_width - x * 2)
    return F.interpolate(source, size=(height, width), mode=upscale_method)


def conditioning_set_values(
    conditioning: list[Any], values: dict[str, Any], append: bool = False,
) -> list[Any]:
    result = []
    for entry in conditioning:
        updated = [entry[0], entry[1].copy()]
        for key, value in values.items():
            if append and key in updated[1]:
                value = updated[1][key] + value
            updated[1][key] = value
        result.append(updated)
    return result


def wan21_process_out(latent: torch.Tensor) -> torch.Tensor:
    mean = torch.tensor(_WAN21_MEAN).view(1, 16, 1, 1, 1).to(
        latent.device, latent.dtype
    )
    std = torch.tensor(_WAN21_STD).view(1, 16, 1, 1, 1).to(
        latent.device, latent.dtype
    )
    return latent * std + mean


async def merge_clip_vision_outputs(*outputs: Any):
    valid = [output for output in outputs if output is not None]
    if not valid:
        return None
    merged = valid[0]
    for output in valid[1:]:
        merged = await merged.concat(output)
    return merged


async def attach_clip_vision(conditioning: Any, output: Any):
    if output is None:
        return conditioning
    return await conditioning.with_clip_vision_output(output)


async def conditioning_outputs(
    positive_high: list[Any],
    positive_low: list[Any],
    negative: list[Any],
    latent: torch.Tensor,
    clip_vision_output: Any = None,
) -> tuple[Any, Any, Any, Any]:
    positive_high_ref = await output_conditioning(positive_high)
    positive_low_ref = await output_conditioning(positive_low)
    negative_ref = await output_conditioning(negative)
    positive_low_ref = await attach_clip_vision(
        positive_low_ref, clip_vision_output
    )
    negative_ref = await attach_clip_vision(
        negative_ref, clip_vision_output
    )
    return (
        positive_high_ref,
        positive_low_ref,
        negative_ref,
        await output_latent(latent),
    )
