from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as functional
from comfy_api.latest import sdk


WEIGHTS = {
    "blip-vqa-base": sdk.HuggingFaceWeight(
        repo_id="Salesforce/blip-vqa-base",
        filename="model.safetensors",
        folder="detection",
        revision="787b3d35d57e49572baabd22884b3d5a05acf072",
        sha256="33786eed34def0c95fa948128cb4386be9b9219aa2c2e25f1c9c744692121bb7",
        on_demand=True,
    ),
    "blip-vqa-capfilt-large": sdk.HuggingFaceWeight(
        repo_id="Salesforce/blip-vqa-capfilt-large",
        filename="pytorch_model.bin",
        folder="detection",
        revision="270352c30d7166e585cd686c3f2250e04bb509da",
        sha256="d47763c493a03f5e10b6d6472b2a8d995c8cbb6d9a466eede3d033fafd94d5a4",
        on_demand=True,
    ),
}

_TEXT_CONFIG = {
    "attention_probs_dropout_prob": 0.0,
    "bos_token_id": 30522,
    "encoder_hidden_size": 768,
    "eos_token_id": 2,
    "hidden_act": "gelu",
    "hidden_dropout_prob": 0.0,
    "hidden_size": 768,
    "initializer_range": 0.02,
    "intermediate_size": 3072,
    "is_decoder": True,
    "layer_norm_eps": 1e-12,
    "max_position_embeddings": 512,
    "num_attention_heads": 12,
    "num_hidden_layers": 12,
    "pad_token_id": 0,
    "projection_dim": 768,
    "sep_token_id": 102,
    "use_cache": True,
    "vocab_size": 30524,
}
_VISION_CONFIG = {
    "attention_dropout": 0.0,
    "dropout": 0.0,
    "hidden_act": "gelu",
    "hidden_size": 768,
    "image_size": 384,
    "initializer_range": 0.02,
    "intermediate_size": 3072,
    "layer_norm_eps": 1e-5,
    "num_attention_heads": 12,
    "num_channels": 3,
    "num_hidden_layers": 12,
    "patch_size": 16,
    "projection_dim": 512,
}


@dataclass
class _Entry:
    model: Any
    tokenizer: Any


_CACHE: OrderedDict[tuple[str, str], _Entry] = OrderedDict()


def _recipe(
    weight: str,
    architecture: str,
    precision: str,
    device: str,
) -> dict[str, str]:
    if architecture not in WEIGHTS:
        raise ValueError(f"unknown LayerStyle VQA model {architecture!r}")
    if precision not in {"fp16", "fp32"}:
        raise ValueError("LayerStyle VQA precision must be fp16 or fp32")
    if device not in {"cuda", "cpu"}:
        raise ValueError("LayerStyle VQA device must be cuda or cpu")
    if not isinstance(weight, str) or not weight:
        raise ValueError("LayerStyle VQA requires a managed model weight")
    return {
        "kind": "layerstyle.blip-vqa",
        "weight": weight,
        "architecture": architecture,
        "precision": precision,
        "device": device,
    }


