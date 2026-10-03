"""Secure Nodes V2 backend for 360-degree panorama previews."""

from __future__ import annotations

import numpy as np
from PIL import Image
import torch

from comfy_api.latest import io, sdk


MAX_DIMENSION = 8192
MAX_IMAGE_PIXELS = 32 * 1024 * 1024
MAX_VIDEO_FRAMES = 512
MAX_VIDEO_PIXELS = 128 * 1024 * 1024


def _validate_image_batch(value: torch.Tensor, *, video: bool) -> torch.Tensor:
    if not isinstance(value, torch.Tensor) or value.ndim != 4:
        label = "video_frames" if video else "images"
        raise ValueError(f"{label} must be a BHWC image tensor")
    batch, height, width, channels = (int(part) for part in value.shape)
    if batch < 1 or height < 1 or width < 1 or channels not in (1, 3, 4):
        raise ValueError("image input must contain non-empty 1, 3, or 4 channel frames")
    if width > MAX_DIMENSION or height > MAX_DIMENSION or width * height > MAX_IMAGE_PIXELS:
        raise ValueError("image dimensions exceed the preview resource limit")
    if video and batch > MAX_VIDEO_FRAMES:
        raise ValueError(f"video frame count exceeds the {MAX_VIDEO_FRAMES}-frame limit")
    if video and batch * width * height > MAX_VIDEO_PIXELS:
        raise ValueError("video pixels exceed the preview resource limit")
    return value


def _target_size(width: int, height: int, max_width: int) -> tuple[int, int]:
    if max_width == 0 or max_width < -1:
        raise ValueError("max_width must be -1 or a positive integer")
    if max_width > MAX_DIMENSION:
        raise ValueError(f"max_width cannot exceed {MAX_DIMENSION}")
    if max_width == -1 or max(width, height) <= max_width:
        return width, height
    scale = max_width / max(width, height)
    # This is the upstream calculation, intentionally truncating rather than
    # rounding so the converted output dimensions are byte-for-byte equivalent.
    return max(1, int(width * scale)), max(1, int(height * scale))


def _frame_to_pil(frame: torch.Tensor) -> Image.Image:
    array = frame.detach().cpu().numpy()
    if array.dtype != np.uint8:
        array = (np.clip(array, 0.0, 1.0) * 255).astype(np.uint8)
    if array.shape[-1] == 1:
        array = np.repeat(array, 3, axis=-1)
    if array.shape[-1] == 4:
        return Image.fromarray(array, mode="RGBA")
    return Image.fromarray(array, mode="RGB")


def prepare_preview(value: torch.Tensor, max_width: int, *, video: bool) -> torch.Tensor:
    """Apply the legacy max-dimension Lanczos transform to a bounded image batch."""

    batch = _validate_image_batch(value, video=video)
    frames = batch if video else batch[:1]
    width, height = int(frames.shape[2]), int(frames.shape[1])
    target = _target_size(width, height, int(max_width))
    converted: list[torch.Tensor] = []
    for frame in frames:
        image = _frame_to_pil(frame)
        if image.size != target:
            image = image.resize(target, resample=Image.Resampling.LANCZOS)
        array = np.asarray(image, dtype=np.float32) / 255.0
        if array.shape[-1] == 4:
            # Comfy IMAGE values are RGB. The legacy PNG transport accepted
            # alpha but the host preview surface composites RGB, so discard it.
            array = array[..., :3]
        converted.append(torch.from_numpy(array.copy()))
    return torch.stack(converted)


class PanoramaViewerNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw", "ui")

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="PanoramaViewerNode",
            display_name="Preview 360 Panorama",
            category="pytorch360convert",
            is_output_node=True,
            inputs=[
                io.Image.Input("images"),
                io.Int.Input(
                    "max_width",
                    default=4096,
                    tooltip=(
                        "The maximum image dimension used by the viewer. "
                        "Set to -1 to disable resizing."
                    ),
                ),
            ],
            outputs=[],
        )

    @classmethod
    async def execute(cls, images: sdk.ImageRef, max_width: int = 4096) -> io.NodeOutput:
        source = await images.raw()
        pixels = prepare_preview(source, int(max_width), video=False)
        preview_ref = await sdk.ImageRef._from_raw(pixels)
        return io.NodeOutput(ui=await sdk.ctx().ui.preview_images(preview_ref))


class PanoramaVideoViewerNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw", "ui")

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="PanoramaVideoViewerNode",
            display_name="Preview 360 Video Panorama",
            category="pytorch360convert",
            is_output_node=True,
            inputs=[
                io.Image.Input("video_frames"),
                io.Int.Input("fps", default=30, min=1, max=120, step=1),
                io.Int.Input(
                    "max_width",
                    default=2048,
                    tooltip=(
                        "The maximum frame dimension used by the viewer. "
                        "Set to -1 to disable resizing."
                    ),
                ),
            ],
            outputs=[],
        )

    @classmethod
    async def execute(
        cls,
        video_frames: sdk.ImageRef,
        fps: int = 30,
        max_width: int = 2048,
    ) -> io.NodeOutput:
        rate = int(fps)
        if not 1 <= rate <= 120:
            raise ValueError("fps must be between 1 and 120")
        source = await video_frames.raw()
        pixels = prepare_preview(source, int(max_width), video=True)
        preview_ref = await sdk.ImageRef._from_raw(pixels)
        return io.NodeOutput(ui=await sdk.ctx().ui.preview_images(preview_ref))


NODE_CLASS_MAPPINGS = {
    "PanoramaViewerNode": PanoramaViewerNode,
    "PanoramaVideoViewerNode": PanoramaVideoViewerNode,
}
