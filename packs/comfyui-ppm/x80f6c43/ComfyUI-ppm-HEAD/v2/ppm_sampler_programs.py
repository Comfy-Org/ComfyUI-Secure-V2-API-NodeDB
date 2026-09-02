"""PPM-owned retained sampler loops.

The broker protocol is intentionally tiny: the host owns denoising, noise
sources, and previews; this pack owns the integration loop and tensor math.
All tensor values are expected to remain device-resident for one invocation.
"""
from __future__ import annotations


async def _preview(broker, step, latent, sigma, sigma_hat, denoised):
    callback = getattr(broker, "preview", None)
    if callback is not None:
        await callback(step, latent, sigma, sigma_hat, denoised)


def _to_d(latent, sigma, denoised):
    """Convert a denoiser prediction to the Karras ODE derivative."""
    return (latent - denoised) / sigma


def _ancestral_step(sigma_from, sigma_to, eta):
    """Pack-local scalar/tensor form of k-diffusion's ancestral split."""
    import torch

    if not float(eta):
        return sigma_to, sigma_to.new_zeros(())
    sigma_up = torch.minimum(
        sigma_to,
        float(eta)
        * (
            sigma_to**2
            * (sigma_from**2 - sigma_to**2)
            / sigma_from**2
        ).sqrt(),
    )
    sigma_down = (sigma_to**2 - sigma_up**2).sqrt()
    return sigma_down, sigma_up


async def _denoise(
    broker,
    latent,
    sigma,
    *,
    capture_uncond=False,
    resize_context=None,
):
    """Invoke only the host-owned denoiser, retaining all integration here.

    ``resize_context`` is required by DY/SMEA steps: their temporary latent
    shape must be mirrored by the host-owned latent image, sampler noise, and
    denoise mask for this call and restored atomically afterwards.
    """
    options = {"capture_uncond": bool(capture_uncond)}
    if resize_context is not None:
        options["resize_context"] = str(resize_context)
    return await broker.denoise(latent, sigma, **options)


async def _noise(
    broker,
    latent,
    *,
    kind,
    step,
    sigma_from,
    sigma_to,
    purpose,
    noise_device=None,
    seeded=False,
):
    metadata = {
        "kind": str(kind),
        "step": int(step),
        "sigma_from": sigma_from,
        "sigma_to": sigma_to,
        "purpose": str(purpose),
        "seeded": bool(seeded),
    }
    if noise_device is not None:
        metadata["noise_device"] = str(noise_device)
    return await broker.noise_like(latent, **metadata)


async def sample_euler_gamma(
    broker,
    latent,
    sigmas,
    *,
    cfg_pp=False,
    s_sigma_diff=2.0,
    s_sigma_max=None,
):
    sigma_max = sigmas[0] if s_sigma_max is None else s_sigma_max
    value = latent
    for step in range(len(sigmas) - 1):
        sigma = sigmas[step]
        sigma_hat = sigma
        sigma_epsilon = sigma + float(s_sigma_diff) * (sigma / sigma_max)
        if sigmas[step + 1] > 0 and sigma_epsilon <= sigma_max:
            sigma_hat = sigma_epsilon
            noise = await broker.noise_like(
                value,
                purpose="gamma",
                step=step,
                sigma_from=sigma,
                sigma_to=sigma_hat,
            )
            value = value - noise * (sigma_hat**2 - sigma**2).sqrt()
        denoised, uncond = await broker.denoise(
            value, sigma_hat, capture_uncond=bool(cfg_pp)
        )
        await _preview(broker, step, value, sigma, sigma_hat, denoised)
        if bool(cfg_pp):
            if uncond is None:
                raise RuntimeError("CFG++ sampler did not receive uncond output")
            derivative = (value - uncond) / sigma_hat
            value = denoised + derivative * sigmas[step + 1]
        else:
            derivative = (value - denoised) / sigma_hat
            value = value + derivative * (sigmas[step + 1] - sigma_hat)
    return value


async def sample_dpmpp_2m_gamma(
    broker,
    latent,
    sigmas,
    *,
    cfg_pp=False,
    s_sigma_diff=2.0,
    s_sigma_max=None,
):
    import torch

    sigma_max = sigmas[0] if s_sigma_max is None else s_sigma_max
    value = latent
    old_denoised = None
    last_h = None
    for step in range(len(sigmas) - 1):
        sigma = sigmas[step]
        sigma_hat = sigma
        sigma_epsilon = sigma + float(s_sigma_diff) * (sigma / sigma_max)
        if sigmas[step + 1] > 0 and sigma_epsilon <= sigma_max:
            sigma_hat = sigma_epsilon
            noise = await broker.noise_like(
                value,
                purpose="gamma",
                step=step,
                sigma_from=sigma,
                sigma_to=sigma_hat,
            )
            value = value - noise * (sigma_hat**2 - sigma**2).sqrt()
        denoised, uncond = await broker.denoise(
            value, sigma_hat, capture_uncond=bool(cfg_pp)
        )
        await _preview(broker, step, value, sigma, sigma_hat, denoised)
        current_t = -torch.log(sigma_hat)
        next_t = -torch.log(sigmas[step + 1])
        h = next_t - current_t
        if bool(cfg_pp):
            if uncond is None:
                raise RuntimeError("CFG++ sampler did not receive uncond output")
            if old_denoised is None or sigmas[step + 1] == 0:
                mixture = -torch.exp(-h) * uncond
            else:
                ratio = last_h / h
                mixture = (
                    -torch.exp(-h) * uncond
                    - torch.expm1(-h) * (1.0 / (2.0 * ratio))
                    * (denoised - old_denoised)
                )
            value = denoised + mixture + torch.exp(-h) * value
            old_denoised = uncond
            last_h = h
        else:
            if old_denoised is None or sigmas[step + 1] == 0:
                value = (
                    torch.exp(-next_t) / torch.exp(-current_t) * value
                    - torch.expm1(-h) * denoised
                )
            else:
                previous_h = current_t - (-torch.log(sigmas[step - 1]))
                ratio = previous_h / h
                derivative = (
                    (1.0 + 1.0 / (2.0 * ratio)) * denoised
                    - (1.0 / (2.0 * ratio)) * old_denoised
                )
                value = (
                    torch.exp(-next_t) / torch.exp(-current_t) * value
                    - torch.expm1(-h) * derivative
                )
            old_denoised = denoised
    return value


