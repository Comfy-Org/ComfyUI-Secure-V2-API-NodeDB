from comfy_api.latest import io, sdk

from .presets import PRESETS

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
    if isinstance(v, bool) or not isinstance(v, int):
        raise TypeError("Dimension must be an integer")
    if v <= 0 or v % stride != 0:
        raise ValueError(f"Dimension must be >0 and divisible by {stride}")


async def _empty_latent(batch_size: int, channels: int, stride: int, w: int, h: int):
    if isinstance(batch_size, bool) or not isinstance(batch_size, int):
        raise TypeError("batch_size must be an integer")
    return await sdk.LatentRef.empty(
        width=w, height=h, batch_size=batch_size, channels=channels,
        spatial_downscale_ratio=stride,
    )


class EmptyLatentAspectPreset(io.ComfyNode):
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

    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="CAS Empty Latent Aspect Ratio Preset", category="latent",
            inputs=[io.Combo.Input("model", options=cls.MODELS),
                    io.Combo.Input("preset", options=list(cls.PRESET_MAP)),
                    io.Int.Input("batch_size", default=1, min=1)],
            outputs=[io.Latent.Output(display_name="LATENT"),
                     io.Int.Output(display_name="width"),
                     io.Int.Output(display_name="height")],
        )

    @classmethod
    async def execute(cls, model: str, preset: str, batch_size: int):
        if preset not in cls.PRESET_MAP:
            raise ValueError(f"Unknown preset: {preset}")
        w, h = cls.PRESET_MAP[preset]

        channels, stride = MODEL_LATENT_SPEC.get(model, DEFAULT_LATENT_SPEC)
        _validate_dim(w, stride)
        _validate_dim(h, stride)

        return io.NodeOutput(await _empty_latent(batch_size, channels, stride, w, h), w, h)


class EmptyLatentAspectByAxis(io.ComfyNode):
    """Creates a blank latent by fixing one axis and computing the other from an aspect ratio."""

    ASPECT_CHOICES = ASPECT_RATIOS
    REFERENCE_CHOICES = ["Width", "Height"]
    RATIO_MAP = dict(ASPECT_CHOICES)
    MODELS = MODELS

    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="CAS Empty Latent Aspect Ratio Axis", category="latent",
            inputs=[io.Int.Input("primary_dim", default=512, min=8),
                    io.Combo.Input("reference", options=cls.REFERENCE_CHOICES),
                    io.Combo.Input("aspect_ratio", options=[label for label, _ in cls.ASPECT_CHOICES]),
                    io.Int.Input("batch_size", default=1, min=1),
                    io.Combo.Input("model", options=cls.MODELS)],
            outputs=[io.Latent.Output(display_name="LATENT"),
                     io.Int.Output(display_name="width"),
                     io.Int.Output(display_name="height")],
        )

    @classmethod
    async def execute(cls, primary_dim: int, reference: str, aspect_ratio: str, batch_size: int, model: str):
        if aspect_ratio not in cls.RATIO_MAP:
            raise ValueError(f"Unknown aspect ratio: {aspect_ratio}")
        wr, hr = cls.RATIO_MAP[aspect_ratio]

        channels, stride = MODEL_LATENT_SPEC.get(model, DEFAULT_LATENT_SPEC)

        _validate_dim(primary_dim, stride)
        if reference == "Width":
            w, h = primary_dim, round(primary_dim * hr / wr)
        else:
            h, w = primary_dim, round(primary_dim * wr / hr)

        _validate_dim(w, stride)
        _validate_dim(h, stride)

        return io.NodeOutput(await _empty_latent(batch_size, channels, stride, w, h), w, h)
