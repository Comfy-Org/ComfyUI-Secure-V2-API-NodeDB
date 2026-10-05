"""Secure V2 implementation of Krea 2 conditioning rebalancing."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import torch

from comfy_api.latest import ComfyExtension, io, sdk


PRESET_WEIGHTS = {
    "balanced": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 2.5, 5.0, 1.1, 4.0, 1.0],
    "detail": [0.8, 0.8, 0.9, 0.9, 1.0, 1.0, 1.2, 3.0, 6.0, 1.5, 5.0, 1.2],
    "subtle": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.5, 2.0, 1.0, 1.5, 1.0],
    "uniform": [1.0] * 12,
}
PRESET_NAMES = ["balanced", "detail", "subtle", "uniform", "custom"]
DEFAULT_WEIGHTS = ", ".join(str(value) for value in PRESET_WEIGHTS["balanced"])

MAX_WEIGHT_TEXT = 4096
MAX_WEIGHTS = 256
MAX_ITEMS = 4096
MAX_DEPTH = 32
MAX_TENSOR_ELEMENTS = 268_435_456
MAX_ABS_WEIGHT = 1_000_000.0


def parse_weights(text: str) -> list[float]:
    if not isinstance(text, str):
        raise TypeError("per_layer_weights must be a string")
    if len(text.encode("utf-8")) > MAX_WEIGHT_TEXT:
        raise ValueError("per_layer_weights is too large")
    parts = [
        part.strip()
        for part in text.replace(";", ",").split(",")
        if part.strip()
    ]
    if not 2 <= len(parts) <= MAX_WEIGHTS:
        raise ValueError(
            f"per_layer_weights needs between 2 and {MAX_WEIGHTS} values")
    try:
        values = [float(part) for part in parts]
    except ValueError as exc:
        raise ValueError(
            f"per_layer_weights has a non-numeric entry: {exc}") from exc
    if any(not math.isfinite(value) or abs(value) > MAX_ABS_WEIGHT for value in values):
        raise ValueError("per_layer_weights contains an invalid value")
    return values


def _rms(tensor: torch.Tensor) -> torch.Tensor:
    return tensor.pow(2).mean(dim=tuple(range(1, tensor.dim()))).sqrt()


def _scale_tensor(
    tensor: torch.Tensor,
    multiplier: float,
    per_layer_weights: Sequence[float] | None,
    renormalize: bool,
) -> torch.Tensor:
    if tensor.numel() > MAX_TENSOR_ELEMENTS:
        raise ValueError("conditioning tensor is too large")
    if tensor.dim() < 2:
        raise ValueError("conditioning tensor must have a batch dimension")
    if per_layer_weights is None or len(per_layer_weights) <= 1:
        return tensor * multiplier

    flat = int(tensor.shape[-1])
    layer_count = len(per_layer_weights)
    if flat % layer_count:
        return tensor * multiplier

    original_dtype = tensor.dtype
    reference_rms = _rms(tensor.float()) if renormalize else None
    output = tensor.float().view(
        *tensor.shape[:-1], layer_count, flat // layer_count)
    gains = torch.tensor(
        list(per_layer_weights), dtype=output.dtype, device=output.device)
    output = output * gains.view(
        *([1] * (output.dim() - 2)), layer_count, 1)
    output = output.view(*output.shape[:-2], flat)

    if renormalize and reference_rms is not None:
        new_rms = _rms(output).clamp_min(1e-8)
        output = output * (reference_rms / new_rms).view(
            -1, *([1] * (output.dim() - 1)))
    return output.to(original_dtype) * multiplier


def _scale_structure(
    value: Any,
    multiplier: float,
    per_layer_weights: Sequence[float] | None,
    renormalize: bool,
    *,
    depth: int = 0,
) -> Any:
    if depth > MAX_DEPTH:
        raise ValueError("conditioning structure is too deeply nested")
    if isinstance(value, torch.Tensor):
        return _scale_tensor(
            value, multiplier, per_layer_weights, renormalize)
    if isinstance(value, list):
        if len(value) > MAX_ITEMS:
            raise ValueError("conditioning list is too large")
        output = []
        for item in value:
            if (
                isinstance(item, (list, tuple))
                and len(item) == 2
                and isinstance(item[0], torch.Tensor)
                and isinstance(item[1], dict)
            ):
                output.append([
                    _scale_tensor(
                        item[0], multiplier, per_layer_weights, renormalize),
                    dict(item[1]),
                ])
            else:
                output.append(_scale_structure(
                    item, multiplier, per_layer_weights, renormalize,
                    depth=depth + 1))
        return output
    if isinstance(value, Mapping):
        if len(value) > MAX_ITEMS:
            raise ValueError("conditioning mapping is too large")
        return {
            key: _scale_structure(
                item, multiplier, per_layer_weights, renormalize,
                depth=depth + 1)
            for key, item in value.items()
        }
    return value


class ConditioningKrea2Rebalance(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ConditioningKrea2Rebalance",
            display_name="🎛️ Krea 2 Conditioning Control",
            category="conditioning/Krea2",
            description=(
                "Rebalance Krea 2's multi-layer text conditioning per tap, "
                "then apply a global gain."),
            inputs=[
                io.Conditioning.Input("conditioning"),
                io.Combo.Input(
                    "preset", options=PRESET_NAMES, default="balanced",
                    tooltip=(
                        "Named per-layer weight profile. Use 'custom' to "
                        "supply your own via per_layer_weights.")),
                io.String.Input(
                    "per_layer_weights", default=DEFAULT_WEIGHTS,
                    multiline=False,
                    tooltip=(
                        "Comma-separated gains, one per conditioning tap "
                        "(12 for Krea 2). Used only for custom.")),
                io.Float.Input(
                    "multiplier", default=1.0, min=-1000.0, max=1000.0,
                    step=0.01,
                    tooltip="Global gain applied after per-layer weighting."),
                io.Boolean.Input(
                    "renormalize", default=True,
                    tooltip=(
                        "Hold input RMS after per-layer weighting so tap "
                        "ratios change without inflating overall magnitude.")),
            ],
            outputs=[io.Conditioning.Output(display_name="conditioning")],
        )

    @classmethod
    async def execute(
        cls,
        conditioning: sdk.CondRef,
        preset: str = "balanced",
        per_layer_weights: str = "",
        multiplier: float = 1.0,
        renormalize: bool = True,
    ) -> io.NodeOutput:
        if preset not in PRESET_NAMES:
            raise ValueError("unknown Krea 2 conditioning preset")
        multiplier = float(multiplier)
        if not math.isfinite(multiplier) or not -1000.0 <= multiplier <= 1000.0:
            raise ValueError("multiplier must be finite and in [-1000, 1000]")
        weights = (
            parse_weights(per_layer_weights)
            if preset == "custom"
            else PRESET_WEIGHTS[preset]
        )
        source = await conditioning.value()
        output = _scale_structure(
            source, multiplier, weights, bool(renormalize))
        return io.NodeOutput(await sdk.CondRef.from_value(output))


NODE_CLASS_MAPPINGS = {
    "ConditioningKrea2Rebalance": ConditioningKrea2Rebalance,
}


class Krea2ConditioningExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint() -> Krea2ConditioningExtension:
    return Krea2ConditioningExtension()
