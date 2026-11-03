"""Secure Nodes V2: ClownsharKSampler_Beta, the reduced exact port of RES4LYF 057a913e.

Where the code runs:
- RES4LYF's own RK loop (vendored in res4lyf_core, upstream code) runs as a custom_sampler closure in this guest.
- Model evaluation stays host-side behind the closure broker; this node never sees the model, the conditioning
  objects or the weights.

The node reproduces the original's arithmetic exactly:
- the outer float64 schedule;
- RES4LYF's init noise;
- KSAMPLER's noise scaling, done host-side on the node's float64 SIGMAS and explicit noise;
- the loop itself;
- the post-sample mask blend;
- both output latents, which also carry the loop's final denoised estimate as the original's state_info does
  (latent_chain.py).

Anything outside the reduced envelope is refused by name:
- at queue time when the widget values decide it;
- at run time when only the connected inputs or the model decide it.
It is never approximated. See SECURE_CONVERSION.md for the envelope and the known differences.
"""
from __future__ import annotations

import asyncio
import copy
import json
import math
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F

from comfy_api.latest import io, sdk

from ._secure_runtime import schema_for
from .latent_chain import CHAIN_KEY
from .options_nodes import export as export_options, materialize as materialize_options
from .res4lyf_core._comfy._refuse import OutOfEnvelope
from .res4lyf_core._comfy.model_sampling import GuestCONST, GuestEPS
from .res4lyf_core.beta import noise_classes as _noise_classes
from .res4lyf_core.beta import rk_sampler_beta
from .res4lyf_core.beta.constants import MAX_STEPS
from .res4lyf_core.beta.noise_classes import NOISE_GENERATOR_CLASSES_SIMPLE
from .res4lyf_core.beta.rk_coefficients_beta import get_default_sampler_name, get_sampler_name_list, \
    process_sampler_name
from .res4lyf_core.helper import ExtraOptions, OptionsManager, initialize_or_scale
from .res4lyf_core.latents import normalize_zscore

NODE_ID = "ClownsharKSampler_Beta"
PREFIX = f"RES4LYF/{NODE_ID}"

_HERE = Path(__file__).resolve().parent
_FROZEN = json.loads((_HERE / "_clown_frozen.json").read_text())
ADMITTED_METHODS = frozenset(_FROZEN["admitted_methods"])
SAMPLER_NAMES = list(_FROZEN["sampler_names"])
DEFAULT_SAMPLER = _FROZEN["default_sampler"]
SCHEDULERS = list(_FROZEN["schedulers"])
EPS_FAMILIES = frozenset({"sd1", "sdxl", "sdxl_refiner"})


MENU_ENTRY = {name.split("/")[-1]: name for name in SAMPLER_NAMES}  # method -> its menu entry (unique)
IMPLICIT_PREFIXES = ("fully_implicit", "diag_implicit")  # process_sampler_name (rk_coefficients_beta.py:312-322)


def _refuse(message: str):
    raise OutOfEnvelope(f"{PREFIX}: {message}")


# --------------------------------------------------------------------------------------------------------------- #
# Queue-time checks (widget values only)
# --------------------------------------------------------------------------------------------------------------- #
def dual_format_contains(options, item) -> bool:
    """RES4LYF's DualFormatList.__contains__ (beta/rk_coefficients_beta.py:241-251).

    The original's sampler_name menu is a DualFormatList, so core's list check accepts names with or without
    their folder prefix. A non-string never matches here; the original would raise instead.
    """
    if item in options:
        return True
    if not isinstance(item, str):
        return False
    if "/" in item:
        base_name = item.split("/")[-1]
        return any(name.endswith(base_name) for name in options)
    return any(isinstance(opt, str) and opt.endswith("/" + item) for opt in options)


def core_value_problems(values: dict) -> list[str]:
    """Core's own min/max and list checks (execution.py validate_inputs) for the inputs that validate_inputs
    names. Core skips those checks for named inputs, so they are made here with the same bounds and lists."""
    problems = []
    for item in schema_for(NODE_ID).inputs:
        if item.id not in values or values[item.id] is None:  # absent, or linked (None at queue time)
            continue
        value = values[item.id]
        if isinstance(item, io.Combo.Input):
            options = list(item.options or [])
            accepted = dual_format_contains(options, value) if item.id == "sampler_name" else value in options
            if not accepted:
                problems.append(f"{item.id}: value not in list: {value!r}")
            continue
        low, high = getattr(item, "min", None), getattr(item, "max", None)
        if low is not None and value < low:
            problems.append(f"{item.id}: value {value} smaller than min of {low}")
        elif high is not None and value > high:
            problems.append(f"{item.id}: value {value} bigger than max of {high}")
    return problems


def envelope_problems(*, sampler_name, scheduler, steps, cfg, seed, sampler_mode, denoise) -> list[str]:
    """The reduced envelope. A None value is a linked input at queue time; execute checks it again with the
    real value."""
    problems = []
    if sampler_mode is not None and sampler_mode != "standard":
        problems.append(f"sampler_mode {sampler_mode!r} continues another sampler's saved state, which a V2 "
                        f"latent cannot carry; only 'standard' is supported")
    if sampler_name is not None:
        name = sampler_name.split("/")[-1] if isinstance(sampler_name, str) else sampler_name
        entry = MENU_ENTRY.get(name)
        if entry is None:
            problems.append(f"sampler_name {sampler_name!r} names no RES4LYF method (the original accepts it "
                            f"at queue time and fails when sampling)")
        elif sampler_name.startswith(IMPLICIT_PREFIXES) != entry.startswith(IMPLICIT_PREFIXES):
            # The original picks implicit or explicit mode from the folder as written, not from the method's
            # menu entry, so this spelling runs the method differently from the case the envelope admits.
            problems.append(f"sampler_name {sampler_name!r} runs {name} in a different mode from its menu entry "
                            f"{entry!r}; use the menu entry")
        elif name not in ADMITTED_METHODS:
            problems.append(f"sampler_name {sampler_name!r} needs more model evaluations per step than the V2 "
                            f"sampling budget allows (3 per step)")
    if isinstance(cfg, (int, float)) and cfg < 0:
        problems.append("a negative cfg selects channelwise CFG, which needs a post-CFG model patch")
    if isinstance(seed, int) and seed < 0:
        problems.append("seed -1 is not supported; set a non-negative seed")
    if isinstance(denoise, (int, float)) and denoise == 0:
        problems.append("denoise 0 fails in the original (RES4LYF get_sigmas returns a tuple); refused")
    if scheduler == "kl_optimal" and steps == 1:
        problems.append("kl_optimal with 1 step gives NaN sigmas in the original; refused")
    if scheduler == "bong_tangent" and steps == 1:
        problems.append("bong_tangent with 1 step divides by zero in the original; refused")
    return problems


