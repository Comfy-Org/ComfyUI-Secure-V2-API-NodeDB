"""Native spectral samplers over the existing invocation-owned broker.

Integration math follows pinned ComfyUI comfy/k_diffusion/sampling.py (GPL-3.0).
Spectral adjustment follows the original pack's MIT-licensed helper.
"""
import torch
from comfy_api.latest import sdk
from .zsampler_tensor_math import _adjust_spectral_distribution


def get_ancestral_step(sigma_from, sigma_to, eta=1.):
    if not eta:
        return sigma_to, 0.
    sigma_up = min(sigma_to, eta * (sigma_to ** 2 * (sigma_from ** 2 - sigma_to ** 2) / sigma_from ** 2) ** 0.5)
    sigma_down = (sigma_to ** 2 - sigma_up ** 2) ** 0.5
    return sigma_down, sigma_up


def spectral_noise(noise_shape, sigma, alpha_tilting, alpha_sharpness, sigma_range):
    # The native wrapper supplies torch.randn_like rather than the base
    # sampler's default/Brownian noise callback. Keep that exact choice and
    # RNG stream in this same guest that generated the stage's initial noise.
    sigma_f = float(sigma.mean().detach().cpu())
    if isinstance(alpha_tilting, (list, tuple)) and len(alpha_tilting) == 2:
        start_sigma, end_sigma = sigma_range
        range = end_sigma - start_sigma
        progress = max(0.0, min(1.0, (sigma_f - start_sigma) / range)) if range != 0 else 1.0
        alpha = alpha_tilting[0] + (progress**alpha_sharpness) * (alpha_tilting[1] - alpha_tilting[0])
    else:
        alpha = float(alpha_tilting)
    noise = torch.randn_like(noise_shape)
    return _adjust_spectral_distribution(noise, alpha=alpha, force_zero_mean=False)


async def integrate_euler(broker, x, sigmas, *, alpha_tilting, alpha_sharpness, sigma_range, eta, s_noise):
    schedule = await broker.schedule_parameters()
    const = schedule['parameterization'] == 'const'
    noise_shape = x
    if const:
        s_noise = s_noise * schedule['noise_scale']
    for i in range(len(sigmas) - 1):
        denoised, _ = await broker.denoise(x, sigmas[i])
        if const:
            await broker.preview(i, x, sigmas[i], sigmas[i], denoised)
            if sigmas[i + 1] == 0:
                x = denoised
            else:
                downstep_ratio = 1 + (sigmas[i + 1] / sigmas[i] - 1) * eta
                sigma_down = sigmas[i + 1] * downstep_ratio
                alpha_ip1 = 1 - sigmas[i + 1]
                alpha_down = 1 - sigma_down
                renoise_coeff = (sigmas[i + 1]**2 - sigma_down**2 * alpha_ip1**2 / alpha_down**2)**0.5
                sigma_down_i_ratio = sigma_down / sigmas[i]
                x = sigma_down_i_ratio * x + (1 - sigma_down_i_ratio) * denoised
                if eta > 0:
                    noise = spectral_noise(noise_shape, sigmas[i], alpha_tilting, alpha_sharpness, sigma_range)
                    x = (alpha_ip1 / alpha_down) * x + noise * s_noise * renoise_coeff
        else:
            sigma_down, sigma_up = get_ancestral_step(sigmas[i], sigmas[i + 1], eta=eta)
            await broker.preview(i, x, sigmas[i], sigmas[i], denoised)
            if sigma_down == 0:
                x = denoised
            else:
                d = (x - denoised) / sigmas[i]
                dt = sigma_down - sigmas[i]
                noise = spectral_noise(noise_shape, sigmas[i], alpha_tilting, alpha_sharpness, sigma_range)
                x = x + d * dt + noise * s_noise * sigma_up
    return x


