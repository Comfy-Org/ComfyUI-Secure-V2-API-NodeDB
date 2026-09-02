from __future__ import annotations

import math

import torch


def repeat_to_batch_size(tensor, batch_size, dim=0):
    if tensor.shape[dim] > batch_size:
        return tensor.narrow(dim, 0, batch_size)
    if tensor.shape[dim] < batch_size:
        repeats = (
            dim * [1]
            + [math.ceil(batch_size / tensor.shape[dim])]
            + [1] * (len(tensor.shape) - 1 - dim)
        )
        return tensor.repeat(repeats).narrow(dim, 0, batch_size)
    return tensor


def _bislerp(samples, width, height):
    def slerp(first, second, ratio):
        channels = first.shape[-1]
        first_norms = torch.norm(first, dim=-1, keepdim=True)
        second_norms = torch.norm(second, dim=-1, keepdim=True)
        first_normalized = first / first_norms
        second_normalized = second / second_norms
        first_normalized[first_norms.expand(-1, channels) == 0.0] = 0.0
        second_normalized[second_norms.expand(-1, channels) == 0.0] = 0.0
        dot = (first_normalized * second_normalized).sum(1)
        omega = torch.acos(dot)
        sine = torch.sin(omega)
        result = (
            (torch.sin((1.0 - ratio.squeeze(1)) * omega) / sine).unsqueeze(1)
            * first_normalized
            + (torch.sin(ratio.squeeze(1) * omega) / sine).unsqueeze(1)
            * second_normalized
        )
        result *= (
            first_norms * (1.0 - ratio) + second_norms * ratio
        ).expand(-1, channels)
        result[dot > 1 - 1e-5] = first[dot > 1 - 1e-5]
        result[dot < 1e-5 - 1] = (
            first * (1.0 - ratio) + second * ratio
        )[dot < 1e-5 - 1]
        return result

    def bilinear_data(old_length, new_length, device):
        first = torch.arange(
            old_length, dtype=torch.float32, device=device
        ).reshape((1, 1, 1, -1))
        first = torch.nn.functional.interpolate(
            first, size=(1, new_length), mode="bilinear"
        )
        ratios = first - first.floor()
        first = first.to(torch.int64)
        second = (
            torch.arange(old_length, dtype=torch.float32, device=device)
            .reshape((1, 1, 1, -1))
            .add(1)
        )
        second[:, :, :, -1] -= 1
        second = torch.nn.functional.interpolate(
            second, size=(1, new_length), mode="bilinear"
        ).to(torch.int64)
        return ratios, first, second

    original_dtype = samples.dtype
    samples = samples.float()
    batch, channels, old_height, old_width = samples.shape

    ratios, first, second = bilinear_data(
        old_width, width, samples.device
    )
    first = first.expand((batch, channels, old_height, -1))
    second = second.expand((batch, channels, old_height, -1))
    ratios = ratios.expand((batch, 1, old_height, -1))
    first_pass = samples.gather(-1, first).movedim(1, -1).reshape(
        (-1, channels)
    )
    second_pass = samples.gather(-1, second).movedim(1, -1).reshape(
        (-1, channels)
    )
    ratios = ratios.movedim(1, -1).reshape((-1, 1))
    result = slerp(first_pass, second_pass, ratios)
    result = result.reshape(batch, old_height, width, channels).movedim(-1, 1)

    ratios, first, second = bilinear_data(
        old_height, height, samples.device
    )
    first = first.reshape((1, 1, -1, 1)).expand(
        (batch, channels, -1, width)
    )
    second = second.reshape((1, 1, -1, 1)).expand(
        (batch, channels, -1, width)
    )
    ratios = ratios.reshape((1, 1, -1, 1)).expand(
        (batch, 1, -1, width)
    )
    first_pass = result.gather(-2, first).movedim(1, -1).reshape(
        (-1, channels)
    )
    second_pass = result.gather(-2, second).movedim(1, -1).reshape(
        (-1, channels)
    )
    ratios = ratios.movedim(1, -1).reshape((-1, 1))
    result = slerp(first_pass, second_pass, ratios)
    result = result.reshape(batch, height, width, channels).movedim(-1, 1)
    return result.to(original_dtype)


