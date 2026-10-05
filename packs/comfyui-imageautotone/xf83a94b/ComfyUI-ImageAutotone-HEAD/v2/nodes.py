"""Secure Nodes V2 implementation of Image Autotone."""

from __future__ import annotations

from typing import Any

import numpy as np
import torch

from comfy_api.latest import io, sdk


MAX_BATCH = 256
MAX_DIMENSION = 8192
MAX_ELEMENTS = 134_217_728


def _parse_rgb(value: str, label: str) -> np.ndarray:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    if value.startswith("#"):
        payload = value[1:]
        if len(payload) != 6:
            raise ValueError(f"{label} hex colors must contain exactly six digits")
        try:
            channels = tuple(bytes.fromhex(payload))
        except ValueError as error:
            raise ValueError(f"{label} contains invalid hex digits") from error
    else:
        parts = value.split(",")
        if len(parts) != 3:
            raise ValueError(f"{label} must contain exactly three RGB channels")
        try:
            channels = tuple(int(part) for part in parts)
        except ValueError as error:
            raise ValueError(f"{label} contains a non-integer RGB channel") from error
    if any(channel < 0 or channel > 255 for channel in channels):
        raise ValueError(f"{label} RGB channels must be in [0, 255]")
    return np.asarray(channels)


def _validate_image(value: Any) -> torch.Tensor:
    if not isinstance(value, torch.Tensor):
        raise TypeError("image must materialize as a tensor")
    if value.ndim != 4 or int(value.shape[-1]) not in (3, 4):
        raise ValueError("image must be a BHWC tensor with 3 or 4 channels")
    batch, height, width, _channels = (int(part) for part in value.shape)
    if not 1 <= batch <= MAX_BATCH:
        raise ValueError(f"image batch must be in [1, {MAX_BATCH}]")
    if not 1 <= height <= MAX_DIMENSION or not 1 <= width <= MAX_DIMENSION:
        raise ValueError(f"image dimensions must be in [1, {MAX_DIMENSION}]")
    if value.numel() > MAX_ELEMENTS:
        raise ValueError("image exceeds the element limit")
    if not value.dtype.is_floating_point:
        raise TypeError("image tensor must use a floating-point dtype")
    return value


def _calculate_adjustment_values(
    histogram: np.ndarray,
    total_pixels: int,
    clip_percent: float,
) -> tuple[int, int]:
    clip_threshold = total_pixels * clip_percent
    cumulative = histogram.cumsum()
    lower = np.where(cumulative > clip_threshold)[0][0]
    upper = np.where(cumulative < (total_pixels - clip_threshold))[0][-1]
    return int(lower), int(upper)


def _autotone(
    image: torch.Tensor,
    highlights: str,
    shadows: str,
    shadow_clip: float,
    highlight_clip: float,
) -> torch.Tensor:
    image = _validate_image(image)
    shadow_rgb = _parse_rgb(shadows, "shadows")
    highlight_rgb = _parse_rgb(highlights, "highlights")
    if not 0.0 <= shadow_clip <= 1.0 or not 0.0 <= highlight_clip <= 1.0:
        raise ValueError("clip percentages must be in [0, 1]")

    outputs: list[np.ndarray] = []
    for item in image:
        pixels = 255.0 * item.detach().cpu().numpy()
        total_pixels = int(pixels.shape[0] * pixels.shape[1])
        for channel in range(3):
            histogram, _ = np.histogram(
                pixels[:, :, channel].flatten(), bins=256, range=[0, 255]
            )
            dark, light = _calculate_adjustment_values(
                histogram, total_pixels, shadow_clip
            )
            _, highlight_light = _calculate_adjustment_values(
                histogram, total_pixels, highlight_clip
            )
            light = max(light, highlight_light)
            if light == dark:
                continue
            pixels[:, :, channel] = (
                (pixels[:, :, channel] - dark)
                * (highlight_rgb[channel] - shadow_rgb[channel])
                / (light - dark)
                + shadow_rgb[channel]
            )
            pixels[:, :, channel] = np.clip(pixels[:, :, channel], 0, 255)
        outputs.append(np.clip(pixels, 0, 255).astype(np.uint8))
    return torch.from_numpy(np.asarray(outputs).astype(np.float32) / 255.0)


class ImageAutotone(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ImageAutotone",
            display_name="Image Autotone",
            category="image",
            description=(
                "Clip color channels independently to increase contrast and "
                "alter color cast. This is a reinterpretation of Photoshop's "
                "Auto Tone algorithm."
            ),
            inputs=[
                io.Image.Input("image"),
                io.String.Input(
                    "shadows",
                    default="0,0,0",
                    tooltip=(
                        "Shadow color as comma-separated RGB or a six-digit "
                        "hex color."
                    ),
                ),
                io.String.Input(
                    "highlights",
                    default="255,255,255",
                    tooltip=(
                        "Highlight color as comma-separated RGB or a six-digit "
                        "hex color."
                    ),
                ),
                io.Float.Input(
                    "shadow_clip", default=0.001, min=0.0, max=1.0, step=0.001
                ),
                io.Float.Input(
                    "highlight_clip", default=0.001, min=0.0, max=1.0, step=0.001
                ),
            ],
            outputs=[io.Image.Output("IMAGE")],
        )

    @classmethod
    async def execute(
        cls,
        image: sdk.ImageRef,
        shadows: str,
        highlights: str,
        shadow_clip: float,
        highlight_clip: float,
    ) -> io.NodeOutput:
        output = _autotone(
            await image.raw(), highlights, shadows, shadow_clip, highlight_clip
        )
        return io.NodeOutput(await sdk.ImageRef._from_raw(output))


NODE_CLASS_MAPPINGS = {"ImageAutotone": ImageAutotone}
NODE_DISPLAY_NAME_MAPPINGS = {"ImageAutotone": "Image Autotone"}
