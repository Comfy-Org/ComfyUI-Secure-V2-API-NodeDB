"""Mask crop helper retained in the untrusted pack runtime."""
from __future__ import annotations

import torch
from comfy_api.latest import io

from .._secure_runtime import image_value, mask_value, output_image


class MaskedSection(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Masked Section",
            display_name="Masked Section",
            category="image_filter/helpers",
            description="return the image cropped to only include the masked section",
            inputs=[
                io.Mask.Input("mask"),
                io.Image.Input("image"),
                io.Int.Input("minimum", default=512, min=16, max=16_384, tooltip="Minimum image size to output"),
            ],
            outputs=[io.Image.Output("image")],
        )

    @classmethod
    async def execute(cls, mask, image, minimum=512):
        mask_tensor = await mask_value(mask)
        image_tensor = await image_value(image)
        if mask_tensor is None or image_tensor is None:
            raise ValueError("Masked Section requires an IMAGE and MASK")
        bounds_mask = mask_tensor.squeeze()
        if bounds_mask.ndim != 2:
            raise ValueError("Masked Section requires one two-dimensional mask")
        height, width = bounds_mask.shape
        positions = torch.nonzero(bounds_mask > 0.5)
        if len(positions) < 2:
            return io.NodeOutput(image)

        min_x = int(torch.min(positions[:, 1]))
        max_x = int(torch.max(positions[:, 1]))
        min_y = int(torch.min(positions[:, 0]))
        max_y = int(torch.max(positions[:, 0]))
        x_pad = (int(minimum) - (max_x - min_x)) // 2
        y_pad = (int(minimum) - (max_y - min_y)) // 2
        if x_pad > 0:
            min_x = max(min_x - x_pad, 0)
            max_x = min(max_x + x_pad, width)
        if y_pad > 0:
            min_y = max(min_y - y_pad, 0)
            max_y = min(max_y + y_pad, height)
        cropped = image_tensor[:, min_y:max_y, min_x:max_x, :]
        return io.NodeOutput(await output_image(cropped))