def _lanczos(samples, width, height):
    import numpy as np
    from PIL import Image

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
        array = np.array(image).astype(np.float32) / 255.0
        tensor = torch.from_numpy(array)
        tensors.append(tensor.movedim(-1, 0) if array.ndim == 3 else tensor)
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
        x = 0
        y = 0
        if old_aspect > new_aspect:
            x = round(
                (old_width - old_width * (new_aspect / old_aspect)) / 2
            )
        elif old_aspect < new_aspect:
            y = round(
                (old_height - old_height * (old_aspect / new_aspect)) / 2
            )
        source = samples.narrow(
            -2, y, old_height - y * 2
        ).narrow(-1, x, old_width - x * 2)
    else:
        source = samples

    if upscale_method == "bislerp":
        output = _bislerp(source, width, height)
    elif upscale_method == "lanczos":
        output = _lanczos(source, width, height)
    else:
        output = torch.nn.functional.interpolate(
            source, size=(height, width), mode=upscale_method
        )

    if len(original_shape) == 4:
        return output
    output = output.reshape(
        (original_shape[0], -1, original_shape[1]) + (height, width)
    )
    return output.movedim(2, 1).reshape(
        original_shape[:-2] + (height, width)
    )


def conditioning_set_values(conditioning, values, append=False):
    result = []
    for entry in conditioning:
        updated = [entry[0], entry[1].copy()]
        for key, value in values.items():
            if append and key in updated[1]:
                value = updated[1][key] + value
            updated[1][key] = value
        result.append(updated)
    return result


def image_alpha_fix(destination, source):
    if destination.shape[-1] < source.shape[-1]:
        source = source[..., :destination.shape[-1]]
    elif destination.shape[-1] > source.shape[-1]:
        source = torch.nn.functional.pad(source, (0, 1))
        source[..., -1] = 1.0
    return destination, source


def composite(
    destination, source, x, y, mask=None, multiplier=8, resize_source=False
):
    source = source.to(destination.device)
    if resize_source:
        source = torch.nn.functional.interpolate(
            source,
            size=(destination.shape[-2], destination.shape[-1]),
            mode="bilinear",
        )
    source = repeat_to_batch_size(source, destination.shape[0])
    x = max(-source.shape[-1] * multiplier,
            min(x, destination.shape[-1] * multiplier))
    y = max(-source.shape[-2] * multiplier,
            min(y, destination.shape[-2] * multiplier))
    left, top = x // multiplier, y // multiplier
    right = left + source.shape[-1]
    bottom = top + source.shape[-2]
    if mask is None:
        mask = torch.ones_like(source)
    else:
        mask = mask.to(destination.device, copy=True)
        mask = torch.nn.functional.interpolate(
            mask.reshape((-1, 1, mask.shape[-2], mask.shape[-1])),
            size=(source.shape[-2], source.shape[-1]),
            mode="bilinear",
        )
        mask = repeat_to_batch_size(mask, source.shape[0])
    visible_width = destination.shape[-1] - left + min(0, x)
    visible_height = destination.shape[-2] - top + min(0, y)
    mask = mask[:, :, :visible_height, :visible_width]
    if mask.ndim < source.ndim:
        mask = mask.unsqueeze(1)
    inverse_mask = torch.ones_like(mask) - mask
    source_portion = mask * source[..., :visible_height, :visible_width]
    destination_portion = (
        inverse_mask * destination[..., top:bottom, left:right]
    )
    destination[..., top:bottom, left:right] = (
        source_portion + destination_portion
    )
    return destination


_WAN21_MEAN = (
    -0.7571, -0.7089, -0.9113, 0.1075, -0.1745, 0.9653, -0.1517,
    1.5508, 0.4134, -0.0715, 0.5517, -0.3632, -0.1922, -0.9497,
    0.2503, -0.2921,
)
_WAN21_STD = (
    2.8184, 1.4541, 2.3275, 2.6558, 1.2196, 1.7708, 2.6052,
    2.0743, 3.2687, 2.1526, 2.8652, 1.5579, 1.6382, 1.1253,
    2.8251, 1.9160,
)


def wan21_process_out(latent):
    mean = torch.tensor(_WAN21_MEAN).view(1, 16, 1, 1, 1).to(
        latent.device, latent.dtype
    )
    std = torch.tensor(_WAN21_STD).view(1, 16, 1, 1, 1).to(
        latent.device, latent.dtype
    )
    return latent * std + mean
