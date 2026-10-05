from comfy_api.latest import ComfyExtension, io, sdk


# Model-specific resolution presets with constraints
# Includes: model-optimized sizes + photo print (4x6, 5x7, 8x10) + digital/social + canvas art ratios
MODEL_RESOLUTIONS = {
    "Flux": {
        "square": [(512, 512), (768, 768), (1024, 1024), (1088, 1088), (1280, 1280), (1328, 1328), (1536, 1536), (1920, 1920), (2048, 2048)],
        "portrait": [(688, 2048), (768, 1344), (832, 1216), (896, 1152), (928, 1664), (1024, 1536), (1024, 1792), (1024, 2048), (1056, 1584), (1088, 1920), (1104, 1472), (1152, 2048), (1200, 1792), (1360, 2048), (1456, 2048), (1536, 2048), (1616, 2048), (1632, 2048), (1712, 2048)],
        "landscape": [(1280, 720), (1344, 768), (1216, 832), (1152, 896), (1472, 1104), (1536, 1024), (1584, 1056), (1664, 928), (1792, 1024), (1792, 1200), (1920, 1088), (2048, 688), (2048, 1024), (2048, 1152), (2048, 1360), (2048, 1456), (2048, 1536), (2048, 1616), (2048, 1632), (2048, 1712)],
        "constraints": {"divisible_by": 16, "min": 256, "max": 2048, "latent_channels": 16}
    },
    "Qwen Image": {
        "square": [(1024, 1024), (1080, 1080), (1280, 1280), (1328, 1328), (1536, 1536), (1920, 1920), (2048, 2048)],
        "portrait": [(680, 2048), (928, 1664), (1024, 1536), (1024, 2048), (1056, 1584), (1080, 1920), (1104, 1472), (1152, 2048), (1200, 1800), (1368, 2048), (1464, 2048), (1536, 2048), (1608, 2048), (1640, 2048), (1704, 2048)],
        "landscape": [(1280, 720), (1472, 1104), (1536, 1024), (1584, 1056), (1664, 928), (1800, 1200), (1920, 1080), (2048, 680), (2048, 1024), (2048, 1152), (2048, 1368), (2048, 1464), (2048, 1536), (2048, 1608), (2048, 1640), (2048, 1704)],
        "constraints": {"divisible_by": 8, "min": 256, "max": 2048, "latent_channels": 16}
    },
    "Z-Image": {
        "square": [(512, 512), (768, 768), (1024, 1024), (1080, 1080), (1280, 1280), (1328, 1328), (1536, 1536), (1920, 1920), (2048, 2048)],
        "portrait": [(680, 2048), (720, 1280), (768, 1024), (928, 1664), (1024, 2048), (1056, 1584), (1080, 1920), (1104, 1472), (1152, 2048), (1200, 1800), (1368, 2048), (1464, 2048), (1536, 2048), (1608, 2048), (1640, 2048), (1704, 2048)],
        "landscape": [(1024, 768), (1280, 720), (1472, 1104), (1584, 1056), (1664, 928), (1800, 1200), (1920, 1080), (2048, 680), (2048, 1024), (2048, 1152), (2048, 1368), (2048, 1464), (2048, 1536), (2048, 1608), (2048, 1640), (2048, 1704)],
        "constraints": {"divisible_by": 8, "min": 256, "max": 2048, "latent_channels": 16}
    },
    "SD 1.5": {
        "square": [(512, 512), (768, 768), (1024, 1024), (1080, 1080), (1280, 1280), (1536, 1536)],
        "portrait": [(512, 768), (512, 680), (512, 1024), (680, 2048), (768, 1024), (768, 1344), (1024, 2048), (1080, 1920), (1200, 1800), (1368, 2048), (1464, 2048), (1536, 2048), (1608, 2048), (1640, 2048), (1704, 2048)],
        "landscape": [(768, 512), (1024, 512), (1024, 768), (1280, 720), (1344, 768), (1536, 512), (1800, 1200), (1920, 1080), (2048, 680), (2048, 1024), (2048, 1368), (2048, 1464), (2048, 1536), (2048, 1608), (2048, 1640), (2048, 1704)],
        "constraints": {"divisible_by": 8, "min": 256, "max": 2048, "latent_channels": 4}
    },
    "SDXL": {
        "square": [(1024, 1024), (1080, 1080), (1280, 1280), (1536, 1536), (1920, 1920), (2048, 2048)],
        "portrait": [(640, 1536), (680, 2048), (768, 1344), (832, 1216), (896, 1152), (1024, 1536), (1024, 2048), (1080, 1920), (1152, 2048), (1200, 1800), (1368, 2048), (1464, 2048), (1536, 2048), (1608, 2048), (1640, 2048), (1704, 2048)],
        "landscape": [(1152, 896), (1216, 832), (1280, 720), (1344, 768), (1536, 640), (1536, 1024), (1800, 1200), (1920, 1080), (2048, 680), (2048, 1024), (2048, 1152), (2048, 1368), (2048, 1464), (2048, 1536), (2048, 1608), (2048, 1640), (2048, 1704)],
        "constraints": {"divisible_by": 8, "min": 256, "max": 2048, "latent_channels": 4}
    }
}


