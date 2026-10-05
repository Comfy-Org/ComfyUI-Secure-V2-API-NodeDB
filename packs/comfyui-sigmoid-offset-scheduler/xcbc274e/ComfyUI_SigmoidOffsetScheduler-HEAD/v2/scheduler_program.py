"""Scalar-only implementation for the declarative ``sigmoid_offset`` scheduler."""

from __future__ import annotations

import math


def _number(value: float, name: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return result


def _integer(value: int, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _sigmoid(value: float, steepness: float, shift: float) -> float:
    mapped = 8.0 * value - 4.0
    exponent = max(-700.0, min(700.0, -steepness * (mapped + 4.0 * shift)))
    return 1.0 / (1.0 + math.exp(exponent))


def sigmoid_indices(
    total_timesteps: int,
    steps: int,
    square_k: float,
    base_c: float,
) -> list[int]:
    """Return the same rounded, de-duplicated indices as the pristine pack."""
    total_timesteps = _integer(total_timesteps, "total_timesteps", 1, 100_000)
    steps = _integer(steps, "steps", 1, 10_000)
    square_k = _number(square_k, "square_k", 0.0, 10.0)
    base_c = _number(base_c, "base_c", -5.0, 5.0)
    shift = 2.0 * (base_c - 0.5)
    minimum = _sigmoid(0.0, square_k, shift)
    maximum = _sigmoid(1.0, square_k, shift)
    span = maximum - minimum
    if span == 0.0:
        # NumPy's NaN-to-int cast in the pristine implementation is clipped
        # to index zero for the allowed square_k=0 edge case.
        return [0]

    indices: list[int] = []
    previous = -1
    for index in range(steps + 1):
        raw = _sigmoid(index / steps, square_k, shift)
        normalized = (raw - minimum) / span
        timestep = round((1.0 - normalized) * total_timesteps)
        timestep = max(0, min(total_timesteps, timestep))
        if timestep != previous or not indices:
            indices.append(timestep)
            previous = timestep
    return indices


def schedule_from_projection(
    projection: list[float],
    steps: int,
    square_k: float = 1.0,
    base_c: float = 0.5,
) -> list[float]:
    if not isinstance(projection, list) or not 2 <= len(projection) <= 100_001:
        raise ValueError("model-sigmas projection must contain 2 to 100001 values")
    values = [
        _number(item, "model sigma", 0.0, 1_000_000_000_000.0)
        for item in projection
    ]
    indices = sigmoid_indices(len(values) - 1, steps, square_k, base_c)
    sigmas = [values[index] for index in indices]
    sigma_floor = values[0]
    if sigmas[-1] <= sigma_floor:
        sigmas[-1] = 0.0
    else:
        sigmas.append(0.0)
    return sigmas


def provide(projection, steps: int, config: dict) -> list[float]:
    if config != {"square_k": 1.0, "base_c": 0.5}:
        raise ValueError("sigmoid_offset scheduler configuration is invalid")
    return schedule_from_projection(
        projection,
        steps,
        square_k=config["square_k"],
        base_c=config["base_c"],
    )