# --------------------------------------------------------------------------------------------------------------- #
# Exact replicas of the original's in-envelope setup (beta/samplers.py at 057a913e)
# --------------------------------------------------------------------------------------------------------------- #
def generate_init_noise(x, seed, noise_type_init, noise_stdev, noise_mean, noise_normalize,
                        sigma_max, sigma_min, alpha_init=None, k_init=None, EO=None):
    """Copied from beta/samplers.py:71-107 (only the noise generator classes come from the vendored module)."""
    if noise_type_init == "none" or noise_stdev == 0.0:
        return torch.zeros_like(x)

    out_dtype = x.dtype
    if EO is not None:
        noise_dtype = EO("noise_dtype", EO("default_dtype", torch.float64, debugMode=2), debugMode=2)
    else:
        noise_dtype = torch.float64
    x = x.to(noise_dtype)

    if EO is not None and EO("bypass_noise_norm") and noise_type_init == "gaussian":
        _refuse("extra option bypass_noise_norm uses core prepare_noise")

    noise_sampler_init = NOISE_GENERATOR_CLASSES_SIMPLE.get(noise_type_init)(
        x=x, seed=seed, sigma_max=sigma_max, sigma_min=sigma_min
    )

    if noise_type_init == "fractal":
        noise_sampler_init.alpha = alpha_init
        noise_sampler_init.k = k_init
        noise_sampler_init.scale = 0.1

    noise = noise_sampler_init(sigma=sigma_max * noise_stdev, sigma_next=sigma_min)

    if noise_normalize and noise.std() > 0:
        channelwise = EO("init_noise_normalize_channelwise", "true") if EO else "true"
        channelwise = True if channelwise == "true" else False
        noise = normalize_zscore(noise, channelwise=channelwise, inplace=True)

    noise *= noise_stdev
    noise = (noise - noise.mean()) + noise_mean
    return noise.to(out_dtype)


# OPTIONS keys whose effect this port reproduces exactly. Any other key is refused by name before sampling.
OPTION_KEYS_ADMITTED = frozenset({
    # ClownsharKSampler_Beta's own OPTIONS output, chained into a later sampler
    "noise_type_sde", "noise_type_sde_substep", "eta", "eta_substep", "noise_type_init", "noise_stdev",
    "denoise_alt",
    # SharkOptions_Beta
    "noise_init_stdev", "channelwise_cfg",
    # ClownOptions_DetailBoost_Beta
    "noise_scaling_weight", "noise_scaling_type", "noise_scaling_mode", "noise_scaling_eta", "noise_scaling_cycles",
    "noise_scaling_weights", "noise_scaling_etas", "noise_boost_step", "noise_boost_substep",
    "noise_boost_normalize",
    # ClownOptions_SigmaScaling_Beta
    "noise_anchor", "s_noise", "s_noise_substep", "d_noise", "d_noise_start_step", "d_noise_inv",
    "d_noise_inv_start_step", "s_noises", "s_noises_substep",
})
# Init-noise types proven exact in parity; "brownian" needs core's Brownian-tree sampler (refused)
INIT_NOISE_ADMITTED = frozenset(NOISE_GENERATOR_CLASSES_SIMPLE) - {"brownian"}


def option_problems(merged: dict) -> list[str]:
    """Which received OPTIONS this port cannot apply exactly."""
    problems = []
    unknown = sorted(set(merged) - OPTION_KEYS_ADMITTED)
    if unknown:
        problems.append(f"OPTIONS keys {unknown} are not converted yet")
    for key in ("noise_type_sde", "noise_type_sde_substep"):
        if key in merged and merged[key] != "gaussian":
            problems.append(f"OPTIONS {key}={merged[key]!r}: only 'gaussian' SDE noise is converted yet")
    if merged.get("channelwise_cfg"):
        problems.append("OPTIONS channelwise_cfg selects channelwise CFG, which needs a post-CFG model patch")
    if "noise_type_init" in merged and merged["noise_type_init"] not in INIT_NOISE_ADMITTED:
        problems.append(f"OPTIONS noise_type_init={merged['noise_type_init']!r} is not converted yet")
    elif merged.get("noise_type_init") == "wavelet" and getattr(_noise_classes, "pywt", None) is None:
        problems.append("OPTIONS noise_type_init='wavelet' needs PyWavelets, which this guest runtime lacks")
    if merged.get("noise_scaling_cycles", 1) != 1:
        problems.append("OPTIONS noise_scaling_cycles other than 1 repeats steps; not converted yet")
    for key in ("noise_boost_step", "noise_boost_substep"):
        if merged.get(key, 0.0) != 0.0:
            problems.append(f"OPTIONS {key}={merged[key]!r} is not converted yet (only 0.0)")
    # The loop multiplies the schedule by d_noise and divides it by d_noise_inv (rk_noise_sampler_beta.py:916-917,
    # rk_sampler_beta.py:2167-2174) and evaluates the model there. The original evaluates at any sigma; the host
    # accepts only finite, non-negative sigmas, so a factor that is not finite and positive is refused by name.
    for key in ("d_noise", "d_noise_inv"):
        value = merged.get(key, 1.0)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value <= 0:
            problems.append(f"OPTIONS {key}={value!r}: only finite positive values are converted (the loop would "
                            f"evaluate the model at negative or non-finite sigmas, which the host refuses)")
    return problems


