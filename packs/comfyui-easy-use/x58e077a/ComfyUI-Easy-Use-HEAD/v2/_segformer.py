"""SegFormer semantic segmentation owned by this pack."""
from __future__ import annotations

import asyncio
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

import torch
import torch.nn.functional as functional


SECURE_KIND = "pack.segformer"
_DEPTHS = {
    "b2": [3, 4, 6, 3],
    "b3": [3, 4, 18, 3],
    "b5": [3, 6, 40, 3],
}
_CACHE: "OrderedDict[tuple[str, str, int], _Entry]" = OrderedDict()
_MAX_CACHED = 2
_MAX_PIXELS = 268_435_456


@dataclass
class _Entry:
    model: Any
    num_labels: int
    lock: threading.Lock = field(default_factory=threading.Lock)


def recipe(weight: str, variant: str, num_labels: int) -> dict[str, Any]:
    if not isinstance(weight, str) or not weight.lower().endswith(
        (".safetensors", ".sft")
    ):
        raise ValueError("SegFormer weights must use SafeTensors")
    if variant not in _DEPTHS:
        raise ValueError("SegFormer variant must be b2, b3, or b5")
    if (
        isinstance(num_labels, bool)
        or not isinstance(num_labels, int)
        or not 1 <= num_labels <= 1024
    ):
        raise ValueError("SegFormer num_labels must be in [1, 1024]")
    return {
        "secure_kind": SECURE_KIND,
        "weight": weight,
        "variant": variant,
        "num_labels": num_labels,
    }


