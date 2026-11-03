"""Pure window maths for Load Audio Pixaroma.

Kept separate from the node so the arithmetic can be tested with no ComfyUI and
no torch on the path (harness: D:\\Claude Tests\\_audio_window_test.py). Only
`apply_window` touches tensors, and it does nothing except act on the plan this
module produced.

The one subtlety worth knowing: "how many samples do we need" and "how many
samples exist" are DIFFERENT numbers, and every bug in this area comes from
conflating them. `plan_window` reports both, so the caller can never accidentally
return a short buffer while believing it matched.
"""
from __future__ import annotations


# A day. Anything past this is a corrupted blob or an attack, never a clip
# someone meant. It exists because `start * sample_rate` on a large-but-FINITE
# float overflows to inf inside the multiply, and round(inf) raises an uncaught
# OverflowError that kills the run with a traceback naming neither the node nor
# the field.
_MAX_SECONDS = 86400.0


def _as_float(v, default=0.0) -> float:
    """Never raise on a value that arrived from a widget or a state blob."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    # NaN and inf both come back from a broken upstream FLOAT wire; either would
    # turn into a nonsense sample count below.
    if f != f or f in (float("inf"), float("-inf")):
        return default
    # Finite but absurd is the same problem one step later - see _MAX_SECONDS.
    if f > _MAX_SECONDS or f < -_MAX_SECONDS:
        return default
    return f


def plan_window(total_samples, sample_rate, start_s, duration_s) -> dict:
    """Work out which slice of a waveform to take.

    Returns a dict with:
      start  first sample to read
      want   how many samples the RESULT must contain
      take   how many real samples actually exist from `start`
      fill   want - take, the gap that has to be padded or looped

    `duration_s` of 0 (or absent) means "everything from `start` to the end",
    in which case fill is always 0 - you cannot come up short of a length you
    did not ask for.
    """
    total = max(0, int(total_samples or 0))
    try:
        sr = int(sample_rate or 0)
    except (TypeError, ValueError):
        sr = 0
    if sr <= 0:
        # No usable rate means seconds are meaningless; hand back the whole
        # thing rather than silently returning an empty clip.
        return {"start": 0, "want": total, "take": total, "fill": 0}

    start_s = max(0.0, _as_float(start_s))
    start = int(round(start_s * sr))
    if start > total:
        start = total          # past the end: nothing to take, all fill

    avail = total - start
    dur = _as_float(duration_s)
    want = avail if dur <= 0 else int(round(dur * sr))
    if want < 0:
        want = 0

    take = min(want, avail)
    return {"start": start, "want": want, "take": take, "fill": want - take}


def apply_window(waveform, plan: dict, when_short: str = "silence"):
    """Cut `waveform` [..., samples] down to exactly `plan["want"]` samples.

    `when_short` is "silence" (pad with real zeros) or "loop" (repeat what we
    have). Looping is done with an index tensor rather than repeated concat so
    that asking for an hour of a one-second sample costs one allocation instead
    of thousands.
    """
    import torch

    want = int(plan.get("want", 0))
    if want <= 0:
        return waveform[..., :0]

    start = int(plan.get("start", 0))
    take = int(plan.get("take", 0))
    piece = waveform[..., start:start + take]
    fill = want - take
    if fill <= 0:
        return piece

    if when_short == "loop" and take > 0:
        idx = torch.arange(fill, device=piece.device) % take
        return torch.cat([piece, piece.index_select(-1, idx)], dim=-1)

    pad = torch.zeros(
        tuple(waveform.shape[:-1]) + (fill,),
        dtype=waveform.dtype,
        device=waveform.device,
    )
    return torch.cat([piece, pad], dim=-1) if take > 0 else pad


def window_report(plan: dict, sample_rate) -> dict:
    """Plain numbers for the node face and the console, in seconds."""
    try:
        sr = int(sample_rate or 0)
    except (TypeError, ValueError):
        sr = 0
    if sr <= 0:
        return {"start_s": 0.0, "want_s": 0.0, "take_s": 0.0, "fill_s": 0.0, "short": False}
    return {
        "start_s": plan.get("start", 0) / sr,
        "want_s": plan.get("want", 0) / sr,
        "take_s": plan.get("take", 0) / sr,
        "fill_s": plan.get("fill", 0) / sr,
        "short": plan.get("fill", 0) > 0,
    }