def resolve_options(options_inputs: dict, *, eta, denoise):
    """ClownsharKSampler_Beta.execute's option handling for the admitted keys, in the original's order
    (beta/samplers.py:1693-1843). Returns (options_mgr after its updates, resolved values)."""
    options_mgr = OptionsManager(options_group=options_inputs)
    eta_substep = eta
    noise_type_init = "gaussian"
    noise_stdev = 1.0
    denoise_alt = 1.0
    channelwise_cfg = False
    if denoise < 0:
        denoise_alt = -denoise
        denoise = 1.0

    noise_type_sde = options_mgr.get('noise_type_sde', "gaussian")
    noise_type_sde_substep = options_mgr.get('noise_type_sde_substep', "gaussian")
    options_mgr.update('noise_type_sde', noise_type_sde)
    options_mgr.update('noise_type_sde_substep', noise_type_sde_substep)
    eta = options_mgr.get('eta', eta)
    eta_substep = options_mgr.get('eta_substep', eta_substep)
    options_mgr.update('eta', eta)
    options_mgr.update('eta_substep', eta_substep)

    noise_type_init = options_mgr.get('noise_type_init', noise_type_init)
    noise_stdev = options_mgr.get('noise_stdev', noise_stdev)
    denoise_alt = options_mgr.get('denoise_alt', denoise_alt)
    channelwise_cfg = options_mgr.get('channelwise_cfg', channelwise_cfg)
    options_mgr.update('noise_type_init', noise_type_init)
    options_mgr.update('noise_stdev', noise_stdev)
    options_mgr.update('denoise_alt', denoise_alt)

    # SharkSampler.main reads the init-noise settings again from the same options (beta/samplers.py:257-259)
    shark_noise_stdev = options_mgr.get('noise_init_stdev', noise_stdev)
    shark_noise_type_init = options_mgr.get('noise_type_init', noise_type_init)
    resolved = {
        "eta": eta, "eta_substep": eta_substep, "noise_type_sde_substep": noise_type_sde_substep,
        "denoise": denoise, "denoise_alt": denoise_alt, "channelwise_cfg": channelwise_cfg,
        "noise_type_init": shark_noise_type_init, "noise_stdev": shark_noise_stdev,
    }
    return options_mgr, resolved


