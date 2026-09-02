"""Pure raw-compute resize helpers mirroring ComfyUI's pinned semantics."""
from __future__ import annotations

import numpy as np
import torch
from PIL import Image


def bislerp(samples, width, height):
    def slerp(b1, b2, ratio):
        channels = b1.shape[-1]
        b1_norms = torch.norm(b1, dim=-1, keepdim=True)
        b2_norms = torch.norm(b2, dim=-1, keepdim=True)
        b1_normalized = b1 / b1_norms
        b2_normalized = b2 / b2_norms
        b1_normalized[b1_norms.expand(-1, channels) == 0.0] = 0.0
        b2_normalized[b2_norms.expand(-1, channels) == 0.0] = 0.0
        dot = (b1_normalized * b2_normalized).sum(1)
        omega = torch.acos(dot)
        so = torch.sin(omega)
        result = (
            (torch.sin((1.0 - ratio.squeeze(1)) * omega) / so).unsqueeze(1)
            * b1_normalized
            + (torch.sin(ratio.squeeze(1) * omega) / so).unsqueeze(1)
            * b2_normalized
        )
        result *= (
            b1_norms * (1.0 - ratio) + b2_norms * ratio
        ).expand(-1, channels)
        result[dot > 1 - 1e-5] = b1[dot > 1 - 1e-5]
        result[dot < 1e-5 - 1] = (
            b1 * (1.0 - ratio) + b2 * ratio
        )[dot < 1e-5 - 1]
        return result

    def coordinates(old, new, device):
        first = torch.arange(
            old, dtype=torch.float32, device=device
        ).reshape((1, 1, 1, -1))
        first = torch.nn.functional.interpolate(
            first, size=(1, new), mode="bilinear"
        )
        ratios = first - first.floor()
        first = first.to(torch.int64)
        second = torch.arange(
            old, dtype=torch.float32, device=device
        ).reshape((1, 1, 1, -1)) + 1
        second[:, :, :, -1] -= 1
        second = torch.nn.functional.interpolate(
            second, size=(1, new), mode="bilinear"
        ).to(torch.int64)
        return ratios, first, second

    original_dtype = samples.dtype
    samples = samples.float()
    batch, channels, old_height, old_width = samples.shape

    ratios, first, second = coordinates(old_width, width, samples.device)
    first = first.expand((batch, channels, old_height, -1))
    second = second.expand((batch, channels, old_height, -1))
    ratios = ratios.expand((batch, 1, old_height, -1))
    left = samples.gather(-1, first).movedim(1, -1).reshape((-1, channels))
    right = samples.gather(-1, second).movedim(1, -1).reshape((-1, channels))
    result = slerp(left, right, ratios.movedim(1, -1).reshape((-1, 1)))
    result = result.reshape(batch, old_height, width, channels).movedim(-1, 1)

    ratios, first, second = coordinates(old_height, height, samples.device)
    first = first.reshape((1, 1, -1, 1)).expand((batch, channels, -1, width))
    second = second.reshape((1, 1, -1, 1)).expand((batch, channels, -1, width))
    ratios = ratios.reshape((1, 1, -1, 1)).expand((batch, 1, -1, width))
    top = result.gather(-2, first).movedim(1, -1).reshape((-1, channels))
    bottom = result.gather(-2, second).movedim(1, -1).reshape((-1, channels))
    result = slerp(top, bottom, ratios.movedim(1, -1).reshape((-1, 1)))
    return result.reshape(batch, height, width, channels).movedim(-1, 1).to(
        original_dtype
    )


def lanczos(samples, width, height):
    if samples.ndim == 4:
        samples = (
            samples.squeeze(1)
            if samples.shape[1] == 1
            else samples.movedim(1, -1)
        )
    images = [
        Image.fromarray(
            np.clip(255.0 * image.cpu().numpy(), 0, 255).astype(np.uint8)
        )
        for image in samples
    ]
    images = [
        image.resize((width, height), resample=Image.Resampling.LANCZOS)
        for image in images
    ]
    tensors = []
    for image in images:
        value = np.array(image).astype(np.float32) / 255.0
        tensors.append(
            torch.from_numpy(value).movedim(-1, 0)
            if value.ndim == 3
            else torch.from_numpy(value)
        )
    return torch.stack(tensors).to(samples.device, samples.dtype)


def common_upscale(samples, width, height, upscale_method, crop):
    original_shape = tuple(samples.shape)
    if len(original_shape) > 4:
        samples = samples.reshape(
            samples.shape[0], samples.shape[1], -1,
            samples.shape[-2], samples.shape[-1]
        )
        samples = samples.movedim(2, 1)
        samples = samples.reshape(
            -1, original_shape[1], original_shape[-2], original_shape[-1]
        )
    if crop == "center":
        old_width = samples.shape[-1]
        old_height = samples.shape[-2]
        old_aspect = old_width / old_height
        new_aspect = width / height
        x = y = 0
        if old_aspect > new_aspect:
            x = round((old_width - old_width * (new_aspect / old_aspect)) / 2)
        elif old_aspect < new_aspect:
            y = round((old_height - old_height * (old_aspect / new_aspect)) / 2)
        source = samples.narrow(-2, y, old_height - y * 2).narrow(
            -1, x, old_width - x * 2
        )
    else:
        source = samples

    if upscale_method == "bislerp":
        output = bislerp(source, width, height)
    elif upscale_method == "lanczos":
        output = lanczos(source, width, height)
    else:
        output = torch.nn.functional.interpolate(
            source, size=(height, width), mode=upscale_method
        )
    if len(original_shape) == 4:
        return output
    output = output.reshape(
        (original_shape[0], -1, original_shape[1]) + (height, width)
    )
    return output.movedim(2, 1).reshape(original_shape[:-2] + (height, width))


__all__ = ["bislerp", "common_upscale", "lanczos"]
