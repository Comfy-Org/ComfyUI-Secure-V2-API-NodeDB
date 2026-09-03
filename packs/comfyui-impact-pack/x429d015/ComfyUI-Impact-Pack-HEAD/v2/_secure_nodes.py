"""Secure Nodes 2.0 conversion for the pinned Impact Pack snapshot.

The upstream pack combines ordinary value, mask, image, SEGS and pipe
operations with detectors that load executable Python stacks, process-global
server routes, arbitrary model paths, and objects containing guest callbacks.
This entrypoint keeps the complete frozen node surface while implementing the
closed data operations locally and routing model work through the Secure Nodes
SDK.  Nodes whose behaviour has no closed host primitive fail explicitly.
"""
from __future__ import annotations

import asyncio
import base64
import io as bytes_io
import math
import random
import re
import zipfile
from collections import namedtuple
from pathlib import PurePosixPath
from typing import Any

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from . import _image_classifier, _ipadapter, _onnx_detector
from ._image_ops import common_upscale
from ._secure_runtime import SCHEMAS, bind_node, materialize, sdk, unsupported
from ._wildcard_runtime import load_catalogue as _load_wildcard_catalogue
from ._wildcard_runtime import populate as _populate_catalogue_wildcards


SEG = namedtuple(
    "SEG",
    (
        "cropped_image",
        "cropped_mask",
        "confidence",
        "crop_region",
        "bbox",
        "label",
        "control_net_wrapper",
    ),
    defaults=(None,),
)


_CLIPSEG_WEIGHT = sdk.HuggingFaceWeight(
    repo_id="Kijai/clipseg-rd64-refined-fp16",
    filename="model.safetensors",
    folder="detection",
    sha256="3bfcd7b05b526f849cf18c3102fed42c48ef396377b8e11b777a691029ca1295",
)

_BIG_LAMA_WEIGHT = sdk.HuggingFaceWeight(
    repo_id="michaelgold/big-lama",
    filename="big-lama.safetensors",
    folder="detection",
    revision="98ab7cface89a594b381f32fc7a9f2cae3f91ccc",
    sha256="326ae1889b92d07c8819c35eaf561f8b290d057536eeb12524b72997f31005ec",
)


def _classifier_weight(repo_id: str, revision: str, sha256: str):
    return sdk.HuggingFaceWeight(
        repo_id=repo_id,
        filename="model.safetensors",
        folder="detection",
        revision=revision,
        sha256=sha256,
        on_demand=True,
    )


_HF_CLASSIFIERS = {
    "rizvandwiki/gender-classification-2": {
        "weight": _classifier_weight(
            "rizvandwiki/gender-classification-2",
            "a999f3503a6893e3dc75350dd623f4219c71e3b9",
            "870a9cfb711ae21637ff145cc5496aa16bf6768b988ae3a09190eb23e6db2064",
        ),
        "architecture": "vit-base-patch16-224",
        "labels": ("female", "male"),
    },
    "NTQAI/pedestrian_gender_recognition": {
        "weight": _classifier_weight(
            "NTQAI/pedestrian_gender_recognition",
            "5bbae752fe1c7793c43f727b94198f385e53e2a6",
            "245e3c6e149684e459d87b2bd290ef88c6b699316ee6f366f5f75a20947e9c4a",
        ),
        "architecture": "beit-base-patch16-224",
        "labels": ("Female", "Male"),
    },
    "Leilab/gender_class": {
        "weight": _classifier_weight(
            "Leilab/gender_class",
            "fa94bd8c595d9824734ec5caf14252fd71afec0a",
            "ac4d98312edaeb37c7c50c218c5e23f31e59d26504224012275243fce7e7a2d8",
        ),
        "architecture": "vit-base-patch16-224",
        "labels": ("men", "women"),
    },
    "ProjectPersonal/GenderClassifier": {
        "weight": _classifier_weight(
            "ProjectPersonal/GenderClassifier",
            "2ab0265efbfea7cb1b4c93c3d1b92bbf6193748b",
            "3bf8c5ef29e34310011e6bf288d7178536579815262765b1e69793ab1b9e0428",
        ),
        "architecture": "vit-base-patch16-224",
        "labels": ("Human Female", "Human Male"),
    },
    "crangana/trained-gender": {
        "weight": _classifier_weight(
            "crangana/trained-gender",
            "792e19c98deefb9b32184e72ec36320901844b74",
            "77cb7f2a3489ffa53d355061e320dbf2e4828a577db6f5fc7eba81d48e85e4dc",
        ),
        "architecture": "resnet-50-224",
        "labels": ("Male", "Female"),
    },
    "cledoux42/GenderNew_v002": {
        "weight": _classifier_weight(
            "cledoux42/GenderNew_v002",
            "86a1b60e057806e78cc43b959a1f237d2a413169",
            "95e8547ca86842eee0fab10f17c265e7c725e42f806c8fc9e62ae091466a1e40",
        ),
        "architecture": "vit-base-patch16-224",
        "labels": ("man", "woman"),
    },
    "ivensamdh/genderage2": {
        "weight": _classifier_weight(
            "ivensamdh/genderage2",
            "5fb5f0d5cfcbfdf41534a0f891a16e1f75c17d01",
            "0942b069e0581a74084dc0881955aee8e2df46239f9c285f7b864191816e9aa3",
        ),
        "architecture": "vit-base-patch16-224",
        "labels": (
            "Female", "Male", "Age0to5", "Age6to10", "Age11to15",
            "Age16to25", "Age26to35", "Age36to49", "Age50to69",
            "Age70to99",
        ),
    },
}


def _ctx():
    return sdk.ctx()


def _one(value: Any) -> tuple[Any]:
    return (value,)


async def _raw(value: Any) -> Any:
    return await materialize(value)


def _asset_name(value: Any) -> str:
    name = str(value or "").replace("\\", "/").strip()
    path = PurePosixPath(name)
    if (
        not name
        or path.is_absolute()
        or any(part in ("", ".", "..") for part in path.parts)
        or "://" in name
        or ":" in path.parts[0]
    ):
        raise ValueError("asset names must come from a host catalogue")
    return path.as_posix()


def _annotated_asset(value: Any) -> tuple[str, str]:
    """Split ComfyUI's ``name [input|output|temp]`` locator safely."""
    text = str(value or "").strip()
    match = re.fullmatch(r"(.*?)(?:\s+\[(input|output|temp)\])?", text)
    if match is None:
        raise ValueError("invalid asset locator")
    return match.group(2) or "input", _asset_name(match.group(1))


def _seg(value: Any) -> SEG:
    if isinstance(value, SEG):
        return value
    if isinstance(value, dict):
        return SEG(*(value.get(field) for field in SEG._fields))
    if isinstance(value, (tuple, list)) and len(value) == 7:
        return SEG(*value)
    raise TypeError("SEG_ELT must use Impact Pack's seven-field tuple layout")


def _segs(value: Any) -> tuple[tuple[int, int], list[SEG]]:
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise TypeError("SEGS must be a (shape, segments) pair")
    header = tuple(int(x) for x in value[0])
    if len(header) != 2:
        raise TypeError("SEGS shape must be (height, width)")
    return (header, [_seg(item) for item in value[1]])


def _basic_pipe(value: Any) -> tuple[Any, Any, Any, Any, Any]:
    if not isinstance(value, (tuple, list)) or len(value) < 5:
        raise TypeError("BASIC_PIPE must contain model, CLIP, VAE and conditioning")
    return tuple(value[:5])


def _detailer_pipe(value: Any) -> tuple[Any, ...]:
    if not isinstance(value, (tuple, list)) or len(value) < 14:
        raise TypeError("DETAILER_PIPE must use Impact Pack's 14-field layout")
    return tuple(value[:14])


def _provider(kind: str):
    async def execute(**kwargs):
        return _one({"secure_kind": kind, "params": dict(kwargs)})

    return execute


async def _preview_hook_provider(quality, **kwargs):
    quality = int(quality)
    if not 20 <= quality <= 100:
        raise ValueError("preview-hook quality must be in [20, 100]")
    recipe = {
        "secure_kind": "PreviewDetailerHookProvider",
        "params": {"quality": quality, **kwargs},
    }
    # Upstream exposes the same hook through DETAILER_HOOK and UPSCALER_HOOK.
    return recipe, recipe


async def _lama_remover_hook_provider(
    mask_threshold, gaussblur_radius, skip_sampling, **_kwargs,
):
    threshold = int(mask_threshold)
    blur_radius = int(gaussblur_radius)
    if not 0 <= threshold <= 255:
        raise ValueError("LaMa mask_threshold must be in [0, 255]")
    if not 0 <= blur_radius <= 20:
        raise ValueError("LaMa gaussblur_radius must be in [0, 20]")
    if type(skip_sampling) is not bool:
        raise TypeError("LaMa skip_sampling must be a bool")
    model = await _ctx().models.load_inpaint_model(
        _BIG_LAMA_WEIGHT.catalogue_name, architecture="big-lama")
    return _one({
        "secure_kind": "LamaRemoverDetailerHookProvider",
        "params": {
            "mask_threshold": threshold,
            "gaussblur_radius": blur_radius,
            "skip_sampling": skip_sampling,
            "model": model,
        },
    })


def _combine_provider(kind: str):
    async def execute(**kwargs):
        return _one({
            "secure_kind": kind,
            "items": [value for value in kwargs.values() if value is not None],
        })

    return execute


_DETAILER_HOOK_RECIPE_KINDS = frozenset({
    "BlackPatchRetryHookProvider",
    "CoreMLDetailerHookProvider",
    "CustomSamplerDetailerHookProvider",
    "DenoiseSchedulerDetailerHookProvider",
    "LamaRemoverDetailerHookProvider",
    "NoiseInjectionDetailerHookProvider",
    "PreviewDetailerHookProvider",
    "SEGSLabelFilterDetailerHookProvider",
    "SEGSOrderedFilterDetailerHookProvider",
    "SEGSRangeFilterDetailerHookProvider",
    "UnsamplerDetailerHookProvider",
    "VariationNoiseDetailerHookProvider",
})


def _detailer_hook_recipes(hook: Any) -> list[dict[str, Any]]:
    """Flatten the closed, data-only hook language in execution order."""
    if hook is None:
        return []
    if not isinstance(hook, dict):
        raise TypeError("DETAILER_HOOK must be a secure declarative recipe")
    kind = hook.get("secure_kind")
    if kind == "detailer_hook_chain":
        items = hook.get("items")
        if not isinstance(items, list):
            raise TypeError("detailer hook chain must contain a recipe list")
        result: list[dict[str, Any]] = []
        for item in items:
            result.extend(_detailer_hook_recipes(item))
        return result
    if kind not in _DETAILER_HOOK_RECIPE_KINDS:
        raise TypeError(f"unknown secure detailer hook recipe {kind!r}")
    params = hook.get("params")
    if not isinstance(params, dict):
        raise TypeError("detailer hook recipe params must be a mapping")
    return [hook]


async def _clipseg_detector_provider(text, blur, threshold, dilation_factor,
                                     **_kwargs):
    """Return a data-only detector recipe backed by the fixed CLIPSeg model."""
    blur = float(blur)
    threshold = float(threshold)
    dilation = int(dilation_factor)
    if not 0.0 <= blur <= 15.0:
        raise ValueError("CLIPSeg blur must be in [0, 15]")
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("CLIPSeg threshold must be in [0, 1]")
    if not 0 <= dilation <= 10:
        raise ValueError("CLIPSeg dilation_factor must be in [0, 10]")
    model = await _ctx().models.load_clipseg(_CLIPSEG_WEIGHT.catalogue_name)
    return _one({
        "secure_kind": "impact.clipseg_bbox",
        "model": model,
        "text": str(text),
        "blur": blur,
        "threshold": threshold,
        "dilation_factor": dilation,
    })


async def _hf_classifier_provider(
    preset_repo_id, manual_repo_id, device_mode, **_kwargs,
):
    if preset_repo_id == "Manual repo id":
        raise RuntimeError(
            "manual Hugging Face repository IDs are not permitted; select a "
            "sealed preset with declared SafeTensors weights")
    spec = _HF_CLASSIFIERS.get(str(preset_repo_id))
    if spec is None:
        raise ValueError("classifier preset is not in the sealed catalogue")
    if device_mode not in ("AUTO", "Prefer GPU", "CPU"):
        raise ValueError("classifier device_mode is invalid")
    del manual_repo_id
    weight = spec["weight"]
    logical = await _ctx().models.download_huggingface_weights(
        weight.repo_id,
        weight.filename,
        weight.folder,
        revision=weight.revision,
        sha256=weight.sha256,
    )
    classifier = await _image_classifier.load(
        _ctx(),
        logical,
        spec["architecture"],
        list(spec["labels"]),
        device_mode != "CPU",
    )
    classifier["repo_id"] = str(preset_repo_id)
    return _one(classifier)


# ---------------------------------------------------------------------------
# Logic and flow nodes
# ---------------------------------------------------------------------------

def _action_result(result=(), actions=()):
    return {
        "ui": {"secure_actions": list(actions)},
        "result": tuple(result),
    }


def _frontend_scalar(value):
    if value is None or isinstance(value, (str, bool, int)):
        if isinstance(value, str) and len(value) > 65536:
            raise ValueError("frontend action strings are limited to 65536 characters")
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise TypeError("frontend workflow actions accept only finite JSON scalars")

async def _identity(value=None, signal=None, **kwargs):
    if value is not None or "value" in kwargs:
        return _one(value)
    if signal is not None or "signal" in kwargs:
        return _one(signal)
    return _one(next(iter(kwargs.values()), None))


async def _compare(cmp, a, b, **_kwargs):
    operations = {
        "a = b": lambda: a == b,
        "a <> b": lambda: a != b,
        "a > b": lambda: a > b,
        "a < b": lambda: a < b,
        "a >= b": lambda: a >= b,
        "a <= b": lambda: a <= b,
        "tt": lambda: True,
        "ff": lambda: False,
    }
    if cmp not in operations:
        raise ValueError(f"unknown comparison {cmp!r}")
    return _one(bool(operations[cmp]()))


async def _not_empty_segs(segs, **_kwargs):
    return _one(bool(_segs(await _raw(segs))[1]))


async def _branch(cond, tt_value=None, ff_value=None, **_kwargs):
    return _one(tt_value if bool(cond) else ff_value)


async def _branch_lazy(cond, tt_value=None, ff_value=None, **_kwargs):
    key = "tt_value" if bool(cond) else "ff_value"
    return [key] if (tt_value if bool(cond) else ff_value) is None else []


async def _convert(value, **_kwargs):
    text = str(value)
    if re.fullmatch(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", text):
        number = float(text)
    else:
        number = 0.0 if text.lower() == "false" else 1.0
    return text, float(number), int(number), bool(number)


async def _if_none(signal=None, any_input=None, **_kwargs):
    return signal, any_input is not None


async def _logical(operator, bool_a, bool_b, **_kwargs):
    if operator == "and":
        result = bool_a and bool_b
    elif operator == "or":
        result = bool_a or bool_b
    elif operator == "xor":
        result = bool(bool_a) != bool(bool_b)
    else:
        raise ValueError(f"unknown logical operator {operator!r}")
    return _one(bool(result))


async def _conditional_stop(cond, **_kwargs):
    actions = ({"kind": "stop-iteration"},) if bool(cond) else ()
    return _action_result(actions=actions)


async def _neg(value, **_kwargs):
    return _one(not bool(value))


async def _value_receiver(typ, value, **_kwargs):
    if typ == "INT":
        result = int(value)
    elif typ == "FLOAT":
        result = float(value)
    elif typ == "BOOLEAN":
        result = str(value).lower() == "true"
    else:
        result = str(value)
    return _one(result)


async def _value_sender(value, link_id=0, signal_opt=None, **_kwargs):
    action = {
        "kind": "value",
        "link_id": int(link_id),
        "value": _frontend_scalar(value),
    }
    return _action_result((signal_opt,), (action,))


async def _image_info(value, **_kwargs):
    image = await _raw(value)
    if image.ndim != 4:
        raise ValueError("IMAGE must be a BHWC tensor")
    return tuple(int(x) for x in image.shape)


async def _latent_info(value, **_kwargs):
    latent = await _raw(value)
    shape = latent["samples"].shape
    return int(shape[0]), int(shape[2] * 8), int(shape[3] * 8), int(shape[1])


async def _minmax(mode, a, b, **_kwargs):
    return _one(max(a, b) if mode else min(a, b))


async def _queue_passthrough(signal=None, mode=True, **_kwargs):
    actions = ({"kind": "queue"},) if bool(mode) else ()
    return _action_result((signal,), actions)


async def _queue_countdown(
    count, total, mode=True, signal=None, unique_id=None, **_kwargs,
):
    count, total = int(count), int(total)
    actions = []
    if bool(mode):
        node_id = await _ctx().graph.current_node_id()
        next_count = count + 1 if count < total - 1 else 0
        actions.append({
            "kind": "widget",
            "node_id": node_id,
            "widget_name": "count",
            "value_type": "INT",
            "value": next_count,
        })
        if count < total - 1:
            actions.append({"kind": "queue"})
    return _action_result((signal, count, total), actions)


async def _set_widget_value(
    signal, node_id, widget_name, boolean_value=None, int_value=None,
    float_value=None, string_value=None, **_kwargs,
):
    candidates = (
        ("BOOLEAN", boolean_value), ("INT", int_value),
        ("FLOAT", float_value), ("STRING", string_value),
    )
    selected = next(((kind, value) for kind, value in candidates
                     if value is not None), None)
    actions = ()
    if selected is not None:
        kind, value = selected
        name = str(widget_name)
        if not name or len(name) > 256 or any(ord(char) < 32 for char in name):
            raise ValueError("widget_name must be a bounded printable name")
        actions = ({
            "kind": "widget",
            "node_id": str(int(node_id)),
            "widget_name": name,
            "value_type": kind,
            "value": _frontend_scalar(value),
        },)
    return _action_result((signal,), actions)


async def _set_mute_state(signal, node_id, set_state, **_kwargs):
    return _action_result((signal,), ({
        "kind": "mute",
        "node_id": str(int(node_id)),
        "is_active": bool(set_state),
    },))


async def _sleep(signal, seconds, **_kwargs):
    await asyncio.sleep(min(3600.0, max(0.0, float(seconds))))
    return _one(signal)


async def _control_bridge(value, mode, behavior="Stop", **_kwargs):
    if behavior == "Stop":
        return _one(value if bool(mode) else await _ctx().graph.block())
    if behavior not in {"Mute", "Bypass"}:
        raise ValueError(f"unknown control bridge behavior {behavior!r}")
    action = {
        "kind": "bridge",
        "node_id": await _ctx().graph.current_node_id(),
        "mode": bool(mode),
        "behavior": behavior,
    }
    return _action_result((value,), (action,))


async def _execution_order(signal, value, **_kwargs):
    return signal, value


async def _list_bridge(list_input, **_kwargs):
    return _one(list_input)


# ---------------------------------------------------------------------------
# BASIC_PIPE and DETAILER_PIPE nodes
# ---------------------------------------------------------------------------

async def _to_basic(model, clip, vae, positive, negative, **_kwargs):
    return _one((model, clip, vae, positive, negative))


async def _from_basic(basic_pipe, **_kwargs):
    return _basic_pipe(basic_pipe)


async def _from_basic_v2(basic_pipe, **_kwargs):
    pipe = _basic_pipe(basic_pipe)
    return (pipe,) + pipe


async def _any_to_basic(any_pipe, **_kwargs):
    return _one(_basic_pipe(any_pipe))


async def _edit_basic(basic_pipe, **kwargs):
    values = list(_basic_pipe(basic_pipe))
    for index, name in enumerate(("model", "clip", "vae", "positive", "negative")):
        if kwargs.get(name) is not None:
            values[index] = kwargs[name]
    return _one(tuple(values))


async def _to_detailer(**kwargs):
    return _one((
        kwargs["model"], kwargs["clip"], kwargs["vae"],
        kwargs["positive"], kwargs["negative"], kwargs.get("wildcard", ""),
        kwargs["bbox_detector"], kwargs.get("segm_detector_opt"),
        kwargs.get("sam_model_opt"), kwargs.get("detailer_hook"),
        kwargs.get("refiner_model"), kwargs.get("refiner_clip"),
        kwargs.get("refiner_positive"), kwargs.get("refiner_negative"),
    ))


async def _basic_to_detailer(basic_pipe=None, base_basic_pipe=None,
                             refiner_basic_pipe=None, **kwargs):
    base = _basic_pipe(basic_pipe or base_basic_pipe)
    refiner = _basic_pipe(refiner_basic_pipe) if refiner_basic_pipe else (None,) * 5
    return _one((
        *base, kwargs.get("wildcard", ""), kwargs["bbox_detector"],
        kwargs.get("segm_detector_opt"), kwargs.get("sam_model_opt"),
        kwargs.get("detailer_hook"), refiner[0], refiner[1], refiner[3], refiner[4],
    ))


async def _from_detailer(detailer_pipe, **_kwargs):
    pipe = _detailer_pipe(detailer_pipe)
    return pipe[0], pipe[1], pipe[2], pipe[3], pipe[4], pipe[6], pipe[8], pipe[7], pipe[9]


async def _from_detailer_v2(detailer_pipe, **_kwargs):
    pipe = _detailer_pipe(detailer_pipe)
    return (pipe,) + await _from_detailer(pipe)


async def _from_detailer_sdxl(detailer_pipe, **_kwargs):
    pipe = _detailer_pipe(detailer_pipe)
    return (
        pipe, pipe[0], pipe[1], pipe[2], pipe[3], pipe[4], pipe[6], pipe[8],
        pipe[7], pipe[9], pipe[10], pipe[11], pipe[12], pipe[13],
    )


async def _detailer_to_basic(detailer_pipe, **_kwargs):
    pipe = _detailer_pipe(detailer_pipe)
    return tuple(pipe[:5]), (pipe[10], pipe[11], pipe[2], pipe[12], pipe[13])


async def _edit_detailer(detailer_pipe, wildcard="", **kwargs):
    values = list(_detailer_pipe(detailer_pipe))
    fields = {
        "model": 0, "clip": 1, "vae": 2, "positive": 3, "negative": 4,
        "bbox_detector": 6, "segm_detector": 7, "sam_model": 8,
        "detailer_hook": 9, "refiner_model": 10, "refiner_clip": 11,
        "refiner_positive": 12, "refiner_negative": 13,
    }
    if wildcard:
        values[5] = wildcard
    for name, index in fields.items():
        if kwargs.get(name) is not None:
            values[index] = kwargs[name]
    return _one(tuple(values))


# ---------------------------------------------------------------------------
# Tensor, list and string utilities
# ---------------------------------------------------------------------------

def _mask3(mask: torch.Tensor) -> torch.Tensor:
    mask = torch.as_tensor(mask).float()
    if mask.ndim == 2:
        mask = mask.unsqueeze(0)
    elif mask.ndim == 4:
        if mask.shape[-1] == 1:
            mask = mask[..., 0]
        elif mask.shape[1] == 1:
            mask = mask[:, 0]
        else:
            mask = mask.amax(dim=-1 if mask.shape[-1] <= 4 else 1)
    if mask.ndim != 3:
        raise ValueError("MASK must be HW, BHW, BHWC1, or B1HW")
    return mask.clamp(0.0, 1.0)


def _image4(image: torch.Tensor) -> torch.Tensor:
    image = torch.as_tensor(image).float()
    if image.ndim == 3:
        image = image.unsqueeze(0)
    if image.ndim != 4:
        raise ValueError("IMAGE must be HWC or BHWC")
    return image


def _resize_masks(mask: torch.Tensor, width: int, height: int,
                  mode: str = "bilinear") -> torch.Tensor:
    source = _mask3(mask).unsqueeze(1)
    if tuple(source.shape[-2:]) == (height, width):
        return source[:, 0]
    options = {"size": (height, width), "mode": mode}
    if mode in ("bilinear", "bicubic"):
        options["align_corners"] = False
    return torch.nn.functional.interpolate(source, **options)[:, 0]


def _resize_images(image: torch.Tensor, width: int, height: int,
                   method: str = "lanczos") -> torch.Tensor:
    image = _image4(image)
    if tuple(image.shape[1:3]) == (height, width):
        return image
    method = {
        "nearest-exact": "nearest-exact", "nearest": "nearest-exact",
        "bicubic": "bicubic", "bilinear": "bilinear", "area": "area",
        "lanczos": "lanczos",
    }.get(str(method), "bilinear")
    return common_upscale(
        image.movedim(-1, 1), int(width), int(height), method, "disabled"
    ).movedim(1, -1)


def _dilate(mask: torch.Tensor, amount: int) -> torch.Tensor:
    value = _mask3(mask)
    amount = int(amount)
    if amount == 0:
        return value
    kernel = abs(amount) * 2 + 1
    if amount > 0:
        result = torch.nn.functional.max_pool2d(
            value.unsqueeze(1), kernel, stride=1, padding=abs(amount)
        )
    else:
        result = 1.0 - torch.nn.functional.max_pool2d(
            (1.0 - value).unsqueeze(1), kernel, stride=1, padding=abs(amount)
        )
    return result[:, 0].clamp(0.0, 1.0)


def _gaussian(mask: torch.Tensor, radius: int, sigma: float | None = None) -> torch.Tensor:
    value = _mask3(mask)
    radius = max(0, int(radius))
    if radius == 0:
        return value
    sigma = max(0.1, float(sigma if sigma is not None else max(1.0, radius / 3)))
    coordinates = torch.arange(-radius, radius + 1, dtype=value.dtype, device=value.device)
    kernel = torch.exp(-(coordinates * coordinates) / (2.0 * sigma * sigma))
    kernel = kernel / kernel.sum()
    source = value.unsqueeze(1)
    source = torch.nn.functional.pad(source, (radius, radius, 0, 0), mode="replicate")
    source = torch.nn.functional.conv2d(source, kernel.reshape(1, 1, 1, -1))
    source = torch.nn.functional.pad(source, (0, 0, radius, radius), mode="replicate")
    return torch.nn.functional.conv2d(source, kernel.reshape(1, 1, -1, 1))[:, 0]


def _dynamic_switch_values(inputs=None, **kwargs):
    values = dict(inputs or {})
    values.update({
        key: value for key, value in kwargs.items() if key.startswith("input")
    })
    return values


async def _switch(select, inputs=None, **kwargs):
    index = int(select)
    name = f"input{index}"
    values = _dynamic_switch_values(inputs, **kwargs)
    label = (
        await _ctx().graph.input_label(name, name)
        if name in values else ""
    )
    return values.get(name), label, index


async def _switch_lazy(select, inputs=None, **kwargs):
    key = f"input{int(select)}"
    values = _dynamic_switch_values(inputs, **kwargs)
    return [key] if key in values and values[key] is None else []


async def _inverse_switch(select, input, **_kwargs):
    block = await _ctx().graph.block()
    selected = int(select)
    return tuple(
        input if index == selected else block
        for index in range(1, 101)
    )


async def _image_mask_switch(select, images1, mask1_opt=None, **kwargs):
    index = int(select)
    if index == 1:
        return images1, mask1_opt
    return kwargs.get(f"images{index}_opt"), kwargs.get(f"mask{index}_opt")


async def _remove_noise_mask(samples, **_kwargs):
    value = dict(await _raw(samples))
    value.pop("noise_mask", None)
    return _one(value)


async def _logger(**_kwargs):
    return ()


async def _dummy(**_kwargs):
    return _one("DUMMY")


async def _masks_to_list(masks=None, **_kwargs):
    if masks is None:
        return _one([torch.zeros((1, 64, 64), dtype=torch.float32)])
    value = _mask3(await _raw(masks))
    return _one([value[index:index + 1] for index in range(value.shape[0])])


async def _mask_list_to_batch(mask, **_kwargs):
    values = await _raw(mask)
    if not isinstance(values, list):
        values = [values]
    if not values:
        return _one(torch.zeros((1, 64, 64), dtype=torch.float32))
    masks = [_mask3(value) for value in values]
    height, width = masks[0].shape[-2:]
    masks = [_resize_masks(value, width, height) for value in masks]
    return _one(torch.cat(masks, dim=0))


async def _image_list_to_batch(images, **_kwargs):
    values = await _raw(images)
    if not isinstance(values, list):
        values = [values]
    if not values:
        raise ValueError("ImageListToImageBatch needs at least one image")
    images4 = [_image4(value) for value in values]
    height, width, channels = images4[0].shape[1:]
    result = []
    for image in images4:
        image = _resize_images(image, width, height)
        if image.shape[-1] > channels:
            image = image[..., :channels]
        elif image.shape[-1] < channels:
            padding = torch.zeros(
                (*image.shape[:-1], channels - image.shape[-1]),
                dtype=image.dtype, device=image.device,
            )
            image = torch.cat((image, padding), dim=-1)
        result.append(image)
    return _one(torch.cat(result, dim=0))


async def _image_batch_to_list(image, **_kwargs):
    value = _image4(await _raw(image))
    return _one([value[index:index + 1] for index in range(value.shape[0])])


async def _make_any_list(**kwargs):
    return _one([value for value in kwargs.values() if value is not None])


async def _make_image_list(**kwargs):
    return _one([value for value in kwargs.values() if value is not None])


async def _make_image_batch(**kwargs):
    return await _image_list_to_batch(
        [value for value in kwargs.values() if value is not None]
    )


async def _make_mask_list(**kwargs):
    return _one([value for value in kwargs.values() if value is not None])


async def _make_mask_batch(**kwargs):
    return await _mask_list_to_batch(
        [value for value in kwargs.values() if value is not None]
    )


async def _nth(any_list, index, **_kwargs):
    values = any_list if isinstance(any_list, list) else [any_list]
    if not values:
        raise ValueError("cannot select from an empty list")
    index = int(index[0] if isinstance(index, (list, tuple)) else index)
    if index >= len(values) or index < -len(values):
        index = -1
    return _one(values[index])


async def _reencode(samples, tile_mode, input_vae, output_vae,
                    tile_size=512, overlap=64, **_kwargs):
    if tile_mode in ("Both", "Decode(input) only"):
        image = await input_vae.decode_tiled(
            samples, tile_size=int(tile_size), overlap=int(overlap))
    else:
        image = await input_vae.decode(samples)
    if tile_mode in ("Both", "Encode(output) only"):
        result = await output_vae.encode_tiled(
            image, tile_x=int(tile_size), tile_y=int(tile_size), overlap=int(overlap)
        )
    else:
        result = await output_vae.encode(image)
    return _one(result)


async def _reencode_pipe(samples, tile_mode, input_basic_pipe,
                         output_basic_pipe, **_kwargs):
    input_vae = _basic_pipe(input_basic_pipe)[2]
    output_vae = _basic_pipe(output_basic_pipe)[2]
    return await _reencode(samples, tile_mode, input_vae, output_vae)


async def _string_selector(strings, multiline, select, **_kwargs):
    lines = str(strings).split("\n")
    if multiline:
        groups: list[str] = []
        current = ""
        for line in lines:
            if line.startswith("#") and current:
                groups.append(current.strip())
                current = ""
            current += line + "\n"
        if current:
            groups.append(current.strip())
        selected = groups[int(select) % len(groups)] if groups else str(strings)
        if selected.startswith("#"):
            selected = selected[1:]
    else:
        selected = lines[int(select) % len(lines)] if lines else str(strings)
    return _one(selected)


async def _string_list(join_with, string_list, **_kwargs):
    separator = join_with[0] if isinstance(join_with, list) else join_with
    if separator == "\\n":
        separator = "\n"
    values = string_list if isinstance(string_list, list) else [string_list]
    return _one(str(separator).join(str(value) for value in values))


async def _wildcard_prompt(string, delimiter, prefix_all, postfix_all,
                           restrict_to_tags, exclude_tags, **_kwargs):
    if delimiter == "\\n":
        delimiter = "\n"
    allow = {x.strip() for x in str(restrict_to_tags or "").split(",") if x.strip()}
    deny = {x.strip() for x in str(exclude_tags or "").split(",") if x.strip()}
    output = ["[LAB]"]
    labels = []
    for index, line in enumerate(str(string).split(str(delimiter)), 1):
        tags = [tag.strip() for tag in line.split(",") if tag.strip()]
        if allow:
            tags = [tag for tag in tags if tag in allow]
        tags = [tag for tag in tags if tag not in deny]
        label = str(index)
        labels.append(label)
        output.append(f"[{label}] {prefix_all or ''} {', '.join(tags)} {postfix_all or ''}".strip())
    text = "\n".join(output)
    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r" {2,}", " ", text)
    return text, ", ".join(labels)


