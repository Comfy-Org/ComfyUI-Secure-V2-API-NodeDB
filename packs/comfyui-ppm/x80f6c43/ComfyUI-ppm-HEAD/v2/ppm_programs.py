"""Pack-owned tensor programs awaiting the generic retained-program bridge.

Nothing in this module is a host API implementation.  These are PPM's own
algorithms, separated from ComfyUI live objects so a bounded bridge can retain
and invoke them while MODEL/CLIP/SAMPLER weights remain host-owned.
"""
from __future__ import annotations

from typing import Any


PROGRAM_CONTRACTS = {
    "post_cfg": {
        "phase": "after each guided denoise prediction",
        "frequency": "at most once per model evaluation",
        "inputs": ("guided", "cond", "uncond", "latent", "sigma", "cfg"),
        "outputs": ("guided",),
        "stateful": False,
        "gpu_resident": True,
    },
    "pre_cfg": {
        "phase": "after conditional predictions, before CFG combination",
        "frequency": "at most once per model evaluation",
        "inputs": ("latent", "predictions", "presence", "sigma"),
        "outputs": ("predictions",),
        "stateful": False,
        "gpu_resident": True,
    },
    "block": {
        "phase": "selected UNet input/middle/output block",
        "frequency": "bounded by the host model's block count",
        "inputs": ("hidden", "skip", "sigma"),
        "outputs": ("hidden", "skip"),
        "stateful": False,
        "gpu_resident": True,
    },
    "latent_operation": {
        "phase": "when a downstream core node applies LATENT_OPERATION",
        "frequency": "once per downstream application",
        "inputs": ("latent",),
        "outputs": ("latent",),
        "stateful": False,
        "gpu_resident": True,
    },
    "conditioning_preprocess": {
        "phase": "before each bounded conditional model batch",
        "frequency": "at most once per model evaluation",
        "inputs": ("conditioning_embedding", "host_rng_noise", "sigma"),
        "outputs": ("conditioning_embedding",),
        "stateful": False,
        "gpu_resident": True,
    },
    "conditioning_selection": {
        "phase": "before host conditional batch construction",
        "frequency": "at most once per model evaluation",
        "inputs": ("presence", "sigma"),
        "outputs": ("presence",),
        "stateful": False,
        "gpu_resident": False,
    },
    "custom_sampler": {
        "phase": "one retained sampler invocation",
        "frequency": "one to three brokered denoise calls per sigma interval",
        "inputs": (
            "latent", "sigmas", "denoise_broker", "noise_broker",
            "preview_broker", "schedule_projection",
        ),
        "outputs": ("latent",),
        "stateful": True,
        "gpu_resident": True,
    },
    "attention_couple": {
        "phase": "cross-attention pre/post pair",
        "frequency": "bounded by host attention layers per model evaluation",
        "inputs": ("q", "k", "v", "masks", "conditioning", "shape"),
        "outputs": ("q", "k", "v", "attention_output"),
        "stateful": True,
        "gpu_resident": True,
    },
    "clip_token_weight_encoder": {
        "phase": "future CLIP token-weight encodes through the returned CLIP ref",
        "frequency": "once per downstream text encode",
        "inputs": ("component", "token_weight_pairs", "base_encode_broker"),
        "outputs": ("embedding", "pooled", "extras"),
        "stateful": False,
        "gpu_resident": True,
    },
    "scheduler_provider": {
        "phase": "host requests a declared scheduler by name",
        "frequency": "once per sampling invocation",
        "inputs": ("model_sampling_projection", "steps"),
        "outputs": ("sigmas",),
        "stateful": False,
        "gpu_resident": False,
    },
}


def _sigma_value(sigma: Any) -> float:
    if hasattr(sigma, "reshape"):
        sigma = sigma.reshape(-1)[0]
    if hasattr(sigma, "item"):
        sigma = sigma.item()
    return float(sigma)


def _inside_sigma_interval(
    sigma: Any, sigma_start: float, sigma_end: float,
) -> bool:
    value = _sigma_value(sigma)
    return not (
        (sigma_start >= 0.0 and value > sigma_start)
        or (sigma_end >= 0.0 and value <= sigma_end)
    )


def guidance_limiter_post(guided, cond, sigma, sigma_start, sigma_end):
    if not _inside_sigma_interval(sigma, sigma_start, sigma_end):
        return cond
    return guided


def cfg_limiter_scale(cfg, sigma, sigma_start, sigma_end):
    return (
        float(cfg)
        if _inside_sigma_interval(sigma, sigma_start, sigma_end)
        else 1.0
    )


