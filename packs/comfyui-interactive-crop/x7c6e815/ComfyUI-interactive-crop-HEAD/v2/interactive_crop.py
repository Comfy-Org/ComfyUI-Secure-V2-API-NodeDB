"""Secure Nodes V2 implementation of Interactive Crop."""
from __future__ import annotations

from typing import Any

import torch
import torch.nn.functional as functional

from comfy_api.latest import io, sdk


INTERACTION_KIND = "image-choice"
INTERACTION_VARIANT = "interactive-crop.inline-v1"
INTERACTION_TIMEOUT_SECONDS = 240.0


def _preview_identity(display: Any) -> dict[str, str]:
    images = display.get("images") if isinstance(display, dict) else None
    if not isinstance(images, (list, tuple)) or not images:
        raise ValueError("Interactive Crop preview did not contain an image")
    value = images[0]
    if not isinstance(value, dict):
        raise TypeError("Interactive Crop preview identity must be an object")
    filename = value.get("filename", value.get("name"))
    folder = value.get("type", "temp")
    subfolder = value.get("subfolder", "") or ""
    if (
        not isinstance(filename, str)
        or not filename
        or len(filename.encode("utf-8")) > 1024
        or "/" in filename
        or "\\" in filename
        or "\0" in filename
    ):
        raise ValueError("Interactive Crop preview filename is invalid")
    if folder not in {"input", "output", "temp"}:
        raise ValueError("Interactive Crop preview folder is invalid")
    if (
        not isinstance(subfolder, str)
        or len(subfolder.encode("utf-8")) > 2048
        or subfolder.startswith(("/", "\\"))
        or "\\" in subfolder
        or any(part in {"", ".", ".."} for part in subfolder.split("/") if subfolder)
    ):
        raise ValueError("Interactive Crop preview subfolder is invalid")
    return {"filename": filename, "type": folder, "subfolder": subfolder}


def _coordinate(response: dict[str, Any], name: str) -> int:
    value = response.get(name)
    if type(value) is not int:
        raise TypeError(f"Interactive Crop response {name} must be an integer")
    return value


def _selection(
    response: Any, *, width: int, height: int,
) -> tuple[str, tuple[int, int, int, int] | None]:
    if not isinstance(response, dict):
        raise TypeError("Interactive Crop response must be an object")
    action = response.get("action")
    if action not in {"continue", "passthrough", "cancel"}:
        raise ValueError("Interactive Crop response action is invalid")
    if action != "continue":
        if set(response) != {"action"}:
            raise TypeError("Interactive Crop non-crop response has unsupported fields")
        return action, None
    expected = {"action", "x0", "y0", "x1", "y1"}
    if set(response) != expected:
        raise TypeError("Interactive Crop crop response has unsupported fields")

    x0, x1 = sorted((_coordinate(response, "x0"), _coordinate(response, "x1")))
    y0, y1 = sorted((_coordinate(response, "y0"), _coordinate(response, "y1")))
    x0 = max(0, min(width - 1, x0))
    x1 = max(0, min(width, x1))
    y0 = max(0, min(height - 1, y0))
    y1 = max(0, min(height, y1))
    return action, (x0, y0, x1, y1)


def _resize_to(tensor: torch.Tensor, height: int, width: int) -> torch.Tensor:
    if tensor.ndim != 4:
        raise ValueError("Interactive Crop expects IMAGE tensors in BHWC layout")
    if tuple(tensor.shape[1:3]) == (height, width):
        return tensor
    channels_first = tensor.permute(0, 3, 1, 2)
    resized = functional.interpolate(
        channels_first,
        size=(height, width),
        mode="bilinear",
        align_corners=False,
    )
    return resized.permute(0, 2, 3, 1).contiguous()


class InteractiveCrop(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw", "ui", "ui.interact", "execution.interrupt")

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="InteractiveCrop",
            display_name="Interactive Crop",
            category="image",
            inputs=[
                io.Image.Input("image"),
                io.Boolean.Input("force_original_ratio", default=False),
                io.Boolean.Input("resize_to_original", default=False),
            ],
            outputs=[
                io.Image.Output("image"),
                io.Boolean.Output("did_crop"),
            ],
            hidden=[
                io.Hidden.unique_id,
                io.Hidden.prompt,
                io.Hidden.extra_pnginfo,
            ],
        )

    @classmethod
    async def execute(
        cls,
        image: sdk.ImageRef,
        force_original_ratio: bool,
        resize_to_original: bool,
    ) -> io.NodeOutput:
        height, width = await image.spatial_shape()
        height, width = int(height), int(width)
        if height < 1 or width < 1:
            raise ValueError("Interactive Crop needs a non-empty IMAGE")

        preview = _preview_identity(await sdk.ctx().ui.preview_images(image))
        response = await sdk.ctx().interact.request(
            INTERACTION_KIND,
            {
                "variant": INTERACTION_VARIANT,
                "image": preview,
                "width": width,
                "height": height,
                "force_original_ratio": bool(force_original_ratio),
            },
            timeout=INTERACTION_TIMEOUT_SECONDS,
        )
        action, rectangle = _selection(response, width=width, height=height)
        if action == "cancel":
            await sdk.ctx().execution.interrupt()
            raise RuntimeError("InteractiveCrop: user cancelled")
        if action == "passthrough" or rectangle is None:
            return io.NodeOutput(image, False)

        x0, y0, x1, y1 = rectangle
        if x1 <= x0 or y1 <= y0:
            return io.NodeOutput(image, False)

        raw = await image.raw()
        if not isinstance(raw, torch.Tensor) or raw.ndim != 4:
            raise ValueError("Interactive Crop expects IMAGE tensors in BHWC layout")
        cropped = raw[:, y0:y1, x0:x1, :].contiguous()
        if resize_to_original:
            cropped = _resize_to(cropped, height, width)
        return io.NodeOutput(await sdk.ImageRef._from_raw(cropped), True)


NODE_CLASS_MAPPINGS = {"InteractiveCrop": InteractiveCrop}
NODE_DISPLAY_NAME_MAPPINGS = {"InteractiveCrop": "Interactive Crop"}

__all__ = ["InteractiveCrop", "NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
