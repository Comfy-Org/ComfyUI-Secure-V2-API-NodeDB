"""Pure maths for H3 Audio Sync Pixaroma.

No torch, no ComfyUI - so the arithmetic can be checked in isolation
(harness: D:\\Claude Tests\\_h3_sync_test.py).

THE NUMBERS, read out of ComfyUI's own comfy_extras/nodes_minimax_h3.py rather
than remembered, because getting any of them wrong produces a clip that is
subtly out of step rather than an error:

  FPS               24    video frames per second
  AUDIO_LATENT_FPS  40    audio latent frames per second
  frame grid        17n+5 the only frame counts the model accepts
  video latent T    2 if frames <= 5 else ((frames - 5) // 17) * 5 + 2
  audio latent T    round(frames / FPS * AUDIO_LATENT_FPS)

The trained range is 124 to 362 frames, i.e. about 5.2s to 15.1s. Past that the
model is untested and in practice falls apart, which is what LIMIT_DEFAULT_S
exists to catch before somebody spends a render finding out.
"""
from __future__ import annotations

FPS = 24
AUDIO_LATENT_FPS = 40
FRAME_STEP = 17
FRAME_PLUS = 5
TRAINED_MAX_FRAMES = 362
LIMIT_DEFAULT_S = 15.0


def frames_from_latent_t(latent_t) -> int:
    """Invert the video latent's time dimension back to a frame count.

    ((frames - 5) // 17) * 5 + 2 is the forward direction, so k = (t - 2) // 5
    and frames = k * 17 + 5. Exact for every value the forward function can
    produce, which is the only kind we are ever handed.
    """
    try:
        t = int(latent_t)
    except (TypeError, ValueError):
        return FRAME_PLUS
    if t <= 2:
        return FRAME_PLUS
    k = (t - 2) // 5
    return k * FRAME_STEP + FRAME_PLUS


def clip_info(video_latent_t, audio_latent_t) -> dict:
    """What the latent we were handed actually represents."""
    frames = frames_from_latent_t(video_latent_t)
    try:
        audio_t = max(0, int(audio_latent_t or 0))
    except (TypeError, ValueError):
        audio_t = 0
    return {
        "frames": frames,
        "seconds": frames / FPS,
        "audio_t": audio_t,
        # What the audio stream itself spans. It differs from `seconds` by up to
        # half an audio-latent frame (1/80 s) because the forward direction
        # rounds; the audio side is the one we must match sample for sample.
        "audio_seconds": (audio_t / AUDIO_LATENT_FPS) if audio_t else 0.0,
    }


def target_samples(audio_latent_t, vae_sample_rate) -> int:
    """How many waveform samples correspond to `audio_latent_t` latent frames.

    Fitting in the WAVEFORM domain and then encoding is deliberate. Padding an
    audio LATENT with zeros does not produce silence - zero is just another
    point in latent space and decodes to a tone or noise - and because the
    stream is then frozen, the model paints video against that noise. Padding
    real samples with real zeros is actual silence.
    """
    try:
        t = max(0, int(audio_latent_t or 0))
        sr = max(0, int(vae_sample_rate or 0))
    except (TypeError, ValueError):
        return 0
    return int(round(t / AUDIO_LATENT_FPS * sr))


def over_limit(clip_seconds, limit_seconds) -> bool:
    """Is this clip longer than the user's guard? A limit of 0 disables it."""
    try:
        limit = float(limit_seconds)
        clip = float(clip_seconds)
    except (TypeError, ValueError):
        return False
    if limit <= 0:
        return False
    # A hair of tolerance, or 15.08s (the top legal length) trips a 15s guard
    # every time and the warning becomes noise people learn to ignore.
    return clip > limit + 0.25


def status(clip, track_seconds, limit_seconds, when_short="silence") -> dict:
    """The one place the readout wording is decided.

    Python owns this rather than the browser because only Python can see inside
    the latent. The face just prints what comes back, so the two can never drift
    apart into saying different things about the same run.
    """
    clip_s = float(clip.get("seconds", 0.0))
    frames = int(clip.get("frames", 0))
    try:
        track_s = max(0.0, float(track_seconds or 0.0))
    except (TypeError, ValueError):
        track_s = 0.0

    head = "Clip {:.2f}s \u00b7 {} frames".format(clip_s, frames)

    if over_limit(clip_s, limit_seconds):
        return {
            "level": "over",
            "head": "Clip {:.2f}s".format(clip_s),
            "detail": "past your {:.0f}s limit, shorten the latent".format(float(limit_seconds)),
        }

    gap = clip_s - track_s
    if track_s <= 0:
        return {"level": "warn", "head": head, "detail": "no track, nothing to lock"}
    if gap > 0.02:
        filled = "looping the track" if when_short == "loop" else "filling with silence"
        return {
            "level": "warn",
            "head": "{} \u00b7 track {:.2f}s".format(head, track_s),
            "detail": "{:.2f}s short, {}".format(gap, filled),
        }
    return {"level": "ok", "head": head, "detail": "track matches, locked"}
