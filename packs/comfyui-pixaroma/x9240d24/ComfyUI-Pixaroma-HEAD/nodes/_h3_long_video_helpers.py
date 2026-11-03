"""Pure maths for H3 Long Video Pixaroma (windowed sampling for MiniMax H3).

No torch, no ComfyUI - so the arithmetic can be checked in isolation
(harness: D:\\Claude Tests\\_h3_long_video_test.py).

THE GRID, read out of ComfyUI's own comfy/ldm/minimax/model.py and
comfy_extras/nodes_minimax_h3.py:

  FRAME_PER_TOKEN  (1, 4, 4, 4, 4)  pixel frames per video latent token, repeating
                                    every 5 tokens = 17 frames
  clip lengths     17n + 5 frames   = 5n + 2 tokens
  audio            40 latent frames per second = 5/3 per pixel frame (24 fps)

So a window must START on a 5-token boundary (17 frames), or its first token
would be read as a 1-frame token when it is really a 4-frame one, and it is
5n + 2 tokens long like every clip the model was trained on. Audio is sliced by
time; 17 frames is 28.33 audio frames, so the audio start rounds by at most
two thirds of an audio frame (17 ms).
"""
from __future__ import annotations

FRAME_PER_TOKEN = (1, 4, 4, 4, 4)
FPS = 24
AUDIO_PER_FRAME = 5.0 / 3.0          # 40 audio latent fps / 24 video fps
CHUNK_FRAMES = 17                     # 5 tokens

WINDOW_DEFAULT_S = 10.0
WINDOW_MIN_S = 4.0                    # MiniMax's model card: 4 to 15 seconds
WINDOW_MAX_S = 15.0
OVERLAP_DEFAULT_S = 1.5
OVERLAP_MIN_S = 0.5
OVERLAP_MAX_S = 7.0
TRACK_REF_TOLERANCE = 4               # audio frames: a reference audio this close to the clip IS the clip's track