async def sample_dpmpp_2m_sde_cfg_pp(
    broker,
    latent,
    sigmas,
    *,
    eta=1.0,
    s_noise=1.0,
    solver_type="midpoint",
    noise_device="cpu",
):
    """PPM's CFG++ DPM-Solver++(2M) SDE integration loop."""
    import torch

    if len(sigmas) <= 1:
        return latent
    if str(solver_type) not in {"heun", "midpoint"}:
        raise ValueError("solver_type must be 'heun' or 'midpoint'")
    value = latent
    old_denoised = None
    last_h = None
    for step in range(len(sigmas) - 1):
        sigma = sigmas[step]
        denoised, uncond = await _denoise(
            broker, value, sigma, capture_uncond=True
        )
        if uncond is None:
            raise RuntimeError("CFG++ sampler did not receive uncond output")
        await _preview(broker, step, value, sigma, sigma, denoised)
        if sigmas[step + 1] == 0:
            value = denoised
            continue
        current_t = -torch.log(sigma)
        next_t = -torch.log(sigmas[step + 1])
        h = next_t - current_t
        eta_h = float(eta) * h
        coefficient = -torch.expm1(-h - eta_h)
        value = (
            sigmas[step + 1] / sigma * torch.exp(-eta_h) * value
            + coefficient * uncond
        )
        if old_denoised is not None:
            ratio = last_h / h
            value = value + coefficient * (
                denoised - old_denoised
            ) / (2.0 * ratio)
        if float(eta):
            noise = await _noise(
                broker,
                value,
                kind="brownian",
                step=step,
                sigma_from=sigma,
                sigma_to=sigmas[step + 1],
                purpose="cfgpp-2m-sde",
                noise_device=noise_device,
            )
            value = value + (
                noise
                * sigmas[step + 1]
                * torch.sqrt(-torch.expm1(-2.0 * eta_h))
                * float(s_noise)
            )
        last_h = h
        old_denoised = uncond
    return value


async def sample_dpmpp_3m_sde_cfg_pp(
    broker,
    latent,
    sigmas,
    *,
    eta=1.0,
    s_noise=1.0,
    noise_device="cpu",
):
    """PPM's CFG++ DPM-Solver++(3M) SDE integration loop."""
    import torch

    if len(sigmas) <= 1:
        return latent
    value = latent
    denoised_1 = None
    denoised_2 = None
    h_1 = None
    h_2 = None
    for step in range(len(sigmas) - 1):
        sigma = sigmas[step]
        denoised, uncond = await _denoise(
            broker, value, sigma, capture_uncond=True
        )
        if uncond is None:
            raise RuntimeError("CFG++ sampler did not receive uncond output")
        await _preview(broker, step, value, sigma, sigma, denoised)
        h = None
        if sigmas[step + 1] == 0:
            value = denoised
        else:
            h = -torch.log(sigmas[step + 1]) + torch.log(sigma)
            h_eta = h * (float(eta) + 1.0)
            value = (
                torch.exp(-h_eta) * (value + denoised - uncond)
                - torch.expm1(-h_eta) * denoised
            )
            if h_2 is not None:
                ratio_0 = h_1 / h
                ratio_1 = h_2 / h
                first_0 = (denoised - denoised_1) / ratio_0
                first_1 = (denoised_1 - denoised_2) / ratio_1
                first = first_0 + (
                    first_0 - first_1
                ) * ratio_0 / (ratio_0 + ratio_1)
                second = (first_0 - first_1) / (ratio_0 + ratio_1)
                phi_2 = torch.expm1(-h_eta) / h_eta + 1.0
                phi_3 = phi_2 / h_eta - 0.5
                value = value + phi_2 * first - phi_3 * second
            elif h_1 is not None:
                ratio = h_1 / h
                derivative = (denoised - denoised_1) / ratio
                phi_2 = torch.expm1(-h_eta) / h_eta + 1.0
                value = value + phi_2 * derivative
            if float(eta):
                noise = await _noise(
                    broker,
                    value,
                    kind="brownian",
                    step=step,
                    sigma_from=sigma,
                    sigma_to=sigmas[step + 1],
                    purpose="cfgpp-3m-sde",
                    noise_device=noise_device,
                )
                value = value + (
                    noise
                    * sigmas[step + 1]
                    * torch.sqrt(-torch.expm1(-2.0 * h * float(eta)))
                    * float(s_noise)
                )
        denoised_1, denoised_2 = denoised, denoised_1
        h_1, h_2 = h, h_1
    return value


async def sample_dpmpp_2s_ancestral_cfg_pp(
    broker,
    latent,
    sigmas,
    *,
    eta=1.0,
    s_noise=1.0,
):
    """PPM's CFG++ DPM-Solver++(2S) ancestral loop."""
    import torch

    value = latent
    for step in range(len(sigmas) - 1):
        sigma = sigmas[step]
        denoised, uncond = await _denoise(
            broker, value, sigma, capture_uncond=True
        )
        if uncond is None:
            raise RuntimeError("CFG++ sampler did not receive uncond output")
        sigma_down, sigma_up = _ancestral_step(
            sigma, sigmas[step + 1], eta
        )
        await _preview(broker, step, value, sigma, sigma, denoised)
        if sigma_down == 0:
            value = denoised + _to_d(value, sigma, uncond) * sigma_down
        else:
            current_t = -torch.log(sigma)
            next_t = -torch.log(sigma_down)
            h = next_t - current_t
            midpoint_t = current_t + 0.5 * h
            midpoint_sigma = torch.exp(-midpoint_t)
            shifted = value + denoised - uncond
            midpoint = (
                midpoint_sigma / torch.exp(-current_t) * shifted
                - torch.expm1(-0.5 * h) * denoised
            )
            denoised_midpoint, uncond_midpoint = await _denoise(
                broker, midpoint, midpoint_sigma, capture_uncond=True
            )
            if uncond_midpoint is None:
                raise RuntimeError(
                    "CFG++ midpoint did not receive uncond output"
                )
            value = (
                torch.exp(-next_t) / torch.exp(-current_t)
                * (value + denoised - uncond_midpoint)
                - torch.expm1(-h) * denoised_midpoint
            )
        if sigmas[step + 1] > 0:
            noise = await _noise(
                broker,
                value,
                kind="ancestral",
                step=step,
                sigma_from=sigma,
                sigma_to=sigmas[step + 1],
                purpose="cfgpp-2s-ancestral",
            )
            value = value + noise * float(s_noise) * sigma_up
    return value


