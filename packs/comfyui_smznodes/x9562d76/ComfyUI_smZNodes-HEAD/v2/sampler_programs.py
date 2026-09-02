"""Pack-owned retained sampler programs for the pinned smZNodes release."""
from __future__ import annotations


async def sample_dpmpp_2m_alt(broker, latent, sigmas):
    """Run smZ's exact DPM++ 2M alternate-history recurrence.

    The host owns model evaluation and previews.  Only the recurrence and its
    one observable difference from DPM++ 2M -- scaling the cached denoised
    history -- live in the pack.
    """
    value = latent
    old_denoised = None
    for step in range(len(sigmas) - 1):
        sigma = sigmas[step]
        denoised, _uncond = await broker.denoise(value, sigma)
        await broker.preview(step, value, sigma, sigma, denoised)
        current_t = sigma.log().neg()
        next_t = sigmas[step + 1].log().neg()
        interval = next_t - current_t
        if old_denoised is None or sigmas[step + 1] == 0:
            value = (
                next_t.neg().exp() / current_t.neg().exp() * value
                - (-interval).expm1() * denoised
            )
        else:
            previous_interval = (
                current_t - sigmas[step - 1].log().neg()
            )
            ratio = previous_interval / interval
            denoised_derivative = (
                (1.0 + 1.0 / (2.0 * ratio)) * denoised
                - (1.0 / (2.0 * ratio)) * old_denoised
            )
            value = (
                next_t.neg().exp() / current_t.neg().exp() * value
                - (-interval).expm1() * denoised_derivative
            )
        sigma_progress = step / len(sigmas)
        adjustment_factor = 1 + (0.15 * (
            sigma_progress * sigma_progress
        ))
        old_denoised = denoised * adjustment_factor
    return value


__all__ = ["sample_dpmpp_2m_alt"]