def calculate_aspect_ratio(width, height):
    """
    Calculate simplified aspect ratio from dimensions, using nearest common ratio.

    Args:
        width (int): Width in pixels
        height (int): Height in pixels

    Returns:
        str: Aspect ratio like "16:9" or "1:1"
    """
    # Calculate actual ratio as decimal
    actual_ratio = width / height

    # Common aspect ratios (ratio_value, "width:height" string)
    common_ratios = [
        (1.0, "1:1"),      # Square
        (1.25, "5:4"),     # 1.25
        (1.33, "4:3"),     # 1.333...
        (1.5, "3:2"),      # 1.5
        (1.6, "16:10"),    # 1.6
        (1.78, "16:9"),    # 1.777...
        (2.0, "2:1"),      # 2.0
        (2.35, "21:9"),    # 2.333... (ultrawide)
        (2.4, "12:5"),     # 2.4
        (3.0, "3:1"),      # 3.0
        # Portrait ratios
        (0.75, "3:4"),     # 0.75
        (0.67, "2:3"),     # 0.666...
        (0.625, "5:8"),    # 0.625
        (0.56, "9:16"),    # 0.5625
        (0.5, "1:2"),      # 0.5
        (0.42, "5:12"),    # 0.4166...
        (0.33, "1:3"),     # 0.333... (panoramic)
    ]

    # Find closest common ratio by absolute difference
    closest_ratio = min(common_ratios, key=lambda r: abs(actual_ratio - r[0]))
    return closest_ratio[1]


def format_resolution(width, height):
    """
    Format resolution tuple into display string with aspect ratio and orientation.
    Uses fixed-width formatting for better alignment in dropdowns.

    Args:
        width (int): Width in pixels
        height (int): Height in pixels

    Returns:
        str: Formatted string like "1920x1080  (16:9 Landscape)" with consistent spacing
    """
    aspect_ratio = calculate_aspect_ratio(width, height)

    if width == height:
        orientation = "Square"
    elif width < height:
        orientation = "Portrait"
    else:
        orientation = "Landscape"

    # Format with fixed width for better alignment (e.g., "1920x1080  ")
    # Most resolutions are 4 digits, so we pad to 9 characters (4x4 + 'x')
    resolution_str = f"{width}x{height}"
    padded_resolution = resolution_str.ljust(13)  # Pad to 13 chars for alignment

    return f"{padded_resolution}({aspect_ratio} {orientation})"


def get_resolution_list(model_name):
    """
    Generate ordered list of resolution strings for a specific model.

    Args:
        model_name (str): Name of the model (or "All" for all unique resolutions)

    Returns:
        list: Formatted resolution strings in order: square, portrait, landscape
    """
    if model_name == "All":
        return get_all_resolutions()

    if model_name not in MODEL_RESOLUTIONS:
        return []

    model_data = MODEL_RESOLUTIONS[model_name]
    resolutions = []

    # Order: square first, then portrait, then landscape
    for category in ["square", "portrait", "landscape"]:
        for width, height in model_data[category]:
            resolutions.append(format_resolution(width, height))

    return resolutions


def get_default_resolution(model_name):
    """
    Get the default/native resolution for a specific model.

    Args:
        model_name (str): Name of the model

    Returns:
        str: Formatted resolution string for the model's native resolution
    """
    # Model-specific native/optimal resolutions
    default_resolutions = {
        "Flux": (1024, 1024),      # Flux native
        "Qwen Image": (1328, 1328), # Qwen native
        "Z-Image": (1024, 1024),    # Z-Image native
        "SD 1.5": (512, 512),       # SD 1.5 native
        "SDXL": (1024, 1024),       # SDXL native
        "All": (1024, 1024),        # Default for "All"
    }

    if model_name in default_resolutions:
        width, height = default_resolutions[model_name]
        return format_resolution(width, height)

    # Fallback to 1024x1024
    return format_resolution(1024, 1024)


def get_latent_channels(model_name):
    """
    Return the latent channel count for a model.

    SD 1.5 and SDXL use 4-channel latents. Flux, Qwen Image, and Z-Image use
    16-channel latents. A wrong channel count makes the LATENT output unusable
    with that model's sampler.

    For "All" (no specific model) this defaults to 4 for backward compatibility
    with SD-based workflows; pick the specific model to get a 16-channel latent.

    Args:
        model_name (str): Model name, or "All".

    Returns:
        int: Latent channel count (4 or 16).
    """
    model_data = MODEL_RESOLUTIONS.get(model_name)
    if model_data:
        return model_data["constraints"].get("latent_channels", 4)
    return 4


