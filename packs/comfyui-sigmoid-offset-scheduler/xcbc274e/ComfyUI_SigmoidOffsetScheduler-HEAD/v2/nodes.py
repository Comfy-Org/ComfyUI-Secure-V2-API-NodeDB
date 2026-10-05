"""Secure Nodes V2 node for ComfyUI Sigmoid Offset Scheduler."""

from __future__ import annotations

import math
import struct

from comfy_api.latest import io, sdk

from .scheduler_program import sigmoid_indices


MODEL_SIGMA_COUNT = 1_000


def _float32(value: float) -> float:
    """Round one scalar exactly as ``torch.FloatTensor`` does upstream."""
    return struct.unpack("f", struct.pack("f", float(value)))[0]


def _number(value: float, name: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return result


class SigmoidOffsetScheduler(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SigmoidOffsetScheduler",
            display_name="SigmoidOffsetScheduler",
            category="sampling/custom_sampling/schedulers",
            inputs=[
                io.Model.Input("model"),
                io.Int.Input("steps", default=30, min=1, max=10_000),
                io.Float.Input(
                    "square_k", default=1.0, min=0.0, max=10.0, step=0.01,
                    tooltip="Sigmoid steepness. Higher = steeper transition.",
                ),
                io.Float.Input(
                    "base_c", default=0.5, min=-5.0, max=5.0, step=0.01,
                    tooltip=(
                        "Shifts sigmoid curve. <0.5: More steps at high sigmas "
                        "(early denoising); >0.5: More steps at low sigmas "
                        "(late denoising)."
                    ),
                ),
                io.Float.Input(
                    "start_sigma", default=1.0, min=0.0, max=1.0, step=0.001,
                    tooltip=(
                        "Rescales the sigma to enable softer start. Set to "
                        "0.983 for old behaviour. 1.0 = no rescaling."
                    ),
                ),
            ],
            outputs=[io.Sigmas.Output()],
        )

    @classmethod
    async def execute(
        cls,
        model: sdk.ModelRef,
        steps: int,
        square_k: float,
        base_c: float,
        start_sigma: float,
    ) -> io.NodeOutput:
        start_sigma = _number(start_sigma, "start_sigma", 0.0, 1.0)
        indices = sigmoid_indices(
            MODEL_SIGMA_COUNT - 1, steps, square_k, base_c,
        )
        sigmas = []
        for timestep in indices:
            percent = 1.0 - timestep / (MODEL_SIGMA_COUNT - 1)
            sigmas.append(
                await model.sigma_for_percent(percent, actual_endpoints=True)
            )
        floor = await model.sigma_for_percent(1.0, actual_endpoints=True)
        if sigmas[-1] <= floor:
            sigmas[-1] = 0.0
        else:
            sigmas.append(0.0)

        if start_sigma != 1.0:
            # The pristine node constructs a FloatTensor before rescaling, so
            # preserve its float32 rounding at each tensor operation.
            sigmas = [_float32(value) for value in sigmas]
            minimum = min(sigmas)
            maximum = max(sigmas)
            scale = _float32(start_sigma)
            span = _float32(maximum - minimum)
            sigmas = [
                _float32(
                    _float32(_float32(value - minimum) * scale) / span
                )
                for value in sigmas
            ]
        return io.NodeOutput(await sdk.SigmasRef.from_values(sigmas))
