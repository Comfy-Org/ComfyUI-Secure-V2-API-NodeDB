"""Pack-owned programs for Power Shift Scheduler's twelve scheduler names."""

from __future__ import annotations

import math

import numpy
import scipy.stats
from scipy.interpolate import PchipInterpolator


MAX_PROJECTED_SIGMAS = 65_536
MAX_PROVIDER_STEPS = 10_000
MAX_NODE_STEPS = 100_000
BASE_SIGMA_POINTS = (
    1.0,
    0.99375,
    0.9875,
    0.98125,
    0.975,
    0.909375,
    0.725,
    0.421875,
)

BETA_PROGRAMS = {
    "beta_33": (0.3, 0.3, "none"),
    "beta_44": (0.4, 0.4, "none"),
    "beta_53": (0.5, 0.3, "none"),
    "beta_54": (0.5, 0.4, "none"),
    "beta_57": (0.5, 0.7, "none"),
    "beta_32": (0.3, 0.2, "twenties"),
    "beta_43": (0.4, 0.3, "twenties"),
    "beta_42": (0.4, 0.2, "tens"),
}

PROVIDER_NAMES = (
    "beta_32",
    "beta_33",
    "beta_42",
    "beta_43",
    "beta_44",
    "beta_53",
    "beta_54",
    "beta_57",
    "power_shift",
    "radiance_shift",
    "sigma_curve_from_points",
    "sigma_curve_pchip",
)


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


def _projection(projection) -> list[float]:
    if not isinstance(projection, list):
        raise TypeError("model-sigmas projection must be a list")
    if not 2 <= len(projection) <= MAX_PROJECTED_SIGMAS:
        raise ValueError(
            "model-sigmas projection must contain 2 to 65536 values"
        )
    return [
        _number(item, "model sigma", 0.0, 1_000_000_000_000.0)
        for item in projection
    ]


def _effective_steps(steps: int, modifier: str) -> int:
    steps = _integer(steps, "steps", 1, MAX_PROVIDER_STEPS)
    if modifier == "none":
        return steps
    if modifier == "twenties":
        return steps + steps // 20
    if modifier == "tens":
        return steps + steps // 10
    raise ValueError(f"unknown step modifier {modifier!r}")


def beta_values(
    projection,
    steps: int,
    alpha: float,
    beta: float,
    modifier: str,
) -> list[float]:
    values = _projection(projection)
    count = _effective_steps(steps, modifier)
    total_timesteps = len(values) - 1
    timesteps = 1.0 - numpy.linspace(0.0, 1.0, count, endpoint=False)
    timesteps = numpy.rint(
        scipy.stats.beta.ppf(timesteps, alpha, beta) * total_timesteps
    )
    result: list[float] = []
    previous = -1
    for timestep in timesteps:
        index = int(timestep)
        if index != previous:
            result.append(values[index])
        previous = index
    result.append(0.0)
    return result


def power_shift_indices(
    total_timesteps: int,
    steps: int,
    power: float,
    midpoint_shift: float,
) -> list[int]:
    total_timesteps = _integer(
        total_timesteps, "total_timesteps", 1, MAX_PROJECTED_SIGMAS - 1
    )
    steps = _integer(steps, "steps", 1, MAX_NODE_STEPS)
    power = _number(power, "power", 0.0, 5.0)
    midpoint_shift = _number(
        midpoint_shift, "midpoint_shift", 0.0, 5.0
    )
    positions = numpy.linspace(0.0, 1.0, steps, endpoint=False)
    positions = positions**midpoint_shift
    normalized = (1.0 - positions**power) ** power
    timesteps = numpy.rint(normalized * total_timesteps)
    result: list[int] = []
    previous = -1
    for timestep in timesteps:
        index = min(int(timestep), total_timesteps)
        if index != previous:
            result.append(index)
        previous = index
    return result


