"""Secure Nodes V2 implementation of TripleKSampler.

The pack still owns its alignment, stage selection, boundary search and sigma
shift refinement algorithms.  Host-owned model patching and diffusion use the
small ModelRef and sampling surfaces.  The optional WanVideo variants compose
the converted ``WanVideoSampler`` node declaratively; no WanVideo sampler code
is imported into this pack or the Secure Nodes core.
"""
from __future__ import annotations

import math
import re
from typing import Any, Awaitable, Callable

from comfy_api.latest import io, sdk


DEFAULT_BASE_QUALITY_THRESHOLD = 20
DEFAULT_BOUNDARY_T2V = 0.875
DEFAULT_BOUNDARY_I2V = 0.900
STAGE3_SEED_OFFSET = 1
SEARCH_INTERVAL = 0.01

SIMPLE_STRATEGIES = (
    "50% of steps",
    "T2V boundary",
    "I2V boundary",
    "T2V boundary (refined)",
    "I2V boundary (refined)",
)
ADVANCED_STRATEGIES = (
    "50% of steps",
    "Manual switch step",
    "T2V boundary",
    "I2V boundary",
    "Manual boundary",
    "T2V boundary (refined)",
    "I2V boundary (refined)",
    "Manual boundary (refined)",
)
SAMPLER_NAMES = (
    "euler", "euler_cfg_pp", "euler_ancestral",
    "euler_ancestral_cfg_pp", "heun", "heunpp2", "exp_heun_2_x0",
    "exp_heun_2_x0_sde", "dpm_2", "dpm_2_ancestral", "lms",
    "dpm_fast", "dpm_adaptive", "dpmpp_2s_ancestral",
    "dpmpp_2s_ancestral_cfg_pp", "dpmpp_sde", "dpmpp_sde_gpu",
    "dpmpp_2m", "dpmpp_2m_cfg_pp", "dpmpp_2m_sde",
    "dpmpp_2m_sde_gpu", "dpmpp_2m_sde_heun",
    "dpmpp_2m_sde_heun_gpu", "dpmpp_3m_sde", "dpmpp_3m_sde_gpu",
    "ddpm", "lcm", "ipndm", "ipndm_v", "deis", "res_multistep",
    "res_multistep_cfg_pp", "res_multistep_ancestral",
    "res_multistep_ancestral_cfg_pp", "gradient_estimation",
    "gradient_estimation_cfg_pp", "er_sde", "seeds_2", "seeds_3",
    "sa_solver", "sa_solver_pece", "ddim", "uni_pc", "uni_pc_bh2",
)
SCHEDULER_NAMES = (
    "simple", "sgm_uniform", "karras", "exponential", "ddim_uniform",
    "beta", "normal", "linear_quadratic", "kl_optimal",
)
WANVIDEO_SCHEDULERS = (
    "unipc", "unipc/beta", "dpm++", "dpm++/beta", "dpm++_sde",
    "dpm++_sde/beta", "euler", "euler/beta", "longcat_distill_euler",
    "deis", "lcm", "lcm/beta", "res_multistep", "flowmatch_causvid",
    "flowmatch_distill", "flowmatch_pusa", "multitalk",
    "sa_ode_stable", "rcm",
)

WANVIDEOMODEL = io.Custom("WANVIDEOMODEL")
WANVIDIMAGE_EMBEDS = io.Custom("WANVIDIMAGE_EMBEDS")
WANVIDEOTEXTEMBEDS = io.Custom("WANVIDEOTEXTEMBEDS")
FETAARGS = io.Custom("FETAARGS")
WANVIDCONTEXT = io.Custom("WANVIDCONTEXT")
CACHEARGS = io.Custom("CACHEARGS")
FLOWEDITARGS = io.Custom("FLOWEDITARGS")
SLGARGS = io.Custom("SLGARGS")
LOOPARGS = io.Custom("LOOPARGS")
EXPERIMENTALARGS = io.Custom("EXPERIMENTALARGS")
UNIANIMATE_POSE = io.Custom("UNIANIMATE_POSE")
FANTASYTALKING_EMBEDS = io.Custom("FANTASYTALKING_EMBEDS")
UNI3C_EMBEDS = io.Custom("UNI3C_EMBEDS")
MULTITALK_EMBEDS = io.Custom("MULTITALK_EMBEDS")
FREEINITARGS = io.Custom("FREEINITARGS")


def calculate_perfect_alignment(
    base_quality_threshold: int,
    lightning_start: int,
    lightning_steps: int,
) -> tuple[int, int, str]:
    """Return the pristine pack's exact integer stage alignment."""
    if lightning_start == 0:
        return 0, 0, "simple_math"
    if base_quality_threshold < 1:
        raise ValueError(
            "base_quality_threshold must be at least 1, "
            f"got {base_quality_threshold}"
        )
    if lightning_steps < 1:
        raise ValueError(
            f"lightning_steps must be at least 1, got {lightning_steps}"
        )
    if not 0 <= lightning_start < lightning_steps:
        raise ValueError(
            f"lightning_start ({lightning_start}) must be between 0 and "
            f"{lightning_steps - 1}"
        )
    if lightning_start == 1:
        base_steps = math.ceil(base_quality_threshold / lightning_steps)
        return base_steps, base_steps * lightning_steps, "simple_math"
    search_limit = base_quality_threshold + lightning_steps
    for candidate_total in range(base_quality_threshold, search_limit):
        if (candidate_total * lightning_start) % lightning_steps == 0:
            base_steps = (
                candidate_total * lightning_start
            ) // lightning_steps
            return base_steps, candidate_total, "mathematical_search"
    base_steps = math.ceil(
        base_quality_threshold * lightning_start / lightning_steps
    )
    optimal_total = base_steps * lightning_steps / lightning_start
    return (
        base_steps,
        max(math.ceil(optimal_total), base_quality_threshold),
        "fallback",
    )


def calculate_manual_base_steps_alignment(
    base_steps: int, lightning_start: int, lightning_steps: int
) -> int:
    if base_steps < 0:
        raise ValueError(f"base_steps must be >= 0, got {base_steps}")
    if lightning_steps < 1:
        raise ValueError(
            f"lightning_steps must be at least 1, got {lightning_steps}"
        )
    if not 0 <= lightning_start < lightning_steps:
        raise ValueError(
            f"lightning_start ({lightning_start}) must be between 0 and "
            f"{lightning_steps - 1}"
        )
    if lightning_start == 0:
        return base_steps
    return max(
        math.floor(base_steps * lightning_steps / lightning_start),
        base_steps,
    )


def _validate_basic(
    lightning_steps: int,
    lightning_start: int,
    switch_strategy: str,
    switch_step: int,
) -> None:
    if lightning_steps < 2:
        raise ValueError("lightning_steps must be at least 2.")
    if not 0 <= lightning_start < lightning_steps:
        raise ValueError(
            "lightning_start must be within [0, lightning_steps-1]. "
            f"Got lightning_start={lightning_start}, "
            f"lightning_steps={lightning_steps}"
        )
    if switch_strategy == "Manual switch step" and switch_step != -1:
        if switch_step < 0:
            raise ValueError(
                f"switch_step ({switch_step}) must be >= 0. "
                "Use switch_step=-1 for auto-calculation."
            )
        if switch_step >= lightning_steps:
            raise ValueError(
                f"switch_step ({switch_step}) must be < "
                f"lightning_steps ({lightning_steps})"
            )
        if switch_step < lightning_start:
            raise ValueError(
                f"switch_step ({switch_step}) cannot be less than "
                f"lightning_start ({lightning_start}). If you want "
                "low-noise only, set lightning_start=0 as well."
            )


