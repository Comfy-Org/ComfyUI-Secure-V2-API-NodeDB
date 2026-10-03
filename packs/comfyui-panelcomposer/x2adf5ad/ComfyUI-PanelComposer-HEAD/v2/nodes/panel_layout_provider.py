import json

from comfy_api.latest import io, sdk

from ..presets import layouts
from ..presets.layouts import apply_reading_order, apply_rotation, get_layout
from ..utils.compositing import pil_to_tensor
from ..utils.geometry import (
    ASPECT_RATIO_CHOICES,
    FIXED_PRESET_MEGAPIXELS,
    compute_panel_dimensions,
    parse_aspect_ratio,
    resolve_oriented_aspect_ratio,
    solve_dimensions_from_megapixels,
)
from ..utils.region_map import render_region_map

ASPECT_RATIOS = list(ASPECT_RATIO_CHOICES.keys())
FIXED_PRESET_SIZES = list(FIXED_PRESET_MEGAPIXELS.keys())
PANEL_DIMENSIONS = io.Custom("PANEL_DIMENSIONS")
COLOR_LIST = io.Custom("COLOR_LIST")


class PanelLayoutProvider(io.ComfyNode):
    """Produces panel geometry and a region map without mutable host state."""

    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="PanelLayoutProvider",
            display_name="Panel Layout Provider (PanelComposer)",
            category="PanelComposer/Layout",
            inputs=[
                io.Combo.Input("layout_preset", options=layouts.LAYOUT_CHOICES),
                io.Combo.Input("reading_order", options=["left_to_right", "right_to_left"]),
                io.Combo.Input("canvas_rotation", options=["0", "90", "180", "270"]),
                io.Combo.Input("aspect_ratio", options=ASPECT_RATIOS),
                io.Combo.Input("page_orientation", options=["portrait", "landscape"]),
                io.Combo.Input("canvas_size_mode", options=["fixed_preset", "fixed_custom"]),
                io.Combo.Input("fixed_preset_size", options=FIXED_PRESET_SIZES),
                io.Float.Input(
                    "fixed_custom_megapixels", default=2.0, min=0.1, max=64.0, step=0.1
                ),
                io.Float.Input("megapixels", default=1.0, min=0.01, max=16.0, step=0.01),
                io.Int.Input("multiple", default=64, min=1, max=256, step=1),
            ],
            outputs=[
                io.String.Output("layout_json", display_name="layout_json"),
                PANEL_DIMENSIONS.Output("panel_dimensions", display_name="panel_dimensions"),
                io.Image.Output("area_image", display_name="area_image"),
                COLOR_LIST.Output("area_colors", display_name="area_colors"),
            ],
        )

    @classmethod
    def validate_inputs(cls, layout_preset=None, **_kwargs):
        try:
            layouts.decode_layout_choice(layout_preset)
        except ValueError as exc:
            return str(exc)
        return True

    @classmethod
    async def execute(
        cls,
        layout_preset,
        reading_order,
        canvas_rotation,
        aspect_ratio,
        page_orientation,
        canvas_size_mode,
        fixed_preset_size,
        fixed_custom_megapixels,
        megapixels,
        multiple,
    ) -> io.NodeOutput:
        panels = get_layout(layout_preset)
        panels = apply_rotation(panels, canvas_rotation)
        panels = apply_reading_order(panels, reading_order, layout_preset)

        page_ar = resolve_oriented_aspect_ratio(
            parse_aspect_ratio(aspect_ratio), page_orientation
        )
        panel_dimensions = compute_panel_dimensions(
            panels, page_ar, float(megapixels), int(multiple)
        )
        canvas_megapixels = (
            FIXED_PRESET_MEGAPIXELS[fixed_preset_size]
            if canvas_size_mode == "fixed_preset"
            else float(fixed_custom_megapixels)
        )
        canvas_width, canvas_height = solve_dimensions_from_megapixels(
            page_ar, canvas_megapixels, int(multiple)
        )
        layout_json = json.dumps(
            {
                "panels": panels,
                "page_orientation": page_orientation,
                "canvas_width": canvas_width,
                "canvas_height": canvas_height,
            }
        )
        region_map_image, area_colors = render_region_map(
            panels, canvas_width, canvas_height
        )
        area_image = await sdk.ImageRef._from_raw(pil_to_tensor(region_map_image))
        return io.NodeOutput(layout_json, panel_dimensions, area_image, area_colors)


NODE_CLASS_MAPPINGS = {"PanelLayoutProvider": PanelLayoutProvider}
NODE_DISPLAY_NAME_MAPPINGS = {
    "PanelLayoutProvider": "Panel Layout Provider (PanelComposer)"
}
