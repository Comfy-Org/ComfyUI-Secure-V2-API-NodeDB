"""Pack-owned per-frame film grain in permissioned tensor value mode."""

import math

import torch
from comfy_api.latest import io


MAX_ELEMENTS = 16_777_216


def _unit_number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number")
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{label} must be between 0 and 1.")
    return float(value)


class FilmGrainLTXV(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="FilmGrainLTXV",
            display_name="Film Grain LTXV",
            category="effects",
            description="Adds film grain to the image.",
            inputs=[
                io.Image.Input("images"),
                io.Float.Input(
                    "grain_intensity", default=0.1, min=0.0, max=1.0, step=0.01,
                ),
                io.Float.Input(
                    "saturation", default=0.5, min=0.0, max=1.0, step=0.01,
                ),
            ],
            outputs=[io.Image.Output()],
        )

    @classmethod
    def execute(cls, images, grain_intensity, saturation):
        grain_intensity = _unit_number(grain_intensity, "Grain intensity")
        saturation = _unit_number(saturation, "Saturation")
        if not isinstance(images, torch.Tensor) or not torch.is_floating_point(images):
            raise TypeError("images must be a floating-point tensor")
        if (
            images.ndim != 4 or images.shape[-1] != 3
            or any(size < 1 for size in images.shape)
            or images.shape[0] > 64
            or images.numel() > MAX_ELEMENTS
        ):
            raise ValueError("images must be a bounded nonempty BHWC RGB batch")
        if not bool(torch.isfinite(images).all()):
            raise ValueError("images must contain finite values")

        # Work on the guest-owned tensor device. Clone to avoid upstream's
        # in-place modification of inputs shared with another graph consumer.
        output = images.clone()
        grain = torch.zeros(output[0:1].shape, device=output.device)
        for index in range(output.shape[0]):
            torch.randn(grain.shape, device=output.device, out=grain)
            grain[:, :, :, 0] *= 2
            grain[:, :, :, 2] *= 3
            grain = grain * saturation + grain[:, :, :, 1].unsqueeze(3).expand(
                -1, -1, -1, 3
            ) * (1 - saturation)
            output[index:index + 1].add_(grain_intensity * grain)
            output[index:index + 1].clamp_(0, 1)
        return io.NodeOutput(output)
