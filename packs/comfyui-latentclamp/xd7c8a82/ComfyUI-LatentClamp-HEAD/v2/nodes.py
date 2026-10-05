"""Secure Nodes V2 implementation of Latent Clamp."""

from __future__ import annotations

import math

import torch
from comfy_api.latest import ComfyExtension, io

MAX_ELEMENTS = 268_435_456
MAX_DIMENSION = 16_384
MAX_RANK = 6


def _bounded_float(name: str, value: float, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    value = float(value)
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be finite and in [{minimum}, {maximum}]")
    return value


def _validate_latent(latent: dict) -> torch.Tensor:
    if not isinstance(latent, dict):
        raise TypeError("Latent Clamp expected a LATENT dictionary")
    samples = latent.get("samples")
    if not isinstance(samples, torch.Tensor):
        raise TypeError("LATENT samples must be a tensor")
    if not 1 <= samples.ndim <= MAX_RANK:
        raise ValueError(f"LATENT samples rank must be in [1, {MAX_RANK}]")
    if any(not 1 <= int(dimension) <= MAX_DIMENSION for dimension in samples.shape):
        raise ValueError(f"LATENT dimensions must be in [1, {MAX_DIMENSION}]")
    if samples.numel() > MAX_ELEMENTS:
        raise ValueError("LATENT exceeds the element limit")
    if not samples.dtype.is_floating_point:
        raise TypeError("LATENT samples must use a floating-point dtype")
    return samples


class LatentClamp(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="LatentClamp",
            display_name="Latent Clamp",
            category="latent/advanced",
            inputs=[
                io.Latent.Input("samples"),
                io.Float.Input(
                    "min",
                    default=-1.0,
                    min=-10.0,
                    max=10.0,
                    step=0.01,
                    tooltip=(
                        "Values in `samples` below this value will be "
                        "multiplied by `outside_multiplier`."
                    ),
                ),
                io.Float.Input(
                    "max",
                    default=1.0,
                    min=-10.0,
                    max=10.0,
                    step=0.01,
                    tooltip=(
                        "Values in `samples` above this value will be "
                        "multiplied by `outside_multiplier`."
                    ),
                ),
                io.Float.Input(
                    "inside_multiplier",
                    default=1.0,
                    min=0.0,
                    max=10.0,
                    step=0.1,
                    tooltip=(
                        "Values in `samples` between `min` and `max` will be "
                        "multiplied by this value."
                    ),
                ),
                io.Float.Input(
                    "outside_multiplier",
                    default=0.5,
                    min=0.0,
                    max=10.0,
                    step=0.1,
                    tooltip=(
                        "Values in `samples` outside of `min` and `max` will "
                        "be multiplied by this value."
                    ),
                ),
                io.Float.Input(
                    "extra_noise",
                    default=0.0,
                    min=0.0,
                    max=100.0,
                    step=0.1,
                    tooltip=("Add compensatory noise to the values in `samples`."),
                ),
            ],
            outputs=[io.Latent.Output("samples")],
        )

    @classmethod
    def execute(
        cls,
        samples: dict,
        min: float,
        max: float,
        inside_multiplier: float,
        outside_multiplier: float,
        extra_noise: float,
    ) -> io.NodeOutput:
        tensor = _validate_latent(samples)
        minimum = _bounded_float("min", min, -10.0, 10.0)
        maximum = _bounded_float("max", max, -10.0, 10.0)
        inside = _bounded_float("inside_multiplier", inside_multiplier, 0.0, 10.0)
        outside = _bounded_float("outside_multiplier", outside_multiplier, 0.0, 10.0)
        noise = _bounded_float("extra_noise", extra_noise, 0.0, 100.0)

        mask_min = tensor < minimum
        mask_max = tensor > maximum
        mask_inside = ~mask_min & ~mask_max
        if noise:
            outside_noise = torch.randn_like(tensor) * noise * (1 - outside)
            inside_noise = torch.randn_like(tensor) * noise * (1 - inside)
        else:
            inside_noise = 0
            outside_noise = 0

        result = torch.where(mask_min, tensor * outside + outside_noise, tensor)
        result = torch.where(mask_max, result * outside + outside_noise, result)
        result = torch.where(mask_inside, result * inside + inside_noise, result)
        output = samples.copy()
        output["samples"] = result
        return io.NodeOutput(output)


NODE_CLASS_MAPPINGS = {"LatentClamp": LatentClamp}
NODE_DISPLAY_NAME_MAPPINGS = {"LatentClamp": "Latent Clamp"}


class LatentClampExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [LatentClamp]


async def comfy_entrypoint() -> LatentClampExtension:
    return LatentClampExtension()


__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "LatentClamp",
    "LatentClampExtension",
    "comfy_entrypoint",
]
