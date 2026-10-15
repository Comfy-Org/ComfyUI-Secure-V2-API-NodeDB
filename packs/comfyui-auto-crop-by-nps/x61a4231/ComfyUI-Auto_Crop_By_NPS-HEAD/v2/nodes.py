"""Stateless bounded wrappers for the pinned Pillow crop/expand/rotate algorithm."""

import math

import torch
from comfy_api.latest import ComfyExtension, io

from .algorithm import AutoCropByNPS as _Algorithm

MAX_DIMENSION = 8192
MAX_ELEMENTS = 16_777_216
MAX_BATCH = 64
CROP_NAMES = ("crop_top", "crop_bottom", "crop_left", "crop_right")


def _rotated_size(width, height, rotation):
    """Match default-center Pillow expand=True geometry without allocating pixels."""
    angle = (-rotation) % 360.0
    if angle in (0, 180):
        return width, height
    if angle in (90, 270):
        return height, width
    radians = -math.radians(angle)
    a, b = round(math.cos(radians), 15), round(math.sin(radians), 15)
    d, e = round(-math.sin(radians), 15), round(math.cos(radians), 15)
    center_x, center_y = width / 2, height / 2
    c = a * -center_x + b * -center_y + center_x
    f = d * -center_x + e * -center_y + center_y
    points = [
        (a * x + b * y + c, d * x + e * y + f)
        for x, y in ((0, 0), (width, 0), (width, height), (0, height))
    ]
    xs, ys = zip(*points)
    return math.ceil(max(xs)) - math.floor(min(xs)), math.ceil(max(ys)) - math.floor(
        min(ys)
    )


def _geometry(height, width, crop_top, crop_bottom, crop_left, crop_right, rotation):
    left = int(width * abs(crop_left)) if crop_left < 0 else 0
    right = width - int(width * abs(crop_right)) if crop_right < 0 else width
    top = int(height * abs(crop_top)) if crop_top < 0 else 0
    bottom = height - int(height * abs(crop_bottom)) if crop_bottom < 0 else height
    if right < left or bottom < top:
        raise ValueError("crop coordinates are inverted")
    padded_width = (
        right - left + sum(int(width * x) for x in (crop_left, crop_right) if x > 0)
    )
    padded_height = (
        bottom - top + sum(int(height * x) for x in (crop_top, crop_bottom) if x > 0)
    )
    if padded_width < 1 or padded_height < 1:
        raise ValueError("crop leaves an empty output")
    result = _rotated_size(padded_width, padded_height, rotation)
    for w, h in ((padded_width, padded_height), result):
        if w > MAX_DIMENSION or h > MAX_DIMENSION:
            raise ValueError("expanded/rotated dimensions exceed bound")
    return padded_width, padded_height, *result


def _validate(values, image, mask):
    for name, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (float, int)):
            raise TypeError(f"{name} must be a real number")
        limit = 180 if name == "rotation" else 1
        if not math.isfinite(value) or not -limit <= value <= limit:
            raise ValueError(f"{name} exceeds finite schema bounds")
    input_elements = output_elements = 0
    for name, tensor, rank in (("image", image, 4), ("mask", mask, 3)):
        if tensor is None:
            continue
        if not isinstance(tensor, torch.Tensor):
            raise TypeError(f"{name} must be a tensor")
        if tensor.ndim != rank or (name == "image" and tensor.shape[-1] not in (3, 4)):
            raise ValueError(f"{name} layout/channels are invalid")
        batch, height, width = tensor.shape[:3]
        if (
            batch > MAX_BATCH
            or not 2 <= height <= MAX_DIMENSION
            or not 2 <= width <= MAX_DIMENSION
        ):
            raise ValueError(f"{name} batch/dimensions exceed bound")
        input_elements += tensor.numel()
        if input_elements > MAX_ELEMENTS:
            raise ValueError("input elements exceed bound")
        if not tensor.dtype.is_floating_point:
            raise TypeError(f"{name} must be floating-point")
        if not torch.isfinite(tensor).all():
            raise ValueError(f"{name} must be finite")
        if batch:
            padded_w, padded_h, out_w, out_h = _geometry(height, width, **values)
            channels = tensor.shape[-1] if name == "image" else 1
            output_elements += (
                batch * max(padded_w * padded_h, out_w * out_h) * channels
            )
            if output_elements > MAX_ELEMENTS:
                raise ValueError("output elements exceed bound")


class AutoCropByNPS(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="AutoCropByNPS",
            display_name="Auto Crop by NPS",
            category="NPS1598",
            inputs=[
                *[
                    io.Float.Input(
                        name,
                        default=0,
                        min=-1.0,
                        max=1.0,
                        step=0.02,
                        display_mode=io.NumberDisplay.slider,
                    )
                    for name in CROP_NAMES
                ],
                io.Float.Input(
                    "rotation",
                    default=0,
                    min=-180,
                    max=180,
                    step=1,
                    display_mode=io.NumberDisplay.slider,
                ),
                io.Image.Input("image", optional=True),
                io.Mask.Input("mask", optional=True),
            ],
            outputs=[io.Image.Output("image"), io.Mask.Output("mask")],
        )

    @classmethod
    def execute(
        cls,
        crop_top,
        crop_bottom,
        crop_left,
        crop_right,
        rotation,
        image=None,
        mask=None,
    ):
        values = {
            "crop_top": crop_top,
            "crop_bottom": crop_bottom,
            "crop_left": crop_left,
            "crop_right": crop_right,
            "rotation": rotation,
        }
        _validate(values, image, mask)
        return io.NodeOutput(
            *_Algorithm().auto_crop_images(**values, image=image, mask=mask)
        )


NODE_CLASS_MAPPINGS = {"AutoCropByNPS": AutoCropByNPS}
NODE_DISPLAY_NAME_MAPPINGS = {"AutoCropByNPS": "Auto Crop by NPS"}


class AutoCropExtension(ComfyExtension):
    async def get_node_list(self):
        return [AutoCropByNPS]


async def comfy_entrypoint():
    return AutoCropExtension()