def rk_kwargs(*, eta, sampler_name, steps_to_run, bongmath, seed, options_dict, eta_substep=None,
              noise_type_sde_substep="gaussian"):
    """The keyword arguments the original passes to sample_rk_beta.

    For in-envelope inputs this mirrors two steps:
    - ClownSamplerAdvanced_Beta.execute building the rk_beta extra_options (beta/samplers.py:1354-1543), with the
      OPTIONS that ClownsharKSampler_Beta passes down as {"options0": options_mgr.as_dict()} (:1905);
    - SharkSampler.main's edits to them (beta/samplers.py:285-299, 368-373, 400, 589-600, 771-775, 861).
    The per-run tensors (state_info, image_initial, noise_initial, outer_sigmas_len) are added by the caller.
    """
    eta_substep = eta if eta_substep is None else eta_substep
    options_mgr = OptionsManager(options_group={"options0": options_dict})
    extra_options = "\n"
    extra_options += "\n" + options_mgr.get('extra_options', "")
    EO = ExtraOptions(extra_options)
    default_dtype = EO("default_dtype", torch.float64)
    rk_type, implicit_sampler_name = process_sampler_name(sampler_name)

    noise_type_sde = options_mgr.get('noise_type_sde', "gaussian")
    noise_mode_sde = options_mgr.get('noise_mode_sde', "hard")
    eta = options_mgr.get('eta', eta)
    eta_substep = options_mgr.get('eta_substep', eta_substep)
    # ClownOptions_DetailBoost_Beta's keys (Advanced reads the values ClownsharKSampler_Beta resolved from the same
    # options with its defaults, :1629-1640 and :1377-1388)
    detail = {
        "noise_scaling_weight": options_mgr.get('noise_scaling_weight', 0.0),
        "noise_scaling_type": options_mgr.get('noise_scaling_type', "sampler"),
        "noise_scaling_mode": options_mgr.get('noise_scaling_mode', "linear"),
        "noise_scaling_eta": options_mgr.get('noise_scaling_eta', 0.0),
        "noise_scaling_cycles": options_mgr.get('noise_scaling_cycles', 1),
        "noise_scaling_weights": options_mgr.get('noise_scaling_weights', None),
        "noise_scaling_etas": options_mgr.get('noise_scaling_etas', None),
        "noise_boost_step": options_mgr.get('noise_boost_step', 0.0),
        "noise_boost_substep": options_mgr.get('noise_boost_substep', 0.0),
        "noise_boost_normalize": options_mgr.get('noise_boost_normalize', True),
    }
    # ClownOptions_SigmaScaling_Beta's keys. ClownsharKSampler_Beta reads them with its own defaults
    # (beta/samplers.py:1641-1648, :1798-1805) and passes the values down (:1924-1930); Advanced reads them again from
    # the same options with those values as defaults (:1389-1396). s_noises and s_noises_substep are not passed
    # down, so Advanced reads them with None (:1438-1439). Every read is options.get(key, default); a key that the
    # options node set to None (an unlinked SIGMAS input) stays None, as there.
    noise_anchor = options_mgr.get('noise_anchor', 1.0)
    s_noise = options_mgr.get('s_noise', 1.0)
    s_noise_substep = options_mgr.get('s_noise_substep', 1.0)
    d_noise = options_mgr.get('d_noise', 1.0)
    d_noise_start_step = options_mgr.get('d_noise_start_step', 0)
    d_noise_inv = options_mgr.get('d_noise_inv', 1.0)
    d_noise_inv_start_step = options_mgr.get('d_noise_inv_start_step', 0)
    s_noises = options_mgr.get('s_noises', None)
    s_noises_substep = options_mgr.get('s_noises_substep', None)
    rescale_floor = EO("rescale_floor")

    # beta/samplers.py:1441-1449
    etas = initialize_or_scale(None, eta, MAX_STEPS).to(default_dtype)
    etas_substep = initialize_or_scale(None, eta_substep, MAX_STEPS).to(default_dtype)
    s_noises = initialize_or_scale(s_noises, s_noise, MAX_STEPS).to(default_dtype)
    s_noises_substep = initialize_or_scale(s_noises_substep, s_noise_substep, MAX_STEPS).to(default_dtype)
    etas = F.pad(etas, (0, MAX_STEPS), value=0.0)
    etas_substep = F.pad(etas_substep, (0, MAX_STEPS), value=0.0)
    s_noises = F.pad(s_noises, (0, MAX_STEPS), value=1.0)
    s_noises_substep = F.pad(s_noises_substep, (0, MAX_STEPS), value=1.0)

    kw = {
        "eta": eta, "eta_substep": eta_substep, "alpha": -1.0, "k": 1.0, "c1": 0.0, "c2": 0.5, "c3": 1.0,
        "cfgpp": 0.0, "noise_sampler_type": noise_type_sde, "noise_sampler_type_substep": noise_type_sde_substep,
        "noise_mode_sde": noise_mode_sde, "noise_seed": -1, "rk_type": rk_type,
        "implicit_sampler_name": implicit_sampler_name, "implicit_steps_diag": 0, "implicit_steps_full": 0,
        "LGW_MASK_RESCALE_MIN": rescale_floor, "sigmas_override": None, "sde_noise": [],
        "extra_options": extra_options, "sampler_mode": "standard", "etas": etas, "etas_substep": etas_substep,
        "s_noises": s_noises, "s_noises_substep": s_noises_substep, "epsilon_scales": None,
        "regional_conditioning_weights": None, "guides": None, "frame_weights_mgr": None,
        "noise_mode_sde_substep": "hard", **detail, "noise_anchor": noise_anchor, "s_noise": s_noise,
        "s_noise_substep": s_noise_substep, "d_noise": d_noise, "d_noise_start_step": d_noise_start_step,
        "d_noise_inv": d_noise_inv, "d_noise_inv_start_step": d_noise_inv_start_step,
        "overshoot_mode": "hard", "overshoot_mode_substep": "hard",
        "overshoot": 0.0, "overshoot_substep": 0.0, "BONGMATH": bongmath, "implicit_type": "bongmath",
        "implicit_type_substeps": "bongmath", "rk_swaps": [], "steps_to_run": steps_to_run, "sde_mask": None,
        "momentum": 0.0,
    }
    # SharkSampler.main (its own OptionsManager over the same options dict)
    shark_mgr = OptionsManager(options_dict)
    kw["start_at_step"] = shark_mgr.get('start_at_step', -1)
    kw["tile_sizes"] = shark_mgr.get('tile_sizes', None)
    kw["unsample_bongmath"] = shark_mgr.get('unsample_bongmath', kw["BONGMATH"])
    kw["flow_sync_eps"] = shark_mgr.get('flow_sync_eps', 0.0)
    kw["steps_to_run"] = steps_to_run
    kw.pop("cfg_cw", None)
    kw = copy.deepcopy(kw)
    if kw["noise_seed"] == -1 and seed != -1:
        kw["noise_seed"] = seed + 1
    kw["sampler_mode"] = "standard"
    shark_extra = "\n"
    shark_extra += "\n" + shark_mgr.get('extra_options', "")
    shark_extra += "\n"
    shark_extra += kw["extra_options"]
    kw["extra_options"] = shark_extra
    return kw


def final_step_fires(outer, sigma_min, steps_to_run, *, sigma_max=None, d_noise=1.0, d_noise_start_step=0,
                     d_noise_inv=1.0, d_noise_inv_start_step=0):
    """Whether the loop ends with RES4LYF's no-evaluation final step, which applies the MODEL's calculate_denoised
    (rk_sampler_beta.py:2202-2209). It mirrors, for standard mode:
    - NS.prepare_sigmas (rk_noise_sampler_beta.py:916-944): the d_noise scaling when d_noise_start_step is 0; drop
      consecutive duplicates; clamp the last nonzero sigma up to sigma_min, or insert sigma_min when it is more
      than 1e-4 away;
    - the loop length (rk_sampler_beta.py:480-487);
    - the loop's rescaling after each step (rk_sampler_beta.py:2167-2174): times d_noise at d_noise_start_step and
      divided by d_noise_inv at d_noise_inv_start_step, each followed by a division by sigma_max when the schedule
      then exceeds it. This can move the last nonzero sigma off sigma_min before the final check.
    NS holds sigma_min and sigma_max as the model's float32 values in float64 (rk_noise_sampler_beta.py:70-71).
    With the default scaling (d_noise and d_noise_inv 1, start steps 0) this is the round-3 rule unchanged.
    """
    sigmas = outer.clone()
    if d_noise_start_step == 0:
        sigmas = sigmas.clone() * d_noise
    keep = torch.cat((torch.tensor([True]), torch.diff(sigmas) != 0))
    sigmas = sigmas[keep]
    smin = torch.tensor(sigma_min, dtype=torch.float32).to(torch.float64)
    if sigmas.numel() >= 2 and sigmas[-1] == 0:
        if sigmas[-2] < smin:
            sigmas[-2] = smin
        elif (sigmas[-2] - smin).abs() > 1e-4:
            sigmas = torch.cat((sigmas[:-1], smin.unsqueeze(0), sigmas[-1:]))
    if sigmas.numel() < 2:
        return False
    num_steps = len(sigmas) - 2 if sigmas[-1] == 0 else len(sigmas) - 1
    run = num_steps if steps_to_run < 0 else min(num_steps, steps_to_run)
    rescales = (d_noise_start_step, d_noise_inv_start_step)
    if any(1 <= start <= run for start in rescales):
        if sigma_max is None:
            raise ValueError("sigma_max is required when the schedule is rescaled during the loop")
        smax = torch.tensor(sigma_max, dtype=torch.float32).to(torch.float64)
        for step in range(1, run + 1):
            if d_noise_start_step == step:
                sigmas = sigmas.clone() * d_noise
                if sigmas.max() > smax:
                    sigmas = sigmas / smax
            if d_noise_inv_start_step == step:
                sigmas = sigmas.clone() / d_noise_inv
                if sigmas.max() > smax:
                    sigmas = sigmas / smax
    return run == len(sigmas) - 2 and bool(sigmas[-1] == 0) and bool(sigmas[-2] == smin)