def _validate_resolved(lightning_start: int, base_steps: int) -> None:
    if lightning_start > 0 and base_steps < 1:
        raise ValueError(
            "base_steps must be >= 1 when lightning_start > 0. "
            f"Got base_steps={base_steps}, lightning_start={lightning_start}"
        )
    if base_steps == 0 and lightning_start != 0:
        raise ValueError(
            "base_steps = 0 is only allowed when lightning_start = 0 "
            f"(Stage 1 skip mode). Got base_steps=0, "
            f"lightning_start={lightning_start}"
        )


def _validate_special(
    lightning_start: int,
    lightning_steps: int,
    base_steps: int,
    switch_strategy: str,
    switch_step: int,
) -> None:
    if lightning_start == 0:
        if switch_strategy == "Manual switch step":
            temporary = (
                switch_step if switch_step != -1 else lightning_steps // 2
            )
        elif switch_strategy in {
            "T2V boundary", "I2V boundary", "Manual boundary"
        }:
            temporary = 1
        else:
            temporary = math.ceil(lightning_steps / 2)
        if temporary == 0 and base_steps > 0:
            raise ValueError(
                "When skipping both Stage 1 and Stage 2, base_steps must "
                "be -1 or 0"
            )
        if base_steps > 0:
            raise ValueError(
                "Set base_steps=0 or base_steps=-1 for Lightning-only "
                "mode, or increase lightning_start to use base denoising."
            )


def _format_stage_range(start: int, end: int, total: int) -> str:
    start_safe = int(max(0, start))
    end_safe = int(max(start_safe, end))
    total_safe = int(max(1, total))
    pct_start = round(max(0.0, min(100.0, start_safe / total_safe * 100)), 1)
    pct_end = round(max(0.0, min(100.0, end_safe / total_safe * 100)), 1)
    return (
        f"steps {start_safe}-{end_safe} of {total_safe} "
        f"(denoising {pct_start:.1f}%–{pct_end:.1f}%)"
    )


def _format_base_compact(value: str) -> str:
    match = re.search(
        r"Auto-calculated base_steps = (\d+), total_base_steps = (\d+) "
        r"\(([^)]+)\)", value,
    )
    if match:
        base_steps, total_steps, method = match.groups()
        return f"Base steps: {base_steps}, Total: {total_steps} ({method})"
    match = re.search(r"Auto-calculated base_steps = (\d+) \(([^)]+)\)", value)
    if match:
        return f"Base steps: {match.group(1)} (fallback)"
    match = re.search(
        r"Auto-calculated total_base_steps = (\d+) for manual "
        r"base_steps = (\d+)", value,
    )
    if match:
        return f"Base steps: {match.group(2)}, Total: {match.group(1)} (manual)"
    return value


def _format_switch_compact(value: str) -> str:
    refinement = ""
    match = re.search(r"\[Refined shift: ([\d.]+)→([\d.]+)\]", value)
    if match:
        refinement = (
            f"\n  (σ-shift refined: {match.group(1)} → {match.group(2)})"
        )
        value = re.sub(
            r"\s*\[Refined shift: [\d.]+→[\d.]+\]", "", value
        )
    match = re.search(
        r"Model switching: ([^(]+) \(boundary = ([^)]+)\) → "
        r"switch at step (\d+) of (\d+)", value,
    )
    if match:
        return (
            f"Switch: {match.group(1).strip()} → step {match.group(3)} "
            f"of {match.group(4)}{refinement}"
        )
    match = re.search(
        r"Model switching: ([^→]+) → switch at step (\d+) of (\d+)",
        value,
    )
    if match:
        return (
            f"Switch: {match.group(1).strip()} → step {match.group(2)} "
            f"of {match.group(3)}{refinement}"
        )
    return value


def _dry_run_payload(
    stage1_info: str,
    stage2_info: str,
    stage3_info: str,
    base_calculation_info: str,
    model_switching_info: str,
) -> dict[str, Any]:
    lines: list[str] = []
    if base_calculation_info or model_switching_info:
        lines.append("Calculations:")
        if base_calculation_info:
            lines.append(f"• {_format_base_compact(base_calculation_info)}")
        if model_switching_info:
            lines.append(f"• {_format_switch_compact(model_switching_info)}")
        lines.append("")
    lines.extend((
        "Stage Configuration:",
        f"• {stage1_info}",
        f"• {stage2_info}",
        f"• {stage3_info}",
    ))
    return {
        "severity": "info",
        "summary": "TripleKSampler: Dry Run Complete",
        "detail": "\n".join(lines),
        "life": 12000,
    }


def _overlap_payload(overlap_pct: float) -> dict[str, Any]:
    return {
        "severity": "warn",
        "summary": "TripleKSampler: Stage overlap",
        "detail": (
            f"Stage 1 and Stage 2 overlap by {overlap_pct:.1f}%. "
            "Consider base_steps=-1 or adjust lightning parameters."
        ),
        "life": 8000,
    }


def _base_calculation(
    base_steps: int,
    base_quality_threshold: int,
    lightning_start: int,
    lightning_steps: int,
) -> tuple[int, int, str, dict[str, Any]]:
    ui: dict[str, Any] = {}
    if base_steps == -1:
        resolved, total, method = calculate_perfect_alignment(
            base_quality_threshold, lightning_start, lightning_steps
        )
        if lightning_start > 0:
            if method == "mathematical_search":
                info = (
                    f"Auto-calculated base_steps = {resolved}, "
                    f"total_base_steps = {total} (mathematical search)"
                )
            elif method == "simple_math":
                info = (
                    f"Auto-calculated base_steps = {resolved}, "
                    f"total_base_steps = {total} (simple math)"
                )
            else:
                info = (
                    f"Auto-calculated base_steps = {resolved} "
                    "(fallback - no perfect alignment found)"
                )
        else:
            info = ""
        return resolved, total, info, ui

    total = calculate_manual_base_steps_alignment(
        base_steps, lightning_start, lightning_steps
    )
    info = (
        f"Auto-calculated total_base_steps = {total} for manual "
        f"base_steps = {base_steps}"
    )
    if lightning_start > 0 and base_steps > 0 and total > 0:
        stage1_end = base_steps / total
        stage2_start = lightning_start / lightning_steps
        if stage1_end > stage2_start:
            ui["triple_ksampler_overlap"] = _overlap_payload(
                (stage1_end - stage2_start) * 100.0
            )
    return base_steps, total, info, ui


def _base_strategy(strategy: str) -> str:
    return strategy.replace(" (refined)", "")


def _target_boundary(strategy: str, manual_boundary: float) -> float:
    base = _base_strategy(strategy)
    if base == "T2V boundary":
        return DEFAULT_BOUNDARY_T2V
    if base == "I2V boundary":
        return DEFAULT_BOUNDARY_I2V
    if base == "Manual boundary":
        return float(manual_boundary)
    raise ValueError(f"Strategy {base!r} is not boundary-based")


