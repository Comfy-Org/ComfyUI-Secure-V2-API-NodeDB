"""Bounded value-mode wrappers; the pinned algorithms remain pack-owned."""

import torch
from comfy_api.latest import ComfyExtension, io

from . import algorithm

MAX_DIMENSION = 8192
MAX_ELEMENTS = 16_777_216
MAX_COMBINATIONS = 4096
MAX_WORK = 134_217_728
MAX_MASKS = 12
MAX_BATCH = 64


def _tensor(value, rank, channels=None, name="tensor"):
    if not isinstance(value, torch.Tensor):
        raise TypeError(f"{name} must be a tensor")
    if value.ndim != rank or (channels and value.shape[-1] not in channels):
        raise ValueError(f"{name} has invalid layout/channels")
    if any(not 1 <= size <= MAX_DIMENSION for size in value.shape[1:3]):
        raise ValueError(f"{name} dimensions exceed bounds")
    if value.numel() > MAX_ELEMENTS:
        raise ValueError(f"{name} exceeds element bound")
    if not value.dtype.is_floating_point:
        raise TypeError(f"{name} must be floating-point")
    if not torch.isfinite(value).all():
        raise ValueError(f"{name} must be finite")
    return value


def _masks(masks):
    _tensor(masks, 3, name="masks")
    if not 0 <= masks.shape[0] <= MAX_MASKS:
        raise ValueError("mask count exceeds bound")


def _images(base_image, candidates, channels=(3, 4)):
    _tensor(base_image, 4, channels, "base_image")
    _tensor(candidates, 4, channels, "candidates")
    if not 1 <= base_image.shape[0] <= MAX_BATCH or candidates.shape[0] > MAX_BATCH:
        raise ValueError("image batch exceeds bound")
    if base_image.shape[1:3] != candidates.shape[1:3]:
        raise ValueError("image geometry must match")
    if base_image.device != candidates.device:
        raise ValueError("image devices must match")


def _output(count, height, width, channels, work_factor=1):
    elements = count * height * width * channels
    if count > MAX_COMBINATIONS or elements > MAX_ELEMENTS:
        raise ValueError("combinatorial output exceeds bound")
    if elements * max(1, work_factor) > MAX_WORK:
        raise ValueError("compute work exceeds bound")


class PermuteMaskBatch(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="PermuteMaskBatch",
            display_name="Permute Mask Batch",
            category="mask",
            inputs=[io.Mask.Input("masks")],
            outputs=[io.Mask.Output("MASK")],
        )

    @classmethod
    def execute(cls, masks):
        _masks(masks)
        n, height, width = masks.shape
        _output(2**n, height, width, 1, n)
        return io.NodeOutput(*algorithm.PermuteMaskBatch().permuteMaskBatch(masks))


class CombinatorialDetailer(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="CombinatorialDetailer",
            display_name="Combinatorial Detailer",
            category="image",
            inputs=[
                io.Mask.Input("masks"),
                io.Image.Input("base_image"),
                io.Image.Input("candidates"),
            ],
            outputs=[io.Image.Output("IMAGE")],
        )

    @classmethod
    def execute(cls, masks, base_image, candidates):
        _masks(masks)
        _images(base_image, candidates, (3,))
        if (
            masks.shape[1:] != base_image.shape[1:3]
            or masks.device != base_image.device
        ):
            raise ValueError("mask geometry/device must match images")
        count = (candidates.shape[0] + 1) ** masks.shape[0]
        _output(count, *base_image.shape[1:3], 3, masks.shape[0])
        return io.NodeOutput(
            *algorithm.CombinatorialDetailer().combinatorialDetailer(
                masks, base_image, candidates
            )
        )


class FlattenAgainstOriginal(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="FlattenAgainstOriginal",
            display_name="Flatten Batch against Original",
            category="image",
            inputs=[io.Image.Input("base_image"), io.Image.Input("candidates")],
            outputs=[io.Image.Output("IMAGE")],
        )

    @classmethod
    def execute(cls, base_image, candidates):
        _images(base_image, candidates)
        _output(
            base_image.shape[0],
            *base_image.shape[1:3],
            base_image.shape[-1],
            candidates.shape[0],
        )
        return io.NodeOutput(
            *algorithm.FlattenAgainstOriginal().flattenAgainstOriginal(
                base_image, candidates
            )
        )


NODE_CLASS_MAPPINGS = {
    cls.__name__: cls
    for cls in (PermuteMaskBatch, CombinatorialDetailer, FlattenAgainstOriginal)
}
NODE_DISPLAY_NAME_MAPPINGS = {
    name: cls.define_schema().display_name for name, cls in NODE_CLASS_MAPPINGS.items()
}


class MaskPermutationExtension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint():
    return MaskPermutationExtension()
