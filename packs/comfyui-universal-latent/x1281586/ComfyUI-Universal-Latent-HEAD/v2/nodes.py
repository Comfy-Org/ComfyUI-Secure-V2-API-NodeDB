"""Secure Nodes V2 implementation of ComfyUI Universal Latent."""

from __future__ import annotations

from comfy_api.latest import ComfyExtension, io, sdk

MAX_RESOLUTION = 16_384
RESOLUTION_OPTIONS = [
    # Square
    "512x512 (1:1)",
    "576x576 (1:1)",
    "640x640 (1:1)",
    "704x704 (1:1)",
    "768x768 (1:1)",
    "832x832 (1:1)",
    "896x896 (1:1)",
    "960x960 (1:1)",
    "1024x1024 (1:1)",
    "1088x1088 (1:1)",
    "1152x1152 (1:1)",
    "1216x1216 (1:1)",
    "1280x1280 (1:1)",
    "1344x1344 (1:1)",
    "1408x1408 (1:1)",
    "1472x1472 (1:1)",
    "1536x1536 (1:1)",
    # Portrait
    "512x768 (2:3)",
    "576x864 (2:3)",
    "640x960 (2:3)",
    "704x1056 (2:3)",
    "768x1152 (2:3)",
    "832x1248 (2:3)",
    "896x1344 (2:3)",
    "960x1440 (2:3)",
    "1024x1536 (2:3)",
    # Landscape
    "768x512 (3:2)",
    "864x576 (3:2)",
    "960x640 (3:2)",
    "1056x704 (3:2)",
    "1152x768 (3:2)",
    "1248x832 (3:2)",
    "1344x896 (3:2)",
    "1440x960 (3:2)",
    "1536x1024 (3:2)",
    # Ultra portrait
    "512x1024 (1:2)",
    "576x1152 (1:2)",
    "640x1280 (1:2)",
    "704x1408 (1:2)",
    "768x1536 (1:2)",
    # Ultra landscape
    "1024x512 (2:1)",
    "1152x576 (2:1)",
    "1280x640 (2:1)",
    "1408x704 (2:1)",
    "1536x768 (2:1)",
    # Mobile/story
    "512x896 (4:7)",
    "576x1008 (4:7)",
    "640x1120 (4:7)",
    "704x1232 (4:7)",
    "768x1344 (4:7)",
    "832x1456 (4:7)",
    # Widescreen
    "1024x576 (16:9)",
    "1152x648 (16:9)",
    "1280x720 (16:9)",
    "1408x792 (16:9)",
    "1536x864 (16:9)",
    "1664x936 (16:9)",
    "1792x1008 (16:9)",
    "1920x1080 (16:9)",
    # Custom ratios
    "640x1536 (5:12)",
    "704x1408 (1:2)",
    "768x1280 (3:5)",
    "832x1216 (13:19)",
    "896x1152 (7:9)",
    "960x1024 (15:16)",
    "1152x896 (9:7)",
    "1216x832 (19:13)",
    "1280x768 (5:3)",
    "1344x704 (21:11)",
    "1408x640 (11:5)",
    "1536x576 (8:3)",
    "1600x512 (25:8)",
]
ASPECT_LOCK_OPTIONS = ["Unlocked", "Width", "Height"]
DOWNSAMPLE_OPTIONS = ["auto", 4, 8]
INVERT_OPTIONS = ["No", "Yes"]