def get_all_resolutions():
    """
    Get all unique resolution strings across all models, sorted by dimensions.

    Returns:
        list: All unique resolution strings sorted by total pixels
    """
    unique_resolutions = {}

    # Collect all unique width×height pairs
    for model_name in MODEL_RESOLUTIONS.keys():
        model_data = MODEL_RESOLUTIONS[model_name]
        for category in ["square", "portrait", "landscape"]:
            for width, height in model_data[category]:
                key = (width, height)
                if key not in unique_resolutions:
                    unique_resolutions[key] = format_resolution(width, height)

    # Sort by total pixels, then by width
    sorted_resolutions = sorted(
        unique_resolutions.items(),
        key=lambda item: (item[0][0] * item[0][1], item[0][0])
    )

    return [res_str for _, res_str in sorted_resolutions]


def parse_resolution_string(resolution_str):
    """
    Parse formatted resolution string back to width, height integers.

    Args:
        resolution_str (str): Format "1920x1080  (16:9 Landscape)" with possible padding

    Returns:
        tuple: (width, height)

    Raises:
        ValueError: If string format is invalid
    """
    try:
        # Format: "1920x1080  (16:9 Landscape)" - may have padding spaces
        # Extract the dimension part (before the opening parenthesis)
        dimension_part = resolution_str.split("(")[0].strip()

        if not dimension_part or 'x' not in dimension_part:
            raise ValueError(f"No dimension part found in: {resolution_str}")

        # Split on 'x' and convert to integers
        width, height = map(int, dimension_part.split("x"))

        return (width, height)
    except (ValueError, IndexError) as e:
        raise ValueError(f"Invalid resolution format: {resolution_str}")


# Tooltips (shared by both API wrappers).
TIP_MODEL  = "Image model. Filters the resolution presets to that model's recommended sizes. 'All' shows every preset."
TIP_RESOLUTION = "Preset resolution. The list filters to the selected model."
TIP_MULT   = "Multiplies the preset width and height (1x to 4x)."
TIP_BATCH  = "Number of latent samples in the preset latent batch."
TIP_CW     = "Custom width in pixels. 0 disables the custom outputs. Must satisfy the model's divisibility and bounds."
TIP_CH     = "Custom height in pixels. 0 disables the custom outputs. Must satisfy the model's divisibility and bounds."
TIP_CMULT  = "Multiplies the custom width and height (1x to 4x)."
TIP_CBATCH = "Number of latent samples in the custom latent batch."

OUTPUT_TIPS = {
    "width": "Preset width in pixels after multiplier.",
    "height": "Preset height in pixels after multiplier.",
    "latent": "Empty latent for the preset resolution.",
    "custom_width": "Custom width after multiplier, or 0 when custom is disabled.",
    "custom_height": "Custom height after multiplier, or 0 when custom is disabled.",
    "custom_latent": "Empty latent for the custom resolution.",
}