def _validated_recipe(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {
        "kind", "weight", "architecture", "precision", "device",
    }:
        raise TypeError("VQAPrompt requires a LayerStyle VQA model")
    if value.get("kind") != "layerstyle.blip-vqa":
        raise TypeError("VQAPrompt requires a LayerStyle VQA model")
    return _recipe(
        value["weight"],
        value["architecture"],
        value["precision"],
        value["device"],
    )


def _build_entry(state: dict[str, torch.Tensor]) -> _Entry:
    try:
        from transformers import BertTokenizer, BlipConfig, BlipForQuestionAnswering
    except ImportError as error:
        raise RuntimeError(
            "LayerStyle VQA requires the pack's Transformers dependency"
        ) from error

    if not state or any(
        not isinstance(name, str) or not isinstance(tensor, torch.Tensor)
        for name, tensor in state.items()
    ):
        raise ValueError("LayerStyle BLIP weights must contain only tensors")
    config = BlipConfig(
        text_config=_TEXT_CONFIG,
        vision_config=_VISION_CONFIG,
        projection_dim=512,
        image_text_hidden_size=256,
    )
    model = BlipForQuestionAnswering(config)
    incompatible = model.load_state_dict(state, strict=False)
    missing = set(incompatible.missing_keys) - {
        "text_decoder.cls.predictions.decoder.bias",
    }
    unexpected = set(incompatible.unexpected_keys) - {
        "text_decoder.bert.embeddings.position_ids",
        "text_encoder.embeddings.position_ids",
    }
    if missing or unexpected:
        raise ValueError("LayerStyle BLIP weights do not match the fixed architecture")
    model.eval().to("cpu")
    vocab = Path(__file__).with_name("vqa_tokenizer") / "vocab.txt"
    tokenizer = BertTokenizer(str(vocab), do_lower_case=True)
    if len(tokenizer) != 30522:
        raise RuntimeError("LayerStyle's BLIP tokenizer vocabulary is invalid")
    return _Entry(model=model, tokenizer=tokenizer)


async def _entry(ctx: Any, value: Any) -> tuple[_Entry, dict[str, str]]:
    recipe = _validated_recipe(value)
    key = (recipe["weight"], recipe["architecture"])
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
        raise ValueError("LayerStyle BLIP weights must contain only tensors")
    state = {
        name: tensor.detach().cpu()
        for name, tensor in state.items()
    }
    loaded = await asyncio.to_thread(_build_entry, state)
    while _CACHE:
        _old_key, old = _CACHE.popitem(last=False)
        old.model.to("cpu")
    _CACHE[key] = loaded
    return loaded, recipe


async def load(
    ctx: Any,
    weight: str,
    architecture: str,
    precision: str,
    device: str,
) -> dict[str, str]:
    recipe = _recipe(weight, architecture, precision, device)
    await _entry(ctx, recipe)
    return recipe


async def answer(
    ctx: Any,
    value: Any,
    pixels: torch.Tensor,
    question: str,
    max_new_tokens: int = 32,
) -> str:
    question = str(question).strip()
    if not question or len(question) > 4096:
        raise ValueError("VQA questions must contain 1..4096 characters")
    if (
        isinstance(max_new_tokens, bool)
        or not isinstance(max_new_tokens, int)
        or not 1 <= max_new_tokens <= 128
    ):
        raise ValueError("VQA max_new_tokens must be in [1, 128]")
    if (
        not isinstance(pixels, torch.Tensor)
        or pixels.ndim != 4
        or pixels.shape[0] != 1
        or pixels.shape[-1] < 3
    ):
        raise ValueError("VQA requires exactly one BHWC RGB image")
    height, width = map(int, pixels.shape[1:3])
    if (
        height <= 0
        or width <= 0
        or height * width > 67_108_864
        or not bool(torch.isfinite(pixels[..., :3]).all())
    ):
        raise ValueError("VQA image dimensions are invalid")

    entry, recipe = await _entry(ctx, value)
    target = (
        torch.device("cuda")
        if recipe["device"] == "cuda" and torch.cuda.is_available()
        else torch.device("cpu")
    )
    dtype = (
        torch.float16
        if recipe["precision"] == "fp16" and target.type == "cuda"
        else torch.float32
    )
    source = pixels[..., :3].movedim(-1, 1).to(
        device=target, dtype=dtype,
    ).clamp(0.0, 1.0)
    source = functional.interpolate(
        source, size=(384, 384), mode="bicubic",
        align_corners=False, antialias=True,
    )
    mean = torch.tensor(
        (0.48145466, 0.4578275, 0.40821073),
        device=target, dtype=dtype,
    ).view(1, 3, 1, 1)
    std = torch.tensor(
        (0.26862954, 0.26130258, 0.27577711),
        device=target, dtype=dtype,
    ).view(1, 3, 1, 1)
    source = (source - mean) / std
    encoded = entry.tokenizer(
        question, return_tensors="pt", truncation=True, max_length=512,
    )
    input_ids = encoded["input_ids"].to(target)
    attention_mask = encoded["attention_mask"].to(target)
    entry.model.to(device=target, dtype=dtype)
    try:
        tokens = entry.model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            pixel_values=source,
            max_new_tokens=max_new_tokens,
        )
        if (
            not isinstance(tokens, torch.Tensor)
            or tokens.ndim != 2
            or tokens.shape[0] != 1
        ):
            raise RuntimeError("LayerStyle BLIP returned invalid tokens")
        return entry.tokenizer.decode(
            tokens[0].detach().cpu().tolist(),
            skip_special_tokens=True,
        ).strip()
    finally:
        entry.model.to("cpu")


def clear_cache() -> int:
    entries = list(_CACHE.values())
    _CACHE.clear()
    for entry in entries:
        entry.model.to("cpu")
    return len(entries)
