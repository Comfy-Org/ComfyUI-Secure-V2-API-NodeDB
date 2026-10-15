import math

import torch
from comfy_api.latest import io

from .algorithm import comfypsi_blur_mask

MAX_ELEMENTS = 16_777_216
MAX_WORK = 268_435_456


class BlurMask(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="comfypsi_blur_mask",
            display_name="Blur Mask",
            category="comfypsi/mask",
            inputs=[
                io.Mask.Input("mask"),
                io.Float.Input("blur", default=5.0, min=0.0, max=100.0, step=0.1),
            ],
            outputs=[io.Mask.Output()],
        )

    @classmethod
    def execute(cls, mask, blur):
        if not isinstance(mask, torch.Tensor):
            raise TypeError("mask must be a tensor")
        if mask.ndim != 3 or not 1 <= mask.shape[0] <= 64:
            raise ValueError("mask must have bounded BHW layout")
        if any(not 1 <= size <= 8192 for size in mask.shape[1:]):
            raise ValueError("mask dimensions exceed bounds")
        if mask.numel() > MAX_ELEMENTS:
            raise ValueError("mask exceeds element bound")
        if not mask.dtype.is_floating_point:
            raise TypeError("mask must be floating-point")
        if not torch.isfinite(mask).all():
            raise ValueError("mask must be finite")
        if isinstance(blur, bool) or not isinstance(blur, (int, float)):
            raise TypeError("blur must be numeric")
        if not math.isfinite(blur) or blur > 100:
            raise ValueError("blur must be finite and at most 100")
        if blur > 0:
            kernel = int(6 * blur)
            kernel += kernel % 2 == 0
            kernel = min(kernel, mask.shape[1] - 1, mask.shape[2] - 1)
            kernel += kernel % 2 == 0
            kernel = max(1, kernel)
            if 2 * kernel * mask.numel() > MAX_WORK:
                raise ValueError("convolution exceeds work bound")
        return io.NodeOutput(*comfypsi_blur_mask().main(mask, blur))
