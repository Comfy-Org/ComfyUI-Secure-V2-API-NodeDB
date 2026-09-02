"""Pack-owned scheduler programs and declarative names for PPM."""
from __future__ import annotations


AYS_TIMESTEPS = {
    "standard": [999, 845, 730, 587, 443, 310, 193, 116, 53, 13, 0],
    "thirty": [
        999, 953, 904, 850, 813, 777, 738, 695, 650, 602, 556, 510,
        462, 417, 374, 331, 290, 250, 214, 182, 155, 131, 108, 85,
        66, 49, 32, 20, 12, 3, 0,
    ],
}

# Exact ``comfy_extras.nodes_gits.NOISE_LEVELS[1.20]`` rows used by the
# pinned source.  PPM fixes the coefficient at 1.20, so retaining the other
# upstream coefficient tables would only enlarge the sealed program surface.
# Row zero is the two-step schedule and row eighteen is the twenty-step
# schedule used as the interpolation source above twenty steps.
GITS_NOISE_LEVELS_1_20 = (
    (14.61464119, 0.803307, 0.02916753),
    (14.61464119, 1.56271636, 0.52423614, 0.02916753),
    (14.61464119, 2.36326075, 0.92192322, 0.36617002, 0.02916753),
    (14.61464119, 2.84484982, 1.24153244, 0.59516323, 0.25053367, 0.02916753),
    (14.61464119, 5.85520077, 2.05039096, 0.95350921, 0.45573691, 0.17026083, 0.02916753),
    (14.61464119, 5.85520077, 2.45070267, 1.24153244, 0.64427125, 0.29807833, 0.09824532, 0.02916753),
    (14.61464119, 5.85520077, 2.45070267, 1.36964464, 0.803307, 0.45573691, 0.25053367, 0.09824532, 0.02916753),
    (14.61464119, 5.85520077, 2.84484982, 1.61558151, 0.95350921, 0.59516323, 0.36617002, 0.19894916, 0.09824532, 0.02916753),
    (14.61464119, 5.85520077, 2.84484982, 1.67050016, 1.08895338, 0.74807048, 0.50118381, 0.32104823, 0.19894916, 0.09824532, 0.02916753),
    (14.61464119, 5.85520077, 2.95596409, 1.84880662, 1.24153244, 0.83188516, 0.59516323, 0.41087446, 0.27464288, 0.17026083, 0.09824532, 0.02916753),
    (14.61464119, 5.85520077, 3.07277966, 1.98035145, 1.36964464, 0.95350921, 0.69515091, 0.50118381, 0.36617002, 0.25053367, 0.17026083, 0.09824532, 0.02916753),
    (14.61464119, 6.77309084, 3.46139455, 2.36326075, 1.56271636, 1.08895338, 0.803307, 0.59516323, 0.45573691, 0.34370604, 0.25053367, 0.17026083, 0.09824532, 0.02916753),
    (14.61464119, 6.77309084, 3.46139455, 2.45070267, 1.61558151, 1.162866, 0.86115354, 0.64427125, 0.50118381, 0.38853383, 0.29807833, 0.22545385, 0.17026083, 0.09824532, 0.02916753),
    (14.61464119, 7.49001646, 4.65472794, 3.07277966, 2.12350607, 1.51179266, 1.08895338, 0.83188516, 0.64427125, 0.50118381, 0.38853383, 0.29807833, 0.22545385, 0.17026083, 0.09824532, 0.02916753),
    (14.61464119, 7.49001646, 4.65472794, 3.07277966, 2.12350607, 1.51179266, 1.08895338, 0.83188516, 0.64427125, 0.50118381, 0.41087446, 0.32104823, 0.25053367, 0.19894916, 0.13792117, 0.09824532, 0.02916753),
    (14.61464119, 7.49001646, 4.65472794, 3.07277966, 2.12350607, 1.51179266, 1.08895338, 0.83188516, 0.64427125, 0.50118381, 0.41087446, 0.34370604, 0.27464288, 0.22545385, 0.17026083, 0.13792117, 0.09824532, 0.02916753),
    (14.61464119, 7.49001646, 4.65472794, 3.07277966, 2.19988537, 1.61558151, 1.20157266, 0.92192322, 0.72133851, 0.57119018, 0.45573691, 0.36617002, 0.29807833, 0.25053367, 0.19894916, 0.17026083, 0.13792117, 0.09824532, 0.02916753),
    (14.61464119, 7.49001646, 4.65472794, 3.07277966, 2.19988537, 1.61558151, 1.24153244, 0.95350921, 0.74807048, 0.59516323, 0.4783645, 0.38853383, 0.32104823, 0.27464288, 0.22545385, 0.19894916, 0.17026083, 0.13792117, 0.09824532, 0.02916753),
    (14.61464119, 7.49001646, 4.65472794, 3.07277966, 2.19988537, 1.61558151, 1.24153244, 0.95350921, 0.74807048, 0.59516323, 0.50118381, 0.41087446, 0.34370604, 0.29807833, 0.25053367, 0.22545385, 0.19894916, 0.17026083, 0.13792117, 0.09824532, 0.02916753),
)

