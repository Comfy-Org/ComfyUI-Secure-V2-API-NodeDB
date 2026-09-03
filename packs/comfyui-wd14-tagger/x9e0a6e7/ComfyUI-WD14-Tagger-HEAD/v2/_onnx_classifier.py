"""WD14 ONNX inference owned by the WD14 pack."""
from __future__ import annotations

import asyncio
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import torch
from PIL import Image


_CACHE: "OrderedDict[str, _Entry]" = OrderedDict()
_MAX_CACHED = 3
_MAX_PIXELS = 268_435_456
_MAX_BATCH = 64
_MAX_WEIGHT_BYTES = 4 * 1024 * 1024 * 1024
_READ_CHUNK_BYTES = 16 * 1024 * 1024


@dataclass
class _Entry:
    session: Any
    input_name: str
    output_name: str
    input_height: int
    input_width: int
    class_count: int
    lock: threading.Lock = field(default_factory=threading.Lock)


def _build(data: bytes) -> _Entry:
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise RuntimeError("WD14 classification requires onnxruntime") from exc
    options = ort.SessionOptions()
    options.log_severity_level = 3
    available = set(ort.get_available_providers())
    providers = [
        provider
        for provider in ("CUDAExecutionProvider", "CPUExecutionProvider")
        if provider in available
    ]
    if not providers:
        raise RuntimeError("ONNX Runtime has no supported execution provider")
    try:
        session = ort.InferenceSession(data, sess_options=options, providers=providers)
    except Exception as exc:
        raise ValueError("WD14 ONNX classifier could not be loaded") from exc
    inputs = session.get_inputs()
    outputs = session.get_outputs()
    if len(inputs) != 1 or len(outputs) != 1:
        raise ValueError("WD14 classifier must have one input and output")
    model_input = inputs[0]
    model_output = outputs[0]
    if model_input.type != "tensor(float)" or model_output.type not in {
        "tensor(float)",
        "tensor(float16)",
        "tensor(double)",
    }:
        raise ValueError("WD14 classifier must use floating-point tensors")
    input_shape = model_input.shape
    output_shape = model_output.shape
    if len(input_shape) != 4 or len(output_shape) != 2 or input_shape[3] != 3:
        raise ValueError("WD14 classifier must use fixed NHWC image inputs")
    height, width, class_count = input_shape[1], input_shape[2], output_shape[1]
    if (
        type(height) is not int
        or type(width) is not int
        or not 1 <= height <= 4096
        or not 1 <= width <= 4096
    ):
        raise ValueError("WD14 classifier spatial dimensions must be fixed")
    if type(class_count) is not int or not 1 <= class_count <= 16_384:
        raise ValueError("WD14 classifier output count is outside the safe range")
    return _Entry(
        session,
        model_input.name,
        model_output.name,
        height,
        width,
        class_count,
    )


async def _entry(ctx: Any, weight: str) -> _Entry:
    if not isinstance(weight, str) or not weight.lower().endswith(".onnx"):
        raise ValueError("WD14 classifiers must use .onnx files")
    cached = _CACHE.pop(weight, None)
    if cached is not None:
        _CACHE[weight] = cached
        return cached
    asset = await ctx.assets.resolve("onnx", weight)
    size = await ctx.assets.size(asset)
    if not 1 <= size <= _MAX_WEIGHT_BYTES:
        raise ValueError("WD14 classifier weight size is outside the safe range")
    chunks = [
        await ctx.assets.read_range(
            asset,
            offset=offset,
            length=min(_READ_CHUNK_BYTES, size - offset),
        )
        for offset in range(0, size, _READ_CHUNK_BYTES)
    ]
    data = b"".join(chunks)
    loaded = await asyncio.to_thread(_build, data)
    while len(_CACHE) >= _MAX_CACHED:
        _CACHE.popitem(last=False)
    _CACHE[weight] = loaded
    return loaded


def _prepare(frame: torch.Tensor, height: int, width: int) -> np.ndarray:
    source = Image.fromarray(
        np.clip(frame.detach().cpu().numpy()[..., :3] * 255.0, 0, 255).astype(
            np.uint8
        )
    )
    ratio = min(width / source.width, height / source.height)
    resized_size = (
        max(1, int(source.width * ratio)),
        max(1, int(source.height * ratio)),
    )
    resized = source.resize(resized_size, Image.Resampling.LANCZOS)
    prepared = Image.new("RGB", (width, height), (255, 255, 255))
    prepared.paste(
        resized,
        ((width - resized_size[0]) // 2, (height - resized_size[1]) // 2),
    )
    array = np.asarray(prepared, dtype=np.float32)[..., ::-1]
    return np.ascontiguousarray(array[None, ...], dtype=np.float32)


async def predict(ctx: Any, weight: str, images: Any) -> np.ndarray:
    entry = await _entry(ctx, weight)
    pixels = await images.raw()
    if (
        not isinstance(pixels, torch.Tensor)
        or pixels.ndim != 4
        or pixels.shape[-1] < 3
        or not 1 <= len(pixels) <= _MAX_BATCH
    ):
        raise ValueError("WD14 images must be a 1-64 item BHWC RGB batch")
    height, width = map(int, pixels.shape[1:3])
    if (
        height <= 0
        or width <= 0
        or height * width * len(pixels) > _MAX_PIXELS
        or not bool(torch.isfinite(pixels[..., :3]).all())
    ):
        raise ValueError("WD14 image values are invalid")

    def infer() -> np.ndarray:
        rows = []
        with entry.lock:
            for frame in pixels:
                output = entry.session.run(
                    [entry.output_name],
                    {
                        entry.input_name: _prepare(
                            frame, entry.input_height, entry.input_width
                        )
                    },
                )[0]
                output = np.asarray(output)
                if output.shape != (1, entry.class_count):
                    raise RuntimeError("WD14 classifier returned an invalid score shape")
                row = output[0].astype(np.float32, copy=True)
                if not np.isfinite(row).all():
                    raise RuntimeError("WD14 classifier returned non-finite scores")
                rows.append(row)
        return np.stack(rows, axis=0)

    return await asyncio.to_thread(infer)


async def select_indices(
    scores: Any,
    batch_index: int,
    bounds: tuple[int, int] | None,
    threshold: float,
) -> list[int]:
    if bounds is None:
        return []
    start, end = bounds
    matrix = np.asarray(scores)
    if (
        matrix.ndim != 2
        or not 0 <= int(batch_index) < matrix.shape[0]
        or not 0 <= start <= end <= matrix.shape[1]
    ):
        raise ValueError("classifier returned an invalid score matrix")
    row = matrix[int(batch_index), start:end]
    if not np.isfinite(row).all():
        raise ValueError("classifier returned a non-finite score")
    return (np.flatnonzero(row > float(threshold)) + start).tolist()