def reshape_mask(input_mask, output_shape):
    """Copied from ComfyUI core comfy/utils.py:1363-1382 (with repeat_to_batch_size, :910-915) at 6257422b."""
    dims = len(output_shape) - 2
    if dims == 1:
        scale_mode = "linear"
    if dims == 2:
        input_mask = input_mask.reshape((-1, 1, input_mask.shape[-2], input_mask.shape[-1]))
        scale_mode = "bilinear"
    if dims == 3:
        if len(input_mask.shape) < 5:
            input_mask = input_mask.reshape((1, 1, -1, input_mask.shape[-2], input_mask.shape[-1]))
        scale_mode = "trilinear"
    mask = torch.nn.functional.interpolate(input_mask, size=output_shape[2:], mode=scale_mode)
    if mask.shape[1] < output_shape[1]:
        mask = mask.repeat((1, output_shape[1]) + (1,) * dims)[:, :output_shape[1]]
    batch_size = output_shape[0]
    if mask.shape[0] > batch_size:
        mask = mask.narrow(0, 0, batch_size)
    elif mask.shape[0] < batch_size:
        mask = mask.repeat([math.ceil(batch_size / mask.shape[0])] + [1] * (len(mask.shape) - 1)).narrow(
            0, 0, batch_size)
    return mask


# --------------------------------------------------------------------------------------------------------------- #
# The guest-side model the vendored loop calls
# --------------------------------------------------------------------------------------------------------------- #
class _Named:
    def _get_name(self):
        return "SecureHostModel"


class _InnerModel:
    def __init__(self, model_sampling):
        self.model_sampling = model_sampling
        self.device = torch.device("cpu")
        self.diffusion_model = _Named()


class _Patcher:
    def __init__(self):
        self.model = type("HostModel", (), {"diffusion_model": _Named()})()


class _Guider:
    def __init__(self, model_sampling):
        self.inner_model = _InnerModel(model_sampling)
        self.conds = {}
        self.model_patcher = _Patcher()


class GuestModel:
    """Stands where the original passes KSAMPLER's model_k: calling it runs ONE host model evaluation."""

    def __init__(self, broker, loop, model_sampling, stats):
        self.inner_model = _Guider(model_sampling)
        self._broker = broker
        self._loop = loop
        self._stats = stats

    def __call__(self, x, sigma, **_extra_args):
        flat = sigma.detach().reshape(-1)
        if flat.numel() > 1 and not bool((flat == flat[0]).all()):
            _refuse("per-sample sigmas within one model call")
        value = float(flat[0].item())
        future = asyncio.run_coroutine_threadsafe(self._broker.denoise(x, value), self._loop)
        denoised, _uncond = future.result()
        self._stats["denoise_calls"] += 1
        self._stats["unpreviewed"] = True
        return denoised


