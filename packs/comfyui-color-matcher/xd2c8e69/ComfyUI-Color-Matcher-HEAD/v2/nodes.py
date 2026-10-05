"""Secure Nodes V2 conversion of ComfyUI-Color-Matcher."""

from __future__ import annotations

import numpy as np
import torch
from color_matcher import ColorMatcher
from color_matcher.normalizer import Normalizer
from comfy_api.latest import ComfyExtension, io

METHODS = ["mkl", "hm", "reinhard", "mvgd", "hm-mvgd-hm", "hm-mkl-hm"]
MAX_TENSOR_ELEMENTS = 67_108_864
MAX_BATCH = 4096


def _validate_image(value, name: str) -> None:
    if not isinstance(value, torch.Tensor) or value.ndim != 4:
        raise TypeError(f"{name} must be a BHWC image tensor")
    if value.shape[0] < 1 or value.shape[0] > MAX_BATCH:
        raise ValueError(f"{name} batch is outside the secure bound")
    if value.shape[-1] != 3:
        raise ValueError(f"{name} must contain exactly three RGB channels")
    if value.numel() < 1 or value.numel() > MAX_TENSOR_ELEMENTS:
        raise ValueError(f"{name} exceeds the secure tensor-size bound")


class ColorMatch(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ColorMatch",
            display_name="Color Match",
            category="image/color",
            inputs=[
                io.Image.Input("image_ref"),
                io.Image.Input("image_target"),
                io.Combo.Input("method", options=METHODS, default="mkl"),
            ],
            outputs=[io.Image.Output("image")],
        )

    @classmethod
    def execute(cls, image_ref, image_target, method) -> io.NodeOutput:
        _validate_image(image_ref, "image_ref")
        _validate_image(image_target, "image_target")
        if method not in METHODS:
            raise ValueError(f"unsupported color-match method: {method}")

        reference = (image_ref[0].cpu().numpy() * 255).astype(np.uint8)
        matcher = ColorMatcher()
        result_frames = []
        for frame in image_target:
            source = (frame.cpu().numpy() * 255).astype(np.uint8)
            matched = matcher.transfer(src=source, ref=reference, method=method)
            matched = Normalizer(matched).uint8_norm()
            result_frames.append(torch.from_numpy(matched.astype(np.float32) / 255.0))
        return io.NodeOutput(torch.stack(result_frames))


NODE_CLASS_MAPPINGS = {"ColorMatch": ColorMatch}
NODE_DISPLAY_NAME_MAPPINGS = {"ColorMatch": "Color Match"}


class ColorMatcherExtension(ComfyExtension):
    async def get_node_list(self):
        return [ColorMatch]


async def comfy_entrypoint() -> ColorMatcherExtension:
    return ColorMatcherExtension()
