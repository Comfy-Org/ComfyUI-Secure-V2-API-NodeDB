"""ViTMatte alpha refinement, owned by this pack.

ViTMatte is one pack's model family rather than part of the node API, so the
architecture, the weights it needs and the refinement itself live here. The
only things asked of the host are generic: resolve a declared weight and read
its state dict.
"""
from __future__ import annotations

import asyncio
import math
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

import torch
import torch.nn.functional as functional
from comfy_api.latest import sdk


WEIGHTS = {
    "small": sdk.HuggingFaceWeight(
        repo_id="hustvl/vitmatte-small-composition-1k",
        filename="model.safetensors",
        folder="detection",
        revision="6a58ad7646403c1df626fbd746900aec7361ea1d",
        sha256="bda9289db1bb6762d978b42d1c62ae3f34daf7497171a347a1d09657efd788cb",
        on_demand=True,
    ),
    "base": sdk.HuggingFaceWeight(
        repo_id="hustvl/vitmatte-base-composition-1k",
        filename="pytorch_model.bin",
        folder="detection",
        revision="bf486d01a7d9e3dbcc8400f7942835caf0eaf76e",
        sha256="b2521bcc4b719fb24611c39605b6642162fd7502e69b3cc846506ca921757b41",
        on_demand=True,
    ),
}

# Backbone width and head count per released variant; the rest of the
# architecture is identical between them.
_VARIANTS = {"small": (384, 6), "base": (768, 12)}

# A refinement pass is bounded so a hostile or mistaken graph cannot ask for an
# unbounded allocation.
_MAX_PIXELS = 268_435_456
_MAX_BATCH = 64


@dataclass
class _Entry:
    model: Any
    variant: str
    lock: threading.Lock = field(default_factory=threading.Lock)


_CACHE: "OrderedDict[tuple[str, str], _Entry]" = OrderedDict()
_MAX_CACHED = 2


def _recipe(weight: str, variant: str) -> dict[str, str]:
    if variant not in _VARIANTS:
        raise ValueError("ViTMatte variant must be small or base")
    if not isinstance(weight, str) or not weight:
        raise ValueError("ViTMatte requires a managed model weight")
    return {"kind": "layerstyle.vitmatte", "weight": weight, "variant": variant}


def _validated_recipe(value: Any) -> dict[str, str]:
    if (
        not isinstance(value, dict)
        or set(value) != {"kind", "weight", "variant"}
        or value.get("kind") != "layerstyle.vitmatte"
    ):
        raise TypeError("detail refinement requires a LayerStyle ViTMatte model")
    return _recipe(value["weight"], value["variant"])


def _build_entry(state: dict[str, torch.Tensor], variant: str) -> _Entry:
    try:
        from transformers import (
            VitDetConfig,
            VitMatteConfig,
            VitMatteForImageMatting,
        )
    except ImportError as exc:
        raise RuntimeError("ViTMatte requires Transformers") from exc

    hidden_size, attention_heads = _VARIANTS[variant]
    backbone = VitDetConfig(
        hidden_size=hidden_size,
        num_attention_heads=attention_heads,
        image_size=512,
        num_channels=4,
        _out_features=["stage12"],
        _out_indices=[12],
        residual_block_indices=[2, 5, 8, 11],
        use_relative_position_embeddings=True,
        window_block_indices=[0, 1, 3, 4, 6, 7, 9, 10],
        window_size=14,
    )
    config = VitMatteConfig(
        backbone_config=backbone,
        hidden_size=hidden_size,
        convstream_hidden_sizes=[48, 96, 192],
        fusion_hidden_sizes=[256, 128, 64, 32],
    )
    model = VitMatteForImageMatting(config)
    model.load_state_dict(state, strict=True)
    model.eval().to("cpu")
    return _Entry(model=model, variant=variant)


async def _entry(ctx: Any, value: Any) -> tuple[_Entry, dict[str, str]]:
    recipe = _validated_recipe(value)
    key = (recipe["weight"], recipe["variant"])
    cached = _CACHE.pop(key, None)
    if cached is not None:
        _CACHE[key] = cached
        return cached, recipe

    asset = await ctx.assets.resolve("detection", recipe["weight"])
    state = await ctx.assets.load_state_dict(asset)
    if not isinstance(state, dict) or not state or any(
        not isinstance(name, str) or not isinstance(tensor, torch.Tensor)
        for name, tensor in state.items()
    ):
        raise ValueError("ViTMatte weights must contain only tensors")
    state = {name: tensor.detach().cpu() for name, tensor in state.items()}
    loaded = await asyncio.to_thread(_build_entry, state, recipe["variant"])
    while len(_CACHE) >= _MAX_CACHED:
        _stale_key, stale = _CACHE.popitem(last=False)
        stale.model.to("cpu")
    _CACHE[key] = loaded
    return loaded, recipe


