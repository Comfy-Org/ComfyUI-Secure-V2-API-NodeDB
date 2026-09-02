"""Small pack-side helpers for the Secure Nodes V2 conversion."""
from __future__ import annotations

from typing import Any

import torch
from comfy_api.latest import sdk


async def materialize(value: Any) -> Any:
    """Resolve only buffer-safe values explicitly granted to this guest."""
    if isinstance(value, sdk.TensorRef):
        return await value.raw()
    if isinstance(value, sdk.ValueRef):
        return await value.value()
    if isinstance(value, list):
        return [await materialize(item) for item in value]
    if isinstance(value, tuple):
        return tuple([await materialize(item) for item in value])
    if isinstance(value, dict):
        return {key: await materialize(item) for key, item in value.items()}
    return value


async def image_value(value: Any) -> torch.Tensor | None:
    if value is None or isinstance(value, torch.Tensor):
        return value
    return await value.raw()


async def mask_value(value: Any) -> torch.Tensor | None:
    if value is None or isinstance(value, torch.Tensor):
        return value
    return await value.raw()


async def latent_value(value: Any) -> dict[str, Any] | None:
    if value is None or isinstance(value, dict):
        return value
    return await value.value()


async def output_image(value: torch.Tensor | None):
    return None if value is None else await sdk.ImageRef._from_raw(value)


async def output_mask(value: torch.Tensor | None):
    return None if value is None else await sdk.MaskRef._from_raw(value)


async def output_latent(value: dict[str, Any] | None):
    return None if value is None else await sdk.LatentRef.from_value(value)
