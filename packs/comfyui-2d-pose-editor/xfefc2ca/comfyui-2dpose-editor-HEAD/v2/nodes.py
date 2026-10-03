"""Secure Nodes V2 backend for the 2D Pose Editor."""

from __future__ import annotations

import base64
import binascii
import hashlib
from io import BytesIO

import numpy as np
from PIL import Image, UnidentifiedImageError
import torch

from comfy_api.latest import io, sdk


MAX_DATA_URL_BYTES = 16 * 1024 * 1024
MAX_IMAGE_PIXELS = 4096 * 4096
VALID_MODES = ("Standard", "Background", "Custom")


def _decode_pose(value: str) -> Image.Image | None:
    if not value or not value.strip():
        return None
    if len(value.encode("utf-8")) > MAX_DATA_URL_BYTES:
        raise ValueError("image_data exceeds the 16 MiB limit")
    encoded = value.split(",", 1)[1] if "," in value else value
    try:
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > MAX_DATA_URL_BYTES:
            raise ValueError("decoded image exceeds the 16 MiB limit")
        with Image.open(BytesIO(raw)) as source:
            width, height = source.size
            if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                raise ValueError("pose image dimensions exceed the resource limit")
            source.load()
            return source.convert("RGBA")
    except (binascii.Error, UnidentifiedImageError, OSError, ValueError):
        # The legacy node deliberately falls back to an empty pose on malformed
        # editor data. Retain that behavior without accepting unbounded input.
        return None


def _tensor_to_rgba(tensor: torch.Tensor) -> Image.Image:
    if tensor.ndim != 4 or tensor.shape[0] < 1 or tensor.shape[-1] not in (1, 3, 4):
        raise ValueError("background_image must be a non-empty BHWC image tensor")
    height, width = int(tensor.shape[1]), int(tensor.shape[2])
    if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
        raise ValueError("background image dimensions exceed the resource limit")
    array = (tensor[0].detach().cpu().clamp(0, 1).numpy() * 255).round().astype(np.uint8)
    if array.shape[-1] == 1:
        array = np.repeat(array, 3, axis=-1)
    return Image.fromarray(array).convert("RGBA")


def _fit_contain(image: Image.Image, width: int, height: int) -> tuple[Image.Image, int, int]:
    scale = min(width / image.width, height / image.height)
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    resized = image.resize(size, Image.Resampling.LANCZOS)
    return resized, (width - size[0]) // 2, (height - size[1]) // 2


def compose_pose(
    image_data: str,
    output_size_mode: str,
    custom_width: int,
    custom_height: int,
    background: torch.Tensor | None,
) -> torch.Tensor:
    if output_size_mode not in VALID_MODES:
        raise ValueError(f"unknown output_size_mode: {output_size_mode}")
    if not 64 <= custom_width <= 4096 or not 64 <= custom_height <= 4096:
        raise ValueError("custom dimensions must be between 64 and 4096")

    pose = _decode_pose(image_data)
    backdrop = _tensor_to_rgba(background) if background is not None else None
    if output_size_mode == "Background" and backdrop is not None:
        width, height = backdrop.size
    elif output_size_mode == "Custom":
        width, height = custom_width, custom_height
    elif pose is not None:
        width, height = pose.size
    elif backdrop is not None:
        width, height = backdrop.size
    else:
        width, height = 600, 600

    result = Image.new("RGBA", (width, height), (224, 224, 224, 255))
    if backdrop is not None:
        if backdrop.size != (width, height):
            backdrop = backdrop.resize((width, height), Image.Resampling.LANCZOS)
        result.paste(backdrop, (0, 0))
    if pose is not None:
        foreground, x, y = _fit_contain(pose, width, height)
        result.paste(foreground, (x, y), foreground)

    array = np.asarray(result.convert("RGB"), dtype=np.float32) / 255.0
    return torch.from_numpy(array.copy()).unsqueeze(0)


class PoseEditor2D(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="PoseEditor2D",
            display_name="2D Pose Editor",
            category="2D Pose",
            inputs=[
                io.String.Input("image_data", default=""),
                io.Combo.Input(
                    "output_size_mode",
                    options=list(VALID_MODES),
                    default="Standard",
                ),
                io.Int.Input("custom_width", default=600, min=64, max=4096, step=8),
                io.Int.Input("custom_height", default=600, min=64, max=4096, step=8),
                io.Image.Input("background_image", optional=True),
            ],
            outputs=[io.Image.Output("image", display_name="image")],
        )

    @classmethod
    async def execute(
        cls,
        image_data: str,
        output_size_mode: str = "Standard",
        custom_width: int = 600,
        custom_height: int = 600,
        background_image: sdk.ImageRef | None = None,
    ) -> io.NodeOutput:
        background = await background_image.raw() if background_image is not None else None
        pixels = compose_pose(
            image_data,
            output_size_mode,
            int(custom_width),
            int(custom_height),
            background,
        )
        return io.NodeOutput(await sdk.ImageRef._from_raw(pixels))

    @classmethod
    async def fingerprint_inputs(
        cls,
        image_data: str,
        output_size_mode: str = "Standard",
        custom_width: int = 600,
        custom_height: int = 600,
        **_kwargs,
    ) -> str:
        key = f"{image_data}|{output_size_mode}|{custom_width}|{custom_height}"
        return hashlib.md5(key.encode()).hexdigest()


NODE_CLASS_MAPPINGS = {"PoseEditor2D": PoseEditor2D}
