"""Secure Nodes V2 implementations for the pinned ComfyUI-ppm release.

The numerical image/mask algorithms stay in this pack.  Live model objects and
weights remain host-owned behind typed refs.  Retained transforms and sampler
programs keep pack-specific math in this sandbox; unsupported model-family
branches and the remaining NegPiP algorithm fail closed until their narrower
retained phases land.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any

from comfy_api.latest import sdk

from ._secure_runtime import SCHEMAS, bind_node
from . import ppm_attention_programs, ppm_programs, ppm_sampler_programs


MAX_RESOLUTION = 16384
MIN_RATIO = 0.15
MAX_RATIO = 1.0 / MIN_RATIO


def _pending_for(node_id: str):
    async def pending(**_kwargs: Any):
        raise RuntimeError(
            f"{node_id} is pending the bounded Secure Nodes V2 "
            "execution-lifetime tensor-program API; its valid algorithm is "
            "not transplanted into core and does not run unsandboxed"
        )

    pending.__name__ = f"pending_{re.sub(r'\W+', '_', node_id).strip('_')}"
    return pending


async def model_attention_selector(model, attention: str):
    mode = str(attention)
    if mode == "optimized":
        return (model,)
    if mode not in {"pytorch", "sub_quad", "split"}:
        raise ValueError(f"unsupported registered attention {mode!r}")
    return (await model.patch("attention_impl", mode=mode),)


async def clip_attention_selector(clip, attention: str):
    return (await clip.with_attention_impl(str(attention)),)


async def clip_text_encode_break(clip, text: str):
    result = None
    for chunk in str(text).split("BREAK"):
        tokens = await clip.tokenize(chunk.strip())
        conditioning = await clip.encode_from_tokens_scheduled(tokens)
        result = conditioning if result is None else await result.concat(conditioning)
    return (result,)


async def clip_micro_conditioning(
    cond,
    width: int,
    height: int,
    crop_w: int,
    crop_h: int,
    target_width: int,
    target_height: int,
):
    return (
        await cond.with_metadata(
            width=int(width),
            height=int(height),
            crop_w=int(crop_w),
            crop_h=int(crop_h),
            target_width=int(target_width),
            target_height=int(target_height),
        ),
    )


async def _described_prompt_tokens(clip, text: str):
    # The source discovers every tokenizer component before examining prompt
    # chunks.  A bounded empty tokenization supplies the same component census
    # without exposing tokenizer objects or vocabularies to the guest.
    baseline = await clip.describe_tokens(await clip.tokenize(""))
    tokens_map: dict[str, list[list[tuple[int, str]]]] = {
        key: [] for key in baseline
    }
    for prompt in _parse_prompts(text):
        if not prompt:
            continue
        tokens = await clip.tokenize(prompt)
        described = await clip.describe_tokens(tokens)
        for key in tokens_map:
            chunks = described.get(key)
            if not chunks:
                continue
            # Upstream intentionally counts only the first tokenizer chunk for
            # each BREAK-separated prompt.
            tokens_map[key].append([
                (int(entry["id"]), str(entry["text"]))
                for entry in chunks[0]
                if not bool(entry["special"])
            ])
    return tokens_map


async def clip_token_counter(clip, text: str):
    tokens_map = await _described_prompt_tokens(clip, str(text))
    count_map = {
        key: [len(prompt_tokens) for prompt_tokens in prompts]
        for key, prompts in tokens_map.items()
    }
    formatted_tokens = {
        key: [
            [f"`{token_text}` ({token_id})`" for token_id, token_text in prompt]
            for prompt in prompts
        ]
        for key, prompts in tokens_map.items()
    }
    return (
        _format_count(count_map),
        json.dumps(count_map, indent=2),
        json.dumps(formatted_tokens, indent=2),
    )


async def conditioning_zero_out_combine(conditioning, zero_out_end: float):
    split = float(zero_out_end)
    zero = await conditioning.zero_out()
    zero = await zero.with_timestep_range(0.0, split)
    original = await conditioning.with_timestep_range(split, 1.0)
    return (await original.combine(zero),)


async def clip_text_encode_invert_weights(
    clip, text: str, invert_special_tokens: bool
):
    result = None
    for chunk in str(text).split("BREAK"):
        tokens = await clip.tokenize(chunk.strip())
        described = await clip.describe_tokens(tokens)
        inverted: dict[str, list[list[tuple[int, float]]]] = {}
        for component, sections in tokens.items():
            component_descriptions = described.get(component)
            if component_descriptions is None or len(component_descriptions) != len(sections):
                raise RuntimeError(
                    f"CLIP descriptions do not match component {component!r}"
                )
            inverted[component] = []
            for section, section_descriptions in zip(
                sections, component_descriptions, strict=True
            ):
                if len(section) != len(section_descriptions):
                    raise RuntimeError(
                        f"CLIP descriptions do not match {component!r} section"
                    )
                output_section = []
                for token, description in zip(
                    section, section_descriptions, strict=True
                ):
                    if not isinstance(token, (tuple, list)) or len(token) < 2:
                        raise TypeError("CLIP token-weight entry is invalid")
                    token_id, weight = int(token[0]), float(token[1])
                    keep = bool(description["special"]) and not bool(
                        invert_special_tokens
                    )
                    output_section.append((token_id, weight if keep else -weight))
                inverted[component].append(output_section)
        conditioning = await clip.encode_from_tokens_scheduled(inverted)
        result = conditioning if result is None else await result.concat(conditioning)
    return (result,)


async def dynamic_thresholding_simple_post(
    model, mimic_scale: float, threshold_percentile: float
):
    return (
        await model.patch(
            "dynamic_thresholding",
            mimic_scale=float(mimic_scale),
            threshold_percentile=float(threshold_percentile),
            mimic_mode="Constant",
            mimic_scale_min=0.0,
            cfg_mode="Constant",
            cfg_scale_min=0.0,
            schedule_value=1.0,
            separate_feature_channels=False,
            scaling_startpoint="MEAN",
            variability_measure="AD",
            interpolate_phi=1.0,
        ),
    )


async def dynamic_thresholding_post(
    model,
    mimic_scale: float,
    threshold_percentile: float,
    separate_feature_channels: bool,
    scaling_startpoint: str,
    variability_measure: str,
    interpolate_phi: float,
):
    return (
        await model.patch(
            "dynamic_thresholding",
            mimic_scale=float(mimic_scale),
            threshold_percentile=float(threshold_percentile),
            mimic_mode="Constant",
            mimic_scale_min=0.0,
            cfg_mode="Constant",
            cfg_scale_min=0.0,
            schedule_value=1.0,
            separate_feature_channels=bool(separate_feature_channels),
            scaling_startpoint=str(scaling_startpoint),
            variability_measure=str(variability_measure),
            interpolate_phi=float(interpolate_phi),
        ),
    )


def _calc_dimensions(resolution: int, ratio: float, step: int) -> tuple[int, int]:
    target_res = int(resolution) * int(resolution)
    height_exact = math.sqrt(target_res / float(ratio))
    height_floor = int((height_exact // int(step)) * int(step))
    height = min(
        (height_floor, height_floor + int(step)),
        key=lambda value: abs(height_exact - value),
    )
    width_exact = height * float(ratio)
    width_floor = int((width_exact // int(step)) * int(step))
    width = min(
        (width_floor, width_floor + int(step)),
        key=lambda value: abs(target_res - value * height),
    )
    return (
        min(max(width, 16), MAX_RESOLUTION),
        min(max(height, 16), MAX_RESOLUTION),
    )


async def empty_latent_image_ar(
    resolution: int, ratio: float, step: int, batch_size: int = 1
):
    width, height = _calc_dimensions(resolution, ratio, step)
    return (await sdk.LatentRef.empty(width, height, int(batch_size), channels=4),)


async def latent_to_width_height(latent):
    height, width = await latent.spatial_shape()
    height *= 8
    width *= 8
    if height > MAX_RESOLUTION or width > MAX_RESOLUTION:
        raise ValueError(
            f"{height} and/or {width} are greater than {MAX_RESOLUTION}"
        )
    return width, height


async def latent_to_mask_bb(
    latent,
    x: float,
    y: float,
    w: float,
    h: float,
    value: float = 1.0,
    outer_value: float = 0.0,
):
    import torch

    x_end = float(x) + float(w)
    y_end = float(y) + float(h)
    if x_end > 1.0 or y_end > 1.0:
        raise ValueError("x + w and y + h must be less than 1.0")
    latent_height, latent_width = await latent.spatial_shape()
    height, width = latent_height * 8, latent_width * 8
    x_coord, x_end_coord = round(float(x) * width), round(x_end * width)
    y_coord, y_end_coord = round(float(y) * height), round(y_end * height)
    mask = torch.full((height, width), float(outer_value), dtype=torch.float32)
    mask[y_coord:y_end_coord, x_coord:x_end_coord] = float(value)
    return (await sdk.MaskRef._from_raw(mask.unsqueeze(0)),)


def _mask_number(name: str) -> tuple[int, str]:
    match = re.fullmatch(r"mask_(\d+)", name)
    return (int(match.group(1)), name) if match else (1 << 30, name)


def _composite_mask(destination, source, operation: str):
    import torch

    output = destination.reshape(
        (-1, destination.shape[-2], destination.shape[-1])
    ).clone()
    source = source.reshape((-1, source.shape[-2], source.shape[-1]))
    right = min(source.shape[-1], destination.shape[-1])
    bottom = min(source.shape[-2], destination.shape[-2])
    source_portion = source[:, :bottom, :right]
    destination_portion = output[:, :bottom, :right]
    if operation == "multiply":
        value = destination_portion * source_portion
    elif operation == "add":
        value = destination_portion + source_portion
    elif operation == "subtract":
        value = destination_portion - source_portion
    elif operation == "and":
        value = torch.bitwise_and(
            destination_portion.round().bool(), source_portion.round().bool()
        ).float()
    elif operation == "or":
        value = torch.bitwise_or(
            destination_portion.round().bool(), source_portion.round().bool()
        ).float()
    elif operation == "xor":
        value = torch.bitwise_xor(
            destination_portion.round().bool(), source_portion.round().bool()
        ).float()
    else:
        raise ValueError(f"unknown mask operation {operation!r}")
    output[:, :bottom, :right] = value
    return torch.clamp(output, 0.0, 1.0)


async def mask_composite_ppm(operation: str, **kwargs: Any):
    masks = [
        kwargs[name]
        for name in sorted(
            (key for key in kwargs if key.startswith("mask_")), key=_mask_number
        )
        if kwargs[name] is not None
    ]
    if not masks:
        raise ValueError("MaskCompositePPM requires at least mask_1")
    output = await masks[0].raw()
    for mask in masks[1:]:
        output = _composite_mask(output, await mask.raw(), str(operation))
    return (await sdk.MaskRef._from_raw(output),)


def _interpolate(value, *, scale_factor=None, size=None, mode: str):
    import torch.nn.functional as functional

    return functional.interpolate(
        value, scale_factor=scale_factor, size=size, mode=mode
    )


def _pyramid_up(value, mode: str):
    import torch
    import torch.nn.functional as functional

    kernel = value.new_tensor(
        [
            [1.0, 4.0, 6.0, 4.0, 1.0],
            [4.0, 16.0, 24.0, 16.0, 4.0],
            [6.0, 24.0, 36.0, 24.0, 6.0],
            [4.0, 16.0, 24.0, 16.0, 4.0],
            [1.0, 4.0, 6.0, 4.0, 1.0],
        ]
    ) / 256.0
    upscaled = _interpolate(value, scale_factor=2.0, mode=mode)
    channels = int(upscaled.shape[1])
    weights = kernel.reshape(1, 1, 5, 5).repeat(channels, 1, 1, 1)
    padded = functional.pad(upscaled, (2, 2, 2, 2), mode="reflect")
    return functional.conv2d(padded, weights, groups=channels)


async def tile_preprocessor_ppm(
    image,
    blur_iters: int,
    downscale_method: str,
    upscale_method: str,
    rescale_to_input: bool,
):
    value = await image.raw()
    samples = value.movedim(-1, 1)
    original_height, original_width = samples.shape[-2:]
    samples = _interpolate(
        samples,
        scale_factor=1.0 / (2 ** int(blur_iters)),
        mode=str(downscale_method),
    )
    for _ in range(int(blur_iters)):
        samples = _pyramid_up(samples, str(upscale_method))
    if bool(rescale_to_input):
        samples = _interpolate(
            samples,
            size=(original_height, original_width),
            mode="nearest-exact",
        )
    return (await sdk.ImageRef._from_raw(samples.movedim(1, -1)),)


async def convert_timestep_to_sigma(model, mode: dict[str, Any]):
    selected = str(mode.get("mode"))
    if selected == "percent":
        return (
            await model.sigma_for_percent(
                float(mode["percent"]),
                actual_endpoints=bool(mode["return_actual_sigma"]),
            ),
        )
    if selected == "schedule_step":
        sigmas = mode["schedule_sigmas"]
        return (await sigmas.value_at(int(mode["schedule_step"])),)
    raise ValueError(f"unknown timestep conversion mode {selected!r}")


async def sampler_gradient_estimation(sampler_name: str, gamma: float):
    return (
        await sdk.SamplerRef.named(
            str(sampler_name), ge_gamma=float(gamma)
        ),
    )


async def guidance_limiter(
    model, sigma_start: float, sigma_end: float,
):
    start = float(sigma_start)
    end = float(sigma_end)

    def post_cfg(guided, cond, uncond, latent, sigma, cfg):
        del uncond, latent, cfg
        return ppm_programs.guidance_limiter_post(
            guided, cond, sigma, start, end)

    closure = await sdk.ctx().closures.retain("post_cfg", post_cfg)
    return (await closure.attach_model(model),)


async def cfg_limiter_guider(
    model,
    positive,
    negative,
    cfg: float,
    sigma_start: float,
    sigma_end: float,
):
    start = float(sigma_start)
    end = float(sigma_end)
    return (
        await model.scheduled_cfg_guider(
            positive,
            negative,
            float(cfg),
            bounds={
                "unit": "sigma",
                "start": None if start < 0.0 else start,
                "end": None if end < 0.0 else end,
            },
        ),
    )


async def rescale_cfg_post(
    model,
    multiplier: float,
    alt_mode: bool,
    sigma_start: float,
    sigma_end: float,
):
    factor = float(multiplier)
    alternative = bool(alt_mode)
    start = float(sigma_start)
    end = float(sigma_end)

    def post_cfg(guided, cond, uncond, latent, sigma, cfg):
        del uncond, latent, cfg
        return ppm_programs.rescale_cfg_post(
            guided, cond, sigma, factor, alternative, start, end)

    closure = await sdk.ctx().closures.retain("post_cfg", post_cfg)
    return (await closure.attach_model(model),)


async def renorm_cfg_post(
    model, renorm_cfg: float, sigma_start: float, sigma_end: float,
):
    factor = float(renorm_cfg)
    start = float(sigma_start)
    end = float(sigma_end)

    def post_cfg(guided, cond, uncond, latent, sigma, cfg):
        del uncond, latent, cfg
        return ppm_programs.renorm_cfg_post(
            guided, cond, sigma, factor, start, end)

    closure = await sdk.ctx().closures.retain("post_cfg", post_cfg)
    return (await closure.attach_model(model),)


async def tcfg_advanced(
    model, multiplier: float, sigma_start: float, sigma_end: float,
):
    factor = float(multiplier)
    start = float(sigma_start)
    end = float(sigma_end)

    def pre_cfg(latent, predictions, presence, sigma):
        return ppm_programs.tangential_cfg_pre(
            latent, predictions, presence, sigma, factor, start, end)

    closure = await sdk.ctx().closures.retain("pre_cfg", pre_cfg)
    return (await closure.attach_model(model),)


async def skip_first_step_cfg(model, skip_percent: float):
    threshold = await model.sigma_for_percent(float(skip_percent))

    def select_conditioning(presence, sigma):
        return ppm_programs.skip_first_step_presence(
            presence, sigma, threshold)

    closure = await sdk.ctx().closures.retain(
        "conditioning_selection", select_conditioning)
    return (await closure.attach_model(model),)


async def cads_ppm(
    model,
    scale: float,
    start_percent: float,
    end_percent: float,
):
    sigma_start = await model.sigma_for_percent(float(start_percent))
    sigma_end = await model.sigma_for_percent(float(end_percent))
    amount = float(scale)

    def preprocess(tensors, noises, sigma):
        return ppm_programs.cads_preprocess_tensors(
            tensors,
            noises,
            sigma,
            sigma_start,
            sigma_end,
            amount,
            1.0,
        )

    closure = await sdk.ctx().closures.retain(
        "conditioning_preprocess", preprocess)
    return (await closure.attach_model(model),)


async def freeu2_ppm(
    model,
    input_block: bool,
    middle_block: bool,
    output_block: bool,
    slice_b1: int,
    slice_b2: int,
    b1: float,
    b2: float,
    s1: float,
    s2: float,
    start_percent: float,
    end_percent: float,
    threshold: int = 1,
):
    sigma_start = await model.sigma_for_percent(float(start_percent))
    sigma_end = await model.sigma_for_percent(float(end_percent))
    common = (
        sigma_start,
        sigma_end,
        int(slice_b1),
        int(slice_b2),
        float(b1),
        float(b2),
    )
    current = model

    if bool(input_block):
        def input_program(hidden, sigmas, block_index):
            del block_index
            return ppm_programs.freeu_block(hidden, sigmas, *common)

        closure = await sdk.ctx().closures.retain(
            "model_input_block", input_program)
        current = await closure.attach_model(current)

    if bool(middle_block):
        def middle_program(hidden, sigmas, block_index):
            del block_index
            return ppm_programs.freeu_block(hidden, sigmas, *common)

        closure = await sdk.ctx().closures.retain(
            "model_middle_block", middle_program)
        current = await closure.attach_model(current)

    if bool(output_block):
        def output_program(hidden, skip, sigmas, block_index):
            del block_index
            return ppm_programs.freeu_output_block(
                hidden,
                skip,
                sigmas,
                *common,
                float(s1),
                float(s2),
                int(threshold),
            )

        closure = await sdk.ctx().closures.retain(
            "model_output_block", output_program)
        current = await closure.attach_model(current)

    return (current,)


async def latent_operation_tonemap_luminance(
    tonemapper: str, multiplier: float,
):
    mode = str(tonemapper)
    factor = float(multiplier)

    def operation(latent):
        return ppm_programs.latent_tonemap_luminance(
            latent, mode, factor)

    closure = await sdk.ctx().closures.retain(
        "latent_operation", operation)
    return (await closure.as_latent_operation(),)


async def epsilon_scaling_ppm(model, scaling_factor: float):
    factor = float(scaling_factor)
    zero_terminal_snr = await model.is_zero_terminal_snr()
    sigma_max = (
        await model.sigma_for_percent(0.0, actual_endpoints=True)
        if zero_terminal_snr
        else None
    )

    def post_cfg(guided, cond, uncond, latent, sigma, cfg):
        del cond, uncond, cfg
        return ppm_programs.epsilon_scaling_post(
            guided,
            latent,
            sigma,
            factor,
            zsnr=zero_terminal_snr,
            sigma_max=sigma_max,
        )

    closure = await sdk.ctx().closures.retain("post_cfg", post_cfg)
    return (await closure.attach_model(model),)


async def _retained_sampler(program_name: str, options: dict[str, Any]):
    try:
        implementation = ppm_sampler_programs.PROGRAMS[program_name]
    except KeyError as error:
        raise ValueError(
            f"unknown retained PPM sampler {program_name!r}"
        ) from error

    # Only pack-plane scalars are captured.  The invocation broker, latent,
    # sigma schedule, model calls, RNGs, and previews remain host-owned and are
    # supplied for one bounded sampling invocation.
    async def program(broker, latent, sigmas):
        return await implementation(broker, latent, sigmas, **options)

    closure = await sdk.ctx().closures.retain("custom_sampler", program)
    return (await closure.as_sampler(),)


_CFGPP_CORE_SAMPLERS = {
    "euler_cfg_pp",
    "dpmpp_2m_cfg_pp",
    "gradient_estimation_cfg_pp",
    "euler_ancestral_cfg_pp",
}
_CFGPP_SDE_SAMPLERS = {
    "dpmpp_2m_sde_cfg_pp",
    "dpmpp_2m_sde_gpu_cfg_pp",
    "dpmpp_3m_sde_cfg_pp",
    "dpmpp_3m_sde_gpu_cfg_pp",
    "dpmpp_2s_ancestral_cfg_pp",
}
_CFGPP_DYNAMIC_SAMPLERS = {
    "euler_dy_cfg_pp",
    "euler_smea_dy_cfg_pp",
    "dpmpp_2m_dy_cfg_pp",
    "euler_ancestral_dy_cfg_pp",
}
_DYNAMIC_SAMPLERS = {
    "euler_dy",
    "euler_smea_dy",
    "euler_ancestral_dy",
    "dpmpp_2m_dy",
    "dpmpp_3m_dy",
    "Kohaku_LoNyu_Yog",
}
_PPM_GAMMA_SAMPLERS = {"euler_gamma", "dpmpp_2m_gamma"}


async def cfgpp_sampler_select(
    sampler_name: str,
    eta: float,
    s_gamma_start: float,
    s_gamma_end: float,
    s_extra_steps: bool,
):
    name = str(sampler_name)
    if name in _CFGPP_CORE_SAMPLERS:
        return (
            await sdk.SamplerRef.named(
                name,
                eta=float(eta) if name == "euler_ancestral_cfg_pp" else None,
            ),
        )
    options: dict[str, Any] = {}
    if name in _CFGPP_SDE_SAMPLERS:
        options["eta"] = float(eta)
        if "_gpu_" in name:
            # Upstream's GPU variants mean "generate Brownian noise on the
            # latent device".  The bounded broker names that closed choice
            # ``latent`` rather than exposing an ambient accelerator string.
            options["noise_device"] = "latent"
    elif name in _CFGPP_DYNAMIC_SAMPLERS:
        options["s_gamma_start"] = float(s_gamma_start)
        options["s_gamma_end"] = float(s_gamma_end)
        if name in {"euler_dy_cfg_pp", "euler_smea_dy_cfg_pp"}:
            options["s_extra_steps"] = bool(s_extra_steps)
        if name == "euler_ancestral_dy_cfg_pp":
            options["eta"] = float(eta)
    else:
        raise ValueError(f"unknown CFG++ sampler {name!r}")
    return await _retained_sampler(name, options)


async def dyn_sampler_select(
    sampler_name: str,
    eta: float,
    s_dy_pow: int,
    s_extra_steps: bool,
):
    name = str(sampler_name)
    if name not in _DYNAMIC_SAMPLERS:
        raise ValueError(f"unknown dynamic sampler {name!r}")
    options: dict[str, Any] = {}
    if name in {"euler_dy", "euler_smea_dy"}:
        options.update(
            s_dy_pow=int(s_dy_pow),
            s_extra_steps=bool(s_extra_steps),
        )
    elif name == "euler_ancestral_dy":
        options.update(eta=float(eta), s_dy_pow=int(s_dy_pow))
    elif name in {"dpmpp_2m_dy", "dpmpp_3m_dy"}:
        options["s_dy_pow"] = int(s_dy_pow)
    else:
        # The source selector passes DY controls through **kwargs, but Kohaku's
        # implementation consumes only eta.  Do not pretend its inert widgets
        # affect the retained loop.
        options["eta"] = float(eta)
    return await _retained_sampler(name, options)


async def ppm_sampler_select(
    sampler_name: str,
    model,
    cfg_pp: bool,
    s_sigma_diff: float,
):
    name = str(sampler_name)
    if name not in _PPM_GAMMA_SAMPLERS:
        raise ValueError(f"unknown PPM gamma sampler {name!r}")
    sigma_max = await model.sigma_for_percent(
        0.0, actual_endpoints=True
    )
    return await _retained_sampler(
        name,
        {
            "cfg_pp": bool(cfg_pp),
            "s_sigma_diff": float(s_sigma_diff),
            "s_sigma_max": float(sigma_max),
        },
    )


async def sampler_seeds_2_scheduled(
    model,
    solver_type: str,
    eta: float,
    sde_start_percent: float,
    sde_end_percent: float,
    s_noise: float,
    r: float,
):
    start_sigma = await model.sigma_for_percent(float(sde_start_percent))
    end_sigma = await model.sigma_for_percent(float(sde_end_percent))
    return await _retained_sampler(
        "seeds_2_scheduled",
        {
            "solver_type": str(solver_type),
            "eta": float(eta),
            "s_noise": float(s_noise),
            "r": float(r),
            "sde_start_sigma": float(start_sigma),
            "sde_end_sigma": float(end_sigma),
        },
    )


async def sampler_er_sde_scheduled(
    model,
    solver_type: str,
    max_stage: int,
    eta: float,
    sde_start_percent: float,
    sde_end_percent: float,
    s_noise: float,
):
    start_sigma = await model.sigma_for_percent(float(sde_start_percent))
    end_sigma = await model.sigma_for_percent(float(sde_end_percent))
    return await _retained_sampler(
        "er_sde_scheduled",
        {
            "solver_type": str(solver_type),
            "max_stage": int(max_stage),
            "eta": float(eta),
            "s_noise": float(s_noise),
            "sde_start_sigma": float(start_sigma),
            "sde_end_sigma": float(end_sigma),
        },
    )


def _parse_prompts(text: str) -> list[str]:
    text = re.sub(r"STYLE\(.*?\)", "", text)
    text = re.sub(r"\[(.*?)(\:.*?)+\]", r"\g<1>", text)
    return text.split("BREAK")


def _format_count(count_map: dict[str, list[int]]) -> str:
    if not count_map:
        return "0"
    grouped: dict[str, list[str]] = {}
    for key, count in count_map.items():
        grouped.setdefault(str(count), []).append(key)
    if len(grouped) == 1:
        simple = next(iter(grouped)).removeprefix("[").removesuffix("]")
        return simple or "0"
    return json.dumps(count_map, indent=2)


async def attention_couple_ppm(model, base_cond, base_mask, **kwargs):
    """Attach PPM's retained regional-attention program.

    Dynamic frontend inputs are required to be contiguous pairs.  The refs are
    declared to the closure rather than captured by Python, so the host can
    resolve and retain them before this node dispatch ends.
    """
    dynamic = {}
    for name, value in kwargs.items():
        match = re.fullmatch(r"(?:cond|mask)_(\d+)", str(name))
        if match is None:
            raise ValueError(
                f"AttentionCouplePPM does not accept dynamic input {name!r}")
        dynamic[str(name)] = value
    indexes = sorted({
        int(re.fullmatch(r"(?:cond|mask)_(\d+)", name).group(1))
        for name in dynamic
    })
    if indexes and indexes != list(range(1, indexes[-1] + 1)):
        raise ValueError("AttentionCouplePPM inputs must be contiguous pairs")
    conditionings = []
    masks = [base_mask]
    for index in indexes:
        cond_name = f"cond_{index}"
        mask_name = f"mask_{index}"
        if cond_name not in dynamic or mask_name not in dynamic:
            raise ValueError(
                f"AttentionCouplePPM needs both {cond_name} and {mask_name}")
        conditionings.append(dynamic[cond_name])
        masks.append(dynamic[mask_name])
    if len(masks) > 32:
        raise ValueError("AttentionCouplePPM accepts at most 32 regions")

    program = ppm_attention_programs.make_regional_attention_program()
    closure = await sdk.ctx().closures.retain(
        "regional_attention",
        program,
        captures={
            "base_conditioning": base_cond,
            "conditionings": conditionings,
            "masks": masks,
        },
    )
    return (await closure.attach_model(model),)


async def clip_negpip(model, clip):
    """Attach PPM's future prompt-weight program as one atomic pair."""
    closure = await sdk.ctx().closures.retain(
        "clip_token_weight_encoder",
        ppm_attention_programs.make_negpip_program(),
    )
    return await closure.attach_model_clip(model, clip)


