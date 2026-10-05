"""Secure Nodes V2 backend for ComfyUI CapitanZiT Scheduler."""

from __future__ import annotations

import json
import math
from typing import Any

from comfy_api.latest import io, sdk

from . import sampler_program


MAX_CUSTOM_SIGMAS_BYTES = 64 * 1024
MAX_CUSTOM_SIGMAS = 1024
MAX_SIGMA = 10_000.0


def _integer(value: int, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _number(value: float, name: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return result


def linear_sigmas(steps: int) -> list[float]:
    steps = _integer(steps, "steps", 1, 100)
    return [1.0 - index / steps for index in range(steps + 1)]


def smooth_cosine_sigmas(steps: int, denoise: float) -> list[float]:
    steps = _integer(steps, "steps", 4, 100)
    denoise = _number(denoise, "denoise", 0.0, 1.0)
    if steps == 1:
        values = [denoise]
    else:
        values = [
            denoise * (1.0 + math.cos(index / (steps - 1) * math.pi)) / 2.0
            for index in range(steps)
        ]
    return [*values, 0.0]


def klein_parametric_sigmas(
    steps: int,
    denoise: float,
    sigma_min: float,
    shift: float,
    curve: float,
) -> list[float]:
    steps = _integer(steps, "steps", 1, 100)
    denoise = _number(denoise, "denoise", 0.001, 2.0)
    sigma_min = _number(sigma_min, "sigma_min", 0.0, 1.0)
    shift = _number(shift, "shift", 0.01, 20.0)
    curve = _number(curve, "curve", 0.01, 10.0)
    values = []
    for index in range(steps + 1):
        t = index / steps
        if abs(curve - 1.0) > 0.001:
            t = t**curve
        if abs(shift - 1.0) > 0.001:
            t = t / (t + shift * (1.0 - t))
        values.append(denoise * (1.0 - t) + sigma_min * t)
    values[0] = denoise
    values[-1] = sigma_min
    if sigma_min > 1e-6:
        values.append(0.0)
    return values


def _drawn_sigmas(custom_sigmas: str) -> list[float] | None:
    if not isinstance(custom_sigmas, str):
        raise TypeError("custom_sigmas must be a string")
    if len(custom_sigmas.encode("utf-8")) > MAX_CUSTOM_SIGMAS_BYTES:
        raise ValueError("custom_sigmas exceeds the 65536-byte limit")
    try:
        decoded = json.loads(custom_sigmas)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(decoded, list) or len(decoded) < 2:
        return None
    if len(decoded) > MAX_CUSTOM_SIGMAS:
        raise ValueError(f"custom_sigmas exceeds the {MAX_CUSTOM_SIGMAS}-value limit")
    values = []
    for item in decoded:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return None
        value = float(item)
        if not math.isfinite(value) or not -MAX_SIGMA <= value <= MAX_SIGMA:
            raise ValueError("custom_sigmas contains an out-of-range value")
        values.append(value)
    if values[-1] > 1e-6:
        values.append(0.0)
    return values


async def _sigmas_ref(values: list[float]) -> sdk.TensorRef:
    import torch

    tensor = torch.tensor(values, dtype=torch.float32)
    return await sdk.TensorRef._from_raw(tensor)


class CapitanZiTLinearSigma(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="CapitanZiTLinearSigma",
            display_name="CapitanZiT Linear Sigma (for Z-Image Turbo)",
            category="sampling/custom_sampling/sigmas",
            description="Generates linear sigma schedule (1.0 → 0.0) for CapitanZiT",
            inputs=[io.Int.Input("steps", default=9, min=1, max=100, step=1)],
            outputs=[io.Sigmas.Output()],
        )

    @classmethod
    async def execute(cls, steps: int) -> io.NodeOutput:
        return io.NodeOutput(await _sigmas_ref(linear_sigmas(steps)))


class FlowMatchSchedulerKleinEdit(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="FlowMatchSchedulerKleinEdit",
            display_name="Klein Edit Scheduler",
            category="sampling/custom_sampling/schedulers",
            description="Full-control Klein Edit scheduler with interactive + drawable graph.",
            inputs=[
                io.Model.Input("model"),
                io.Int.Input(
                    "steps", default=4, min=1, max=100,
                    tooltip="Total sigma steps. Klein native=4.",
                ),
                io.Float.Input(
                    "denoise", default=1.0, min=0.001, max=2.0, step=0.001,
                    tooltip="Starting sigma / edit strength.",
                ),
                io.Float.Input(
                    "sigma_min", default=0.0, min=0.0, max=1.0, step=0.001,
                    tooltip="Ending sigma. Raise to 0.01-0.03 to soften final step.",
                ),
                io.Float.Input(
                    "shift", default=1.0, min=0.01, max=20.0, step=0.01,
                    tooltip="Timestep shift. >1=more steps at high sigma.",
                ),
                io.Float.Input(
                    "curve", default=1.0, min=0.01, max=10.0, step=0.01,
                    tooltip="Power curve. <1=bunch at start. >1=bunch at end.",
                ),
                io.String.Input("draw_mode", default="parametric", optional=True),
                io.String.Input("custom_sigmas", default="[]", optional=True),
            ],
            outputs=[io.Model.Output(), io.Sigmas.Output()],
        )

    @classmethod
    async def execute(
        cls,
        model: sdk.ModelRef,
        steps: int,
        denoise: float,
        sigma_min: float,
        shift: float,
        curve: float,
        draw_mode: str = "parametric",
        custom_sigmas: str = "[]",
    ) -> io.NodeOutput:
        if not isinstance(draw_mode, str):
            raise TypeError("draw_mode must be a string")
        values = _drawn_sigmas(custom_sigmas) if draw_mode == "draw" else None
        if values is None:
            values = klein_parametric_sigmas(steps, denoise, sigma_min, shift, curve)
        return io.NodeOutput(model, await _sigmas_ref(values))


class FlowMatchSchedulerSmoothCosine(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="FlowMatchSchedulerSmoothCosine",
            display_name="Flow Scheduler (Smooth Cosine)",
            category="sampling/custom_sampling/schedulers",
            description="Smooth cosine schedule - gentle transitions, no sudden changes",
            inputs=[
                io.Model.Input("model"),
                io.Int.Input(
                    "steps", default=8, min=4, max=100,
                    tooltip="Number of sampling steps",
                ),
                io.Float.Input(
                    "denoise", default=1.0, min=0.0, max=1.0, step=0.01,
                    tooltip="Denoising strength (1.0 = full denoise)",
                ),
            ],
            outputs=[io.Model.Output(), io.Sigmas.Output()],
        )

    @classmethod
    async def execute(
        cls, model: sdk.ModelRef, steps: int, denoise: float,
    ) -> io.NodeOutput:
        return io.NodeOutput(
            model, await _sigmas_ref(smooth_cosine_sigmas(steps, denoise))
        )


class SamplerMinimalChangeFlow(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("closures",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SamplerMinimalChangeFlow",
            display_name="Minimal Change Flow",
            category="sampling/custom_sampling/samplers",
            description=(
                "Minimal Change Flow sampler - limits change per step to prevent drift"
            ),
            inputs=[
                io.Float.Input(
                    "max_change_per_step", default=0.70, min=0.05, max=1.0,
                    step=0.05,
                    tooltip="Maximum relative change allowed per step",
                )
            ],
            outputs=[io.Sampler.Output()],
        )

    @classmethod
    async def execute(cls, max_change_per_step: float) -> io.NodeOutput:
        limit = _number(
            max_change_per_step, "max_change_per_step", 0.05, 1.0
        )

        async def program(broker: Any, latent: Any, sigmas: Any):
            return await sampler_program.minimal_change_flow(
                broker, latent, sigmas, limit
            )

        closure = await sdk.ctx().closures.retain("custom_sampler", program)
        return io.NodeOutput(await closure.as_sampler())


NODE_CLASS_MAPPINGS = {
    "CapitanZiTLinearSigma": CapitanZiTLinearSigma,
    "FlowMatchSchedulerKleinEdit": FlowMatchSchedulerKleinEdit,
    "FlowMatchSchedulerSmoothCosine": FlowMatchSchedulerSmoothCosine,
    "SamplerMinimalChangeFlow": SamplerMinimalChangeFlow,
}
