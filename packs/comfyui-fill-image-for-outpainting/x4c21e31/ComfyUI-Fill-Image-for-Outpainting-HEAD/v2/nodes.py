"""Secure Nodes V2 conversion of Fill Image for Outpainting."""

from __future__ import annotations

import cv2
import numpy as np
import scipy.signal
import torch
from comfy_api.latest import ComfyExtension, io

FILL_METHODS = ["cv2_ns", "cv2_telea", "edge_pad"]
MAX_DIMENSION = 8192
MAX_PIXELS = 33_554_432


def _validate_inputs(image: torch.Tensor, mask: torch.Tensor) -> None:
    if not isinstance(image, torch.Tensor) or image.ndim != 4:
        raise TypeError("image must be a BHWC tensor")
    if image.shape[0] < 1:
        raise ValueError("image batch must not be empty")
    if image.shape[-1] != 3:
        raise ValueError("image must contain exactly three RGB channels")
    if not isinstance(mask, torch.Tensor) or mask.ndim != 2:
        raise TypeError("mask must be a two-dimensional tensor")
    height, width = image.shape[1:3]
    if tuple(mask.shape) != (height, width):
        raise ValueError("image and mask dimensions must match")
    if height < 1 or width < 1 or height > MAX_DIMENSION or width > MAX_DIMENSION:
        raise ValueError("image dimensions are outside the secure bound")
    if height * width > MAX_PIXELS:
        raise ValueError("image exceeds the secure pixel bound")


def edge_pad(img: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mask = 255 - mask
    record: dict[tuple[int, int], int] = {}
    kernel = [[1] * 3 for _ in range(3)]
    nmask = mask.copy()
    nmask[nmask > 0] = 1
    res = scipy.signal.convolve2d(
        nmask, kernel, mode="same", boundary="fill", fillvalue=1
    )
    res[nmask < 1] = 0
    res[res == 9] = 0
    res[res > 0] = 1
    y_values, x_values = res.nonzero()
    queue = [(y, x) for y, x in zip(y_values, x_values)]
    count = res.astype(np.float32)
    accumulator = img.astype(np.float32)
    step = 1
    height, width = accumulator.shape[:2]
    offsets = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    while queue:
        target = []
        for y, x in queue:
            value = accumulator[y][x]
            for y_offset, x_offset in offsets:
                next_y = y + y_offset
                next_x = x + x_offset
                if (
                    0 <= next_y < height
                    and 0 <= next_x < width
                    and nmask[next_y][next_x] < 1
                    and record.get((next_y, next_x), step) == step
                ):
                    accumulator[next_y][next_x] = (
                        accumulator[next_y][next_x] * count[next_y][next_x] + value
                    )
                    count[next_y][next_x] += 1
                    accumulator[next_y][next_x] /= count[next_y][next_x]
                    if (next_y, next_x) not in record:
                        record[(next_y, next_x)] = step
                        target.append((next_y, next_x))
        step += 1
        queue = target
    return accumulator.astype(np.uint8), 255 - mask


class FillImageForOutpainting(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="FillImageForOutpainting",
            display_name="Fill Image For Outpainting",
            category="image",
            inputs=[
                io.Image.Input("image"),
                io.Mask.Input("mask"),
                io.Combo.Input(
                    "fill_method", options=FILL_METHODS, default="cv2_ns"
                ),
            ],
            outputs=[io.Image.Output(), io.Mask.Output()],
        )

    @classmethod
    def execute(cls, image, mask, fill_method) -> io.NodeOutput:
        _validate_inputs(image, mask)
        if fill_method not in FILL_METHODS:
            raise ValueError(f"unsupported fill method: {fill_method}")

        image_value = (image.numpy() * 255).astype(np.uint8)[0]
        mask_value = (mask.numpy() * 255).astype(np.uint8)
        if fill_method == "cv2_ns":
            result = cv2.inpaint(image_value, mask_value, 5, cv2.INPAINT_NS)
        elif fill_method == "cv2_telea":
            result = cv2.inpaint(image_value, mask_value, 5, cv2.INPAINT_TELEA)
        else:
            result, mask_value = edge_pad(image_value, mask_value)

        result_image = torch.from_numpy(result) / 255.0
        result_mask = torch.from_numpy(mask_value) / 255.0
        return io.NodeOutput(result_image.unsqueeze(0), result_mask)


NODE_CLASS_MAPPINGS = {"FillImageForOutpainting": FillImageForOutpainting}
NODE_DISPLAY_NAME_MAPPINGS = {
    "FillImageForOutpainting": "Fill Image For Outpainting"
}


class FillImageForOutpaintingExtension(ComfyExtension):
    async def get_node_list(self):
        return [FillImageForOutpainting]


async def comfy_entrypoint() -> FillImageForOutpaintingExtension:
    return FillImageForOutpaintingExtension()
