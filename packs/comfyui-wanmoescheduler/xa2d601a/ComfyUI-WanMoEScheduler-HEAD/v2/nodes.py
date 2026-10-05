"""Secure Nodes V2 backend for WanMoEScheduler."""

from __future__ import annotations

import math

from comfy_api.latest import io, sdk


SCHEDULERS = ["simple", "sgm_uniform", "ddim_uniform", "beta", "normal"]


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


class WanMoEScheduler(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="WanMoEScheduler",
            display_name="WanMoEScheduler",
            category="sampling/custom_sampling/schedulers",
            description=(
                "Finds an optimal sigma shift value and calculates sigmas for "
                "two-stage sampling."
            ),
            inputs=[
                io.Model.Input(
                    "model", tooltip="The model used for calculating sigmas."
                ),
                io.Combo.Input(
                    "scheduler",
                    options=SCHEDULERS,
                    tooltip=(
                        "The scheduler to use for sigma calculation.\n\n"
                        "NOTE: If you do not use sigmas for sampling don't "
                        "forget to match the scheduler values."
                    ),
                ),
                io.Int.Input(
                    "steps_high", default=4, min=1, max=99,
                    tooltip="Number of steps for high noise sampling.",
                ),
                io.Int.Input(
                    "steps_low", default=4, min=1, max=99,
                    tooltip=(
                        "Number of steps for the low noise sampling.\n\n"
                        "NOTE: Higher steps require lower speed lora strength."
                    ),
                ),
                io.Float.Input(
                    "boundary", default=0.875, min=0.0, max=0.999,
                    step=0.001, round=0.001,
                    tooltip=(
                        "The target sigma value for the boundary between high "
                        "and low steps. Usually 0.930-0.875.\n\nOffical WAN "
                        "values are 0.90 (I2V) and 0.875 (T2V)."
                    ),
                ),
                io.Float.Input(
                    "interval", default=0.01, min=0.01, max=1.0,
                    step=0.01, round=0.01,
                    tooltip=(
                        "The step size to increment the shift while searching "
                        "for the optimal value. Lower is more precise."
                    ),
                ),
                io.Float.Input(
                    "denoise", default=1.0, min=0.0, max=1.0, step=0.01,
                    tooltip=(
                        "The amount of noise to remove. A value of 1.0 is full "
                        "denoising (default)."
                    ),
                ),
            ],
            outputs=[
                io.Float.Output("shift", display_name="shift"),
                io.Int.Output("steps", display_name="steps"),
                io.Int.Output("steps_high", display_name="steps_high"),
                io.Int.Output("steps_low", display_name="steps_low"),
                io.Sigmas.Output("sigmas", display_name="sigmas"),
                io.Sigmas.Output("sigmas_high", display_name="sigmas_high"),
                io.Sigmas.Output("sigmas_low", display_name="sigmas_low"),
            ],
        )

    @classmethod
    async def execute(
        cls,
        model: sdk.ModelRef,
        scheduler: str,
        steps_high: int,
        steps_low: int,
        boundary: float,
        interval: float,
        denoise: float,
    ) -> io.NodeOutput:
        steps_high = _integer(steps_high, "steps_high", 1, 99)
        steps_low = _integer(steps_low, "steps_low", 1, 99)
        if scheduler not in SCHEDULERS:
            raise ValueError("scheduler is not supported")
        boundary = _number(boundary, "boundary", 0.0, 0.999)
        interval = _number(interval, "interval", 0.01, 1.0)
        denoise = _number(denoise, "denoise", 0.0, 1.0)
        if denoise == 0.0:
            raise ZeroDivisionError("float division by zero")

        steps_total = steps_high + steps_low
        shift = 0.0
        final_shift = 0.0
        found_sigmas = None
        while shift <= 100.0:
            found_sigmas = await model.sampling_sigmas(
                scheduler=scheduler,
                steps=steps_total,
                denoise=denoise,
                shift=shift,
            )
            final_shift = shift
            if await found_sigmas.value_at(steps_high) >= boundary:
                break
            shift += interval
            assert shift <= 100.0, "Could not find shift."

        assert found_sigmas is not None
        sigmas_high = await found_sigmas.slice(0, steps_high + 1)
        sigmas_low = await found_sigmas.slice(steps_high)
        return io.NodeOutput(
            round(final_shift, 2),
            steps_total,
            steps_high,
            steps_low,
            found_sigmas,
            sigmas_high,
            sigmas_low,
        )
