"""Bounded mask analysis and a permission-free scalar strategy selector."""

from __future__ import annotations

import math

import torch
from comfy_api.latest import ComfyExtension, io

from . import algorithm

MAX_DIMENSION = 8192
MAX_BATCH = 64
MAX_INPUT_ELEMENTS = 16_777_216
MAX_ANALYZED_PIXELS = 1_048_576
MAX_LABEL_ELEMENTS = 12_582_924
MAX_DFS_WORK = 9_437_184
MAX_STRING_BYTES = 4096


def _int(name, value, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} exceeds bounds")


def _float(name, value, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    if not minimum <= value <= maximum or not math.isfinite(value):
        raise ValueError(f"{name} must be finite and within bounds")


def _mask(mask):
    if not isinstance(mask, torch.Tensor):
        raise TypeError("mask must be a MASK tensor")
    if mask.ndim not in (2, 3) or mask.layout != torch.strided:
        raise ValueError("mask must be a strided HW or BHW tensor")
    if mask.dtype not in (
        torch.float16,
        torch.float32,
        torch.float64,
        torch.bool,
        torch.uint8,
        torch.int8,
        torch.int16,
        torch.int32,
        torch.int64,
    ):
        raise TypeError("mask must use a NumPy-compatible real dtype")
    if any(not 1 <= d <= MAX_DIMENSION for d in mask.shape[-2:]):
        raise ValueError("mask dimensions exceed bounds")
    if mask.ndim == 3 and not 1 <= mask.shape[0] <= MAX_BATCH:
        raise ValueError("mask batch exceeds bounds")
    if mask.numel() > MAX_INPUT_ELEMENTS:
        raise ValueError("mask input elements exceed bounds")
    pixels = math.prod(mask.shape[-2:])
    if pixels > MAX_ANALYZED_PIXELS:
        raise ValueError("analyzed pixels exceed bounds")
    # Worst-case projections include a label per pixel, stats/centroids/coords,
    # binary and visited arrays; DFS visits each pixel and tests 8 neighbors.
    if 12 * (pixels + 1) > MAX_LABEL_ELEMENTS:
        raise ValueError("projected label/array storage exceeds bounds")
    if 9 * pixels > MAX_DFS_WORK:
        raise ValueError("projected DFS work exceeds bounds")


class MaskAnalyze(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MaskAnalyze",
            display_name="Mask Analyze",
            category="Mask Tools",
            inputs=[
                io.Mask.Input("mask"),
                io.Float.Input("threshold", default=0.5, min=0.0, max=1.0, step=0.01),
                io.Int.Input(
                    "min_component_area", default=40, min=1, max=100000, step=1
                ),
                io.Int.Input(
                    "small_component_area", default=300, min=1, max=100000, step=1
                ),
                io.Int.Input(
                    "direct_max_components", default=4, min=1, max=1000, step=1
                ),
                io.Int.Input(
                    "overlay_min_components", default=9, min=1, max=1000, step=1
                ),
                io.Float.Input(
                    "wide_aspect_overlay", default=3.2, min=1.0, max=20.0, step=0.1
                ),
                io.Float.Input(
                    "small_ratio_overlay", default=0.45, min=0.0, max=1.0, step=0.01
                ),
            ],
            outputs=[
                io.Int.Output("component_count"),
                io.Int.Output("small_component_count"),
                io.Float.Output("small_component_ratio"),
                io.Float.Output("aspect_ratio"),
                io.Float.Output("complexity_score"),
                io.String.Output("strategy"),
                io.Boolean.Output("use_overlay_mode"),
            ],
        )

    @classmethod
    def execute(
        cls,
        mask,
        threshold,
        min_component_area,
        small_component_area,
        direct_max_components,
        overlay_min_components,
        wide_aspect_overlay,
        small_ratio_overlay,
    ):
        _mask(mask)
        _float("threshold", threshold, 0.0, 1.0)
        _int("min_component_area", min_component_area, 1, 100000)
        _int("small_component_area", small_component_area, 1, 100000)
        _int("direct_max_components", direct_max_components, 1, 1000)
        _int("overlay_min_components", overlay_min_components, 1, 1000)
        _float("wide_aspect_overlay", wide_aspect_overlay, 1.0, 20.0)
        _float("small_ratio_overlay", small_ratio_overlay, 0.0, 1.0)
        return io.NodeOutput(
            *algorithm.MaskAnalyze().analyze(
                mask,
                threshold,
                min_component_area,
                small_component_area,
                direct_max_components,
                overlay_min_components,
                wide_aspect_overlay,
                small_ratio_overlay,
            )
        )


class MaskStrategySwitch(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MaskStrategySwitch",
            display_name="Mask Strategy Switch",
            category="Mask Tools",
            inputs=[
                io.String.Input("strategy", default="direct"),
                io.Int.Input(
                    "direct_value", default=0, min=-999999, max=999999, step=1
                ),
                io.Int.Input(
                    "simplified_value", default=1, min=-999999, max=999999, step=1
                ),
                io.Int.Input(
                    "overlay_value", default=2, min=-999999, max=999999, step=1
                ),
            ],
            outputs=[io.Int.Output("selected_value")],
        )

    @classmethod
    def execute(cls, strategy, direct_value, simplified_value, overlay_value):
        if not isinstance(strategy, str):
            raise TypeError("strategy must be a string")
        if (
            len(strategy) > MAX_STRING_BYTES
            or len(strategy.encode("utf8")) > MAX_STRING_BYTES
        ):
            raise ValueError("strategy exceeds UTF-8 byte bounds")
        for name, value in [
            ("direct_value", direct_value),
            ("simplified_value", simplified_value),
            ("overlay_value", overlay_value),
        ]:
            _int(name, value, -999999, 999999)
        return io.NodeOutput(
            *algorithm.MaskStrategySwitch().pick(
                strategy, direct_value, simplified_value, overlay_value
            )
        )


NODE_CLASS_MAPPINGS = {
    "MaskAnalyze": MaskAnalyze,
    "MaskStrategySwitch": MaskStrategySwitch,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "MaskAnalyze": "Mask Analyze",
    "MaskStrategySwitch": "Mask Strategy Switch",
}


class MaskAnalyzerExtension(ComfyExtension):
    async def get_node_list(self):
        return [MaskAnalyze, MaskStrategySwitch]


async def comfy_entrypoint():
    return MaskAnalyzerExtension()