async def integrate_dpmpp(broker, x, sigmas, *, alpha_tilting, alpha_sharpness, sigma_range, eta, s_noise, r):
    if len(sigmas) <= 1:
        return x
    schedule = await broker.schedule_parameters()
    const = schedule['parameterization'] == 'const'
    noise_shape = x
    def sigma_fn(value):
        return value.neg().sigmoid() if const else value.neg().exp()
    def lambda_fn(value):
        return value.logit().neg() if const else value.log().neg()
    if const and sigmas[0] >= 1:
        sigmas = sigmas.clone()
        sigmas[0] = schedule['first_sigma']
    s_noise = s_noise * schedule['noise_scale']
    for i in range(len(sigmas) - 1):
        denoised, _ = await broker.denoise(x, sigmas[i])
        await broker.preview(i, x, sigmas[i], sigmas[i], denoised)
        if sigmas[i + 1] == 0:
            x = denoised
        else:
            lambda_s, lambda_t = lambda_fn(sigmas[i]), lambda_fn(sigmas[i + 1])
            h = lambda_t - lambda_s
            lambda_s_1 = lambda_s + r * h
            fac = 1 / (2 * r)
            sigma_s_1 = sigma_fn(lambda_s_1)
            alpha_s = sigmas[i] * lambda_s.exp()
            alpha_s_1 = sigma_s_1 * lambda_s_1.exp()
            alpha_t = sigmas[i + 1] * lambda_t.exp()
            sd, su = get_ancestral_step(lambda_s.neg().exp(), lambda_s_1.neg().exp(), eta)
            lambda_s_1_ = sd.log().neg()
            h_ = lambda_s_1_ - lambda_s
            x_2 = (alpha_s_1 / alpha_s) * (-h_).exp() * x - alpha_s_1 * (-h_).expm1() * denoised
            if eta > 0 and s_noise > 0:
                noise = spectral_noise(noise_shape, sigmas[i], alpha_tilting, alpha_sharpness, sigma_range)
                x_2 = x_2 + alpha_s_1 * noise * s_noise * su
            denoised_2, _ = await broker.denoise(x_2, sigma_s_1)
            sd, su = get_ancestral_step(lambda_s.neg().exp(), lambda_t.neg().exp(), eta)
            lambda_t_ = sd.log().neg()
            h_ = lambda_t_ - lambda_s
            denoised_d = (1 - fac) * denoised + fac * denoised_2
            x = (alpha_t / alpha_s) * (-h_).exp() * x - alpha_t * (-h_).expm1() * denoised_d
            if eta > 0 and s_noise > 0:
                noise = spectral_noise(noise_shape, sigmas[i], alpha_tilting, alpha_sharpness, sigma_range)
                x = x + alpha_t * noise * s_noise * su
    return x


async def EulerAss(alpha_tilting=(.1, -1.), alpha_sharpness=1., sigma_range=(.9999, 0.), *, eta=None, s_noise=None):
    async def loop(broker, x, sigmas):
        with torch.no_grad():
            return await integrate_euler(broker, x, sigmas, alpha_tilting=alpha_tilting,
                alpha_sharpness=alpha_sharpness, sigma_range=sigma_range,
                eta=1. if eta is None else eta, s_noise=1. if s_noise is None else s_noise)
    closure = await sdk.ctx().closures.retain('custom_sampler', loop)
    return await closure.as_sampler()


async def DPMPP_SDEss(alpha_tilting=(.1, -1.), alpha_sharpness=1., sigma_range=(.9999, 0.), *, eta=None, s_noise=None, r=None, noise_device='cpu'):
    # The native wrapper installs its independent noise callback for both
    # dpmpp_sde and dpmpp_sde_gpu; the underlying integration body is identical.
    del noise_device
    async def loop(broker, x, sigmas):
        with torch.no_grad():
            return await integrate_dpmpp(broker, x, sigmas, alpha_tilting=alpha_tilting,
                alpha_sharpness=alpha_sharpness, sigma_range=sigma_range,
                eta=1. if eta is None else eta, s_noise=1. if s_noise is None else s_noise,
                r=.5 if r is None else r)
    closure = await sdk.ctx().closures.retain('custom_sampler', loop)
    return await closure.as_sampler()