# ---------------------------------------------------------------------------
# Mask and SEGS operations
# ---------------------------------------------------------------------------

async def _mask_binary(mask, threshold=20, **_kwargs):
    value = _mask3(await _raw(mask))
    return _one((value > float(threshold) / 255.0).float())


async def _mask_flatten(masks, **_kwargs):
    value = _mask3(await _raw(masks))
    return _one(value.amax(dim=0, keepdim=True))


async def _mask_and(mask1, mask2, **_kwargs):
    first, second = await _raw(mask1), await _raw(mask2)
    first = _mask3(first)
    second = _resize_masks(second, first.shape[-1], first.shape[-2])
    batch = max(first.shape[0], second.shape[0])
    first = first.expand(batch, -1, -1) if first.shape[0] == 1 else first
    second = second.expand(batch, -1, -1) if second.shape[0] == 1 else second
    return _one(torch.minimum(first, second))


async def _mask_subtract(mask1, mask2, **_kwargs):
    first, second = await _raw(mask1), await _raw(mask2)
    first = _mask3(first)
    second = _resize_masks(second, first.shape[-1], first.shape[-2])
    batch = max(first.shape[0], second.shape[0])
    first = first.expand(batch, -1, -1) if first.shape[0] == 1 else first
    second = second.expand(batch, -1, -1) if second.shape[0] == 1 else second
    return _one((first - second).clamp(0.0, 1.0))


async def _mask_add(mask1, mask2, **_kwargs):
    first, second = await _raw(mask1), await _raw(mask2)
    first = _mask3(first)
    second = _resize_masks(second, first.shape[-1], first.shape[-2])
    batch = max(first.shape[0], second.shape[0])
    first = first.expand(batch, -1, -1) if first.shape[0] == 1 else first
    second = second.expand(batch, -1, -1) if second.shape[0] == 1 else second
    return _one(torch.maximum(first, second))


async def _rect_mask(x, y, width, height, blur_radius,
                     image_width=512, image_height=512, percent=False,
                     **_kwargs):
    image_width = max(1, int(image_width))
    image_height = max(1, int(image_height))
    if percent:
        x = round(max(0, min(100, int(x))) * image_width / 100)
        y = round(max(0, min(100, int(y))) * image_height / 100)
        width = round(max(0, min(100, int(width))) * image_width / 100)
        height = round(max(0, min(100, int(height))) * image_height / 100)
    x, y = max(0, int(x)), max(0, int(y))
    right = min(image_width, x + max(0, int(width)))
    bottom = min(image_height, y + max(0, int(height)))
    result = torch.zeros((1, image_height, image_width), dtype=torch.float32)
    if right > x and bottom > y:
        result[:, y:bottom, x:right] = 1.0
    return _one(_gaussian(result, int(blur_radius)))


async def _rect_percent(**kwargs):
    return await _rect_mask(percent=True, **kwargs)


async def _rect_advanced(**kwargs):
    return await _rect_mask(percent=False, **kwargs)


def _components(binary: np.ndarray) -> list[
    tuple[tuple[int, int, int, int], list[tuple[int, int]]]
]:
    """Return 4-connected bounds and pixels without native detector plugins."""
    binary = np.asarray(binary, dtype=np.bool_)
    height, width = binary.shape
    seen = np.zeros_like(binary, dtype=np.bool_)
    components = []
    for y in range(height):
        for x in range(width):
            if not binary[y, x] or seen[y, x]:
                continue
            seen[y, x] = True
            stack = [(x, y)]
            pixels: list[tuple[int, int]] = []
            left = right = x
            top = bottom = y
            while stack:
                px, py = stack.pop()
                pixels.append((px, py))
                left, right = min(left, px), max(right, px)
                top, bottom = min(top, py), max(bottom, py)
                for nx, ny in ((px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1)):
                    if (
                        0 <= nx < width and 0 <= ny < height
                        and binary[ny, nx] and not seen[ny, nx]
                    ):
                        seen[ny, nx] = True
                        stack.append((nx, ny))
            components.append(((left, top, right + 1, bottom + 1), pixels))
    return components


def _expand_box(
    box: tuple[int, int, int, int], factor: float,
    width: int, height: int, minimum: int | None = None,
) -> tuple[int, int, int, int]:
    left, top, right, bottom = box
    center_x, center_y = (left + right) / 2.0, (top + bottom) / 2.0
    minimum = max(0, int(minimum or 0))
    target_width = max(
        1, minimum, round((right - left) * max(1.0, float(factor))))
    target_height = max(
        1, minimum, round((bottom - top) * max(1.0, float(factor))))
    left = max(0, round(center_x - target_width / 2))
    top = max(0, round(center_y - target_height / 2))
    right = min(width, left + target_width)
    bottom = min(height, top + target_height)
    left = max(0, right - target_width)
    top = max(0, bottom - target_height)
    return int(left), int(top), int(right), int(bottom)


def _filled_component(
    bbox: tuple[int, int, int, int], pixels: list[tuple[int, int]],
) -> torch.Tensor:
    """Fill holes enclosed by one component without importing OpenCV."""
    left, top, right, bottom = bbox
    height, width = bottom - top, right - left
    foreground = torch.zeros((height, width), dtype=torch.bool)
    for x, y in pixels:
        foreground[y - top, x - left] = True
    exterior = torch.zeros_like(foreground)
    stack = []
    for x in range(width):
        stack.extend(((x, 0), (x, height - 1)))
    for y in range(height):
        stack.extend(((0, y), (width - 1, y)))
    while stack:
        x, y = stack.pop()
        if (
            x < 0 or y < 0 or x >= width or y >= height
            or foreground[y, x] or exterior[y, x]
        ):
            continue
        exterior[y, x] = True
        stack.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
    return ~exterior


def _mask_to_segs_value(
    mask: torch.Tensor, combined: bool, crop_factor: float,
    bbox_fill: bool, drop_size: int, contour_fill: bool = True,
    label: str | None = None, crop_min_size: int | None = None,
) -> tuple[tuple[int, int], list[SEG]]:
    masks = _mask3(mask).cpu()
    height, width = masks.shape[-2:]
    union = masks.amax(dim=0) > 0.0
    components = _components(union.numpy())
    if combined and components:
        boxes = [component[0] for component in components]
        components = [((
            min(box[0] for box in boxes), min(box[1] for box in boxes),
            max(box[2] for box in boxes), max(box[3] for box in boxes),
        ), [pixel for _box, pixels in components for pixel in pixels])]
    result: list[SEG] = []
    for index, (bbox, pixels) in enumerate(components):
        if bbox[2] - bbox[0] < int(drop_size) or bbox[3] - bbox[1] < int(drop_size):
            continue
        crop = _expand_box(
            bbox, crop_factor, width, height, minimum=crop_min_size)
        left, top, right, bottom = crop
        cropped = masks[:, top:bottom, left:right].clone()
        if bbox_fill:
            bx1, by1, bx2, by2 = bbox
            cropped.zero_()
            cropped[:, by1 - top:by2 - top, bx1 - left:bx2 - left] = 1.0
        else:
            component_mask = torch.zeros(
                (bottom - top, right - left), dtype=cropped.dtype
            )
            if contour_fill and not combined:
                filled = _filled_component(bbox, pixels)
                bx1, by1, bx2, by2 = bbox
                component_mask[
                    by1 - top:by2 - top, bx1 - left:bx2 - left
                ] = filled.to(component_mask.dtype)
                cropped = component_mask.unsqueeze(0).expand_as(cropped).clone()
            else:
                for px, py in pixels:
                    component_mask[py - top, px - left] = 1.0
                cropped.mul_(component_mask.unsqueeze(0))
        result.append(SEG(
            None, cropped, 1.0, crop, tuple(int(v) for v in bbox),
            str(index + 1) if label is None else str(label), None,
        ))
    return (height, width), result


async def _mask_to_segs(
    mask, combined, crop_factor, bbox_fill, drop_size,
    contour_fill=True, **_kwargs,
):
    return _one(_mask_to_segs_value(
        await _raw(mask), bool(combined), float(crop_factor), bool(bbox_fill),
        int(drop_size), bool(contour_fill),
    ))


