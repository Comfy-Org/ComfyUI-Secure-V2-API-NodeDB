"""Secure Nodes V2: RES4LYF's sampler options nodes SharkOptions_Beta, ClownOptions_DetailBoost_Beta and
ClownOptions_SigmaScaling_Beta.

Bodies are copied from upstream 057a913e (beta/samplers_extensions.py). An OPTIONS value is a dict; its tensor
entries cross between nodes as tensor refs (materialized with ``raw()``, exported with ``_from_raw``), so the
values and dtypes arriving at the sampler are the original's.
Known differences (SECURE_CONVERSION.md):
- The original updates the incoming OPTIONS dict in place, which other consumers of that upstream output also
  see. V2 hands each node its own copy; the returned dict has the same entries in the same order.
- ClownOptions_DetailBoost_Beta builds its float64 tables on the CUDA device (samplers_extensions.py:292), so it
  fails on a CPU-only host. V2 builds the same values on the guest's CPU; the sampler moves them to the latent's
  device either way (rk_sampler_beta.py:781).
"""
from __future__ import annotations

from typing import Any

import torch
import torch.nn.functional as F

from comfy_api.latest import io, sdk

from ._secure_runtime import schema_for
from .res4lyf_core.beta.constants import MAX_STEPS
from .res4lyf_core.helper import initialize_or_scale