class ResolutionSelector(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        model_list = ["All"] + list(MODEL_RESOLUTIONS.keys())
        all_resolutions = get_all_resolutions()
        multipliers = ["1x", "2x", "3x", "4x"]
        return io.Schema(
            node_id="ResolutionSelectorPlus",
            display_name="Resolution Selector Plus",
            category="utils",
            description=(
                "Model-aware resolution presets, custom dimensions, and "
                "empty latent output."
            ),
            inputs=[
                io.Combo.Input(
                    "model", options=model_list, default="SDXL", tooltip=TIP_MODEL,
                ),
                io.Combo.Input(
                    "resolution", options=all_resolutions,
                    default="1024x1024 (1:1 Square)", tooltip=TIP_RESOLUTION,
                ),
                io.Combo.Input(
                    "resolution_multiplier", options=multipliers,
                    default="1x", tooltip=TIP_MULT,
                ),
                io.Int.Input(
                    "batch_size", default=1, min=1, max=64, step=1,
                    tooltip=TIP_BATCH,
                ),
                io.Int.Input(
                    "custom_width", default=0, min=0, max=4096, step=8,
                    optional=True, tooltip=TIP_CW,
                ),
                io.Int.Input(
                    "custom_height", default=0, min=0, max=4096, step=8,
                    optional=True, tooltip=TIP_CH,
                ),
                io.Combo.Input(
                    "custom_multiplier", options=multipliers, default="1x",
                    optional=True, tooltip=TIP_CMULT,
                ),
                io.Int.Input(
                    "custom_batch", default=1, min=1, max=64, step=1,
                    optional=True, tooltip=TIP_CBATCH,
                ),
            ],
            outputs=[
                io.Int.Output("width", display_name="width", tooltip=OUTPUT_TIPS["width"]),
                io.Int.Output("height", display_name="height", tooltip=OUTPUT_TIPS["height"]),
                io.Latent.Output("latent", display_name="latent", tooltip=OUTPUT_TIPS["latent"]),
                io.Int.Output(
                    "custom_width", display_name="custom_width",
                    tooltip=OUTPUT_TIPS["custom_width"],
                ),
                io.Int.Output(
                    "custom_height", display_name="custom_height",
                    tooltip=OUTPUT_TIPS["custom_height"],
                ),
                io.Latent.Output(
                    "custom_latent", display_name="custom_latent",
                    tooltip=OUTPUT_TIPS["custom_latent"],
                ),
            ],
        )

    @classmethod
    async def execute(
        cls,
        model: str,
        resolution: str,
        resolution_multiplier: str = "1x",
        batch_size: int = 1,
        custom_width: int = 0,
        custom_height: int = 0,
        custom_multiplier: str = "1x",
        custom_batch: int = 1,
    ) -> io.NodeOutput:
        if model not in ("All", *MODEL_RESOLUTIONS):
            raise ValueError("unknown model")
        multipliers = {"1x": 1, "2x": 2, "3x": 3, "4x": 4}
        if resolution_multiplier not in multipliers:
            raise ValueError("unknown resolution multiplier")
        if custom_multiplier not in multipliers:
            raise ValueError("unknown custom multiplier")
        if isinstance(batch_size, bool) or not 1 <= batch_size <= 64:
            raise ValueError("batch size is out of range")
        if isinstance(custom_batch, bool) or not 1 <= custom_batch <= 64:
            raise ValueError("custom batch size is out of range")

        multiplier = multipliers[resolution_multiplier]
        custom_mult = multipliers[custom_multiplier]
        width, height = parse_resolution_string(resolution)
        cls._validate_dimensions(model, width, height)
        width *= multiplier
        height *= multiplier
        channels = get_latent_channels(model)
        latent = await sdk.LatentRef.empty(
            width, height, batch_size=batch_size, channels=channels,
        )

        if custom_width > 0 and custom_height > 0:
            final_custom_width = custom_width * custom_mult
            final_custom_height = custom_height * custom_mult
            cls._validate_dimensions(
                model, final_custom_width, final_custom_height,
            )
            custom_latent = await sdk.LatentRef.empty(
                final_custom_width, final_custom_height,
                batch_size=custom_batch, channels=channels,
            )
            return io.NodeOutput(
                width, height, latent, final_custom_width,
                final_custom_height, custom_latent,
            )
        else:
            custom_latent = await sdk.LatentRef.empty(
                8, 8, batch_size=1, channels=channels,
            )
            return io.NodeOutput(width, height, latent, 0, 0, custom_latent)

    @staticmethod
    def _validate_dimensions(model, width, height):
        """
        Validate dimensions against model-specific constraints.

        Args:
            model (str): Model name
            width (int): Width in pixels
            height (int): Height in pixels

        Raises:
            ValueError: If dimensions violate model constraints
        """
        if model in MODEL_RESOLUTIONS:
            constraints = MODEL_RESOLUTIONS[model]["constraints"]
        else:
            # "All" or unknown model: enforce the generic latent requirement so
            # dimensions divide cleanly by 8 and stay within sane bounds.
            constraints = {"divisible_by": 8, "min": 64, "max": 4096}

        divisible_by = constraints.get("divisible_by", 8)
        min_dim = constraints.get("min", 64)
        max_dim = constraints.get("max", 4096)

        # Check divisibility
        if width % divisible_by != 0:
            raise ValueError(
                f"{model} requires width divisible by {divisible_by}. "
                f"Got {width} (remainder: {width % divisible_by})"
            )

        if height % divisible_by != 0:
            raise ValueError(
                f"{model} requires height divisible by {divisible_by}. "
                f"Got {height} (remainder: {height % divisible_by})"
            )

        # Check bounds
        if width < min_dim or width > max_dim:
            raise ValueError(
                f"{model} requires width between {min_dim} and {max_dim}. Got {width}"
            )

        if height < min_dim or height > max_dim:
            raise ValueError(
                f"{model} requires height between {min_dim} and {max_dim}. Got {height}"
            )

NODE_CLASS_MAPPINGS = {
    "ResolutionSelectorPlus": ResolutionSelector,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ResolutionSelectorPlus": "Resolution Selector Plus",
}
class ResolutionSelectorPlusExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [ResolutionSelector]


async def comfy_entrypoint() -> ResolutionSelectorPlusExtension:
    return ResolutionSelectorPlusExtension()