def frames_of(n_tokens) -> int:
    """Pixel frames covered by the first n video latent tokens."""
    n = max(0, int(n_tokens))
    return (n // 5) * CHUNK_FRAMES + sum(FRAME_PER_TOKEN[k] for k in range(n % 5))


def audio_at(frame) -> int:
    """Audio latent frame that lines up with a pixel frame."""
    return int(round(frame * AUDIO_PER_FRAME))


def _num(value, fallback):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return fallback
    return v if v == v and v not in (float("inf"), float("-inf")) else fallback


def window_chunks(window_seconds, overlap_seconds):
    """Seconds from the node -> (window chunks n, stride chunks). A window is 17n + 5 frames.

    The overlap is (n - stride) chunks + 5 frames, so it is snapped to the nearest
    17 frames too; it never reaches the whole window (stride >= 1)."""
    w = min(WINDOW_MAX_S, max(WINDOW_MIN_S, _num(window_seconds, WINDOW_DEFAULT_S)))
    o = min(OVERLAP_MAX_S, max(OVERLAP_MIN_S, _num(overlap_seconds, OVERLAP_DEFAULT_S)))
    n = max(1, int(round((w * FPS - 5) / CHUNK_FRAMES)))
    ov = max(1, int(round((o * FPS - 5) / CHUNK_FRAMES)))
    return n, max(1, n - ov)


def describe(n, stride):
    """Human numbers for a plan: (window seconds, overlap seconds)."""
    win = (CHUNK_FRAMES * n + 5) / FPS
    ovl = (CHUNK_FRAMES * (n - stride) + 5) / FPS
    return round(win, 2), round(ovl, 2)


def plan_windows(latent_t, audio_t, n, stride):
    """-> [(l0, l1, a0, a1)] token / audio-frame ranges, every window the SAME shape, or None when one window
    already covers the clip (the node then does nothing).

    The last window is shifted back so it ends exactly on the clip's end instead of running short; identical
    shapes also mean ComfyUI's allocation recording sees one shape, not a new one per window."""
    latent_t, audio_t = int(latent_t), int(audio_t)
    chunks = (latent_t - 2) // 5
    if latent_t != 5 * chunks + 2 or n >= chunks or audio_t <= 0:
        return None
    starts = list(range(0, chunks - n + 1, max(1, stride)))
    if starts[-1] != chunks - n:
        starts.append(chunks - n)
    alen = min(audio_t, audio_at(frames_of(5 * n + 2)))
    out = []
    for s in starts:
        l0 = 5 * s
        # the last window ENDS on the clip's last audio frame: from its rounded start it could stop one short
        a0 = audio_t - alen if s == starts[-1] else min(audio_at(frames_of(l0)), audio_t - alen)
        out.append((l0, l0 + 5 * n + 2, a0, a0 + alen))
    return out


def ramp_weights(spans):
    """Blend weights per window over its own [start, stop): 1 inside, a straight ramp across the overlap with
    each neighbour, normalised so the windows covering any position add up to exactly 1."""
    ws = []
    for i, (s, e) in enumerate(spans):
        w = [1.0] * (e - s)
        if i > 0 and spans[i - 1][1] > s:
            width = spans[i - 1][1] - s
            w = [min(v, (j + 0.5) / width) for j, v in enumerate(w)]
        if i + 1 < len(spans) and spans[i + 1][0] < e:
            width = e - spans[i + 1][0]
            w = [min(v, (e - (s + j) - 0.5) / width) for j, v in enumerate(w)]
        ws.append([max(v, 1e-4) for v in w])
    total = [0.0] * max(e for _, e in spans)
    for (s, _), w in zip(spans, ws):
        for j, v in enumerate(w):
            total[s + j] += v
    return [[v / total[s + j] for j, v in enumerate(w)] for (s, _), w in zip(spans, ws)]


def place_guide(frame_idx, clip_tokens, l0, l1):
    """Where a pinned guide (MiniMaxH3AddGuide / a first or last frame) lands inside window [l0, l1).

    frame_idx is the guide's first pixel frame on the WHOLE clip, clip_tokens its video latent length (0 for an
    audio-only guide, 1 for a single picture). Returns (token_from, token_to, new_frame_idx) - the slice of the
    guide's own tokens to keep and its frame inside the window - or None when it does not reach this window.

    A clip that starts on a 17-frame boundary is CUT to the window (its tokens line up with the target's); any
    other guide is kept only when it fits inside the window whole. An audio-only guide has no token grid, so it
    is cut anywhere (guide_audio_slice then says whether any of its sound reaches the window)."""
    f0, f1 = frames_of(l0), frames_of(l1)
    if clip_tokens <= 0:
        return None if frame_idx >= f1 else (0, 0, max(frame_idx, f0) - f0)
    span = frames_of(clip_tokens) if clip_tokens > 1 else 1
    if clip_tokens > 1 and frame_idx % CHUNK_FRAMES == 0:
        k0 = 5 * (frame_idx // CHUNK_FRAMES)
        a, b = max(k0, l0), min(k0 + clip_tokens, l1)
        if a >= b:
            return None
        return a - k0, b - k0, frames_of(a) - f0
    if f0 <= frame_idx and frame_idx + span <= f1:
        return 0, clip_tokens, frame_idx - f0
    return None


def guide_audio_slice(frame_idx, new_frame_idx, f0, audio_len, window_audio_len):
    """Audio frames [from, to) of a guide's soundtrack to keep in a window, given where place_guide put it.
    The soundtrack starts with the guide, so a guide cut at its front loses the same time from its audio."""
    skip = audio_at(f0 + new_frame_idx) - audio_at(frame_idx)
    room = window_audio_len - audio_at(new_frame_idx)
    a = max(0, skip)
    b = min(audio_len, a + max(0, room))
    return (a, b) if b > a else None


def is_track_ref(ref_audio_t, audio_t) -> bool:
    """A reference audio as long as the clip is the clip's own track (the song as <Audio 1>): it is cut to each
    window so every window hears the same part of the song it is singing."""
    try:
        return abs(int(ref_audio_t) - int(audio_t)) <= TRACK_REF_TOLERANCE
    except (TypeError, ValueError):
        return False