async def materialize(value: Any) -> Any:
    """A received OPTIONS value with its tensor refs replaced by the tensors (exact dtype and values)."""
    if isinstance(value, sdk.Ref):
        return await value.raw()
    if isinstance(value, dict):
        return {key: await materialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [await materialize(item) for item in value]
    if isinstance(value, tuple):
        return tuple([await materialize(item) for item in value])
    return value


async def export(value: Any) -> Any:
    """An OPTIONS value to return: tensors become tensor refs, everything else stays plain data."""
    if isinstance(value, torch.Tensor):
        return await sdk.TensorRef._from_raw(value)
    if isinstance(value, dict):
        return {key: await export(item) for key, item in value.items()}
    if isinstance(value, list):
        return [await export(item) for item in value]
    if isinstance(value, tuple):
        return tuple([await export(item) for item in value])
    return value


class SharkOptionsBetaV2(io.ComfyNode):
    """beta/samplers_extensions.py:892-927 (SharkOptions_Beta.main)."""
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("SharkOptions_Beta")

    @classmethod
    async def execute(cls, noise_type_init="gaussian", s_noise_init=1.0, denoise_alt=1.0, channelwise_cfg=False,
                      options=None) -> io.NodeOutput:
        options = await materialize(options) if options is not None else {}

        options['noise_type_init']  = noise_type_init
        options['noise_init_stdev'] = s_noise_init
        options['denoise_alt']      = denoise_alt
        options['channelwise_cfg']  = channelwise_cfg

        return io.NodeOutput(await export(options))


class ClownOptionsDetailBoostBetaV2(io.ComfyNode):
    """beta/samplers_extensions.py:225-351 (ClownOptions_DetailBoost_Beta.main), on the guest's CPU."""
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("ClownOptions_DetailBoost_Beta")

    @classmethod
    async def execute(cls, weight: float = 0.0, method: str = "sampler", mode: str = "linear", eta: float = 0.5,
                      start_step: int = 0, end_step: int = -1, weights=None, etas=None,
                      options=None) -> io.NodeOutput:
        noise_scaling_cycles      = 1
        noise_boost_step          = 0.0
        noise_boost_substep       = 0.0
        sampler_scaling_normalize = False

        noise_scaling_weight     = weight
        noise_scaling_type       = method
        noise_scaling_mode       = mode
        noise_scaling_eta        = eta
        noise_scaling_start_step = start_step
        noise_scaling_end_step   = end_step

        noise_scaling_weights = await weights.raw() if weights is not None else None
        noise_scaling_etas    = await etas.raw() if etas is not None else None

        options = await materialize(options) if options is not None else {}

        default_dtype = torch.float64
        default_device = torch.device('cpu')  # upstream: torch.device('cuda'); same values, see module docstring

        if noise_scaling_type.endswith("_normal"):
            sampler_scaling_normalize = True
            noise_scaling_type = noise_scaling_type[:-7]

        if noise_scaling_end_step == -1:
            noise_scaling_end_step = MAX_STEPS

        if noise_scaling_weights == None:
            noise_scaling_weights = initialize_or_scale(None, noise_scaling_weight, MAX_STEPS).to(default_dtype).to(default_device)

        if noise_scaling_etas == None:
            noise_scaling_etas = initialize_or_scale(None, noise_scaling_eta, MAX_STEPS).to(default_dtype).to(default_device)

        noise_scaling_prepend = torch.zeros((noise_scaling_start_step,), dtype=default_dtype, device=default_device)

        noise_scaling_weights = torch.cat((noise_scaling_prepend, noise_scaling_weights), dim=0)
        noise_scaling_etas    = torch.cat((noise_scaling_prepend, noise_scaling_etas),    dim=0)

        if noise_scaling_weights.shape[-1] > noise_scaling_end_step:
            noise_scaling_weights = noise_scaling_weights[:noise_scaling_end_step]

        if noise_scaling_etas.shape[-1] > noise_scaling_end_step:
            noise_scaling_etas = noise_scaling_etas[:noise_scaling_end_step]

        noise_scaling_weights = F.pad(noise_scaling_weights, (0, MAX_STEPS), value=0.0)
        noise_scaling_etas = F.pad(noise_scaling_etas, (0, MAX_STEPS), value=0.0)

        options['noise_scaling_weight']  = noise_scaling_weight
        options['noise_scaling_type']    = noise_scaling_type
        options['noise_scaling_mode']    = noise_scaling_mode
        options['noise_scaling_eta']     = noise_scaling_eta
        options['noise_scaling_cycles']  = noise_scaling_cycles

        options['noise_scaling_weights'] = noise_scaling_weights
        options['noise_scaling_etas']    = noise_scaling_etas

        options['noise_boost_step']      = noise_boost_step
        options['noise_boost_substep']   = noise_boost_substep
        options['noise_boost_normalize'] = sampler_scaling_normalize

        return io.NodeOutput(await export(options))


class ClownOptionsSigmaScalingBetaV2(io.ComfyNode):
    """beta/samplers_extensions.py:356-418 (ClownOptions_SigmaScaling_Beta.main). Unlinked SIGMAS inputs are
    stored as None, as there; linked ones as the exact tensors."""
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("ClownOptions_SigmaScaling_Beta")

    @classmethod
    async def execute(cls, noise_anchor_sde: float = 1.0, s_noise: float = 1.0, s_noise_substep: float = 1.0,
                      lying: float = 1.0, lying_start_step: int = 0, lying_inv: float = 1.0,
                      lying_inv_start_step: int = 1, s_noises=None, s_noises_substep=None,
                      options=None) -> io.NodeOutput:
        s_noises         = await s_noises.raw() if s_noises is not None else None
        s_noises_substep = await s_noises_substep.raw() if s_noises_substep is not None else None

        options = await materialize(options) if options is not None else {}

        options['noise_anchor']           = noise_anchor_sde
        options['s_noise']                = s_noise
        options['s_noise_substep']        = s_noise_substep
        options['d_noise']                = lying
        options['d_noise_start_step']     = lying_start_step
        options['d_noise_inv']            = lying_inv
        options['d_noise_inv_start_step'] = lying_inv_start_step

        options['s_noises']                = s_noises
        options['s_noises_substep']        = s_noises_substep

        return io.NodeOutput(await export(options))


__all__ = ["ClownOptionsDetailBoostBetaV2", "ClownOptionsSigmaScalingBetaV2", "SharkOptionsBetaV2", "export",
           "materialize"]
