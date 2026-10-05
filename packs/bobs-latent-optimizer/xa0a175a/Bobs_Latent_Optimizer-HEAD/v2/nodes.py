"""Secure Nodes V2 implementation of Bobs Latent Optimizer."""

from __future__ import annotations

import logging
import math

import torch
from comfy_api.latest import ComfyExtension, io

logger = logging.getLogger(__name__)

MP_BASE_AREA = 1024 * 1024
MAX_TILE_DIM = 2048
MAX_DIMENSION = 16_384
MAX_LATENT_ELEMENTS = 268_435_456
MAX_ASPECT_RATIO_CHARACTERS = 128
TILE_ALIGN = 8

MODEL_SPECS = {
    "SD15": {"channels": 4, "vae_scale": 8, "align": 64, "temporal": 1, "dims": 2},
    "SD21": {"channels": 4, "vae_scale": 8, "align": 64, "temporal": 1, "dims": 2},
    "SDXL": {"channels": 4, "vae_scale": 8, "align": 64, "temporal": 1, "dims": 2},
    "PIXART": {"channels": 4, "vae_scale": 8, "align": 64, "temporal": 1, "dims": 2},
    "AURAFLOW": {"channels": 4, "vae_scale": 8, "align": 64, "temporal": 1, "dims": 2},
    "HUNYUAN_DIT": {
        "channels": 4,
        "vae_scale": 8,
        "align": 64,
        "temporal": 1,
        "dims": 2,
    },
    "SD3": {"channels": 16, "vae_scale": 8, "align": 64, "temporal": 1, "dims": 2},
    "FLUX": {"channels": 16, "vae_scale": 8, "align": 64, "temporal": 1, "dims": 2},
    "CHROMA": {"channels": 16, "vae_scale": 8, "align": 64, "temporal": 1, "dims": 2},
    "HIDREAM": {"channels": 16, "vae_scale": 8, "align": 64, "temporal": 1, "dims": 2},
    "LUMINA2": {"channels": 16, "vae_scale": 8, "align": 64, "temporal": 1, "dims": 2},
    "OMNIGEN2": {"channels": 16, "vae_scale": 8, "align": 64, "temporal": 1, "dims": 2},
    "QWEN": {"channels": 16, "vae_scale": 8, "align": 16, "temporal": 1, "dims": 2},
    "COSMOS_PREDICT2": {
        "channels": 16,
        "vae_scale": 8,
        "align": 16,
        "temporal": 1,
        "dims": 2,
    },
    "FLUX2": {"channels": 128, "vae_scale": 16, "align": 64, "temporal": 1, "dims": 2},
    "HUNYUAN_IMAGE": {
        "channels": 64,
        "vae_scale": 32,
        "align": 64,
        "temporal": 1,
        "dims": 2,
    },
    "CHROMA_RADIANCE": {
        "channels": 3,
        "vae_scale": 1,
        "align": 16,
        "temporal": 1,
        "dims": 2,
    },
    "HIDREAM_O1": {
        "channels": 3,
        "vae_scale": 1,
        "align": 16,
        "temporal": 1,
        "dims": 2,
    },
    "ZIMAGE_PIXEL": {
        "channels": 3,
        "vae_scale": 1,
        "align": 16,
        "temporal": 1,
        "dims": 2,
    },
    "PIXELDIT": {"channels": 3, "vae_scale": 1, "align": 16, "temporal": 1, "dims": 2},
    "WAN": {"channels": 16, "vae_scale": 8, "align": 16, "temporal": 4, "dims": 3},
    "WAN22": {"channels": 48, "vae_scale": 16, "align": 32, "temporal": 4, "dims": 3},
    "HUNYUAN_VIDEO": {
        "channels": 16,
        "vae_scale": 8,
        "align": 16,
        "temporal": 4,
        "dims": 3,
    },
    "HUNYUAN_VIDEO_15": {
        "channels": 32,
        "vae_scale": 16,
        "align": 32,
        "temporal": 4,
        "dims": 3,
    },
    "COSMOS": {"channels": 16, "vae_scale": 8, "align": 16, "temporal": 8, "dims": 3},
    "COGVIDEOX": {
        "channels": 16,
        "vae_scale": 8,
        "align": 16,
        "temporal": 4,
        "dims": 3,
    },
    "MOCHI": {"channels": 12, "vae_scale": 8, "align": 16, "temporal": 6, "dims": 3},
    "LTXV": {"channels": 128, "vae_scale": 32, "align": 32, "temporal": 8, "dims": 3},
    "SEEDVR2": {
        "channels": 16,
        "vae_scale": 8,
        "align": 16,
        "temporal": 1,
        "dims": 3,
        "starts_from_empty": False,
    },
    "HUNYUAN_IMAGE_REFINER": {
        "channels": 64,
        "vae_scale": 8,
        "align": 16,
        "temporal": 1,
        "dims": 3,
        "starts_from_empty": False,
    },
}