async def _dy_sampling_step(
    broker,
    latent,
    dt,
    step,
    sigma,
    sigma_hat,
    *,
    cfg_pp=False,
    sigma_next=None,
):
    """Apply PPM's checkerboard DY substep without exposing model objects."""
    import torch

    original_shape = latent.shape
    batch, channels = original_shape[:2]
    rows, columns = original_shape[2] // 2, original_shape[3] // 2
    extra_row = original_shape[2] % 2 == 1
    extra_column = original_shape[3] % 2 == 1
    row_content = latent[:, :, -1:, :] if extra_row else None
    column_content = latent[:, :, :, -1:] if extra_column else None
    even = latent
    if extra_row:
        even = even[:, :, :-1, :]
    if extra_column:
        even = even[:, :, :, :-1]
    blocks = (
        even.unfold(2, 2, 2)
        .unfold(3, 2, 2)
        .contiguous()
        .view(batch, channels, rows * columns, 2, 2)
    )
    sampled = blocks[:, :, :, 1, 1].view(batch, channels, rows, columns)
    denoised, uncond = await _denoise(
        broker,
        sampled,
        sigma_hat,
        capture_uncond=bool(cfg_pp),
        resize_context="nearest-exact",
    )
    await _preview(broker, step, sampled, sigma, sigma_hat, denoised)
    if bool(cfg_pp):
        if uncond is None or sigma_next is None:
            raise RuntimeError("CFG++ DY substep requires uncond and sigma_next")
        sampled = denoised + _to_d(sampled, sigma_hat, uncond) * sigma_next
    else:
        sampled = sampled + _to_d(sampled, sigma_hat, denoised) * dt
    blocks[:, :, :, 1, 1] = sampled.view(
        batch, channels, rows * columns, 1, 1
    )[:, :, :, 0, 0]
    even = (
        blocks.view(batch, channels, rows, columns, 2, 2)
        .permute(0, 1, 2, 4, 3, 5)
        .reshape(batch, channels, 2 * rows, 2 * columns)
    )
    if not (extra_row or extra_column):
        return even
    expanded = torch.zeros(original_shape, dtype=even.dtype, device=even.device)
    expanded[:, :, : 2 * rows, : 2 * columns] = even
    if extra_row:
        expanded[:, :, -1:, : 2 * columns + 1] = row_content
    if extra_column:
        expanded[:, :, : 2 * rows, -1:] = column_content
    if extra_row and extra_column:
        expanded[:, :, -1:, -1:] = column_content[:, :, -1:, :]
    return expanded


async def _smea_sampling_step(
    broker,
    latent,
    dt,
    step,
    sigma,
    sigma_hat,
    *,
    cfg_pp=False,
    sigma_next=None,
):
    """Apply PPM's temporary 1.25x SMEA substep."""
    import torch.nn.functional as functional

    original_size = latent.shape[-2:]
    enlarged = functional.interpolate(
        latent, scale_factor=(1.25, 1.25), mode="nearest-exact"
    )
    denoised, uncond = await _denoise(
        broker,
        enlarged,
        sigma_hat,
        capture_uncond=bool(cfg_pp),
        resize_context="nearest-exact",
    )
    await _preview(broker, step, enlarged, sigma, sigma_hat, denoised)
    if bool(cfg_pp):
        if uncond is None or sigma_next is None:
            raise RuntimeError("CFG++ SMEA substep requires uncond and sigma_next")
        enlarged = denoised + _to_d(enlarged, sigma_hat, uncond) * sigma_next
    else:
        enlarged = enlarged + _to_d(enlarged, sigma_hat, denoised) * dt
    return functional.interpolate(
        enlarged, size=original_size, mode="nearest-exact"
    )


def _dynamic_gamma(step, sigmas, s_churn, s_tmin, s_tmax, s_dy_pow):
    sigma = sigmas[step]
    gamma = (
        max(float(s_churn) / (len(sigmas) - 1), 2**0.5 - 1)
        if float(s_tmin) <= sigma <= float(s_tmax)
        else 0.0
    )
    if int(s_dy_pow) >= 0:
        gamma *= 1.0 - (step / (len(sigmas) - 2)) ** int(s_dy_pow)
    return gamma


async def sample_euler_dy(
    broker,
    latent,
    sigmas,
    *,
    s_churn=0.0,
    s_tmin=0.0,
    s_tmax=float("inf"),
    s_noise=1.0,
    s_dy_pow=-1,
    s_extra_steps=True,
):
    value = latent
    for step in range(len(sigmas) - 1):
        sigma = sigmas[step]
        gamma = _dynamic_gamma(
            step, sigmas, s_churn, s_tmin, s_tmax, s_dy_pow
        )
        sigma_hat = sigma * (gamma + 1.0)
        dt = sigmas[step + 1] - sigma_hat
        if gamma > 0.0:
            noise = await _noise(
                broker,
                value,
                kind="independent",
                step=step,
                sigma_from=sigma,
                sigma_to=sigma_hat,
                purpose="dynamic-churn",
            )
            value = value - noise * float(s_noise) * (
                sigma_hat**2 - sigma**2
            ).sqrt()
        denoised, _ = await _denoise(broker, value, sigma_hat)
        await _preview(broker, step, value, sigma, sigma_hat, denoised)
        value = value + _to_d(value, sigma_hat, denoised) * dt
        # This deliberately preserves PPM's published trigger (steps 2 and 3),
        # rather than silently inventing a different cadence for existing graphs.
        if sigmas[step + 1] > 0 and bool(s_extra_steps) and step // 2 == 1:
            value = await _dy_sampling_step(
                broker, value, dt, step, sigma, sigma_hat
            )
    return value


