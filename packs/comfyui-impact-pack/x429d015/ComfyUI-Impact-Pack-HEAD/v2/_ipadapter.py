"""Typed accessors for the host's IP-Adapter operations.

The pipeline patches a live diffusion model, so it stays host-owned and the
operations stay in core. What lives here is the typed façade over them: the
ergonomics belong to the pack that wants them rather than to the API every
pack inherits, so core can gain operations without gaining surface.

Anything not wrapped here is still reachable as ``ref.op(name, **params)``.
"""
from __future__ import annotations

from typing import Any, Optional


PIPELINE_KIND = "IPADAPTER_PIPE"
EMBEDS_KIND = "IPADAPTER_EMBEDS"


def is_pipeline(value: Any) -> bool:
    return getattr(value, "kind", None) == PIPELINE_KIND


def is_embeds(value: Any) -> bool:
    return getattr(value, "kind", None) == EMBEDS_KIND


async def encode(
    pipeline: Any, image: Any, weight: float = 1.0, mask: Any = None,
) -> tuple[Any, Any]:
    """Encode one image into positive and negative IP-Adapter embeddings."""
    positive, negative = await pipeline.op(
        "ipadapter.encode",
        image=image, weight=float(weight), mask=mask,
    )
    return positive, negative


async def combine_embeds(
    embeds: Any, others: list[Any], method: str = "concat",
) -> Any:
    return await embeds.op(
        "ipadapter_embeds.combine",
        others=list(others), method=str(method),
    )


async def apply_embeds(
    pipeline: Any,
    model: Any,
    positive: Any,
    negative: Optional[Any] = None,
    attn_mask: Optional[Any] = None,
    weight: float = 1.0,
    weight_type: str = "linear",
    start_percent: float = 0.0,
    end_percent: float = 1.0,
    embeds_scaling: str = "V only",
) -> Any:
    """Apply already encoded image embeddings to a model."""
    return await pipeline.op(
        "ipadapter.apply_embeds",
        model=model,
        positive=positive,
        negative=negative,
        attn_mask=attn_mask,
        weight=float(weight),
        weight_type=str(weight_type),
        start_percent=float(start_percent),
        end_percent=float(end_percent),
        embeds_scaling=str(embeds_scaling),
    )


async def apply(
    pipeline: Any,
    model: Any,
    image: Any,
    negative_image: Optional[Any] = None,
    attn_mask: Optional[Any] = None,
    style_image: Optional[Any] = None,
    composition_image: Optional[Any] = None,
    weight: float = 0.7,
    weight_type: str = "channel penalty",
    start_percent: float = 0.0,
    end_percent: float = 1.0,
    combine_embeds: str = "concat",
    weight_faceidv2: float = 1.0,
    embeds_scaling: str = "V only",
    unfold_batch: bool = False,
    layer_weights: Optional[str] = None,
    weight_style: float = 1.0,
    weight_composition: float = 1.0,
    expand_style: bool = False,
) -> Any:
    """Apply this pipeline to a model using bounded image inputs."""
    return await pipeline.op(
        "ipadapter.apply",
        model=model,
        image=image,
        negative_image=negative_image,
        attn_mask=attn_mask,
        style_image=style_image,
        composition_image=composition_image,
        weight=float(weight),
        weight_type=str(weight_type),
        start_percent=float(start_percent),
        end_percent=float(end_percent),
        combine_embeds=str(combine_embeds),
        weight_faceidv2=float(weight_faceidv2),
        embeds_scaling=str(embeds_scaling),
        unfold_batch=bool(unfold_batch),
        layer_weights=layer_weights,
        weight_style=float(weight_style),
        weight_composition=float(weight_composition),
        expand_style=bool(expand_style),
    )

async def apply_tiled(
    pipeline: Any,
    model: Any,
    image: Any,
    negative_image: Optional[Any] = None,
    attn_mask: Optional[Any] = None,
    weight: float = 0.7,
    weight_type: str = "linear",
    start_percent: float = 0.0,
    end_percent: float = 1.0,
    combine_embeds: str = "concat",
    embeds_scaling: str = "V only",
    sharpening: float = 0.0,
    unfold_batch: bool = False,
) -> tuple[Any, Any, Any]:
    """Apply the canonical tiled IP-Adapter operation."""
    result = await pipeline.op(
        "ipadapter.apply_tiled",
        model=model,
        image=image,
        negative_image=negative_image,
        attn_mask=attn_mask,
        weight=float(weight),
        weight_type=str(weight_type),
        start_percent=float(start_percent),
        end_percent=float(end_percent),
        combine_embeds=str(combine_embeds),
        embeds_scaling=str(embeds_scaling),
        sharpening=float(sharpening),
        unfold_batch=bool(unfold_batch),
    )
    return result[0], result[1], result[2]

