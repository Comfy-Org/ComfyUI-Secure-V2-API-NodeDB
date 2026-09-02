"""Secure raw-compute implementation of Y7 stereoscopic image nodes."""
from __future__ import annotations

import torch
import torch.nn.functional as F

from comfy_api.latest import io, sdk


_WORK_DTYPE = torch.float32
_OUTPUT_DTYPE = torch.float16
_MAX_AXIS = 16_384
_MAX_FRAMES = 4_096
_MAX_OUTPUT_ELEMENTS = 134_217_728  # 512 MiB at the working dtype.

_METHODS = ["mesh_warping", "grid_sampling"]
_MODES = ["parallel", "cross-eyed"]
_OUTPUT_TYPES = ["sbs", "top-bottom", "anaglyph"]

_IMAGE_DESCRIPTION = """2D To 3D Image Converter

Converts a base image and its grayscale depth map to stereoscopic 3D. Choose
mesh warping or grid sampling, parallel or cross-eyed viewing, and side-by-side,
top-bottom, or red-cyan anaglyph output. Depth scale controls stereo strength;
depth blur smooths transitions in the depth map."""

_VIDEO_DESCRIPTION = """2D To 3D Video Converter

Converts a sequence of frames and matching depth maps to stereoscopic frames.
It supports the same methods, viewing modes, and layouts as the image node.
Temporal smoothing reduces depth-map flicker between frames, and batch size
controls how many frames are held in each processing chunk."""


def _validate_image(value: torch.Tensor, label: str) -> None:
    if not isinstance(value, torch.Tensor) or value.ndim != 4:
        raise ValueError(f"{label} must be a four-dimensional IMAGE tensor")
    batch, height, width, channels = value.shape
    if batch < 1 or height < 2 or width < 2 or channels not in (1, 3, 4):
        raise ValueError(f"{label} has an unsupported IMAGE shape")
    if height > _MAX_AXIS or width > _MAX_AXIS:
        raise ValueError(f"{label} exceeds the {_MAX_AXIS}-pixel axis limit")


def _validate_output(
    frames: int,
    height: int,
    width: int,
    channels: int,
    output_type: str,
) -> None:
    if frames > _MAX_FRAMES:
        raise ValueError(f"video exceeds the {_MAX_FRAMES:,}-frame limit")
    multiplier = 1 if output_type == "anaglyph" else 2
    elements = frames * height * width * channels * multiplier
    if elements > _MAX_OUTPUT_ELEMENTS:
        raise ValueError("stereoscopic output exceeds the bounded in-memory limit")


def _depth_nchw(
    depth_map: torch.Tensor,
    device: torch.device,
    batch: int,
    height: int,
    width: int,
) -> torch.Tensor:
    if depth_map.ndim == 4 and depth_map.shape[-1] in (1, 3, 4):
        depth = depth_map.permute(0, 3, 1, 2)[:, :1]
    elif depth_map.ndim == 3:
        depth = depth_map.unsqueeze(1)
    else:
        raise ValueError("depth map must be an IMAGE tensor with one or more channels")
    if depth.shape[0] == 1 and batch > 1:
        depth = depth.expand(batch, -1, -1, -1)
    elif depth.shape[0] != batch:
        raise ValueError("image and depth-map batch counts must match")
    depth = depth.to(device=device, dtype=_WORK_DTYPE)
    if depth.shape[2:] != (height, width):
        depth = F.interpolate(
            depth,
            size=(height, width),
            mode="bilinear",
            align_corners=False,
        )
    return depth


def _blur_depth(depth: torch.Tensor, strength: int) -> torch.Tensor:
    strength = int(strength)
    if strength % 2 == 0:
        strength += 1
    padding = strength // 2
    for kernel, pad in (
        ((1, strength), (0, padding)),
        ((strength, 1), (padding, 0)),
        ((1, strength), (0, padding)),
        ((strength, 1), (padding, 0)),
    ):
        depth = F.avg_pool2d(depth, kernel_size=kernel, stride=1, padding=pad)
    return depth


def _ordered_views(
    left: torch.Tensor,
    right: torch.Tensor,
    mode: str,
) -> tuple[torch.Tensor, torch.Tensor]:
    if mode == "parallel":
        return left, right
    if mode == "cross-eyed":
        return right, left
    raise ValueError(f"unknown viewing mode: {mode}")


