"""Bounded pack-local tile algorithms; TILE_INFO is data, never host authority."""

from __future__ import annotations

import math

import torch
from comfy_api.latest import ComfyExtension, io

from . import algorithm

TILE_INFO = io.Custom("TILE_INFO")
MAX_ELEMENTS = 16_777_216
MAX_WORK_ELEMENTS = 33_554_432
MAX_DIMENSION = 8192
MAX_TILES = 512
MAX_BATCH = 64


def _int(name, value, low, high):
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if not low <= value <= high:
        raise ValueError(f"{name} exceeds bounds [{low}, {high}]")
    return value


def _ratio(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise TypeError("feather_ratio must be a number")
    if not 0 <= value <= 0.5 or not math.isfinite(value):
        raise ValueError("feather_ratio exceeds bounds")


def _image(value, *, empty=False, tiles=False):
    if not isinstance(value, torch.Tensor):
        raise TypeError("image must be a tensor")
    if value.ndim != 4 or value.layout != torch.strided:
        raise ValueError("image must be a strided BHWC tensor")
    if not value.dtype.is_floating_point:
        raise TypeError("image must be floating-point")
    batch, height, width, channels = value.shape
    _int("batch", batch, 0 if empty else 1, MAX_TILES if tiles else MAX_BATCH)
    _int("height", height, 1, MAX_DIMENSION)
    _int("width", width, 1, MAX_DIMENSION)
    _int("channels", channels, 1, 4)
    if value.numel() > MAX_ELEMENTS:
        raise ValueError("input element count exceeds bounds")
    return batch, height, width, channels


def _validate_split(image, tile_width, tile_height, overlap, feather_ratio):
    batch, height, width, channels = _image(image)
    _int("tile_width", tile_width, 64, 8192)
    _int("tile_height", tile_height, 64, 8192)
    _int("overlap", overlap, 0, 512)
    _ratio(feather_ratio)
    tw, th = min(tile_width, width), min(tile_height, height)
    cols = math.ceil((width - overlap) / max(1, tw - overlap))
    rows = math.ceil((height - overlap) / max(1, th - overlap))
    count = batch * max(0, rows) * max(0, cols)
    if batch * max(0, rows) > MAX_TILES:
        raise ValueError("projected row loop count exceeds bounds")
    if count > MAX_TILES:
        raise ValueError("projected tile count exceeds bounds")
    # Empty-grid legacy fallback returns the original batch and a single 2D mask.
    work = count * th * tw * (channels + 1) if count else image.numel() + height * width
    if work > MAX_WORK_ELEMENTS:
        raise ValueError("projected split output exceeds bounds")


def _validate_merge(images, tile_info):
    count, _, _, input_channels = _image(images, empty=True, tiles=True)
    if not isinstance(tile_info, dict):
        raise TypeError("tile_info must be a dictionary")
    allowed = {
        "original_height",
        "original_width",
        "tile_width",
        "tile_height",
        "overlap",
        "feather_ratio",
        "batch_size",
        "positions",
    }
    if not set(tile_info) <= allowed:
        raise ValueError("tile_info has undeclared fields")
    required = allowed - {"batch_size"}
    if not required <= set(tile_info):
        raise ValueError("tile_info is missing fields")
    height = _int("original_height", tile_info["original_height"], 1, MAX_DIMENSION)
    width = _int("original_width", tile_info["original_width"], 1, MAX_DIMENSION)
    batch = _int("batch_size", tile_info.get("batch_size", 1), 1, MAX_BATCH)
    th = _int("tile_height", tile_info["tile_height"], 1, MAX_DIMENSION)
    tw = _int("tile_width", tile_info["tile_width"], 1, MAX_DIMENSION)
    _int("overlap", tile_info["overlap"], 0, 512)
    _ratio(tile_info["feather_ratio"])
    positions = tile_info["positions"]
    if not isinstance(positions, list):
        raise TypeError("positions must be a list")
    if len(positions) > MAX_TILES:
        raise ValueError("position count exceeds bounds")
    channels = (
        input_channels if count else 3
    )  # Preserve upstream empty-input RGB fallback.
    processed = min(count, len(positions))
    accumulators = batch * height * width * (channels + 1)
    slots = processed * th * tw * (channels + 1)
    if accumulators + slots > MAX_WORK_ELEMENTS:
        raise ValueError("projected merge output/work exceeds bounds")
    for pos in positions:
        if not isinstance(pos, dict):
            raise TypeError("position must be a dictionary")
        if not {"batch_index", "x", "y"} <= set(pos) or not set(pos) <= {
            "batch_index",
            "x",
            "y",
            "row",
            "col",
        }:
            raise ValueError("position has invalid fields")
        _int("batch_index", pos["batch_index"], 0, batch - 1)
        _int("x", pos["x"], 0, width - 1)
        _int("y", pos["y"], 0, height - 1)
        for key in ("row", "col"):
            if key in pos:
                _int(key, pos[key], 0, MAX_DIMENSION)
        if pos["x"] + tw > width or pos["y"] + th > height:
            raise ValueError("position tile lies outside the original canvas")


class TiledImageSplitter(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="TiledImageSplitter",
            display_name="Tiled Image Splitter",
            category="TiledNodes",
            inputs=[
                io.Image.Input("image"),
                io.Int.Input("tile_width", default=1024, min=64, max=8192, step=8),
                io.Int.Input("tile_height", default=1024, min=64, max=8192, step=8),
                io.Int.Input("overlap", default=128, min=0, max=512, step=8),
                io.Float.Input(
                    "feather_ratio", default=0.1, min=0.0, max=0.5, step=0.01
                ),
            ],
            outputs=[
                io.Image.Output("tiles"),
                io.Mask.Output("masks"),
                TILE_INFO.Output("tile_info"),
            ],
        )

    @classmethod
    def execute(cls, image, tile_width, tile_height, overlap, feather_ratio):
        _validate_split(image, tile_width, tile_height, overlap, feather_ratio)
        return io.NodeOutput(
            *algorithm.TiledImageSplitter().split(
                image, tile_width, tile_height, overlap, feather_ratio
            )
        )


class TiledImageMerger(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="TiledImageMerger",
            display_name="Tiled Image Merger",
            category="TiledNodes",
            inputs=[io.Image.Input("images"), TILE_INFO.Input("tile_info")],
            outputs=[io.Image.Output("image")],
        )

    @classmethod
    def execute(cls, images, tile_info):
        _validate_merge(images, tile_info)
        return io.NodeOutput(*algorithm.TiledImageMerger().merge(images, tile_info))


NODE_CLASS_MAPPINGS = {
    "TiledImageSplitter": TiledImageSplitter,
    "TiledImageMerger": TiledImageMerger,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "TiledImageSplitter": "Tiled Image Splitter",
    "TiledImageMerger": "Tiled Image Merger",
}


class TiledImageExtension(ComfyExtension):
    async def get_node_list(self):
        return [TiledImageSplitter, TiledImageMerger]


async def comfy_entrypoint():
    return TiledImageExtension()