async def load(ctx: Any, weight: str, variant: str) -> dict[str, str]:
    recipe = _recipe(weight, variant)
    await _entry(ctx, recipe)
    return recipe


def _checked_inputs(
    pixels: torch.Tensor, trimap: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    if (
        not isinstance(pixels, torch.Tensor)
        or pixels.ndim != 4
        or pixels.shape[-1] < 3
        or not 1 <= len(pixels) <= _MAX_BATCH
    ):
        raise ValueError("matting requires a non-empty BHWC RGB batch")
    if trimap.ndim == 4 and trimap.shape[1] == 1:
        trimap = trimap[:, 0]
    elif trimap.ndim == 4 and trimap.shape[-1] == 1:
        trimap = trimap[..., 0]
    if not isinstance(trimap, torch.Tensor) or trimap.ndim != 3:
        raise ValueError("matting trimaps must be a BHW mask batch")
    height, width = map(int, pixels.shape[1:3])
    if (
        tuple(trimap.shape[-2:]) != (height, width)
        or len(trimap) not in (1, len(pixels))
    ):
        raise ValueError("matting image and trimap dimensions must match")
    if (
        height <= 0
        or width <= 0
        or height * width * len(pixels) > _MAX_PIXELS
        or not bool(torch.isfinite(pixels[..., :3]).all())
        or not bool(torch.isfinite(trimap).all())
    ):
        raise ValueError("matting inputs are invalid or too large")
    if len(trimap) == 1 and len(pixels) > 1:
        trimap = trimap.expand(len(pixels), -1, -1)
    return pixels, trimap


async def refine(
    ctx: Any,
    value: Any,
    pixels: torch.Tensor,
    trimap: torch.Tensor,
    max_megapixels: float = 2.0,
) -> torch.Tensor:
    """Refine a trimap into an alpha mask, returned as a BHW CPU tensor."""
    max_megapixels = float(max_megapixels)
    if not math.isfinite(max_megapixels) or not 0.1 <= max_megapixels <= 1024.0:
        raise ValueError("matting max_megapixels must be in [0.1, 1024]")
    entry, _recipe_used = await _entry(ctx, value)
    pixels, trimap = _checked_inputs(pixels, trimap)

    height, width = map(int, pixels.shape[1:3])
    limit = max_megapixels * 1_048_576.0
    if height * width > limit:
        ratio = width / height
        target_width = max(1, int(math.sqrt(ratio * limit)))
        target_height = max(1, int(target_width / ratio))
    else:
        target_height, target_width = height, width

    device = (
        torch.device("cuda")
        if torch.cuda.is_available()
        else torch.device("cpu")
    )
    source = pixels[..., :3].movedim(-1, 1).to(
        device=device, dtype=torch.float32).clamp(0.0, 1.0)
    source_trimap = trimap.unsqueeze(1).to(
        device=device, dtype=torch.float32).clamp(0.0, 1.0)
    if (target_height, target_width) != (height, width):
        source = functional.interpolate(
            source, size=(target_height, target_width),
            mode="bilinear", align_corners=False)
        source_trimap = functional.interpolate(
            source_trimap, size=(target_height, target_width),
            mode="bilinear", align_corners=False)
    values = torch.cat((source * 2.0 - 1.0, source_trimap), dim=1)
    # The backbone needs both dimensions to be a multiple of 32.
    pad_height = (-target_height) % 32
    pad_width = (-target_width) % 32
    if pad_height or pad_width:
        values = functional.pad(values, (0, pad_width, 0, pad_height))

    with entry.lock:
        entry.model.to(device=device, dtype=torch.float32)
        try:
            alpha = entry.model(pixel_values=values).alphas
            if (
                not isinstance(alpha, torch.Tensor)
                or alpha.ndim != 4
                or alpha.shape[:2] != (len(pixels), 1)
            ):
                raise RuntimeError("ViTMatte returned an invalid alpha mask")
            alpha = alpha[:, 0, :target_height, :target_width]
            if (target_height, target_width) != (height, width):
                alpha = functional.interpolate(
                    alpha.unsqueeze(1), size=(height, width),
                    mode="bilinear", align_corners=False)[:, 0]
            result = alpha.detach().to(
                device="cpu", dtype=torch.float32).clamp(0.0, 1.0)
        finally:
            entry.model.to("cpu")
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return result