async def _patch_sd3(model: Any, shift: float):
    return await model.patch(
        "sd3_advanced_sampling",
        shift=float(shift),
        cut_off=1.0,
        shift_multiplier=1.0,
    )


async def _standard_sigma_at(
    model: Any,
    scheduler: str,
    steps: int,
    step: int,
    shift: float,
    sampler_name: str,
) -> float:
    patched = await _patch_sd3(model, shift)
    delta = await patched.sampling_sigma_delta(
        steps=int(steps),
        sampler_name=str(sampler_name),
        scheduler=str(scheduler),
        start_step=int(step),
        end_step=int(steps),
        denoise=1.0,
    )
    return float(delta) * float(await patched.latent_scale_factor())


async def _standard_boundary_step(
    patched_model: Any,
    scheduler: str,
    steps: int,
    boundary: float,
    sampler_name: str,
) -> int:
    if not 0.0 <= float(boundary) <= 1.0:
        raise ValueError(
            f"boundary must be between 0.0 and 1.0, got {boundary}. "
            "Recommended: T2V=0.875, I2V=0.900"
        )
    scale = float(await patched_model.latent_scale_factor())
    switching_step = steps
    # The pristine implementation deliberately ignores the schedule's first
    # sigma for ComfyUI samplers.
    for index in range(1, steps + 1):
        delta = await patched_model.sampling_sigma_delta(
            steps=steps,
            sampler_name=sampler_name,
            scheduler=scheduler,
            start_step=index,
            end_step=steps,
            denoise=1.0,
        )
        if float(delta) * scale < float(boundary):
            switching_step = index
            break
    return min(int(switching_step), steps - 1)


async def _refine_shift(
    sigma_at: Callable[[float], Awaitable[float]],
    target_sigma: float,
    initial_shift: float,
) -> tuple[float, str]:
    baseline = await sigma_at(initial_shift)
    baseline_diff = abs(baseline - target_sigma)
    test_up = min(initial_shift + SEARCH_INTERVAL, 100.0)
    test_down = max(initial_shift - SEARCH_INTERVAL, 0.0)
    diff_up = abs(await sigma_at(test_up) - target_sigma)
    diff_down = abs(await sigma_at(test_down) - target_sigma)
    if diff_up < baseline_diff:
        direction = 1
    elif diff_down < baseline_diff:
        direction = -1
    else:
        return initial_shift, (
            f"Local optimum at initial shift {initial_shift:.2f} "
            f"(diff={baseline_diff:.4f})"
        )
    shift = initial_shift
    previous = baseline_diff
    iterations = 0
    while True:
        shift += direction * SEARCH_INTERVAL
        if shift < 0.0 or shift > 100.0:
            final = shift - direction * SEARCH_INTERVAL
            return final, (
                f"Boundary reached after {iterations} iterations "
                f"(closest: {final:.2f})"
            )
        current = abs(await sigma_at(shift) - target_sigma)
        iterations += 1
        if current > previous:
            final = shift - direction * SEARCH_INTERVAL
            return final, (
                f"Converged after {iterations} iterations at {final:.2f} "
                f"(diff={previous:.4f})"
            )
        previous = current
        if iterations > 10000:
            raise ValueError(
                "Search exceeded 10000 iterations. "
                f"Started at {initial_shift:.2f}, "
                f"target_sigma={target_sigma:.3f}"
            )


async def _standard_switch(
    strategy: str,
    switch_step: int,
    switch_boundary: float,
    lightning_steps: int,
    patched_high: Any,
    scheduler: str,
    sampler_name: str,
) -> tuple[int, str]:
    if strategy == "Manual switch step":
        if switch_step == -1:
            calculated = lightning_steps // 2
            effective = "50% of steps (auto)"
        else:
            calculated = switch_step
            effective = "Manual switch step"
    elif strategy in {"T2V boundary", "I2V boundary", "Manual boundary"}:
        boundary = _target_boundary(strategy, switch_boundary)
        calculated = await _standard_boundary_step(
            patched_high, scheduler, lightning_steps, boundary, sampler_name
        )
        effective = strategy
    else:
        # Refined strategies intentionally discover at 50%, then tune shift so
        # their requested boundary lands on that fixed step.
        calculated = math.ceil(lightning_steps / 2)
        effective = strategy
    calculated = int(calculated)
    if strategy in {"T2V boundary", "I2V boundary", "Manual boundary"}:
        boundary = _target_boundary(strategy, switch_boundary)
        info = (
            f"Model switching: {effective} (boundary = {boundary}) → "
            f"switch at step {calculated} of {lightning_steps}"
        )
    else:
        info = (
            f"Model switching: {effective} → switch at step {calculated} "
            f"of {lightning_steps}"
        )
    return calculated, info


async def _standard_execute(
    *,
    base_high: Any,
    lightning_high: Any,
    lightning_low: Any,
    positive: Any,
    negative: Any,
    latent_image: Any,
    seed: int,
    sigma_shift: float,
    base_quality_threshold: int,
    base_steps: int,
    base_cfg: float,
    base_sampler: str,
    base_scheduler: str,
    lightning_start: int,
    lightning_steps: int,
    lightning_cfg: float,
    lightning_sampler: str,
    lightning_scheduler: str,
    switch_strategy: str,
    switch_step: int,
    switch_boundary: float,
    dry_run: bool,
):
    _validate_basic(
        lightning_steps, lightning_start, switch_strategy, switch_step
    )
    resolved_base, total_base, base_info, ui_payload = _base_calculation(
        base_steps,
        base_quality_threshold,
        lightning_start,
        lightning_steps,
    )
    _validate_resolved(lightning_start, resolved_base)
    _validate_special(
        lightning_start,
        lightning_steps,
        resolved_base,
        switch_strategy,
        switch_step,
    )

    patched_base = await _patch_sd3(base_high, sigma_shift)
    patched_high = await _patch_sd3(lightning_high, sigma_shift)
    patched_low = await _patch_sd3(lightning_low, sigma_shift)
    calculated_switch, switch_info = await _standard_switch(
        switch_strategy,
        switch_step,
        switch_boundary,
        lightning_steps,
        patched_high,
        lightning_scheduler,
        lightning_sampler,
    )

    final_shift = float(sigma_shift)
    if switch_strategy.endswith(" (refined)"):
        try:
            boundary = _target_boundary(switch_strategy, switch_boundary)

            async def sigma_at(candidate: float) -> float:
                return await _standard_sigma_at(
                    lightning_high,
                    lightning_scheduler,
                    lightning_steps,
                    calculated_switch,
                    candidate,
                    lightning_sampler,
                )

            final_shift, _ = await _refine_shift(
                sigma_at, boundary, float(sigma_shift)
            )
            switch_info += (
                f" [Refined shift: {sigma_shift:.2f}→{final_shift:.2f}]"
            )
        except Exception:
            final_shift = float(sigma_shift)
    if final_shift != float(sigma_shift):
        patched_base = await _patch_sd3(base_high, final_shift)
        patched_high = await _patch_sd3(lightning_high, final_shift)
        patched_low = await _patch_sd3(lightning_low, final_shift)

    if lightning_start > calculated_switch:
        raise ValueError("lightning_start cannot be greater than switch_step.")
    skip_stage1 = lightning_start == 0
    skip_stage2 = lightning_start == calculated_switch
    stage1_info = (
        "Skipped (Lightning-only mode)"
        if skip_stage1
        else _format_stage_range(0, resolved_base, total_base)
    )
    stage2_info = (
        "Skipped (lightning_start equals switch point)"
        if skip_stage2
        else _format_stage_range(
            lightning_start, calculated_switch, lightning_steps
        )
    )
    stage3_start = max(lightning_start, calculated_switch)
    stage3_info = _format_stage_range(
        stage3_start, lightning_steps, lightning_steps
    )

    if dry_run:
        ui_payload["triple_ksampler_dry_run"] = _dry_run_payload(
            stage1_info,
            stage2_info,
            stage3_info,
            base_info,
            switch_info,
        )
        await sdk.ctx().execution.interrupt()
        return io.NodeOutput(latent_image, ui=ui_payload)

    stage1_output = latent_image
    if not skip_stage1:
        stage1_output = await sdk.ctx().sample(
            latent_image,
            total_base,
            model=patched_base,
            positive=positive,
            negative=negative,
            cfg=base_cfg,
            seed=seed,
            sampler_name=base_sampler,
            scheduler=base_scheduler,
            denoise=1.0,
            disable_noise=False,
            start_step=0,
            last_step=resolved_base,
            force_full_denoise=False,
        )

    stage2_output = stage1_output
    if not skip_stage2:
        stage2_output = await sdk.ctx().sample(
            stage1_output,
            lightning_steps,
            model=patched_high,
            positive=positive,
            negative=negative,
            cfg=lightning_cfg,
            seed=seed,
            sampler_name=lightning_sampler,
            scheduler=lightning_scheduler,
            denoise=1.0,
            disable_noise=not skip_stage1,
            start_step=lightning_start,
            last_step=calculated_switch,
            force_full_denoise=False,
        )

    final = await sdk.ctx().sample(
        stage2_output,
        lightning_steps,
        model=patched_low,
        positive=positive,
        negative=negative,
        cfg=lightning_cfg,
        seed=seed + STAGE3_SEED_OFFSET,
        sampler_name=lightning_sampler,
        scheduler=lightning_scheduler,
        denoise=1.0,
        disable_noise=not (skip_stage1 and skip_stage2),
        start_step=stage3_start,
        last_step=lightning_steps,
        force_full_denoise=True,
    )
    return io.NodeOutput(final, ui=ui_payload or None)


