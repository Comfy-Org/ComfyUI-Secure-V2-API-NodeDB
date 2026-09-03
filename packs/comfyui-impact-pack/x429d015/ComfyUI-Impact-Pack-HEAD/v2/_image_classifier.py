"""Transformers image classification owned by Impact Pack."""
from __future__ import annotations

import asyncio
import threading
from collections import OrderedDict
from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import torch
from PIL import Image


SECURE_KIND = "impact.image_classifier"
_ARCHITECTURES = {
    "vit-base-patch16-224",
    "beit-base-patch16-224",
    "resnet-50-224",
}
_CACHE: "OrderedDict[tuple[str, str], _Entry]" = OrderedDict()
_MAX_CACHED = 3


@dataclass
class _Entry:
    model: Any
    processor: Any
    num_labels: int
    weight_dtype: torch.dtype
    lock: threading.Lock = field(default_factory=threading.Lock)


def recipe(
    weight: str,
    architecture: str,
    labels: list[str] | tuple[str, ...],
    use_accelerator: bool,
) -> dict[str, Any]:
    if not isinstance(weight, str) or not weight.lower().endswith(".safetensors"):
        raise ValueError("image classifier weights must use SafeTensors")
    if architecture not in _ARCHITECTURES:
        raise ValueError("image classifier architecture is not supported")
    if not isinstance(labels, (list, tuple)):
        raise TypeError("image classifier labels must be a list")
    normalized = tuple(str(label) for label in labels)
    if (
        not normalized
        or len(normalized) > 10_000
        or any(not label or len(label) > 256 for label in normalized)
    ):
        raise ValueError("image classifier labels are invalid")
    return {
        "secure_kind": SECURE_KIND,
        "weight": weight,
        "architecture": architecture,
        "labels": normalized,
        "use_accelerator": bool(use_accelerator),
    }