MAX_PROJECTED_SIGMAS = 65_536

# These declarations capture the documented behavior, including the intended
# distinction the source's import-time mapping accidentally loses for its two
# middle entries.
SCHEDULER_DECLARATIONS = {
    "ays": {"program": "ays", "variant": "standard", "force_sigma_min": False},
    "ays+": {"program": "ays", "variant": "standard", "force_sigma_min": True},
    "ays_30": {"program": "ays", "variant": "thirty", "force_sigma_min": False},
    "ays_30+": {"program": "ays", "variant": "thirty", "force_sigma_min": True},
    "gits": {"program": "gits", "coeff": 1.2},
    "beta_1_1": {"program": "beta", "alpha": 1.0, "beta": 1.0},
}

# Exact manifest records for the generic scheduler-provider bridge.  These are
# inert pack data until the conversion is fully sealable; keeping them beside
# the algorithms prevents a later manifest generator from inventing or
# weakening the provider contract.
SCHEDULER_PROVIDERS = [
    {
        "name": name,
        "module": "ppm_scheduler_programs",
        "function": "provide",
        "projection": (
            "simple" if config["program"] == "ays"
            else "model_sigmas" if config["program"] == "beta"
            else "none"
        ),
        **({"projection_steps": 1000} if config["program"] == "ays" else {}),
        "min_steps": 2 if config["program"] == "gits" else 1,
        "max_steps": 10000,
        "config": config,
    }
    for name, config in SCHEDULER_DECLARATIONS.items()
]


def _validated_steps(steps, minimum, label):
    if isinstance(steps, bool) or not isinstance(steps, int):
        raise TypeError(f"{label} steps must be an integer")
    if not minimum <= steps <= 10000:
        raise ValueError(f"{label} steps must be in [{minimum}, 10000]")
    return steps


def _projection_tensor(projection, label, *, exact=None, minimum=2):
    import torch

    try:
        value = torch.as_tensor(projection)
    except (TypeError, ValueError, RuntimeError) as error:
        raise TypeError(f"{label} projection must be a scalar sequence") from error
    if value.ndim != 1:
        raise ValueError(f"{label} projection must be one-dimensional")
    if exact is not None and len(value) != exact:
        raise ValueError(
            f"{label} projection must contain exactly {exact} sigmas"
        )
    if not minimum <= len(value) <= MAX_PROJECTED_SIGMAS:
        raise ValueError(
            f"{label} projection must contain between {minimum} and "
            f"{MAX_PROJECTED_SIGMAS} sigmas"
        )
    value = value.detach().to(device="cpu", dtype=torch.float32)
    if not bool(torch.isfinite(value).all()):
        raise ValueError(f"{label} projection must contain only finite sigmas")
    if bool((value < 0).any()):
        raise ValueError(f"{label} projection cannot contain negative sigmas")
    return value


def loglinear_interpolate(values, count):
    import numpy

    source_x = numpy.linspace(0.0, 1.0, len(values))
    source_y = numpy.log(list(reversed(values)))
    target_x = numpy.linspace(0.0, 1.0, int(count))
    target_y = numpy.interp(target_x, source_x, source_y)
    return numpy.exp(target_y)[::-1].copy()


def ays_from_simple_schedule(
    simple_sigmas,
    steps,
    *,
    variant="standard",
    force_sigma_min=False,
):
    import torch

    steps = _validated_steps(steps, 1, "AYS")
    if variant not in AYS_TIMESTEPS:
        raise ValueError(f"unknown AYS variant {variant!r}")
    simple_sigmas = _projection_tensor(
        simple_sigmas, "AYS simple-schedule", exact=1001
    )
    indices = AYS_TIMESTEPS[variant]
    selected = simple_sigmas.flip(0)[1:][indices]
    count = steps if bool(force_sigma_min) else steps + 1
    interpolated = torch.as_tensor(
        loglinear_interpolate(selected.tolist(), count),
        dtype=torch.float32,
    )
    body = interpolated if bool(force_sigma_min) else interpolated[:-1]
    return torch.cat((body, torch.zeros(1, dtype=torch.float32)))