# --------------------------------------------------------------------------------------------------------------- #
# The node
# --------------------------------------------------------------------------------------------------------------- #
class ClownsharKSamplerBetaV2(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("closures", "raw", "sample")

    @classmethod
    def define_schema(cls):
        # The original's own V3 schema, frozen from upstream at 057a913e (see _secure_runtime.py)
        return schema_for(NODE_ID)

    @classmethod
    def validate_inputs(cls, sampler_name=None, scheduler=None, steps=None, cfg=None, seed=None,
                        sampler_mode=None, denoise=None):
        values = {"sampler_name": sampler_name, "scheduler": scheduler, "steps": steps, "cfg": cfg, "seed": seed,
                  "sampler_mode": sampler_mode, "denoise": denoise}
        problems = core_value_problems(values)  # what core would refuse for the original
        if problems:
            return f"{PREFIX}: " + "; ".join(problems)
        problems = envelope_problems(**values)
        if problems:
            return f"{PREFIX}: " + "; ".join(problems)
        return True

    @classmethod
    async def execute(cls, eta=0.5, sampler_name=DEFAULT_SAMPLER, scheduler="beta57", steps=30, steps_to_run=-1,
                      denoise=1.0, cfg=5.5, seed=0, sampler_mode="standard", bongmath=True, model=None,
                      positive=None, negative=None, latent_image=None, sigmas=None, guides=None,
                      options_group=None):
        problems = envelope_problems(sampler_name=sampler_name, scheduler=scheduler, steps=steps, cfg=cfg,
                                     seed=seed, sampler_mode=sampler_mode, denoise=denoise)
        if problems:
            _refuse("; ".join(problems))
        async with _RUN_LOCK:
            try:
                return await _run(eta=eta, sampler_name=sampler_name, scheduler=scheduler, steps=steps,
                                  steps_to_run=steps_to_run, denoise=denoise, cfg=cfg, seed=seed, bongmath=bongmath,
                                  model=model, positive=positive, negative=negative, latent_image=latent_image,
                                  sigmas=sigmas, guides=guides, options_group=options_group)
            finally:
                _ACTIVE["handler"] = None


TABLE_PROBE_STEPS = 1000  # core's "simple" schedule over exactly the table length returns the whole table

# Custom-sampler programs. A retained program lives until its prompt ends, and the platform caps how many a guest
# may hold (transport/wire.py: MAX_RETAINED_CLOSURES). So the node retains ONE generic program per prompt and
# reuses it for every pass and every execution. Before each ctx.sample, it names the handler for that pass.
_PROGRAMS: dict = {}            # prompt id -> ClosureRef of the generic program
_ACTIVE: dict = {"handler": None}
_RUN_LOCK = asyncio.Lock()      # one sampler run at a time per guest, so the active handler is unambiguous


async def _generic_program(broker, latent, host_sigmas):
    handler = _ACTIVE["handler"]
    if handler is None:
        raise RuntimeError(f"{PREFIX}: sampler program invoked outside a pass")
    return await handler(broker, latent, host_sigmas)


async def _sampler_for(ctx, handler):
    """A host SAMPLER that runs ``handler`` for the next pass."""
    _ACTIVE["handler"] = handler
    prompt_id = getattr(ctx.closures, "_prompt_id", None)
    closure = _PROGRAMS.get(prompt_id) if prompt_id else None
    if closure is None:
        closure = await ctx.closures.retain("custom_sampler", _generic_program)
        if prompt_id:
            _PROGRAMS.clear()  # earlier prompts' programs were released with those prompts
            _PROGRAMS[prompt_id] = closure
    return await closure.as_sampler()


async def _schedule_pass(ctx, model, positive, negative, latent_ref, cfg, seed, scheduler, total, stats):
    """One zero-evaluation host pass. Given a scheduler name, ctx.sample builds the schedule with core's
    calculate_sigmas (transport/host.py:1277-1285). The capture closure records the float32 schedule and the
    model's schedule parameters, and makes no denoise call."""
    box = {}

    async def capture(broker, latent, host_sigmas):
        box["table"] = host_sigmas.detach().to(device="cpu").clone()
        stats["params"] = await broker.schedule_parameters()
        return latent

    sampler = await _sampler_for(ctx, capture)
    await ctx.sample(latent_ref, int(total), model=model, positive=positive, negative=negative, cfg=float(cfg),
                     seed=int(seed), sampler=sampler, scheduler=scheduler, denoise=1.0, disable_noise=True,
                     fix_empty_latent=False)
    stats["zero_evaluation_passes"] += 1
    table = box["table"]
    if table.dtype != torch.float32:
        _refuse(f"host schedule dtype {table.dtype} is not float32")
    return table


def _provider_result(values, steps):
    """The host's checks on a scheduler provider's result (schedulerproviders.py:213-229), applied unchanged to
    the same provider function run in this guest."""
    result = torch.as_tensor(values, dtype=torch.float32, device="cpu")
    if result.ndim != 1 or not 2 <= len(result) <= steps + 1:
        _refuse("the scheduler returned a schedule of the wrong shape")
    if not bool(torch.isfinite(result).all()) or bool((result < 0).any()):
        _refuse("the scheduler returned invalid sigma values")
    if len(result) > 1 and bool((result[1:] > result[:-1]).any()):
        _refuse("the scheduler returned an increasing schedule")
    if float(result[-1]) != 0.0:
        _refuse("the scheduler returned a schedule that does not end at zero")
    return result


async def _local_schedule(ctx, model, positive, negative, latent_ref, cfg, seed, scheduler, total, sigma_min,
                          sigma_max, stats):
    """beta57 and bong_tangent computed in this guest by the pack's own provider functions (schedulers.py), with
    the host's provider checks. Same function, same inputs, same result as the provider path, without starting a
    separate scheduler guest for every run. Returns None when the model's sigma table cannot be confirmed; the
    caller then uses the registered provider through the host."""
    from . import schedulers

    probe = await _schedule_pass(ctx, model, positive, negative, latent_ref, cfg, seed, "simple",
                                 TABLE_PROBE_STEPS, stats)
    if scheduler == "bong_tangent":  # projection "none": no model data
        return _provider_result(schedulers.bong_tangent(None, total, {}), total)
    # simple_scheduler(model_sampling, N) takes sigmas[-(1 + int(x * len/N))]: with N == len it is the whole table,
    # reversed. It is that iff it rises strictly from the model's sigma_min to its sigma_max.
    table = probe[:-1].flip(0)
    whole = (len(table) == TABLE_PROBE_STEPS and bool((table[1:] > table[:-1]).all())
             and float(table[0]) == sigma_min and float(table[-1]) == sigma_max)
    if not whole:
        return None
    # The "model_sigmas" projection is the float64 copy of the float32 table (schedulerproviders.py:190-210).
    return _provider_result(schedulers.beta57(table.to(torch.float64).tolist(), total, {}), total)


async def _outer_sigmas(ctx, model, positive, negative, latent_ref, cfg, seed, scheduler, steps, denoise,
                        sigmas_ref, denoise_alt, stats, sigma_min, sigma_max):
    """The original's outer schedule (beta/samplers.py:404-410 with sigmas.py:1398-1430), float64."""
    if sigmas_ref is not None:
        count = await sigmas_ref.steps()
        values = [await sigmas_ref.value_at(i) for i in range(count + 1)]
        outer = torch.tensor(values, dtype=torch.float64)
        outer *= denoise
    else:
        total = steps
        if denoise < 1.0:
            total = int(steps / denoise)
        table = None
        if scheduler in ("beta57", "bong_tangent"):
            table = await _local_schedule(ctx, model, positive, negative, latent_ref, cfg, seed, scheduler, total,
                                          sigma_min, sigma_max, stats)
            stats["schedule_source"] = "guest" if table is not None else "provider"
        if table is None:
            # Upstream get_sigmas makes the same core calls on the same model_sampling; beta57 and bong_tangent
            # otherwise come from this pack's scheduler providers registered on the host.
            table = await _schedule_pass(ctx, model, positive, negative, latent_ref, cfg, seed, scheduler, total,
                                         stats)
        outer = table[-(steps + 1):].to(torch.float64)
    outer *= denoise_alt
    return outer


async def _run(*, eta, sampler_name, scheduler, steps, steps_to_run, denoise, cfg, seed, bongmath, model, positive,
               negative, latent_image, sigmas, guides, options_group):
    if guides is not None:
        _refuse("latent guides are not in the reduced envelope")
    # OPTIONS: Autogrow delivers {"options0": dict, ...}; tensor entries arrive as tensor refs
    options_inputs = {}
    for name, value in (options_group or {}).items():
        if value is not None:
            options_inputs[name] = await materialize_options(value)
    problems = option_problems(OptionsManager(options_group=options_inputs).merged)
    if problems:
        _refuse("; ".join(problems))
    if model is None:
        _refuse("model must be connected (the original takes it from a chained sampler's latent, which a V2 "
                "latent cannot carry)")
    if latent_image is None:
        _refuse("latent_image must be connected")

    ctx = sdk.ctx()
    latent_value = await latent_image.value()
    if CHAIN_KEY in latent_value and (positive is None or negative is None):
        _refuse("positive and negative must be connected when the latent comes from another ClownsharKSampler: "
                "the original reuses that sampler's conditioning from the latent, which a V2 latent cannot carry")
    if positive is None or negative is None:
        _refuse("positive and negative must both be connected; the original's empty-conditioning fallback is not "
                "converted yet")
    unsupported = sorted(set(latent_value) - {"samples", "noise_mask", "batch_index", CHAIN_KEY})
    if unsupported:
        _refuse(f"latent fields {unsupported} are not in the reduced envelope")

    family = await model.family()
    is_flow = await model.is_flow()

    # ClownsharKSampler_Beta.execute: denoise < 0 means denoise_alt (beta/samplers.py:1709-1711), then the options
    options_mgr, resolved = resolve_options(options_inputs, eta=eta, denoise=denoise)
    options_dict = options_mgr.as_dict()
    denoise = resolved["denoise"]
    denoise_alt = resolved["denoise_alt"]

    # SharkSampler.main: fix empty latent channels, work dtype, noise (beta/samplers.py:355-361, 602-628)
    fixed_ref = await model.fix_empty_latent_channels(latent_image)
    fixed_value = await fixed_ref.value()
    samples = fixed_value["samples"]
    if not isinstance(samples, torch.Tensor) or samples.ndim != 4:
        _refuse("only 4-D image latents are in the reduced envelope")
    noise_mask = latent_value.get("noise_mask")
    EO = ExtraOptions("\n\n")
    x = samples.clone().to(torch.float32)
    sigma_max = await model.sigma_for_percent(0.0, actual_endpoints=True)
    sigma_min = await model.sigma_for_percent(1.0, actual_endpoints=True)
    sigma_max_t = torch.tensor(sigma_max, dtype=torch.float32)
    sigma_min_t = torch.tensor(sigma_min, dtype=torch.float32)
    noise = generate_init_noise(x=x.clone(), seed=seed, noise_type_init=resolved["noise_type_init"],
                                noise_stdev=resolved["noise_stdev"], noise_mean=0.0, noise_normalize=True,
                                sigma_max=sigma_max_t, sigma_min=sigma_min_t, alpha_init=-1.0, k_init=1.0, EO=EO)

    stats = {"denoise_calls": 0, "previews": 0, "unpreviewed": False, "zero_evaluation_passes": 0}
    main_latent = {"samples": x}
    if noise_mask is not None:
        main_latent["noise_mask"] = noise_mask.clone()
    main_latent_ref = await sdk.LatentRef.from_value(main_latent)

    outer = await _outer_sigmas(ctx, model, positive, negative, main_latent_ref, cfg, seed, scheduler, steps,
                                abs(denoise), sigmas, denoise_alt, stats, sigma_min, sigma_max)
    if outer.numel() < 2 or not bool(torch.isfinite(outer).all()):
        _refuse("the schedule has fewer than two finite sigmas")
    if bool((outer[:-1] < outer[1:]).any()) or bool((outer < 0).any()):
        _refuse("the custom-sampler host accepts only non-negative, non-increasing schedules")

    kw = rk_kwargs(eta=resolved["eta"], sampler_name=sampler_name, steps_to_run=steps_to_run, bongmath=bongmath,
                   seed=seed, options_dict=options_dict, eta_substep=resolved["eta_substep"],
                   noise_type_sde_substep=resolved["noise_type_sde_substep"])
    stash = {"x0": None, "x_final": None, "params": None, "failure": None, "state_info_out": None}
    fires = final_step_fires(outer, sigma_min, kw["steps_to_run"], sigma_max=sigma_max, d_noise=kw["d_noise"],
                             d_noise_start_step=kw["d_noise_start_step"], d_noise_inv=kw["d_noise_inv"],
                             d_noise_inv_start_step=kw["d_noise_inv_start_step"])

    def model_sampling_for(params):
        if params["parameterization"] == "const":
            if not (is_flow or family == "flux"):
                _refuse(f"this CONST-parameterized model (family {family!r}) is not a plain flow model the guest "
                        f"can confirm")
            return GuestCONST(sigma_min, sigma_max, float(params["noise_scale"]))
        if family not in EPS_FAMILIES:
            _refuse(f"this sigma-parameterized model (family {family!r}) is outside the EPS families the guest can "
                    f"confirm")
        if fires:
            _refuse("this schedule ends on the model's sigma_min, where the original applies the model's own "
                    "calculate_denoised; for a sigma-parameterized model the guest cannot confirm EPS against "
                    "V_PREDICTION/X0/EDM, which differ exactly there")
        return GuestEPS(sigma_min, sigma_max)

    if stats.get("params") is not None:
        model_sampling_for(stats["params"])  # refuse before the main pass when the schedule pass already knows

    async def main_program(broker, latent, host_sigmas):
        try:
            return await _main_program(broker, latent, host_sigmas)
        except BaseException as error:  # the host reports only "closure failed"; keep the real reason
            stash["failure"] = error
            return latent

    async def _main_program(broker, latent, host_sigmas):
        loop = asyncio.get_running_loop()
        params = await broker.schedule_parameters()
        stash["params"] = params
        ms = model_sampling_for(params)
        if not torch.equal(host_sigmas.detach().to(torch.float64).cpu(), outer):
            _refuse("host schedule differs from the node's schedule")
        guest_model = GuestModel(broker, loop, ms, stats)
        state_kw = dict(kw)
        state_kw["state_info"] = {}
        state_kw["state_info_out"] = {}
        state_kw["image_initial"] = x
        state_kw["noise_initial"] = noise
        state_kw["outer_sigmas_len"] = outer.shape[-1]

        def callback(payload):
            stash["x0"] = payload["denoised"]
            if stats["unpreviewed"] and not payload.get("final", False):
                asyncio.run_coroutine_threadsafe(
                    broker.preview(int(payload["i"]), payload["x"], float(payload["sigma"]),
                                   float(payload["sigma"]), payload["denoised"]), loop).result()
                stats["unpreviewed"] = False
                stats["previews"] += 1

        def run():
            extra_args = {"model_options": {"transformer_options": {}}, "seed": seed, "denoise_mask": None}
            return rk_sampler_beta.sample_rk_beta(guest_model, latent, outer.clone(), extra_args=extra_args,
                                                  callback=callback, disable=True, **state_kw)

        result = await asyncio.to_thread(run)
        stash["x_final"] = result
        stash["state_info_out"] = state_kw["state_info_out"]
        return result.to(dtype=latent.dtype, device=latent.device)

    async def passthrough_program(broker, latent, host_sigmas):
        del broker, host_sigmas
        x0 = stash["x0"]
        return x0.to(dtype=latent.dtype, device=latent.device)

    main_sampler = await _sampler_for(ctx, main_program)
    sigmas_ref = await sdk.SigmasRef._from_raw(outer.clone())
    noise_ref = await sdk.TensorRef._from_raw(noise.clone())
    sampled_ref, _host_denoised = await ctx.sample(
        main_latent_ref, int(outer.numel() - 1), model=model, positive=positive, negative=negative,
        cfg=float(cfg), seed=int(seed), sampler=main_sampler, noise=noise_ref, sigmas=sigmas_ref,
        return_denoised=True, fix_empty_latent=False)
    failure = stash["failure"]
    if isinstance(failure, OutOfEnvelope):
        raise OutOfEnvelope(str(failure))
    if failure is not None:
        raise RuntimeError(f"{PREFIX}: the sampling loop failed in the guest: "
                           f"{type(failure).__name__}: {failure}") from failure
    samples_out = (await sampled_ref.value())["samples"]

    # Post-sample mask blend, then the denoised output (beta/samplers.py:946-998, in that order)
    if noise_mask is not None:
        reshaped = reshape_mask(noise_mask, samples_out.shape).to(samples_out.device)
        samples_out = samples_out * reshaped + x.to(samples_out.device) * (1.0 - reshaped)

    if stash["x0"] is not None:
        pass_sampler = await _sampler_for(ctx, passthrough_program)
        zero_ref = await sdk.SigmasRef._from_raw(torch.zeros(2, dtype=torch.float64))
        processed_ref = await ctx.sample(
            main_latent_ref, 1, model=model, positive=positive, negative=negative, cfg=float(cfg), seed=int(seed),
            sampler=pass_sampler, sigmas=zero_ref, disable_noise=True, fix_empty_latent=False)
        stats["zero_evaluation_passes"] += 1
        x0_out = (await processed_ref.value())["samples"].to(torch.float32)
    else:
        x0_out = samples_out.to(torch.float32)

    out = {"samples": samples_out}
    out_denoised = {"samples": x0_out}
    if noise_mask is not None:
        out["noise_mask"] = noise_mask.clone()
        out_denoised["noise_mask"] = noise_mask.clone()
    # The original attaches the loop's state_info to both output latents (beta/samplers.py:1009-1010). Of it, a V2
    # latent carries the one entry a converted consumer reads in standard mode: the loop's final denoised estimate
    # (rk_sampler_beta.py:2254), which LatentUpscaleWithVAE decodes in place of the samples
    # (helper_sigma_preview_image_preproc.py:658-666). When the loop ran no step, the original's state is instead
    # the incoming latent's (a deep copy, beta/samplers.py:436; rk_sampler_beta.py:2231-2232), so the marker carries
    # the incoming marker's estimate, or none.
    chain = {"node": NODE_ID}
    state_info_out = stash["state_info_out"] or {}
    incoming = latent_value.get(CHAIN_KEY)
    if "denoised" in state_info_out:
        chain["denoised"] = state_info_out["denoised"]
    elif isinstance(incoming, dict) and "denoised" in incoming:
        chain["denoised"] = incoming["denoised"].clone()
    out[CHAIN_KEY] = chain
    out_denoised[CHAIN_KEY] = dict(chain)
    return io.NodeOutput(
        await sdk.LatentRef.from_value(out),
        await sdk.LatentRef.from_value(out_denoised),
        await export_options(options_dict),
    )