def _seed_input() -> io.Int.Input:
    return io.Int.Input(
        "seed",
        default=0,
        min=0,
        max=0xFFFFFFFFFFFFFFFF,
        step=1,
        control_after_generate=True,
        tooltip="The random seed used for creating the noise.",
    )


def _model_inputs() -> list[io.Input]:
    return [
        io.Model.Input("base_high", tooltip="Base high-noise model for Stage 1."),
        io.Model.Input(
            "lightning_high", tooltip="Lightning high-noise model for Stage 2."
        ),
        io.Model.Input(
            "lightning_low", tooltip="Lightning low-noise model for Stage 3."
        ),
        io.Conditioning.Input("positive", tooltip="Positive prompt conditioning."),
        io.Conditioning.Input("negative", tooltip="Negative prompt conditioning."),
        io.Latent.Input("latent_image", tooltip="Latent image to denoise."),
    ]


def _standard_common_inputs() -> list[io.Input]:
    return [
        *_model_inputs(),
        _seed_input(),
        io.Float.Input(
            "sigma_shift", default=5.0, min=0.0, max=100.0, step=0.01,
            tooltip=(
                "Sigma adjustment applied via ModelSamplingSD3 for model sampling."
            ),
        ),
    ]


def _standard_advanced_inputs(*, dynamic: bool) -> list[io.Input]:
    inputs = [
        *_standard_common_inputs(),
        io.Int.Input(
            "base_quality_threshold", default=20, min=1, max=100, step=1,
            tooltip=(
                "Minimum total steps for base_steps auto-calculation "
                "(config default: 20). Only applies when base_steps=-1."
            ),
        ),
        io.Int.Input(
            "base_steps", default=-1, min=-1, max=100,
            tooltip=(
                "Stage 1 steps for base high-noise model. Use -1 for "
                "auto-calculation based on quality threshold."
            ),
        ),
        io.Float.Input(
            "base_cfg", default=3.5, min=0.0, max=100.0, step=0.1,
            tooltip="CFG scale for Stage 1.",
        ),
        io.Combo.Input(
            "base_sampler", options=SAMPLER_NAMES, default="euler",
            tooltip="Sampler for Stage 1 (base model).",
        ),
        io.Combo.Input(
            "base_scheduler", options=SCHEDULER_NAMES, default="simple",
            tooltip="Scheduler for Stage 1 (base model).",
        ),
        io.Int.Input(
            "lightning_start", default=1, min=0, max=99,
            tooltip=(
                "Starting step within lightning schedule. Set to 0 to skip "
                "Stage 1 entirely."
            ),
        ),
        io.Int.Input(
            "lightning_steps", default=8, min=2, max=100,
            tooltip="Total steps for lightning stages.",
        ),
        io.Float.Input(
            "lightning_cfg", default=1.0, min=0.0, max=100.0, step=0.1,
            tooltip="CFG scale for Stage 2 and Stage 3.",
        ),
        io.Combo.Input(
            "lightning_sampler", options=SAMPLER_NAMES, default="euler",
            tooltip="Sampler for Stage 2 and Stage 3 (lightning models).",
        ),
        io.Combo.Input(
            "lightning_scheduler", options=SCHEDULER_NAMES, default="simple",
            tooltip="Scheduler for Stage 2 and Stage 3 (lightning models).",
        ),
        io.Combo.Input(
            "switch_strategy", options=ADVANCED_STRATEGIES,
            default="50% of steps",
            tooltip=(
                "Strategy for switching between models. Refined variants "
                "auto-tune sigma_shift for perfect boundary alignment at the "
                "switch step."
            ),
        ),
    ]
    inputs.extend((
        io.Int.Input(
            "switch_step", default=-1, min=-1, max=99, optional=dynamic,
            tooltip=(
                "Manual step to switch models. Only used when switch_strategy "
                "is 'Manual switch step'. Use -1 for auto-calculation at 50% "
                "of lightning steps."
            ),
        ),
        io.Float.Input(
            "switch_boundary", default=0.875, min=0.0, max=1.0,
            step=0.001, optional=dynamic,
            tooltip=(
                "Sigma boundary for switching. Only used when switch_strategy "
                "is 'Manual boundary'."
            ),
        ),
        io.Boolean.Input(
            "dry_run", default=False, optional=dynamic,
            tooltip=(
                "Enable dry run mode to test stage calculations without actual "
                "sampling."
            ),
        ),
    ))
    return inputs


