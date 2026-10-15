"""Bounded raw-compute migration preserving all six legacy interpolation modes."""

import torch
from comfy_api.latest import ComfyExtension, io

from . import algorithm

MODES = ("nearest", "bilinear", "bicubic", "area", "nearest-exact", "lanczos")
MAX_BATCH = 64
MAX_DIMENSION = 8192
MAX_ELEMENTS = 16_777_216


def _validate(image, width, height, keep_proportion, interpolation):
    for name, value in (("width", width), ("height", height)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{name} must be an integer")
        if not 576 <= value <= 1024:
            raise ValueError(f"{name} exceeds schema bounds")
    if type(keep_proportion) is not bool:
        raise TypeError("keep_proportion must be bool")
    if interpolation not in MODES:
        raise ValueError("unknown interpolation mode")
    if not isinstance(image, torch.Tensor):
        raise TypeError("image must be a tensor")
    if image.ndim != 4 or image.shape[-1] not in (3, 4):
        raise ValueError("image must use BHWC RGB/RGBA layout")
    batch, original_h, original_w, channels = image.shape
    if not 1 <= batch <= MAX_BATCH or any(
        not 1 <= x <= MAX_DIMENSION for x in (original_h, original_w)
    ):
        raise ValueError("image batch/dimensions exceed bounds")
    if image.numel() > MAX_ELEMENTS:
        raise ValueError("input elements exceed bound")
    if not image.dtype.is_floating_point:
        raise TypeError("image must use floating-point dtype")
    if not torch.isfinite(image).all():
        raise ValueError("image must be finite")
    out_w, out_h = width, height
    if keep_proportion:
        ratio = min(width / original_w, height / original_h)
        out_w, out_h = round(original_w * ratio), round(original_h * ratio)
    if out_w < 1 or out_h < 1:
        raise ValueError("aspect fit collapses an output dimension")
    if batch * out_w * out_h * channels > MAX_ELEMENTS:
        raise ValueError("output elements exceed bound")


class SVDRsizer(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SVDRsizer",
            display_name="SVDRsizer",
            category="essentials",
            inputs=[
                io.Image.Input("image"),
                io.Int.Input("width", default=576, min=576, max=1024, step=64),
                io.Int.Input("height", default=1024, min=576, max=1024, step=64),
                io.Combo.Input("interpolation", options=list(MODES)),
                io.Boolean.Input("keep_proportion", default=False),
            ],
            outputs=[
                io.Image.Output("IMAGE"),
                io.Int.Output("width"),
                io.Int.Output("height"),
            ],
        )

    @classmethod
    def execute(cls, image, width, height, keep_proportion, interpolation="nearest"):
        _validate(image, width, height, keep_proportion, interpolation)
        return io.NodeOutput(
            *algorithm.resize(image, width, height, keep_proportion, interpolation)
        )


NODE_CLASS_MAPPINGS = {"SVDRsizer": SVDRsizer}
# Preserve the upstream orphan mapping rather than silently renaming the node.
NODE_DISPLAY_NAME_MAPPINGS = {"SVDResizer": "SVDResizer"}


class SVDResizerExtension(ComfyExtension):
    async def get_node_list(self):
        return [SVDRsizer]


async def comfy_entrypoint():
    return SVDResizerExtension()
