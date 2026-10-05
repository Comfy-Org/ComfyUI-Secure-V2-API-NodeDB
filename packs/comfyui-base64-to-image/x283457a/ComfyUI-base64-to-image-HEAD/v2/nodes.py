"""Secure Nodes V2 conversion of comfyui-base64-to-image."""

from __future__ import annotations

import base64
import binascii
from io import BytesIO

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError
import torch

from comfy_api.latest import ComfyExtension, io


MAX_ENCODED_BYTES = 16 * 1024 * 1024
MAX_DECODED_BYTES = 12 * 1024 * 1024
MAX_DIMENSION = 8192
MAX_PIXELS = 33_554_432


def _decode_payload(data: str) -> bytes:
    if not isinstance(data, str):
        raise TypeError("data must be a base64 string")
    try:
        encoded_size = len(data.encode("ascii"))
    except UnicodeEncodeError as exc:
        raise ValueError("data must contain ASCII base64 text") from exc
    if encoded_size > MAX_ENCODED_BYTES:
        raise ValueError(
            f"base64 input exceeds the {MAX_ENCODED_BYTES}-byte limit"
        )
    try:
        payload = base64.b64decode(data)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("data is not valid base64") from exc
    if not payload:
        raise ValueError("base64 payload is empty")
    if len(payload) > MAX_DECODED_BYTES:
        raise ValueError(
            f"decoded image exceeds the {MAX_DECODED_BYTES}-byte limit"
        )
    return payload


def _validate_image_header(payload: bytes) -> tuple[int, int]:
    try:
        with Image.open(BytesIO(payload)) as image:
            width, height = image.size
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError("decoded payload is not a supported image") from exc
    if width < 1 or height < 1:
        raise ValueError("decoded image dimensions must be positive")
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise ValueError(
            f"decoded image dimensions exceed {MAX_DIMENSION} pixels"
        )
    if width * height > MAX_PIXELS:
        raise ValueError(f"decoded image exceeds the {MAX_PIXELS}-pixel limit")
    return width, height


def decode_image(data: str) -> tuple[torch.Tensor, torch.Tensor]:
    """Decode with the same OpenCV channel semantics as the pinned upstream."""

    payload = _decode_payload(data)
    expected_width, expected_height = _validate_image_header(payload)
    encoded = np.frombuffer(payload, np.uint8)
    decoded = cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED)
    if decoded is None:
        raise ValueError("decoded payload is not a supported image")
    if decoded.ndim != 3 or decoded.shape[2] not in (3, 4):
        raise ValueError("decoded image must have RGB or RGBA channels")
    height, width = decoded.shape[:2]
    if (width, height) != (expected_width, expected_height):
        raise ValueError("decoded image dimensions changed during decoding")

    if decoded.shape[2] == 4:
        mask = torch.from_numpy(
            decoded[:, :, 3].astype(np.float32) / 255.0
        )
        rgb = cv2.cvtColor(decoded, cv2.COLOR_BGRA2RGB)
    else:
        mask = torch.ones((height, width), dtype=torch.float32, device="cpu")
        rgb = cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)

    image = torch.from_numpy(rgb.astype(np.float32) / 255.0).unsqueeze(0)
    return image, mask.unsqueeze(0)


class LoadImageFromBase64(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="LoadImageFromBase64",
            display_name="Load Image From Base64",
            category="image",
            inputs=[io.String.Input("data", default="")],
            outputs=[io.Image.Output(), io.Mask.Output()],
        )

    @classmethod
    def execute(cls, data: str) -> io.NodeOutput:
        image, mask = decode_image(data)
        return io.NodeOutput(image, mask)


NODE_CLASS_MAPPINGS = {"LoadImageFromBase64": LoadImageFromBase64}
NODE_DISPLAY_NAME_MAPPINGS = {
    "LoadImageFromBase64": "Load Image From Base64",
}


class Base64ToImageExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [LoadImageFromBase64]


async def comfy_entrypoint() -> Base64ToImageExtension:
    return Base64ToImageExtension()