def _convex_hull(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    points = sorted(set(points))
    if len(points) <= 1:
        return points

    def cross(
        origin: tuple[int, int], first: tuple[int, int],
        second: tuple[int, int],
    ) -> int:
        return (
            (first[0] - origin[0]) * (second[1] - origin[1])
            - (first[1] - origin[1]) * (second[0] - origin[0])
        )

    lower: list[tuple[int, int]] = []
    for point in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper: list[tuple[int, int]] = []
    for point in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def _convex_component_mask(
    height: int, width: int, points: list[tuple[int, int]],
) -> torch.Tensor:
    hull = _convex_hull(points)
    canvas = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(canvas)
    if len(hull) >= 3:
        draw.polygon(hull, fill=255)
    elif len(hull) == 2:
        draw.line(hull, fill=255, width=1)
    elif hull:
        draw.point(hull[0], fill=255)
    return torch.from_numpy(
        np.asarray(canvas, dtype=np.float32).copy() / 255.0)


async def _mediapipe_facemesh_to_segs(
    image, crop_factor, bbox_fill, crop_min_size, drop_size, dilation,
    face, mouth, left_eyebrow, left_eye, left_pupil,
    right_eyebrow, right_eye, right_pupil, **_kwargs,
):
    pixels = _image4(await _raw(image))
    if pixels.shape[0] != 1 or pixels.shape[-1] < 3:
        raise ValueError(
            "MediaPipeFaceMeshToSEGS requires one RGB face-mesh image")
    encoded = (pixels[0, ..., :3].clamp(0.0, 1.0) * 255).to(torch.uint8)
    height, width = map(int, encoded.shape[:2])
    colors = {
        "face": (0x0A, 0xC8, 0x0A),
        "mouth": (0x0A, 0xB4, 0x0A),
        "left_eyebrow": (0xB4, 0xDC, 0x0A),
        "left_eye": (0xB4, 0xC8, 0x0A),
        "left_pupil": (0xFA, 0xC8, 0x0A),
        "right_eyebrow": (0x0A, 0xDC, 0xB4),
        "right_eye": (0x0A, 0xC8, 0xB4),
        "right_pupil": (0x0A, 0xC8, 0xFA),
    }
    enabled = {
        "face": bool(face),
        "mouth": bool(mouth),
        "left_eyebrow": bool(left_eyebrow),
        "left_eye": bool(left_eye),
        "left_pupil": bool(left_pupil),
        "right_eyebrow": bool(right_eyebrow),
        "right_eye": bool(right_eye),
        "right_pupil": bool(right_pupil),
    }
    items: list[SEG] = []
    for label, color in colors.items():
        if not enabled[label]:
            continue
        target = torch.tensor(color, dtype=torch.uint8)
        binary = torch.all(encoded.cpu() == target, dim=-1).numpy()
        for _bbox, component in _components(binary):
            mask = _convex_component_mask(height, width, component)
            mask = _dilate(mask, int(dilation))
            _header, current = _mask_to_segs_value(
                mask, False, float(crop_factor), bool(bbox_fill),
                int(drop_size), contour_fill=True, label=label,
                crop_min_size=int(crop_min_size),
            )
            items.extend(current)
    return _one(((height, width), items))


def _clipseg_recipe(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("secure_kind") != "impact.clipseg_bbox":
        raise TypeError(
            "BBOX_DETECTOR must be a Secure Nodes CLIPSeg detector recipe")
    model = value.get("model")
    if not isinstance(model, sdk.ClipSegRef):
        raise TypeError("CLIPSeg detector recipe has no opaque CLIPSeg model")
    return value


async def _clipseg_detector_mask(detector: Any, image: Any) -> torch.Tensor:
    """Reproduce the detector's text mask, blur, normalize and dilation intent."""
    recipe = _clipseg_recipe(detector)
    image_value = _image4(await _raw(image))
    if image_value.shape[0] != 1:
        raise ValueError("Impact BBOX detectors accept one image at a time")
    prediction_ref = await recipe["model"].predict_mask(
        image, recipe["text"], use_accelerator=True)
    prediction = _mask3(await _raw(prediction_ref))
    threshold = float(recipe["threshold"])
    prediction = torch.where(
        prediction > threshold, prediction, torch.zeros_like(prediction))
    blur = float(recipe["blur"])
    if blur > 0:
        prediction = _gaussian(
            prediction, max(1, math.ceil(4.0 * blur)), sigma=blur)
    minimum, maximum = prediction.amin(), prediction.amax()
    span = maximum - minimum
    if float(span) > torch.finfo(prediction.dtype).eps:
        prediction = (prediction - minimum) / span
    else:
        prediction = torch.zeros_like(prediction)
    prediction = _dilate(prediction, int(recipe["dilation_factor"]))
    prediction = _resize_masks(
        prediction,
        int(image_value.shape[2]),
        int(image_value.shape[1]),
        mode="bilinear",
    )
    return (prediction > 0.5).float().cpu()


_ULTRALYTICS_MODELS: dict[str, tuple[Any, tuple[str, ...], int]] = {}


def _is_ultralytics_detector(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("secure_kind") == "impact.ultralytics_bbox"
    )


def _ultralytics_recipe(value: Any) -> dict[str, Any]:
    if not _is_ultralytics_detector(value):
        raise TypeError(
            "BBOX_DETECTOR must be a Secure Nodes Ultralytics recipe")
    weight = value.get("weight")
    architecture = value.get("architecture")
    classes = value.get("classes")
    input_size = value.get("input_size")
    if (
        not isinstance(weight, str)
        or not weight.endswith(".safetensors")
        or ".." in PurePosixPath(weight).parts
        or architecture != "yolov8x"
        or not isinstance(classes, list)
        or not classes
        or len(classes) > 256
        or not all(isinstance(item, str) and item for item in classes)
        or isinstance(input_size, bool)
        or not isinstance(input_size, int)
        or not 64 <= input_size <= 2048
    ):
        raise ValueError("Ultralytics detector recipe is invalid")
    return value


async def _load_ultralytics_model(
    recipe: dict[str, Any],
) -> tuple[Any, tuple[str, ...], int]:
    weight = str(recipe["weight"])
    cached = _ULTRALYTICS_MODELS.get(weight)
    if cached is not None:
        return cached

    # The state dict is parsed by the host's SafeTensors reader and arrives as
    # tensors. Architecture construction and all YOLO behavior stay here in
    # the sandboxed pack runtime; repository code/config is never downloaded.
    asset = await _ctx().assets.resolve("detection", weight)
    state = await _ctx().assets.load_state_dict(asset)
    try:
        from ultralytics.nn.tasks import DetectionModel
    except ImportError as error:
        raise RuntimeError(
            "Ultralytics detector recipes require the pack's pinned "
            "ultralytics dependency"
        ) from error
    normalized = {}
    for key, tensor in state.items():
        if not isinstance(key, str) or not key.startswith("model."):
            raise ValueError(
                "Ultralytics SafeTensors keys must use the fixed model prefix")
        normalized[key.removeprefix("model.")] = tensor.detach().cpu()
    classes = tuple(str(item) for item in recipe["classes"])
    model = DetectionModel(
        "yolov8x.yaml", ch=3, nc=len(classes), verbose=False)
    model.load_state_dict(normalized, strict=True)
    model.names = {index: name for index, name in enumerate(classes)}
    model.eval().requires_grad_(False)
    result = model, classes, int(recipe["input_size"])
    _ULTRALYTICS_MODELS[weight] = result
    return result


def _letterbox(
    pixels: torch.Tensor, size: int,
) -> tuple[torch.Tensor, float, int, int]:
    height, width = map(int, pixels.shape[1:3])
    scale = min(float(size) / height, float(size) / width)
    resized_height = max(1, min(size, round(height * scale)))
    resized_width = max(1, min(size, round(width * scale)))
    source = pixels[..., :3].movedim(-1, 1).float()
    source = torch.nn.functional.interpolate(
        source, size=(resized_height, resized_width), mode="bilinear",
        align_corners=False,
    )
    pad_x = (size - resized_width) // 2
    pad_y = (size - resized_height) // 2
    padded = torch.nn.functional.pad(
        source,
        (pad_x, size - resized_width - pad_x,
         pad_y, size - resized_height - pad_y),
        value=114.0 / 255.0,
    )
    return padded, scale, pad_x, pad_y


async def _ultralytics_detect(
    detector: Any, image: Any, threshold: float, max_detections: int = 4096,
) -> list[list[dict[str, Any]]]:
    recipe = _ultralytics_recipe(detector)
    pixels = _image4(await _raw(image))
    if not 1 <= int(pixels.shape[0]) <= 64:
        raise ValueError("Ultralytics detector batch must be in [1, 64]")
    confidence = float(threshold)
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("Ultralytics threshold must be in [0, 1]")
    limit = int(max_detections)
    if not 1 <= limit <= 4096:
        raise ValueError("Ultralytics max detections must be in [1, 4096]")
    model, classes, size = await _load_ultralytics_model(recipe)
    network_input, scale, pad_x, pad_y = _letterbox(pixels, size)
    device = next(model.parameters()).device
    network_input = network_input.to(device)
    try:
        from ultralytics.utils.ops import non_max_suppression
    except ImportError as error:
        raise RuntimeError("Ultralytics NMS is unavailable") from error
    with torch.inference_mode():
        prediction = model(network_input)
        if isinstance(prediction, (tuple, list)):
            prediction = prediction[0]
        selected = non_max_suppression(
            prediction,
            conf_thres=confidence,
            iou_thres=0.7,
            max_det=limit,
            nc=len(classes),
        )
    height, width = map(int, pixels.shape[1:3])
    output: list[list[dict[str, Any]]] = []
    for batch_result in selected:
        current = []
        for row in batch_result.detach().cpu():
            left, top, right, bottom, score, class_index = row[:6].tolist()
            left = max(0.0, min(float(width), (left - pad_x) / scale))
            right = max(0.0, min(float(width), (right - pad_x) / scale))
            top = max(0.0, min(float(height), (top - pad_y) / scale))
            bottom = max(0.0, min(float(height), (bottom - pad_y) / scale))
            index = int(class_index)
            if right <= left or bottom <= top or not 0 <= index < len(classes):
                continue
            current.append({
                "label": classes[index],
                "score": float(score),
                "box": [left, top, right, bottom],
            })
        output.append(current)
    if len(output) != int(pixels.shape[0]):
        raise RuntimeError("Ultralytics detector returned the wrong batch size")
    return output


async def _onnx_detector_provider(model_name, **_kwargs):
    name = _asset_name(model_name)
    if not name.lower().endswith(".onnx"):
        raise ValueError("ONNXDetectorProvider accepts .onnx models only")
    return _one(_onnx_detector.recipe(name))


async def _onnx_detector_segs_value(
    detector: Any, image: Any, threshold: float, dilation: int,
    crop_factor: float, drop_size: int, labels: str,
) -> tuple[tuple[int, int], list[SEG]]:
    pixels = _image4(await _raw(image))
    if pixels.shape[0] != 1:
        raise ValueError("Impact ONNX detectors accept one image at a time")
    height, width = map(int, pixels.shape[1:3])
    image_ref = (
        image if isinstance(image, sdk.ImageRef)
        else await sdk.ImageRef._from_raw(pixels)
    )
    detections = await _onnx_detector.detect(_ctx(), detector, pixels)
    wanted = {part.strip() for part in str(labels).split(",") if part.strip()}
    result: list[SEG] = []
    for detection in detections:
        confidence = float(detection["score"])
        if confidence <= float(threshold):
            continue
        box = detection["box"]
        left = max(0, min(width, math.floor(float(box[0]))))
        top = max(0, min(height, math.floor(float(box[1]))))
        right = max(0, min(width, math.ceil(float(box[2]))))
        bottom = max(0, min(height, math.ceil(float(box[3]))))
        if right - left <= int(drop_size) or bottom - top <= int(drop_size):
            continue
        label = str(int(detection["label"]))
        if wanted and "all" not in wanted and label not in wanted:
            continue
        bbox = (left, top, right, bottom)
        crop = _expand_box(bbox, float(crop_factor), width, height)
        crop_left, crop_top, crop_right, crop_bottom = crop
        mask = torch.zeros((
            1, crop_bottom - crop_top, crop_right - crop_left,
        ), dtype=torch.float32)
        mask[
            :, top - crop_top:bottom - crop_top,
            left - crop_left:right - crop_left,
        ] = 1.0
        mask = _dilate(mask, int(dilation))
        result.append(SEG(
            None, mask, confidence, crop, bbox, label, None))
    return (height, width), result


async def _ultralytics_detector_segs_value(
    detector: Any, image: Any, threshold: float, dilation: int,
    crop_factor: float, drop_size: int, labels: str,
) -> tuple[tuple[int, int], list[SEG]]:
    pixels = _image4(await _raw(image))
    if pixels.shape[0] != 1:
        raise ValueError("Impact Ultralytics detectors accept one image at a time")
    height, width = map(int, pixels.shape[1:3])
    detections = (await _ultralytics_detect(
        detector, image, threshold))[0]
    wanted = {part.strip() for part in str(labels).split(",") if part.strip()}
    result: list[SEG] = []
    minimum = max(1, int(drop_size))
    for detection in detections:
        confidence = float(detection["score"])
        left_value, top_value, right_value, bottom_value = detection["box"]
        left = max(0, min(width, math.floor(float(left_value))))
        top = max(0, min(height, math.floor(float(top_value))))
        right = max(0, min(width, math.ceil(float(right_value))))
        bottom = max(0, min(height, math.ceil(float(bottom_value))))
        if right - left <= minimum or bottom - top <= minimum:
            continue
        label = str(detection["label"])
        if wanted and "all" not in wanted and label not in wanted:
            continue
        bbox = (left, top, right, bottom)
        crop = _expand_box(bbox, float(crop_factor), width, height)
        crop_left, crop_top, crop_right, crop_bottom = crop
        mask = torch.zeros((
            1, crop_bottom - crop_top, crop_right - crop_left,
        ), dtype=torch.float32)
        mask[
            :, top - crop_top:bottom - crop_top,
            left - crop_left:right - crop_left,
        ] = 1.0
        mask = _dilate(mask, int(dilation))
        result.append(SEG(
            None, mask, confidence, crop, bbox, label, None))
    return (height, width), result


async def _bbox_detector_combined(bbox_detector, image, threshold, dilation,
                                  **_kwargs):
    if _is_ultralytics_detector(bbox_detector):
        segs = await _ultralytics_detector_segs_value(
            bbox_detector, image, threshold, dilation, 1.0, 1, "all")
        return _one(_combined_mask_value(segs))
    if _onnx_detector.is_recipe(bbox_detector):
        segs = await _onnx_detector_segs_value(
            bbox_detector, image, threshold, dilation, 1.0, 1, "all")
        return _one(_combined_mask_value(segs))
    # CLIPSeg providers intentionally own threshold/dilation; the detector
    # socket values are fallbacks only for providers that leave them unset.
    del threshold, dilation
    return _one(await _clipseg_detector_mask(bbox_detector, image))


async def _bbox_detector_segs(
    bbox_detector, image, threshold, dilation, crop_factor, drop_size,
    labels="all", detailer_hook=None, **_kwargs,
):
    if _is_ultralytics_detector(bbox_detector):
        segs = await _ultralytics_detector_segs_value(
            bbox_detector, image, threshold, dilation, crop_factor,
            drop_size, labels,
        )
        return _one(await _detailer_hook_post_detection(
            segs, detailer_hook))
    if _onnx_detector.is_recipe(bbox_detector):
        segs = await _onnx_detector_segs_value(
            bbox_detector, image, threshold, dilation, crop_factor,
            drop_size, labels,
        )
        return _one(await _detailer_hook_post_detection(
            segs, detailer_hook))
    del threshold, dilation
    mask = await _clipseg_detector_mask(bbox_detector, image)
    header, items = _mask_to_segs_value(
        mask, False, float(crop_factor), True, int(drop_size))
    wanted = {part.strip() for part in str(labels).split(",") if part.strip()}
    if wanted and "all" not in wanted:
        items = [item for item in items if item.label in wanted]
    return _one(await _detailer_hook_post_detection(
        (header, items), detailer_hook))


async def _segm_detector_combined(
    segm_detector, image, threshold, dilation, **_kwargs,
):
    # A converted provider must expose a closed data recipe. The current
    # CLIPSeg provider is mask-native, so it can safely satisfy segmentation
    # consumers without invoking a detector callback object.
    del threshold, dilation
    return _one(await _clipseg_detector_mask(segm_detector, image))


async def _segm_detector_segs(
    segm_detector, image, threshold, dilation, crop_factor, drop_size,
    labels="all", detailer_hook=None, **_kwargs,
):
    del threshold, dilation
    mask = await _clipseg_detector_mask(segm_detector, image)
    header, items = _mask_to_segs_value(
        mask, False, float(crop_factor), False, int(drop_size),
        contour_fill=False,
    )
    wanted = {part.strip() for part in str(labels).split(",") if part.strip()}
    if wanted and "all" not in wanted:
        items = [item for item in items if item.label in wanted]
    return _one(await _detailer_hook_post_detection(
        (header, items), detailer_hook))


async def _refine_segs_with_detector(
    segs: Any,
    segm_detector: Any,
    image: Any,
    threshold: float,
    dilation: int,
    crop_factor: float,
    drop_size: int,
    detailer_hook: Any = None,
) -> Any:
    """Intersect bbox SEGS with a mask-native detector's result."""
    segmented = (await _segm_detector_segs(
        segm_detector=segm_detector,
        image=image,
        threshold=threshold,
        dilation=dilation,
        crop_factor=crop_factor,
        drop_size=drop_size,
        labels="all",
        detailer_hook=detailer_hook,
    ))[0]
    if (
        isinstance(segm_detector, dict)
        and bool(segm_detector.get("override_bbox_by_segm"))
    ):
        return segmented
    return (await _segs_apply_mask(
        segs, mask=_combined_mask_value(segmented)))[0]


async def _sam_loader(model_name, device_mode="AUTO", **_kwargs):
    model_name = _asset_name(model_name)
    lowered = model_name.lower()
    if not lowered.endswith((".safetensors", ".sft")):
        raise RuntimeError(
            "SAMLoader accepts SafeTensors weights only; legacy .pt/.pth "
            "checkpoints require unsafe pickle deserialization")
    stem = re.sub(r"\.(?:safetensors|sft)$", "", lowered)
    sam2_architectures = {
        "sam2_hiera_tiny", "sam2_hiera_small", "sam2_hiera_base_plus",
        "sam2_hiera_large", "sam2.1_hiera_tiny", "sam2.1_hiera_small",
        "sam2.1_hiera_base_plus", "sam2.1_hiera_large",
    }
    if stem in sam2_architectures:
        architecture = stem
    elif "sam2" in lowered:
        raise ValueError(
            "SAM2 filename must identify a supported Hiera architecture")
    elif "vit_h" in lowered:
        architecture = "vit_h"
    elif "vit_l" in lowered:
        architecture = "vit_l"
    else:
        architecture = "vit_b"
    mode = {
        "auto": "AUTO",
        "prefer gpu": "Prefer GPU",
        "cpu": "CPU",
    }.get(str(device_mode).strip().lower())
    if mode is None:
        raise ValueError("unknown SAM device mode")
    return _one(await _ctx().models.load_sam(
        model_name, architecture=architecture, device_mode=mode))


async def _sam2_video_detector_segs(
    image_frames, bbox_detector, sam2_model, bbox_threshold,
    sam2_threshold, crop_factor, drop_size, **_kwargs,
):
    if not isinstance(sam2_model, sdk.SamModelRef):
        raise TypeError("SAM_MODEL must come from the secure SAMLoader")
    frames = _image4(await _raw(image_frames)).cpu()
    if frames.shape[0] < 1:
        raise ValueError("SAM2 Video Detector needs at least one frame")
    height, width = map(int, frames.shape[1:3])

    async def detect(frame: torch.Tensor):
        frame_ref = await sdk.ImageRef._from_raw(frame.unsqueeze(0))
        result = await _bbox_detector_segs(
            bbox_detector=bbox_detector,
            image=frame_ref,
            threshold=bbox_threshold,
            dilation=0,
            crop_factor=1.0,
            drop_size=drop_size,
            labels="all",
        )
        return result[0]

    reversed_video = False
    initial = await detect(frames[0])
    if not initial[1]:
        initial = await detect(frames[-1])
        if not initial[1]:
            return _one(((height, width), []))
        reversed_video = True

    tracked_frames = torch.flip(frames, dims=(0,)) if reversed_video else frames
    tracked_ref = await sdk.ImageRef._from_raw(tracked_frames)
    boxes = [list(map(float, item.bbox)) for item in initial[1]]
    logits_ref = await sam2_model.segment_video(tracked_ref, boxes)
    logits = torch.as_tensor(await _raw(logits_ref)).float().cpu()
    expected = (len(boxes), len(frames), height, width)
    if tuple(logits.shape) != expected:
        raise RuntimeError(
            f"SAM2 returned {tuple(logits.shape)} mask logits; expected "
            f"{expected}")
    if reversed_video:
        logits = torch.flip(logits, dims=(1,))
    threshold = float(sam2_threshold)
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("sam2_threshold must be in [0, 1]")
    logit_threshold = threshold * 100.0 - 50.0
    items: list[SEG] = []
    for index, object_logits in enumerate(logits):
        temporal_masks = (object_logits >= logit_threshold).float()
        merged = temporal_masks.amax(dim=0, keepdim=True)
        _header, regions = _mask_to_segs_value(
            merged, True, float(crop_factor), False, int(drop_size),
            contour_fill=True, label=str(index + 1),
        )
        if not regions:
            continue
        region = regions[0]
        left, top, right, bottom = map(int, region.crop_region)
        items.append(region._replace(
            cropped_mask=temporal_masks[:, top:bottom, left:right].clone(),
        ))
    return _one(((height, width), items))


def _sam_points_from_mask(
    item: SEG, threshold: float, include_negative: bool,
) -> tuple[list[list[float]], list[int]]:
    left, top, _right, _bottom = map(int, item.crop_region)
    mask = _seg_mask(item).amax(dim=0)
    y_step = max(3, int(mask.shape[0] / 20))
    x_step = max(3, int(mask.shape[1] / 20))
    points = []
    labels = []
    for y in range(0, mask.shape[0], y_step):
        for x in range(0, mask.shape[1], x_step):
            value = float(mask[y, x])
            if value > threshold:
                points.append([left + x, top + y])
                labels.append(1)
            elif include_negative and value == 0.0:
                points.append([left + x, top + y])
                labels.append(0)
    return points, labels


def _sam_outer_negative_points(
    width: int, height: int, crop_region: Any,
) -> tuple[list[list[float]], list[int]]:
    left, top, right, bottom = map(int, crop_region)
    x_step = max(3, int(width / 20))
    y_step = max(3, int(height / 20))
    points = []
    for y in range(10, max(10, height - 10), y_step):
        for x in range(10, max(10, width - 10), x_step):
            if not (
                left - 10 <= x <= right + 10
                and top - 10 <= y <= bottom + 10
            ):
                points.append([x, y])
    return points, [0] * len(points)


def _sam_query_hints(
    item: SEG, detection_hint: str, bbox_expansion: int,
    mask_hint_threshold: float, mask_hint_use_negative: str,
    width: int, height: int,
) -> tuple[list[float], list[list[float]], list[int]]:
    left, top, right, bottom = map(float, item.bbox)
    center = [(left + right) / 2.0, (top + bottom) / 2.0]
    x1 = max(0.0, left - bbox_expansion)
    y1 = max(0.0, top - bbox_expansion)
    x2 = min(float(width), right + bbox_expansion)
    y2 = min(float(height), bottom + bbox_expansion)
    box = [x1, y1, x2, y2]
    points: list[list[float]] = []
    labels: list[int] = []
    if detection_hint == "center-1":
        points, labels = [center], [1]
    elif detection_hint == "horizontal-2":
        gap = (x2 - x1) / 3.0
        points, labels = [
            [x1 + gap, center[1]], [x1 + gap * 2, center[1]],
        ], [1, 1]
    elif detection_hint == "vertical-2":
        gap = (y2 - y1) / 3.0
        points, labels = [
            [center[0], y1 + gap], [center[0], y1 + gap * 2],
        ], [1, 1]
    elif detection_hint == "rect-4":
        x_gap, y_gap = (x2 - x1) / 3.0, (y2 - y1) / 3.0
        points, labels = [
            [x1 + x_gap, center[1]], [x1 + x_gap * 2, center[1]],
            [center[0], y1 + y_gap], [center[0], y1 + y_gap * 2],
        ], [1, 1, 1, 1]
    elif detection_hint == "diamond-4":
        x_gap, y_gap = (x2 - x1) / 3.0, (y2 - y1) / 3.0
        points, labels = [
            [x1 + x_gap, y1 + y_gap],
            [x1 + x_gap * 2, y1 + y_gap],
            [x1 + x_gap, y1 + y_gap * 2],
            [x1 + x_gap * 2, y1 + y_gap * 2],
        ], [1, 1, 1, 1]
    elif detection_hint == "mask-point-bbox":
        points, labels = [center], [1]
    elif detection_hint == "mask-area":
        points, labels = _sam_points_from_mask(
            item, mask_hint_threshold,
            mask_hint_use_negative == "Small")
    elif detection_hint not in {"none", "mask-points"}:
        raise ValueError(f"unknown SAM detection hint {detection_hint!r}")
    if mask_hint_use_negative in {"Outter", "Outer"}:
        negative_points, negative_labels = _sam_outer_negative_points(
            width, height, item.crop_region)
        points += negative_points
        labels += negative_labels
    return box, points, labels


async def _sam_masks(
    sam_model, segs, image, detection_hint, dilation, threshold,
    bbox_expansion, mask_hint_threshold, mask_hint_use_negative,
) -> tuple[torch.Tensor, torch.Tensor]:
    if not isinstance(sam_model, sdk.SamModelRef):
        raise TypeError("SAM_MODEL must come from the secure SAMLoader")
    image_value = _image4(await _raw(image))
    if image_value.shape[0] != 1:
        raise ValueError("SAM detectors accept one image at a time")
    height, width = int(image_value.shape[1]), int(image_value.shape[2])
    _header, items = _segs(await _raw(segs))
    if not items:
        empty = torch.zeros((1, height, width), dtype=torch.float32)
        return empty, empty
    threshold = float(threshold)
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("SAM threshold must be in [0, 1]")
    mask_hint_threshold = float(mask_hint_threshold)
    if not 0.0 <= mask_hint_threshold <= 1.0:
        raise ValueError("SAM mask hint threshold must be in [0, 1]")
    image_ref = (
        image if isinstance(image, sdk.ImageRef)
        else await sdk.ImageRef._from_raw(image_value)
    )
    if detection_hint == "mask-points":
        points = []
        labels = []
        for item in items:
            left, top, right, bottom = map(float, item.bbox)
            points.append([(left + right) / 2.0, (top + bottom) / 2.0])
            labels.append(
                0 if mask_hint_use_negative == "Small" and right - left < 10
                else 1)
        boxes = [None]
        point_coords = [points]
        point_labels = [labels]
    else:
        hints = [
            _sam_query_hints(
                item, str(detection_hint), int(bbox_expansion),
                mask_hint_threshold, str(mask_hint_use_negative), width, height)
            for item in items
        ]
        boxes = [hint[0] for hint in hints]
        point_coords = [hint[1] for hint in hints]
        point_labels = [hint[2] for hint in hints]
    masks_ref, scores = await sam_model.segment(
        image_ref,
        boxes,
        point_coords=point_coords,
        point_labels=point_labels,
        multimask_output=True,
    )
    masks = torch.as_tensor(await _raw(masks_ref)).float()
    if masks.ndim != 4 or masks.shape[:2] != (len(scores), 3):
        raise RuntimeError("SAM returned an invalid multimask tensor")
    selected = []
    for query_masks, query_scores in zip(masks, scores):
        if len(query_scores) != query_masks.shape[0]:
            raise RuntimeError("SAM returned mismatched masks and scores")
        indices = [
            index for index, score in enumerate(query_scores)
            if float(score) >= threshold
        ]
        if not indices:
            indices = [max(
                range(len(query_scores)), key=lambda index: query_scores[index]
            )]
        selected.append(query_masks[indices].amax(dim=0))
    batch = torch.stack(selected, dim=0)
    batch = _dilate(batch, int(dilation))
    combined = batch.amax(dim=0, keepdim=True)
    return combined, batch


async def _sam_detector_combined(**kwargs):
    combined, _batch = await _sam_masks(**kwargs)
    return _one(combined)


async def _sam_detector_segmented(**kwargs):
    return await _sam_masks(**kwargs)


async def _simple_detector_segs(
    bbox_detector, image, bbox_threshold, bbox_dilation, crop_factor,
    drop_size, sub_threshold, sub_dilation, sub_bbox_expansion,
    sam_mask_hint_threshold, post_dilation=0, sam_model_opt=None,
    segm_detector_opt=None, detailer_hook=None, **_kwargs,
):
    result = await _bbox_detector_segs(
        bbox_detector=bbox_detector,
        image=image,
        threshold=bbox_threshold,
        dilation=bbox_dilation,
        crop_factor=crop_factor,
        drop_size=drop_size,
        labels="all",
        detailer_hook=detailer_hook,
    )
    segs = result[0]
    if sam_model_opt is not None:
        sam_mask, _batch = await _sam_masks(
            sam_model=sam_model_opt,
            segs=segs,
            image=image,
            detection_hint="center-1",
            dilation=sub_dilation,
            threshold=sub_threshold,
            bbox_expansion=sub_bbox_expansion,
            mask_hint_threshold=sam_mask_hint_threshold,
            mask_hint_use_negative="False",
        )
        segs = (await _segs_apply_mask(segs, mask=sam_mask))[0]
    elif segm_detector_opt is not None:
        segs = await _refine_segs_with_detector(
            segs,
            segm_detector_opt,
            image,
            sub_threshold,
            sub_dilation,
            crop_factor,
            drop_size,
            detailer_hook,
        )
    if int(post_dilation) != 0:
        segs = (await _dilate_segs(segs, int(post_dilation)))[0]
    return _one(segs)


async def _simple_detector_pipe(detailer_pipe, image, **kwargs):
    pipe = _detailer_pipe(detailer_pipe)
    return await _simple_detector_segs(
        bbox_detector=pipe[6],
        image=image,
        sam_model_opt=pipe[8],
        segm_detector_opt=pipe[7],
        detailer_hook=pipe[9],
        **kwargs,
    )


async def _simple_detector_animatediff(
    bbox_detector, image_frames, bbox_threshold, bbox_dilation, crop_factor,
    drop_size, sub_threshold, sub_dilation, sub_bbox_expansion,
    sam_mask_hint_threshold, masking_mode="Pivot SEGS",
    segs_pivot="Combined mask", sam_model_opt=None,
    segm_detector_opt=None, **_kwargs,
):
    if masking_mode not in {
        "Pivot SEGS", "Combine neighboring frames", "Don't combine",
    }:
        raise ValueError("unknown Simple Detector for Video masking mode")
    if segs_pivot not in {"Combined mask", "1st frame mask"}:
        raise ValueError("unknown Simple Detector for Video pivot mode")

    frames = _image4(await _raw(image_frames))
    if frames.shape[0] == 0:
        raise ValueError("Simple Detector for Video needs at least one frame")
    height, width = int(frames.shape[1]), int(frames.shape[2])
    frame_segs = []
    frame_masks = []
    for frame in frames:
        frame_ref = await sdk.ImageRef._from_raw(frame.unsqueeze(0))
        segs = (await _bbox_detector_segs(
            bbox_detector=bbox_detector,
            image=frame_ref,
            threshold=bbox_threshold,
            dilation=bbox_dilation,
            crop_factor=crop_factor,
            drop_size=drop_size,
            labels="all",
        ))[0]
        if sam_model_opt is not None:
            sam_mask, _batch = await _sam_masks(
                sam_model=sam_model_opt,
                segs=segs,
                image=frame_ref,
                detection_hint="center-1",
                dilation=sub_dilation,
                threshold=sub_threshold,
                bbox_expansion=sub_bbox_expansion,
                mask_hint_threshold=sam_mask_hint_threshold,
                mask_hint_use_negative="False",
            )
            segs = (await _segs_apply_mask(segs, mask=sam_mask))[0]
        elif segm_detector_opt is not None:
            segs = await _refine_segs_with_detector(
                segs,
                segm_detector_opt,
                frame_ref,
                sub_threshold,
                sub_dilation,
                crop_factor,
                drop_size,
            )
        frame_segs.append(segs)
        frame_masks.append(_combined_mask_value(segs).amax(dim=0))

    if segs_pivot == "1st frame mask":
        pivot = frame_segs[0]
    else:
        merged = torch.stack(frame_masks, dim=0).amax(dim=0, keepdim=True)
        pivot = _mask_to_segs_value(
            merged, False, float(crop_factor), False, int(drop_size))
    if masking_mode == "Pivot SEGS":
        return _one(pivot)

    masks = frame_masks
    if masking_mode == "Combine neighboring frames":
        masks = [
            torch.stack([
                frame_masks[max(0, index - 1)],
                frame_masks[index],
                frame_masks[min(len(frame_masks) - 1, index + 1)],
            ]).amax(dim=0)
            for index in range(len(frame_masks))
        ]

    result = []
    for item in pivot[1]:
        left, top, right, bottom = map(int, item.crop_region)
        left, top = max(0, left), max(0, top)
        right, bottom = min(width, right), min(height, bottom)
        if right <= left or bottom <= top:
            continue
        pivot_mask = _resize_masks(
            _seg_mask(item).amax(dim=0, keepdim=True),
            right - left,
            bottom - top,
        )[0]
        batch_mask = torch.stack([
            mask[top:bottom, left:right] * pivot_mask
            for mask in masks
        ], dim=0)
        result.append(item._replace(cropped_mask=batch_mask))
    return _one(((height, width), result))


_SYMBOLIC_CLASSIFIER_LABELS = {
    "#Female": {"female", "Female", "Human Female", "woman", "women", "girl"},
    "#Male": {"male", "Male", "Human Male", "man", "men", "boy"},
}


def _classifier_recipe(value: Any) -> dict[str, Any]:
    return _image_classifier.validated(value)


def _classified_score(scores: list[dict[str, Any]], label: str):
    wanted = _SYMBOLIC_CLASSIFIER_LABELS.get(label, {label})
    for item in scores:
        if item.get("label") in wanted:
            return float(item["score"])
    return None


async def _classifier_crop(seg: SEG, reference: Any):
    if seg.cropped_image is not None:
        value = _image4(await _raw(seg.cropped_image))
        return await sdk.ImageRef._from_raw(value)
    if reference is None:
        return None
    image = _image4(await _raw(reference))
    left, top, right, bottom = (int(value) for value in seg.crop_region)
    left, top = max(0, left), max(0, top)
    right = min(int(image.shape[2]), right)
    bottom = min(int(image.shape[1]), bottom)
    if right <= left or bottom <= top:
        return None
    return await sdk.ImageRef._from_raw(image[:, top:bottom, left:right, :])


async def _segs_classify(
    classifier, segs, preset_expr, manual_expr, ref_image_opt=None, **_kwargs,
):
    recipe = _classifier_recipe(classifier)
    header, items = _segs(segs)
    expression = str(manual_expr if preset_expr == "Manual expr" else preset_expr)
    match = re.fullmatch(
        r"\s*([^><=\s]+)\s*(>=|<=|>|<|=)\s*([^><=\s]+)\s*",
        expression,
    )
    if match is None:
        return (header, []), (header, items), []
    left_operand, operator, right_operand = match.groups()

    def numeric(value: str):
        return float(value) if re.fullmatch(r"-?\d+(?:\.\d+)?", value) else None

    left_number = numeric(left_operand)
    right_number = numeric(right_operand)
    selected, remainder = [], []
    provided_labels: set[str] = set()
    comparisons = {
        ">": lambda left, right: left > right,
        "<": lambda left, right: left < right,
        ">=": lambda left, right: left >= right,
        "<=": lambda left, right: left <= right,
        "=": lambda left, right: left == right,
    }
    for item in items:
        image = await _classifier_crop(item, ref_image_opt)
        if image is None:
            remainder.append(item)
            continue
        result = await _image_classifier.classify(
            _ctx(),
            recipe,
            image,
            top_k=5,
        )
        scores = result[0]
        provided_labels.update(str(score["label"]) for score in scores)
        left = (
            left_number if left_number is not None
            else _classified_score(scores, left_operand)
        )
        right = (
            right_number if right_number is not None
            else _classified_score(scores, right_operand)
        )
        if left is None or right is None:
            remainder.append(item)
        elif comparisons[operator](float(left), float(right)):
            selected.append(item)
        else:
            remainder.append(item)
    return (
        (header, selected),
        (header, remainder),
        sorted(provided_labels),
    )


async def _empty_segs(**_kwargs):
    return _one(((0, 0), []))


def _seg_mask(seg: SEG) -> torch.Tensor:
    value = torch.as_tensor(seg.cropped_mask)
    return _mask3(value)


def _combined_mask_value(segs: Any) -> torch.Tensor:
    (height, width), items = _segs(segs)
    if height <= 0 or width <= 0:
        return torch.zeros((1, max(1, height), max(1, width)), dtype=torch.float32)
    batches = max((_seg_mask(item).shape[0] for item in items), default=1)
    output = torch.zeros((batches, height, width), dtype=torch.float32)
    for item in items:
        left, top, right, bottom = (int(x) for x in item.crop_region)
        left, top = max(0, left), max(0, top)
        right, bottom = min(width, right), min(height, bottom)
        if right <= left or bottom <= top:
            continue
        mask = _resize_masks(_seg_mask(item), right - left, bottom - top)
        if mask.shape[0] == 1 and batches > 1:
            mask = mask.expand(batches, -1, -1)
        elif mask.shape[0] != batches:
            mask = mask.amax(dim=0, keepdim=True).expand(batches, -1, -1)
        output[:, top:bottom, left:right] = torch.maximum(
            output[:, top:bottom, left:right], mask
        )
    return output


async def _segs_to_mask(segs, **_kwargs):
    return _one(_combined_mask_value(await _raw(segs)))


def _segs_mask_list_value(segs: Any) -> list[torch.Tensor]:
    header, items = _segs(segs)
    return [_combined_mask_value((header, [item])) for item in items]


async def _segs_to_mask_list(segs, **_kwargs):
    return _one(_segs_mask_list_value(await _raw(segs)))


async def _segs_to_mask_batch(segs, **_kwargs):
    masks = _segs_mask_list_value(await _raw(segs))
    if not masks:
        header = _segs(await _raw(segs))[0]
        return _one(torch.zeros((1, max(1, header[0]), max(1, header[1]))))
    flattened = [mask.amax(dim=0, keepdim=True) for mask in masks]
    return _one(torch.cat(flattened, dim=0))


async def _segs_apply_mask(segs, mask=None, masks=None, subtract=False, **_kwargs):
    raw_segs = _segs(await _raw(segs))
    full = _mask3(await _raw(mask if mask is not None else masks))
    height, width = raw_segs[0]
    full = _resize_masks(full, width, height)
    new_items: list[SEG] = []
    for item in raw_segs[1]:
        left, top, right, bottom = map(int, item.crop_region)
        selected = full[:, top:bottom, left:right]
        selected = _resize_masks(selected, right - left, bottom - top)
        source = _seg_mask(item)
        if selected.shape[0] == 1 and source.shape[0] > 1:
            selected = selected.expand(source.shape[0], -1, -1)
        if source.shape[0] == 1 and selected.shape[0] > 1:
            source = source.expand(selected.shape[0], -1, -1)
        result = (source - selected).clamp(0.0, 1.0) if subtract else torch.minimum(source, selected)
        if torch.any(result > 0):
            new_items.append(item._replace(cropped_mask=result))
    return _one((raw_segs[0], new_items))


async def _segs_and_mask(**kwargs):
    return await _segs_apply_mask(**kwargs)


async def _segs_and_segs(base_segs, mask_segs, subtract=False, **_kwargs):
    mask = _combined_mask_value(await _raw(mask_segs))
    return await _segs_apply_mask(base_segs, mask=mask, subtract=subtract)


async def _segs_subtract(base_segs, mask_segs, **kwargs):
    return await _segs_and_segs(base_segs, mask_segs, subtract=True, **kwargs)


async def _decompose(segs, **_kwargs):
    return _segs(await _raw(segs))


async def _assemble(seg_header, seg_elt, **_kwargs):
    header = seg_header[0] if isinstance(seg_header, list) and len(seg_header) == 1 else seg_header
    elements = seg_elt if isinstance(seg_elt, list) else [seg_elt]
    return _one((tuple(header), [_seg(value) for value in elements]))


async def _from_seg(seg_elt, **_kwargs):
    item = _seg(await _raw(seg_elt))
    return (
        item, item.cropped_image, item.cropped_mask, item.crop_region, item.bbox,
        item.control_net_wrapper, float(item.confidence), str(item.label),
    )


async def _from_box(bbox=None, crop_region=None, **_kwargs):
    return tuple(int(value) for value in (bbox if bbox is not None else crop_region))


async def _edit_seg(seg_elt, **kwargs):
    item = _seg(await _raw(seg_elt))
    values = item._asdict()
    mapping = {
        "cropped_image_opt": "cropped_image", "cropped_mask_opt": "cropped_mask",
        "crop_region_opt": "crop_region", "bbox_opt": "bbox",
        "control_net_wrapper_opt": "control_net_wrapper",
        "confidence_opt": "confidence", "label_opt": "label",
    }
    for source, target in mapping.items():
        if kwargs.get(source) is not None:
            values[target] = await _raw(kwargs[source])
    return _one(SEG(**values))


async def _dilate_mask(mask, dilation, **_kwargs):
    return _one(_dilate(await _raw(mask), int(dilation)))


async def _blur_mask(mask, kernel_size, sigma, **_kwargs):
    return _one(_gaussian(await _raw(mask), int(kernel_size), float(sigma)))


async def _map_seg_masks(segs, operation, **params):
    header, items = _segs(await _raw(segs))
    result = [item._replace(cropped_mask=operation(_seg_mask(item), **params)) for item in items]
    return _one((header, result))


async def _dilate_segs(segs, dilation, **_kwargs):
    return await _map_seg_masks(segs, _dilate, amount=int(dilation))


async def _blur_segs(segs, kernel_size, sigma, **_kwargs):
    return await _map_seg_masks(
        segs, _gaussian, radius=int(kernel_size), sigma=float(sigma)
    )


async def _dilate_seg(seg_elt, dilation, **_kwargs):
    item = _seg(await _raw(seg_elt))
    return _one(item._replace(cropped_mask=_dilate(_seg_mask(item), int(dilation))))


async def _scale_bbox(seg, scale_by, **_kwargs):
    item = _seg(await _raw(seg))
    left, top, right, bottom = map(int, item.bbox)
    width, height = right - left, bottom - top
    dx = round((width * float(scale_by) - width) / 2)
    dy = round((height * float(scale_by) - height) / 2)
    bbox = (left - dx, top - dy, right + dx, bottom + dy)
    crop_left, crop_top, crop_right, crop_bottom = map(int, item.crop_region)
    mask = _seg_mask(item).clone()
    x1, y1 = max(0, bbox[0] - crop_left), max(0, bbox[1] - crop_top)
    x2, y2 = min(mask.shape[-1], bbox[2] - crop_left), min(mask.shape[-2], bbox[3] - crop_top)
    clipped = torch.zeros_like(mask)
    if x2 > x1 and y2 > y1:
        clipped[:, y1:y2, x1:x2] = mask[:, y1:y2, x1:x2]
    return _one(item._replace(cropped_mask=clipped, bbox=bbox))


async def _count_segs(segs, **_kwargs):
    return _one(len(_segs(await _raw(segs))[1]))


async def _label_assign(segs, labels, **_kwargs):
    header, items = _segs(await _raw(segs))
    names = [name.strip() for name in str(labels).split(",")]
    result = [item._replace(label=names[index]) if index < len(names) else item
              for index, item in enumerate(items)]
    return _one((header, result))


async def _label_filter(segs, preset, labels, **_kwargs):
    header, items = _segs(await _raw(segs))
    wanted = {str(preset)} | {name.strip() for name in str(labels).split(",")}
    wanted.discard("")
    if "all" in wanted:
        return (header, items), (header, [])
    selected, remainder = [], []
    for item in items:
        aliases = {
            "eyes": item.label in ("left_eye", "right_eye"),
            "eyebrows": item.label in ("left_eyebrow", "right_eyebrow"),
            "pupils": item.label in ("left_pupil", "right_pupil"),
        }
        (selected if item.label in wanted or any(aliases.get(x, False) for x in wanted)
         else remainder).append(item)
    return (header, selected), (header, remainder)


def _seg_metric(item: SEG, target: str) -> float:
    left, top, right, bottom = map(float, item.crop_region)
    width, height = right - left, bottom - top
    if target == "area(=w*h)":
        return width * height
    if target == "width":
        return width
    if target == "height":
        return height
    if target == "x1":
        return left
    if target == "y1":
        return top
    if target == "x2":
        return right
    if target == "y2":
        return bottom
    if target in ("confidence", "confidence(0-100)"):
        return float(item.confidence) * (100.0 if "100" in target else 1.0)
    if target == "length_percent":
        return max(height / max(width, 1.0), width / max(height, 1.0)) * 100.0
    if target == "none":
        return 0.0
    raise ValueError(f"unknown SEGS metric {target!r}")


async def _ordered_filter(segs, target, order, take_start, take_count, **_kwargs):
    header, items = _segs(await _raw(segs))
    values = list(items)
    if target != "none":
        values.sort(key=lambda item: _seg_metric(item, target), reverse=bool(order))
    start, stop = int(take_start), int(take_start) + int(take_count)
    return (header, values[start:stop]), (header, values[:start] + values[stop:])


async def _range_filter(segs, target, mode, min_value, max_value, **_kwargs):
    header, items = _segs(await _raw(segs))
    selected, remainder = [], []
    for item in items:
        inside = float(min_value) <= _seg_metric(item, target) <= float(max_value)
        (selected if inside == bool(mode) else remainder).append(item)
    return (header, selected), (header, remainder)


def _detailer_coreml_crop_region(
    item: SEG, image_width: int, image_height: int,
    target_width: int, target_height: int,
) -> SEG:
    """Adjust one crop toward CoreML's aspect ratio without losing its bbox."""
    left, top, right, bottom = map(int, item.crop_region)
    bbox_left, bbox_top, bbox_right, bbox_bottom = map(int, item.bbox)
    left, top = max(0, left), max(0, top)
    right, bottom = min(image_width, right), min(image_height, bottom)
    crop_width, crop_height = right - left, bottom - top
    if crop_width <= 0 or crop_height <= 0:
        return item
    target_ratio = target_width / target_height
    crop_ratio = crop_width / crop_height
    new_left, new_top, new_right, new_bottom = left, top, right, bottom
    if crop_ratio < target_ratio:
        wanted = min(
            crop_height,
            max(bbox_bottom - bbox_top, round(crop_width / target_ratio)),
        )
        removable = crop_height - wanted
        top_margin = max(0, bbox_top - top)
        bottom_margin = max(0, bottom - bbox_bottom)
        margin_total = top_margin + bottom_margin
        offset = (
            round(removable * top_margin / margin_total)
            if margin_total else removable // 2
        )
        new_top = max(top, min(top + offset, bottom - wanted))
        new_bottom = new_top + wanted
    elif crop_ratio > target_ratio:
        wanted = min(
            crop_width,
            max(bbox_right - bbox_left, round(crop_height * target_ratio)),
        )
        removable = crop_width - wanted
        left_margin = max(0, bbox_left - left)
        right_margin = max(0, right - bbox_right)
        margin_total = left_margin + right_margin
        offset = (
            round(removable * left_margin / margin_total)
            if margin_total else removable // 2
        )
        new_left = max(left, min(left + offset, right - wanted))
        new_right = new_left + wanted
    new_crop = (new_left, new_top, new_right, new_bottom)
    if new_crop == (left, top, right, bottom):
        return item

    source_mask = _resize_masks(_seg_mask(item), crop_width, crop_height)
    y1, y2 = new_top - top, new_bottom - top
    x1, x2 = new_left - left, new_right - left
    cropped_mask = source_mask[:, y1:y2, x1:x2].clone()
    cropped_image = item.cropped_image
    if cropped_image is not None:
        source_image = _resize_images(
            torch.as_tensor(cropped_image), crop_width, crop_height)
        cropped_image = source_image[:, y1:y2, x1:x2].clone()
    return item._replace(
        cropped_image=cropped_image,
        cropped_mask=cropped_mask,
        crop_region=new_crop,
    )


async def _detailer_hook_post_detection(
    segs: Any, hook: Any,
) -> tuple[tuple[int, int], list[SEG]]:
    """Apply only the hook behaviors that transform a detected SEGS value."""
    current = _segs(await _raw(segs))
    recipes = _detailer_hook_recipes(hook)
    height, width = current[0]
    for recipe in recipes:
        if recipe["secure_kind"] == "CoreMLDetailerHookProvider":
            target_width, target_height = _detailer_coreml_resolution(recipe)
            current = (
                current[0],
                [
                    _detailer_coreml_crop_region(
                        item, width, height, target_width, target_height)
                    for item in current[1]
                ],
            )
    for recipe in recipes:
        kind = recipe["secure_kind"]
        params = recipe["params"]
        if kind == "SEGSOrderedFilterDetailerHookProvider":
            current = (await _ordered_filter(
                current,
                target=params.get("target", "area(=w*h)"),
                order=bool(params.get("order", True)),
                take_start=max(0, int(params.get("take_start", 0))),
                take_count=max(0, int(params.get("take_count", 1))),
            ))[0]
        elif kind == "SEGSRangeFilterDetailerHookProvider":
            current = (await _range_filter(
                current,
                target=params.get("target", "area(=w*h)"),
                mode=bool(params.get("mode", True)),
                min_value=float(params.get("min_value", 0)),
                max_value=float(params.get("max_value", 67_108_864)),
            ))[0]
        elif kind == "SEGSLabelFilterDetailerHookProvider":
            # The provider exposes both a preset and a free-form list. Treat
            # them as the intended union even though the legacy implementation
            # accidentally dropped the preset before constructing its hook.
            current = (await _label_filter(
                current,
                preset=str(params.get("preset", "")),
                labels=str(params.get("labels", "")),
            ))[0]
    return current


def _box_iou(first: tuple[int, int, int, int],
             second: tuple[int, int, int, int]) -> float:
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[2], second[2])
    bottom = min(first[3], second[3])
    intersection = max(0, right - left) * max(0, bottom - top)
    first_area = max(0, first[2] - first[0]) * max(0, first[3] - first[1])
    second_area = max(0, second[2] - second[0]) * max(0, second[3] - second[1])
    union = first_area + second_area - intersection
    return float(intersection / union) if union else 0.0


async def _nms_filter(segs, iou_threshold, **_kwargs):
    header, items = _segs(await _raw(segs))
    candidates = sorted(items, key=lambda item: float(item.confidence), reverse=True)
    kept: list[SEG] = []
    while candidates:
        current = candidates.pop(0)
        kept.append(current)
        candidates = [item for item in candidates
                      if _box_iou(tuple(current.bbox), tuple(item.bbox)) <= float(iou_threshold)]
    return _one((header, kept))


async def _intersection_filter(segs1, segs2, ioa_threshold, **_kwargs):
    header, first = _segs(await _raw(segs1))
    _, second = _segs(await _raw(segs2))
    result = []
    for item in first:
        area = max(1, (item.bbox[2] - item.bbox[0]) * (item.bbox[3] - item.bbox[1]))
        remove = False
        for other in second:
            left, top = max(item.bbox[0], other.bbox[0]), max(item.bbox[1], other.bbox[1])
            right, bottom = min(item.bbox[2], other.bbox[2]), min(item.bbox[3], other.bbox[3])
            intersection = max(0, right - left) * max(0, bottom - top)
            if intersection / area > float(ioa_threshold):
                remove = True
                break
        if not remove:
            result.append(item)
    return _one((header, result))


async def _concat_segs(**kwargs):
    header = None
    result: list[SEG] = []
    for value in kwargs.values():
        if value is None:
            continue
        current_header, items = _segs(await _raw(value))
        if current_header == (0, 0) or not items:
            continue
        if header is None:
            header = current_header
        if current_header == header:
            result.extend(items)
    return _one((header or (0, 0), result))


async def _merge_segs(segs, **_kwargs):
    header, items = _segs(await _raw(segs))
    if len(items) <= 1:
        return _one((header, items))
    mask = _combined_mask_value((header, items))
    return _one(_mask_to_segs_value(mask, True, 1.0, False, 1))


def _parse_picks(text: str, length: int) -> list[int]:
    result: list[int] = []
    for token in re.split(r"[\s,]+", str(text).strip()):
        if not token:
            continue
        match = re.fullmatch(r"(-?\d+)(?:-(-?\d+))?", token)
        if not match:
            continue
        start = int(match.group(1))
        stop = int(match.group(2)) if match.group(2) is not None else start
        step = 1 if stop >= start else -1
        for value in range(start, stop + step, step):
            index = value - 1 if value > 0 else length + value
            if 0 <= index < length and index not in result:
                result.append(index)
    return result


async def _picker(picks, segs, **_kwargs):
    header, items = _segs(await _raw(segs))
    indices = _parse_picks(picks, len(items))
    return _one((header, [items[index] for index in indices]))


async def _remove_seg_images(segs, **_kwargs):
    header, items = _segs(await _raw(segs))
    return _one((header, [item._replace(cropped_image=None) for item in items]))


def _crop_image(image: torch.Tensor, region: tuple[int, int, int, int]) -> torch.Tensor:
    left, top, right, bottom = map(int, region)
    image = _image4(image)
    left, top = max(0, left), max(0, top)
    right, bottom = min(image.shape[2], right), min(image.shape[1], bottom)
    return image[:, top:bottom, left:right, :]


async def _default_seg_images(segs, image, override, **_kwargs):
    header, items = _segs(await _raw(segs))
    pixels = _image4(await _raw(image))
    result = []
    for item in items:
        cropped = _crop_image(pixels, item.crop_region)
        result.append(item._replace(
            cropped_image=cropped if override or item.cropped_image is None
            else item.cropped_image
        ))
    return _one((header, result))


async def _segs_to_images(segs, fallback_image_opt=None, masked=False, **_kwargs):
    header, items = _segs(await _raw(segs))
    fallback = await _raw(fallback_image_opt) if fallback_image_opt is not None else None
    result: list[torch.Tensor] = []
    for item in items:
        image = item.cropped_image
        if image is None and fallback is not None:
            image = _crop_image(fallback, item.crop_region)
        if image is None:
            continue
        image = _image4(torch.as_tensor(image)).clone()
        if masked:
            mask = _resize_masks(_seg_mask(item), image.shape[2], image.shape[1])
            if mask.shape[0] == 1 and image.shape[0] > 1:
                mask = mask.expand(image.shape[0], -1, -1)
            image = image * mask[..., None]
        result.append(image)
    return _one(result)


async def _segs_preview(segs, alpha_mode=True, fallback_image_opt=None, **_kwargs):
    return await _segs_to_images(
        segs, fallback_image_opt=fallback_image_opt, masked=bool(alpha_mode)
    )


async def _segs_preview_cnet(segs, **_kwargs):
    _, items = _segs(segs)
    images = []
    for item in items:
        wrapper = item.control_net_wrapper
        if (isinstance(wrapper, dict)
                and wrapper.get("secure_kind") == "impact.controlnet"):
            image = wrapper.get("control_image")
            if image is not None:
                images.append(image)
    return _one(images)


async def _paste_segs(image, segs, feather, alpha=255,
                      ref_image_opt=None, **_kwargs):
    output = _image4(await _raw(image)).clone()
    _, items = _segs(await _raw(segs))
    reference = _image4(await _raw(ref_image_opt)) if ref_image_opt is not None else None
    for item in items:
        crop = item.cropped_image
        if crop is None and reference is not None:
            crop = _crop_image(reference, item.crop_region)
        if crop is None:
            continue
        left, top, right, bottom = map(int, item.crop_region)
        left, top = max(0, left), max(0, top)
        right, bottom = min(output.shape[2], right), min(output.shape[1], bottom)
        if right <= left or bottom <= top:
            continue
        crop = _resize_images(torch.as_tensor(crop), right - left, bottom - top)
        mask = _resize_masks(_seg_mask(item), right - left, bottom - top)
        mask = _gaussian(mask, int(feather)) * (max(0, min(255, int(alpha))) / 255.0)
        batch = output.shape[0]
        if crop.shape[0] == 1 and batch > 1:
            crop = crop.expand(batch, -1, -1, -1)
        if mask.shape[0] == 1 and batch > 1:
            mask = mask.expand(batch, -1, -1)
        crop = crop[:batch, ..., :output.shape[-1]].to(output.device, output.dtype)
        mask = mask[:batch].to(output.device, output.dtype)[..., None]
        target = output[:, top:bottom, left:right, :crop.shape[-1]]
        output[:, top:bottom, left:right, :crop.shape[-1]] = target * (1.0 - mask) + crop * mask
    return _one(output)


async def _clear_control(segs, **_kwargs):
    header, items = _segs(segs)
    return _one((header, [item._replace(control_net_wrapper=None) for item in items]))


async def _ipadapter_apply_segs(
    segs, ipadapter_pipe, weight, noise, weight_type, start_at, end_at,
    unfold_batch, faceid_v2, weight_v2, context_crop_factor,
    reference_image, combine_embeds="concat", neg_image=None, **_kwargs,
):
    """Attach a data-only IP-Adapter recipe to each segment.

    Crop selection and wrapper chaining are Impact behavior and deliberately
    stay here.  The trusted plane receives only the eventual, typed request to
    apply an already-created IP-Adapter pipeline to a model.
    """
    if getattr(ipadapter_pipe, "kind", None) != "IPADAPTER_PIPE":
        raise TypeError(
            "ipadapter_pipe must come from a host IPADAPTER_PIPE provider")
    header, items = _segs(await _raw(segs))
    height, width = map(int, header)
    if height <= 0 or width <= 0:
        raise ValueError("SEGS dimensions must be positive")
    reference = _resize_images(
        _image4(await _raw(reference_image)), width, height)
    weight = float(weight)
    noise = float(noise)
    start_at = float(start_at)
    end_at = float(end_at)
    weight_v2 = float(weight_v2)
    context_crop_factor = float(context_crop_factor)
    if not all(math.isfinite(value) for value in (
        weight, noise, start_at, end_at, weight_v2, context_crop_factor,
    )):
        raise ValueError("IP-Adapter SEGS parameters must be finite")
    if not -1.0 <= weight <= 3.0:
        raise ValueError("weight must be in [-1, 3]")
    if not 0.0 <= noise <= 1.0:
        raise ValueError("noise must be in [0, 1]")
    if not 0.0 <= start_at <= end_at <= 1.0:
        raise ValueError("start_at and end_at must satisfy 0 <= start <= end <= 1")
    if not -1.0 <= weight_v2 <= 3.0:
        raise ValueError("weight_v2 must be in [-1, 3]")
    if not 1.0 <= context_crop_factor <= 100.0:
        raise ValueError("context_crop_factor must be in [1, 100]")
    if str(weight_type) not in {"original", "linear", "channel penalty"}:
        raise ValueError("unsupported IP-Adapter weight_type")
    if str(combine_embeds) not in {
        "concat", "add", "subtract", "average", "norm average",
    }:
        raise ValueError("unsupported IP-Adapter combine_embeds value")

    result = []
    for item in items:
        previous = item.control_net_wrapper
        if previous is not None and not isinstance(previous, dict):
            raise TypeError(
                "secure IP-Adapter SEGS can only chain declarative wrappers")
        context_region = _expand_box(
            tuple(int(value) for value in item.crop_region),
            context_crop_factor,
            width,
            height,
        )
        reference_crop = _crop_image(reference, context_region).clone()
        reference_ref = await sdk.ImageRef._from_raw(reference_crop)
        wrapper = {
            "secure_kind": "impact.ipadapter",
            "version": 1,
            "pipeline": ipadapter_pipe,
            "weight": weight,
            # These three fields are retained because they are part of the
            # frozen Impact socket contract.  The pinned upstream application
            # path does not consume them, so the secure conversion does not
            # invent semantics for them.
            "noise": noise,
            "unfold_batch": bool(unfold_batch),
            "faceid_v2": bool(faceid_v2),
            "weight_type": str(weight_type),
            "start_percent": start_at,
            "end_percent": end_at,
            "weight_faceidv2": weight_v2,
            "combine_embeds": str(combine_embeds),
            "reference_image": reference_ref,
            "negative_image": neg_image,
            "context_crop_region": context_region,
            "previous": previous,
        }
        result.append(item._replace(control_net_wrapper=wrapper))
    return _one((header, result))


def _controlnet_apply_segs(advanced: bool):
    async def execute(
        segs, control_net, strength, start_percent=0.0, end_percent=1.0,
        segs_preprocessor=None, control_image=None, vae=None, **_kwargs,
    ):
        header, items = _segs(segs)
        strength_value = float(strength)
        start = float(start_percent) if advanced else 0.0
        end = float(end_percent) if advanced else 1.0
        if (not math.isfinite(strength_value)
                or not 0.0 <= strength_value <= 10.0):
            raise ValueError("Impact ControlNet strength must be in [0, 10]")
        if not 0.0 <= start <= end <= 1.0:
            raise ValueError(
                "Impact ControlNet percentages must satisfy "
                "0 <= start <= end <= 1")

        full_control = None
        if control_image is not None:
            full_control = _resize_images(
                _image4(await _raw(control_image)), header[1], header[0])
        preprocessor = (
            None if segs_preprocessor is None
            else await _raw(segs_preprocessor))
        result = []
        for item in items:
            previous = item.control_net_wrapper
            if previous is not None and not isinstance(previous, dict):
                raise TypeError(
                    "secure ControlNet SEGS can only chain declarative wrappers")
            cropped_ref = None
            if full_control is not None:
                cropped = _crop_image(full_control, item.crop_region).clone()
                cropped_ref = await sdk.ImageRef._from_raw(cropped)
            wrapper = {
                "secure_kind": "impact.controlnet",
                "version": 1,
                "mode": "advanced" if advanced else "positive_only",
                "control_net": control_net,
                "strength": strength_value,
                "start_percent": start,
                "end_percent": end,
                "preprocessor": preprocessor,
                "previous": previous,
                "original_size": header,
                "crop_region": tuple(int(value) for value in item.crop_region),
                "control_image": cropped_ref,
                "vae": vae if advanced else None,
            }
            result.append(item._replace(control_net_wrapper=wrapper))
        return _one((header, result))

    return execute


async def _tile_segs(images, bbox_size, crop_factor, min_overlap,
                     filter_in_segs_opt=None, filter_out_segs_opt=None, **_kwargs):
    pixels = _image4(await _raw(images))
    height, width = pixels.shape[1:3]
    size = max(8, int(bbox_size))
    stride = max(1, size - max(0, int(min_overlap)))
    include = (_combined_mask_value(await _raw(filter_in_segs_opt)).amax(dim=0)
               if filter_in_segs_opt is not None else None)
    exclude = (_combined_mask_value(await _raw(filter_out_segs_opt)).amax(dim=0)
               if filter_out_segs_opt is not None else None)
    items: list[SEG] = []
    for top in range(0, height, stride):
        for left in range(0, width, stride):
            right, bottom = min(width, left + size), min(height, top + size)
            if include is not None and not torch.any(include[top:bottom, left:right] > 0):
                continue
            if exclude is not None and torch.any(exclude[top:bottom, left:right] > 0):
                continue
            bbox = (left, top, right, bottom)
            crop = _expand_box(bbox, crop_factor, width, height)
            mask = torch.ones((1, crop[3] - crop[1], crop[2] - crop[0]))
            items.append(SEG(None, mask, 1.0, crop, bbox, "tile", None))
            if right == width:
                break
        if bottom == height:
            break
    return _one(((height, width), items))


# ---------------------------------------------------------------------------
# Prompt, model-reference and brokered sampling operations
# ---------------------------------------------------------------------------

async def _wildcard_process(wildcard_text, populated_text, mode, seed, **_kwargs):
    source = wildcard_text if mode == "populate" else populated_text
    catalogue = await _load_wildcard_catalogue(
        _ctx(), "impact_wildcards", style="impact"
    )
    return _one(_populate_catalogue_wildcards(
        str(source), int(seed), catalogue, style="impact"
    ))


_LORA = re.compile(
    r"<lora:([^:>]+)(?::(-?\d+(?:\.\d+)?))?(?::(-?\d+(?:\.\d+)?))?>",
    re.IGNORECASE,
)


async def _wildcard_encode(model, clip, wildcard_text, populated_text,
                           mode, seed, **_kwargs):
    source = wildcard_text if mode == "populate" else populated_text
    catalogue = await _load_wildcard_catalogue(
        _ctx(), "impact_wildcards", style="impact"
    )
    text = _populate_catalogue_wildcards(
        str(source), int(seed), catalogue, style="impact"
    )
    for match in list(_LORA.finditer(text)):
        name = _asset_name(match.group(1))
        model_strength = float(match.group(2) or 1.0)
        clip_strength = float(match.group(3) or model_strength)
        asset = await _ctx().assets.resolve("loras", name)
        model, clip = await model.apply_lora(
            asset, clip, model_strength, clip_strength
        )
    text = _LORA.sub("", text).strip()
    conditioning = await clip.encode(text)
    return model, clip, conditioning, text


async def _scheduler_adapter(scheduler, extra_scheduler, **_kwargs):
    return _one(extra_scheduler if extra_scheduler != "None" else scheduler)


async def _combine_conditionings(**kwargs):
    values = [value for value in kwargs.values() if value is not None]
    if not values:
        raise ValueError("at least one conditioning is required")
    result = values[0]
    for value in values[1:]:
        result = await result.combine(value)
    return _one(result)


async def _concat_conditionings(**kwargs):
    values = [value for value in kwargs.values() if value is not None]
    if not values:
        raise ValueError("at least one conditioning is required")
    result = values[0]
    for value in values[1:]:
        result = await result.concat(value)
    return _one(result)


async def _negative_placeholder(**_kwargs):
    return _one(await sdk.CondRef.from_value([]))


# ---------------------------------------------------------------------------
# Detailer operations
# ---------------------------------------------------------------------------

_HOST_SCHEDULERS = {
    "simple", "sgm_uniform", "karras", "exponential", "ddim_uniform",
    "beta", "normal", "linear_quadratic", "kl_optimal",
}


def _sigma_schedule_recipe(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or value.get("secure_kind") != "gits_scheduler":
        raise TypeError(
            "SCHEDULER_FUNC must come from the secure GITS provider")
    params = value.get("params")
    if not isinstance(params, dict):
        raise TypeError("GITS scheduler recipe params must be a mapping")
    coefficient = float(params.get("coeff", 1.2))
    denoise = float(params.get("denoise", 1.0))
    if not 0.8 <= coefficient <= 1.5:
        raise ValueError("GITS coefficient must be in [0.8, 1.5]")
    if not 0.0 <= denoise <= 1.0:
        raise ValueError("GITS denoise must be in [0, 1]")
    return {"kind": "gits", "coeff": coefficient, "denoise": denoise}


def _empty_detail_image(channels: int = 3) -> torch.Tensor:
    return torch.zeros((1, 64, 64, channels), dtype=torch.float32)


def _scale_segs_to_image(
    segs: Any, image: torch.Tensor,
) -> tuple[tuple[int, int], list[SEG]]:
    """Scale SEGS geometry to the actual image, preserving x/y semantics."""
    (source_height, source_width), items = _segs(segs)
    image = _image4(image)
    height, width = map(int, image.shape[1:3])
    if (
        (source_height, source_width) == (height, width)
        or source_height <= 0
        or source_width <= 0
    ):
        return (source_height, source_width), items
    x_scale = width / source_width
    y_scale = height / source_height
    result = []
    for item in items:
        def scaled_box(box):
            left, top, right, bottom = map(float, box)
            return (
                max(0, min(width, round(left * x_scale))),
                max(0, min(height, round(top * y_scale))),
                max(0, min(width, round(right * x_scale))),
                max(0, min(height, round(bottom * y_scale))),
            )

        crop_region = scaled_box(item.crop_region)
        bbox = scaled_box(item.bbox)
        crop_width = max(1, crop_region[2] - crop_region[0])
        crop_height = max(1, crop_region[3] - crop_region[1])
        mask = _resize_masks(_seg_mask(item), crop_width, crop_height)
        cropped_image = item.cropped_image
        if cropped_image is not None:
            cropped_image = _resize_images(
                torch.as_tensor(cropped_image), crop_width, crop_height)
        result.append(item._replace(
            cropped_image=cropped_image,
            cropped_mask=mask,
            crop_region=crop_region,
            bbox=bbox,
        ))
    return (height, width), result


async def _crop_detail_conditioning(
    conditioning: Any,
    image: torch.Tensor,
    crop_region: tuple[int, int, int, int],
) -> Any:
    """Crop only conditioning masks; embeddings remain opaque/value-safe."""
    if conditioning is None or isinstance(conditioning, str):
        return conditioning
    value = await _raw(conditioning)
    if not isinstance(value, (tuple, list)):
        return conditioning
    image_height, image_width = map(int, _image4(image).shape[1:3])
    changed = False
    output = []
    for entry in value:
        if not isinstance(entry, (tuple, list)) or len(entry) != 2:
            output.append(entry)
            continue
        embedding, metadata = entry
        metadata = dict(metadata)
        if "mask" in metadata:
            mask = _mask3(await _raw(metadata["mask"]))
            left, top, right, bottom = map(int, crop_region)
            mask_left = round(left * mask.shape[-1] / image_width)
            mask_right = round(right * mask.shape[-1] / image_width)
            mask_top = round(top * mask.shape[-2] / image_height)
            mask_bottom = round(bottom * mask.shape[-2] / image_height)
            metadata["mask"] = mask[
                :, max(0, mask_top):max(0, mask_bottom),
                max(0, mask_left):max(0, mask_right),
            ].clone()
            changed = True
        output.append([embedding, metadata])
    return await sdk.CondRef.from_value(output) if changed else conditioning


def _detail_wildcard_records(text: str) -> list[tuple[int | None, str]]:
    pieces = re.split(r"(\[SEP(?::(?:R|\d+))?\])", text)
    records: list[tuple[int | None, str]] = [(None, pieces[0])]
    for index in range(1, len(pieces), 2):
        marker = pieces[index]
        prompt = pieces[index + 1] if index + 1 < len(pieces) else ""
        if marker == "[SEP:R]":
            marker_seed = -1
        elif marker == "[SEP]":
            marker_seed = None
        else:
            marker_seed = int(marker[5:-1])
        records.append((marker_seed, prompt))
    return records


def _detail_wildcard_plan(
    text: str | None, items: list[SEG], seed: int,
) -> tuple[list[tuple[SEG, int, str]], bool]:
    """Interpret Impact's per-SEG ordering/label prompt language as data."""
    source = str(text or "")
    concat = source.startswith("[CONCAT]")
    if concat:
        source = source[8:]
    if source.startswith("[LAB]"):
        labelled = {
            key: value.strip()
            for key, value in re.findall(
                r"\[([A-Za-z0-9_. ]+)\]([^\[]+)(?=\[|$)", source)
            if value.strip()
        }
        plan = []
        for index, item in enumerate(items):
            prompt = labelled.get("ALL", "") + labelled.get(str(item.label), "")
            plan.append((item, seed + index, prompt))
        return plan, concat

    match = re.match(r"\[(ASC-SIZE|DSC-SIZE|ASC|DSC|RND)\]", source)
    mode = match.group(1) if match else None
    if match:
        source = source[len(match.group(0)):]
    ordered = list(items)
    if mode == "ASC":
        ordered.sort(key=lambda item: (item.bbox[0], item.bbox[1]))
    elif mode == "DSC":
        ordered.sort(key=lambda item: (item.bbox[0], item.bbox[1]), reverse=True)
    elif mode == "ASC-SIZE":
        ordered.sort(key=lambda item: (
            (item.bbox[2] - item.bbox[0])
            * (item.bbox[3] - item.bbox[1])))
    elif mode == "DSC-SIZE":
        ordered.sort(key=lambda item: (
            (item.bbox[2] - item.bbox[0])
            * (item.bbox[3] - item.bbox[1])), reverse=True)
    elif mode == "RND":
        random.Random(seed).shuffle(ordered)

    records = _detail_wildcard_records(source)
    if mode == "RND":
        random.Random(seed ^ 0x49D15).shuffle(records)
    plan = []
    for index, item in enumerate(ordered):
        record_seed, prompt = records[index % len(records)]
        if record_seed == -1:
            record_seed = random.Random(seed + index).randrange(1 << 50)
        plan.append((
            item,
            seed + index if record_seed is None else int(record_seed),
            prompt,
        ))
    return plan, concat


async def _conditioning_with_values(
    conditioning: Any, values: dict[str, Any],
) -> Any:
    if isinstance(conditioning, str):
        raise RuntimeError(
            "inpaint-model conditioning needs concrete conditioning data")
    source = await _raw(conditioning)
    output = []
    for entry in source:
        embedding, metadata = entry
        output.append([embedding, {**dict(metadata), **values}])
    return await sdk.CondRef.from_value(output)


async def _detail_encode(
    vae: Any,
    image: torch.Tensor,
    mask: torch.Tensor | None,
    positive: Any,
    negative: Any,
    *,
    inpaint_model: bool,
    tiled_encode: bool,
) -> tuple[Any, Any, Any]:
    image = _image4(image)
    image_ref = await sdk.ImageRef._from_raw(image)
    if not inpaint_model:
        latent = (
            await vae.encode_tiled(
                image_ref, tile_x=512, tile_y=512, overlap=64)
            if tiled_encode else await vae.encode(image_ref)
        )
        if mask is not None:
            latent = await _latent_noise_mask(latent, _mask3(mask))
        return latent, positive, negative

    if mask is None:
        raise RuntimeError(
            "inpaint_model requires noise_mask so the host model receives an "
            "explicit inpaint region")
    height, width = map(int, image.shape[1:3])
    encoded_height, encoded_width = (height // 8) * 8, (width // 8) * 8
    if encoded_height <= 0 or encoded_width <= 0:
        raise ValueError("detailer crops must be at least 8x8 for inpainting")
    y_offset = (height % 8) // 2
    x_offset = (width % 8) // 2
    resized_mask = _resize_masks(mask, width, height).unsqueeze(1)
    concat_image = image[
        :, y_offset:y_offset + encoded_height,
        x_offset:x_offset + encoded_width,
    ].clone()
    concat_mask = resized_mask[
        :, :, y_offset:y_offset + encoded_height,
        x_offset:x_offset + encoded_width,
    ]
    outside = (1.0 - concat_mask.round()).movedim(1, -1)
    concat_image[..., :3] = (
        (concat_image[..., :3] - 0.5) * outside + 0.5)
    concat_ref = await sdk.ImageRef._from_raw(concat_image)
    concat_latent = (
        await vae.encode_tiled(
            concat_ref, tile_x=512, tile_y=512, overlap=64)
        if tiled_encode else await vae.encode(concat_ref)
    )
    original_latent = (
        await vae.encode_tiled(
            image_ref, tile_x=512, tile_y=512, overlap=64)
        if tiled_encode else await vae.encode(image_ref)
    )
    concat_value = await _raw(concat_latent)
    original_value = dict(await _raw(original_latent))
    original_value["noise_mask"] = concat_mask
    latent = await sdk.LatentRef.from_value(original_value)
    values = {
        "concat_latent_image": concat_value["samples"],
        "concat_mask": concat_mask,
    }
    return (
        latent,
        await _conditioning_with_values(positive, values),
        await _conditioning_with_values(negative, values),
    )


async def _detail_sample(
    latent: Any,
    *,
    model: Any,
    positive: Any,
    negative: Any,
    seed: int,
    steps: int,
    cfg: float,
    sampler_name: str,
    scheduler: str,
    denoise: float,
    cycle: int,
    refiner: tuple[Any, Any, Any] | None,
    refiner_ratio: float | None,
    detailer_hook: Any = None,
    scheduler_func_opt: Any = None,
) -> Any:
    sigma_schedule = _sigma_schedule_recipe(scheduler_func_opt)
    if sigma_schedule is None and scheduler not in _HOST_SCHEDULERS:
        raise RuntimeError(
            f"Impact scheduler {scheduler!r} needs a typed host sigma-schedule "
            "primitive; choose a native host scheduler")
    current = latent
    total_cycles = max(1, int(cycle))
    custom_sampler = _detailer_hook_custom_sampler(detailer_hook)
    for cycle_index in range(total_cycles):
        current = await _detailer_hook_cycle_latent(
            current, detailer_hook, cycle_index, total_cycles)
        cycle_denoise = _detailer_hook_denoise(
            detailer_hook, float(denoise), cycle_index, total_cycles)
        cycle_seed = int(seed) + cycle_index
        if cycle_denoise <= 0.0:
            continue
        custom_noise = await _detailer_hook_noise(
            current, detailer_hook, cycle_seed)
        if refiner is None or refiner_ratio is None:
            current = await _ctx().sample(
                latent=current,
                steps=int(steps),
                model=model,
                positive=positive,
                negative=negative,
                cfg=float(cfg),
                seed=cycle_seed,
                sampler_name=str(sampler_name),
                scheduler=str(scheduler),
                denoise=cycle_denoise,
                force_full_denoise=True,
                sampler=custom_sampler,
                noise=custom_noise,
                sigma_schedule=sigma_schedule,
            )
            continue
        ratio = float(refiner_ratio)
        if not 0.0 <= ratio <= 1.0:
            raise ValueError("refiner_ratio must be in [0, 1]")
        advanced_steps = max(
            int(steps), math.floor(int(steps) / cycle_denoise))
        start_step = advanced_steps - int(steps)
        switch_step = start_step + math.floor(int(steps) * (1.0 - ratio))
        current = await _ctx().sample(
            latent=current,
            steps=advanced_steps,
            model=model,
            positive=positive,
            negative=negative,
            cfg=float(cfg),
            seed=cycle_seed,
            sampler_name=str(sampler_name),
            scheduler=str(scheduler),
            denoise=1.0,
            start_step=start_step,
            last_step=switch_step,
            force_full_denoise=False,
            sampler=custom_sampler,
            noise=custom_noise,
            sigma_schedule=sigma_schedule,
        )
        refiner_model, refiner_positive, refiner_negative = refiner
        current = await _ctx().sample(
            latent=current,
            steps=advanced_steps,
            model=refiner_model,
            positive=refiner_positive,
            negative=refiner_negative,
            cfg=float(cfg),
            seed=cycle_seed,
            sampler_name=str(sampler_name),
            scheduler=str(scheduler),
            denoise=1.0,
            disable_noise=True,
            start_step=switch_step,
            last_step=advanced_steps,
            force_full_denoise=True,
            sampler=custom_sampler,
            sigma_schedule=sigma_schedule,
        )
    return current


def _detailer_coreml_resolution(recipe: dict[str, Any]) -> tuple[int, int]:
    mode = str(recipe["params"].get("mode", ""))
    match = re.fullmatch(r"(512|768)x(512|768)", mode)
    if match is None:
        raise ValueError("CoreML detailer mode must be a supported resolution")
    return int(match.group(1)), int(match.group(2))


def _detailer_hook_scaled_size(
    hook: Any, width: int, height: int,
) -> tuple[int, int]:
    for recipe in _detailer_hook_recipes(hook):
        if recipe["secure_kind"] == "CoreMLDetailerHookProvider":
            width, height = _detailer_coreml_resolution(recipe)
    return width, height


def _detailer_hook_denoise(
    hook: Any, denoise: float, cycle_index: int, total_cycles: int,
) -> float:
    value = float(denoise)
    for recipe in _detailer_hook_recipes(hook):
        if recipe["secure_kind"] != "DenoiseSchedulerDetailerHookProvider":
            continue
        target = float(recipe["params"].get("target_denoise", 0.3))
        if not 0.0 <= target <= 1.0:
            raise ValueError("detailer target_denoise must be in [0, 1]")
        # The detailer-specific legacy hook intentionally has no effect for a
        # one-cycle render. Across multiple cycles it linearly reaches target.
        if total_cycles > 1:
            progress = cycle_index / (total_cycles - 1)
            value += (target - value) * progress
    return value


def _detailer_hook_custom_sampler(hook: Any) -> Any:
    for recipe in _detailer_hook_recipes(hook):
        if recipe["secure_kind"] != "CustomSamplerDetailerHookProvider":
            continue
        sampler = recipe["params"].get("sampler")
        if not isinstance(sampler, sdk.SamplerRef):
            raise TypeError(
                "custom detailer sampler must be a typed SAMPLER ref")
        return sampler
    return None


async def _detailer_hook_noise(
    latent: Any, hook: Any, seed: int,
) -> Any:
    recipes = [
        recipe for recipe in _detailer_hook_recipes(hook)
        if recipe["secure_kind"] == "VariationNoiseDetailerHookProvider"
    ]
    if not recipes:
        return None
    value = dict(await _raw(latent))
    samples = torch.as_tensor(value.get("samples"))
    if samples.numel() > 128 * 1024 * 1024:
        raise ValueError("detailer custom-noise tensor is too large")

    def random_noise(noise_seed: int) -> torch.Tensor:
        generator = torch.Generator(device="cpu").manual_seed(noise_seed)
        return torch.randn(
            samples.shape,
            generator=generator,
            dtype=samples.dtype,
            device="cpu",
        )

    noise = random_noise(int(seed))
    for recipe in recipes:
        params = recipe["params"]
        strength = float(params.get("strength", 0.0))
        if not 0.0 <= strength <= 1.0:
            raise ValueError("variation-noise strength must be in [0, 1]")
        variation = random_noise(int(params.get("seed", 0)))
        scale = math.sqrt((1.0 - strength) ** 2 + strength ** 2)
        noise = (
            (1.0 - strength) * noise + strength * variation
        ) / max(scale, torch.finfo(noise.dtype).eps)
    return await sdk.TensorRef._from_raw(noise)


async def _detailer_coreml_batch(
    latent: Any, hook: Any, *, before_decode: bool,
) -> Any:
    count = sum(
        recipe["secure_kind"] == "CoreMLDetailerHookProvider"
        for recipe in _detailer_hook_recipes(hook)
    )
    if count == 0:
        return latent
    value = dict(await _raw(latent))
    samples = torch.as_tensor(value.get("samples"))
    if samples.ndim < 1 or samples.shape[0] < 1:
        raise ValueError("CoreML detailer hook needs a non-empty latent batch")
    for _ in range(count):
        samples = samples[:1] if before_decode else samples.repeat(
            (2,) + (1,) * (samples.ndim - 1))
    value["samples"] = samples
    return await sdk.LatentRef.from_value(value)


def _latent_mask_for_samples(
    mask: Any, samples: torch.Tensor,
) -> torch.Tensor:
    if samples.ndim != 4:
        raise ValueError("detailer noise injection needs a 4D latent tensor")
    value = _resize_masks(
        _mask3(torch.as_tensor(mask)), samples.shape[-1], samples.shape[-2])
    if value.shape[0] == 1 and samples.shape[0] > 1:
        value = value.expand(samples.shape[0], -1, -1)
    elif value.shape[0] != samples.shape[0]:
        raise ValueError("detailer noise mask batch does not match the latent")
    return value[:, None].expand(-1, samples.shape[1], -1, -1)


async def _detailer_hook_cycle_latent(
    latent: Any, hook: Any, cycle_index: int, total_cycles: int,
) -> Any:
    current = latent
    for recipe in _detailer_hook_recipes(hook):
        kind = recipe["secure_kind"]
        params = recipe["params"]
        if kind not in {
            "NoiseInjectionDetailerHookProvider",
            "UnsamplerDetailerHookProvider",
        }:
            continue
        from_start = "from_start" in str(
            params.get("schedule_for_cycle", "skip_start"))
        if cycle_index == 0 and not from_start:
            continue
        current_step = cycle_index if from_start else cycle_index - 1
        scheduled_steps = total_cycles if from_start else total_cycles - 1
        if scheduled_steps <= 0:
            continue
        if kind == "UnsamplerDetailerHookProvider":
            start = int(params.get("start_end_at_step", 21))
            end = int(params.get("end_end_at_step", 24))
            end_at_step = int(
                start + (end - start) * current_step / scheduled_steps)
            current = await _ctx().unsample(
                current,
                steps=int(params.get("steps", 25)),
                model=params.get("model"),
                positive=params.get("positive"),
                negative=params.get("negative"),
                cfg=float(params.get("cfg", 1.0)),
                sampler_name=str(params.get("sampler_name", "euler")),
                scheduler=str(params.get("scheduler", "normal")),
                end_at_step=end_at_step,
                normalize=str(params.get("normalize", "disable")) == "enable",
            )
            continue

        start_strength = float(params.get("start_strength", 2.0))
        end_strength = float(params.get("end_strength", 1.0))
        strength = start_strength + (
            end_strength - start_strength
        ) * current_step / scheduled_steps
        if not 0.0 <= strength <= 200.0:
            raise ValueError("detailer injected-noise strength is out of range")
        value = dict(await _raw(current))
        samples = torch.as_tensor(value.get("samples"))
        generator = torch.Generator(device="cpu").manual_seed(
            int(params.get("seed", 0)) + current_step * 2)
        noise = torch.randn(
            samples.shape, generator=generator, dtype=samples.dtype,
            device="cpu").to(samples.device)
        injected = samples + noise * strength
        if value.get("noise_mask") is not None:
            latent_mask = _latent_mask_for_samples(
                value["noise_mask"], samples).to(samples.device, samples.dtype)
            injected = latent_mask * injected + (1.0 - latent_mask) * samples
        value["samples"] = injected
        current = await sdk.LatentRef.from_value(value)
    return current


def _detailer_hook_should_retry(image: torch.Tensor, hook: Any) -> bool:
    for recipe in _detailer_hook_recipes(hook):
        if recipe["secure_kind"] != "BlackPatchRetryHookProvider":
            continue
        params = recipe["params"]
        mean_threshold = int(params.get("mean_thresh", 10))
        variance_threshold = int(params.get("var_thresh", 5))
        if not 0 <= mean_threshold <= 255 or not 0 <= variance_threshold <= 255:
            raise ValueError("black-patch retry thresholds must be in [0, 255]")
        patch = _image4(image)
        grayscale = patch[..., :3].mean(dim=-1)
        if (
            float(grayscale.mean()) <= mean_threshold / 255.0
            and float(grayscale.var()) <= variance_threshold / 255.0
        ):
            return True
    return False


def _validate_detailer_sampling_hooks(hook: Any) -> None:
    for recipe in _detailer_hook_recipes(hook):
        if recipe["secure_kind"] != "LamaRemoverDetailerHookProvider":
            continue
        params = recipe["params"]
        threshold = int(params.get("mask_threshold", 250))
        blur_radius = int(params.get("gaussblur_radius", 8))
        if not 0 <= threshold <= 255:
            raise ValueError("LaMa mask_threshold must be in [0, 255]")
        if not 0 <= blur_radius <= 20:
            raise ValueError("LaMa gaussblur_radius must be in [0, 20]")
        if type(params.get("skip_sampling", True)) is not bool:
            raise TypeError("LaMa skip_sampling must be a bool")
        if not isinstance(params.get("model"), sdk.InpaintModelRef):
            raise TypeError("LaMa detailer hook has no typed inpaint model")


def _detailer_hook_skip_sampling(hook: Any) -> bool:
    recipes = _detailer_hook_recipes(hook)
    return bool(recipes) and all(
        recipe["secure_kind"] == "LamaRemoverDetailerHookProvider"
        and recipe["params"].get("skip_sampling", True) is True
        for recipe in recipes
    )


def _lama_remover_mask(
    mask: torch.Tensor, threshold: int, blur_radius: int,
) -> torch.Tensor:
    results = []
    for item in _mask3(mask):
        array = (item.clamp(0.0, 1.0) * 255.0).to(
            torch.uint8).cpu().numpy()
        image = Image.fromarray(array, mode="L")
        image = ImageOps.invert(image)
        image = image.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        image = image.point(lambda value: 0 if value > threshold else 255)
        results.append(torch.from_numpy(np.asarray(image).copy()).float() / 255.0)
    return torch.stack(results, dim=0)


async def _detailer_hook_post_upscale(
    image: torch.Tensor, mask: torch.Tensor | None, hook: Any,
) -> torch.Tensor:
    current = _image4(image).cpu()
    for recipe in _detailer_hook_recipes(hook):
        if recipe["secure_kind"] != "LamaRemoverDetailerHookProvider":
            continue
        if mask is None:
            raise ValueError("LaMa detailer hook requires a noise mask")
        params = recipe["params"]
        model = params["model"]
        if not isinstance(model, sdk.InpaintModelRef):
            raise TypeError("LaMa detailer hook has no typed inpaint model")
        threshold = int(params.get("mask_threshold", 250))
        blur_radius = int(params.get("gaussblur_radius", 8))
        height, width = map(int, current.shape[1:3])
        padded_height = max(16, (height + 7) // 8 * 8)
        padded_width = max(16, (width + 7) // 8 * 8)
        current_mask = _resize_masks(mask, width, height).cpu()
        if len(current_mask) not in (1, len(current)):
            raise ValueError("LaMa image and mask batches must match")
        prepared = (current.clamp(0.0, 1.0) * 255.0).to(
            torch.uint8).float() / 255.0
        prepared = torch.nn.functional.pad(
            prepared,
            (0, 0, 0, padded_width - width, 0, padded_height - height),
        )
        current_mask = torch.nn.functional.pad(
            current_mask,
            (0, padded_width - width, 0, padded_height - height),
        )
        current_mask = _lama_remover_mask(
            current_mask, threshold, blur_radius)
        image_ref = await sdk.ImageRef._from_raw(prepared)
        mask_ref = await sdk.MaskRef._from_raw(current_mask)
        result_ref = None
        try:
            result_ref = await model.inpaint(image_ref, mask_ref)
            result = _image4(await _raw(result_ref)).cpu()
        finally:
            await image_ref.release()
            await mask_ref.release()
            if result_ref is not None:
                await result_ref.release()
        current = result[:, :height, :width]
        current = (current.clamp(0.0, 1.0) * 255.0).to(
            torch.uint8).float() / 255.0
    return current


async def _detailer_hook_post_paste(
    image: Any, hook: Any, value: int, total: int,
) -> None:
    for recipe in _detailer_hook_recipes(hook):
        if recipe["secure_kind"] != "PreviewDetailerHookProvider":
            continue
        quality = int(recipe["params"].get("quality", 95))
        if not 20 <= quality <= 100:
            raise ValueError("preview-hook quality must be in [20, 100]")
        # Progress previews are a fixed, brokered UI primitive. Encoding and
        # transport stay host-side; the recipe's quality remains validated for
        # workflow compatibility but cannot alter the host preview policy.
        preview = await _as_image_ref(image)
        await _ctx().progress.update(
            max(0, int(value)), max(1, int(total)), preview=preview)


def _validate_upscaler_hook(hook: Any) -> None:
    for recipe in _detailer_hook_recipes(hook):
        if recipe["secure_kind"] != "PreviewDetailerHookProvider":
            raise TypeError(
                "UPSCALER_HOOK must come from PreviewDetailerHookProvider")


def _wrapper_kind(wrapper: Any) -> str | None:
    if wrapper is None:
        return None
    if not isinstance(wrapper, dict):
        raise TypeError(
            "detailer wrappers must be declarative Secure Nodes recipes")
    kind = wrapper.get("secure_kind")
    if kind not in {"impact.ipadapter", "impact.controlnet"}:
        raise ValueError(f"unsupported detailer wrapper recipe {kind!r}")
    return str(kind)


def _wrapper_preview_images(wrapper: Any) -> list[Any]:
    kind = _wrapper_kind(wrapper)
    if kind is None:
        return []
    result = _wrapper_preview_images(wrapper.get("previous"))
    image = wrapper.get(
        "reference_image" if kind == "impact.ipadapter" else "control_image")
    if image is not None:
        result.append(image)
    return result


async def _as_image_ref(value: Any) -> Any:
    if isinstance(value, sdk.ImageRef):
        return value
    return await sdk.ImageRef._from_raw(_image4(value))


async def _apply_controlnet_wrappers(
    wrapper: Any,
    positive: Any,
    negative: Any,
    image: torch.Tensor,
    *,
    mask: torch.Tensor | None = None,
    video: bool = False,
) -> tuple[Any, Any]:
    """Apply the conditioning side of a declarative wrapper chain.

    Impact's ordinary wrapper intentionally modifies positive conditioning
    only.  Its advanced wrapper, and both wrappers in the AnimateDiff path,
    modify positive and negative.  The typed core ControlNet operation already
    supplies the primitive needed for each case; this ordering is pack logic.
    """
    kind = _wrapper_kind(wrapper)
    if kind is None:
        return positive, negative
    positive, negative = await _apply_controlnet_wrappers(
        wrapper.get("previous"), positive, negative, image,
        mask=mask, video=video)
    if kind == "impact.ipadapter":
        return positive, negative
    control_net = wrapper.get("control_net")
    if not isinstance(control_net, sdk.ControlNetRef):
        raise TypeError("Impact ControlNet recipe has no typed CONTROL_NET")
    control_image = wrapper.get("control_image")
    preprocessor = wrapper.get("preprocessor")
    if control_image is not None:
        hint = await _as_image_ref(control_image)
    elif preprocessor is None:
        hint = await _as_image_ref(image)
    elif isinstance(preprocessor, sdk.ImagePreprocessorRef):
        source = await _as_image_ref(image)
        mask_ref = (
            None if mask is None
            else await sdk.MaskRef._from_raw(_mask3(mask)))
        hint = await preprocessor.apply(source, mask_ref)
    else:
        raise TypeError(
            "SEGS preprocessor must come from a typed host provider")
    mode = wrapper.get("mode")
    if mode == "advanced":
        return await control_net.apply(
            positive,
            negative,
            hint,
            strength=wrapper["strength"],
            start_percent=wrapper["start_percent"],
            end_percent=wrapper["end_percent"],
            vae=wrapper.get("vae"),
        )
    if mode != "positive_only":
        raise ValueError(f"unsupported Impact ControlNet mode {mode!r}")
    applied_positive, applied_negative = await control_net.apply(
        positive,
        negative,
        hint,
        strength=wrapper["strength"],
        start_percent=0.0,
        end_percent=1.0,
    )
    return (
        applied_positive,
        applied_negative if video else negative,
    )


async def _apply_ipadapter_wrappers(wrapper: Any, model: Any) -> Any:
    """Apply only the model side of a declarative wrapper chain."""
    kind = _wrapper_kind(wrapper)
    if kind is None:
        return model
    model = await _apply_ipadapter_wrappers(wrapper.get("previous"), model)
    if kind == "impact.controlnet":
        return model
    pipeline = wrapper.get("pipeline")
    image = wrapper.get("reference_image")
    if getattr(pipeline, "kind", None) != "IPADAPTER_PIPE":
        raise TypeError("Impact IP-Adapter recipe has no typed pipeline")
    if not isinstance(image, sdk.ImageRef):
        image = await sdk.ImageRef._from_raw(_image4(image))
    negative = wrapper.get("negative_image")
    if negative is not None and not isinstance(negative, sdk.ImageRef):
        negative = await sdk.ImageRef._from_raw(_image4(negative))
    return await _ipadapter.apply(
        pipeline,
        model=model,
        image=image,
        negative_image=negative,
        weight=wrapper["weight"],
        weight_type=wrapper["weight_type"],
        start_percent=wrapper["start_percent"],
        end_percent=wrapper["end_percent"],
        combine_embeds=wrapper["combine_embeds"],
        weight_faceidv2=wrapper["weight_faceidv2"],
    )


async def _enhance_detail_crop(
    cropped: torch.Tensor,
    item: SEG,
    *,
    model: Any,
    vae: Any,
    positive: Any,
    negative: Any,
    guide_size: float,
    guide_size_for: bool,
    max_size: float,
    seed: int,
    steps: int,
    cfg: float,
    sampler_name: str,
    scheduler: str,
    denoise: float,
    noise_mask: torch.Tensor | None,
    force_inpaint: bool,
    cycle: int,
    inpaint_model: bool,
    tiled_encode: bool,
    tiled_decode: bool,
    refiner: tuple[Any, Any, Any] | None,
    refiner_ratio: float | None,
    detailer_hook: Any = None,
    scheduler_func_opt: Any = None,
) -> torch.Tensor | None:
    cropped = _image4(cropped)
    if isinstance(model, str) and model == "DUMMY":
        return cropped
    height, width = map(int, cropped.shape[1:3])
    left, top, right, bottom = map(float, item.bbox)
    bbox_width, bbox_height = right - left, bottom - top
    if bbox_width <= 0 or bbox_height <= 0:
        return None
    guide_size = float(guide_size)
    if (
        not force_inpaint
        and bbox_height >= guide_size
        and bbox_width >= guide_size
    ):
        return None
    scale_basis = min(bbox_width, bbox_height) if guide_size_for else min(width, height)
    scale = guide_size / scale_basis
    new_width, new_height = int(width * scale), int(height * scale)
    maximum = max(64, int(max_size))
    if new_width > maximum or new_height > maximum:
        scale *= maximum / max(new_width, new_height)
        new_width, new_height = int(width * scale), int(height * scale)
    if scale <= 1.0 or new_width <= 0 or new_height <= 0:
        if not force_inpaint:
            return None
        new_width, new_height = width, height
    new_width, new_height = _detailer_hook_scaled_size(
        detailer_hook, new_width, new_height)
    upscaled = _resize_images(cropped, new_width, new_height)
    upscaled_mask = (
        None if noise_mask is None
        else _resize_masks(noise_mask, new_width, new_height)
    )
    upscaled = await _detailer_hook_post_upscale(
        upscaled, upscaled_mask, detailer_hook)
    if _detailer_hook_skip_sampling(detailer_hook):
        return _resize_images(upscaled, width, height).cpu()
    positive, negative = await _apply_controlnet_wrappers(
        item.control_net_wrapper, positive, negative, upscaled,
        mask=upscaled_mask)
    model = await _apply_ipadapter_wrappers(
        item.control_net_wrapper, model)
    latent, sampled_positive, sampled_negative = await _detail_encode(
        vae, upscaled, upscaled_mask, positive, negative,
        inpaint_model=bool(inpaint_model), tiled_encode=bool(tiled_encode))
    latent = await _detailer_coreml_batch(
        latent, detailer_hook, before_decode=False)
    sampled = await _detail_sample(
        latent,
        model=model,
        positive=sampled_positive,
        negative=sampled_negative,
        seed=int(seed),
        steps=int(steps),
        cfg=float(cfg),
        sampler_name=str(sampler_name),
        scheduler=str(scheduler),
        denoise=float(denoise),
        cycle=int(cycle),
        refiner=refiner,
        refiner_ratio=refiner_ratio,
        detailer_hook=detailer_hook,
        scheduler_func_opt=scheduler_func_opt,
    )
    sampled = await _detailer_coreml_batch(
        sampled, detailer_hook, before_decode=True)
    try:
        decoded_ref = (
            await vae.decode_tiled(sampled, tile_size=512, overlap=64)
            if tiled_decode else await vae.decode(sampled)
        )
    except Exception:
        if tiled_decode:
            raise
        decoded_ref = await vae.decode_tiled(
            sampled, tile_size=512, overlap=64)
    decoded = torch.as_tensor(await _raw(decoded_ref)).float()
    if decoded.ndim == 5 and decoded.shape[0] == 1:
        decoded = decoded.squeeze(0)
    return _resize_images(decoded, width, height).cpu()


def _paste_detail_crop(
    image: torch.Tensor,
    crop: torch.Tensor,
    mask: torch.Tensor,
    region: tuple[int, int, int, int],
) -> None:
    left, top, right, bottom = map(int, region)
    left, top = max(0, left), max(0, top)
    right, bottom = min(image.shape[2], right), min(image.shape[1], bottom)
    if right <= left or bottom <= top:
        return
    crop = _resize_images(crop, right - left, bottom - top)
    mask = _resize_masks(mask, right - left, bottom - top)
    if crop.shape[0] == 1 and image.shape[0] > 1:
        crop = crop.expand(image.shape[0], -1, -1, -1)
    if mask.shape[0] == 1 and image.shape[0] > 1:
        mask = mask.expand(image.shape[0], -1, -1)
    channels = min(image.shape[-1], crop.shape[-1])
    alpha = mask[:image.shape[0], ..., None].to(image.device, image.dtype)
    target = image[:, top:bottom, left:right, :channels]
    source = crop[:image.shape[0], ..., :channels].to(image.device, image.dtype)
    image[:, top:bottom, left:right, :channels] = (
        target * (1.0 - alpha) + source * alpha)


async def _detail_segs_common(
    image: Any,
    segs: Any,
    *,
    model: Any,
    clip: Any,
    vae: Any,
    positive: Any,
    negative: Any,
    guide_size: float,
    guide_size_for: bool,
    max_size: float,
    seed: int,
    steps: int,
    cfg: float,
    sampler_name: str,
    scheduler: str,
    denoise: float,
    feather: int,
    noise_mask: bool,
    force_inpaint: bool,
    wildcard: str | None,
    cycle: int,
    detailer_hook: Any = None,
    inpaint_model: bool = False,
    noise_mask_feather: int = 0,
    scheduler_func_opt: Any = None,
    tiled_encode: bool = False,
    tiled_decode: bool = False,
    refiner: tuple[Any, Any, Any] | None = None,
    refiner_ratio: float | None = None,
    prefer_seg_image: bool = False,
    max_retries: int = 1,
) -> tuple[
    torch.Tensor, list[torch.Tensor], list[torch.Tensor], list[torch.Tensor],
    list[torch.Tensor], tuple[tuple[int, int], list[SEG]],
]:
    _validate_detailer_sampling_hooks(detailer_hook)
    _sigma_schedule_recipe(scheduler_func_opt)
    pixels = _image4(await _raw(image)).cpu()
    if pixels.shape[0] != 1:
        raise ValueError("Impact per-SEGS detailers accept one image at a time")
    scaled_segs = _scale_segs_to_image(await _raw(segs), pixels)
    plan, concat_wildcard = _detail_wildcard_plan(
        wildcard, scaled_segs[1], int(seed))
    output = pixels.clone()
    cropped_list: list[torch.Tensor] = []
    enhanced_list: list[torch.Tensor] = []
    enhanced_alpha_list: list[torch.Tensor] = []
    cnet_images: list[torch.Tensor] = []
    new_items: list[SEG] = []
    detail_model = model
    if (
        not (isinstance(model, str) and model == "DUMMY")
        and int(noise_mask_feather) > 0
    ):
        detail_model = await model.patch(
            "differential_diffusion", strength=1.0)

    for plan_index, (item, item_seed, item_wildcard) in enumerate(plan):
        source = (
            _image4(torch.as_tensor(item.cropped_image)).clone()
            if prefer_seg_image and item.cropped_image is not None
            else _crop_image(output, item.crop_region).clone()
        )
        source_mask = _seg_mask(item)
        if not torch.any(source_mask > 0):
            if prefer_seg_image:
                new_items.append(item)
            continue
        paste_mask = _gaussian(source_mask, int(feather))
        sample_mask = (
            _gaussian(source_mask, int(noise_mask_feather))
            if noise_mask else None)
        cropped_positive = await _crop_detail_conditioning(
            positive, pixels, item.crop_region)
        cropped_negative = await _crop_detail_conditioning(
            negative, pixels, item.crop_region)
        item_model = detail_model
        if item_wildcard.strip() == "[SKIP]":
            continue
        if item_wildcard.strip() == "[STOP]":
            break
        if item_wildcard.strip():
            item_model, _item_clip, wildcard_positive, _text = (
                await _wildcard_encode(
                    item_model, clip, item_wildcard, "", "populate", item_seed))
            cropped_positive = (
                await cropped_positive.concat(wildcard_positive)
                if concat_wildcard else wildcard_positive)
        original_crop = source.clone()
        attempts = max(1, int(max_retries))
        enhanced = None
        for retry in range(attempts):
            enhanced = await _enhance_detail_crop(
                source,
                item,
                model=item_model,
                vae=vae,
                positive=cropped_positive,
                negative=cropped_negative,
                guide_size=guide_size,
                guide_size_for=guide_size_for,
                max_size=max_size,
                seed=item_seed + retry,
                steps=steps,
                cfg=cfg,
                sampler_name=sampler_name,
                scheduler=scheduler,
                denoise=denoise,
                noise_mask=sample_mask,
                force_inpaint=force_inpaint,
                cycle=cycle,
                inpaint_model=inpaint_model,
                tiled_encode=tiled_encode,
                tiled_decode=tiled_decode,
                refiner=refiner,
                refiner_ratio=refiner_ratio,
                detailer_hook=detailer_hook,
                scheduler_func_opt=scheduler_func_opt,
            )
            if (
                enhanced is None
                or isinstance(item_model, str) and item_model == "DUMMY"
                or not _detailer_hook_should_retry(enhanced, detailer_hook)
            ):
                break
            if retry + 1 == attempts:
                raise RuntimeError("Max retries reached")
        cropped_list.append(original_crop)
        if enhanced is not None:
            cnet_images.extend(_wrapper_preview_images(
                item.control_net_wrapper))
            _paste_detail_crop(output, enhanced, paste_mask, item.crop_region)
            await _detailer_hook_post_paste(
                output, detailer_hook, plan_index + 1, len(plan))
            enhanced = _image4(enhanced).cpu()
            enhanced_list.append(enhanced)
            alpha = _resize_masks(
                paste_mask, enhanced.shape[2], enhanced.shape[1])
            if alpha.shape[0] == 1 and enhanced.shape[0] > 1:
                alpha = alpha.expand(enhanced.shape[0], -1, -1)
            enhanced_alpha_list.append(torch.cat(
                (enhanced[..., :3], alpha[..., None]), dim=-1))
            new_image = enhanced
        else:
            new_image = None
        new_items.append(item._replace(cropped_image=new_image))

    key = lambda tensor: tuple(tensor.shape)
    cropped_list.sort(key=key, reverse=True)
    enhanced_list.sort(key=key, reverse=True)
    enhanced_alpha_list.sort(key=key, reverse=True)
    return (
        output[..., :3], cropped_list, enhanced_list, enhanced_alpha_list,
        cnet_images, (scaled_segs[0], new_items),
    )


async def _detailer_for_each(**kwargs):
    # AutoRetry supplies max_retries; the ordinary node gets one attempt.
    kwargs.setdefault("max_retries", 1)
    result = await _detail_segs_common(**kwargs)
    return _one(result[0])


def _detail_refiner(
    refiner_basic_pipe_opt: Any, refiner_ratio: Any,
) -> tuple[tuple[Any, Any, Any] | None, float | None]:
    if refiner_basic_pipe_opt is None:
        return None, None
    model, _clip, _vae, positive, negative = _basic_pipe(
        refiner_basic_pipe_opt)
    return (model, positive, negative), float(refiner_ratio)


async def _detailer_pipe_node(basic_pipe, refiner_basic_pipe_opt=None,
                              refiner_ratio=None, **kwargs):
    model, clip, vae, positive, negative = _basic_pipe(basic_pipe)
    refiner, ratio = _detail_refiner(
        refiner_basic_pipe_opt, refiner_ratio)
    result = await _detail_segs_common(
        model=model, clip=clip, vae=vae, positive=positive,
        negative=negative, refiner=refiner, refiner_ratio=ratio, **kwargs)
    cnet_images = result[4] or [_empty_detail_image()]
    return result[0], result[5], basic_pipe, cnet_images


async def _detailer_debug(**kwargs):
    result = await _detail_segs_common(**kwargs)
    return (
        result[0],
        result[1] or [_empty_detail_image()],
        result[2] or [_empty_detail_image()],
        result[3] or [_empty_detail_image(4)],
        result[4] or [_empty_detail_image()],
    )


async def _detailer_debug_pipe(
    basic_pipe, refiner_basic_pipe_opt=None, refiner_ratio=None, **kwargs,
):
    model, clip, vae, positive, negative = _basic_pipe(basic_pipe)
    refiner, ratio = _detail_refiner(
        refiner_basic_pipe_opt, refiner_ratio)
    result = await _detail_segs_common(
        model=model, clip=clip, vae=vae, positive=positive,
        negative=negative, refiner=refiner, refiner_ratio=ratio, **kwargs)
    return (
        result[0], result[5], basic_pipe,
        result[1] or [_empty_detail_image()],
        result[2] or [_empty_detail_image()],
        result[3] or [_empty_detail_image(4)],
        result[4] or [_empty_detail_image()],
    )


async def _segs_detailer(
    image, segs, basic_pipe, refiner_basic_pipe_opt=None,
    refiner_ratio=None, batch_size=1, **kwargs,
):
    model, clip, vae, positive, negative = _basic_pipe(basic_pipe)
    refiner, ratio = _detail_refiner(
        refiner_basic_pipe_opt, refiner_ratio)
    header = None
    items: list[SEG] = []
    cnet_images: list[torch.Tensor] = []
    base_seed = int(kwargs.pop("seed"))
    for batch_index in range(max(1, int(batch_size))):
        result = await _detail_segs_common(
            image=image,
            segs=segs,
            model=model,
            clip=clip,
            vae=vae,
            positive=positive,
            negative=negative,
            seed=base_seed + batch_index + 1,
            feather=0,
            wildcard=None,
            refiner=refiner,
            refiner_ratio=ratio,
            prefer_seg_image=True,
            **kwargs,
        )
        header = result[5][0]
        items.extend(result[5][1])
        cnet_images.extend(result[4])
    return (
        (header or (0, 0), items),
        cnet_images or [_empty_detail_image()],
    )


async def _face_detailer_batches(
    image: Any, settings: dict[str, Any],
) -> tuple[
    torch.Tensor, list[torch.Tensor], list[torch.Tensor], torch.Tensor,
    list[torch.Tensor],
]:
    pixels = _image4(await _raw(image)).cpu()
    output_images = []
    cropped_images: list[torch.Tensor] = []
    alpha_images: list[torch.Tensor] = []
    masks = []
    cnet_images: list[torch.Tensor] = []
    for frame_index, frame in enumerate(pixels):
        frame_ref = await sdk.ImageRef._from_raw(frame.unsqueeze(0))
        detector = settings["bbox_detector"]
        if isinstance(detector, dict) and not str(detector.get("text", "")).strip():
            detector = {**detector, "text": "face"}
        detected = (await _bbox_detector_segs(
            bbox_detector=detector,
            image=frame_ref,
            threshold=settings["bbox_threshold"],
            dilation=settings["bbox_dilation"],
            crop_factor=settings["bbox_crop_factor"],
            drop_size=settings["drop_size"],
            labels="all",
            detailer_hook=settings.get("detailer_hook"),
        ))[0]
        sam_model = settings.get("sam_model_opt")
        segm_detector = settings.get("segm_detector_opt")
        if sam_model is not None:
            sam_mask, _batch = await _sam_masks(
                sam_model=sam_model,
                segs=detected,
                image=frame_ref,
                detection_hint=settings["sam_detection_hint"],
                dilation=settings["sam_dilation"],
                threshold=settings["sam_threshold"],
                bbox_expansion=settings["sam_bbox_expansion"],
                mask_hint_threshold=settings["sam_mask_hint_threshold"],
                mask_hint_use_negative=settings["sam_mask_hint_use_negative"],
            )
            detected = (await _segs_apply_mask(
                detected, mask=sam_mask))[0]
        elif segm_detector is not None:
            detected = await _refine_segs_with_detector(
                detected,
                segm_detector,
                frame_ref,
                settings["bbox_threshold"],
                settings["bbox_dilation"],
                settings["bbox_crop_factor"],
                settings["drop_size"],
            )
        detection_mask = _combined_mask_value(detected)
        result = await _detail_segs_common(
            image=frame_ref,
            segs=detected,
            model=settings["model"],
            clip=settings["clip"],
            vae=settings["vae"],
            positive=settings["positive"],
            negative=settings["negative"],
            guide_size=settings["guide_size"],
            guide_size_for=settings["guide_size_for"],
            max_size=settings["max_size"],
            seed=int(settings["seed"]) + frame_index,
            steps=settings["steps"],
            cfg=settings["cfg"],
            sampler_name=settings["sampler_name"],
            scheduler=settings["scheduler"],
            denoise=settings["denoise"],
            feather=settings["feather"],
            noise_mask=settings["noise_mask"],
            force_inpaint=settings["force_inpaint"],
            wildcard=settings.get("wildcard"),
            cycle=settings.get("cycle", 1),
            detailer_hook=settings.get("detailer_hook"),
            inpaint_model=settings.get("inpaint_model", False),
            noise_mask_feather=settings.get("noise_mask_feather", 0),
            scheduler_func_opt=settings.get("scheduler_func_opt"),
            tiled_encode=settings.get("tiled_encode", False),
            tiled_decode=settings.get("tiled_decode", False),
            refiner=settings.get("refiner"),
            refiner_ratio=settings.get("refiner_ratio"),
        )
        output_images.append(result[0])
        cropped_images.extend(result[2])
        alpha_images.extend(result[3])
        masks.append(detection_mask)
        cnet_images.extend(result[4])
    return (
        torch.cat(output_images, dim=0),
        cropped_images or [_empty_detail_image()],
        alpha_images or [_empty_detail_image(4)],
        torch.cat(masks, dim=0),
        cnet_images or [_empty_detail_image()],
    )


async def _face_detailer(image, **settings):
    result = await _face_detailer_batches(image, settings)
    detailer_pipe = (
        settings["model"], settings["clip"], settings["vae"],
        settings["positive"], settings["negative"], settings.get("wildcard"),
        settings["bbox_detector"], settings.get("segm_detector_opt"),
        settings.get("sam_model_opt"), settings.get("detailer_hook"),
        None, None, None, None,
    )
    return result[0], result[1], result[2], result[3], detailer_pipe, result[4]


async def _face_detailer_pipe(image, detailer_pipe, refiner_ratio=None,
                              **settings):
    pipe = _detailer_pipe(detailer_pipe)
    settings.update({
        "model": pipe[0],
        "clip": pipe[1],
        "vae": pipe[2],
        "positive": pipe[3],
        "negative": pipe[4],
        "wildcard": pipe[5],
        "bbox_detector": pipe[6],
        "segm_detector_opt": pipe[7],
        "sam_model_opt": pipe[8],
        "detailer_hook": pipe[9],
        "refiner_ratio": refiner_ratio,
    })
    if all(pipe[index] is not None for index in (10, 11, 12, 13)):
        settings["refiner"] = (pipe[10], pipe[12], pipe[13])
    result = await _face_detailer_batches(image, settings)
    return result[0], result[1], result[2], result[3], detailer_pipe, result[4]


async def _mask_detailer_pipe(
    image, mask, basic_pipe, guide_size, guide_size_for, max_size, mask_mode,
    seed, steps, cfg, sampler_name, scheduler, denoise, feather, crop_factor,
    drop_size, refiner_ratio, batch_size, cycle=1,
    refiner_basic_pipe_opt=None, detailer_hook=None, inpaint_model=False,
    noise_mask_feather=0, bbox_fill=False, contour_fill=True,
    scheduler_func_opt=None, **_kwargs,
):
    pixels = _image4(await _raw(image)).cpu()
    if pixels.shape[0] != 1:
        raise ValueError("MaskDetailer accepts one source image at a time")
    model, clip, vae, positive, negative = _basic_pipe(basic_pipe)
    refiner, ratio = _detail_refiner(
        refiner_basic_pipe_opt, refiner_ratio)
    if mask is None:
        segs = ((pixels.shape[1], pixels.shape[2]), [])
    else:
        mask_value = _mask3(await _raw(mask)).amax(dim=0, keepdim=True)
        mask_value = _resize_masks(
            mask_value, pixels.shape[2], pixels.shape[1])
        segs = _mask_to_segs_value(
            mask_value, False, float(crop_factor), bool(bbox_fill),
            int(drop_size), bool(contour_fill))
    outputs = []
    cropped: list[torch.Tensor] = []
    alphas: list[torch.Tensor] = []
    for batch_index in range(max(1, int(batch_size))):
        result = await _detail_segs_common(
            image=image,
            segs=segs,
            model=model,
            clip=clip,
            vae=vae,
            positive=positive,
            negative=negative,
            guide_size=guide_size,
            guide_size_for=guide_size_for,
            max_size=max_size,
            seed=int(seed) + batch_index,
            steps=steps,
            cfg=cfg,
            sampler_name=sampler_name,
            scheduler=scheduler,
            denoise=denoise,
            feather=feather,
            noise_mask=bool(mask_mode),
            force_inpaint=True,
            wildcard=None,
            cycle=cycle,
            detailer_hook=detailer_hook,
            inpaint_model=inpaint_model,
            noise_mask_feather=noise_mask_feather,
            scheduler_func_opt=scheduler_func_opt,
            refiner=refiner,
            refiner_ratio=ratio,
        )
        outputs.append(result[0])
        cropped.extend(result[2])
        alphas.extend(result[3])
    return (
        torch.cat(outputs, dim=0),
        cropped or [_empty_detail_image()],
        alphas or [_empty_detail_image(4)],
        basic_pipe,
        refiner_basic_pipe_opt,
    )


async def _upscale_detail_crop(
    cropped: torch.Tensor,
    item: SEG,
    *,
    model: Any,
    vae: Any,
    positive: Any,
    negative: Any,
    seed: int,
    steps: int,
    cfg: float,
    sampler_name: str,
    scheduler: str,
    denoise: float,
    inpaint_model: bool,
    noise_mask_feather: int,
    scheduler_func_opt: Any = None,
) -> torch.Tensor:
    cropped = _image4(cropped)
    if isinstance(model, str) and model == "DUMMY":
        return cropped
    original_height, original_width = map(int, cropped.shape[1:3])
    encoded_width = max(8, math.ceil(original_width / 8) * 8)
    encoded_height = max(8, math.ceil(original_height / 8) * 8)
    encoded = _resize_images(cropped, encoded_width, encoded_height)
    mask = _resize_masks(
        _gaussian(_seg_mask(item), int(noise_mask_feather)),
        encoded_width,
        encoded_height,
    )
    positive, negative = await _apply_controlnet_wrappers(
        item.control_net_wrapper, positive, negative, encoded, mask=mask)
    model = await _apply_ipadapter_wrappers(
        item.control_net_wrapper, model)
    latent, sampled_positive, sampled_negative = await _detail_encode(
        vae,
        encoded,
        mask,
        positive,
        negative,
        inpaint_model=bool(inpaint_model),
        tiled_encode=False,
    )
    sampled = await _detail_sample(
        latent,
        model=model,
        positive=sampled_positive,
        negative=sampled_negative,
        seed=int(seed),
        steps=int(steps),
        cfg=float(cfg),
        sampler_name=str(sampler_name),
        scheduler=str(scheduler),
        denoise=float(denoise),
        cycle=1,
        refiner=None,
        refiner_ratio=None,
        scheduler_func_opt=scheduler_func_opt,
    )
    try:
        decoded_ref = await vae.decode(sampled)
    except Exception:
        decoded_ref = await vae.decode_tiled(
            sampled, tile_size=512, overlap=64)
    decoded = _image4(await _raw(decoded_ref)).cpu()
    return _resize_images(decoded, original_width, original_height)


async def _segs_upscaler(
    image, segs, model, clip, vae, rescale_factor, resampling_method,
    supersample, rounding_modulus, seed, steps, cfg, sampler_name, scheduler,
    positive, negative, denoise, feather, inpaint_model,
    noise_mask_feather, upscale_model_opt=None, upscaler_hook_opt=None,
    scheduler_func_opt=None, **_kwargs,
):
    del clip
    _validate_upscaler_hook(upscaler_hook_opt)
    _sigma_schedule_recipe(scheduler_func_opt)
    pixels = _image4(await _raw(image)).cpu()
    source_height, source_width = map(int, pixels.shape[1:3])
    factor = float(rescale_factor)
    if not math.isfinite(factor) or not 0.01 <= factor <= 100.0:
        raise ValueError("rescale_factor must be finite and in [0.01, 100]")
    modulus = int(rounding_modulus)
    if not 8 <= modulus <= 1024:
        raise ValueError("rounding_modulus must be in [8, 1024]")
    target_width = max(modulus, math.ceil(source_width * factor / modulus) * modulus)
    target_height = max(modulus, math.ceil(source_height * factor / modulus) * modulus)
    if target_width > 16384 or target_height > 16384:
        raise ValueError("SEGSUpscaler target dimensions exceed 16384 pixels")

    enlarged = pixels
    if upscale_model_opt is not None:
        source_ref = (
            image if isinstance(image, sdk.ImageRef)
            else await sdk.ImageRef._from_raw(pixels)
        )
        enlarged = _image4(await _raw(
            await upscale_model_opt.upscale(source_ref))).cpu()
    if str(supersample).strip().lower() == "true":
        high_width = min(16384, target_width * 8)
        high_height = min(16384, target_height * 8)
        enlarged = _resize_images(
            enlarged, high_width, high_height, str(resampling_method))
    output = _resize_images(
        enlarged, target_width, target_height, str(resampling_method)).cpu()
    scaled_segs = _scale_segs_to_image(await _raw(segs), output)
    detail_model = model
    if (
        not (isinstance(model, str) and model == "DUMMY")
        and int(noise_mask_feather) > 0
    ):
        detail_model = await model.patch(
            "differential_diffusion", strength=1.0)
    for index, item in enumerate(scaled_segs[1]):
        source_mask = _seg_mask(item)
        if not torch.any(source_mask > 0):
            continue
        cropped = _crop_image(output, item.crop_region).clone()
        enhanced = await _upscale_detail_crop(
            cropped,
            item,
            model=detail_model,
            vae=vae,
            positive=positive,
            negative=negative,
            seed=int(seed) + index,
            steps=steps,
            cfg=cfg,
            sampler_name=sampler_name,
            scheduler=scheduler,
            denoise=denoise,
            inpaint_model=inpaint_model,
            noise_mask_feather=noise_mask_feather,
            scheduler_func_opt=scheduler_func_opt,
        )
        _paste_detail_crop(
            output, enhanced, _gaussian(source_mask, int(feather)),
            item.crop_region)
        await _detailer_hook_post_paste(
            output, upscaler_hook_opt, index + 1, len(scaled_segs[1]))
    return _one(output[..., :3])


async def _segs_upscaler_pipe(basic_pipe, **kwargs):
    model, clip, vae, positive, negative = _basic_pipe(basic_pipe)
    return await _segs_upscaler(
        model=model,
        clip=clip,
        vae=vae,
        positive=positive,
        negative=negative,
        **kwargs,
    )


async def _enhance_detail_video(
    cropped_frames: torch.Tensor,
    item: SEG,
    *,
    model: Any,
    vae: Any,
    positive: Any,
    negative: Any,
    guide_size: float,
    guide_size_for: bool,
    max_size: float,
    seed: int,
    steps: int,
    cfg: float,
    sampler_name: str,
    scheduler: str,
    denoise: float,
    noise_mask_feather: int,
    refiner: tuple[Any, Any, Any] | None,
    refiner_ratio: float | None,
    scheduler_func_opt: Any = None,
) -> torch.Tensor:
    frames = _image4(cropped_frames)
    if isinstance(model, str) and model == "DUMMY":
        return frames
    height, width = map(int, frames.shape[1:3])
    left, top, right, bottom = map(float, item.bbox)
    bbox_width, bbox_height = right - left, bottom - top
    if bbox_width <= 0 or bbox_height <= 0:
        return frames
    scale_basis = min(bbox_width, bbox_height) if guide_size_for else min(width, height)
    scale = float(guide_size) / scale_basis
    new_width, new_height = int(width * scale), int(height * scale)
    maximum = max(64, int(max_size))
    if new_width > maximum or new_height > maximum:
        scale *= maximum / max(new_width, new_height)
        new_width, new_height = int(width * scale), int(height * scale)
    if scale <= 1.0 or new_width <= 0 or new_height <= 0:
        new_width, new_height = width, height
    upscaled = _resize_images(frames, new_width, new_height)
    mask = _gaussian(_seg_mask(item), int(noise_mask_feather))
    mask = _resize_masks(mask, new_width, new_height)
    if mask.shape[0] > 1 and mask.shape[0] != upscaled.shape[0]:
        mask = mask.amax(dim=0, keepdim=True).expand(
            upscaled.shape[0], -1, -1).clone()
        mask = (mask > 0.1).float()
    positive, negative = await _apply_controlnet_wrappers(
        item.control_net_wrapper, positive, negative, upscaled,
        mask=mask, video=True)
    model = await _apply_ipadapter_wrappers(
        item.control_net_wrapper, model)
    image_ref = await sdk.ImageRef._from_raw(upscaled)
    latent = await vae.encode(image_ref)
    latent = await _latent_noise_mask(latent, mask)
    sampled = await _detail_sample(
        latent,
        model=model,
        positive=positive,
        negative=negative,
        seed=int(seed),
        steps=int(steps),
        cfg=float(cfg),
        sampler_name=str(sampler_name),
        scheduler=str(scheduler),
        denoise=float(denoise),
        cycle=1,
        refiner=refiner,
        refiner_ratio=refiner_ratio,
        scheduler_func_opt=scheduler_func_opt,
    )
    try:
        decoded_ref = await vae.decode(sampled)
    except Exception:
        decoded_ref = await vae.decode_tiled(
            sampled, tile_size=512, overlap=64)
    decoded = _image4(await _raw(decoded_ref)).cpu()
    return _resize_images(decoded, width, height)


async def _segs_detailer_animatediff(
    image_frames, segs, guide_size, guide_size_for, max_size, seed, steps,
    cfg, sampler_name, scheduler, denoise, basic_pipe, refiner_ratio=None,
    refiner_basic_pipe_opt=None, noise_mask_feather=0,
    scheduler_func_opt=None, **_kwargs,
):
    _sigma_schedule_recipe(scheduler_func_opt)
    frames = _image4(await _raw(image_frames)).cpu()
    scaled_segs = _scale_segs_to_image(await _raw(segs), frames)
    model, _clip, vae, positive, negative = _basic_pipe(basic_pipe)
    refiner, ratio = _detail_refiner(
        refiner_basic_pipe_opt, refiner_ratio)
    detail_model = model
    if (
        not (isinstance(model, str) and model == "DUMMY")
        and int(noise_mask_feather) > 0
    ):
        detail_model = await model.patch(
            "differential_diffusion", strength=1.0)
    result = []
    preview_images: list[Any] = []
    for item in scaled_segs[1]:
        stored = (
            None if item.cropped_image is None
            else _image4(torch.as_tensor(item.cropped_image)).cpu()
        )
        cropped = (
            stored if stored is not None and stored.shape[0] == frames.shape[0]
            else _crop_image(frames, item.crop_region).clone()
        )
        if not torch.any(_seg_mask(item) > 0):
            result.append(item)
            continue
        cropped_positive = await _crop_detail_conditioning(
            positive, frames, item.crop_region)
        cropped_negative = await _crop_detail_conditioning(
            negative, frames, item.crop_region)
        enhanced = await _enhance_detail_video(
            cropped,
            item,
            model=detail_model,
            vae=vae,
            positive=cropped_positive,
            negative=cropped_negative,
            guide_size=guide_size,
            guide_size_for=guide_size_for,
            max_size=max_size,
            seed=seed,
            steps=steps,
            cfg=cfg,
            sampler_name=sampler_name,
            scheduler=scheduler,
            denoise=denoise,
            noise_mask_feather=noise_mask_feather,
            refiner=refiner,
            refiner_ratio=ratio,
            scheduler_func_opt=scheduler_func_opt,
        )
        preview_images.extend(_wrapper_preview_images(
            item.control_net_wrapper))
        result.append(item._replace(
            cropped_image=enhanced,
            control_net_wrapper=None,
        ))
    return (
        (scaled_segs[0], result),
        preview_images or [_empty_detail_image()],
    )


async def _detailer_pipe_animatediff(
    image_frames, segs, basic_pipe, feather, detailer_hook=None,
    **kwargs,
):
    _detailer_hook_recipes(detailer_hook)
    frames = _image4(await _raw(image_frames)).cpu().clone()
    header, items = _scale_segs_to_image(await _raw(segs), frames)
    enhanced_items = []
    cnet_images: list[torch.Tensor] = []
    for item in items:
        enhanced, previews = await _segs_detailer_animatediff(
            image_frames=await sdk.ImageRef._from_raw(frames),
            segs=(header, [item]),
            basic_pipe=basic_pipe,
            **kwargs,
        )
        enhanced_item = enhanced[1][0]
        if enhanced_item.cropped_image is not None:
            _paste_detail_crop(
                frames,
                torch.as_tensor(enhanced_item.cropped_image),
                _gaussian(_seg_mask(enhanced_item), int(feather)),
                enhanced_item.crop_region,
            )
            await _detailer_hook_post_paste(
                frames, detailer_hook, len(enhanced_items) + 1, len(items))
        enhanced_items.append(enhanced_item)
        cnet_images.extend(previews)
    return frames[..., :3], (header, enhanced_items), basic_pipe, cnet_images


async def _sampler_provider(kind="ksampler", **kwargs):
    return _one({"secure_kind": kind, "params": dict(kwargs)})


def _impact_sampler_recipe(value: Any, expected: str) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("secure_kind") != expected:
        raise TypeError(
            f"sampler must come from Impact's secure {expected} provider")
    params = dict(value.get("params") or {})
    _sigma_schedule_recipe(params.get("scheduler_func_opt"))
    return params


async def _run_basic_sampler_recipe(recipe, latent):
    params = _impact_sampler_recipe(recipe, "ksampler")
    pipe = _basic_pipe(params["basic_pipe"])
    return _as_latent_ref(await _ctx().sample(
        latent=latent,
        steps=int(params["steps"]),
        model=pipe[0],
        positive=pipe[3],
        negative=pipe[4],
        cfg=float(params["cfg"]),
        seed=int(params["seed"]),
        sampler_name=str(params["sampler_name"]),
        scheduler=str(params["scheduler"]),
        denoise=float(params["denoise"]),
        force_full_denoise=True,
        sigma_schedule=_sigma_schedule_recipe(
            params.get("scheduler_func_opt")),
    ))


async def _run_advanced_sampler_recipe(
    recipe, latent, *, seed, steps, start_step, end_step,
    add_noise, leftover_noise, noise=None, recovery_mode="DISABLE",
    recovery_sampler="AUTO", recovery_sigma_ratio=1.0,
):
    params = _impact_sampler_recipe(recipe, "ksampler_advanced")
    sampler = params.get("sampler_opt")
    if sampler is not None and not isinstance(sampler, sdk.SamplerRef):
        raise TypeError("sampler_opt must be a typed SAMPLER ref")
    sigma_factor = float(params.get("sigma_factor", 1.0))
    if not 0.0 <= sigma_factor <= 10.0:
        raise ValueError("sigma_factor must be in [0, 10]")
    pipe = _basic_pipe(params["basic_pipe"])
    scheduler = str(params["scheduler"])
    sigma_schedule = _sigma_schedule_recipe(
        params.get("scheduler_func_opt"))
    if sigma_schedule is None and scheduler not in _HOST_SCHEDULERS:
        raise RuntimeError(
            f"Impact scheduler {scheduler!r} needs a typed host sigma-schedule "
            "primitive")
    mode = str(recovery_mode)
    if mode not in {"DISABLE", "ratio additional", "ratio between"}:
        raise ValueError("unknown special-sampler recovery mode")
    recovery_ratio = float(recovery_sigma_ratio)
    if not 0.0 <= recovery_ratio <= 1.0:
        raise ValueError("recovery_sigma_ratio must be in [0, 1]")
    sampler_name = str(params["sampler_name"])
    recovery_names = {
        "uni_pc", "uni_pc_bh2", "dpmpp_sde", "dpmpp_sde_gpu",
        "dpmpp_2m_sde", "dpmpp_2m_sde_gpu", "dpmpp_3m_sde",
        "dpmpp_3m_sde_gpu",
    }
    use_recovery = mode != "DISABLE" and sampler_name in recovery_names
    primary_ratio = (
        1.0 - recovery_ratio
        if use_recovery and mode == "ratio between" else 1.0
    )

    async def sample_once(
        source: Any, selected_sampler: str, selected_factor: float,
        *, explicit_noise: Any = None,
    ) -> Any:
        if selected_factor <= 0.0:
            return source
        return _as_latent_ref(await _ctx().sample(
            latent=source,
            steps=int(steps),
            model=pipe[0],
            positive=pipe[3],
            negative=pipe[4],
            cfg=float(params["cfg"]),
            seed=int(seed),
            sampler_name=selected_sampler,
            scheduler=scheduler,
            denoise=1.0,
            disable_noise=not bool(add_noise),
            start_step=int(start_step),
            last_step=int(end_step),
            force_full_denoise=not bool(leftover_noise),
            sampler=sampler,
            noise=explicit_noise if add_noise else None,
            sigma_factor=selected_factor,
            sigma_schedule=sigma_schedule,
        ))

    base = latent
    current = await sample_once(
        latent,
        sampler_name,
        primary_ratio * sigma_factor,
        explicit_noise=noise,
    )
    if not use_recovery or recovery_ratio <= 0.0:
        return current

    base_value = dict(await _raw(_as_latent_ref(base)))
    mask = base_value.get("noise_mask")
    if mask is not None:
        current = await _latent_composite_masked(
            base, current, _mask3(torch.as_tensor(mask)))
        current = await _latent_masked(current, _mask3(torch.as_tensor(mask)))
    selected_recovery = str(recovery_sampler)
    if selected_recovery == "AUTO":
        selected_recovery = (
            "dpm_fast"
            if sampler_name in {
                "uni_pc", "uni_pc_bh2", "dpmpp_sde", "dpmpp_sde_gpu",
            }
            else "dpmpp_2m"
        )
    if selected_recovery not in _HOST_SCHEDULERS and selected_recovery not in {
        "euler", "heun", "heunpp2", "dpm_2", "dpm_fast", "dpmpp_2m",
        "ddpm",
    }:
        raise ValueError("unknown recovery sampler")
    return await sample_once(
        current,
        selected_recovery,
        recovery_ratio * sigma_factor,
    )


async def _latent_masked(latent: Any, mask: torch.Tensor) -> Any:
    value = dict(await _raw(_as_latent_ref(latent)))
    value["noise_mask"] = _mask3(mask)
    return await sdk.LatentRef.from_value(value)


async def _latent_unmasked(latent: Any) -> Any:
    value = dict(await _raw(_as_latent_ref(latent)))
    value.pop("noise_mask", None)
    return await sdk.LatentRef.from_value(value)


async def _latent_composite_masked(base: Any, overlay: Any,
                                   mask: torch.Tensor) -> Any:
    base_value = dict(await _raw(_as_latent_ref(base)))
    overlay_value = dict(await _raw(_as_latent_ref(overlay)))
    base_samples = torch.as_tensor(base_value["samples"])
    overlay_samples = torch.as_tensor(overlay_value["samples"])
    if base_samples.shape != overlay_samples.shape or base_samples.ndim != 4:
        raise ValueError(
            "regional latent compositing requires matching BCHW latents")
    resized = _resize_masks(
        mask, base_samples.shape[-1], base_samples.shape[-2])
    if resized.shape[0] == 1 and base_samples.shape[0] > 1:
        resized = resized.expand(base_samples.shape[0], -1, -1)
    if resized.shape[0] != base_samples.shape[0]:
        resized = resized.amax(dim=0, keepdim=True).expand(
            base_samples.shape[0], -1, -1)
    alpha = resized[:, None].to(base_samples.device, base_samples.dtype)
    base_value["samples"] = (
        base_samples * (1.0 - alpha)
        + overlay_samples.to(base_samples.device, base_samples.dtype) * alpha)
    base_value.pop("noise_mask", None)
    return await sdk.LatentRef.from_value(base_value)


async def _two_samplers_for_mask(
    latent_image, base_sampler, mask_sampler, mask, **_kwargs,
):
    selected = _mask3(await _raw(mask))
    inverse = torch.where(
        selected != 1.0, torch.ones_like(selected), torch.zeros_like(selected))
    current = await _run_basic_sampler_recipe(
        base_sampler, await _latent_masked(latent_image, inverse))
    current = await _run_basic_sampler_recipe(
        mask_sampler, await _latent_masked(current, selected))
    return _one(await _latent_unmasked(current))


def _regional_specs(regional_prompts: Any) -> list[dict[str, Any]]:
    if not isinstance(regional_prompts, list) or not regional_prompts:
        raise ValueError("RegionalSampler needs at least one regional prompt")
    result = []
    for value in regional_prompts:
        if (
            not isinstance(value, dict)
            or value.get("secure_kind") != "regional_prompt"
        ):
            raise TypeError(
                "regional prompts must come from the secure RegionalPrompt node")
        strength = float(value.get("variation_strength", 0.0))
        if not 0.0 <= strength <= 1.0:
            raise ValueError("regional variation strength must be in [0, 1]")
        if str(value.get("variation_method", "linear")) not in {
            "linear", "slerp",
        }:
            raise ValueError("regional variation method must be linear or slerp")
        variation_seed = int(value.get("variation_seed", 0))
        if not 0 <= variation_seed <= (1 << 64) - 1:
            raise ValueError("regional variation seed is out of range")
        _impact_sampler_recipe(value.get("sampler"), "ksampler_advanced")
        result.append(value)
    return result


def _mix_regional_noise(
    source: torch.Tensor, variation: torch.Tensor,
    strength: float, method: str,
) -> torch.Tensor:
    if method == "linear":
        scale = math.sqrt((1.0 - strength) ** 2 + strength ** 2)
        return (
            (1.0 - strength) * source + strength * variation
        ) / max(scale, torch.finfo(source.dtype).eps)
    shape = source.shape
    low = source.reshape(shape[0], -1)
    high = variation.reshape(shape[0], -1)
    low_norm = low / torch.linalg.vector_norm(
        low, dim=1, keepdim=True).clamp_min(torch.finfo(low.dtype).eps)
    high_norm = high / torch.linalg.vector_norm(
        high, dim=1, keepdim=True).clamp_min(torch.finfo(high.dtype).eps)
    omega = torch.acos(
        (low_norm * high_norm).sum(dim=1).clamp(-1.0, 1.0))
    sine = torch.sin(omega)
    near_zero = sine.abs() <= torch.finfo(sine.dtype).eps
    first = torch.sin((1.0 - strength) * omega) / sine.clamp_min(
        torch.finfo(sine.dtype).eps)
    second = torch.sin(strength * omega) / sine.clamp_min(
        torch.finfo(sine.dtype).eps)
    result = first[:, None] * low + second[:, None] * high
    if torch.any(near_zero):
        result[near_zero] = (
            (1.0 - strength) * low[near_zero]
            + strength * high[near_zero]
        )
    return result.reshape(shape)


async def _regional_noise(
    latent: Any, seed: int, prompts: list[dict[str, Any]],
) -> Any:
    value = dict(await _raw(_as_latent_ref(latent)))
    samples = torch.as_tensor(value.get("samples"))
    if samples.ndim != 4:
        raise ValueError("regional variation noise requires BCHW latents")
    generator = torch.Generator(device="cpu").manual_seed(int(seed))
    noise = torch.randn(
        samples.shape, generator=generator, dtype=samples.dtype,
        device="cpu")
    for prompt in prompts:
        strength = float(prompt.get("variation_strength", 0.0))
        if strength <= 0.0:
            continue
        variation_generator = torch.Generator(device="cpu").manual_seed(
            int(prompt.get("variation_seed", 0)))
        variation = torch.randn(
            samples.shape,
            generator=variation_generator,
            dtype=samples.dtype,
            device="cpu",
        )
        mixed = _mix_regional_noise(
            noise, variation, strength,
            str(prompt.get("variation_method", "linear")))
        mask = _resize_masks(
            _mask3(await _raw(prompt["mask"])),
            samples.shape[-1], samples.shape[-2])
        if mask.shape[0] == 1 and samples.shape[0] > 1:
            mask = mask.expand(samples.shape[0], -1, -1)
        elif mask.shape[0] != samples.shape[0]:
            raise ValueError("regional mask batch does not match latent batch")
        alpha = (mask == 1.0)[:, None].expand(
            -1, samples.shape[1], -1, -1)
        noise = torch.where(alpha, mixed, noise)
    return await sdk.TensorRef._from_raw(noise)


async def _regional_masks(
    regional_prompts: list[dict[str, Any]], overlap_factor: int,
) -> tuple[torch.Tensor, list[torch.Tensor]]:
    masks = [_mask3(await _raw(item["mask"])) for item in regional_prompts]
    combined = masks[0]
    for mask in masks[1:]:
        width = max(combined.shape[-1], mask.shape[-1])
        height = max(combined.shape[-2], mask.shape[-2])
        combined = _resize_masks(combined, width, height)
        mask = _resize_masks(mask, width, height)
        batch = max(combined.shape[0], mask.shape[0])
        if combined.shape[0] == 1:
            combined = combined.expand(batch, -1, -1)
        if mask.shape[0] == 1:
            mask = mask.expand(batch, -1, -1)
        combined = torch.maximum(combined, mask)
    regions = [
        _dilate(mask, max(0, int(overlap_factor)))
        for mask in masks
    ]
    return (combined > 0).float(), regions


def _recovery_needed(recipe: Any, mode: str) -> bool:
    if mode == "DISABLE":
        return False
    params = _impact_sampler_recipe(recipe, "ksampler_advanced")
    return str(params["sampler_name"]) in {
        "uni_pc", "uni_pc_bh2", "dpmpp_sde", "dpmpp_sde_gpu",
        "dpmpp_2m_sde", "dpmpp_2m_sde_gpu", "dpmpp_3m_sde",
        "dpmpp_3m_sde_gpu",
    }


async def _regional_step_loop(
    latent: Any,
    *,
    seed: int,
    steps: int,
    start_step: int,
    end_step: int,
    add_noise: bool,
    return_with_leftover_noise: bool,
    base_sampler: Any,
    regional_prompts: list[dict[str, Any]],
    overlap_factor: int,
    restore_latent: bool,
    additional_mode: str,
    additional_sampler: str,
    additional_sigma_ratio: float,
) -> Any:
    combined, region_masks = await _regional_masks(
        regional_prompts, overlap_factor)
    inverse = torch.where(
        combined == 0.0, torch.ones_like(combined), torch.zeros_like(combined))
    current = latent
    first = True
    initial_noise = (
        await _regional_noise(latent, seed, regional_prompts)
        if add_noise else None
    )
    for step in range(int(start_step), int(end_step)):
        base = await _run_advanced_sampler_recipe(
            base_sampler,
            await _latent_masked(current, inverse),
            seed=seed,
            steps=steps,
            start_step=step,
            end_step=step + 1,
            add_noise=bool(add_noise and first),
            leftover_noise=(
                step + 1 < end_step or return_with_leftover_noise),
            noise=initial_noise if first else None,
            recovery_mode=additional_mode,
            recovery_sampler=additional_sampler,
            recovery_sigma_ratio=additional_sigma_ratio,
        )
        base = await _latent_unmasked(base)
        current = base
        for prompt, region_mask in zip(
            regional_prompts, region_masks, strict=True,
        ):
            regional = await _run_advanced_sampler_recipe(
                prompt["sampler"],
                await _latent_masked(base if restore_latent else current,
                                     region_mask),
                seed=seed,
                steps=steps,
                start_step=step,
                end_step=step + 1,
                add_noise=False,
                leftover_noise=(
                    step + 1 < end_step or return_with_leftover_noise),
                recovery_mode=additional_mode,
                recovery_sampler=additional_sampler,
                recovery_sigma_ratio=additional_sigma_ratio,
            )
            regional = await _latent_unmasked(regional)
            current = (
                await _latent_composite_masked(base, regional, region_mask)
                if restore_latent else regional)
            if restore_latent:
                base = current
        first = False
    return await _latent_unmasked(current)


async def _regional_sampler(
    seed, seed_2nd, seed_2nd_mode, steps, base_only_steps, denoise,
    samples, base_sampler, regional_prompts, overlap_factor, restore_latent,
    additional_mode, additional_sampler, additional_sigma_ratio,
    **_kwargs,
):
    prompts = _regional_specs(regional_prompts)
    steps = int(steps)
    denoise = float(denoise)
    if not 0.0 < denoise <= 1.0:
        raise ValueError("RegionalSampler denoise must be in (0, 1]")
    advanced_steps = max(steps, int(steps / denoise))
    start = advanced_steps - steps
    base_end = min(advanced_steps, start + int(base_only_steps))
    current = samples
    if base_end > start:
        base_noise = await _regional_noise(current, int(seed), prompts)
        current = await _run_advanced_sampler_recipe(
            base_sampler, current,
            seed=int(seed), steps=advanced_steps,
            start_step=start, end_step=base_end,
            add_noise=True,
            leftover_noise=(seed_2nd_mode == "ignore"),
            noise=base_noise,
        )
    regional_seed = int(seed)
    if seed_2nd_mode == "seed+seed_2nd":
        regional_seed = (regional_seed + int(seed_2nd)) % (1 << 64)
    elif seed_2nd_mode == "seed-seed_2nd":
        regional_seed = (regional_seed - int(seed_2nd)) % (1 << 64)
    elif seed_2nd_mode != "ignore":
        regional_seed = int(seed_2nd)
    return _one(await _regional_step_loop(
        current,
        seed=regional_seed,
        steps=advanced_steps,
        start_step=base_end,
        end_step=advanced_steps,
        add_noise=(seed_2nd_mode != "ignore" or base_end == start),
        return_with_leftover_noise=False,
        base_sampler=base_sampler,
        regional_prompts=prompts,
        overlap_factor=overlap_factor,
        restore_latent=bool(restore_latent),
        additional_mode=str(additional_mode),
        additional_sampler=str(additional_sampler),
        additional_sigma_ratio=float(additional_sigma_ratio),
    ))


async def _regional_sampler_advanced(
    add_noise, noise_seed, steps, start_at_step, end_at_step, overlap_factor,
    restore_latent, return_with_leftover_noise, latent_image, base_sampler,
    regional_prompts, additional_mode, additional_sampler,
    additional_sigma_ratio, **_kwargs,
):
    prompts = _regional_specs(regional_prompts)
    start = max(0, min(int(steps), int(start_at_step)))
    end = max(start, min(int(steps), int(end_at_step)))
    if end == start:
        return _one(latent_image)
    return _one(await _regional_step_loop(
        latent_image,
        seed=int(noise_seed),
        steps=int(steps),
        start_step=start,
        end_step=end,
        add_noise=bool(add_noise),
        return_with_leftover_noise=bool(return_with_leftover_noise),
        base_sampler=base_sampler,
        regional_prompts=prompts,
        overlap_factor=overlap_factor,
        restore_latent=bool(restore_latent),
        additional_mode=str(additional_mode),
        additional_sampler=str(additional_sampler),
        additional_sigma_ratio=float(additional_sigma_ratio),
    ))


async def _two_advanced_samplers_for_mask(
    seed, steps, denoise, samples, base_sampler, mask_sampler, mask,
    overlap_factor, **_kwargs,
):
    prompt = (await _regional_prompt(
        mask=mask, advanced_sampler=mask_sampler))[0]
    return await _regional_sampler(
        seed=seed,
        seed_2nd=0,
        seed_2nd_mode="ignore",
        steps=steps,
        base_only_steps=1,
        denoise=denoise,
        samples=samples,
        base_sampler=base_sampler,
        regional_prompts=prompt,
        overlap_factor=overlap_factor,
        restore_latent=True,
        additional_mode="ratio between",
        additional_sampler="AUTO",
        additional_sigma_ratio=0.3,
    )


async def _regional_prompt(mask, advanced_sampler, variation_seed=0,
                           variation_strength=0.0, variation_method="linear",
                           **_kwargs):
    return _one([{
        "secure_kind": "regional_prompt", "mask": mask,
        "sampler": advanced_sampler, "variation_seed": int(variation_seed),
        "variation_strength": float(variation_strength),
        "variation_method": str(variation_method),
    }])


async def _combine_regional(**kwargs):
    result = []
    for value in kwargs.values():
        if value is not None:
            result.extend(value)
    return _one(result)


async def _sample_basic(basic_pipe, latent_image, seed=0, noise_seed=0,
                        steps=20, cfg=8.0, sampler_name="euler",
                        scheduler="normal", denoise=1.0, add_noise=True,
                        start_at_step=None, end_at_step=None,
                        return_with_leftover_noise=False,
                        scheduler_func_opt=None, **_kwargs):
    sigma_schedule = _sigma_schedule_recipe(scheduler_func_opt)
    pipe = _basic_pipe(basic_pipe)
    sampled = await _ctx().sample(
        latent=latent_image,
        steps=int(steps),
        model=pipe[0],
        positive=pipe[3],
        negative=pipe[4],
        cfg=float(cfg),
        seed=int(noise_seed if noise_seed is not None else seed),
        sampler_name=str(sampler_name),
        scheduler=str(scheduler),
        denoise=float(denoise),
        disable_noise=not bool(add_noise),
        start_step=None if start_at_step is None else int(start_at_step),
        last_step=None if end_at_step is None else int(end_at_step),
        force_full_denoise=not bool(return_with_leftover_noise),
        sigma_schedule=sigma_schedule,
    )
    return pipe, sampled, pipe[2]


async def _sample_simple(seed, **kwargs):
    kwargs["seed"] = seed
    kwargs["noise_seed"] = seed
    kwargs["add_noise"] = True
    return await _sample_basic(**kwargs)


async def _sample_advanced(noise_seed, **kwargs):
    kwargs["noise_seed"] = noise_seed
    return await _sample_basic(**kwargs)


async def _latent_pixel_scale(samples, scale_method, scale_factor, vae,
                              use_tiled_vae=False, upscale_model_opt=None,
                              **_kwargs):
    if bool(use_tiled_vae):
        image_ref = await vae.decode_tiled(
            samples, tile_size=512, overlap=64)
    else:
        image_ref = await vae.decode(samples)
    image = _image4(await _raw(image_ref))
    height, width = image.shape[1:3]
    target_width = max(1, int(width * float(scale_factor)))
    target_height = max(1, int(height * float(scale_factor)))

    if upscale_model_opt is not None:
        previous_width = int(width)
        for _ in range(64):
            if previous_width >= target_width:
                break
            image_ref = await upscale_model_opt.upscale(image_ref)
            image = _image4(await _raw(image_ref))
            current_width = int(image.shape[2])
            if current_width <= previous_width:
                break
            previous_width = current_width

    scaled = _resize_images(image, target_width, target_height, str(scale_method))
    scaled_ref = await sdk.ImageRef._from_raw(scaled)
    if bool(use_tiled_vae):
        latent = await vae.encode_tiled(
            scaled_ref, tile_x=512, tile_y=512, overlap=64)
    else:
        latent = await vae.encode(scaled_ref)
    return latent, scaled


_PIXEL_HOOK_RECIPE_KINDS = frozenset({
    "CfgScheduleHookProvider",
    "DenoiseScheduleHookProvider",
    "NoiseInjectionHookProvider",
    "StepsScheduleHookProvider",
    "UnsamplerHookProvider",
})


def _pixel_hook_recipes(hook: Any) -> list[dict[str, Any]]:
    """Flatten Impact's data-only pixel-hook language in execution order."""
    if hook is None:
        return []
    if not isinstance(hook, dict):
        raise TypeError("PK_HOOK must be a secure declarative recipe")
    kind = hook.get("secure_kind")
    if kind == "pixel_hook_chain":
        items = hook.get("items")
        if not isinstance(items, list):
            raise TypeError("pixel hook chain must contain a recipe list")
        result: list[dict[str, Any]] = []
        for item in items:
            result.extend(_pixel_hook_recipes(item))
        return result
    if kind not in _PIXEL_HOOK_RECIPE_KINDS:
        raise TypeError(f"unknown secure pixel hook recipe {kind!r}")
    params = hook.get("params")
    if not isinstance(params, dict):
        raise TypeError("pixel hook recipe params must be a mapping")
    if str(params.get("schedule_for_iteration", "simple")) != "simple":
        raise ValueError("only Impact's simple pixel-hook schedule is supported")
    return [hook]


def _pixel_hook_sample_values(
    hook: Any,
    step_info: tuple[int, int],
    *,
    steps: int,
    cfg: float,
    denoise: float,
) -> tuple[int, float, float]:
    current_step, total_steps = step_info
    if not 0 <= current_step < total_steps or total_steps < 1:
        raise ValueError("invalid iterative-upscale step information")
    current_steps = int(steps)
    current_cfg = float(cfg)
    current_denoise = float(denoise)
    progress = current_step / (total_steps - 1) if total_steps > 1 else 1.0
    for recipe in _pixel_hook_recipes(hook):
        kind = recipe["secure_kind"]
        params = recipe["params"]
        if kind == "CfgScheduleHookProvider":
            target = float(params.get("target_cfg", 3.0))
            if not 0.0 <= target <= 100.0:
                raise ValueError("pixel-hook target_cfg must be in [0, 100]")
            current_cfg = int(current_cfg + (target - current_cfg) * progress)
        elif kind == "DenoiseScheduleHookProvider":
            target = float(params.get("target_denoise", 0.2))
            if not 0.0 <= target <= 1.0:
                raise ValueError("pixel-hook target_denoise must be in [0, 1]")
            current_denoise += (target - current_denoise) * progress
        elif kind == "StepsScheduleHookProvider":
            target = int(params.get("target_steps", 20))
            if not 1 <= target <= 10000:
                raise ValueError("pixel-hook target_steps must be in [1, 10000]")
            current_steps = int(
                current_steps + (target - current_steps) * progress)
    return current_steps, current_cfg, current_denoise


async def _pixel_hook_post_encode(
    latent: Any, hook: Any, step_info: tuple[int, int],
) -> Any:
    """Apply latent transforms while model execution remains brokered."""
    current_step, total_steps = step_info
    current = _as_latent_ref(latent)
    for recipe in _pixel_hook_recipes(hook):
        kind = recipe["secure_kind"]
        params = recipe["params"]
        if kind == "UnsamplerHookProvider":
            start = int(params.get("start_end_at_step", 21))
            end = int(params.get("end_end_at_step", 24))
            end_at_step = int(
                start + (end - start) * current_step / total_steps)
            current = await _ctx().unsample(
                current,
                steps=int(params.get("steps", 25)),
                model=params.get("model"),
                positive=params.get("positive"),
                negative=params.get("negative"),
                cfg=float(params.get("cfg", 1.0)),
                sampler_name=str(params.get("sampler_name", "euler")),
                scheduler=str(params.get("scheduler", "normal")),
                end_at_step=end_at_step,
                normalize=str(params.get("normalize", "disable")) == "enable",
            )
            continue
        if kind != "NoiseInjectionHookProvider":
            continue
        source = str(params.get("source", "CPU"))
        if source not in {"CPU", "GPU"}:
            raise ValueError("pixel-hook noise source must be CPU or GPU")
        start = float(params.get("start_strength", 1.0))
        end = float(params.get("end_strength", 1.0))
        strength = start + (end - start) * current_step / total_steps
        if not 0.0 <= strength <= 200.0:
            raise ValueError("pixel-hook noise strength must be in [0, 200]")
        value = dict(await _raw(current))
        samples = torch.as_tensor(value.get("samples"))
        if samples.ndim != 4:
            raise ValueError("pixel-hook noise injection requires BCHW latents")
        generator = torch.Generator(device="cpu").manual_seed(
            int(params.get("seed", 0)) + current_step * 2)
        noise = torch.randn(
            samples.shape,
            generator=generator,
            dtype=samples.dtype,
            device="cpu",
        ).to(samples.device)
        injected = samples + noise * strength
        if value.get("noise_mask") is not None:
            latent_mask = _latent_mask_for_samples(
                value["noise_mask"], samples).to(samples.device, samples.dtype)
            injected = latent_mask * injected + (1.0 - latent_mask) * samples
        value["samples"] = injected
        current = await sdk.LatentRef.from_value(value)
    return current


def _pixel_upscaler_spec(upscaler: Any) -> dict[str, Any]:
    if not isinstance(upscaler, dict):
        raise TypeError("UPSCALER must be an Impact secure provider value")
    kind = upscaler.get("secure_kind")
    pixel_kinds = {
        "PixelKSampleUpscalerProvider",
        "PixelKSampleUpscalerProviderPipe",
    }
    tiled_kinds = {
        "PixelTiledKSampleUpscalerProvider",
        "PixelTiledKSampleUpscalerProviderPipe",
    }
    two_sampler_kinds = {
        "TwoSamplersForMaskUpscalerProvider",
        "TwoSamplersForMaskUpscalerProviderPipe",
    }
    if kind not in pixel_kinds | tiled_kinds | two_sampler_kinds:
        raise TypeError(f"unknown Impact upscaler provider {kind!r}")
    params = dict(upscaler.get("params") or {})
    if kind in {
        "PixelKSampleUpscalerProviderPipe",
        "PixelTiledKSampleUpscalerProviderPipe",
        "TwoSamplersForMaskUpscalerProviderPipe",
    }:
        model, _clip, vae, positive, negative = _basic_pipe(params["basic_pipe"])
        params.update({
            "model": model,
            "vae": vae,
            "positive": positive,
            "negative": negative,
        })
    params["_provider_kind"] = str(kind)
    if kind in two_sampler_kinds:
        required = (
            "scale_method", "full_sample_schedule", "base_sampler",
            "mask_sampler", "mask", "vae",
        )
        for name in (
            "base_sampler", "mask_sampler", "full_sampler_opt",
        ):
            if params.get(name) is not None:
                _impact_sampler_recipe(params[name], "ksampler")
        for name in (
            "pk_hook_base_opt", "pk_hook_mask_opt", "pk_hook_full_opt",
        ):
            _pixel_hook_recipes(params.get(name))
        schedule = str(params.get("full_sample_schedule", "none"))
        if schedule not in {
            "none", "interleave1", "interleave2", "interleave3",
            "last1", "last2", "interleave1+last1",
            "interleave2+last1", "interleave3+last1",
        }:
            raise ValueError("unknown two-sampler full-sample schedule")
    else:
        _pixel_hook_recipes(params.get("pk_hook_opt"))
        _sigma_schedule_recipe(params.get("scheduler_func_opt"))
        required = (
            "scale_method", "model", "vae", "seed", "steps", "cfg",
            "sampler_name", "scheduler", "positive", "negative", "denoise",
        )
        if kind in tiled_kinds:
            required += ("tile_width", "tile_height", "tiling_strategy")
            tile_width = int(params.get("tile_width", 0))
            tile_height = int(params.get("tile_height", 0))
            if not 320 <= tile_width <= 16384:
                raise ValueError("tile_width must be in [320, 16384]")
            if not 320 <= tile_height <= 16384:
                raise ValueError("tile_height must be in [320, 16384]")
            strategy = str(params.get("tiling_strategy"))
            if strategy not in {"random", "padded", "simple"}:
                raise ValueError("unknown tiled-sampling strategy")
            overlap = int(params.get("overlap", 64))
            if not 0 <= overlap <= 4096:
                raise ValueError("tiled VAE overlap must be in [0, 4096]")
            vae_tile_size = max(
                64, min(4096, max(tile_width, tile_height)))
            if overlap >= vae_tile_size:
                raise ValueError("tiled VAE overlap must be smaller than its tile")
            params.update({
                "use_tiled_vae": True,
                "tile_size": vae_tile_size,
                "overlap": overlap,
                "_tiled_sampling": True,
            })
        tile_cnet = params.get("tile_cnet_opt")
        if tile_cnet is not None and not isinstance(
            tile_cnet, sdk.ControlNetRef
        ):
            raise TypeError("tile_cnet_opt must be a typed CONTROL_NET ref")
        tile_strength = float(params.get("tile_cnet_strength", 1.0))
        if not math.isfinite(tile_strength) or not 0.0 <= tile_strength <= 1.0:
            raise ValueError("tile_cnet_strength must be in [0, 1]")
        params["tile_cnet_strength"] = tile_strength
    missing = [name for name in required if name not in params]
    if missing:
        raise ValueError(f"pixel upscaler is missing {', '.join(missing)}")
    return params


def _as_latent_ref(value: Any):
    if isinstance(value, sdk.LatentRef):
        return value
    if isinstance(value, sdk.Ref) and value.kind == "LATENT":
        return sdk.LatentRef._wrap(value)
    raise TypeError("LATENT input must be an opaque latent reference")


async def _latent_noise_mask(latent: Any, noise_mask: Any):
    latent = _as_latent_ref(latent)
    if noise_mask is None:
        return latent
    value = dict(await _raw(latent))
    value["noise_mask"] = noise_mask
    return await sdk.LatentRef.from_value(value)


async def _pixel_sample_values(
    latent: Any,
    *,
    model: Any,
    positive: Any,
    negative: Any,
    seed: int,
    steps: int,
    cfg: float,
    sampler_name: str,
    scheduler: str,
    denoise: float,
    hook: Any,
    step_info: tuple[int, int],
    sigma_schedule: Any = None,
):
    current = await _pixel_hook_post_encode(latent, hook, step_info)
    steps, cfg, denoise = _pixel_hook_sample_values(
        hook, step_info, steps=steps, cfg=cfg, denoise=denoise)
    schedule = _sigma_schedule_recipe(sigma_schedule)
    if schedule is None and str(scheduler) not in _HOST_SCHEDULERS:
        raise RuntimeError(
            f"Impact scheduler {scheduler!r} needs a typed host "
            "sigma-schedule primitive")
    return _as_latent_ref(await _ctx().sample(
        latent=current,
        steps=int(steps),
        model=model,
        positive=positive,
        negative=negative,
        cfg=float(cfg),
        seed=int(seed),
        sampler_name=str(sampler_name),
        scheduler=str(scheduler),
        denoise=float(denoise),
        disable_noise=False,
        force_full_denoise=True,
        sigma_schedule=schedule,
    ))


def _as_cond_ref(value: Any):
    if isinstance(value, sdk.CondRef):
        return value
    if isinstance(value, sdk.Ref) and value.kind == "CONDITIONING":
        return sdk.CondRef._wrap(value)
    raise TypeError("tiled sampling needs opaque CONDITIONING references")


def _tile_control_preprocess(image: torch.Tensor) -> torch.Tensor:
    """Impact's fixed three-level Tile ControlNet preprocessor.

    This is deliberately pack code: it is the policy selected by these
    upscaler providers, not a new model operation.  It reduces the image by
    eight and reconstructs it through three pyramid-sized interpolation
    passes, leaving the high-frequency detail out of the ControlNet hint.
    """
    image = _image4(image).clamp(0.0, 1.0)
    height, width = map(int, image.shape[1:3])
    target_height = max(64, round(height / 64.0) * 64)
    target_width = max(64, round(width / 64.0) * 64)
    current = _resize_images(
        image, target_width // 8, target_height // 8, "area")
    for factor in (4, 2, 1):
        current = _resize_images(
            current,
            target_width // factor,
            target_height // factor,
            "bilinear",
        )
    return current


async def _pixel_tile_conditioning(
    spec: dict[str, Any], image: torch.Tensor,
) -> tuple[Any, Any]:
    positive = _as_cond_ref(spec["positive"])
    negative = _as_cond_ref(spec["negative"])
    control_net = spec.get("tile_cnet_opt")
    if control_net is None or int(image.shape[0]) > 1:
        # This is the upstream provider's explicit batch behavior: Tile
        # ControlNet is skipped for an image batch, while sampling proceeds.
        return positive, negative
    if not isinstance(control_net, sdk.ControlNetRef):
        raise TypeError("tile_cnet_opt must be a typed CONTROL_NET ref")
    preprocessed_ref = await sdk.ImageRef._from_raw(
        _tile_control_preprocess(image))
    try:
        return await control_net.apply(
            positive,
            negative,
            preprocessed_ref,
            strength=float(spec.get("tile_cnet_strength", 1.0)),
            start_percent=0.0,
            end_percent=1.0,
            vae=spec["vae"],
        )
    finally:
        await preprocessed_ref.release()


def _prepare_tiled_noise(
    samples: torch.Tensor, seed: int, batch_index: Any = None,
) -> torch.Tensor:
    """Reproduce ComfyUI's deterministic global noise before slicing tiles."""
    samples = torch.as_tensor(samples)
    if samples.ndim != 4:
        raise ValueError("tiled sampling requires BCHW latents")
    generator = torch.Generator(device="cpu").manual_seed(int(seed))

    def generate_one() -> torch.Tensor:
        return torch.randn(
            (1, *samples.shape[1:]),
            dtype=torch.float32,
            device="cpu",
            generator=generator,
        ).to(dtype=samples.dtype)

    if batch_index is None:
        return torch.randn(
            samples.shape,
            dtype=torch.float32,
            device="cpu",
            generator=generator,
        ).to(dtype=samples.dtype)
    indices = list(batch_index)
    if len(indices) != samples.shape[0]:
        raise ValueError("latent batch_index length does not match its batch")
    if any(
        isinstance(index, bool) or not isinstance(index, int) or index < 0
        for index in indices
    ):
        raise ValueError("latent batch_index values must be nonnegative integers")
    if indices and max(indices) > 65535:
        raise ValueError("latent batch_index is too large for bounded noise")
    wanted = set(indices)
    generated: dict[int, torch.Tensor] = {}
    for index in range(max(indices, default=-1) + 1):
        noise = generate_one()
        if index in wanted:
            generated[index] = noise
    return torch.cat([generated[index] for index in indices], dim=0)


def _tile_ranges(length: int, size: int) -> list[tuple[int, int]]:
    return [
        (start, min(size, length - start))
        for start in range(0, length, size)
    ]


def _jittered_tile_ranges(
    length: int, size: int, jitter: int,
) -> list[tuple[int, int]]:
    count = (length + jitter - 1) // size + 1
    points = [
        min(length, max(0, size * index - jitter))
        for index in range(count + 1)
    ]
    return [
        (left, right - left)
        for left, right in zip(points, points[1:])
        if right > left
    ]


def _simple_tile_pass(
    latent_height: int, latent_width: int,
    tile_height: int, tile_width: int,
) -> list[tuple[int, int, int, int, torch.Tensor | None]]:
    return [
        (y, height, x, width, None)
        for y, height in _tile_ranges(latent_height, tile_height)
        for x, width in _tile_ranges(latent_width, tile_width)
    ]


def _random_tile_groups(
    latent_height: int, latent_width: int,
    tile_height: int, tile_width: int,
    steps: int, seed: int,
) -> list[list[tuple[int, int, int, int, torch.Tensor | None]]]:
    generator = torch.Generator(device="cpu").manual_seed(int(seed))
    groups = []
    for step in range(steps):
        random_width, random_height = torch.rand(
            (2,), dtype=torch.float32, generator=generator).tolist()
        width_jitters = (
            int(random_width * tile_width),
            int(((random_width + 0.5) % 1.0) * tile_width),
        )
        height_jitters = (
            int(random_height * tile_height),
            int(((random_height + 0.5) % 1.0) * tile_height),
        )
        rows = [
            _jittered_tile_ranges(latent_height, tile_height, jitter)
            for jitter in height_jitters
        ]
        columns = [
            _jittered_tile_ranges(latent_width, tile_width, jitter)
            for jitter in width_jitters
        ]
        tiles = []
        if step % 2 == 0:
            for row_index, (y, height) in enumerate(rows[0]):
                for x, width in columns[row_index % 2]:
                    tiles.append((y, height, x, width, None))
        else:
            for column_index, (x, width) in enumerate(columns[0]):
                for y, height in rows[column_index % 2]:
                    tiles.append((y, height, x, width, None))
        groups.append(tiles)
    return groups


def _padded_tile_mask(
    batch: int, tile_height: int, tile_width: int,
    row_index: int, column_index: int,
    last_row: int, last_column: int,
    extend_height_edges: bool, extend_width_edges: bool,
) -> torch.Tensor:
    quarter_height = tile_height // 4
    quarter_width = tile_width // 4
    top = (
        0 if extend_height_edges and row_index == 0 else quarter_height)
    bottom = (
        tile_height
        if extend_height_edges and row_index == last_row
        else tile_height - quarter_height
    )
    left = (
        0 if extend_width_edges and column_index == 0 else quarter_width)
    right = (
        tile_width
        if extend_width_edges and column_index == last_column
        else tile_width - quarter_width
    )
    mask = torch.zeros(
        (batch, 1, tile_height, tile_width), dtype=torch.float32)
    mask[..., top:bottom, left:right] = 1.0
    return mask


def _pad_boundary_tile(
    tile: tuple[int, int, int, int, torch.Tensor | None],
    latent_height: int, latent_width: int,
    tile_height: int, tile_width: int,
) -> tuple[int, int, int, int, torch.Tensor | None]:
    y, height, x, width, mask = tile
    if (
        (height == tile_height or height == latent_height)
        and (width == tile_width or width == latent_width)
    ):
        return tile
    y_offset = min(0, latent_height - (y + tile_height))
    x_offset = min(0, latent_width - (x + tile_width))
    padded = torch.zeros(
        (mask.shape[0], 1, tile_height, tile_width), dtype=mask.dtype)
    target_y = -y_offset
    target_x = -x_offset
    padded[..., target_y:target_y + height, target_x:target_x + width] = mask
    return (
        y + y_offset, tile_height,
        x + x_offset, tile_width,
        padded,
    )


def _padded_tile_passes(
    batch: int, latent_height: int, latent_width: int,
    tile_height: int, tile_width: int,
) -> list[list[tuple[int, int, int, int, torch.Tensor | None]]]:
    base_rows = list(range(0, latent_height, tile_height))
    base_columns = list(range(0, latent_width, tile_width))
    shifted_rows = list(range(
        tile_height // 2,
        max(tile_height // 2, latent_height - tile_height // 2),
        tile_height,
    ))
    shifted_columns = list(range(
        tile_width // 2,
        max(tile_width // 2, latent_width - tile_width // 2),
        tile_width,
    ))
    configurations = (
        (base_rows, base_columns, True, True),
        (shifted_rows, base_columns, False, True),
        (base_rows, shifted_columns, True, False),
        (shifted_rows, shifted_columns, False, False),
    )
    passes = []
    for rows, columns, extend_height, extend_width in configurations:
        tiles = []
        for row_index, y in enumerate(rows):
            for column_index, x in enumerate(columns):
                height = min(tile_height, latent_height - y)
                width = min(tile_width, latent_width - x)
                mask = _padded_tile_mask(
                    batch, tile_height, tile_width,
                    row_index, column_index,
                    len(rows) - 1, len(columns) - 1,
                    extend_height, extend_width,
                )[..., :height, :width]
                tiles.append(_pad_boundary_tile(
                    (y, height, x, width, mask),
                    latent_height, latent_width, tile_height, tile_width,
                ))
        if tiles:
            passes.append(tiles)
    return passes


def _tiled_noise_mask(
    latent_value: dict[str, Any], samples: torch.Tensor,
) -> torch.Tensor | None:
    source = latent_value.get("noise_mask")
    if source is None:
        return None
    mask = _resize_masks(
        _mask3(torch.as_tensor(source)),
        int(samples.shape[-1]),
        int(samples.shape[-2]),
    )
    if mask.shape[0] == 1 and samples.shape[0] > 1:
        mask = mask.expand(samples.shape[0], -1, -1)
    elif mask.shape[0] != samples.shape[0]:
        raise ValueError("tiled noise-mask batch does not match the latent")
    return mask[:, None]


def _tile_mask_for_region(
    source_mask: torch.Tensor | None,
    plan_mask: torch.Tensor | None,
    y: int, height: int, x: int, width: int,
    batch: int,
) -> torch.Tensor | None:
    result = (
        None
        if source_mask is None
        else source_mask[..., y:y + height, x:x + width].clone()
    )
    if plan_mask is not None:
        selected = plan_mask
        if selected.shape[0] == 1 and batch > 1:
            selected = selected.expand(batch, -1, -1, -1)
        elif selected.shape[0] != batch:
            raise ValueError("tile-mask batch does not match the latent")
        result = selected if result is None else result * selected
    return result


async def _sample_tiled_region(
    latent_value: dict[str, Any],
    noise: torch.Tensor,
    positive: Any,
    negative: Any,
    *,
    y: int,
    height: int,
    x: int,
    width: int,
    mask: torch.Tensor | None,
    add_noise: bool,
    model: Any,
    seed: int,
    total_steps: int,
    start_step: int,
    end_step: int,
    cfg: float,
    sampler_name: str,
    scheduler: str,
) -> torch.Tensor:
    samples = torch.as_tensor(latent_value["samples"])
    tile_value = dict(latent_value)
    tile_value["samples"] = samples[
        ..., y:y + height, x:x + width].clone()
    if mask is None:
        tile_value.pop("noise_mask", None)
    else:
        tile_value["noise_mask"] = mask[:, 0]

    tile_ref = await sdk.LatentRef.from_value(tile_value)
    noise_ref = None
    positive_ref = None
    negative_ref = None
    sampled_ref = None
    try:
        positive_ref = await _as_cond_ref(positive).spatial_crop(
            x=x, y=y, width=width, height=height,
            source_width=int(samples.shape[-1]),
            source_height=int(samples.shape[-2]),
        )
        negative_ref = await _as_cond_ref(negative).spatial_crop(
            x=x, y=y, width=width, height=height,
            source_width=int(samples.shape[-1]),
            source_height=int(samples.shape[-2]),
        )
        if add_noise:
            noise_ref = await sdk.TensorRef._from_raw(
                noise[..., y:y + height, x:x + width].clone())
        sampled_ref = _as_latent_ref(await _ctx().sample(
            latent=tile_ref,
            steps=int(total_steps),
            model=model,
            positive=positive_ref,
            negative=negative_ref,
            cfg=float(cfg),
            seed=int(seed),
            sampler_name=str(sampler_name),
            scheduler=str(scheduler),
            denoise=1.0,
            disable_noise=not add_noise,
            start_step=int(start_step),
            last_step=int(end_step),
            force_full_denoise=False,
            noise=noise_ref,
        ))
        sampled_value = dict(await _raw(sampled_ref))
        sampled = torch.as_tensor(sampled_value.get("samples"))
        if sampled.shape != tile_value["samples"].shape:
            raise ValueError("tiled sampler changed the latent tile shape")
        return sampled.clone()
    finally:
        released = set()
        for ref in (
            sampled_ref, noise_ref, positive_ref, negative_ref, tile_ref,
        ):
            if ref is not None and ref.id not in released:
                released.add(ref.id)
                await ref.release()


async def _pixel_tiled_sample(
    encoded: Any,
    spec: dict[str, Any],
    step_info: tuple[int, int],
    positive: Any,
    negative: Any,
):
    current = await _pixel_hook_post_encode(
        encoded, spec.get("pk_hook_opt"), step_info)
    steps, cfg, denoise = _pixel_hook_sample_values(
        spec.get("pk_hook_opt"),
        step_info,
        steps=int(spec["steps"]),
        cfg=float(spec["cfg"]),
        denoise=float(spec["denoise"]),
    )
    if denoise <= 0.0:
        return current
    scheduler = str(spec["scheduler"])
    if scheduler not in _HOST_SCHEDULERS:
        raise RuntimeError(
            f"Impact scheduler {scheduler!r} needs a typed host "
            "sigma-schedule primitive")
    strategy = str(spec["tiling_strategy"])
    sampler_name = str(spec["sampler_name"])
    if strategy == "random" and sampler_name in {"uni_pc", "uni_pc_bh2"}:
        raise RuntimeError(
            "Impact's random tile strategy cannot preserve UniPC's "
            "cross-step sampler state; use padded or simple")

    latent_value = dict(await _raw(_as_latent_ref(current)))
    samples = torch.as_tensor(latent_value.get("samples"))
    if samples.ndim != 4:
        raise ValueError("tiled sampling requires BCHW latents")
    samples = samples.clone()
    latent_value["samples"] = samples
    latent_height, latent_width = map(int, samples.shape[-2:])
    tile_height = min(latent_height, max(1, int(spec["tile_height"]) // 8))
    tile_width = min(latent_width, max(1, int(spec["tile_width"]) // 8))
    if strategy == "padded":
        if tile_height >= 4:
            tile_height = max(4, tile_height // 4 * 4)
        if tile_width >= 4:
            tile_width = max(4, tile_width // 4 * 4)

    total_steps = int(steps / denoise)
    if not steps <= total_steps <= 10000:
        raise ValueError(
            "tiled denoise expands the diffusion schedule beyond 10000 steps")
    schedule_start = total_steps - steps
    seed = int(spec["seed"])
    noise = _prepare_tiled_noise(
        samples, seed, latent_value.get("batch_index"))
    source_mask = _tiled_noise_mask(latent_value, samples)

    if strategy == "random":
        passes = [[
            (relative_step, 1, tiles)
            for relative_step, tiles in enumerate(_random_tile_groups(
                latent_height, latent_width,
                tile_height, tile_width,
                steps, seed,
            ))
        ]]
    elif strategy == "padded":
        passes = [
            [(0, steps, tiles)]
            for tiles in _padded_tile_passes(
                int(samples.shape[0]), latent_height, latent_width,
                tile_height, tile_width,
            )
        ]
    elif strategy == "simple":
        passes = [[(0, steps, _simple_tile_pass(
            latent_height, latent_width, tile_height, tile_width))]]
    else:
        raise ValueError("unknown tiled-sampling strategy")

    for image_pass in passes:
        for relative_step, tile_steps, tiles in image_pass:
            start_step = schedule_start + relative_step
            end_step = start_step + tile_steps
            add_noise = relative_step == 0
            for y, height, x, width, plan_mask in tiles:
                mask = _tile_mask_for_region(
                    source_mask,
                    plan_mask,
                    y,
                    height,
                    x,
                    width,
                    int(samples.shape[0]),
                )
                if mask is not None and not torch.any(mask != 0):
                    continue
                result = await _sample_tiled_region(
                    latent_value,
                    noise,
                    positive,
                    negative,
                    y=y,
                    height=height,
                    x=x,
                    width=width,
                    mask=mask,
                    add_noise=add_noise,
                    model=spec["model"],
                    seed=seed,
                    total_steps=total_steps,
                    start_step=start_step,
                    end_step=end_step,
                    cfg=cfg,
                    sampler_name=sampler_name,
                    scheduler=scheduler,
                )
                destination = samples[
                    ..., y:y + height, x:x + width]
                if mask is None:
                    destination.copy_(result.to(destination))
                else:
                    alpha = mask.to(destination).expand_as(destination)
                    destination.copy_(
                        destination * (1.0 - alpha)
                        + result.to(destination) * alpha)
    latent_value["samples"] = samples
    return await sdk.LatentRef.from_value(latent_value)


async def _pixel_run_sampler_recipe(
    recipe: Any, latent: Any, hook: Any, step_info: tuple[int, int],
):
    params = _impact_sampler_recipe(recipe, "ksampler")
    pipe = _basic_pipe(params["basic_pipe"])
    return await _pixel_sample_values(
        latent,
        model=pipe[0],
        positive=pipe[3],
        negative=pipe[4],
        seed=int(params["seed"]),
        steps=int(params["steps"]),
        cfg=float(params["cfg"]),
        sampler_name=str(params["sampler_name"]),
        scheduler=str(params["scheduler"]),
        denoise=float(params["denoise"]),
        hook=hook,
        step_info=step_info,
        sigma_schedule=params.get("scheduler_func_opt"),
    )


def _two_sampler_full_time(
    step_info: tuple[int, int], schedule: str,
) -> bool:
    current, total = step_info
    one_based = current + 1
    if schedule == "none":
        return False
    if schedule == "interleave1":
        return one_based % 2 == 0
    if schedule == "interleave2":
        return one_based % 3 == 0
    if schedule == "interleave3":
        return one_based % 4 == 0
    if schedule == "last1":
        return one_based == total
    if schedule == "last2":
        return one_based >= max(1, total - 1)
    intervals = {
        "interleave1+last1": 2,
        "interleave2+last1": 3,
        "interleave3+last1": 4,
    }
    if schedule in intervals:
        return one_based % intervals[schedule] == 0 or one_based == total
    raise ValueError("unknown two-sampler full-sample schedule")


async def _two_sampler_upscale_sample(
    encoded: Any, spec: dict[str, Any], step_info: tuple[int, int],
):
    value = dict(await _raw(_as_latent_ref(encoded)))
    samples = torch.as_tensor(value.get("samples"))
    if samples.ndim != 4:
        raise ValueError("two-sampler upscale requires BCHW latents")
    selected = _resize_masks(
        _mask3(await _raw(spec["mask"])),
        samples.shape[-1],
        samples.shape[-2],
    )
    if selected.shape[0] == 1 and samples.shape[0] > 1:
        selected = selected.expand(samples.shape[0], -1, -1)
    elif selected.shape[0] != samples.shape[0]:
        raise ValueError("two-sampler mask batch does not match latent batch")

    base_sampler = spec["base_sampler"]
    if _two_sampler_full_time(
        step_info, str(spec.get("full_sample_schedule", "none"))
    ):
        current = await _pixel_run_sampler_recipe(
            base_sampler,
            await _latent_unmasked(encoded),
            spec.get("pk_hook_base_opt"),
            step_info,
        )
        return await _pixel_run_sampler_recipe(
            spec.get("full_sampler_opt") or base_sampler,
            current,
            spec.get("pk_hook_full_opt"),
            step_info,
        )

    inverse = torch.where(
        selected != 1.0, torch.ones_like(selected), torch.zeros_like(selected))
    current = await _pixel_run_sampler_recipe(
        base_sampler,
        await _latent_masked(encoded, inverse),
        spec.get("pk_hook_base_opt"),
        step_info,
    )
    current = await _pixel_run_sampler_recipe(
        spec["mask_sampler"],
        await _latent_masked(current, selected),
        spec.get("pk_hook_mask_opt"),
        step_info,
    )
    return await _latent_unmasked(current)


async def _pixel_upscale_step(
    latent: Any,
    width: float,
    height: float,
    spec: dict[str, Any],
    noise_mask: Any,
    step_info: tuple[int, int],
    emit_preview: bool = False,
):
    latent = _as_latent_ref(latent)
    vae = spec["vae"]
    tiled = bool(spec.get("use_tiled_vae", False))
    tile_size = int(spec.get("tile_size", 512))
    overlap = int(spec.get("overlap", 64))
    if tiled:
        image_ref = await vae.decode_tiled(
            latent, tile_size=tile_size, overlap=overlap)
    else:
        image_ref = await vae.decode(latent)
    image = _image4(await _raw(image_ref))
    if emit_preview:
        await _ctx().progress.update(
            step_info[0] + 1, step_info[1], preview=image_ref)
    target_width, target_height = max(1, int(width)), max(1, int(height))

    upscale_model = spec.get("upscale_model_opt")
    if upscale_model is not None:
        previous_width = int(image.shape[2])
        for _ in range(64):
            if previous_width >= width:
                break
            image_ref = await upscale_model.upscale(image_ref)
            image = _image4(await _raw(image_ref))
            current_width = int(image.shape[2])
            if current_width <= previous_width:
                break
            previous_width = current_width

    scaled = _resize_images(
        image, target_width, target_height, str(spec["scale_method"])
    )
    scaled_ref = await sdk.ImageRef._from_raw(scaled)
    if tiled:
        encoded = await vae.encode_tiled(
            scaled_ref, tile_x=tile_size, tile_y=tile_size, overlap=overlap)
    else:
        encoded = await vae.encode(scaled_ref)
    provider_kind = str(spec.get("_provider_kind", ""))
    if provider_kind.startswith("TwoSamplersForMaskUpscalerProvider"):
        sampled = await _two_sampler_upscale_sample(encoded, spec, step_info)
    else:
        encoded = await _latent_noise_mask(encoded, noise_mask)
        positive, negative = spec["positive"], spec["negative"]
        if spec.get("tile_cnet_opt") is not None:
            positive, negative = await _pixel_tile_conditioning(
                spec, scaled)
        if bool(spec.get("_tiled_sampling", False)):
            sampled = await _pixel_tiled_sample(
                encoded, spec, step_info, positive, negative)
        else:
            sampled = await _pixel_sample_values(
                encoded,
                model=spec["model"],
                positive=positive,
                negative=negative,
                seed=int(spec["seed"]),
                steps=int(spec["steps"]),
                cfg=float(spec["cfg"]),
                sampler_name=str(spec["sampler_name"]),
                scheduler=str(spec["scheduler"]),
                denoise=float(spec["denoise"]),
                hook=spec.get("pk_hook_opt"),
                step_info=step_info,
                sigma_schedule=spec.get("scheduler_func_opt"),
            )
    return await _latent_noise_mask(sampled, noise_mask)


async def _iterative_latent_upscale(
    samples,
    upscale_factor,
    steps,
    temp_prefix,
    upscaler,
    step_mode="simple",
    vae_compression=8,
    **_kwargs,
):
    preview_prefix = str(temp_prefix)
    if len(preview_prefix) > 256:
        raise ValueError("iterative preview prefix is too long")
    emit_preview = bool(preview_prefix)
    spec = _pixel_upscaler_spec(upscaler)
    current = _as_latent_ref(samples)
    initial = dict(await _raw(current))
    tensor = torch.as_tensor(initial["samples"])
    compression = int(vae_compression)
    if compression <= 0:
        raise ValueError("vae_compression must be greater than zero")
    factor, count = float(upscale_factor), int(steps)
    if not math.isfinite(factor) or factor < 1.0:
        raise ValueError("upscale_factor must be finite and at least 1")
    if count < 1:
        raise ValueError("steps must be at least 1")
    if step_mode not in {"simple", "geometric"}:
        raise ValueError(f"unknown iterative upscale mode {step_mode!r}")

    base_height = int(tensor.shape[-2]) * compression
    base_width = int(tensor.shape[-1]) * compression
    noise_mask = initial.get("noise_mask")
    unit = (
        factor ** (1.0 / count)
        if step_mode == "geometric"
        else max(0.0, (factor - 1.0) / count)
    )
    scale = 1.0
    for index in range(count - 1):
        scale = scale * unit if step_mode == "geometric" else scale + unit
        current = await _pixel_upscale_step(
            current,
            base_width * scale,
            base_height * scale,
            spec,
            noise_mask,
            (index, count),
            emit_preview,
        )
    if scale < factor:
        current = await _pixel_upscale_step(
            current,
            base_width * factor,
            base_height * factor,
            spec,
            noise_mask,
            (count - 1, count),
            emit_preview,
        )
    return current, spec["vae"]


async def _iterative_image_upscale(
    pixels,
    upscale_factor,
    steps,
    temp_prefix,
    upscaler,
    vae,
    step_mode="simple",
    vae_compression=8,
    **kwargs,
):
    spec = _pixel_upscaler_spec(upscaler)
    image = _image4(await _raw(pixels))
    image_ref = await sdk.ImageRef._from_raw(image)
    if bool(spec.get("_tiled_sampling", False)):
        latent = await vae.encode_tiled(
            image_ref,
            tile_x=int(spec["tile_size"]),
            tile_y=int(spec["tile_size"]),
            overlap=int(spec.get("overlap", 64)),
        )
    else:
        latent = await vae.encode(image_ref)
    refined, _provider_vae = await _iterative_latent_upscale(
        latent,
        upscale_factor,
        steps,
        temp_prefix,
        upscaler,
        step_mode,
        vae_compression,
        **kwargs,
    )
    if bool(spec.get("_tiled_sampling", False)):
        result_ref = await vae.decode_tiled(
            refined,
            tile_size=int(spec["tile_size"]),
            overlap=int(spec.get("overlap", 64)),
        )
    else:
        result_ref = await vae.decode(refined)
    return _one(result_ref)


async def _image_sender(
    images, filename_prefix="ImgSender", link_id=0, **_kwargs,
):
    display = await _ctx().output.save_images(
        images, filename_prefix=str(filename_prefix)
    )
    ui = dict(display)
    saved = list(ui.get("images") or [])
    if saved:
        ui["secure_send"] = [{
            "kind": "image",
            "link_id": int(link_id),
            "asset": saved[0],
            "images": saved,
        }]
    return {"ui": ui, "result": (images,)}


async def _image_receiver(
    image, save_to_workflow=False, image_data="", **_kwargs,
):
    if bool(save_to_workflow) and image_data:
        payload = str(image_data)
        if "," in payload:
            payload = payload.split(",", 1)[1]
        data = base64.b64decode(payload, validate=True)
    else:
        folder, name = _annotated_asset(image)
        asset = await _ctx().assets.resolve(folder, name)
        data = await _ctx().assets.read_bytes(asset)
    loaded = Image.open(bytes_io.BytesIO(data))
    loaded.load()
    array = np.asarray(loaded.convert("RGBA")).astype(np.float32) / 255.0
    pixels = torch.from_numpy(array[..., :3]).unsqueeze(0)
    alpha = 1.0 - torch.from_numpy(array[..., 3]).unsqueeze(0)
    return pixels, alpha


async def _latent_sender(
    samples,
    filename_prefix="latents/LatentSender",
    link_id=0,
    preview_method="Latent2RGB-SDXL",
    **_kwargs,
):
    display = await _ctx().output.save_latent(
        samples,
        filename_prefix=str(filename_prefix),
        preview_method=str(preview_method),
    )
    artifact = display.get("artifact")
    images = list(display.get("images") or [])
    ui = {key: value for key, value in display.items() if key != "artifact"}
    if artifact:
        ui["secure_send"] = [{
            "kind": "latent",
            "link_id": int(link_id),
            "asset": artifact,
            "images": images,
        }]
    return {"ui": ui, "result": ()}


async def _legacy_preview_latent(ref):
    """Decode legacy EXIF/ZIP latent.png data inside the sandbox."""
    data = await _ctx().assets.read_bytes(ref)
    image = Image.open(bytes_io.BytesIO(data))
    image.load()
    comment = image.getexif().get(37510)
    if not isinstance(comment, bytes):
        raise ValueError("legacy latent preview has no EXIF UserComment")
    with zipfile.ZipFile(bytes_io.BytesIO(comment), mode="r") as archive:
        names = archive.namelist()
        if names != ["latent"]:
            raise ValueError("legacy latent preview must contain one latent member")
        info = archive.getinfo("latent")
        if info.file_size > 256 * 1024 * 1024:
            raise ValueError("legacy latent payload exceeds 256 MiB")
        if info.compress_size and info.file_size / info.compress_size > 100:
            raise ValueError("legacy latent payload has an unsafe compression ratio")
        payload = archive.read("latent")
    from safetensors.torch import load

    value = load(payload)
    tensor = value.get("latent_tensor")
    if not isinstance(tensor, torch.Tensor) or tensor.ndim not in (4, 5):
        raise ValueError("legacy latent payload has no valid latent_tensor")
    return {"samples": tensor.float()}


async def _latent_receiver(latent="", **_kwargs):
    if not str(latent or "").strip():
        return _one({"samples": torch.zeros((1, 4, 8, 8))})
    folder, name = _annotated_asset(latent)
    asset = await _ctx().assets.resolve(folder, name)
    parent = PurePosixPath(name).parent
    descriptor = {
        "filename": PurePosixPath(name).name,
        "subfolder": "" if str(parent) == "." else str(parent),
        "type": folder,
    }
    if name.lower().endswith(".latent.png"):
        value = await _legacy_preview_latent(asset)
    else:
        value = await _ctx().assets.load_latent(asset)
    return {"ui": {"latents": [descriptor]}, "result": (value,)}


async def _preview_bridge(images, **_kwargs):
    value = _image4(await _raw(images))
    reference = await sdk.ImageRef._from_raw(value)
    display = await _ctx().ui.preview_images(reference)
    mask = torch.zeros((value.shape[0], value.shape[1], value.shape[2]))
    return {"ui": display, "result": (value, mask)}


async def _preview_bridge_latent(latent, vae_opt=None, **_kwargs):
    value = await _raw(latent)
    shape = value["samples"].shape
    mask = torch.zeros((shape[0], shape[2] * 8, shape[3] * 8))
    ui = {}
    if vae_opt is not None:
        image = await vae_opt.decode(latent)
        ui = await _ctx().ui.preview_images(image)
    return {"ui": ui, "result": (latent, mask)}


# ---------------------------------------------------------------------------
# Frozen surface registration and security declarations
# ---------------------------------------------------------------------------

_HANDLERS: dict[str, tuple[Any, tuple[str, ...]]] = {
    node_id: (
        unsupported(
            node_id,
            "the upstream implementation requires a detector, plugin object, "
            "host callback, arbitrary model path, or another capability that "
            "does not yet have a closed Secure Nodes primitive",
        ),
        (),
    )
    for node_id in SCHEMAS
}
_REQUIRED_WEIGHTS: dict[
    str, tuple[sdk.HuggingFaceWeight, ...]
] = {}


def _set(node_ids, handler, *permissions):
    for node_id in node_ids:
        if node_id not in SCHEMAS:
            raise RuntimeError(f"unknown Impact Pack schema {node_id}")
        _HANDLERS[node_id] = (handler, tuple(permissions))


_set({"ImpactCompare"}, _compare)
_set({"ImpactIsNotEmptySEGS"}, _not_empty_segs, "raw")
_set({"ImpactConditionalBranch", "ImpactConditionalBranchSelMode"}, _branch)
_set({"ImpactConvertDataType"}, _convert)
_set({"ImpactIfNone"}, _if_none)
_set({"ImpactLogicalOperators"}, _logical)
_set({"ImpactConditionalStopIteration"}, _conditional_stop, "ui.workflow")
_set({"ImpactNeg"}, _neg)
_set({"ImpactInt", "ImpactFloat", "ImpactBoolean"}, _identity)
_set({"ImpactValueReceiver"}, _value_receiver)
_set({"ImpactValueSender"}, _value_sender, "ui.workflow")
_set({"ImpactImageInfo"}, _image_info, "raw")
_set({"ImpactLatentInfo"}, _latent_info, "raw")
_set({"ImpactMinMax"}, _minmax)
_set({"ImpactQueueTrigger"}, _queue_passthrough, "ui.workflow")
_set({"ImpactQueueTriggerCountdown"}, _queue_countdown, "graph", "ui.workflow")
_set({"ImpactSetWidgetValue"}, _set_widget_value, "ui.workflow")
_set({"ImpactNodeSetMuteState"}, _set_mute_state, "ui.workflow")
_set({"ImpactSleep"}, _sleep)
_set(
    {"ImpactRemoteBoolean", "ImpactRemoteInt"},
    unsupported(
        "Impact remote widget input",
        "cross-node prompt rewriting before execution is outside graph "
        "dataflow and is not permitted",
    ),
)
_set(
    {"ImpactControlBridge"},
    _control_bridge,
    "graph",
    "graph.block",
    "ui.workflow",
)
_set({"ImpactExecutionOrderController"}, _execution_order)
_set({"ImpactListBridge"}, _list_bridge)


_set({"ToBasicPipe"}, _to_basic)
_set({"FromBasicPipe"}, _from_basic)
_set({"FromBasicPipe_v2"}, _from_basic_v2)
_set({"AnyPipeToBasic"}, _any_to_basic)
_set({"EditBasicPipe"}, _edit_basic)
_set({"ToDetailerPipe", "ToDetailerPipeSDXL"}, _to_detailer)
_set({"BasicPipeToDetailerPipe", "BasicPipeToDetailerPipeSDXL"}, _basic_to_detailer)
_set({"FromDetailerPipe"}, _from_detailer)
_set({"FromDetailerPipe_v2"}, _from_detailer_v2)
_set({"FromDetailerPipeSDXL"}, _from_detailer_sdxl)
_set({"DetailerPipeToBasicPipe"}, _detailer_to_basic)
_set({"EditDetailerPipe", "EditDetailerPipeSDXL"}, _edit_detailer)


_set({"ImpactSwitch", "LatentSwitch", "SEGSSwitch"}, _switch, "graph")
_set({"ImpactInversedSwitch"}, _inverse_switch, "graph.block")
_set({"ImageMaskSwitch"}, _image_mask_switch)
_set({"RemoveNoiseMask"}, _remove_noise_mask, "raw")
_set({"ImpactLogger"}, _logger)
_set({"ImpactDummyInput"}, _dummy)
_set({"MasksToMaskList"}, _masks_to_list, "raw")
_set({"MaskListToMaskBatch"}, _mask_list_to_batch, "raw")
_set({"ImageListToImageBatch"}, _image_list_to_batch, "raw")
_set({"ImpactImageBatchToImageList"}, _image_batch_to_list, "raw")
_set({"ImpactMakeAnyList"}, _make_any_list)
_set({"ImpactMakeImageList"}, _make_image_list)
_set({"ImpactMakeImageBatch"}, _make_image_batch, "raw")
_set({"ImpactMakeMaskList"}, _make_mask_list)
_set({"ImpactMakeMaskBatch"}, _make_mask_batch, "raw")
_set({"ImpactSelectNthItemOfAnyList"}, _nth)
_set({"ReencodeLatent"}, _reencode)
_set({"ReencodeLatentPipe"}, _reencode_pipe)
_set({"ImpactStringSelector"}, _string_selector)
_set({"StringListToString"}, _string_list)
_set({"WildcardPromptFromString"}, _wildcard_prompt)


_set({"ToBinaryMask"}, _mask_binary, "raw")
_set({"ImpactFlattenMask"}, _mask_flatten, "raw")
_set({"BitwiseAndMask"}, _mask_and, "raw")
_set({"SubtractMask"}, _mask_subtract, "raw")
_set({"AddMask"}, _mask_add, "raw")
_set({"MaskRectArea"}, _rect_percent, "raw")
_set({"MaskRectAreaAdvanced"}, _rect_advanced, "raw")
_set({"MaskToSEGS", "MaskToSEGS_for_AnimateDiff"}, _mask_to_segs, "raw")
_set({"MediaPipeFaceMeshToSEGS"}, _mediapipe_facemesh_to_segs, "raw")
_set({"EmptySegs"}, _empty_segs)
_set({"SegsToCombinedMask"}, _segs_to_mask, "raw")
_set({"ImpactSEGSToMaskList"}, _segs_to_mask_list, "raw")
_set({"ImpactSEGSToMaskBatch"}, _segs_to_mask_batch, "raw")
_set({"ImpactSegsAndMask", "ImpactSegsAndMaskForEach"}, _segs_and_mask, "raw")
_set({"BitwiseAndMaskForEach"}, _segs_and_segs, "raw")
_set({"SubtractMaskForEach"}, _segs_subtract, "raw")
_set({"ImpactDecomposeSEGS"}, _decompose, "raw")
_set({"ImpactAssembleSEGS"}, _assemble, "raw")
_set({"ImpactFrom_SEG_ELT"}, _from_seg, "raw")
_set({"ImpactFrom_SEG_ELT_bbox", "ImpactFrom_SEG_ELT_crop_region"}, _from_box)
_set({"ImpactEdit_SEG_ELT"}, _edit_seg, "raw")
_set({"ImpactDilateMask"}, _dilate_mask, "raw")
_set({"ImpactGaussianBlurMask"}, _blur_mask, "raw")
_set({"ImpactDilateMaskInSEGS"}, _dilate_segs, "raw")
_set({"ImpactGaussianBlurMaskInSEGS"}, _blur_segs, "raw")
_set({"ImpactDilate_Mask_SEG_ELT"}, _dilate_seg, "raw")
_set({"ImpactScaleBy_BBOX_SEG_ELT"}, _scale_bbox, "raw")
_set({"ImpactCount_Elts_in_SEGS"}, _count_segs, "raw")
_set({"ImpactSEGSLabelAssign"}, _label_assign, "raw")
_set({"ImpactSEGSLabelFilter"}, _label_filter, "raw")
_set({"ImpactSEGSOrderedFilter"}, _ordered_filter, "raw")
_set({"ImpactSEGSRangeFilter"}, _range_filter, "raw")
_set({"ImpactSEGSNMSFilter"}, _nms_filter, "raw")
_set({"ImpactSEGSIntersectionFilter"}, _intersection_filter, "raw")
_set({"ImpactSEGSConcat"}, _concat_segs, "raw")
_set({"ImpactSEGSMerge"}, _merge_segs, "raw")
_set({"ImpactSEGSPicker"}, _picker, "raw")
_set({"RemoveImageFromSEGS"}, _remove_seg_images, "raw")
_set({"SetDefaultImageForSEGS"}, _default_seg_images, "raw")
_set({"SEGSToImageList"}, _segs_to_images, "raw")
_set({"SEGSPreview"}, _segs_preview, "raw")
_set({"SEGSPreviewCNet"}, _segs_preview_cnet)
_set({"SEGSPaste"}, _paste_segs, "raw")
_set({"ImpactControlNetClearSEGS"}, _clear_control)
_set({"ImpactIPAdapterApplySEGS"}, _ipadapter_apply_segs, "raw")
_set({"ImpactControlNetApplySEGS"}, _controlnet_apply_segs(False), "raw")
_set(
    {"ImpactControlNetApplyAdvancedSEGS"},
    _controlnet_apply_segs(True),
    "raw",
)
_set({"ImpactMakeTileSEGS"}, _tile_segs, "raw")
_set({"BboxDetectorCombined_v2"}, _bbox_detector_combined, "raw", "assets")
_set({"BboxDetectorSEGS"}, _bbox_detector_segs, "raw", "assets")
_set({"SegmDetectorCombined_v2"}, _segm_detector_combined, "raw", "assets")
_set({"SegmDetectorSEGS"}, _segm_detector_segs, "raw", "assets")
_set({"ONNXDetectorSEGS"}, _bbox_detector_segs, "raw", "assets")
_set({"ImpactSimpleDetectorSEGS"}, _simple_detector_segs, "raw", "assets")
_set({"ImpactSimpleDetectorSEGSPipe"}, _simple_detector_pipe, "raw", "assets")
_set(
    {"ImpactSimpleDetectorSEGS_for_AD"},
    _simple_detector_animatediff,
    "raw", "assets",
)
_set({"SAMLoader"}, _sam_loader, "models")
_set({"SAMDetectorCombined"}, _sam_detector_combined, "raw")
_set({"SAMDetectorSegmented"}, _sam_detector_segmented, "raw")
_set({"ImpactSAM2VideoDetectorSEGS"}, _sam2_video_detector_segs, "raw")


_set({"ImpactWildcardProcessor"}, _wildcard_process, "assets")
_set({"ImpactWildcardEncode"}, _wildcard_encode, "assets")
_set({"ImpactSchedulerAdapter"}, _scheduler_adapter)
_set({"ImpactCombineConditionings"}, _combine_conditionings)
_set({"ImpactConcatConditionings"}, _concat_conditionings)
_set({"ImpactNegativeConditioningPlaceholder"}, _negative_placeholder, "raw")
_set({"CombineRegionalPrompts"}, _combine_regional)
_set({"RegionalPrompt"}, _regional_prompt)
_set({"KSamplerProvider"}, _provider("ksampler"))
_set({"TiledKSamplerProvider"}, _provider("tiled_ksampler"))
_set({"KSamplerAdvancedProvider"}, _provider("ksampler_advanced"))
_set({"GITSSchedulerFuncProvider"}, _provider("gits_scheduler"))
_set({"TwoSamplersForMask"}, _two_samplers_for_mask, "raw", "sample")
_set(
    {"TwoAdvancedSamplersForMask"},
    _two_advanced_samplers_for_mask,
    "raw", "sample",
)
_set({"RegionalSampler"}, _regional_sampler, "raw", "sample")
_set(
    {"RegionalSamplerAdvanced"},
    _regional_sampler_advanced,
    "raw", "sample",
)
_set({"ImpactKSamplerBasicPipe"}, _sample_simple, "sample")
_set({"ImpactKSamplerAdvancedBasicPipe"}, _sample_advanced, "sample")
_set({"LatentPixelScale"}, _latent_pixel_scale, "raw")
_set({"IterativeLatentUpscale"}, _iterative_latent_upscale, "raw", "sample")
_set({"IterativeImageUpscale"}, _iterative_image_upscale, "raw", "sample")
_set(
    {"DetailerForEach", "DetailerForEachAutoRetry"},
    _detailer_for_each,
    "raw", "sample", "assets",
)
_set(
    {"DetailerForEachDebug"},
    _detailer_debug,
    "raw", "sample", "assets",
)
_set(
    {"DetailerForEachPipe"},
    _detailer_pipe_node,
    "raw", "sample", "assets",
)
_set(
    {"DetailerForEachDebugPipe"},
    _detailer_debug_pipe,
    "raw", "sample", "assets",
)
_set(
    {"SEGSDetailer"},
    _segs_detailer,
    "raw", "sample", "assets",
)
_set(
    {"FaceDetailer"},
    _face_detailer,
    "raw", "sample", "assets",
)
_set(
    {"FaceDetailerPipe"},
    _face_detailer_pipe,
    "raw", "sample", "assets",
)
_set(
    {"MaskDetailerPipe"},
    _mask_detailer_pipe,
    "raw", "sample", "assets",
)
_set(
    {"SEGSUpscaler"},
    _segs_upscaler,
    "raw", "sample",
)
_set(
    {"SEGSUpscalerPipe"},
    _segs_upscaler_pipe,
    "raw", "sample",
)
_set(
    {"SEGSDetailerForAnimateDiff"},
    _segs_detailer_animatediff,
    "raw", "sample",
)
_set(
    {"DetailerForEachPipeForAnimateDiff"},
    _detailer_pipe_animatediff,
    "raw", "sample",
)
_set({"ImageSender"}, _image_sender, "output")
_set({"ImageReceiver"}, _image_receiver, "assets", "raw")
_set({"LatentSender"}, _latent_sender, "output")
_set({"LatentReceiver"}, _latent_receiver, "assets", "raw")
_set({"PreviewBridge"}, _preview_bridge, "raw", "ui")
_set({"PreviewBridgeLatent"}, _preview_bridge_latent, "raw", "ui")


_PURE_PROVIDER_NODES = {
    "BlackPatchRetryHookProvider", "CfgScheduleHookProvider",
    "CoreMLDetailerHookProvider", "CustomSamplerDetailerHookProvider",
    "DenoiseScheduleHookProvider", "DenoiseSchedulerDetailerHookProvider",
    "NoiseInjectionDetailerHookProvider",
    "NoiseInjectionHookProvider", "PixelKSampleUpscalerProvider",
    "PixelKSampleUpscalerProviderPipe", "PixelTiledKSampleUpscalerProvider",
    "PixelTiledKSampleUpscalerProviderPipe",
    "SEGSLabelFilterDetailerHookProvider", "SEGSOrderedFilterDetailerHookProvider",
    "SEGSRangeFilterDetailerHookProvider", "StepsScheduleHookProvider",
    "TwoSamplersForMaskUpscalerProvider", "TwoSamplersForMaskUpscalerProviderPipe",
    "UnsamplerDetailerHookProvider", "UnsamplerHookProvider",
    "VariationNoiseDetailerHookProvider",
}
for _node_id in _PURE_PROVIDER_NODES:
    _set({_node_id}, _provider(_node_id))

_set(
    {"LamaRemoverDetailerHookProvider"},
    _lama_remover_hook_provider,
    "models",
)
_REQUIRED_WEIGHTS["LamaRemoverDetailerHookProvider"] = (_BIG_LAMA_WEIGHT,)
_set({"PreviewDetailerHookProvider"}, _preview_hook_provider)
_set({"DetailerHookCombine"}, _combine_provider("detailer_hook_chain"))
_set({"PixelKSampleHookCombine"}, _combine_provider("pixel_hook_chain"))


_set(
    {"ImpactHFTransformersClassifierProvider"},
    _hf_classifier_provider,
    "assets",
    "models.download",
)
_REQUIRED_WEIGHTS["ImpactHFTransformersClassifierProvider"] = tuple(
    spec["weight"] for spec in _HF_CLASSIFIERS.values())
_set({"ImpactSEGSClassify"}, _segs_classify, "assets", "raw")
_set({"CLIPSegDetectorProvider"}, _clipseg_detector_provider, "models")
_REQUIRED_WEIGHTS["CLIPSegDetectorProvider"] = (_CLIPSEG_WEIGHT,)
_set({"ONNXDetectorProvider"}, _onnx_detector_provider)


if set(_HANDLERS) != set(SCHEMAS):
    raise RuntimeError(
        "Impact Pack secure conversion coverage changed: "
        f"missing={sorted(set(SCHEMAS) - set(_HANDLERS))}, "
        f"extra={sorted(set(_HANDLERS) - set(SCHEMAS))}"
    )


_LAZY_STATUS = {
    "ImpactConditionalBranch": _branch_lazy,
    "ImpactSwitch": _switch_lazy,
    "LatentSwitch": _switch_lazy,
    "SEGSSwitch": _switch_lazy,
}


NODE_CLASS_MAPPINGS = {
    node_id: bind_node(
        node_id,
        handler,
        permissions=permissions,
        required_weights=_REQUIRED_WEIGHTS.get(node_id, ()),
        check_lazy_status=_LAZY_STATUS.get(node_id),
    )
    for node_id, (handler, permissions) in _HANDLERS.items()
}
NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: SCHEMAS[node_id]["schema"]["attrs"]["display_name"]
    for node_id in NODE_CLASS_MAPPINGS
}


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
