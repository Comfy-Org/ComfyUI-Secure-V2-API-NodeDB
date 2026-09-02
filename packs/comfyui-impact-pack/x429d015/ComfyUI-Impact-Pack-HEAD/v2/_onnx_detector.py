"""ONNX object detection, owned by this pack.

The detector is one pack's model family rather than part of the node API, so
loading the graph and interpreting its outputs live here. The pack asks the
host only to resolve a declared asset; the graph itself is executed inside this
pack's sandbox, which is where an untrusted model belongs.

The detector crosses to other packs as a plain ``secure_kind`` recipe, matching
how this pack already exports its Ultralytics detector.
"""
from __future__ import annotations

import asyncio
import math
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

import numpy as np
import torch


SECURE_KIND = "impact.onnx_detector"
ASSET_FOLDER = "onnx"

# A detector image is bounded so a graph cannot ask for an unbounded allocation.
_MAX_PIXELS = 268_435_456
_MAX_OBJECTS = 4096

# BGR means the model was trained on Caffe-style inputs.
_MEAN_BGR = (103.939, 116.779, 123.68)


@dataclass
class _Entry:
    net: Any
    lock: threading.Lock = field(default_factory=threading.Lock)


_CACHE: "OrderedDict[str, _Entry]" = OrderedDict()
_MAX_CACHED = 2


def recipe(weight: str) -> dict[str, str]:
    """The value this pack hands downstream for an ONNX detector."""
    if not isinstance(weight, str) or not weight.lower().endswith(".onnx"):
        raise ValueError("ONNX detectors must use .onnx model files")
    if ".." in PurePosixPath(weight).parts:
        raise ValueError("ONNX detector weight name is invalid")
    return {"secure_kind": SECURE_KIND, "weight": weight}


def is_recipe(value: Any) -> bool:
    return isinstance(value, dict) and value.get("secure_kind") == SECURE_KIND


def validated(value: Any) -> dict[str, str]:
    if not is_recipe(value):
        raise TypeError("ONNX_DETECTOR must be a Secure Nodes ONNX recipe")
    return recipe(value.get("weight"))


def _build(data: bytes) -> _Entry:
    import tempfile

    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("ONNX detection requires OpenCV DNN") from exc
    with tempfile.NamedTemporaryFile(suffix=".onnx") as staged:
        staged.write(data)
        staged.flush()
        return _Entry(net=cv2.dnn.readNetFromONNX(staged.name))


async def _entry(ctx: Any, value: Any) -> _Entry:
    spec = validated(value)
    cached = _CACHE.pop(spec["weight"], None)
    if cached is not None:
        _CACHE[spec["weight"]] = cached
        return cached
    asset = await ctx.assets.resolve(ASSET_FOLDER, spec["weight"])
    # The guest gets content, never a host path, so the graph is staged in this
    # pack's own sandboxed scratch before OpenCV reads it.
    data = await ctx.assets.read_bytes(asset)
    loaded = await asyncio.to_thread(_build, data)
    while len(_CACHE) >= _MAX_CACHED:
        _CACHE.popitem(last=False)
    _CACHE[spec["weight"]] = loaded
    return loaded


def _outputs_to_detections(arrays: list[np.ndarray]) -> list[dict[str, Any]]:
    """Pick labels, scores and xyxy boxes out of the model's raw outputs."""
    labels = next(
        (v for v in arrays
         if np.issubdtype(v.dtype, np.integer) and v.size), None)
    boxes = next(
        (v for v in arrays
         if v.ndim >= 2 and v.shape[-1] == 4 and v.size), None)
    scores = next(
        (v for v in arrays
         if np.issubdtype(v.dtype, np.floating) and v is not boxes and v.size
         and (v.ndim <= 2 or v.shape[-1] == 1)), None)
    if labels is None or scores is None or boxes is None:
        raise RuntimeError(
            "ONNX detector must return integer labels, scores, and xyxy boxes")
    labels = labels.reshape(-1)
    scores = scores.reshape(-1)
    boxes = boxes.reshape(-1, 4)
    count = min(len(labels), len(scores), len(boxes))
    # A label of -1 marks the end of the populated rows in a fixed-size output.
    invalid = np.flatnonzero(labels[:count] == -1)
    if len(invalid):
        count = int(invalid[0])
    if count > _MAX_OBJECTS:
        raise RuntimeError(
            f"ONNX detector returned more than {_MAX_OBJECTS} objects")

    result = []
    for label, score, box in zip(
        labels[:count], scores[:count], boxes[:count], strict=True,
    ):
        values = [float(value) for value in box]
        confidence = float(score)
        if not math.isfinite(confidence) or not all(
            math.isfinite(value) for value in values
        ):
            raise RuntimeError("ONNX detector returned non-finite values")
        result.append({
            "label": int(label), "score": confidence, "box": values,
        })
    return result


async def detect(
    ctx: Any, value: Any, pixels: torch.Tensor,
) -> list[dict[str, Any]]:
    """Detect objects in one BHWC RGB image."""
    if (not isinstance(pixels, torch.Tensor) or pixels.ndim != 4
            or pixels.shape[0] != 1 or pixels.shape[-1] < 3):
        raise ValueError("ONNX detection requires one BHWC RGB image")
    height, width = map(int, pixels.shape[1:3])
    if height <= 0 or width <= 0 or height * width > _MAX_PIXELS:
        raise ValueError("ONNX detector image dimensions are invalid")

    entry = await _entry(ctx, value)
    source = np.ascontiguousarray(
        pixels[0, ..., :3].detach().cpu().numpy()[..., ::-1] * 255.0,
        dtype=np.float32,
    )
    source -= np.asarray(_MEAN_BGR, dtype=np.float32)

    def infer() -> list[np.ndarray]:
        with entry.lock:
            entry.net.setInput(source[None, ...])
            outputs = entry.net.forward(
                entry.net.getUnconnectedOutLayersNames())
        if isinstance(outputs, np.ndarray):
            outputs = [outputs]
        return [np.asarray(output) for output in outputs]

    return _outputs_to_detections(await asyncio.to_thread(infer))