def _grid_sampling(
    base_image: torch.Tensor,
    depth_map: torch.Tensor,
    depth_scale: int,
    mode: str,
    depth_blur_strength: int,
    *,
    convergence: float = 0.0,
    layout: str = "side-by-side",
) -> torch.Tensor:
    device = base_image.device
    base = base_image.to(device=device, dtype=_WORK_DTYPE)
    batch, height, width, _ = base.shape
    image = base.permute(0, 3, 1, 2)
    depth = _blur_depth(
        _depth_nchw(depth_map, device, batch, height, width),
        depth_blur_strength,
    )
    disparity = (depth - float(convergence)) * 255.0 * (float(depth_scale) / width)

    y, x = torch.meshgrid(
        torch.arange(height, device=device, dtype=_WORK_DTYPE),
        torch.arange(width, device=device, dtype=_WORK_DTYPE),
        indexing="ij",
    )
    x = x.reshape(1, 1, height, width).expand(batch, -1, -1, -1)
    y = y.reshape(1, 1, height, width).expand(batch, -1, -1, -1)
    y_norm = (2.0 * y / (height - 1)) - 1.0
    left_x = (2.0 * (x - disparity) / (width - 1)) - 1.0
    right_x = (2.0 * (x + disparity) / (width - 1)) - 1.0
    left_grid = torch.stack((left_x.squeeze(1), y_norm.squeeze(1)), dim=-1)
    right_grid = torch.stack((right_x.squeeze(1), y_norm.squeeze(1)), dim=-1)
    left = F.grid_sample(
        image, left_grid, mode="bilinear", padding_mode="border", align_corners=True,
    )
    right = F.grid_sample(
        image, right_grid, mode="bilinear", padding_mode="border", align_corners=True,
    )
    first, second = _ordered_views(left, right, mode)
    output = torch.cat(
        (first, second), dim=2 if layout == "top-bottom" else 3,
    )
    return output.permute(0, 2, 3, 1).to(_OUTPUT_DTYPE)


def _mesh_warping(
    base_image: torch.Tensor,
    depth_map: torch.Tensor,
    depth_scale: int,
    mode: str,
    depth_blur_strength: int,
    *,
    convergence: float = 0.0,
    layout: str = "side-by-side",
) -> torch.Tensor:
    device = base_image.device
    base = base_image.to(device=device, dtype=_WORK_DTYPE)
    batch, height, width, _ = base.shape
    depth = _blur_depth(
        _depth_nchw(depth_map, device, batch, height, width),
        depth_blur_strength,
    ) - float(convergence)
    y, x = torch.meshgrid(
        torch.linspace(-1, 1, height, device=device, dtype=_WORK_DTYPE),
        torch.linspace(-1, 1, width, device=device, dtype=_WORK_DTYPE),
        indexing="ij",
    )
    grid = torch.stack((x, y), dim=-1).unsqueeze(0).expand(batch, -1, -1, -1)
    offset = (float(depth_scale) / (width * 2.0)) * depth[:, 0]
    left_grid = grid.clone()
    right_grid = grid.clone()
    left_grid[..., 0] -= offset
    right_grid[..., 0] += offset
    image = base.permute(0, 3, 1, 2)
    left = F.grid_sample(
        image, left_grid, mode="bilinear", padding_mode="border", align_corners=True,
    ).permute(0, 2, 3, 1)
    right = F.grid_sample(
        image, right_grid, mode="bilinear", padding_mode="border", align_corners=True,
    ).permute(0, 2, 3, 1)
    first, second = _ordered_views(left, right, mode)
    return torch.cat(
        (first, second), dim=1 if layout == "top-bottom" else 2,
    ).to(_OUTPUT_DTYPE)


def _stereo(
    base_image: torch.Tensor,
    depth_map: torch.Tensor,
    method: str,
    depth_scale: int,
    mode: str,
    output_type: str,
    depth_blur_strength: int,
) -> torch.Tensor:
    if output_type not in _OUTPUT_TYPES:
        raise ValueError(f"unsupported output type: {output_type}")
    if output_type == "anaglyph":
        if base_image.shape[-1] != 3:
            raise ValueError("anaglyph output requires an RGB image")
        pair = _pair(
            base_image,
            depth_map,
            method,
            depth_scale,
            "parallel",
            depth_blur_strength,
            convergence=0.5,
            layout="side-by-side",
        )
        width = pair.shape[2] // 2
        left, right = pair[:, :, :width], pair[:, :, width:]
        return torch.stack((left[..., 0], right[..., 1], right[..., 2]), dim=-1)
    return _pair(
        base_image,
        depth_map,
        method,
        depth_scale,
        mode,
        depth_blur_strength,
        layout="top-bottom" if output_type == "top-bottom" else "side-by-side",
    )


def _pair(
    base_image: torch.Tensor,
    depth_map: torch.Tensor,
    method: str,
    depth_scale: int,
    mode: str,
    depth_blur_strength: int,
    *,
    convergence: float = 0.0,
    layout: str,
) -> torch.Tensor:
    processor = {
        "grid_sampling": _grid_sampling,
        "mesh_warping": _mesh_warping,
    }.get(method)
    if processor is None:
        raise ValueError(f"unknown processing method: {method}")
    return processor(
        base_image,
        depth_map,
        depth_scale,
        mode,
        depth_blur_strength,
        convergence=convergence,
        layout=layout,
    )