class TripleKSamplerAdvancedAlt(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("sample", "execution.interrupt")

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="TripleKSamplerWan22LightningAdvancedAlt",
            display_name="TripleKSampler (Advanced Alt)",
            category="TripleKSampler/sampling",
            description=(
                "Advanced triple-stage cascade sampler with all parameters "
                "exposed for Wan2.2 split models with Lightning LoRA."
            ),
            inputs=_standard_advanced_inputs(dynamic=False),
            outputs=[io.Latent.Output("LATENT")],
        )

    @classmethod
    async def execute(
        cls, base_high, lightning_high, lightning_low, positive, negative,
        latent_image, seed, sigma_shift, base_quality_threshold, base_steps,
        base_cfg, base_sampler, base_scheduler, lightning_start,
        lightning_steps, lightning_cfg, lightning_sampler,
        lightning_scheduler, switch_strategy, switch_step=-1,
        switch_boundary=0.875, dry_run=False,
    ):
        return await _standard_execute(
            base_high=base_high,
            lightning_high=lightning_high,
            lightning_low=lightning_low,
            positive=positive,
            negative=negative,
            latent_image=latent_image,
            seed=int(seed),
            sigma_shift=float(sigma_shift),
            base_quality_threshold=int(base_quality_threshold),
            base_steps=int(base_steps),
            base_cfg=float(base_cfg),
            base_sampler=str(base_sampler),
            base_scheduler=str(base_scheduler),
            lightning_start=int(lightning_start),
            lightning_steps=int(lightning_steps),
            lightning_cfg=float(lightning_cfg),
            lightning_sampler=str(lightning_sampler),
            lightning_scheduler=str(lightning_scheduler),
            switch_strategy=str(switch_strategy),
            switch_step=int(switch_step),
            switch_boundary=float(switch_boundary),
            dry_run=bool(dry_run),
        )


class TripleKSamplerAdvanced(TripleKSamplerAdvancedAlt):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="TripleKSamplerWan22LightningAdvanced",
            display_name="TripleKSampler (Advanced)",
            category="TripleKSampler/sampling",
            description=(
                "Advanced triple-stage cascade sampler with dynamic UI for "
                "Wan2.2 split models with Lightning LoRA."
            ),
            inputs=_standard_advanced_inputs(dynamic=True),
            outputs=[io.Latent.Output("LATENT")],
        )


