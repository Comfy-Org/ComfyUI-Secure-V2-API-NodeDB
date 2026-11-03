"""Krea2 Enhancer Pixaroma: the prompt-adherence math.

A port of the basic node of ComfyUI-Krea2T-Enhancer by capitan01R (v1.1.2, MIT), whose author removed the
project from GitHub, the Comfy Registry and Civitai in October 2026. The math below is theirs, kept unchanged
so a workflow gives the SAME image with this node as with the original; only the names, the wrapper / option
keys (so both can be installed side by side) and the debug printing differ.

How it works: Krea 2 fuses the 12 text-encoder layers it receives ("taps") into one text stream in its
`txtfusion` transformer. During sampling this runs that fusion twice, once as usual and once with the taps
scaled up (a fixed 24-chunk gain profile times a global multiplier, both grown by `strength`), and keeps the
difference, capped per text token at 0.75 of the token's own size. The result leans harder on the prompt.

Pure torch: no comfy import here, so it can be tested on its own.

Original licence (MIT), kept as its terms require:

    MIT License

    Copyright (c) 2026 capitan01R

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
"""
import math

import torch

# transformer_options key (the node's settings) and wrapper key: our own, so the original node can sit beside it.
OPTION_KEY = "pixaroma_krea2_enhancer"
WRAPPER_KEY = "pixaroma_krea2_enhancer"
_ORIGINAL_FORWARD = "_pix_krea2_enhancer_original_forward"

KREA2_TAP_LAYERS = (2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35)
KREA2_TAP_DIM = 2560
KREA2_CHUNK_COUNT = 24
KREA2_CHUNK_DIM = 1280

ENHANCER_PROFILE_12 = (1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 2.5, 5.0, 1.1, 4.0, 1.0)
ENHANCER_CHUNK_PROFILE = ENHANCER_PROFILE_12 + ENHANCER_PROFILE_12
ENHANCER_GLOBAL_MULTIPLIER = 15.0
TXTFUSION_TOKEN_REL_CAP = 0.75

STRENGTH_MIN = 0.0
STRENGTH_MAX = 2.0


def is_krea2_model(dm):
    """True for a Krea 2 diffusion model with the 12 x 2560 text layout this math is made for."""
    return (
        hasattr(dm, "txtfusion")
        and hasattr(dm, "txtmlp")
        and hasattr(dm, "blocks")
        and hasattr(dm, "_unpack_context")
        and int(getattr(dm, "txtlayers", 0)) == len(KREA2_TAP_LAYERS)
        and int(getattr(dm, "txtdim", 0)) == KREA2_TAP_DIM
    )


def bounded_strength(value, default=1.0):
    try:
        v = float(value)
    except Exception:
        v = default
    if not math.isfinite(v):
        v = default
    return max(STRENGTH_MIN, min(STRENGTH_MAX, v))


def _chunk_gains(device, dtype, strength):
    base = torch.tensor(ENHANCER_CHUNK_PROFILE, device=device, dtype=torch.float32)
    gains = 1.0 + float(strength) * (base - 1.0)
    return gains.to(dtype=dtype)


def _run_txtfusion_parts(txtfusion, x, mask=None, transformer_options=None):
    """Core's TextFusionTransformer.forward, step by step (comfy/ldm/krea2/model.py)."""
    transformer_options = transformer_options or {}
    b, seq, taps, dim = x.shape
    y = x.reshape(b * seq, taps, dim)
    for block in txtfusion.layerwise_blocks:
        y = block(y.contiguous(), mask=None, transformer_options=transformer_options)
    tap_mix = y.reshape(b, seq, taps, dim).permute(0, 1, 3, 2).contiguous()
    projected = txtfusion.projector(tap_mix).squeeze(-1)
    out = projected
    for block in txtfusion.refiner_blocks:
        out = block(out, mask=mask, transformer_options=transformer_options)
    return out


def enhanced_txtfusion_forward(txtfusion, x, mask=None, transformer_options=None, strength=1.0):
    transformer_options = transformer_options or {}
    b, seq, taps, dim = x.shape
    if taps != len(KREA2_TAP_LAYERS) or dim != KREA2_TAP_DIM:
        return getattr(txtfusion, _ORIGINAL_FORWARD)(x, mask=mask, transformer_options=transformer_options)

    reference_out = _run_txtfusion_parts(txtfusion, x, mask=mask, transformer_options=transformer_options)
    if strength != 0.0:
        gains = _chunk_gains(x.device, x.dtype, strength)
        global_multiplier = 1.0 + float(strength) * (ENHANCER_GLOBAL_MULTIPLIER - 1.0)
        scaled_x = (
            x.reshape(b, seq, KREA2_CHUNK_COUNT, KREA2_CHUNK_DIM)
            * gains.view(1, 1, KREA2_CHUNK_COUNT, 1)
            * global_multiplier
        ).reshape_as(x)
        candidate_out = _run_txtfusion_parts(txtfusion, scaled_x, mask=mask, transformer_options=transformer_options)
    else:
        candidate_out = reference_out

    # Keep the change, capped per text token at TXTFUSION_TOKEN_REL_CAP of the token's own size.
    post_delta = candidate_out.detach().float() - reference_out.detach().float()
    token_base_rms = torch.sqrt(torch.mean(reference_out.detach().float() ** 2, dim=-1, keepdim=True)).clamp_min(1e-8)
    token_delta_rms = torch.sqrt(torch.mean(post_delta ** 2, dim=-1, keepdim=True)).clamp_min(1e-8)
    token_rel = token_delta_rms / token_base_rms
    token_scale = (TXTFUSION_TOKEN_REL_CAP / token_rel).clamp(max=1.0)
    return (reference_out.detach().float() + post_delta * token_scale).to(candidate_out.dtype)


def krea2_enhancer_wrapper(executor, *args, **kwargs):
    """DIFFUSION_MODEL wrapper: swaps the model's txtfusion forward for the enhanced one for this call only.
    Variadic on purpose: core added `ref_latents` to this call in 2026-07 and the fixed signature broke."""
    transformer_options = kwargs.get("transformer_options")
    if transformer_options is None:
        transformer_options = next((arg for arg in args if isinstance(arg, dict)), {})

    cfg = transformer_options.get(OPTION_KEY, {})
    if not cfg or not cfg.get("enabled", True) or cfg.get("_active", False):
        return executor(*args, **kwargs)

    dm = executor.class_obj
    if not is_krea2_model(dm):
        return executor(*args, **kwargs)

    strength = bounded_strength(cfg.get("strength", 1.0))
    if strength == 0.0:
        return executor(*args, **kwargs)

    txtfusion = dm.txtfusion
    if hasattr(txtfusion, _ORIGINAL_FORWARD):   # left over from an interrupted call
        txtfusion.forward = getattr(txtfusion, _ORIGINAL_FORWARD)
        delattr(txtfusion, _ORIGINAL_FORWARD)
    original_forward = txtfusion.forward

    def enhanced_forward(x_in, mask=None, transformer_options=None):
        setattr(txtfusion, _ORIGINAL_FORWARD, original_forward)
        try:
            return enhanced_txtfusion_forward(txtfusion, x_in, mask=mask,
                                              transformer_options=transformer_options or {}, strength=strength)
        finally:
            if hasattr(txtfusion, _ORIGINAL_FORWARD):
                delattr(txtfusion, _ORIGINAL_FORWARD)

    try:
        cfg["_active"] = True
        txtfusion.forward = enhanced_forward
        return executor(*args, **kwargs)
    finally:
        cfg["_active"] = False
        txtfusion.forward = original_forward