def rescale_cfg_post(
    guided, cond, sigma, multiplier, alt_mode, sigma_start, sigma_end,
):
    import torch

    factor = float(multiplier)
    if factor == 0.0 or not _inside_sigma_interval(
        sigma, sigma_start, sigma_end
    ):
        return guided
    latent_dimensions = tuple(range(1, len(cond.shape)))
    positive_std = torch.std(cond, dim=latent_dimensions, keepdim=True)
    guided_std = torch.std(guided, dim=latent_dimensions, keepdim=True)
    rescaled = guided * (positive_std / guided_std)
    if bool(alt_mode):
        factor = factor * (1.0 - (positive_std / guided_std) ** 2)
    return factor * rescaled + (1.0 - factor) * guided


def renorm_cfg_post(
    guided, cond, sigma, renorm_cfg, sigma_start, sigma_end,
):
    import torch

    factor = float(renorm_cfg)
    if factor == 0.0 or not _inside_sigma_interval(
        sigma, sigma_start, sigma_end
    ):
        return guided
    latent_dimensions = tuple(range(1, len(cond.shape)))
    cond_norm = (
        torch.linalg.vector_norm(cond, dim=latent_dimensions, keepdim=True)
        * factor
    )
    guided_norm = torch.linalg.vector_norm(
        guided, dim=latent_dimensions, keepdim=True
    )
    return guided * (cond_norm / guided_norm).clamp(max=1.0)


def epsilon_scaling_post(
    guided, latent, sigma, scaling_factor, *, zsnr=False, sigma_max=None,
):
    factor = float(scaling_factor)
    if factor == 0.0:
        factor = 1e-9
    if (
        bool(zsnr)
        and sigma_max is not None
        and _sigma_value(sigma) >= float(sigma_max)
    ):
        return guided
    noise_prediction = latent - guided
    return latent - noise_prediction / factor


def score_tangential_damping(cond_score, uncond_score):
    import torch

    batch = cond_score.shape[0]
    cond_flat = cond_score.reshape(batch, 1, -1).float()
    uncond_flat = uncond_score.reshape(batch, 1, -1).float()
    score_matrix = torch.cat((uncond_flat, cond_flat), dim=1)
    try:
        _, _, vectors = torch.linalg.svd(score_matrix, full_matrices=False)
    except RuntimeError:
        _, _, vectors = torch.linalg.svd(
            score_matrix.cpu(), full_matrices=False
        )
    primary = vectors[:, 0:1, :].to(uncond_flat.device)
    damped = (uncond_flat @ primary.transpose(-2, -1)) * primary
    return damped.reshape_as(uncond_score).to(uncond_score.dtype)


def tangential_cfg_pre(
    latent,
    predictions,
    presence,
    sigma,
    multiplier,
    sigma_start,
    sigma_end,
):
    if (
        len(predictions) <= 1
        or len(presence) <= 1
        or not presence[0]
        or not presence[1]
        or not _inside_sigma_interval(sigma, sigma_start, sigma_end)
    ):
        return predictions
    cond_prediction, uncond_prediction = predictions[:2]
    uncond_damped = score_tangential_damping(
        latent - cond_prediction, latent - uncond_prediction
    )
    aligned = latent - uncond_damped
    output = (
        float(multiplier) * aligned
        + (1.0 - float(multiplier)) * uncond_prediction
    )
    return [cond_prediction, output, *predictions[2:]]


def cads_add_noise(conditioning, noise, scale, psi=1.0):
    source_mean, source_std = conditioning.mean(), conditioning.std()
    output = (1.0 - float(scale)) * conditioning + float(scale) * noise
    if float(psi) != 0.0:
        normalized = (
            (output - output.mean()) / output.std() * source_std + source_mean
        )
        output = float(psi) * normalized + (1.0 - float(psi)) * output
    return output


def cads_preprocess_tensors(
    tensors,
    noises,
    sigma,
    sigma_start,
    sigma_end,
    scale,
    psi=1.0,
):
    """Noise only host-selected c_concat/c_crossattn tensor payloads.

    The retained host adapter owns traversal and wrapper reconstruction; the
    pack receives no CONDRegular objects or model internals.
    """
    if len(tensors) != len(noises):
        raise ValueError("CADS tensor/noise lists must have equal length")
    sigma_value = _sigma_value(sigma)
    if not float(sigma_end) <= sigma_value <= float(sigma_start):
        return list(tensors)
    return [
        cads_add_noise(tensor, noise, scale, psi)
        for tensor, noise in zip(tensors, noises, strict=True)
    ]


def skip_first_step_presence(presence, sigma, skip_sigma):
    """Omit only the unconditioned branch above the configured threshold."""
    result = list(presence)
    if len(result) > 1 and _sigma_value(sigma) > float(skip_sigma):
        result[1] = False
    return result