class TripleKSampler(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("sample",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="TripleKSamplerWan22Lightning",
            display_name="TripleKSampler (Simple)",
            category="TripleKSampler/sampling",
            description=(
                "Triple-stage sampler for Wan2.2 split models with Lightning "
                "LoRA. Simplified interface with auto-calculated parameters."
            ),
            inputs=[
                *_standard_common_inputs(),
                io.Float.Input(
                    "base_cfg", default=3.5, min=0.0, max=100.0, step=0.1,
                    tooltip="CFG scale for Stage 1.",
                ),
                io.Int.Input(
                    "lightning_start", default=1, min=0, max=99,
                    tooltip=(
                        "Starting step within lightning schedule. Set to 0 to "
                        "skip Stage 1 entirely."
                    ),
                ),
                io.Int.Input(
                    "lightning_steps", default=8, min=2, max=100,
                    tooltip="Total steps for lightning stages.",
                ),
                io.Combo.Input(
                    "sampler_name", options=SAMPLER_NAMES, default="euler",
                    tooltip="Sampler to use for all stages.",
                ),
                io.Combo.Input(
                    "scheduler", options=SCHEDULER_NAMES, default="simple",
                    tooltip="Scheduler to use for all stages.",
                ),
                io.Combo.Input(
                    "switch_strategy", options=SIMPLE_STRATEGIES,
                    default="50% of steps",
                    tooltip=(
                        "Strategy for switching between models. Refined "
                        "variants auto-tune sigma_shift for perfect boundary "
                        "alignment at the switch step."
                    ),
                ),
            ],
            outputs=[io.Latent.Output("LATENT")],
        )

    @classmethod
    async def execute(
        cls, base_high, lightning_high, lightning_low, positive, negative,
        latent_image, seed, sigma_shift, base_cfg, lightning_start,
        lightning_steps, sampler_name, scheduler, switch_strategy,
    ):
        return await _standard_execute(
            base_high=base_high,
            lightning_high=lightning_high,
            lightning_low=lightning_low,
            positive=positive,
            negative=negative,
            latent_image=latent_image,
            seed=int(seed),
            sigma_shift=float(sigma_shift),
            base_quality_threshold=DEFAULT_BASE_QUALITY_THRESHOLD,
            base_steps=-1,
            base_cfg=float(base_cfg),
            base_sampler=str(sampler_name),
            base_scheduler=str(scheduler),
            lightning_start=int(lightning_start),
            lightning_steps=int(lightning_steps),
            lightning_cfg=1.0,
            lightning_sampler=str(sampler_name),
            lightning_scheduler=str(scheduler),
            switch_strategy=str(switch_strategy),
            switch_step=-1,
            switch_boundary=DEFAULT_BOUNDARY_T2V,
            dry_run=False,
        )


class SwitchStrategySimple(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SwitchStrategySimple",
            display_name="Switch Strategy (Simple)",
            category="TripleKSampler/utilities",
            description=(
                "Strategy selector for TripleKSampler (Simple). Outputs one "
                "of the five simple switching strategies."
            ),
            inputs=[io.Combo.Input(
                "switch_strategy", options=SIMPLE_STRATEGIES,
                default="50% of steps",
            )],
            outputs=[io.Combo.Output(
                "switch_strategy", options=SIMPLE_STRATEGIES
            )],
        )

    @classmethod
    async def execute(cls, switch_strategy):
        return io.NodeOutput(str(switch_strategy))


class SwitchStrategyAdvanced(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SwitchStrategyAdvanced",
            display_name="Switch Strategy (Advanced)",
            category="TripleKSampler/utilities",
            description=(
                "Strategy selector for TripleKSampler (Advanced). Outputs one "
                "of all eight switching strategies."
            ),
            inputs=[io.Combo.Input(
                "switch_strategy", options=ADVANCED_STRATEGIES,
                default="50% of steps",
            )],
            outputs=[io.Combo.Output(
                "switch_strategy", options=ADVANCED_STRATEGIES
            )],
        )

    @classmethod
    async def execute(cls, switch_strategy):
        return io.NodeOutput(str(switch_strategy))


def _wanvideo_optional_inputs(*, include_dry_run: bool) -> list[io.Input]:
    values: list[io.Input] = [
        WANVIDEOTEXTEMBEDS.Input("text_embeds", optional=True),
        FETAARGS.Input("feta_args", optional=True),
        WANVIDCONTEXT.Input("context_options", optional=True),
        CACHEARGS.Input("cache_args", optional=True),
        FLOWEDITARGS.Input("flowedit_args", optional=True),
        SLGARGS.Input("slg_args", optional=True),
        LOOPARGS.Input("loop_args", optional=True),
        EXPERIMENTALARGS.Input("experimental_args", optional=True),
        io.Sigmas.Input("sigmas", optional=True),
        UNIANIMATE_POSE.Input("unianimate_poses", optional=True),
        FANTASYTALKING_EMBEDS.Input("fantasytalking_embeds", optional=True),
        UNI3C_EMBEDS.Input("uni3c_embeds", optional=True),
        MULTITALK_EMBEDS.Input("multitalk_embeds", optional=True),
        FREEINITARGS.Input("freeinit_args", optional=True),
    ]
    if include_dry_run:
        values.append(io.Boolean.Input(
            "dry_run", default=False, optional=True,
            tooltip=(
                "Enable dry run mode to test stage calculations without actual "
                "sampling."
            ),
        ))
    return values


def _wanvideo_model_inputs() -> list[io.Input]:
    return [
        WANVIDEOMODEL.Input(
            "base_high", tooltip="Base high-noise model for Stage 1."
        ),
        WANVIDEOMODEL.Input(
            "lightning_high", tooltip="Lightning high-noise model for Stage 2."
        ),
        WANVIDEOMODEL.Input(
            "lightning_low", tooltip="Lightning low-noise model for Stage 3."
        ),
        WANVIDIMAGE_EMBEDS.Input("image_embeds"),
        _seed_input(),
        io.Float.Input(
            "sigma_shift", default=5.0, min=0.0, max=100.0, step=0.01,
            tooltip="Sigma adjustment applied to all models for WanVideo sampling.",
        ),
    ]


def _wanvideo_tail_inputs() -> list[io.Input]:
    return [
        io.Boolean.Input(
            "force_offload", default=True,
            tooltip="Moves the model to the offload device after sampling",
        ),
        io.Int.Input(
            "riflex_freq_index", default=0, min=0, max=1000, step=1,
            tooltip=(
                "Frequency index for RIFLEX, disabled when 0, default 6. "
                "Allows for new frames to be generated after without looping"
            ),
        ),
        io.Boolean.Input(
            "batched_cfg", default=False,
            tooltip=(
                "Batch cond and uncond for faster sampling, possibly faster on "
                "some hardware, uses more memory"
            ),
        ),
        io.Combo.Input(
            "rope_function", options=("default", "comfy", "comfy_chunked"),
            default="comfy",
            tooltip=(
                "Comfy's RoPE implementation avoids complex numbers and can be "
                "compiled; chunked mode reduces peak VRAM."
            ),
        ),
    ]


def _wanvideo_advanced_inputs() -> list[io.Input]:
    return [
        *_wanvideo_model_inputs(),
        io.Int.Input(
            "base_quality_threshold", default=20, min=1, max=100, step=1,
            tooltip=(
                "Minimum total steps for base_steps auto-calculation. Only "
                "applies when base_steps=-1."
            ),
        ),
        io.Int.Input(
            "base_steps", default=-1, min=-1, max=100,
            tooltip=(
                "Stage 1 steps for base high-noise model. Use -1 for "
                "auto-calculation based on quality threshold."
            ),
        ),
        io.Float.Input(
            "base_cfg", default=3.5, min=0.0, max=100.0, step=0.1,
            tooltip="CFG scale for Stage 1 (base model).",
        ),
        io.Combo.Input(
            "base_scheduler", options=WANVIDEO_SCHEDULERS, default="unipc",
            tooltip="Scheduler for Stage 1 (base model).",
        ),
        io.Int.Input(
            "lightning_start", default=1, min=0, max=99,
            tooltip=(
                "Starting step within lightning schedule. Set to 0 to skip "
                "Stage 1 entirely."
            ),
        ),
        io.Int.Input(
            "lightning_steps", default=8, min=2, max=100,
            tooltip="Total steps for lightning stages.",
        ),
        io.Float.Input(
            "lightning_cfg", default=1.0, min=0.0, max=100.0, step=0.1,
            tooltip="CFG scale for Stage 2 and Stage 3 (lightning models).",
        ),
        io.Combo.Input(
            "lightning_scheduler", options=WANVIDEO_SCHEDULERS,
            default="unipc",
            tooltip="Scheduler for Stage 2 and Stage 3 (lightning models).",
        ),
        io.Combo.Input(
            "switch_strategy", options=ADVANCED_STRATEGIES,
            default="50% of steps",
        ),
        io.Int.Input("switch_step", default=-1, min=-1, max=99),
        io.Float.Input(
            "switch_boundary", default=0.875, min=0.0, max=1.0,
            step=0.001,
        ),
        *_wanvideo_tail_inputs(),
        *_wanvideo_optional_inputs(include_dry_run=True),
    ]


def _wanvideo_shared_options(values: dict[str, Any]) -> dict[str, Any]:
    names = (
        "text_embeds", "feta_args", "context_options", "cache_args",
        "flowedit_args", "slg_args", "loop_args", "experimental_args",
        "sigmas", "unianimate_poses", "fantasytalking_embeds",
        "uni3c_embeds", "multitalk_embeds", "freeinit_args",
    )
    return {name: values[name] for name in names if values.get(name) is not None}


async def _wanvideo_sigmas(
    scheduler: str,
    steps: int,
    shift: float,
    transformer_dim: int,
) -> list[float]:
    """Calculate a bounded WanVideo sigma page inside the pack guest.

    The scheduler implementation is pinned under ``vendor/``.  ``multitalk``
    is the one upstream special case: WanVideoSampler constructs that schedule
    inline rather than through ``get_scheduler`` even though it is present in
    ``scheduler_list``.
    """
    scheduler = str(scheduler)
    steps = int(steps)
    shift = float(shift)
    if scheduler not in WANVIDEO_SCHEDULERS:
        raise ValueError(f"Unsupported WanVideo scheduler: {scheduler!r}")
    if not 2 <= steps <= 100:
        raise ValueError(f"WanVideo steps must be within [2, 100], got {steps}")
    if not 0.0 <= shift <= 100.0 or not math.isfinite(shift):
        raise ValueError("WanVideo shift must be finite and within [0, 100]")
    if not 1 <= int(transformer_dim) <= 65536:
        raise ValueError("WanVideo transformer_dim is outside the supported range")

    if scheduler == "multitalk":
        # Exact normalized form of WanVideoWrapper's multitalk sampling path:
        # linspace(1000, 1, steps), append 0, then timestep_transform().
        unshifted = [
            (1000.0 + (1.0 - 1000.0) * index / (steps - 1)) / 1000.0
            for index in range(steps)
        ]
        unshifted.append(0.0)
        values = [
            shift * value / (1.0 + (shift - 1.0) * value)
            for value in unshifted
        ]
    else:
        import torch

        from .vendor.wanvideo_schedulers import get_scheduler

        sample_scheduler, _, _, _ = get_scheduler(
            scheduler,
            steps,
            start_step=0,
            end_step=-1,
            shift=shift,
            device=torch.device("cpu"),
            transformer_dim=int(transformer_dim),
        )
        values = sample_scheduler.sigmas

    if hasattr(values, "tolist"):
        values = values.tolist()
    if not isinstance(values, (list, tuple)) or not 2 <= len(values) <= steps + 2:
        raise RuntimeError("WanVideo scheduler returned an invalid sigma page")
    result = [float(value) for value in values]
    if not all(math.isfinite(value) for value in result):
        raise RuntimeError("WanVideo scheduler returned a non-finite sigma")
    return result


def _wanvideo_boundary_step(
    sigmas: list[float], steps: int, boundary: float
) -> int:
    switching_step = steps
    # WanVideo's pristine implementation includes index zero but excludes the
    # terminal sigma.
    for index, sigma in enumerate(sigmas[:-1]):
        if sigma < float(boundary):
            switching_step = index
            break
    return min(int(switching_step), steps - 1)


async def _wanvideo_switch(
    *,
    model: Any,
    scheduler: str,
    steps: int,
    shift: float,
    strategy: str,
    switch_step: int,
    switch_boundary: float,
) -> tuple[int, str, float]:
    base = _base_strategy(strategy)
    transformer_dim = 5120
    if scheduler == "flowmatch_causvid" and base in {
        "T2V boundary", "I2V boundary", "Manual boundary",
    }:
        transformer_dim = int(
            await sdk.ctx().integrations.wanvideo.transformer_dim(model)
        )
        if not 1 <= transformer_dim <= 65536:
            raise RuntimeError(
                "WanVideo integration returned an invalid transformer_dim"
            )
    if base == "50% of steps":
        calculated = math.ceil(steps / 2)
        info = (
            f"Model switching: 50% of steps → switch at step {calculated} "
            f"of {steps}"
        )
    elif base == "Manual switch step":
        calculated = (
            math.ceil(steps / 2) if switch_step == -1 else int(switch_step)
        )
        label = (
            "Manual switch step (auto at 50%)"
            if switch_step == -1 else "Manual switch step"
        )
        info = (
            f"Model switching: {label} → switch at step {calculated} of {steps}"
        )
    elif base in {"T2V boundary", "I2V boundary", "Manual boundary"}:
        boundary = _target_boundary(strategy, switch_boundary)
        try:
            sigmas = await _wanvideo_sigmas(
                scheduler, steps, shift, transformer_dim
            )
            calculated = _wanvideo_boundary_step(sigmas, steps, boundary)
        except Exception:
            # Pinned WanVideo behavior keeps the workflow usable when a
            # vendor scheduler rejects a step count or cannot construct its
            # sigma page: it falls back to the midpoint.  Permission and
            # metadata failures occur before this pack-side scheduler call and
            # therefore still fail closed.
            calculated = math.ceil(steps / 2)
        info = (
            f"Model switching: {base} (boundary = {boundary:.3f}) → "
            f"switch at step {calculated} of {steps}"
        )
    else:
        calculated = math.ceil(steps / 2)
        info = (
            f"Model switching: 50% of steps (fallback) → switch at step "
            f"{calculated} of {steps}"
        )

    final_shift = float(shift)
    if strategy.endswith(" (refined)"):
        try:
            boundary = _target_boundary(strategy, switch_boundary)

            async def sigma_at(candidate: float) -> float:
                page = await _wanvideo_sigmas(
                    scheduler, steps, candidate, transformer_dim
                )
                if not 0 <= calculated < len(page):
                    raise RuntimeError(
                        "WanVideo schedule does not contain the switch step"
                    )
                return page[calculated]

            final_shift, _ = await _refine_shift(
                sigma_at, boundary, float(shift)
            )
            info += f" [Refined shift: {shift:.2f}→{final_shift:.2f}]"
        except Exception:
            final_shift = float(shift)
    return int(calculated), info, final_shift


def _graph_link(node: str, output: int) -> dict[str, Any]:
    return {"node": node, "output": output}


async def _wanvideo_execute(
    *,
    base_high: Any,
    lightning_high: Any,
    lightning_low: Any,
    image_embeds: Any,
    seed: int,
    sigma_shift: float,
    base_quality_threshold: int,
    base_steps: int,
    base_cfg: float,
    base_scheduler: str,
    lightning_start: int,
    lightning_steps: int,
    lightning_cfg: float,
    lightning_scheduler: str,
    switch_strategy: str,
    switch_step: int,
    switch_boundary: float,
    dry_run: bool,
    force_offload: bool,
    riflex_freq_index: int,
    batched_cfg: bool,
    rope_function: str,
    optional: dict[str, Any],
):
    _validate_basic(
        lightning_steps, lightning_start, switch_strategy, switch_step
    )
    resolved_base, total_base, base_info, ui_payload = _base_calculation(
        base_steps,
        base_quality_threshold,
        lightning_start,
        lightning_steps,
    )
    calculated_switch, switch_info, final_shift = await _wanvideo_switch(
        model=lightning_high,
        scheduler=lightning_scheduler,
        steps=lightning_steps,
        shift=sigma_shift,
        strategy=switch_strategy,
        switch_step=switch_step,
        switch_boundary=switch_boundary,
    )
    _validate_resolved(lightning_start, resolved_base)
    _validate_special(
        lightning_start,
        lightning_steps,
        resolved_base,
        switch_strategy,
        switch_step,
    )
    if lightning_start > calculated_switch:
        raise ValueError("lightning_start cannot be greater than switch_step.")

    skip_stage1 = lightning_start == 0 or resolved_base == 0
    skip_stage2 = lightning_start == calculated_switch
    stage1_info = (
        "Skipped (Lightning-only mode)"
        if skip_stage1
        else _format_stage_range(0, resolved_base, total_base)
    )
    stage2_info = (
        "Skipped (lightning_start equals switch point)"
        if skip_stage2
        else _format_stage_range(
            lightning_start, calculated_switch, lightning_steps
        )
    )
    stage3_start = max(lightning_start, calculated_switch)
    stage3_info = _format_stage_range(
        stage3_start, lightning_steps, lightning_steps
    )
    if dry_run:
        ui_payload["triple_ksampler_dry_run"] = _dry_run_payload(
            stage1_info,
            stage2_info,
            stage3_info,
            "" if skip_stage1 else base_info,
            switch_info,
        )
        await sdk.ctx().execution.interrupt()
        return io.NodeOutput(None, None, ui=ui_payload)

    shared = {
        "image_embeds": image_embeds,
        "shift": final_shift,
        "seed": seed,
        "riflex_freq_index": riflex_freq_index,
        "batched_cfg": batched_cfg,
        "rope_function": rope_function,
        **optional,
    }
    nodes: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    if not skip_stage1:
        nodes.append({
            "id": "stage1",
            "class_type": "WanVideoSampler",
            "inputs": {
                "model": base_high,
                "steps": total_base,
                "cfg": base_cfg,
                "scheduler": base_scheduler,
                "force_offload": force_offload,
                "start_step": 0,
                "end_step": resolved_base,
                "add_noise_to_samples": True,
                **shared,
            },
        })
        previous = _graph_link("stage1", 0)
    if not skip_stage2:
        inputs = {
            "model": lightning_high,
            "steps": lightning_steps,
            "cfg": lightning_cfg,
            "scheduler": lightning_scheduler,
            "force_offload": force_offload,
            "start_step": lightning_start,
            "end_step": calculated_switch,
            "add_noise_to_samples": previous is None,
            **shared,
        }
        if previous is not None:
            inputs["samples"] = previous
        nodes.append({
            "id": "stage2",
            "class_type": "WanVideoSampler",
            "inputs": inputs,
        })
        previous = _graph_link("stage2", 0)

    stage3_shared = {**shared, "seed": seed + STAGE3_SEED_OFFSET}
    stage3_inputs = {
        "model": lightning_low,
        "steps": lightning_steps,
        "cfg": lightning_cfg,
        "scheduler": lightning_scheduler,
        "force_offload": force_offload,
        "start_step": stage3_start,
        "end_step": -1,
        "add_noise_to_samples": previous is None,
        **stage3_shared,
    }
    if previous is not None:
        stage3_inputs["samples"] = previous
    nodes.append({
        "id": "stage3",
        "class_type": "WanVideoSampler",
        "inputs": stage3_inputs,
    })
    expansion = await sdk.ctx().graph.expand_nodes(
        nodes,
        [_graph_link("stage3", 0), _graph_link("stage3", 1)],
    )
    if ui_payload:
        expansion["ui"] = ui_payload
    return expansion


class TripleWVSamplerAdvancedAlt(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = (
        "graph.expand",
        "graph.expand.external:WanVideoSampler",
        "integrations.wanvideo",
        "execution.interrupt",
    )

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="TripleWVSamplerAdvancedAlt",
            display_name="TripleWVSampler (Advanced Alt)",
            category="TripleKSampler/wanvideo",
            description=(
                "Advanced triple-stage sampler for WanVideo models with "
                "Lightning LoRA. Static UI variant with all parameters visible."
            ),
            inputs=_wanvideo_advanced_inputs(),
            outputs=[
                io.Latent.Output("samples"),
                io.Latent.Output("denoised_samples"),
            ],
            enable_expand=True,
        )

    @classmethod
    async def execute(
        cls, base_high, lightning_high, lightning_low, image_embeds, seed,
        sigma_shift, base_quality_threshold, base_steps, base_cfg,
        base_scheduler, lightning_start, lightning_steps, lightning_cfg,
        lightning_scheduler, switch_strategy, switch_step, switch_boundary,
        force_offload, riflex_freq_index, batched_cfg, rope_function,
        text_embeds=None, feta_args=None, context_options=None,
        cache_args=None, flowedit_args=None, slg_args=None, loop_args=None,
        experimental_args=None, sigmas=None, unianimate_poses=None,
        fantasytalking_embeds=None, uni3c_embeds=None,
        multitalk_embeds=None, freeinit_args=None, dry_run=False,
    ):
        values = locals()
        return await _wanvideo_execute(
            base_high=base_high,
            lightning_high=lightning_high,
            lightning_low=lightning_low,
            image_embeds=image_embeds,
            seed=int(seed),
            sigma_shift=float(sigma_shift),
            base_quality_threshold=int(base_quality_threshold),
            base_steps=int(base_steps),
            base_cfg=float(base_cfg),
            base_scheduler=str(base_scheduler),
            lightning_start=int(lightning_start),
            lightning_steps=int(lightning_steps),
            lightning_cfg=float(lightning_cfg),
            lightning_scheduler=str(lightning_scheduler),
            switch_strategy=str(switch_strategy),
            switch_step=int(switch_step),
            switch_boundary=float(switch_boundary),
            dry_run=bool(dry_run),
            force_offload=bool(force_offload),
            riflex_freq_index=int(riflex_freq_index),
            batched_cfg=bool(batched_cfg),
            rope_function=str(rope_function),
            optional=_wanvideo_shared_options(values),
        )


class TripleWVSamplerAdvanced(TripleWVSamplerAdvancedAlt):
    @classmethod
    def define_schema(cls):
        schema = super().define_schema()
        schema.node_id = "TripleWVSamplerAdvanced"
        schema.display_name = "TripleWVSampler (Advanced)"
        schema.description = (
            "Advanced triple-stage sampler for WanVideo models with Lightning "
            "LoRA. Dynamic UI variant with context-aware parameter visibility."
        )
        return schema


class TripleWVSampler(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = (
        "graph.expand",
        "graph.expand.external:WanVideoSampler",
        "integrations.wanvideo",
    )

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="TripleWVSampler",
            display_name="TripleWVSampler (Simple)",
            category="TripleKSampler/wanvideo",
            description=(
                "Triple-stage sampler for WanVideo models with Lightning LoRA. "
                "Simplified interface with auto-calculated parameters."
            ),
            inputs=[
                *_wanvideo_model_inputs(),
                io.Float.Input(
                    "base_cfg", default=3.5, min=0.0, max=100.0, step=0.1,
                    tooltip="CFG scale for Stage 1 (Stages 2&3 use fixed 1.0).",
                ),
                io.Int.Input(
                    "lightning_start", default=1, min=0, max=99,
                    tooltip=(
                        "Starting step within lightning schedule. Set to 0 to "
                        "skip Stage 1 entirely."
                    ),
                ),
                io.Int.Input(
                    "lightning_steps", default=8, min=2, max=100,
                    tooltip="Total steps for lightning stages.",
                ),
                io.Combo.Input(
                    "scheduler", options=WANVIDEO_SCHEDULERS, default="unipc",
                    tooltip="Scheduler for all stages.",
                ),
                io.Combo.Input(
                    "switch_strategy", options=SIMPLE_STRATEGIES,
                    default="50% of steps",
                ),
                *_wanvideo_tail_inputs(),
                *_wanvideo_optional_inputs(include_dry_run=False),
            ],
            outputs=[
                io.Latent.Output("samples"),
                io.Latent.Output("denoised_samples"),
            ],
            enable_expand=True,
        )

    @classmethod
    async def execute(
        cls, base_high, lightning_high, lightning_low, image_embeds, seed,
        sigma_shift, base_cfg, lightning_start, lightning_steps, scheduler,
        switch_strategy, force_offload, riflex_freq_index, batched_cfg,
        rope_function, text_embeds=None, feta_args=None,
        context_options=None, cache_args=None, flowedit_args=None,
        slg_args=None, loop_args=None, experimental_args=None, sigmas=None,
        unianimate_poses=None, fantasytalking_embeds=None, uni3c_embeds=None,
        multitalk_embeds=None, freeinit_args=None,
    ):
        values = locals()
        return await _wanvideo_execute(
            base_high=base_high,
            lightning_high=lightning_high,
            lightning_low=lightning_low,
            image_embeds=image_embeds,
            seed=int(seed),
            sigma_shift=float(sigma_shift),
            base_quality_threshold=DEFAULT_BASE_QUALITY_THRESHOLD,
            base_steps=-1,
            base_cfg=float(base_cfg),
            base_scheduler=str(scheduler),
            lightning_start=int(lightning_start),
            lightning_steps=int(lightning_steps),
            lightning_cfg=1.0,
            lightning_scheduler=str(scheduler),
            switch_strategy=str(switch_strategy),
            switch_step=-1,
            switch_boundary=DEFAULT_BOUNDARY_T2V,
            dry_run=False,
            force_offload=bool(force_offload),
            riflex_freq_index=int(riflex_freq_index),
            batched_cfg=bool(batched_cfg),
            rope_function=str(rope_function),
            optional=_wanvideo_shared_options(values),
        )


NODE_CLASS_MAPPINGS = {
    "TripleKSamplerWan22Lightning": TripleKSampler,
    "TripleKSamplerWan22LightningAdvanced": TripleKSamplerAdvanced,
    "TripleKSamplerWan22LightningAdvancedAlt": TripleKSamplerAdvancedAlt,
    "SwitchStrategySimple": SwitchStrategySimple,
    "SwitchStrategyAdvanced": SwitchStrategyAdvanced,
    "TripleWVSamplerAdvancedAlt": TripleWVSamplerAdvancedAlt,
    "TripleWVSamplerAdvanced": TripleWVSamplerAdvanced,
    "TripleWVSampler": TripleWVSampler,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TripleKSamplerWan22Lightning": "TripleKSampler (Simple)",
    "TripleKSamplerWan22LightningAdvanced": "TripleKSampler (Advanced)",
    "TripleKSamplerWan22LightningAdvancedAlt": "TripleKSampler (Advanced Alt)",
    "SwitchStrategySimple": "Switch Strategy (Simple)",
    "SwitchStrategyAdvanced": "Switch Strategy (Advanced)",
    "TripleWVSamplerAdvancedAlt": "TripleWVSampler (Advanced Alt)",
    "TripleWVSamplerAdvanced": "TripleWVSampler (Advanced)",
    "TripleWVSampler": "TripleWVSampler (Simple)",
}