MODEL_TYPES = list(MODEL_SPECS)
VIDEO_MODEL_TYPES = [name for name, spec in MODEL_SPECS.items() if spec["dims"] == 3]

MP_SIZE_TO_AREA = {
    "0.25": 512 * 512,
    "0.5": 768 * 768,
    "1": 1024 * 1024,
    "1.25": 1280 * 1024,
    "1.5": 1440 * 1080,
    "1.75": 1664 * 1088,
    "2": 1920 * 1080,
    "2.5": 1536 * 1536,
    "3": 1792 * 1792,
    "4": 2048 * 2048,
}
MP_SIZES = list(MP_SIZE_TO_AREA)
_ASPECT_SEPARATORS = (":", "/", "x", "X")

OUTPUT_TOOLTIPS = (
    "Empty latent batch sized for the selected model.",
    "Suggested tile width for a tiled upscaler operating on the upscaled pixel output.",
    "Suggested tile height for a tiled upscaler operating on the upscaled pixel output.",
    "The upscale factor, passed through unchanged for convenience.",
    "Base image width in pixels.",
    "Base image height in pixels.",
)


def round_to_nearest_multiple(value, multiple):
    if multiple <= 0:
        return int(round(value))  # noqa: RUF046 - preserve the pristine helper.
    return int(round(value / multiple)) * multiple  # noqa: RUF046


def parse_aspect_ratio(aspect_ratio):
    if isinstance(aspect_ratio, bool):
        raise ValueError(  # noqa: TRY004 - bool is an invalid numeric value here.
            "Aspect ratio must be a positive number or ratio string."
        )
    if isinstance(aspect_ratio, (int, float)):
        parts = [str(aspect_ratio)]
    else:
        text = str(aspect_ratio).strip()
        if not text:
            raise ValueError(
                "Aspect ratio is empty. Use a format like '1:1' or '16:9'."
            )
        if len(text) > MAX_ASPECT_RATIO_CHARACTERS:
            raise ValueError("Aspect ratio exceeds the character limit.")
        parts = [text]
        for separator in _ASPECT_SEPARATORS:
            if separator in text:
                parts = text.split(separator)
                break

    try:
        numbers = [float(part.strip()) for part in parts]
    except ValueError as error:
        raise ValueError(
            f"Invalid aspect ratio: {aspect_ratio!r}. Use 'width:height' with numeric "
            "components, for example '1:1', '16:9' or '3:2'."
        ) from error

    if len(numbers) == 1:
        ratio = numbers[0]
    elif len(numbers) == 2:
        width, height = numbers
        if height == 0:
            raise ValueError(
                f"Invalid aspect ratio: {aspect_ratio!r}. The height component cannot be zero."
            )
        ratio = width / height
    else:
        raise ValueError(
            f"Invalid aspect ratio: {aspect_ratio!r}. Expected two components, got {len(numbers)}."
        )

    if not math.isfinite(ratio) or ratio <= 0:
        raise ValueError(
            f"Invalid aspect ratio: {aspect_ratio!r}. The ratio must be a positive number."
        )
    return ratio


