"""Pure scalar math. All authored presets travel with workflow widgets."""
import math

from comfy_api.latest import io

DEFAULT_PRESETS = "512x512\n512x768\n768x768\n1024x1024\n896x1216\n1216x896\n1088x1920\n1920x1088\n1152x1536\n1536x1152\n1536x2048\n2048x1536\n2048x2048"


class ResolutionAndRatio(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="ResolutionAndRatio", display_name="Resolution and Ratio",
            category="CustomUtils",
            inputs=[
                io.Int.Input("width", default=1152, min=8, max=4096, step=32),
                io.Int.Input("height", default=1536, min=8, max=4096, step=32),
                io.Int.Input("W_ratio", default=3, min=1, max=512),
                io.Int.Input("H_ratio", default=4, min=1, max=512),
                io.Int.Input("scale_percent", default=100, min=10, max=200, step=5, display_mode=io.NumberDisplay.slider),
                io.Boolean.Input("reset", default=False, label_on="RESET", label_off="RESET"),
                io.Boolean.Input("swap", default=False, label_on="SWAP", label_off="SWAP"),
                io.Combo.Input("preset", options=["Custom"]),
                io.String.Input("custom_presets", multiline=True, default=DEFAULT_PRESETS),
            ],
            outputs=[io.Int.Output("width"), io.Int.Output("height")],
        )

    @classmethod
    def _snap_size(cls, value):
        # Python round is intentionally retained (banker's ties), not JS round.
        value = int(round(float(value)))
        value = max(8, min(4096, value))
        if value > 32:
            value = int(round(value / 32)) * 32
            value = max(32, value)
        return value

    @classmethod
    def validate_inputs(cls, width, height, **kwargs):
        if not 8 <= width <= 4096:
            return "Width must be between 8 and 4096"
        if not 8 <= height <= 4096:
            return "Height must be between 8 and 4096"
        return True

    @classmethod
    def execute(cls, width, height, W_ratio, H_ratio, scale_percent, reset, swap, preset, custom_presets):
        for name, value in (("width", width), ("height", height), ("W_ratio", W_ratio), ("H_ratio", H_ratio), ("scale_percent", scale_percent)):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a finite scalar")
            if abs(value) > 10**9 or not math.isfinite(value):
                raise ValueError(f"{name} exceeds the finite scalar resource bound")
        if not isinstance(reset, bool) or not isinstance(swap, bool):
            raise TypeError("reset and swap must be boolean")
        if not isinstance(preset, str) or len(preset) > 128:
            raise ValueError("preset must be bounded text")
        if not isinstance(custom_presets, str) or len(custom_presets) > 65536 or len(custom_presets.encode("utf-8")) > 65536 or custom_presets.count("\n") >= 1024:
            raise ValueError("custom_presets must be text within 65536 UTF-8 bytes and 1024 lines")
        if reset:
            width = height = 512
        if swap:
            width, height = height, width
        return io.NodeOutput(cls._snap_size(width), cls._snap_size(height))