def power_shift_values(
    projection,
    steps: int,
    power: float,
    midpoint_shift: float,
    discard_penultimate: bool,
) -> list[float]:
    values = _projection(projection)
    if not isinstance(discard_penultimate, bool):
        raise TypeError("discard_penultimate must be a boolean")
    indices = power_shift_indices(
        len(values) - 1, steps, power, midpoint_shift
    )
    result = [values[index] for index in indices]
    result.append(0.0)
    if discard_penultimate:
        result = result[:-2] + result[-1:]
    return result


def parse_float_list(value: str) -> list[float]:
    if not isinstance(value, str):
        raise TypeError("custom_points must be a string")
    if len(value.encode("utf-8")) > 65_536:
        raise ValueError("custom_points exceeds 65536 bytes")
    result = [float(item.strip()) for item in value.split(",") if item.strip()]
    if len(result) > 10_001:
        raise ValueError("custom_points exceeds 10001 values")
    return result


def sigma_curve_values(
    steps: int,
    discard_penultimate: bool,
    sigma_points=BASE_SIGMA_POINTS,
    *,
    method: str,
) -> list[float]:
    steps = _integer(steps, "steps", 1, MAX_NODE_STEPS)
    if not isinstance(discard_penultimate, bool):
        raise TypeError("discard_penultimate must be a boolean")
    if (
        not isinstance(sigma_points, (list, tuple))
        or not 2 <= len(sigma_points) <= 10_001
    ):
        raise ValueError("sigma_points must contain 2 to 10001 values")
    points = numpy.array(sigma_points, dtype=numpy.float32)
    if points.ndim != 1 or not bool(numpy.isfinite(points).all()):
        raise ValueError("sigma_points must contain finite scalars")
    if bool((points < 0).any()):
        raise ValueError("sigma_points cannot contain negative values")
    base_x = numpy.linspace(0.0, float(len(points) - 1), len(points))
    target_x = numpy.linspace(0.0, float(len(points) - 1), steps)
    if method == "linear":
        curve = numpy.interp(target_x, base_x, points).astype(numpy.float32)
    elif method == "pchip":
        curve = PchipInterpolator(base_x, points)(target_x).astype(numpy.float32)
    else:
        raise ValueError(f"unknown sigma curve method {method!r}")
    result = numpy.concatenate(
        (curve, numpy.array([0.0], dtype=numpy.float32))
    ).tolist()
    if discard_penultimate:
        result = result[:-2] + result[-1:]
    return result


def provide(projection, steps: int, config: dict) -> list[float]:
    """Execute one closed declarative scheduler with scalar-only inputs."""
    if not isinstance(config, dict) or set(config) != {"name"}:
        raise ValueError("scheduler config must contain exactly 'name'")
    name = config["name"]
    if name not in PROVIDER_NAMES:
        raise ValueError(f"unknown scheduler program {name!r}")
    _integer(steps, "steps", 1, MAX_PROVIDER_STEPS)

    if name in BETA_PROGRAMS:
        alpha, beta, modifier = BETA_PROGRAMS[name]
        return beta_values(projection, steps, alpha, beta, modifier)
    if name == "power_shift":
        return power_shift_values(projection, steps, 2.0, 1.0, False)
    if name == "radiance_shift":
        return power_shift_values(projection, steps + 1, 2.4, 0.98, True)
    if name == "sigma_curve_from_points":
        _projection(projection)
        return sigma_curve_values(
            steps, False, BASE_SIGMA_POINTS, method="linear"
        )
    _projection(projection)
    return sigma_curve_values(
        steps, False, BASE_SIGMA_POINTS, method="pchip"
    )


__all__ = [
    "BASE_SIGMA_POINTS",
    "BETA_PROGRAMS",
    "PROVIDER_NAMES",
    "beta_values",
    "parse_float_list",
    "power_shift_indices",
    "power_shift_values",
    "provide",
    "sigma_curve_values",
]