# Start from fail-closed handlers so any still-pending attention algorithms
# remain registered and mechanically visible in the ledger.
_HANDLERS: dict[str, Any] = {
    node_id: _pending_for(node_id) for node_id in SCHEMAS
}
_HANDLERS.update(
    {
        "ModelAttentionSelector": model_attention_selector,
        "AttentionCouplePPM": attention_couple_ppm,
        "CLIPNegPip": clip_negpip,
        "CLIPAttentionSelector": clip_attention_selector,
        "CLIPTextEncodeBREAK": clip_text_encode_break,
        "CLIPMicroConditioning": clip_micro_conditioning,
        "CLIPTokenCounter": clip_token_counter,
        "ConditioningZeroOutCombine": conditioning_zero_out_combine,
        "CLIPTextEncodeInvertWeights": clip_text_encode_invert_weights,
        "DynamicThresholdingSimplePost": dynamic_thresholding_simple_post,
        "DynamicThresholdingPost": dynamic_thresholding_post,
        "EmptyLatentImageAR": empty_latent_image_ar,
        "LatentToWidthHeight": latent_to_width_height,
        "LatentToMaskBB": latent_to_mask_bb,
        "MaskCompositePPM": mask_composite_ppm,
        "TilePreprocessorPPM": tile_preprocessor_ppm,
        "ConvertTimestepToSigma": convert_timestep_to_sigma,
        "SamplerGradientEstimation": sampler_gradient_estimation,
        "Guidance Limiter": guidance_limiter,
        "CFGLimiterGuider": cfg_limiter_guider,
        "RescaleCFGPost": rescale_cfg_post,
        "RenormCFGPost": renorm_cfg_post,
        "TCFGAdvanced": tcfg_advanced,
        "SkipFirstStepCFG": skip_first_step_cfg,
        "CADSPPM": cads_ppm,
        "FreeU2PPM": freeu2_ppm,
        "LatentOperationTonemapLuminance": (
            latent_operation_tonemap_luminance),
        "EpsilonScalingPPM": epsilon_scaling_ppm,
        "CFGPPSamplerSelect": cfgpp_sampler_select,
        "DynSamplerSelect": dyn_sampler_select,
        "PPMSamplerSelect": ppm_sampler_select,
        "SamplerSEEDS2Scheduled": sampler_seeds_2_scheduled,
        "SamplerER_SDEScheduled": sampler_er_sde_scheduled,
    }
)