def gits_from_noise_levels(noise_levels, steps):
    import torch

    steps = _validated_steps(steps, 2, "GITS")
    values = list(noise_levels)
    if steps > 20:
        values = list(loglinear_interpolate(values, steps + 1))
    values = values[-(steps + 1):]
    if len(values) != steps + 1:
        raise ValueError("GITS source levels do not cover the requested steps")
    values[-1] = 0.0
    return torch.tensor(values, dtype=torch.float32)


def beta_1_1_from_model_sigmas(model_sigmas, steps):
    """Apply the pinned source's beta scheduler with alpha=beta=1."""
    import numpy
    import torch

    steps = _validated_steps(steps, 1, "beta_1_1")
    model_sigmas = _projection_tensor(model_sigmas, "beta_1_1 model-sigmas")
    total_timesteps = len(model_sigmas) - 1

    # scipy.stats.beta.ppf(x, 1, 1) is exactly x.  Keeping the source's
    # linspace/rint/index-deduplication sequence preserves its float schedule
    # without requiring the retained guest to import SciPy.
    timesteps = 1.0 - numpy.linspace(0.0, 1.0, steps, endpoint=False)
    timesteps = numpy.rint(timesteps * total_timesteps)
    values = []
    last_timestep = -1
    for timestep in timesteps:
        index = int(timestep)
        if index != last_timestep:
            values.append(float(model_sigmas[index]))
        last_timestep = index
    values.append(0.0)
    return torch.tensor(values, dtype=torch.float32)


def _require_exact_config(config, keys, program):
    if not isinstance(config, dict):
        raise TypeError("scheduler config must be an object")
    if set(config) != set(keys):
        raise ValueError(
            f"{program} scheduler config must contain exactly {sorted(keys)}"
        )


def _fixed_number(config, key, expected, program):
    value = config[key]
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or float(value) != expected
    ):
        raise ValueError(f"{program} requires {key}={expected}")


def provide(projection, steps, config):
    """Run one closed scheduler declaration for the retained host bridge.

    Inputs and outputs are deliberately plain scalar data.  No MODEL object,
    ref, path, device handle, or ambient host service crosses this boundary.
    """
    if not isinstance(config, dict):
        raise TypeError("scheduler config must be an object")
    program = config.get("program")

    if program == "ays":
        _require_exact_config(
            config, {"program", "variant", "force_sigma_min"}, "AYS"
        )
        variant = config["variant"]
        force_sigma_min = config["force_sigma_min"]
        if variant not in AYS_TIMESTEPS:
            raise ValueError(f"unknown AYS variant {variant!r}")
        if not isinstance(force_sigma_min, bool):
            raise TypeError("AYS force_sigma_min must be a boolean")
        result = ays_from_simple_schedule(
            projection,
            steps,
            variant=variant,
            force_sigma_min=force_sigma_min,
        )
    elif program == "gits":
        _require_exact_config(config, {"program", "coeff"}, "GITS")
        _fixed_number(config, "coeff", 1.2, "GITS")
        if projection is not None:
            raise ValueError("GITS does not accept a model-schedule projection")
        steps = _validated_steps(steps, 2, "GITS")
        source = GITS_NOISE_LEVELS_1_20[
            steps - 2 if steps <= 20 else -1
        ]
        result = gits_from_noise_levels(source, steps)
    elif program == "beta":
        _require_exact_config(
            config, {"program", "alpha", "beta"}, "beta_1_1"
        )
        _fixed_number(config, "alpha", 1.0, "beta_1_1")
        _fixed_number(config, "beta", 1.0, "beta_1_1")
        result = beta_1_1_from_model_sigmas(projection, steps)
    else:
        raise ValueError(f"unknown scheduler program {program!r}")

    return result.tolist()


__all__ = [
    "AYS_TIMESTEPS",
    "GITS_NOISE_LEVELS_1_20",
    "MAX_PROJECTED_SIGMAS",
    "SCHEDULER_DECLARATIONS",
    "ays_from_simple_schedule",
    "beta_1_1_from_model_sigmas",
    "gits_from_noise_levels",
    "loglinear_interpolate",
    "provide",
]
