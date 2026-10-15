import torch

from .presets import PRESETS

try:
    # Same device ComfyUI's own EmptyLatentImage/EmptySD3LatentImage create latents on.
    # A CPU-resident latent forces per-step CPU<->GPU transfers during sampling.
    import comfy.model_management as _model_management
    _LATENT_DEVICE = _model_management.intermediate_device()
except ImportError:  # allows importing this module outside a running ComfyUI (e.g. sanity checks)
    _LATENT_DEVICE = "cpu"

# Per-model (channels, spatial_stride) latent spec, matching each model's native
# ComfyUI empty-latent node. SD1.5/SDXL/Flux.1/Krea/Qwen-Image all use an 8x-downsampled
# VAE (4ch legacy or 16ch SD3-family); Flux.2 is the outlier — comfy_extras/nodes_flux.py's
# EmptyFlux2LatentImage uses 128 channels at 16x downsample. Getting either value wrong
# silently produces a latent of the wrong shape (e.g. 2x the intended resolution per axis).
MODEL_LATENT_SPEC = {
    "SD15":       (4, 8),
    "SDXL":       (4, 8),
    "Flux.1":     (16, 8),
    "Flux.2":     (128, 16),
    "Krea":       (16, 8),
    "Qwen-Image": (16, 8),
}
DEFAULT_LATENT_SPEC = (4, 8)

# Unique models in presets.py order (most relevant first, per its own convention) — both
# nodes default to whichever model is listed first there, so adding a new architecture at
# the top of presets.py automatically becomes the new default without touching this file.
MODELS = list(dict.fromkeys(model for model, _, _, _ in PRESETS))

ASPECT_RATIOS = [
    ("1:1 Square",      (1, 1)),
    ("3:2 Landscape",   (3, 2)),
    ("2:3 Portrait",    (2, 3)),
    ("4:3 Landscape",   (4, 3)),
    ("3:4 Portrait",    (3, 4)),
    ("16:9 Landscape",  (16, 9)),
    ("9:16 Portrait",   (9, 16)),
    ("5:4 Landscape",   (5, 4)),
    ("4:5 Portrait",    (4, 5)),
    ("21:9 Widescreen", (21, 9)),
    ("9:21 Portrait",   (9, 21)),
    ("7:5 Landscape",   (7, 5)),
    ("5:7 Portrait",    (5, 7)),
]


def _validate_dim(v: int, stride: int = 8):
    if v <= 0 or v % stride != 0:
        raise ValueError(f"Dimension must be >0 and divisible by {stride}")


def _empty_latent(batch_size: int, channels: int, stride: int, w: int, h: int):
    return {"samples": torch.zeros(
        [batch_size, channels, h // stride, w // stride],
        dtype=torch.float32,
        device=_LATENT_DEVICE,
    )}


class EmptyLatentAspectPreset:
    """Creates a blank latent using one of the predefined presets."""

    # Built once at import time and shared by all instances/calls.
    PRESET_MAP = {
        f"{w}x{h} - {lbl} - {model}": (w, h)
        for model, lbl, w, h in PRESETS
    }
    # The "model" widget is purely a client-side filter (see web/aspect_ratio_filter.js)
    # for the "preset" dropdown, which already encodes the model in its label — parsed
    # there, not duplicated.
    MODELS = MODELS

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model":      (cls.MODELS,),
                "preset":     (list(cls.PRESET_MAP.keys()),),
                "batch_size": ("INT", {"default": 1, "min": 1}),
            }
        }

    RETURN_TYPES = ("LATENT", "INT", "INT")
    RETURN_NAMES = ("LATENT", "width", "height")
    FUNCTION = "generate"
    CATEGORY = "latent"

    def generate(self, model: str, preset: str, batch_size: int):
        if preset not in self.PRESET_MAP:
            raise ValueError(f"Unknown preset: {preset}")
        w, h = self.PRESET_MAP[preset]

        channels, stride = MODEL_LATENT_SPEC.get(model, DEFAULT_LATENT_SPEC)
        _validate_dim(w, stride)
        _validate_dim(h, stride)

        return (_empty_latent(batch_size, channels, stride, w, h), w, h)


class EmptyLatentAspectByAxis:
    """Creates a blank latent by fixing one axis and computing the other from an aspect ratio."""

    ASPECT_CHOICES = ASPECT_RATIOS
    REFERENCE_CHOICES = ["Width", "Height"]
    RATIO_MAP = dict(ASPECT_CHOICES)
    MODELS = MODELS

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "primary_dim":  ("INT", {"default": 512, "min": 8}),
                "reference":    (cls.REFERENCE_CHOICES,),
                "aspect_ratio": ([lbl for lbl, _ in cls.ASPECT_CHOICES],),
                "batch_size":   ("INT", {"default": 1, "min": 1}),
                "model":        (cls.MODELS,),
            }
        }

    RETURN_TYPES = ("LATENT", "INT", "INT")
    RETURN_NAMES = ("LATENT", "width", "height")
    FUNCTION = "generate"
    CATEGORY = "latent"

    def generate(self, primary_dim: int, reference: str, aspect_ratio: str, batch_size: int, model: str):
        if aspect_ratio not in self.RATIO_MAP:
            raise ValueError(f"Unknown aspect ratio: {aspect_ratio}")
        wr, hr = self.RATIO_MAP[aspect_ratio]

        channels, stride = MODEL_LATENT_SPEC.get(model, DEFAULT_LATENT_SPEC)

        _validate_dim(primary_dim, stride)
        if reference == "Width":
            w, h = primary_dim, round(primary_dim * hr / wr)
        else:
            h, w = primary_dim, round(primary_dim * wr / hr)

        _validate_dim(w, stride)
        _validate_dim(h, stride)

        return (_empty_latent(batch_size, channels, stride, w, h), w, h)