async def sample_euler_smea_dy(
    broker,
    latent,
    sigmas,
    *,
    s_churn=0.0,
    s_tmin=0.0,
    s_tmax=float("inf"),
    s_noise=1.0,
    s_dy_pow=-1,
    s_extra_steps=True,
):
    value = latent
    for step in range(len(sigmas) - 1):
        sigma = sigmas[step]
        gamma = _dynamic_gamma(
            step, sigmas, s_churn, s_tmin, s_tmax, s_dy_pow
        )
        sigma_hat = sigma * (gamma + 1.0)
        dt = sigmas[step + 1] - sigma_hat
        if gamma > 0.0:
            noise = await _noise(
                broker,
                value,
                kind="independent",
                step=step,
                sigma_from=sigma,
                sigma_to=sigma_hat,
                purpose="dynamic-churn",
            )
            value = value - noise * float(s_noise) * (
                sigma_hat**2 - sigma**2
            ).sqrt()
        denoised, _ = await _denoise(broker, value, sigma_hat)
        await _preview(broker, step, value, sigma, sigma_hat, denoised)
        value = value + _to_d(value, sigma_hat, denoised) * dt
        if sigmas[step + 1] > 0 and bool(s_extra_steps):
            # Python precedence makes the two upstream expressions select
            # SMEA at step 0 and DY at step 1; preserve that observable intent.
            if step + 1 // 2 == 1:
                value = await _dy_sampling_step(
                    broker, value, dt, step, sigma, sigma_hat
                )
            if step + 1 // 2 == 0:
                value = await _smea_sampling_step(
                    broker, value, dt, step, sigma, sigma_hat
                )
    return value


async def sample_euler_ancestral_dy(
    broker,
    latent,
    sigmas,
    *,
    eta=1.0,
    s_noise=1.0,
    s_dy_pow=-1,
):
    value = latent
    for step in range(len(sigmas) - 1):
        sigma = sigmas[step]
        gamma = 2**0.5 - 1
        if int(s_dy_pow) >= 0:
            gamma *= 1.0 - (
                step / (len(sigmas) - 2)
            ) ** int(s_dy_pow)
        sigma_hat = sigma * (gamma + 1.0)
        if gamma > 0.0:
            noise = await _noise(
                broker,
                value,
                kind="independent",
                step=step,
                sigma_from=sigma,
                sigma_to=sigma_hat,
                purpose="dynamic-churn",
            )
            value = value - noise * float(s_noise) * (
                sigma_hat**2 - sigma**2
            ).sqrt()
        denoised, _ = await _denoise(broker, value, sigma_hat)
        sigma_down, sigma_up = _ancestral_step(
            sigma_hat, sigmas[step + 1], eta
        )
        await _preview(broker, step, value, sigma, sigma_hat, denoised)
        value = value + _to_d(value, sigma_hat, denoised) * (
            sigma_down - sigma_hat
        )
        if sigmas[step + 1] > 0:
            noise = await _noise(
                broker,
                value,
                kind="ancestral",
                step=step,
                sigma_from=sigma_hat,
                sigma_to=sigmas[step + 1] * (gamma + 1.0),
                purpose="dynamic-ancestral",
            )
            value = value + noise * float(s_noise) * sigma_up
    return value


async def sample_dpmpp_2m_dy(
    broker,
    latent,
    sigmas,
    *,
    s_noise=1.0,
    s_dy_pow=-1,
):
    import torch

    value = latent
    old_denoised = None
    last_h = None
    for step in range(len(sigmas) - 1):
        sigma = sigmas[step]
        gamma = 2**0.5 - 1
        if int(s_dy_pow) >= 0:
            gamma *= 1.0 - (
                step / (len(sigmas) - 2)
            ) ** int(s_dy_pow)
        sigma_hat = sigma * (gamma + 1.0)
        if gamma > 0.0:
            noise = await _noise(
                broker,
                value,
                kind="independent",
                step=step,
                sigma_from=sigma,
                sigma_to=sigma_hat,
                purpose="dynamic-churn",
            )
            value = value - noise * float(s_noise) * (
                sigma_hat**2 - sigma**2
            ).sqrt()
        denoised, _ = await _denoise(broker, value, sigma_hat)
        await _preview(broker, step, value, sigma, sigma_hat, denoised)
        current_t = -torch.log(sigma_hat)
        next_t = -torch.log(sigmas[step + 1])
        h = next_t - current_t
        if old_denoised is None or sigmas[step + 1] == 0:
            value = (
                torch.exp(-next_t) / torch.exp(-current_t) * value
                - torch.expm1(-h) * denoised
            )
        else:
            ratio = last_h / h
            derivative = (
                (1.0 + 1.0 / (2.0 * ratio)) * denoised
                - (1.0 / (2.0 * ratio)) * old_denoised
            )
            value = (
                torch.exp(-next_t) / torch.exp(-current_t) * value
                - torch.expm1(-h) * derivative
            )
        old_denoised = denoised
        last_h = h
    return value


