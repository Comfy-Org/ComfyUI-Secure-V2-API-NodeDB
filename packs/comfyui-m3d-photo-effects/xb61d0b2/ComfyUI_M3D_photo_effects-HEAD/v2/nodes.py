"""Secure Nodes V2 conversion of M3D Photo Effects."""

from __future__ import annotations

import numpy as np
import torch
from comfy_api.latest import ComfyExtension, io
from PIL import Image, ImageEnhance

MAX_DIMENSION = 8192
MAX_PIXELS = 33_554_432


def _validate_image(image: torch.Tensor) -> None:
    if not isinstance(image, torch.Tensor) or image.ndim != 4:
        raise TypeError("image must be a BHWC tensor")
    if image.shape[0] != 1:
        raise ValueError("M3D photo effects require exactly one image")
    if image.shape[-1] not in (3, 4):
        raise ValueError("image must contain RGB or RGBA channels")
    height, width = image.shape[1:3]
    if height < 1 or width < 1 or height > MAX_DIMENSION or width > MAX_DIMENSION:
        raise ValueError("image dimensions are outside the secure bound")
    if height * width > MAX_PIXELS:
        raise ValueError("image exceeds the secure pixel bound")


def tanh(value, slope=3.5, offset=0.5):
    return np.tanh(slope * (value - offset))


def normalized_tanh(value, slope=3.5, offset=0.5):
    return (tanh(value, slope, offset) - tanh(0, slope, offset)) / (
        tanh(1, slope, offset) - tanh(0, slope, offset)
    )


def overlay(base: np.ndarray, top: np.ndarray, factor=0.9):
    lower = base < 0.5
    upper = base >= 0.5
    result = np.zeros_like(base)
    result[lower] = 2 * base[lower] * top[lower]
    result[upper] = 1 - 2 * (1 - base[upper]) * (1 - top[upper])
    return result * factor


def bleach_bypass(
    image: np.ndarray,
    slope=3.5,
    offset=0.5,
    desaturation=0.75,
    strength=0.9,
):
    source = Image.fromarray((image * 255).astype(np.uint8))
    enhancer = ImageEnhance.Color(source)
    base = enhancer.enhance(1 - desaturation)
    base_array = normalized_tanh(np.asarray(base) / 255.0, slope, offset)
    top = enhancer.enhance(desaturation)
    top_array = np.asarray(top) / 255.0
    return overlay(base_array, top_array, strength)


class BleachBypass(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Bleach Bypass",
            display_name="Bleach Bypass",
            category="M3D/image-effects/curve",
            description=(
                'Apply the "bleach bypass" effect to the input image.\n\n'
                'This effect is well-known in movies like "300",\n'
                "it enforces shadows and desaturates the image.\n"
                "To ensure a good result, keep the slope value between 2 and 5.\n"
                "If your image is overexposed, you can increase the shadow offset.\n"
                "At the opposite, if your image is underexposed, you can decrease "
                "the shadow offset.\n"
            ),
            inputs=[
                io.Image.Input("image"),
                io.Float.Input(
                    "slope",
                    min=1.0,
                    max=50,
                    step=0.1,
                    default=4,
                    tooltip="The slope of the S-curve. keep value from 2 to 10 to expect good results.",
                ),
                io.Float.Input(
                    "shadow_offset",
                    min=0.0,
                    max=1.0,
                    step=0.01,
                    default=0.5,
                    tooltip="The shadow offset of the image. keep value near 0.5. If >0.5 the shadows are more present, <0.5 the lights are more present.",
                ),
                io.Float.Input(
                    "desaturation",
                    min=0.0,
                    max=1.0,
                    step=0.01,
                    default=0.8,
                    tooltip="The input desaturation (1-value) of the image. keep value near 0.7 to 0.9 for common effect.",
                ),
                io.Float.Input(
                    "overlay_strength",
                    min=0.0,
                    max=1.0,
                    step=0.01,
                    default=0.9,
                    tooltip="The strength of the overlay effect. keep value near 0.8 to 1.0 for common effect.",
                ),
            ],
            outputs=[io.Image.Output("image")],
        )

    @classmethod
    def execute(
        cls, image, slope, shadow_offset, desaturation, overlay_strength
    ) -> io.NodeOutput:
        _validate_image(image)
        value = image.numpy().squeeze(0)
        result = bleach_bypass(
            value,
            slope=slope,
            offset=shadow_offset,
            desaturation=desaturation,
            strength=overlay_strength,
        )
        return io.NodeOutput(torch.from_numpy(np.expand_dims(result, axis=0)))


class RGBCurve(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="RGB Curve",
            display_name="RGB Curve",
            category="M3D/image-effects/curve",
            description=(
                "Apply a RGB curve to the input image at once.\n\n"
                "This node apply a correction to the all channels of the image at once.\n"
                "It helps to enhance the contrast and the colors of the image.\n"
            ),
            inputs=[
                io.Image.Input("image"),
                io.Float.Input(
                    "slope",
                    min=1.0,
                    max=50,
                    step=0.1,
                    default=4,
                    tooltip="The slope of the S-curve. keep value from 2 to 10 to expect good results.",
                ),
                io.Float.Input(
                    "shadow_offset",
                    min=0.0,
                    max=1.0,
                    step=0.01,
                    default=0.5,
                    tooltip="The shadow offset of the image. keep value near 0.5. If >0.5 the shadows are more present, <0.5 the lights are more present.",
                ),
            ],
            outputs=[io.Image.Output("image")],
        )

    @classmethod
    def execute(cls, image, slope, shadow_offset) -> io.NodeOutput:
        _validate_image(image)
        value = image.numpy().squeeze(0)
        result = normalized_tanh(value, slope, shadow_offset)
        return io.NodeOutput(torch.from_numpy(np.expand_dims(result, axis=0)))


NODE_CLASS_MAPPINGS = {"Bleach Bypass": BleachBypass, "RGB Curve": RGBCurve}


class M3DPhotoEffectsExtension(ComfyExtension):
    async def get_node_list(self):
        return [BleachBypass, RGBCurve]


async def comfy_entrypoint() -> M3DPhotoEffectsExtension:
    return M3DPhotoEffectsExtension()