class Y7SideBySide(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Y7_SideBySide",
            display_name="Y7 SBS (Image)",
            category="Y7 SBS",
            description=_IMAGE_DESCRIPTION,
            not_idempotent=True,
            inputs=[
                io.Image.Input(
                    "base_image",
                    tooltip="The main image to convert to stereoscopic 3D.",
                ),
                io.Image.Input(
                    "depth_map",
                    tooltip="A grayscale map where brighter areas appear closer.",
                ),
                io.Combo.Input("method", options=_METHODS, default="mesh_warping"),
                io.Int.Input("depth_scale", default=40),
                io.Combo.Input("mode", options=_MODES, default="parallel"),
                io.Combo.Input("output_type", options=_OUTPUT_TYPES, default="sbs"),
                io.Int.Input(
                    "depth_blur_strength", default=7, min=3, max=33, step=2,
                ),
            ],
            outputs=[io.Image.Output("image")],
        )

    @classmethod
    async def execute(
        cls,
        base_image: sdk.ImageRef,
        depth_map: sdk.ImageRef,
        method: str,
        depth_scale: int,
        mode: str,
        output_type: str,
        depth_blur_strength: int,
    ) -> io.NodeOutput:
        base = await base_image.raw()
        depth = await depth_map.raw()
        _validate_image(base, "base image")
        _validate_image(depth, "depth map")
        _validate_output(*base.shape, output_type)
        await sdk.ctx().progress.update(1, 2)
        result = _stereo(
            base,
            depth,
            method,
            depth_scale,
            mode,
            output_type,
            depth_blur_strength,
        )
        await sdk.ctx().progress.update(2, 2)
        return io.NodeOutput(await sdk.ImageRef._from_raw(result))


class Y7VideoSideBySide(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Y7_VideoSideBySide",
            display_name="Y7 SBS (Video)",
            category="Y7 SBS",
            description=_VIDEO_DESCRIPTION,
            not_idempotent=True,
            inputs=[
                io.Image.Input("frames", tooltip="Sequence of source video frames."),
                io.Image.Input("depth_maps", tooltip="Matching sequence of depth maps."),
                io.Combo.Input("method", options=_METHODS, default="mesh_warping"),
                io.Int.Input("depth_scale", default=30, min=1, max=100, step=1),
                io.Combo.Input("mode", options=_MODES, default="parallel"),
                io.Combo.Input("output_type", options=_OUTPUT_TYPES, default="sbs"),
                io.Int.Input(
                    "depth_blur_strength", default=7, min=3, max=33, step=2,
                ),
                io.Float.Input(
                    "temporal_smoothing",
                    default=0.2,
                    min=0.0,
                    max=0.5,
                    step=0.05,
                ),
                io.Int.Input("batch_size", default=32, min=1, max=256, step=1),
            ],
            outputs=[io.Image.Output("image")],
        )

    @classmethod
    async def execute(
        cls,
        frames: sdk.ImageRef,
        depth_maps: sdk.ImageRef,
        method: str,
        depth_scale: int,
        mode: str,
        output_type: str,
        depth_blur_strength: int,
        temporal_smoothing: float,
        batch_size: int,
    ) -> io.NodeOutput:
        frame_values = await frames.raw()
        depth_values = await depth_maps.raw()
        _validate_image(frame_values, "frames")
        _validate_image(depth_values, "depth maps")
        if frame_values.shape[0] != depth_values.shape[0]:
            raise ValueError("video frame and depth-map counts must match")
        _validate_output(*frame_values.shape, output_type)
        batch_size = max(1, min(int(batch_size), 256))
        previous_disparity: torch.Tensor | None = None
        output_batches: list[torch.Tensor] = []

        with torch.no_grad():
            for start in range(0, frame_values.shape[0], batch_size):
                stop = min(start + batch_size, frame_values.shape[0])
                current_outputs: list[torch.Tensor] = []
                for index in range(start, stop):
                    frame = frame_values[index:index + 1]
                    depth = depth_values[index:index + 1]
                    prepared = _blur_depth(
                        _depth_nchw(
                            depth,
                            frame.device,
                            1,
                            frame.shape[1],
                            frame.shape[2],
                        ),
                        depth_blur_strength,
                    )
                    disparity = prepared * 255.0 * (
                        float(depth_scale) / frame.shape[2]
                    )
                    if temporal_smoothing > 0 and previous_disparity is not None:
                        disparity = torch.lerp(
                            disparity,
                            previous_disparity.to(disparity.dtype),
                            float(temporal_smoothing),
                        )
                        prepared = disparity / (
                            255.0 * (float(depth_scale) / frame.shape[2])
                        )
                    if temporal_smoothing > 0:
                        previous_disparity = disparity.clone()
                    current_outputs.append(
                        _stereo(
                            frame,
                            prepared.permute(0, 2, 3, 1),
                            method,
                            depth_scale,
                            mode,
                            output_type,
                            depth_blur_strength,
                        )
                    )
                output_batches.append(torch.cat(current_outputs, dim=0))
                await sdk.ctx().progress.update(stop, frame_values.shape[0])

        result = torch.cat(output_batches, dim=0).to(_OUTPUT_DTYPE)
        return io.NodeOutput(await sdk.ImageRef._from_raw(result))


NODE_CLASS_MAPPINGS = {
    "Y7_SideBySide": Y7SideBySide,
    "Y7_VideoSideBySide": Y7VideoSideBySide,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Y7_SideBySide": "Y7 SBS (Image)",
    "Y7_VideoSideBySide": "Y7 SBS (Video)",
}

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "Y7SideBySide",
    "Y7VideoSideBySide",
]