async def sample_dpmpp_3m_dy(
    broker,
    latent,
    sigmas,
    *,
    s_noise=1.0,
    s_dy_pow=-1,
):
    """PPM's deterministic dynamic DPM-Solver++(3M) loop."""
    import torch

    if len(sigmas) <= 1:
        return latent
    value = latent
    denoised_1 = None
    denoised_2 = None
    h_1 = None
    h_2 = None
    gamma = 2**0.5 - 1
    for step in range(len(sigmas) - 1):
        sigma = sigmas[step]
        if int(s_dy_pow) >= 0:
            gamma *= 1.0 - (
                step / (len(sigmas) - 2)
            ) ** int(s_dy_pow)
        sigma_hat = sigma * (gamma + 1.0)
        if gamma > 0.0:
            noise = await _noise(
                broker,
                value,
                kind="independent",
                step=step,
                sigma_from=sigma,
                sigma_to=sigma_hat,
                purpose="dynamic-churn",
            )
            value = value - noise * float(s_noise) * (
                sigma_hat**2 - sigma**2
            ).sqrt()
        denoised, _ = await _denoise(broker, value, sigma_hat)
        await _preview(broker, step, value, sigma, sigma_hat, denoised)
        h = None
        if sigmas[step + 1] == 0:
            value = denoised
        else:
            h = -torch.log(sigmas[step + 1]) + torch.log(sigma_hat)
            value = torch.exp(-h) * value - torch.expm1(-h) * denoised
            if h_2 is not None:
                ratio_0 = h_1 / h
                ratio_1 = h_2 / h
                first_0 = (denoised - denoised_1) / ratio_0
                first_1 = (denoised_1 - denoised_2) / ratio_1
                first = first_0 + (
                    first_0 - first_1
                ) * ratio_0 / (ratio_0 + ratio_1)
                second = (first_0 - first_1) / (ratio_0 + ratio_1)
                phi_2 = torch.expm1(-h) / h + 1.0
                phi_3 = phi_2 / h - 0.5
                value = value + phi_2 * first - phi_3 * second
            elif h_1 is not None:
                ratio = h_1 / h
                derivative = (denoised - denoised_1) / ratio
                phi_2 = torch.expm1(-h) / h + 1.0
                value = value + phi_2 * derivative
        denoised_1, denoised_2 = denoised, denoised_1
        h_1, h_2 = h, h_1
    return value


async def sample_kohaku_lonyu_yog(
    broker,
    latent,
    sigmas,
    *,
    s_churn=0.0,
    s_tmin=0.0,
    s_tmax=float("inf"),
    s_noise=1.0,
    eta=1.0,
):
    value = latent
    for step in range(len(sigmas) - 1):
        sigma = sigmas[step]
        gamma = (
            min(float(s_churn) / (len(sigmas) - 1), 2**0.5 - 1)
            if float(s_tmin) <= sigma <= float(s_tmax)
            else 0.0
        )
        sigma_hat = sigma * (gamma + 1.0)
        churn_noise = await _noise(
            broker,
            value,
            kind="independent",
            step=step,
            sigma_from=sigma,
            sigma_to=sigma_hat,
            purpose="kohaku-churn",
        )
        if gamma > 0.0:
            value = value + churn_noise * float(s_noise) * (
                sigma_hat**2 - sigma**2
            ).sqrt()
        denoised, _ = await _denoise(broker, value, sigma_hat)
        derivative = _to_d(value, sigma_hat, denoised)
        sigma_down, sigma_up = _ancestral_step(
            sigma, sigmas[step + 1], eta
        )
        await _preview(broker, step, value, sigma, sigma_hat, denoised)
        dt = sigma_down - sigma
        if step <= (len(sigmas) - 1) / 2:
            negated = -value
            denoised_negative, _ = await _denoise(
                broker, negated, sigma_hat
            )
            derivative_negative = _to_d(
                negated, sigma_hat, denoised_negative
            )
            midpoint = value + (
                (derivative + derivative_negative) / 2.0
            ) * dt
            denoised_midpoint, _ = await _denoise(
                broker, midpoint, sigma_hat
            )
            derivative_midpoint = _to_d(
                midpoint, sigma_hat, denoised_midpoint
            )
            value = value + (
                derivative + derivative_midpoint
            ) / 2.0 * dt
            noise = await _noise(
                broker,
                value,
                kind="ancestral",
                step=step,
                sigma_from=sigma,
                sigma_to=sigmas[step + 1],
                purpose="kohaku-ancestral",
            )
            value = value + noise * float(s_noise) * sigma_up
        else:
            value = value + derivative * dt
    return value


def _gamma_step_bounds(sigmas, start, end):
    start = round(float(start)) if float(start) > 1.0 else (
        len(sigmas) - 1
    ) * float(start)
    end = round(float(end)) if float(end) > 1.0 else (
        len(sigmas) - 1
    ) * float(end)
    return start, end


async def sample_euler_dy_cfg_pp(
    broker,
    latent,
    sigmas,
    *,
    s_churn=0.0,
    s_tmin=0.0,
    s_tmax=float("inf"),
    s_noise=1.0,
    s_gamma_start=0.0,
    s_gamma_end=0.0,
    s_extra_steps=True,
):
    value = latent
    gamma_start, gamma_end = _gamma_step_bounds(
        sigmas, s_gamma_start, s_gamma_end
    )
    for step in range(len(sigmas) - 1):
        sigma = sigmas[step]
        gamma = (
            max(float(s_churn) / (len(sigmas) - 1), 2**0.5 - 1)
            if (
                gamma_start <= step < gamma_end
                and float(s_tmin) <= sigma <= float(s_tmax)
            )
            else 0.0
        )
        sigma_hat = sigma * (gamma + 1.0)
        if gamma > 0.0:
            noise = await _noise(
                broker,
                value,
                kind="independent",
                step=step,
                sigma_from=sigma,
                sigma_to=sigma_hat,
                purpose="cfgpp-dynamic-churn",
            )
            value = value - noise * float(s_noise) * (
                sigma_hat**2 - sigma**2
            ).sqrt()
        denoised, uncond = await _denoise(
            broker, value, sigma_hat, capture_uncond=True
        )
        if uncond is None:
            raise RuntimeError("CFG++ sampler did not receive uncond output")
        await _preview(broker, step, value, sigma, sigma_hat, denoised)
        value = denoised + _to_d(value, sigma_hat, uncond) * sigmas[
            step + 1
        ]
        if sigmas[step + 1] > 0 and bool(s_extra_steps) and step // 2 == 1:
            value = await _dy_sampling_step(
                broker,
                value,
                sigmas[step + 1] - sigma_hat,
                step,
                sigma,
                sigma_hat,
                cfg_pp=True,
                sigma_next=sigmas[step + 1],
            )
    return value