def compute_base_dimensions(
    target_area, aspect_ratio_multiplier, align, max_dim=MAX_DIMENSION
):
    if target_area <= 0:
        raise ValueError(f"Target area must be positive, got {target_area}.")
    if align <= 0:
        raise ValueError(f"Alignment must be positive, got {align}.")

    ceiling = (int(max_dim) // align) * align
    if ceiling < align:
        raise ValueError(
            f"max_dim ({max_dim}) is smaller than one alignment step ({align})."
        )

    width = math.sqrt(target_area * aspect_ratio_multiplier)
    height = width / aspect_ratio_multiplier
    overshoot = max(width / ceiling, height / ceiling, 1.0)
    if overshoot > 1.0:
        logger.warning(
            "Bobs Latent Optimizer: %.0fx%.0f px exceeds the %d px limit; scaling down "
            "by %.2fx. The latent will be smaller than the megapixel target you asked for.",
            width,
            height,
            ceiling,
            overshoot,
        )
        width /= overshoot
        height /= overshoot

    aligned_width = round_to_nearest_multiple(width, align)
    aligned_height = round_to_nearest_multiple(height, align)
    if aligned_width < align or aligned_height < align:
        logger.warning(
            "Bobs Latent Optimizer: %dx%d px is below the %d px minimum for this model; "
            "raising it. The aspect ratio will not match what you asked for.",
            aligned_width,
            aligned_height,
            align,
        )
    return (
        min(ceiling, max(align, aligned_width)),
        min(ceiling, max(align, aligned_height)),
    )


def compute_latent_frames(length, temporal):
    length = max(1, int(length))
    if temporal <= 1:
        return length
    return ((length - 1) // temporal) + 1


def compute_tile_dimensions(width, height, upscale_by, max_tile_dim=MAX_TILE_DIM):
    upscaled_width = max(1, int(width * upscale_by))
    upscaled_height = max(1, int(height * upscale_by))
    max_tile_dim = max(TILE_ALIGN, int(max_tile_dim))

    def axis_tiles(total):
        tiles = 2
        if -(-total // tiles) > max_tile_dim:
            tiles = -(-total // max_tile_dim)
        return max(1, tiles)

    tiles_x = axis_tiles(upscaled_width)
    tiles_y = axis_tiles(upscaled_height)

    def tile_size(total, tiles):
        size = -(-total // tiles)
        size = -(-size // TILE_ALIGN) * TILE_ALIGN
        return max(TILE_ALIGN, min(size, total))

    return (
        tile_size(upscaled_width, tiles_x),
        tile_size(upscaled_height, tiles_y),
        tiles_x,
        tiles_y,
    )


def _bounded_int(name: str, value: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be in [{minimum}, {maximum}]")
    return value


def _bounded_float(name: str, value: float, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    value = float(value)
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be finite and in [{minimum}, {maximum}]")
    return value


def build_latent(
    aspect_ratio,
    target_area,
    upscale_by,
    model_type,
    batch_size,
    max_tile_size,
    length,
):
    spec = MODEL_SPECS.get(model_type)
    if spec is None:
        raise ValueError(
            f"Unknown model_type {model_type!r}. Expected one of {', '.join(MODEL_TYPES)}."
        )
    upscale_by = _bounded_float("upscale_by", upscale_by, 1.0, 10.0)
    batch_size = _bounded_int("batch_size", batch_size, 1, 64)
    max_tile_size = _bounded_int("max_tile_size", max_tile_size, 256, 8192)
    length = _bounded_int("length", length, 1, 4096)

    if not spec.get("starts_from_empty", True):
        logger.warning(
            "Bobs Latent Optimizer: %s is not normally driven from an empty latent - it "
            "consumes an existing image or latent. This gives you a correctly shaped zero "
            "tensor, but it is probably not the input that model wants.",
            model_type,
        )

    ratio = parse_aspect_ratio(aspect_ratio)
    width, height = compute_base_dimensions(target_area, ratio, spec["align"])
    latent_width = width // spec["vae_scale"]
    latent_height = height // spec["vae_scale"]
    channels = spec["channels"]

    if spec["dims"] == 3:
        frames = compute_latent_frames(length, spec["temporal"])
        shape = [batch_size, channels, frames, latent_height, latent_width]
    else:
        if length > 1:
            logger.warning(
                "Bobs Latent Optimizer: length=%d ignored - %s is an image model and "
                "produces a 4-D latent. Pick a video model (%s) to use length.",
                length,
                model_type,
                ", ".join(VIDEO_MODEL_TYPES),
            )
        shape = [batch_size, channels, latent_height, latent_width]

    elements = math.prod(shape)
    if elements > MAX_LATENT_ELEMENTS:
        raise ValueError(
            f"LATENT shape {shape} exceeds the {MAX_LATENT_ELEMENTS}-element limit"
        )
    try:
        samples = torch.zeros(shape, device="cpu")
    except Exception as error:
        raise RuntimeError(
            f"Could not allocate latent of shape {shape} for {model_type}: {error}"
        ) from error

    tile_width, tile_height, _, _ = compute_tile_dimensions(
        width, height, upscale_by, max_tile_size
    )
    return {"samples": samples}, tile_width, tile_height, upscale_by, width, height


def _shared_inputs() -> list[io.Input]:
    model_tooltip = (
        "Model family. Sets latent channels, VAE downscale and pixel alignment. "
        f"Video families ({', '.join(VIDEO_MODEL_TYPES)}) produce a 5-D latent and "
        "use the `length` input. See the README for the full table."
    )
    return [
        io.Float.Input(
            "upscale_by",
            default=2.0,
            min=1.0,
            max=10.0,
            step=0.01,
            tooltip=(
                "Upscale factor for the FINAL output image. Used only to compute the "
                "tile dimensions; the generated latent is NOT upscaled."
            ),
        ),
        io.Combo.Input(
            "model_type", options=MODEL_TYPES, default="FLUX", tooltip=model_tooltip
        ),
        io.Int.Input(
            "batch_size",
            default=1,
            min=1,
            max=64,
            step=1,
            tooltip="Number of latents in the batch.",
        ),
    ]


def _optional_inputs() -> list[io.Input]:
    return [
        io.Int.Input(
            "max_tile_size",
            default=MAX_TILE_DIM,
            min=256,
            max=8192,
            step=64,
            optional=True,
            tooltip=(
                "Largest tile edge allowed before the tile grid is subdivided further. "
                "Lower this if your upscaler runs out of VRAM."
            ),
        ),
        io.Int.Input(
            "length",
            default=1,
            min=1,
            max=4096,
            step=1,
            optional=True,
            tooltip=(
                "Number of video frames. Only used by video model families; ignored "
                "(with a warning) for image models."
            ),
        ),
    ]


def _outputs() -> list[io.Output]:
    return [
        io.Latent.Output("latent", tooltip=OUTPUT_TOOLTIPS[0]),
        io.Int.Output("tile_width", tooltip=OUTPUT_TOOLTIPS[1]),
        io.Int.Output("tile_height", tooltip=OUTPUT_TOOLTIPS[2]),
        io.Float.Output("upscale_by", tooltip=OUTPUT_TOOLTIPS[3]),
        io.Int.Output("width", tooltip=OUTPUT_TOOLTIPS[4]),
        io.Int.Output("height", tooltip=OUTPUT_TOOLTIPS[5]),
    ]


class BobsLatentNode(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="BobsLatentNode",
            display_name="Bobs Latent Optimizer",
            category="latent/generate",
            description=(
                "Empty latent sized for a wide range of image and video model families "
                "from an aspect ratio and a preset megapixel area, plus suggested tile "
                "dimensions for tiled upscaling."
            ),
            inputs=[
                io.String.Input(
                    "aspect_ratio",
                    default="1:1",
                    tooltip="Aspect ratio of the base image, e.g. '1:1', '16:9', '3:2'.",
                ),
                io.Combo.Input(
                    "mp_size",
                    options=MP_SIZES,
                    default="1",
                    tooltip=(
                        "Approximate megapixel area of the base image. Values map to "
                        "common standard resolution areas (1 = 1024x1024, 4 = 2048x2048)."
                    ),
                ),
                *_shared_inputs(),
                *_optional_inputs(),
            ],
            outputs=_outputs(),
        )

    @classmethod
    def execute(
        cls,
        aspect_ratio: str,
        mp_size: str,
        upscale_by: float,
        model_type: str,
        batch_size: int,
        max_tile_size: int = MAX_TILE_DIM,
        length: int = 1,
    ) -> io.NodeOutput:
        target_area = MP_SIZE_TO_AREA.get(mp_size)
        if target_area is None:
            raise ValueError(
                f"Unknown mp_size {mp_size!r}. Expected one of {', '.join(MP_SIZES)}."
            )
        return io.NodeOutput(
            *build_latent(
                aspect_ratio,
                target_area,
                upscale_by,
                model_type,
                batch_size,
                max_tile_size,
                length,
            )
        )


class BobsLatentNodeAdvanced(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="BobsLatentNodeAdvanced",
            display_name="Bobs Latent Optimizer (Advanced)",
            category="latent/generate",
            description=(
                "Empty latent sized for a wide range of image and video model families "
                "from an aspect ratio and a continuous megapixel target, plus suggested "
                "tile dimensions for tiled upscaling."
            ),
            inputs=[
                io.String.Input(
                    "aspect_ratio",
                    default="1:1",
                    tooltip="Aspect ratio of the base image, e.g. '1:1', '16:9', '3:2'.",
                ),
                io.Float.Input(
                    "mp_size_float",
                    default=1.0,
                    min=0.01,
                    max=16.0,
                    step=0.01,
                    display_mode=io.NumberDisplay.number,
                    tooltip=(
                        f"Target area in megapixels, where 1.0 = {MP_BASE_AREA} pixels "
                        "(1024x1024). 4.0 is a 2048x2048 area."
                    ),
                ),
                *_shared_inputs(),
                *_optional_inputs(),
            ],
            outputs=_outputs(),
        )

    @classmethod
    def execute(
        cls,
        aspect_ratio: str,
        mp_size_float: float,
        upscale_by: float,
        model_type: str,
        batch_size: int,
        max_tile_size: int = MAX_TILE_DIM,
        length: int = 1,
    ) -> io.NodeOutput:
        mp_size_float = _bounded_float("mp_size_float", mp_size_float, 0.01, 16.0)
        return io.NodeOutput(
            *build_latent(
                aspect_ratio,
                mp_size_float * MP_BASE_AREA,
                upscale_by,
                model_type,
                batch_size,
                max_tile_size,
                length,
            )
        )


NODE_CLASS_MAPPINGS = {
    "BobsLatentNode": BobsLatentNode,
    "BobsLatentNodeAdvanced": BobsLatentNodeAdvanced,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "BobsLatentNode": "Bobs Latent Optimizer",
    "BobsLatentNodeAdvanced": "Bobs Latent Optimizer (Advanced)",
}


class BobsLatentOptimizerExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [BobsLatentNode, BobsLatentNodeAdvanced]


async def comfy_entrypoint() -> BobsLatentOptimizerExtension:
    return BobsLatentOptimizerExtension()


__all__ = [
    "MAX_ASPECT_RATIO_CHARACTERS",
    "MAX_DIMENSION",
    "MAX_LATENT_ELEMENTS",
    "MAX_TILE_DIM",
    "MODEL_SPECS",
    "MODEL_TYPES",
    "MP_BASE_AREA",
    "MP_SIZES",
    "MP_SIZE_TO_AREA",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "OUTPUT_TOOLTIPS",
    "TILE_ALIGN",
    "VIDEO_MODEL_TYPES",
    "BobsLatentNode",
    "BobsLatentNodeAdvanced",
    "BobsLatentOptimizerExtension",
    "build_latent",
    "comfy_entrypoint",
    "compute_base_dimensions",
    "compute_latent_frames",
    "compute_tile_dimensions",
    "parse_aspect_ratio",
    "round_to_nearest_multiple",
]
