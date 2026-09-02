"""Sandboxed image scaling implementation for the pinned upstream pack."""
from __future__ import annotations

import math

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

from comfy_api.latest import io, sdk


def _lanczos(samples: torch.Tensor, width: int, height: int) -> torch.Tensor:
    """Match ComfyUI's Lanczos helper without importing host internals."""
    if samples.ndim == 4:
        samples = (
            samples.squeeze(1)
            if samples.shape[1] == 1
            else samples.movedim(1, -1)
        )
    images = [
        Image.fromarray(
            np.clip(255.0 * image.cpu().numpy(), 0, 255).astype(np.uint8)
        )
        for image in samples
    ]
    images = [
        image.resize((width, height), resample=Image.Resampling.LANCZOS)
        for image in images
    ]
    tensors = []
    for image in images:
        value = np.array(image).astype(np.float32) / 255.0
        tensors.append(
            torch.from_numpy(value).movedim(-1, 0)
            if value.ndim == 3
            else torch.from_numpy(value)
        )
    return torch.stack(tensors).to(samples.device, samples.dtype)


class ImageScaleToTotalPixelsX(io.ComfyNode):
    """Resize an image to a target pixel count or explicit resolution."""

    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    upscale_methods = [
        "nearest-exact",
        "bilinear",
        "area",
        "bicubic",
        "lanczos",
    ]
    resize_modes = ["stretch", "crop", "pad"]

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ImageScaleToTotalPixelsX",
            display_name="Scale Image to Total Pixels Adv",
            category="image/upscaling",
            inputs=[
                io.Image.Input("image"),
                io.Float.Input(
                    "megapixels",
                    default=1.05,
                    min=0.0,
                    max=16.0,
                    step=0.01,
                ),
                io.Int.Input(
                    "multiple_of",
                    default=16,
                    min=1,
                    max=128,
                    step=1,
                ),
                io.Combo.Input(
                    "resize_mode",
                    options=cls.resize_modes,
                    default="crop",
                ),
                io.Combo.Input(
                    "upscale_method",
                    options=cls.upscale_methods,
                    default="lanczos",
                ),
                io.Int.Input("width", optional=True, force_input=True),
                io.Int.Input("height", optional=True, force_input=True),
            ],
            outputs=[
                io.Image.Output("image"),
                io.Int.Output("width"),
                io.Int.Output("height"),
            ],
            hidden=[io.Hidden.unique_id],
            is_output_node=True,
        )

    @classmethod
    async def execute(
        cls,
        image: sdk.ImageRef,
        megapixels: float,
        multiple_of: int,
        resize_mode: str,
        upscale_method: str,
        width: int | None = None,
        height: int | None = None,
    ) -> io.NodeOutput:
        image_value = await image.raw()
        _, original_height, original_width, _ = image_value.shape
        manual_resolution = width is not None and height is not None

        if manual_resolution:
            target_width = int(width)
            target_height = int(height)
        elif megapixels == 0:
            target_width = original_width
            target_height = original_height
        else:
            total = int(megapixels * 1_000_000)
            scale_by = math.sqrt(total / (original_width * original_height))
            target_width = round(original_width * scale_by)
            target_height = round(original_height * scale_by)

        if multiple_of > 1:
            target_width -= target_width % multiple_of
            target_height -= target_height % multiple_of

        target_width = max(multiple_of, target_width)
        target_height = max(multiple_of, target_height)

        resize_width = target_width
        resize_height = target_height

        x = y = x2 = y2 = 0
        pad_left = pad_right = pad_top = pad_bottom = 0

        if resize_mode == "pad":
            ratio = min(
                target_width / original_width,
                target_height / original_height,
            )
            new_width = round(original_width * ratio)
            new_height = round(original_height * ratio)

            pad_left = (target_width - new_width) // 2
            pad_right = target_width - new_width - pad_left
            pad_top = (target_height - new_height) // 2
            pad_bottom = target_height - new_height - pad_top

            resize_width = new_width
            resize_height = new_height

        elif resize_mode == "crop":
            ratio = max(
                target_width / original_width,
                target_height / original_height,
            )
            new_width = round(original_width * ratio)
            new_height = round(original_height * ratio)

            x = (new_width - target_width) // 2
            y = (new_height - target_height) // 2
            x2 = x + target_width
            y2 = y + target_height

            if x2 > new_width:
                x -= x2 - new_width
            if x < 0:
                x = 0

            if y2 > new_height:
                y -= y2 - new_height
            if y < 0:
                y = 0

            resize_width = new_width
            resize_height = new_height

        samples = image_value.permute(0, 3, 1, 2)

        if upscale_method == "lanczos":
            outputs = _lanczos(samples, resize_width, resize_height)
        else:
            outputs = F.interpolate(
                samples,
                size=(resize_height, resize_width),
                mode=upscale_method,
            )

        if resize_mode == "pad" and any(
            (pad_left, pad_right, pad_top, pad_bottom)
        ):
            outputs = F.pad(
                outputs,
                (pad_left, pad_right, pad_top, pad_bottom),
                value=0,
            )

        outputs = outputs.permute(0, 2, 3, 1)

        if resize_mode == "crop" and any((x, y, x2, y2)):
            outputs = outputs[:, y:y2, x:x2, :]

        if multiple_of > 1 and (
            outputs.shape[2] % multiple_of != 0
            or outputs.shape[1] % multiple_of != 0
        ):
            final_width = outputs.shape[2]
            final_height = outputs.shape[1]

            x = (final_width % multiple_of) // 2
            y = (final_height % multiple_of) // 2
            x2 = final_width - ((final_width % multiple_of) - x)
            y2 = final_height - ((final_height % multiple_of) - y)

            outputs = outputs[:, y:y2, x:x2, :]

        outputs = torch.clamp(outputs, 0, 1)

        final_width = outputs.shape[2]
        final_height = outputs.shape[1]
        image_ref = await sdk.ImageRef._from_raw(outputs)

        return io.NodeOutput(
            image_ref,
            final_width,
            final_height,
            ui={"text": [f"{final_width} x {final_height}"]},
        )


__all__ = ["ImageScaleToTotalPixelsX"]