async def sample_euler_smea_dy_cfg_pp(
    broker,
    latent,
    sigmas,
    *,
    s_churn=0.0,
    s_tmin=0.0,
    s_tmax=float("inf"),
    s_noise=1.0,
    s_gamma_start=0.0,
    s_gamma_end=0.0,
    s_extra_steps=True,
):
    value = latent
    gamma_start, gamma_end = _gamma_step_bounds(
        sigmas, s_gamma_start, s_gamma_end
    )
    for step in range(len(sigmas) - 1):
        sigma = sigmas[step]
        gamma = (
            max(float(s_churn) / (len(sigmas) - 1), 2**0.5 - 1)
            if (
                gamma_start <= step < gamma_end
                and float(s_tmin) <= sigma <= float(s_tmax)
            )
            else 0.0
        )
        sigma_hat = sigma * (gamma + 1.0)
        if gamma > 0.0:
            noise = await _noise(
                broker,
                value,
                kind="independent",
                step=step,
                sigma_from=sigma,
                sigma_to=sigma_hat,
                purpose="cfgpp-dynamic-churn",
            )
            value = value - noise * float(s_noise) * (
                sigma_hat**2 - sigma**2
            ).sqrt()
        denoised, uncond = await _denoise(
            broker, value, sigma_hat, capture_uncond=True
        )
        if uncond is None:
            raise RuntimeError("CFG++ sampler did not receive uncond output")
        await _preview(broker, step, value, sigma, sigma_hat, denoised)
        value = denoised + _to_d(value, sigma_hat, uncond) * sigmas[
            step + 1
        ]
        if sigmas[step + 1] > 0 and bool(s_extra_steps):
            if step + 1 // 2 == 1:
                value = await _dy_sampling_step(
                    broker,
                    value,
                    sigmas[step + 1] - sigma_hat,
                    step,
                    sigma,
                    sigma_hat,
                    cfg_pp=True,
                    sigma_next=sigmas[step + 1],
                )
            if step + 1 // 2 == 0:
                value = await _smea_sampling_step(
                    broker,
                    value,
                    sigmas[step + 1] - sigma_hat,
                    step,
                    sigma,
                    sigma_hat,
                    cfg_pp=True,
                    sigma_next=sigmas[step + 1],
                )
    return value


async def sample_euler_ancestral_dy_cfg_pp(
    broker,
    latent,
    sigmas,
    *,
    eta=1.0,
    s_noise=1.0,
    s_gamma_start=0.0,
    s_gamma_end=0.0,
):
    value = latent
    gamma_start, gamma_end = _gamma_step_bounds(
        sigmas, s_gamma_start, s_gamma_end
    )
    for step in range(len(sigmas) - 1):
        sigma = sigmas[step]
        gamma = 2**0.5 - 1 if gamma_start <= step < gamma_end else 0.0
        sigma_hat = sigma * (gamma + 1.0)
        if gamma > 0.0:
            noise = await _noise(
                broker,
                value,
                kind="independent",
                step=step,
                sigma_from=sigma,
                sigma_to=sigma_hat,
                purpose="cfgpp-dynamic-churn",
            )
            value = value - noise * float(s_noise) * (
                sigma_hat**2 - sigma**2
            ).sqrt()
        denoised, uncond = await _denoise(
            broker, value, sigma_hat, capture_uncond=True
        )
        if uncond is None:
            raise RuntimeError("CFG++ sampler did not receive uncond output")
        sigma_down, sigma_up = _ancestral_step(
            sigma, sigmas[step + 1], eta
        )
        await _preview(broker, step, value, sigma, sigma_hat, denoised)
        value = denoised + _to_d(value, sigma_hat, uncond) * sigma_down
        if sigmas[step + 1] > 0:
            noise = await _noise(
                broker,
                value,
                kind="ancestral",
                step=step,
                sigma_from=sigma,
                sigma_to=sigmas[step + 1],
                purpose="cfgpp-dynamic-ancestral",
            )
            value = value + noise * float(s_noise) * sigma_up
    return value


async def sample_dpmpp_2m_dy_cfg_pp(
    broker,
    latent,
    sigmas,
    *,
    s_noise=1.0,
    s_gamma_start=0.0,
    s_gamma_end=0.0,
):
    import torch

    value = latent
    old_uncond = None
    last_h = None
    gamma_start, gamma_end = _gamma_step_bounds(
        sigmas, s_gamma_start, s_gamma_end
    )
    for step in range(len(sigmas) - 1):
        sigma = sigmas[step]
        gamma = 2**0.5 - 1 if gamma_start <= step < gamma_end else 0.0
        sigma_hat = sigma * (gamma + 1.0)
        if gamma > 0.0:
            noise = await _noise(
                broker,
                value,
                kind="independent",
                step=step,
                sigma_from=sigma,
                sigma_to=sigma_hat,
                purpose="cfgpp-dynamic-churn",
            )
            value = value - noise * float(s_noise) * (
                sigma_hat**2 - sigma**2
            ).sqrt()
        denoised, uncond = await _denoise(
            broker, value, sigma_hat, capture_uncond=True
        )
        if uncond is None:
            raise RuntimeError("CFG++ sampler did not receive uncond output")
        await _preview(broker, step, value, sigma, sigma_hat, denoised)
        current_t = -torch.log(sigma_hat)
        next_t = -torch.log(sigmas[step + 1])
        h = next_t - current_t
        if old_uncond is None or sigmas[step + 1] == 0:
            mixture = -torch.exp(-h) * uncond
        else:
            ratio = last_h / h
            mixture = (
                -torch.exp(-h) * uncond
                - torch.expm1(-h) * (1.0 / (2.0 * ratio))
                * (denoised - old_uncond)
            )
        value = denoised + mixture + torch.exp(-h) * value
        old_uncond = uncond
        last_h = h
    return value


