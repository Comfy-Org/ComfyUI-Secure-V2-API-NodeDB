"""Secure Nodes V2 conversion of AD Image Concatenation Advanced."""

from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image
import torch

from comfy_api.latest import io, sdk


DIRECTIONS = ["horizontal", "vertical"]
METHODS = ["lanczos", "bicubic", "bilinear", "nearest"]
MAX_BATCH = 256
MAX_DIMENSION = 16_384
MAX_PIXELS = 67_108_864

_SAMPLERS = {
    "lanczos": Image.Resampling.LANCZOS,
    "bicubic": Image.Resampling.BICUBIC,
    "bilinear": Image.Resampling.BILINEAR,
    "nearest": Image.Resampling.NEAREST,
}


def _validate_image(value: Any) -> torch.Tensor:
    if not isinstance(value, torch.Tensor):
        raise TypeError("image must materialize as a tensor")
    if value.ndim != 4 or int(value.shape[-1]) not in (1, 3, 4):
        raise ValueError("image must be a BHWC tensor with 1, 3, or 4 channels")
    batch, height, width, _channels = (int(part) for part in value.shape)
    if not 1 <= batch <= MAX_BATCH:
        raise ValueError(f"image batch must be in [1, {MAX_BATCH}]")
    if not 1 <= height <= MAX_DIMENSION or not 1 <= width <= MAX_DIMENSION:
        raise ValueError(f"image dimensions must be in [1, {MAX_DIMENSION}]")
    if height * width > MAX_PIXELS:
        raise ValueError("image exceeds the pixel limit")
    if not value.dtype.is_floating_point:
        raise TypeError("image tensor must use a floating-point dtype")
    return value


def _tensor_to_image(value: torch.Tensor) -> Image.Image:
    frame = _validate_image(value)[0].detach().cpu().numpy()
    pixels = (frame * 255).astype(np.uint8)
    if pixels.shape[-1] == 1:
        pixels = pixels[:, :, 0]
    return Image.fromarray(pixels)


def _image_to_tensor(value: Image.Image) -> torch.Tensor:
    pixels = np.array(value, copy=True)
    if pixels.ndim == 2:
        pixels = pixels[:, :, None]
    return torch.from_numpy(pixels).to(torch.float32).div_(255.0).unsqueeze(0)


def _check_output(width: int, height: int) -> None:
    if width > MAX_DIMENSION or height > MAX_DIMENSION or width * height > MAX_PIXELS:
        raise ValueError("concatenated image exceeds the output limit")


def _concat_two(
    first: Image.Image,
    second: Image.Image,
    direction: str,
    match_size: bool,
    method: str,
) -> Image.Image:
    if first.mode != second.mode:
        mode = "RGBA" if "A" in first.mode or "A" in second.mode else "RGB"
        first = first.convert(mode)
        second = second.convert(mode)

    sampler = _SAMPLERS[method]
    if match_size and direction == "horizontal" and first.height != second.height:
        new_height = second.height
        new_width = int(first.width * (new_height / first.height))
        _check_output(new_width, new_height)
        first = first.resize((new_width, new_height), sampler)
    elif match_size and direction == "vertical" and first.width != second.width:
        new_width = second.width
        new_height = int(first.height * (new_width / first.width))
        _check_output(new_width, new_height)
        first = first.resize((new_width, new_height), sampler)

    if direction == "horizontal":
        width, height = first.width + second.width, max(first.height, second.height)
    else:
        width, height = max(first.width, second.width), first.height + second.height
    _check_output(width, height)
    output = Image.new(first.mode, (width, height))
    if direction == "horizontal":
        output.paste(first, (0, (height - first.height) // 2))
        output.paste(second, (first.width, (height - second.height) // 2))
    else:
        output.paste(first, ((width - first.width) // 2, 0))
        output.paste(second, ((width - second.width) // 2, first.height))
    return output


def _concatenate(
    images: list[torch.Tensor], direction: str, match_size: bool, method: str
) -> torch.Tensor:
    if len(images) == 1:
        return images[0]
    result = _tensor_to_image(images[0])
    for image in images[1:]:
        result = _concat_two(result, _tensor_to_image(image), direction, match_size, method)
    return _image_to_tensor(result)


class ADImageConcatAdvanced(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="AD_image-concat-advanced",
            display_name="AD Image Concatenation Advanced",
            category="🌻 Addoor/image",
            inputs=[
                io.Image.Input("image1"),
                io.Combo.Input("direction", options=DIRECTIONS, default="horizontal"),
                io.Boolean.Input("match_size", default=True),
                io.Combo.Input("method", options=METHODS, default="lanczos"),
                io.Boolean.Input("output_all_concatenations", default=False),
                io.Image.Input("image2", optional=True),
                io.Image.Input("image3", optional=True),
                io.Image.Input("image4", optional=True),
                io.Image.Input("image5", optional=True),
            ],
            outputs=[io.Image.Output("IMAGE", is_output_list=True)],
        )

    @classmethod
    async def execute(
        cls,
        image1: sdk.ImageRef,
        direction: str = "horizontal",
        match_size: bool = False,
        method: str = "lanczos",
        output_all_concatenations: bool = False,
        image2: sdk.ImageRef | None = None,
        image3: sdk.ImageRef | None = None,
        image4: sdk.ImageRef | None = None,
        image5: sdk.ImageRef | None = None,
    ) -> io.NodeOutput:
        if direction not in DIRECTIONS or method not in METHODS:
            return io.NodeOutput([image1])
        refs = [image1] + [
            item for item in (image2, image3, image4, image5) if item is not None
        ]
        try:
            raw = [_validate_image(await item.raw()) for item in refs]
            if output_all_concatenations:
                tensors = [
                    _concatenate(raw[: index + 1], direction, match_size, method)
                    for index in range(len(raw))
                ]
            else:
                tensors = [_concatenate(raw, direction, match_size, method)]
            outputs = []
            for index, tensor in enumerate(tensors):
                if index == 0 and (len(raw) == 1 or output_all_concatenations):
                    outputs.append(image1)
                else:
                    outputs.append(await sdk.ImageRef._from_raw(tensor))
            return io.NodeOutput(outputs)
        except PermissionError:
            raise
        except Exception:
            return io.NodeOutput([image1])


NODE_CLASS_MAPPINGS = {"AD_image-concat-advanced": ADImageConcatAdvanced}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AD_image-concat-advanced": "AD Image Concatenation Advanced"
}
