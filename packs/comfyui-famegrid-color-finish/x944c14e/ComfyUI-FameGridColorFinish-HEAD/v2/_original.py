"""A deterministic color-and-detail finishing node for ComfyUI."""

from __future__ import annotations

import torch
import torch.nn.functional as functional


class FameGridColorFinish:
    """Apply FameGrid's adjustable lightness, color-balance, and detail recipe."""

    CATEGORY = "FameGrid/Color"
    FUNCTION = "finish"
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    DESCRIPTION = "FameGrid color and detail finish with separate master strengths."

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"image": ("IMAGE",)},
            "optional": {
                "color_strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05}),
                "sharpen_strength": ("FLOAT", {"default": 0.6, "min": 0.0, "max": 1.0, "step": 0.05}),
            },
        }

    @staticmethod
    def _validate_image(image: torch.Tensor) -> None:
        if not isinstance(image, torch.Tensor):
            raise TypeError("image must be a torch.Tensor")
        if image.ndim != 4 or image.shape[-1] < 3:
            raise ValueError("image must use ComfyUI's [batch, height, width, channels] layout")
        if not image.is_floating_point():
            raise TypeError("image must be a floating-point tensor")

    @staticmethod
    def _set_lightness(rgb: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        maximum = rgb.max(dim=-1).values
        minimum = rgb.min(dim=-1).values
        current = ((maximum + minimum) * 0.5).clamp(1e-6, 1.0 - 1e-6)
        darker = rgb * (target / current).unsqueeze(-1)
        lighter = 1.0 - (1.0 - rgb) * ((1.0 - target) / (1.0 - current)).unsqueeze(-1)
        return torch.where((target <= current).unsqueeze(-1), darker, lighter).clamp(0.0, 1.0)

    @staticmethod
    def _sharpen(rgb: torch.Tensor, strength: float) -> torch.Tensor:
        channels_first = rgb.permute(0, 3, 1, 2)
        padded = functional.pad(channels_first, (1, 1, 1, 1), mode="replicate")
        center = padded[:, :, 1:-1, 1:-1]
        top = padded[:, :, :-2, 1:-1]
        bottom = padded[:, :, 2:, 1:-1]
        left = padded[:, :, 1:-1, :-2]
        right = padded[:, :, 1:-1, 2:]
        edges = center * 4.0 - top - bottom - left - right
        return (center + edges * strength).clamp(0.0, 1.0).permute(0, 2, 3, 1)

    def finish(self, image: torch.Tensor, color_strength: float = 1.0, sharpen_strength: float = 0.6):
        self._validate_image(image)
        original_dtype = image.dtype
        rgb = image[..., :3].to(dtype=torch.float32).clamp(0.0, 1.0)
        color_strength = max(0.0, min(1.0, float(color_strength)))
        sharpen_strength = max(0.0, min(1.0, float(sharpen_strength)))

        # Scale every color adjustment together from bypass (0) to the full recipe (1).
        luminance_weights = rgb.new_tensor([0.299, 0.587, 0.114])
        gray = (rgb * luminance_weights).sum(dim=-1, keepdim=True)
        rgb = gray + (rgb - gray) * (1.0 - 0.01 * color_strength)
        rgb = rgb + (1.0 - rgb) * (0.06 * color_strength)

        # Tonal color balance with the pre-balance lightness preserved.
        maximum = rgb.max(dim=-1).values
        minimum = rgb.min(dim=-1).values
        original_lightness = (maximum + minimum) * 0.5
        a, b, scale = 0.25, 0.333, 0.7
        shadow_weight = torch.clamp((original_lightness - b) / -a + 0.5, 0.0, 1.0) * scale
        midtone_weight = (
            torch.clamp((original_lightness - b) / a + 0.5, 0.0, 1.0)
            * torch.clamp((original_lightness + b - 1.0) / -a + 0.5, 0.0, 1.0)
            * scale
        )
        highlight_weight = torch.clamp((original_lightness + b - 1.0) / a + 0.5, 0.0, 1.0) * scale
        shadows = rgb.new_tensor([0.0, 0.0, -0.03]) * color_strength
        midtones = rgb.new_tensor([-0.01, -0.02, -0.02]) * color_strength
        highlights = rgb.new_tensor([0.0, -0.01, -0.02]) * color_strength
        balanced = (
            rgb
            + shadow_weight.unsqueeze(-1) * shadows
            + midtone_weight.unsqueeze(-1) * midtones
            + highlight_weight.unsqueeze(-1) * highlights
        ).clamp(0.0, 1.0)
        rgb = self._set_lightness(balanced, original_lightness)

        rgb = self._sharpen(rgb, sharpen_strength)
        if image.shape[-1] > 3:
            output = torch.cat((rgb.to(original_dtype), image[..., 3:]), dim=-1)
        else:
            output = rgb.to(original_dtype)
        return (output,)