def _bounded_int(name: str, value: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be in [{minimum}, {maximum}]")
    return value


def calculate_dimensions(
    resolution: str,
    width_override: int = 0,
    height_override: int = 0,
    aspect_ratio_lock: str = "Unlocked",
    downsample_factor: str | int = "auto",
    invert_ratios: str = "No",
) -> tuple[int, int, int]:
    """Return the exact represented pixel dimensions and latent ratio."""
    if not isinstance(resolution, str):
        raise TypeError("resolution must be a string")
    try:
        base_width, base_height = map(int, resolution.split(" ")[0].split("x"))
    except (ValueError, IndexError):
        raise ValueError(
            f"Invalid resolution format: {resolution}. "
            "Expected format: 'WIDTHxHEIGHT (RATIO)'"
        ) from None
    if base_width <= 0 or base_height <= 0:
        raise ValueError("resolution dimensions must be positive")

    width_override = _bounded_int("width_override", width_override, 0, MAX_RESOLUTION)
    height_override = _bounded_int(
        "height_override", height_override, 0, MAX_RESOLUTION
    )
    if aspect_ratio_lock not in ASPECT_LOCK_OPTIONS:
        raise ValueError("aspect_ratio_lock is not a supported option")
    if invert_ratios not in INVERT_OPTIONS:
        raise ValueError("invert_ratios is not a supported option")
    if downsample_factor == "auto":
        factor = 8
    elif downsample_factor in (4, 8, "4", "8"):
        factor = int(downsample_factor)
    else:
        raise ValueError("downsample_factor must be 'auto', 4, or 8")

    width, height = base_width, base_height
    if aspect_ratio_lock == "Width" and width_override > 0:
        width = min(width_override, MAX_RESOLUTION)
        height = max(64, round((base_height / base_width) * width))
    elif aspect_ratio_lock == "Height" and height_override > 0:
        height = min(height_override, MAX_RESOLUTION)
        width = max(64, round((base_width / base_height) * height))
    else:
        if width_override > 0:
            width = min(width_override, MAX_RESOLUTION)
        if height_override > 0:
            height = min(height_override, MAX_RESOLUTION)

    if invert_ratios == "Yes":
        width, height = height, width
    width = max(64, min(width, MAX_RESOLUTION))
    height = max(64, min(height, MAX_RESOLUTION))
    latent_width = (width + factor - 1) // factor
    latent_height = (height + factor - 1) // factor
    return latent_width * factor, latent_height * factor, factor


class UniversalLatent(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="UniversalLatent",
            display_name="🌌✨ Universal Latent (Enhanced) 🎨⚡",
            category="latent",
            inputs=[
                io.Combo.Input(
                    "resolution",
                    options=RESOLUTION_OPTIONS,
                    default="1024x1024 (1:1)",
                ),
                io.Int.Input("batch_size", default=1, min=1, max=4096),
                io.Int.Input(
                    "width_override",
                    default=0,
                    min=0,
                    max=MAX_RESOLUTION,
                    step=8,
                ),
                io.Int.Input(
                    "height_override",
                    default=0,
                    min=0,
                    max=MAX_RESOLUTION,
                    step=8,
                ),
                io.Combo.Input(
                    "aspect_ratio_lock",
                    options=ASPECT_LOCK_OPTIONS,
                    default="Unlocked",
                ),
                io.Int.Input(
                    "latent_channels",
                    default=4,
                    min=1,
                    max=16,
                    step=1,
                ),
                io.Combo.Input(
                    "downsample_factor",
                    options=DOWNSAMPLE_OPTIONS,
                    default="auto",
                ),
                io.Combo.Input(
                    "invert_ratios",
                    options=INVERT_OPTIONS,
                    default="No",
                ),
            ],
            outputs=[
                io.Latent.Output("LATENT", display_name="LATENT"),
                io.Int.Output("width", display_name="width"),
                io.Int.Output("height", display_name="height"),
            ],
        )

    @classmethod
    async def execute(
        cls,
        resolution: str,
        batch_size: int,
        width_override: int = 0,
        height_override: int = 0,
        aspect_ratio_lock: str = "Unlocked",
        latent_channels: int = 4,
        downsample_factor: str | int = "auto",
        invert_ratios: str = "No",
    ) -> io.NodeOutput:
        batch_size = _bounded_int("batch_size", batch_size, 1, 4096)
        latent_channels = _bounded_int("latent_channels", latent_channels, 1, 16)
        width, height, factor = calculate_dimensions(
            resolution=resolution,
            width_override=width_override,
            height_override=height_override,
            aspect_ratio_lock=aspect_ratio_lock,
            downsample_factor=downsample_factor,
            invert_ratios=invert_ratios,
        )
        latent = await sdk.LatentRef.empty(
            width=width,
            height=height,
            batch_size=batch_size,
            channels=latent_channels,
            spatial_downscale_ratio=factor,
        )
        return io.NodeOutput(latent, width, height)


NODE_CLASS_MAPPINGS = {"UniversalLatent": UniversalLatent}
NODE_DISPLAY_NAME_MAPPINGS = {
    "UniversalLatent": "🌌✨ Universal Latent (Enhanced) 🎨⚡",
}


class UniversalLatentExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [UniversalLatent]


async def comfy_entrypoint() -> UniversalLatentExtension:
    return UniversalLatentExtension()


__all__ = [
    "ASPECT_LOCK_OPTIONS",
    "DOWNSAMPLE_OPTIONS",
    "INVERT_OPTIONS",
    "MAX_RESOLUTION",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "RESOLUTION_OPTIONS",
    "UniversalLatent",
    "UniversalLatentExtension",
    "calculate_dimensions",
    "comfy_entrypoint",
]