_RAW_NODES = {"LatentToMaskBB", "MaskCompositePPM", "TilePreprocessorPPM"}
_CLOSURE_NODES = {
    "AttentionCouplePPM", "CLIPNegPip",
    "Guidance Limiter", "RescaleCFGPost", "RenormCFGPost", "TCFGAdvanced",
    "SkipFirstStepCFG",
    "CADSPPM",
    "FreeU2PPM",
    "LatentOperationTonemapLuminance",
    "EpsilonScalingPPM",
    "CFGPPSamplerSelect", "DynSamplerSelect", "PPMSamplerSelect",
    "SamplerSEEDS2Scheduled", "SamplerER_SDEScheduled",
}


def _permissions_for(node_id: str) -> tuple[str, ...]:
    if node_id in _RAW_NODES:
        return ("raw",)
    if node_id in _CLOSURE_NODES:
        return ("closures",)
    return ()

NODE_CLASS_MAPPINGS = {
    node_id: bind_node(
        node_id,
        _HANDLERS[node_id],
        permissions=_permissions_for(node_id),
        always_changed=node_id in _CLOSURE_NODES,
    )
    for node_id in SCHEMAS
}
NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: entry["schema"]["attrs"].get("display_name") or node_id
    for node_id, entry in SCHEMAS.items()
}


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