def validated(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("secure_kind") != SECURE_KIND:
        raise TypeError("value is not a pack-owned SegFormer recipe")
    return recipe(value.get("weight"), value.get("variant"), value.get("num_labels"))


def _build_entry(
    state: dict[str, torch.Tensor], variant: str, num_labels: int,
) -> _Entry:
    try:
        from transformers import SegformerConfig, SegformerForSemanticSegmentation
    except ImportError as exc:
        raise RuntimeError("SegFormer requires Transformers") from exc
    config = SegformerConfig(
        num_labels=num_labels,
        num_channels=3,
        depths=_DEPTHS[variant],
        hidden_sizes=[64, 128, 320, 512],
        decoder_hidden_size=768,
        patch_sizes=[7, 3, 3, 3],
        strides=[4, 2, 2, 2],
        num_attention_heads=[1, 2, 5, 8],
        mlp_ratios=[4, 4, 4, 4],
        sr_ratios=[8, 4, 2, 1],
        hidden_act="gelu",
        hidden_dropout_prob=0.0,
        attention_probs_dropout_prob=0.0,
        classifier_dropout_prob=0.1,
        drop_path_rate=0.1,
        reshape_last_stage=True,
        semantic_loss_ignore_index=255,
    )
    model = SegformerForSemanticSegmentation(config)
    model_state = model.state_dict()
    if set(state) != set(model_state):
        try:
            from transformers.conversion_mapping import get_model_conversion_mapping
            from transformers.core_model_loading import WeightRenaming, rename_source_key
        except ImportError as exc:
            raise ValueError(
                "SegFormer weights do not match the installed Transformers version"
            ) from exc
        conversions = get_model_conversion_mapping(model, add_legacy=False)
        if not conversions or any(
            not isinstance(item, WeightRenaming) for item in conversions
        ):
            raise ValueError("SegFormer checkpoint conversion is not a pure key rename")
        converted = {}
        for key, tensor in state.items():
            renamed, _pattern = rename_source_key(
                key, conversions, [], model.base_model_prefix, model_state
            )
            if renamed in converted:
                raise ValueError("SegFormer checkpoint produced duplicate keys")
            converted[renamed] = tensor
        state = converted
    model.load_state_dict(state, strict=True)
    model.eval().to("cpu")
    return _Entry(model, num_labels)


async def _entry(ctx: Any, value: Any) -> tuple[_Entry, dict[str, Any]]:
    spec = validated(value)
    key = (spec["weight"], spec["variant"], spec["num_labels"])
    cached = _CACHE.pop(key, None)
    if cached is not None:
        _CACHE[key] = cached
        return cached, spec
    asset = await ctx.assets.resolve("semantic_segmentation", spec["weight"])
    state = await ctx.assets.load_state_dict(asset)
    if not isinstance(state, dict) or not state or any(
        not isinstance(name, str) or not isinstance(tensor, torch.Tensor)
        for name, tensor in state.items()
    ):
        raise ValueError("SegFormer weights must contain only tensors")
    state = {name: tensor.detach().cpu() for name, tensor in state.items()}
    loaded = await asyncio.to_thread(
        _build_entry, state, spec["variant"], spec["num_labels"]
    )
    while len(_CACHE) >= _MAX_CACHED:
        _unused_key, stale = _CACHE.popitem(last=False)
        stale.model.to("cpu")
    _CACHE[key] = loaded
    return loaded, spec


async def load(ctx: Any, weight: str, variant: str, num_labels: int) -> dict[str, Any]:
    value = recipe(weight, variant, num_labels)
    await _entry(ctx, value)
    return value


def _device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if getattr(torch.backends, "mps", None) is not None:
        if torch.backends.mps.is_available():
            return torch.device("mps")
    return torch.device("cpu")


async def mask(
    ctx: Any, value: Any, image: Any, classes: list[int] | tuple[int, ...],
) -> torch.Tensor:
    entry, spec = await _entry(ctx, value)
    if not isinstance(classes, (list, tuple)) or not 1 <= len(classes) <= 64:
        raise ValueError("semantic segmentation needs between 1 and 64 classes")
    selected = []
    for class_id in classes:
        if (
            isinstance(class_id, bool)
            or not isinstance(class_id, int)
            or not 0 <= class_id < spec["num_labels"]
        ):
            raise ValueError("semantic segmentation class IDs must match the model")
        if class_id not in selected:
            selected.append(class_id)
    pixels = await image.raw()
    if (
        not isinstance(pixels, torch.Tensor)
        or pixels.ndim != 4
        or pixels.shape[-1] < 3
        or not 1 <= len(pixels) <= 64
    ):
        raise ValueError("semantic segmentation needs a non-empty BHWC RGB batch")
    height, width = map(int, pixels.shape[1:3])
    if (
        height <= 0
        or width <= 0
        or height * width * len(pixels) > _MAX_PIXELS
        or not bool(torch.isfinite(pixels[..., :3]).all())
    ):
        raise ValueError("semantic segmentation image values are invalid")
    device = _device()
    mean = torch.tensor(
        (0.485, 0.456, 0.406), device=device, dtype=torch.float32
    ).view(1, 3, 1, 1)
    std = torch.tensor(
        (0.229, 0.224, 0.225), device=device, dtype=torch.float32
    ).view(1, 3, 1, 1)
    masks = []
    with entry.lock:
        entry.model.to(device=device, dtype=torch.float32)
        try:
            for frame in pixels:
                source = frame[..., :3].movedim(-1, 0).unsqueeze(0)
                source = source.to(device=device, dtype=torch.float32)
                source = functional.interpolate(
                    source, size=(512, 512), mode="bilinear", align_corners=False
                )
                logits = entry.model(pixel_values=(source - mean) / std).logits
                if (
                    not isinstance(logits, torch.Tensor)
                    or logits.ndim != 4
                    or logits.shape[:2] != (1, spec["num_labels"])
                ):
                    raise RuntimeError("SegFormer returned an invalid logits shape")
                logits = functional.interpolate(
                    logits, size=(height, width), mode="bilinear", align_corners=False
                )
                labels = logits.argmax(dim=1)[0]
                selected_mask = torch.zeros_like(labels, dtype=torch.bool)
                for class_id in selected:
                    selected_mask |= labels == class_id
                masks.append(selected_mask.detach().cpu().float())
        finally:
            entry.model.to("cpu")
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return torch.stack(masks, dim=0)