async def _sampling_schedule_info(broker, schedule):
    if schedule is None:
        schedule = await broker.schedule_parameters(percent_offset=1e-4)
    if not isinstance(schedule, dict):
        raise TypeError("sampling schedule parameters must be a mapping")
    kind = str(schedule.get("parameterization"))
    if kind not in {"sigma", "const"}:
        raise ValueError("unknown sampling schedule parameterization")
    noise_scale = float(schedule.get("noise_scale", 1.0))
    first_sigma = schedule.get("first_sigma")
    first_sigma = None if first_sigma is None else float(first_sigma)
    return {
        "parameterization": kind,
        "noise_scale": noise_scale,
        "first_sigma": first_sigma,
    }


def _offset_first_sigma(sigmas, schedule):
    if (
        schedule["parameterization"] == "const"
        and sigmas[0] >= 1
        and schedule["first_sigma"] is not None
    ):
        sigmas = sigmas.clone()
        sigmas[0] = schedule["first_sigma"]
    return sigmas


def _sigma_to_half_log_snr(sigma, schedule):
    if schedule["parameterization"] == "const":
        return -sigma.logit()
    return -sigma.log()


def _half_log_snr_to_sigma(value, schedule):
    if schedule["parameterization"] == "const":
        return (-value).sigmoid()
    return (-value).exp()


def _phi_1(value):
    return value.expm1()


def _phi_2(value):
    return (value.expm1() - value) / value


def _tau_at(sigma, start_sigma, end_sigma, eta):
    if float(eta) <= 0.0:
        return 0.0
    value = float(sigma)
    return (
        float(eta)
        if float(start_sigma) >= value >= float(end_sigma)
        else 0.0
    )


async def sample_seeds_2_scheduled(
    broker,
    latent,
    sigmas,
    *,
    eta=1.0,
    s_noise=1.0,
    r=0.5,
    solver_type="phi_1",
    sde_start_sigma,
    sde_end_sigma,
    schedule=None,
):
    """SEEDS-2 stays pack-side; the broker only projects model schedule data."""
    import torch

    if str(solver_type) not in {"phi_1", "phi_2"}:
        raise ValueError("solver_type must be 'phi_1' or 'phi_2'")
    schedule = await _sampling_schedule_info(broker, schedule)
    sigmas = _offset_first_sigma(sigmas, schedule)
    noise_strength = float(s_noise) * schedule["noise_scale"]
    value = latent
    stage_fraction = float(r)
    final_mix = 1.0 / (2.0 * stage_fraction)
    for step in range(len(sigmas) - 1):
        sigma = sigmas[step]
        denoised, _ = await _denoise(broker, value, sigma)
        await _preview(broker, step, value, sigma, sigma, denoised)
        if sigmas[step + 1] == 0:
            value = denoised
            continue
        tau = _tau_at(
            sigmas[step + 1], sde_start_sigma, sde_end_sigma, eta
        )
        inject_noise = tau > 0.0 and noise_strength > 0.0
        lambda_start = _sigma_to_half_log_snr(sigma, schedule)
        lambda_end = _sigma_to_half_log_snr(sigmas[step + 1], schedule)
        h = lambda_end - lambda_start
        h_eta = h * (tau + 1.0)
        lambda_stage = torch.lerp(
            lambda_start, lambda_end, stage_fraction
        )
        sigma_stage = _half_log_snr_to_sigma(lambda_stage, schedule)
        alpha_stage = sigma_stage * lambda_stage.exp()
        alpha_end = sigmas[step + 1] * lambda_end.exp()
        stage_value = (
            sigma_stage / sigma * torch.exp(-stage_fraction * h * tau)
            * value
            - alpha_stage * _phi_1(-stage_fraction * h_eta) * denoised
        )
        accumulated_noise = None
        if inject_noise:
            segment_noise = await _noise(
                broker,
                value,
                kind="independent",
                step=step,
                sigma_from=sigma,
                sigma_to=sigma_stage,
                purpose="seeds-stage-1",
                seeded=True,
            )
            accumulated_noise = (
                torch.sqrt(-torch.expm1(-2.0 * stage_fraction * h * tau))
                * segment_noise
            )
            stage_value = (
                stage_value
                + accumulated_noise * sigma_stage * noise_strength
            )
        denoised_stage, _ = await _denoise(
            broker, stage_value, sigma_stage
        )
        if str(solver_type) == "phi_1":
            denoised_mix = torch.lerp(
                denoised, denoised_stage, final_mix
            )
            value = (
                sigmas[step + 1] / sigma * torch.exp(-h * tau) * value
                - alpha_end * _phi_1(-h_eta) * denoised_mix
            )
        else:
            b2 = _phi_2(-h_eta) / stage_fraction
            b1 = _phi_1(-h_eta) - b2
            value = (
                sigmas[step + 1] / sigma * torch.exp(-h * tau) * value
                - alpha_end * (b1 * denoised + b2 * denoised_stage)
            )
        if inject_noise:
            segment_factor = (stage_fraction - 1.0) * h * tau
            accumulated_noise = accumulated_noise * segment_factor.exp()
            final_noise = await _noise(
                broker,
                value,
                kind="independent",
                step=step,
                sigma_from=sigma_stage,
                sigma_to=sigmas[step + 1],
                purpose="seeds-stage-2",
                seeded=True,
            )
            accumulated_noise = accumulated_noise + torch.sqrt(
                -torch.expm1(2.0 * segment_factor)
            ) * final_noise
            value = (
                value
                + accumulated_noise * sigmas[step + 1] * noise_strength
            )
    return value


def _er_noise_scale(value, mode, eta):
    if str(mode) == "er_sde":
        return value * (torch_exp(value**0.3) + 10.0)
    if str(mode) == "reverse_sde":
        return value ** (float(eta) + 1.0)
    if str(mode) == "ode":
        return value
    raise ValueError("unknown ER-SDE noise scale mode")


def torch_exp(value):
    # Kept as a small helper so ER-SDE's formula remains independently
    # testable without importing torch at pack import time.
    return value.exp()


