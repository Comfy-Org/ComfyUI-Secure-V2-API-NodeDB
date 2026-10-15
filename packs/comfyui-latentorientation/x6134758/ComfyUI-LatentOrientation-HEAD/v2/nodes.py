"""Bounded pack-local latent transformations with legacy view semantics."""

from __future__ import annotations

import math

import torch
from comfy_api.latest import ComfyExtension, io

from . import algorithm

ORIENTATIONS = ("portrait", "landscape", "min square", "max square", "avg square")
MAX_ELEMENTS = 16_777_216
MAX_DIMENSION = 8192
MAX_RANK = 6


def _validate(samples: dict, orientation: str) -> None:
    if not isinstance(samples, dict):
        raise TypeError("samples must be a LATENT dictionary")
    tensor = samples.get("samples")
    if not isinstance(tensor, torch.Tensor):
        raise TypeError("LATENT samples must be a tensor")
    if not 4 <= tensor.ndim <= MAX_RANK:
        raise ValueError("LATENT rank must be 4..6")
    if tensor.layout != torch.strided or not tensor.dtype.is_floating_point:
        raise TypeError("LATENT samples must be a strided floating-point tensor")
    shape = list(tensor.shape)
    if any(not 1 <= size <= MAX_DIMENSION for size in shape):
        raise ValueError("input dimensions exceed bounds")
    if tensor.numel() > MAX_ELEMENTS:
        raise ValueError("input element count exceeds bounds")
    if not isinstance(orientation, str) or orientation not in ORIENTATIONS:
        raise ValueError("invalid orientation")

    # Project the literal upstream operations, including higher-rank quirks:
    # it reads axes 2/3 but F.pad always changes the final two axes.
    h, w = shape[2:4]
    if (orientation == "portrait" and h < w) or (orientation == "landscape" and h > w):
        shape[2], shape[3] = w, h
    elif orientation == "min square":
        shape[2] = shape[3] = min(h, w)
    elif orientation == "max square" and h != w:
        shape[-2 if h < w else -1] += abs(h - w)
    elif orientation == "avg square" and h != w:
        if tensor.ndim != 4:
            raise ValueError("legacy avg square resize requires rank 4")
        shape[2] = shape[3] = (h + w) // 2
    if any(size > MAX_DIMENSION for size in shape):
        raise ValueError("output dimensions exceed bounds")
    if math.prod(shape) > MAX_ELEMENTS:
        raise ValueError("output element count exceeds bounds")


class LatentOrient(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="LatentOrient",
            display_name="Orient Latent",
            category="latent/transform",
            inputs=[
                io.Latent.Input("samples"),
                io.Combo.Input("orientation", options=list(ORIENTATIONS)),
            ],
            outputs=[io.Latent.Output()],
        )

    @classmethod
    def execute(cls, samples: dict, orientation: str) -> io.NodeOutput:
        _validate(samples, orientation)
        return io.NodeOutput(*algorithm.LatentOrient().op(samples, orientation))


NODE_CLASS_MAPPINGS = {"LatentOrient": LatentOrient}
NODE_DISPLAY_NAME_MAPPINGS = {"LatentOrient": "Orient Latent"}


class LatentOrientationExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [LatentOrient]


async def comfy_entrypoint() -> LatentOrientationExtension:
    return LatentOrientationExtension()