def validated(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("secure_kind") != SECURE_KIND:
        raise TypeError("TRANSFORMERS_CLASSIFIER must be an Impact classifier recipe")
    return recipe(
        value.get("weight"),
        value.get("architecture"),
        value.get("labels"),
        value.get("use_accelerator", True),
    )


def _build_entry(
    state: dict[str, torch.Tensor], architecture: str,
) -> _Entry:
    try:
        from transformers import (
            BeitConfig,
            BeitForImageClassification,
            BeitImageProcessor,
            ConvNextImageProcessor,
            ResNetConfig,
            ResNetForImageClassification,
            ViTConfig,
            ViTForImageClassification,
            ViTImageProcessor,
        )
    except ImportError as exc:
        raise RuntimeError("Impact image classification requires Transformers") from exc

    heads = {
        "vit-base-patch16-224": "classifier.weight",
        "beit-base-patch16-224": "classifier.weight",
        "resnet-50-224": "classifier.1.weight",
    }
    head = state.get(heads[architecture])
    if not isinstance(head, torch.Tensor) or head.ndim != 2:
        raise ValueError("classifier weights have no compatible output head")
    num_labels = int(head.shape[0])
    if not 1 <= num_labels <= 10_000:
        raise ValueError("classifier output count is outside the safe range")
    dtypes = {
        value.dtype
        for value in state.values()
        if isinstance(value, torch.Tensor) and value.is_floating_point()
    }
    if len(dtypes) != 1:
        raise ValueError("classifier weights must use one floating-point dtype")
    weight_dtype = next(iter(dtypes))
    if weight_dtype not in (torch.float16, torch.bfloat16, torch.float32):
        raise ValueError("classifier weights use an unsupported dtype")

    if architecture == "vit-base-patch16-224":
        config = ViTConfig(
            num_labels=num_labels,
            attention_probs_dropout_prob=0.0,
            encoder_stride=16,
            hidden_act="gelu",
            hidden_dropout_prob=0.0,
            hidden_size=768,
            image_size=224,
            initializer_range=0.02,
            intermediate_size=3072,
            layer_norm_eps=1e-12,
            num_attention_heads=12,
            num_channels=3,
            num_hidden_layers=12,
            patch_size=16,
            qkv_bias=True,
        )
        model = ViTForImageClassification(config)
        processor = ViTImageProcessor(
            do_resize=True,
            size={"height": 224, "width": 224},
            resample=2,
            do_rescale=True,
            rescale_factor=1.0 / 255.0,
            do_normalize=True,
            image_mean=(0.5, 0.5, 0.5),
            image_std=(0.5, 0.5, 0.5),
        )
    elif architecture == "beit-base-patch16-224":
        config = BeitConfig(
            num_labels=num_labels,
            attention_probs_dropout_prob=0.0,
            drop_path_rate=0.1,
            hidden_act="gelu",
            hidden_dropout_prob=0.0,
            hidden_size=768,
            image_size=224,
            initializer_range=0.02,
            intermediate_size=3072,
            layer_norm_eps=1e-12,
            layer_scale_init_value=0.1,
            num_attention_heads=12,
            num_channels=3,
            num_hidden_layers=12,
            patch_size=16,
            use_absolute_position_embeddings=False,
            use_mask_token=False,
            use_mean_pooling=True,
            use_relative_position_bias=True,
            use_shared_relative_position_bias=False,
        )
        model = BeitForImageClassification(config)
        processor = BeitImageProcessor(
            do_resize=True,
            size={"height": 224, "width": 224},
            resample=2,
            do_rescale=True,
            rescale_factor=1.0 / 255.0,
            do_normalize=True,
            do_center_crop=False,
            crop_size={"height": 224, "width": 224},
            do_reduce_labels=False,
            image_mean=(0.5, 0.5, 0.5),
            image_std=(0.5, 0.5, 0.5),
        )
    else:
        config = ResNetConfig(
            num_labels=num_labels,
            depths=[3, 4, 6, 3],
            downsample_in_first_stage=False,
            embedding_size=64,
            hidden_act="relu",
            hidden_sizes=[256, 512, 1024, 2048],
            layer_type="bottleneck",
            num_channels=3,
            out_features=["stage4"],
            out_indices=[4],
        )
        model = ResNetForImageClassification(config)
        processor = ConvNextImageProcessor(
            do_resize=True,
            size={"shortest_edge": 224},
            resample=3,
            do_rescale=True,
            rescale_factor=1.0 / 255.0,
            do_normalize=True,
            image_mean=(0.485, 0.456, 0.406),
            image_std=(0.229, 0.224, 0.225),
        )

    model = model.to(dtype=weight_dtype)
    model.load_state_dict(state, strict=True)
    model.eval().to("cpu")
    return _Entry(model, processor, num_labels, weight_dtype)


async def _entry(ctx: Any, value: Any) -> tuple[_Entry, dict[str, Any]]:
    spec = validated(value)
    key = (spec["weight"], spec["architecture"])
    cached = _CACHE.pop(key, None)
    if cached is not None:
        _CACHE[key] = cached
        if cached.num_labels != len(spec["labels"]):
            raise ValueError("classifier labels do not match the weight output count")
        return cached, spec

    asset = await ctx.assets.resolve("detection", spec["weight"])
    state = await ctx.assets.load_state_dict(asset)
    if not isinstance(state, dict) or not state or any(
        not isinstance(name, str) or not isinstance(tensor, torch.Tensor)
        for name, tensor in state.items()
    ):
        raise ValueError("classifier weights must contain only tensors")
    state = {name: tensor.detach().cpu() for name, tensor in state.items()}
    loaded = await asyncio.to_thread(_build_entry, state, spec["architecture"])
    if loaded.num_labels != len(spec["labels"]):
        raise ValueError("classifier labels do not match the weight output count")
    while len(_CACHE) >= _MAX_CACHED:
        _unused_key, stale = _CACHE.popitem(last=False)
        stale.model.to("cpu")
    _CACHE[key] = loaded
    return loaded, spec


async def load(
    ctx: Any,
    weight: str,
    architecture: str,
    labels: list[str] | tuple[str, ...],
    use_accelerator: bool,
) -> dict[str, Any]:
    value = recipe(weight, architecture, labels, use_accelerator)
    await _entry(ctx, value)
    return value


def _device(enabled: bool) -> torch.device:
    if enabled and torch.cuda.is_available():
        return torch.device("cuda")
    if enabled and getattr(torch.backends, "mps", None) is not None:
        if torch.backends.mps.is_available():
            return torch.device("mps")
    return torch.device("cpu")


async def classify(
    ctx: Any,
    value: Any,
    images: Any,
    top_k: int = 5,
) -> list[list[dict[str, Any]]]:
    top_k = int(top_k)
    if not 1 <= top_k <= 1000:
        raise ValueError("image classifier top_k must be in [1, 1000]")
    entry, spec = await _entry(ctx, value)
    pixels = await images.raw()
    if (
        not isinstance(pixels, torch.Tensor)
        or pixels.ndim != 4
        or pixels.shape[-1] < 3
        or not 1 <= len(pixels) <= 4096
    ):
        raise ValueError("classifier images must be a non-empty BHWC batch")
    labels = spec["labels"]
    device = _device(spec["use_accelerator"])
    dtype = entry.weight_dtype if device.type == "cuda" else torch.float32
    scope = (
        torch.autocast("cuda", dtype=dtype)
        if device.type == "cuda" and dtype != torch.float32
        else nullcontext()
    )
    with entry.lock:
        entry.model.to(device=device, dtype=dtype)
        try:
            source = [
                Image.fromarray(
                    np.clip(
                        image.detach().cpu().numpy()[..., :3] * 255.0,
                        0,
                        255,
                    ).astype(np.uint8),
                    mode="RGB",
                )
                for image in pixels
            ]
            inputs = entry.processor(images=source, return_tensors="pt")
            inputs = {name: tensor.to(device) for name, tensor in inputs.items()}
            with scope, torch.inference_mode():
                scores = torch.softmax(entry.model(**inputs).logits.float(), dim=-1)
        finally:
            entry.model.to(device="cpu", dtype=entry.weight_dtype)
    if scores.ndim != 2 or scores.shape[1] != len(labels):
        raise RuntimeError("image classifier returned an invalid score shape")
    count = min(top_k, len(labels))
    values, indices = torch.topk(scores.cpu(), count, dim=-1)
    return [
        [
            {"label": labels[int(index)], "score": float(score)}
            for score, index in zip(row_scores, row_indices, strict=True)
        ]
        for row_scores, row_indices in zip(values, indices, strict=True)
    ]