async def sample_er_sde_scheduled(
    broker,
    latent,
    sigmas,
    *,
    solver_type="ER-SDE",
    max_stage=3,
    eta=1.0,
    s_noise=1.0,
    sde_start_sigma,
    sde_end_sigma,
    schedule=None,
):
    """Extended reverse-time SDE integration with pack-owned stages."""
    import torch

    schedule = await _sampling_schedule_info(broker, schedule)
    sigmas = _offset_first_sigma(sigmas, schedule)
    noise_strength = float(s_noise) * schedule["noise_scale"]
    label = str(solver_type)
    if label == "ODE" or (label == "Reverse-time SDE" and float(eta) == 0.0):
        eta = 0.0
        noise_strength = 0.0
        scale_mode = "ode"
    elif label == "ER-SDE":
        scale_mode = "er_sde"
    elif label == "Reverse-time SDE":
        scale_mode = "reverse_sde"
    else:
        raise ValueError("unknown ER-SDE solver type")
    value = latent
    points = torch.arange(
        0, 200, dtype=torch.float32, device=value.device
    )
    half_log_snrs = _sigma_to_half_log_snr(sigmas, schedule)
    er_lambdas = torch.exp(-half_log_snrs)
    old_denoised = None
    old_derivative = None
    for step in range(len(sigmas) - 1):
        sigma = sigmas[step]
        denoised, _ = await _denoise(broker, value, sigma)
        await _preview(broker, step, value, sigma, sigma, denoised)
        stage_used = min(int(max_stage), step + 1)
        if sigmas[step + 1] == 0:
            value = denoised
            old_denoised = denoised
            continue
        tau = _tau_at(
            sigmas[step + 1], sde_start_sigma, sde_end_sigma, eta
        )
        inject_noise = tau > 0.0 and noise_strength > 0.0
        active_mode = scale_mode if inject_noise else "ode"
        lambda_start = er_lambdas[step]
        lambda_end = er_lambdas[step + 1]
        alpha_start = sigma / lambda_start
        alpha_end = sigmas[step + 1] / lambda_end
        alpha_ratio = alpha_end / alpha_start
        scale_ratio = _er_noise_scale(
            lambda_end, active_mode, eta
        ) / _er_noise_scale(lambda_start, active_mode, eta)
        value = (
            alpha_ratio * scale_ratio * value
            + alpha_end * (1.0 - scale_ratio) * denoised
        )
        if stage_used >= 2:
            delta = lambda_end - lambda_start
            integration_step = -delta / 200.0
            positions = lambda_end + points * integration_step
            scaled_positions = _er_noise_scale(
                positions, active_mode, eta
            )
            integral = torch.sum(1.0 / scaled_positions) * integration_step
            derivative = (denoised - old_denoised) / (
                lambda_start - er_lambdas[step - 1]
            )
            value = value + alpha_end * (
                delta
                + integral
                * _er_noise_scale(lambda_end, active_mode, eta)
            ) * derivative
            if stage_used >= 3:
                weighted = torch.sum(
                    (positions - lambda_start) / scaled_positions
                ) * integration_step
                second = (derivative - old_derivative) / (
                    (lambda_start - er_lambdas[step - 2]) / 2.0
                )
                value = value + alpha_end * (
                    delta**2 / 2.0
                    + weighted
                    * _er_noise_scale(lambda_end, active_mode, eta)
                ) * second
            old_derivative = derivative
        if noise_strength > 0.0:
            noise = await _noise(
                broker,
                value,
                kind="independent",
                step=step,
                sigma_from=sigma,
                sigma_to=sigmas[step + 1],
                purpose="er-sde",
                seeded=True,
            )
            variance = torch.sqrt(
                lambda_end**2 - lambda_start**2 * scale_ratio**2
            ).nan_to_num(nan=0.0)
            value = value + alpha_end * noise * noise_strength * variance
        old_denoised = denoised
    return value


PROGRAMS = {
    "euler_gamma": sample_euler_gamma,
    "dpmpp_2m_gamma": sample_dpmpp_2m_gamma,
    "euler_dy": sample_euler_dy,
    "euler_smea_dy": sample_euler_smea_dy,
    "euler_ancestral_dy": sample_euler_ancestral_dy,
    "dpmpp_2m_dy": sample_dpmpp_2m_dy,
    "dpmpp_3m_dy": sample_dpmpp_3m_dy,
    "Kohaku_LoNyu_Yog": sample_kohaku_lonyu_yog,
    "euler_dy_cfg_pp": sample_euler_dy_cfg_pp,
    "euler_smea_dy_cfg_pp": sample_euler_smea_dy_cfg_pp,
    "euler_ancestral_dy_cfg_pp": sample_euler_ancestral_dy_cfg_pp,
    "dpmpp_2m_dy_cfg_pp": sample_dpmpp_2m_dy_cfg_pp,
    "dpmpp_2m_sde_cfg_pp": sample_dpmpp_2m_sde_cfg_pp,
    "dpmpp_2m_sde_gpu_cfg_pp": sample_dpmpp_2m_sde_cfg_pp,
    "dpmpp_3m_sde_cfg_pp": sample_dpmpp_3m_sde_cfg_pp,
    "dpmpp_3m_sde_gpu_cfg_pp": sample_dpmpp_3m_sde_cfg_pp,
    "dpmpp_2s_ancestral_cfg_pp": sample_dpmpp_2s_ancestral_cfg_pp,
    "seeds_2_scheduled": sample_seeds_2_scheduled,
    "er_sde_scheduled": sample_er_sde_scheduled,
}


__all__ = [
    "PROGRAMS",
    "sample_dpmpp_2m_sde_cfg_pp",
    "sample_dpmpp_2s_ancestral_cfg_pp",
    "sample_dpmpp_3m_sde_cfg_pp",
    "sample_dpmpp_2m_dy",
    "sample_dpmpp_2m_dy_cfg_pp",
    "sample_dpmpp_2m_gamma",
    "sample_dpmpp_3m_dy",
    "sample_euler_ancestral_dy",
    "sample_euler_ancestral_dy_cfg_pp",
    "sample_euler_dy",
    "sample_euler_dy_cfg_pp",
    "sample_euler_gamma",
    "sample_euler_smea_dy",
    "sample_euler_smea_dy_cfg_pp",
    "sample_er_sde_scheduled",
    "sample_kohaku_lonyu_yog",
    "sample_seeds_2_scheduled",
]
