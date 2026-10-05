"""Pack-owned retained minimal-change sampler loop."""

from __future__ import annotations


async def minimal_change_flow(broker, latent, sigmas, max_change_per_step: float):
    """Run the pinned sampler algorithm through the invocation-only broker."""
    value = latent
    for step in range(len(sigmas) - 1):
        sigma = sigmas[step]
        sigma_next = sigmas[step + 1]
        denoised, _uncond = await broker.denoise(value, sigma)
        await broker.preview(step, value, sigma, sigma, denoised)

        if float(sigma_next) == 0.0:
            value = denoised
            break

        if float(sigma) > 1e-6:
            ratio = sigma_next / sigma
            proposed = ratio * value + (1.0 - ratio) * denoised
            delta = proposed - value
            relative_change = delta.abs().mean() / (value.abs().mean() + 1e-8)
            if float(relative_change) > max_change_per_step:
                scale = max_change_per_step / (relative_change + 1e-8)
                value = value + delta * scale
            else:
                value = proposed
        else:
            value = denoised
    return value
