"""Secure Nodes V2 nodes for ComfyUI Power Shift Scheduler."""

from __future__ import annotations

import math

from comfy_api.latest import io, sdk

from .scheduler_program import (
    BASE_SIGMA_POINTS,
    MAX_NODE_STEPS,
    parse_float_list,
    power_shift_indices,
    sigma_curve_values,
)


MODEL_SIGMA_COUNT = 1_000
CATEGORY = "sampling/custom_sampling/schedulers"


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


def _total_steps(steps: int, denoise: float, *, zero_divides: bool) -> int:
    denoise = _number(denoise, "denoise", 0.0, 1.0)
    total = steps
    if (denoise < 1.0) if zero_divides else (0.0 < denoise < 1.0):
        if denoise == 0.0:
            raise ZeroDivisionError("float division by zero")
        total = int(steps / denoise)
    if total > MAX_NODE_STEPS:
        raise ValueError(f"effective steps cannot exceed {MAX_NODE_STEPS}")
    return total


async def _power_values(
    model: sdk.ModelRef,
    steps: int,
    power: float,
    midpoint_shift: float,
    discard_penultimate: bool,
) -> list[float]:
    if not isinstance(discard_penultimate, bool):
        raise TypeError("discard_penultimate must be a boolean")
    indices = power_shift_indices(
        MODEL_SIGMA_COUNT - 1, steps, power, midpoint_shift
    )
    values = []
    for timestep in indices:
        values.append(await model.sigma_for_percent(
            1.0 - timestep / (MODEL_SIGMA_COUNT - 1),
            actual_endpoints=True,
        ))
    values.append(0.0)
    if discard_penultimate:
        values = values[:-2] + values[-1:]
    return values


class PowerShiftSchedulerNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="PowerShiftScheduler",
            display_name="Power Shift Scheduler",
            category=CATEGORY,
            inputs=[
                io.Model.Input("model"),
                io.Int.Input("steps", default=20, min=3, max=1_000),
                io.Float.Input("power", default=2.0, min=0.0, max=5.0, step=0.001),
                io.Float.Input(
                    "midpoint_shift", default=1.0, min=0.0, max=5.0, step=0.001,
                ),
                io.Boolean.Input("discard_penultimate", default=False),
                io.Float.Input("denoise", default=1.0, min=0.0, max=1.0, step=0.01),
            ],
            outputs=[io.Sigmas.Output()],
        )

    @classmethod
    async def execute(
        cls, model: sdk.ModelRef, steps: int, power: float,
        midpoint_shift: float, discard_penultimate: bool, denoise: float,
    ) -> io.NodeOutput:
        steps = _integer(steps, "steps", 3, 1_000)
        total = _total_steps(steps, denoise, zero_divides=True)
        values = await _power_values(
            model,
            total,
            _number(power, "power", 0.0, 5.0),
            _number(midpoint_shift, "midpoint_shift", 0.0, 5.0),
            discard_penultimate,
        )
        return io.NodeOutput(await sdk.SigmasRef.from_values(values[-(steps + 1):]))


class RadianceShiftSchedulerNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="RadianceShiftScheduler",
            display_name="Radiance Shift Scheduler",
            category=CATEGORY,
            inputs=[
                io.Model.Input("model"),
                io.Int.Input("steps", default=20, min=3, max=1_000),
                io.Float.Input("power", default=2.4, min=0.0, max=5.0, step=0.001),
                io.Float.Input(
                    "midpoint_shift", default=0.98, min=0.0, max=5.0, step=0.001,
                ),
                io.Boolean.Input("discard_penultimate", default=True),
                io.Float.Input("denoise", default=1.0, min=0.0, max=1.0, step=0.01),
            ],
            outputs=[io.Sigmas.Output()],
        )

    @classmethod
    async def execute(
        cls, model: sdk.ModelRef, steps: int, power: float,
        midpoint_shift: float, discard_penultimate: bool, denoise: float,
    ) -> io.NodeOutput:
        # The pinned node intentionally calls power_shift_scheduler rather
        # than its separately registered radiance_shift scheduler.
        return await PowerShiftSchedulerNode.execute(
            model, steps, power, midpoint_shift, discard_penultimate, denoise,
        )


class SigmaCurveFromPointsSchedulerNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SigmaCurveFromPointsScheduler",
            display_name="From Points Scheduler",
            category=CATEGORY,
            inputs=[
                io.Model.Input("model"),
                io.Int.Input("steps", default=8, min=1, max=1_000),
                io.Boolean.Input("discard_penultimate", default=False),
                io.Float.Input("denoise", default=1.0, min=0.0, max=1.0, step=0.01),
                io.String.Input(
                    "custom_points",
                    optional=True,
                    multiline=False,
                    tooltip=(
                        "sigma curve points provided as comma separated list "
                        "of floats. e.g. '1.0, 0.9, 0.8' etc."
                    ),
                ),
            ],
            outputs=[io.Sigmas.Output()],
        )

    @classmethod
    async def execute(
        cls, model: sdk.ModelRef, steps: int, discard_penultimate: bool,
        denoise: float, custom_points: str | None = None,
    ) -> io.NodeOutput:
        del model
        steps = _integer(steps, "steps", 1, 1_000)
        total = _total_steps(steps, denoise, zero_divides=False)
        points = BASE_SIGMA_POINTS
        if custom_points is not None:
            parsed = parse_float_list(custom_points)
            if len(parsed) >= 2:
                points = parsed
        values = sigma_curve_values(
            total, discard_penultimate, points, method="linear"
        )[-(steps + 1):]
        return io.NodeOutput(await sdk.SigmasRef.from_values(values))


class SigmaCurvePchipSchedulerNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SigmaCurvePchipScheduler",
            display_name="PCHIP Scheduler",
            category=CATEGORY,
            inputs=[
                io.Model.Input("model"),
                io.Int.Input("steps", default=8, min=1, max=2_000),
                io.Boolean.Input("discard_penultimate", default=False),
                io.Float.Input("denoise", default=1.0, min=0.0, max=1.0, step=0.01),
                io.String.Input(
                    "custom_points",
                    optional=True,
                    multiline=False,
                    tooltip=(
                        "sigma curve points provided as comma separated list "
                        "of floats. e.g. '1.0, 0.9, 0.8'"
                    ),
                ),
            ],
            outputs=[io.Sigmas.Output()],
        )

    @classmethod
    async def execute(
        cls, model: sdk.ModelRef, steps: int, discard_penultimate: bool,
        denoise: float, custom_points: str | None = None,
    ) -> io.NodeOutput:
        del model
        steps = _integer(steps, "steps", 1, 2_000)
        total = _total_steps(steps, denoise, zero_divides=False)
        points = BASE_SIGMA_POINTS
        if custom_points is not None:
            parsed = parse_float_list(custom_points)
            if len(parsed) >= 2:
                points = parsed
        values = sigma_curve_values(
            total, discard_penultimate, points, method="pchip"
        )[-(steps + 1):]
        return io.NodeOutput(await sdk.SigmasRef.from_values(values))