def fourier_filter(value, threshold, scale):
    import torch

    if isinstance(value, list):
        value = value[0]
    if not isinstance(value, torch.Tensor):
        return value
    frequency = torch.fft.fftn(value.float(), dim=(-2, -1))
    frequency = torch.fft.fftshift(frequency, dim=(-2, -1))
    batch, channels, height, width = frequency.shape
    mask = torch.ones(
        (batch, channels, height, width), device=value.device
    )
    center_row, center_column = height // 2, width // 2
    amount = int(threshold)
    mask[
        ...,
        center_row - amount:center_row + amount,
        center_column - amount:center_column + amount,
    ] = float(scale)
    frequency = frequency * mask
    frequency = torch.fft.ifftshift(frequency, dim=(-2, -1))
    return torch.fft.ifftn(frequency, dim=(-2, -1)).real.to(value.dtype)


def _freeu_hidden_mean(hidden):
    import torch

    hidden_mean = hidden.mean(1).unsqueeze(1)
    batch = hidden_mean.shape[0]
    hidden_max, _ = torch.max(
        hidden_mean.view(batch, -1), dim=-1, keepdim=True
    )
    hidden_min, _ = torch.min(
        hidden_mean.view(batch, -1), dim=-1, keepdim=True
    )
    return (
        hidden_mean - hidden_min.unsqueeze(2).unsqueeze(3)
    ) / (
        hidden_max - hidden_min
    ).unsqueeze(2).unsqueeze(3)


def freeu_block(
    hidden,
    sigma,
    sigma_start,
    sigma_end,
    slice_b1,
    slice_b2,
    b1,
    b2,
):
    if not (float(sigma_end) < _sigma_value(sigma) <= float(sigma_start)):
        return hidden
    slice_b1 = max(min(1280, int(slice_b1)), 64)
    slice_b2 = max(min(min(slice_b1, 640), int(slice_b2)), 64)
    output = hidden.clone()
    if output.shape[1] == 1280:
        mean = _freeu_hidden_mean(output)
        output[:, :slice_b1] *= (float(b1) - 1.0) * mean + 1.0
    if output.shape[1] == 640:
        mean = _freeu_hidden_mean(output)
        output[:, :slice_b2] *= (float(b2) - 1.0) * mean + 1.0
    return output


def freeu_output_block(
    hidden,
    skip,
    sigma,
    sigma_start,
    sigma_end,
    slice_b1,
    slice_b2,
    b1,
    b2,
    s1,
    s2,
    threshold,
):
    if not (float(sigma_end) < _sigma_value(sigma) <= float(sigma_start)):
        return hidden, skip
    channels = hidden.shape[1]
    output = freeu_block(
        hidden, sigma, sigma_start, sigma_end,
        slice_b1, slice_b2, b1, b2,
    )
    if channels == 1280:
        skip = fourier_filter(skip, threshold, s1)
    elif channels == 640:
        skip = fourier_filter(skip, threshold, s2)
    return output, skip


def latent_tonemap_luminance(latent, tonemapper, multiplier):
    import torch

    luminance = latent[:, 0:1]
    magnitude = (
        torch.linalg.vector_norm(luminance, dim=1) + 1e-10
    )[:, None]
    normalized = luminance / magnitude
    dimensions = tuple(range(1, len(latent.shape)))
    mean = torch.mean(magnitude, dim=dimensions, keepdim=True)
    std = torch.std(magnitude, dim=dimensions, keepdim=True)
    top = (std * 5.0 + mean) * float(multiplier)
    mapped_input = magnitude / top
    if tonemapper == "reinhard":
        mapped = mapped_input / (mapped_input + 1.0)
    elif tonemapper == "mobius":
        mapped = (
            mapped_input * (1.0 + mapped_input)
        ) / (1.0 + mapped_input * mapped_input)
    elif tonemapper == "aces":
        mapped = (
            mapped_input * (mapped_input + 0.45)
        ) / (
            mapped_input * mapped_input + 0.91 * mapped_input + 0.91
        )
    else:
        raise ValueError(f"unknown luminance tonemapper {tonemapper!r}")
    output = latent.clone()
    output[:, 0:1] = normalized * mapped * top
    return output


__all__ = [
    "PROGRAM_CONTRACTS",
    "cads_add_noise",
    "cads_preprocess_tensors",
    "cfg_limiter_scale",
    "epsilon_scaling_post",
    "fourier_filter",
    "freeu_block",
    "freeu_output_block",
    "guidance_limiter_post",
    "latent_tonemap_luminance",
    "renorm_cfg_post",
    "rescale_cfg_post",
    "score_tangential_damping",
    "skip_first_step_presence",
    "tangential_cfg_pre",
]
