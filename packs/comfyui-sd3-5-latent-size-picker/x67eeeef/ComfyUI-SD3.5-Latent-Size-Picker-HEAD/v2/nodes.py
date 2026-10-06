from comfy_api.latest import ComfyExtension, io, sdk

MAX_RESOLUTION = 16384
SD35_OPTIONS = [
    "640x1536 (0.98)",
    "704x1344 (0.94)",
    "768x1280 (0.98)",
    "832x1152 (0.96)",
    "896x1152 (1.03)",
    "960x1024 (0.98)",
    "1024x1024 (1.0)",
    "1152x896 (1.03)",
    "1216x832 (1.01)",
    "1280x768 (0.98)",
    "1344x704 (0.95)",
]
FLUX_OPTIONS = [
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
    "512x768 (2:3)",
    "576x864 (2:3)",
    "640x960 (2:3)",
    "704x1056 (2:3)",
    "768x1152 (2:3)",
    "832x1248 (2:3)",
    "896x1344 (2:3)",
    "960x1440 (2:3)",
    "1024x1536 (2:3)",
    "768x512 (3:2)",
    "864x576 (3:2)",
    "960x640 (3:2)",
    "1056x704 (3:2)",
    "1152x768 (3:2)",
    "1248x832 (3:2)",
    "1344x896 (3:2)",
    "1440x960 (3:2)",
    "1536x1024 (3:2)",
    "512x1024 (1:2)",
    "576x1152 (1:2)",
    "640x1280 (1:2)",
    "704x1408 (1:2)",
    "768x1536 (1:2)",
    "1024x512 (2:1)",
    "1152x576 (2:1)",
    "1280x640 (2:1)",
    "1408x704 (2:1)",
    "1536x768 (2:1)",
    "512x896 (4:7)",
    "576x1008 (4:7)",
    "640x1120 (4:7)",
    "704x1232 (4:7)",
    "768x1344 (4:7)",
    "832x1456 (4:7)",
    "1024x576 (16:9)",
    "1152x648 (16:9)",
    "1280x720 (16:9)",
    "1408x792 (16:9)",
    "1536x864 (16:9)",
    "1664x936 (16:9)",
    "1792x1008 (16:9)",
    "1920x1080 (16:9)",
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


def bounded_int(name, value, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} outside bounded range")
    return value


def parse_dimensions(resolution):
    if not isinstance(resolution, str):
        raise TypeError("resolution must be a string")
    if len(resolution) > 1024:
        raise ValueError("resolution exceeds text bound")
    try:
        width, height = map(int, resolution.split(" ")[0].split("x"))
    except (ValueError, IndexError):
        raise ValueError(
            f"Invalid resolution format: {resolution}. "
            "Expected format: 'WIDTHxHEIGHT (RATIO)'"
        ) from None
    bounded_int("parsed width", width, -1048576, 1048576)
    bounded_int("parsed height", height, -1048576, 1048576)
    return width, height


def sd35_dimensions(
    resolution, width_override=0, height_override=0, invert_ratios="No"
):
    width, height = parse_dimensions(resolution)
    bounded_int("width_override", width_override, 0, MAX_RESOLUTION)
    bounded_int("height_override", height_override, 0, MAX_RESOLUTION)
    if invert_ratios not in ("No", "Yes"):
        raise ValueError("invalid invert_ratios")
    if width_override > 0:
        width = min(width_override, MAX_RESOLUTION)
    if height_override > 0:
        height = min(height_override, MAX_RESOLUTION)
    width = max(64, min(width, MAX_RESOLUTION))
    height = max(64, min(height, MAX_RESOLUTION))
    if invert_ratios == "Yes":
        width, height = height, width
    return (width // 64) * 64, (height // 64) * 64


def flux_dimensions(
    resolution,
    width_override=0,
    height_override=0,
    aspect_ratio_lock="Unlocked",
    downsample_factor="auto",
    invert_ratios="No",
):
    base_width, base_height = parse_dimensions(resolution)
    bounded_int("width_override", width_override, 0, MAX_RESOLUTION)
    bounded_int("height_override", height_override, 0, MAX_RESOLUTION)
    if aspect_ratio_lock not in ("Unlocked", "Width", "Height"):
        raise ValueError("invalid aspect_ratio_lock")
    if invert_ratios not in ("No", "Yes"):
        raise ValueError("invalid invert_ratios")
    if isinstance(downsample_factor, bool) or downsample_factor not in (
        "auto",
        4,
        8,
        "4",
        "8",
    ):
        raise ValueError("invalid downsample_factor")
    factor = 8 if downsample_factor == "auto" else int(downsample_factor)
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
    return (
        ((width + factor - 1) // factor) * factor,
        ((height + factor - 1) // factor) * factor,
        factor,
    )


def base_inputs(options, default):
    return [
        io.Combo.Input("resolution", options=options, default=default),
        io.Int.Input("batch_size", default=1, min=1, max=4096),
        io.Int.Input("width_override", default=0, min=0, max=MAX_RESOLUTION, step=8),
        io.Int.Input("height_override", default=0, min=0, max=MAX_RESOLUTION, step=8),
    ]


def latent_outputs():
    return [
        io.Latent.Output("LATENT", display_name="LATENT"),
        io.Int.Output("width", display_name="width"),
        io.Int.Output("height", display_name="height"),
    ]


class SD3_5EmptyLatent(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SD3_5EmptyLatent",
            display_name="🔧 SD3.5 Empty Latent Size Picker",
            category="sd3.5/utilities",
            inputs=base_inputs(SD35_OPTIONS, "1024x1024 (1.0)")
            + [
                io.Combo.Input("invert_ratios", options=["No", "Yes"], default="No"),
            ],
            outputs=latent_outputs(),
        )

    @classmethod
    async def execute(
        cls,
        resolution,
        batch_size,
        width_override=0,
        height_override=0,
        invert_ratios="No",
    ):
        bounded_int("batch_size", batch_size, 1, 4096)
        width, height = sd35_dimensions(
            resolution, width_override, height_override, invert_ratios
        )
        latent = await sdk.LatentRef.empty(
            width=width,
            height=height,
            batch_size=batch_size,
            channels=4,
            spatial_downscale_ratio=8,
        )
        return io.NodeOutput(latent, width, height)


class FluxEmptyLatent(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="FluxEmptyLatent",
            display_name="🔧 Flux Empty Latent (Enhanced)",
            category="latent",
            inputs=base_inputs(FLUX_OPTIONS, "1024x1024 (1:1)")
            + [
                io.Combo.Input(
                    "aspect_ratio_lock",
                    options=["Unlocked", "Width", "Height"],
                    default="Unlocked",
                ),
                io.Int.Input("latent_channels", default=4, min=1, max=16, step=1),
                io.Combo.Input(
                    "downsample_factor", options=["auto", 4, 8], default="auto"
                ),
                io.Combo.Input("invert_ratios", options=["No", "Yes"], default="No"),
            ],
            outputs=latent_outputs(),
        )

    @classmethod
    async def execute(
        cls,
        resolution,
        batch_size,
        width_override=0,
        height_override=0,
        aspect_ratio_lock="Unlocked",
        latent_channels=4,
        downsample_factor="auto",
        invert_ratios="No",
    ):
        bounded_int("batch_size", batch_size, 1, 4096)
        bounded_int("latent_channels", latent_channels, 1, 16)
        width, height, factor = flux_dimensions(
            resolution,
            width_override,
            height_override,
            aspect_ratio_lock,
            downsample_factor,
            invert_ratios,
        )
        latent = await sdk.LatentRef.empty(
            width=width,
            height=height,
            batch_size=batch_size,
            channels=latent_channels,
            spatial_downscale_ratio=factor,
        )
        return io.NodeOutput(latent, width, height)


NODE_CLASS_MAPPINGS = {
    "SD3_5EmptyLatent": SD3_5EmptyLatent,
    "FluxEmptyLatent": FluxEmptyLatent,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "SD3_5EmptyLatent": "🔧 SD3.5 Empty Latent Size Picker",
    "FluxEmptyLatent": "🔧 Flux Empty Latent (Enhanced)",
}


class LatentSizePickerExtension(ComfyExtension):
    async def get_node_list(self):
        return [SD3_5EmptyLatent, FluxEmptyLatent]


async def comfy_entrypoint():
    return LatentSizePickerExtension()
