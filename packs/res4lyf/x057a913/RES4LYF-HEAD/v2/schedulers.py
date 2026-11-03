"""Scheduler providers for the two schedulers RES4LYF adds to ComfyUI's global scheduler list at import time.

Upstream registers them in __init__.py:24-30, which makes them available to every sampler node, not only
RES4LYF's own:
  * "bong_tangent" -> sigmas.bong_tangent_scheduler (no model input)
  * "beta57"       -> comfy.samplers.beta_scheduler(model_sampling, steps, alpha=0.5, beta=0.7)

V2 declares both in secure-nodes.json as manifest scheduler providers, so the host registers the same two names.
- beta57 receives the model's sigma table through the "model_sigmas" projection: the float64 copy of the
  float32 table, which is exact. It runs core's beta_scheduler body unchanged (comfy/samplers.py:696-708 at
  6257422b).
- bong_tangent is RES4LYF's own pure function (sigmas.py:4066-4099 at 057a913e) and needs no projection.
"""
from math import atan, pi


def beta57(projection, steps, config):
    import numpy
    import scipy.stats
    import torch

    if config != {}:
        raise ValueError("beta57 takes no configuration")
    table = list(projection)
    alpha, beta = 0.5, 0.7
    total_timesteps = (len(table) - 1)
    ts = 1 - numpy.linspace(0, 1, steps, endpoint=False)
    ts = numpy.rint(scipy.stats.beta.ppf(ts, alpha, beta) * total_timesteps)

    sigs = []
    last_t = -1
    for t in ts:
        if t != last_t:
            sigs += [float(table[int(t)])]
        last_t = t
    sigs += [0.0]
    return torch.FloatTensor(sigs)


def get_bong_tangent_sigmas(steps, slope, pivot, start, end):
    smax = ((2/pi)*atan(-slope*(0-pivot))+1)/2
    smin = ((2/pi)*atan(-slope*((steps-1)-pivot))+1)/2

    srange = smax-smin
    sscale = start - end

    sigmas = [  ( (((2/pi)*atan(-slope*(x-pivot))+1)/2) - smin) * (1/srange) * sscale + end    for x in range(steps)]

    return sigmas


def bong_tangent_scheduler(model_sampling, steps, start=1.0, middle=0.5, end=0.0, pivot_1=0.6, pivot_2=0.6, slope_1=0.2, slope_2=0.2, pad=False):
    import torch

    steps += 2

    midpoint = int( (steps*pivot_1 + steps*pivot_2) / 2 )
    pivot_1 = int(steps * pivot_1)
    pivot_2 = int(steps * pivot_2)

    slope_1 = slope_1 / (steps/40)
    slope_2 = slope_2 / (steps/40)

    stage_2_len = steps - midpoint
    stage_1_len = steps - stage_2_len

    tan_sigmas_1 = get_bong_tangent_sigmas(stage_1_len, slope_1, pivot_1, start, middle)
    tan_sigmas_2 = get_bong_tangent_sigmas(stage_2_len, slope_2, pivot_2 - stage_1_len, middle, end)

    tan_sigmas_1 = tan_sigmas_1[:-1]
    if pad:
        tan_sigmas_2 = tan_sigmas_2+[0]

    tan_sigmas = torch.tensor(tan_sigmas_1 + tan_sigmas_2)

    return tan_sigmas


def bong_tangent(projection, steps, config):
    if projection is not None or config != {}:
        raise ValueError("bong_tangent takes no projection and no configuration")
    return bong_tangent_scheduler(None, steps)


SCHEDULER_PROVIDERS = [
    {"name": "bong_tangent", "module": "schedulers", "function": "bong_tangent", "projection": "none",
     "min_steps": 1, "max_steps": 10000, "config": {}},
    {"name": "beta57", "module": "schedulers", "function": "beta57", "projection": "model_sigmas",
     "min_steps": 1, "max_steps": 10000, "config": {}},
]
