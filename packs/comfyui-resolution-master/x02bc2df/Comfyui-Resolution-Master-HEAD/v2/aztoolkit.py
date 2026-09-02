"""Secure Nodes V2 implementation of Resolution Master."""

from comfy_api.latest import ComfyExtension, io, sdk

from .core.auto_detect import (
    apply_backend_auto_detect_fallback,
    calculate_rescale_factor,
    safe_float,
    safe_int,
)


class ResolutionMaster(io.ComfyNode):
    """Calculate a resolution and create its bounded empty latent."""

    SDK_REFS = True
    SDK_PERMISSIONS = ("graph",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ResolutionMaster",
            display_name="Resolution Master",
            category="utils/azToolkit",
            description=(
                "Interactive resolution, scaling, preset, and latent-size "
                "helper with optional input-image auto-detection."
            ),
            inputs=[
                io.Combo.Input(
                    "mode",
                    options=[
                        "Manual",
                        "Manual Sliders",
                        "Common Resolutions",
                        "Aspect Ratios",
                    ],
                    tooltip=(
                        "Choose how to control the output size. Manual mode "
                        "uses the Resolution Master canvas."
                    ),
                ),
                io.Combo.Input(
                    "latent_type",
                    options=["latent_4x8", "latent_128x16"],
                    default="latent_4x8",
                    tooltip=(
                        "Choose the latent type. Use 4x8 for most models, "
                        "or 128x16 for Flux.2."
                    ),
                ),
                io.Int.Input(
                    "width", default=512, min=0, max=32768, step=64,
                    tooltip="Final output width in pixels.",
                ),
                io.Int.Input(
                    "height", default=512, min=0, max=32768, step=64,
                    tooltip="Final output height in pixels.",
                ),
                io.Boolean.Input(
                    "auto_detect", default=False,
                    label_on="Auto-detect from input", label_off="Manual",
                    tooltip="Detect the size from the connected input image.",
                ),
                io.String.Input(
                    "auto_detect_source", default="backend",
                    tooltip=(
                        "Technical setting used by the Resolution Master "
                        "interface."
                    ),
                ),
                io.Int.Input(
                    "auto_detect_width", default=0, min=0, max=32768,
                    tooltip="Detected input width used by auto-detect.",
                ),
                io.Int.Input(
                    "auto_detect_height", default=0, min=0, max=32768,
                    tooltip="Detected input height used by auto-detect.",
                ),
                io.Boolean.Input(
                    "auto_fit_on_change", default=False,
                    tooltip=(
                        "When a new image is detected, fit it to the closest "
                        "preset automatically."
                    ),
                ),
                io.Boolean.Input(
                    "auto_resize_on_change", default=False,
                    tooltip=(
                        "When a new image is detected, resize it automatically "
                        "using the selected scaling mode."
                    ),
                ),
                io.Boolean.Input(
                    "auto_snap_on_change", default=False,
                    tooltip=(
                        "When a new image is detected, round its size to the "
                        "selected snap step."
                    ),
                ),
                io.Boolean.Input(
                    "smart_fit", default=False,
                    tooltip=(
                        "Fit to the closest preset aspect ratio while keeping "
                        "the size close to the current resolution."
                    ),
                ),
                io.Boolean.Input(
                    "use_custom_calc", default=False,
                    tooltip=(
                        "When a new image is detected, apply the selected "
                        "model or category size rules automatically."
                    ),
                ),
                io.Boolean.Input(
                    "preserve_scaling_ratio", default=False,
                    tooltip="Keep the image proportions while scaling.",
                ),
                io.String.Input(
                    "selected_category", default="",
                    tooltip="Selected preset category.",
                ),
                io.Int.Input(
                    "snap_value", default=64, min=1, max=32768,
                    tooltip="Snap step used when rounding width and height.",
                ),
                io.Float.Input(
                    "upscale_value", default=1.0, min=0.0, max=100.0,
                    tooltip="Manual scale multiplier.",
                ),
                io.Int.Input(
                    "target_resolution", default=1080, min=1, max=32768,
                    tooltip="Target p-resolution used for scaling.",
                ),
                io.Float.Input(
                    "target_megapixels", default=2.0, min=0.0, max=1000.0,
                    tooltip="Target megapixels used for scaling.",
                ),
                io.String.Input(
                    "auto_detect_presets_json", default="{}",
                    tooltip="Technical preset data used by auto-detect.",
                ),
                io.String.Input(
                    "rescale_mode", default="resolution",
                    tooltip="Scaling mode used for the Rescale Factor output.",
                ),
                io.Float.Input(
                    "rescale_value", default=1.0, step=0.001,
                    min=0.0, max=100.0,
                    tooltip=(
                        "Current Rescale Factor value shown by the interface."
                    ),
                ),
                io.Int.Input(
                    "batch_size", default=1, min=1, max=4096,
                    tooltip="How many latent images to create in one batch.",
                ),
                io.Image.Input(
                    "input_image", optional=True,
                    tooltip=(
                        "Optional image used for auto-detecting width and "
                        "height."
                    ),
                ),
            ],
            outputs=[
                io.Int.Output(
                    "width", tooltip="Final output width in pixels."
                ),
                io.Int.Output(
                    "height", tooltip="Final output height in pixels."
                ),
                io.Float.Output(
                    "rescale_factor",
                    tooltip=(
                        "Scale factor calculated from the selected scaling "
                        "mode."
                    ),
                ),
                io.Int.Output(
                    "batch_size",
                    tooltip="Number of latent images created in one batch.",
                ),
                io.Latent.Output(
                    "latent",
                    tooltip=(
                        "Empty latent created with the selected size, batch "
                        "size, and latent type."
                    ),
                ),
            ],
            hidden=[io.Hidden.unique_id, io.Hidden.prompt],
        )

    @staticmethod
    async def detect_image_dimensions(input_image: sdk.ImageRef):
        if not isinstance(input_image, sdk.ImageRef):
            raise TypeError("input_image must be an IMAGE ref")
        height, width = await input_image.spatial_shape()
        return int(width), int(height)

    @staticmethod
    def _is_empty_local_image_gallery_selection(value):
        return str(value or "").strip().lower() in (
            "", "none", "null", "undefined",
        )

    @classmethod
    async def is_empty_linked_gallery_input(cls):
        """Inspect only the directly linked producer's bounded widget values."""

        try:
            values = await sdk.ctx().graph.widget_values(
                linked_input="input_image"
            )
        except Exception as error:
            if not (
                isinstance(error, KeyError)
                or getattr(error, "remote_type", "") == "KeyError"
            ):
                raise
            return False
        return (
            "selected_image" in values
            and cls._is_empty_local_image_gallery_selection(
                values.get("selected_image")
            )
        )

    @staticmethod
    async def _empty_latent(width, height, batch_size, latent_type):
        channels, ratio = (
            (128, 16)
            if latent_type == "latent_128x16"
            else (4, 8)
        )
        latent_width = (int(width) // ratio) * ratio
        latent_height = (int(height) // ratio) * ratio
        if latent_width < 64 or latent_height < 64:
            raise ValueError(
                "Resolution Master requires width and height to produce at "
                "least one supported latent region (64 pixels per side)"
            )
        return await sdk.LatentRef.empty(
            width=latent_width,
            height=latent_height,
            batch_size=int(batch_size),
            channels=channels,
            spatial_downscale_ratio=ratio,
        )

    @classmethod
    async def execute(
        cls,
        mode,
        latent_type,
        width,
        height,
        auto_detect,
        auto_detect_source,
        auto_detect_width,
        auto_detect_height,
        auto_fit_on_change,
        auto_resize_on_change,
        auto_snap_on_change,
        smart_fit,
        use_custom_calc,
        preserve_scaling_ratio,
        selected_category,
        snap_value,
        upscale_value,
        target_resolution,
        target_megapixels,
        auto_detect_presets_json,
        rescale_mode,
        rescale_value,
        batch_size=1,
        input_image=None,
    ) -> io.NodeOutput:
        del mode, rescale_value
        width = safe_int(width, 1)
        height = safe_int(height, 1)
        detected_width = None
        detected_height = None

        frontend_source_empty = auto_detect_source == "frontend-empty"
        linked_gallery_empty = False
        if auto_detect and input_image is not None and not frontend_source_empty:
            linked_gallery_empty = await cls.is_empty_linked_gallery_input()

        if (
            auto_detect
            and input_image is not None
            and not frontend_source_empty
            and not linked_gallery_empty
        ):
            detected_width, detected_height = (
                await cls.detect_image_dimensions(input_image)
            )
            frontend_matches_tensor = (
                auto_detect_source == "frontend"
                and safe_int(auto_detect_width) == detected_width
                and safe_int(auto_detect_height) == detected_height
            )
            if not frontend_matches_tensor:
                width, height = apply_backend_auto_detect_fallback(
                    detected_width,
                    detected_height,
                    auto_fit_on_change,
                    auto_resize_on_change,
                    auto_snap_on_change,
                    smart_fit,
                    use_custom_calc,
                    preserve_scaling_ratio,
                    selected_category,
                    safe_int(snap_value, 64),
                    safe_float(upscale_value, 1.0),
                    safe_int(target_resolution, 1080),
                    safe_float(target_megapixels, 2.0),
                    rescale_mode,
                    auto_detect_presets_json,
                )

        rescale_factor = calculate_rescale_factor(
            width,
            height,
            rescale_mode,
            safe_float(upscale_value, 1.0),
            safe_int(target_resolution, 1080),
            safe_float(target_megapixels, 2.0),
        )
        latent = await cls._empty_latent(
            width, height, batch_size, latent_type
        )
        ui = {
            "resolution_master": {
                "detected_width": detected_width,
                "detected_height": detected_height,
                "width": int(width),
                "height": int(height),
                "rescale_factor": float(rescale_factor),
                "source_empty": bool(
                    frontend_source_empty or linked_gallery_empty
                ),
            }
        }
        return io.NodeOutput(
            int(width), int(height), float(rescale_factor), int(batch_size),
            latent, ui=ui,
        )


class ResolutionMasterExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [ResolutionMaster]


async def comfy_entrypoint() -> ResolutionMasterExtension:
    return ResolutionMasterExtension()


NODE_CLASS_MAPPINGS = {"ResolutionMaster": ResolutionMaster}
NODE_DISPLAY_NAME_MAPPINGS = {"ResolutionMaster": "Resolution Master"}


__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "ResolutionMaster",
    "ResolutionMasterExtension",
    "comfy_entrypoint",
]
