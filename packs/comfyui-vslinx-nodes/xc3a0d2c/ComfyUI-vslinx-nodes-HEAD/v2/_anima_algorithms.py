"""Pack-owned tiling and colour-transfer algorithms from the pinned release."""
from __future__ import annotations

import torch
import torch.nn.functional as F


def _tile_image(image, rows, cols, overlap, overlap_x, overlap_y):
    height, width = image.shape[1:3]
    tile_height = height // rows
    tile_width = width // cols
    height = tile_height * rows
    width = tile_width * cols
    overlap_height = min(
        tile_height // 2, int(tile_height * overlap) + overlap_y)
    overlap_width = min(
        tile_width // 2, int(tile_width * overlap) + overlap_x)
    if rows == 1:
        overlap_height = 0
    if cols == 1:
        overlap_width = 0
    tiles = []
    for row in range(rows):
        for column in range(cols):
            top, left = row * tile_height, column * tile_width
            if row > 0:
                top -= overlap_height
            if column > 0:
                left -= overlap_width
            bottom = top + tile_height + overlap_height
            right = left + tile_width + overlap_width
            if bottom > height:
                bottom, top = height, height - tile_height - overlap_height
            if right > width:
                right, left = width, width - tile_width - overlap_width
            tiles.append(image[:, top:bottom, left:right, :])
    return (
        torch.cat(tiles), tile_width + overlap_width,
        tile_height + overlap_height, overlap_width, overlap_height,
    )


def _untile_image(tiles, overlap_x, overlap_y, rows, cols):
    tile_height, tile_width = tiles.shape[1:3]
    tile_height -= overlap_y
    tile_width -= overlap_x
    output_width, output_height = cols * tile_width, rows * tile_height
    output = torch.zeros(
        (1, output_height, output_width, tiles.shape[3]),
        device=tiles.device, dtype=tiles.dtype)
    for row in range(rows):
        for column in range(cols):
            top, left = row * tile_height, column * tile_width
            if row > 0:
                top -= overlap_y
            if column > 0:
                left -= overlap_x
            bottom = top + tile_height + overlap_y
            right = left + tile_width + overlap_x
            if bottom > output_height:
                bottom, top = output_height, output_height - tile_height - overlap_y
            if right > output_width:
                right, left = output_width, output_width - tile_width - overlap_x
            mask = torch.ones(
                (1, tile_height + overlap_y, tile_width + overlap_x),
                device=tiles.device, dtype=tiles.dtype)
            if row > 0 and overlap_y > 0:
                mask[:, :overlap_y, :] *= torch.linspace(
                    0, 1, overlap_y, device=tiles.device,
                    dtype=tiles.dtype).unsqueeze(1)
            if column > 0 and overlap_x > 0:
                mask[:, :, :overlap_x] *= torch.linspace(
                    0, 1, overlap_x, device=tiles.device,
                    dtype=tiles.dtype).unsqueeze(0)
            mask = mask.unsqueeze(-1).repeat(1, 1, 1, tiles.shape[3])
            tile = tiles[row * cols + column] * mask
            output[:, top:bottom, left:right, :] = (
                output[:, top:bottom, left:right, :] * (1 - mask) + tile)
    return output


def _color_match_meanstd(target, reference):
    dimensions = (1, 2)
    target_mean = target.mean(dim=dimensions, keepdim=True)
    target_std = target.std(dim=dimensions, keepdim=True)
    reference_mean = reference.mean(dim=dimensions, keepdim=True)
    reference_std = reference.std(dim=dimensions, keepdim=True)
    return (
        (target - target_mean) / (target_std + 1e-5)
        * reference_std + reference_mean)


def _gaussian_blur(image, radius):
    values = torch.arange(
        -radius, radius + 1, device=image.device, dtype=image.dtype)
    kernel = torch.exp(-(values * values) / (2.0 * radius * radius))
    kernel /= kernel.sum()
    channels = image.shape[1]
    horizontal = kernel.view(1, 1, 1, -1).repeat(channels, 1, 1, 1)
    vertical = kernel.view(1, 1, -1, 1).repeat(channels, 1, 1, 1)
    result = F.pad(image, (radius, radius, 0, 0), mode="reflect")
    result = F.conv2d(result, horizontal, groups=channels)
    result = F.pad(result, (0, 0, radius, radius), mode="reflect")
    return F.conv2d(result, vertical, groups=channels)


def _wavelet_decompose(image, levels=5):
    high = torch.zeros_like(image)
    low = image
    for index in range(levels):
        blurred = _gaussian_blur(low, 2 ** index)
        high += low - blurred
        low = blurred
    return high, low


def _color_match_wavelet(target, reference):
    target_channels = target.movedim(-1, 1)
    reference_channels = reference.movedim(-1, 1)
    target_high, _ = _wavelet_decompose(target_channels)
    _, reference_low = _wavelet_decompose(reference_channels)
    return (target_high + reference_low).movedim(1, -1)


__all__ = [
    "_tile_image", "_untile_image", "_color_match_meanstd",
    "_color_match_wavelet",
]
