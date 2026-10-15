"""Unregistered canonical-native vision branch; bundled Wan CLIP is pending.

Pinned nodes.py:611-703 / utils.py:361-443 algorithms stay pack-side.
Requires raw compute for numeric token/image buffers, never host model access.
The temporary work ceiling is not a physical host model/compute budget.
"""
import torch
from comfy_api.latest import sdk
from .secure_tensor_nodes import _bound_payload, MAX_PAYLOAD_BYTES


def split_tiles(embeds, num_split):
    _, height, width, _ = embeds.shape
    out = []
    for image in embeds:
        image = image.unsqueeze(0)
        h, w = height // num_split, width // num_split
        parts = torch.cat([image[:, i*h:(i+1)*h, j*w:(j+1)*w, :]
            for i in range(num_split) for j in range(num_split)], dim=0)
        out.append(parts)
    return torch.stack(out, dim=0)


def merge_hiddenstates(value, tiles):
    out = []
    for embeds in value.split(tiles*tiles):
        tile_size = int((embeds.shape[1]-1) ** 0.5)
        grid_size = int(embeds.shape[0] ** 0.5)
        avg_class_token = embeds[:, 0, :].mean(dim=0, keepdim=True).unsqueeze(0)
        reshaped = embeds[:, 1:, :].reshape(grid_size, grid_size,
            tile_size, tile_size, embeds.shape[-1])
        merged = torch.cat([torch.cat([reshaped[i, j] for j in range(grid_size)], dim=1)
            for i in range(grid_size)], dim=0).unsqueeze(0)
        pooled = torch.nn.functional.adaptive_avg_pool2d(merged.permute(0, 3, 1, 2),
            (tile_size, tile_size)).permute(0, 2, 3, 1)
        out.append(torch.cat([avg_class_token,
            pooled.reshape(1, tile_size*tile_size, embeds.shape[-1])], dim=1))
    return torch.cat(out, dim=0)


def _preflight_images(images, tiles):
    _bound_payload(images)
    if not isinstance(images, torch.Tensor) or images.ndim != 4:
        raise ValueError('Wan native vision requires bounded BHWC images')
    batch, height, width, channels = images.shape
    if not 1 <= batch <= 64 or min(height, width) < 1 or channels != 3:
        raise ValueError('Wan native vision requires 1..64 nonempty RGB images')
    if isinstance(tiles, bool) or not isinstance(tiles, int):
        raise ValueError('Wan native vision tiles must be an integer')
    actual_tiles = min(tiles, 16)
    if actual_tiles > 1:
        if min(height, width) < actual_tiles:
            raise ValueError('Wan native vision tile images must be nonempty')
        # split_tiles retains a full-size tile stack beside per-image cat inputs.
        if images.numel()*images.element_size()*3 > MAX_PAYLOAD_BYTES:
            raise ValueError('Wan native vision projected tile work exceeds 64 MiB')


async def _encode_tokens(vision, image, last):
    handle = await sdk.ImageRef.from_value(image)
    # Native upstream ignores the crop widget and uses encode_image's default.
    output = await vision.encode_image(handle, crop=True)
    read = output.last_hidden_state if last else output.penultimate_hidden_states
    batch = image.shape[0]
    pieces = []
    for start in range(0, batch, 64):
        # One encoder call above, no inference chunking. Transport independent
        # token windows only; preserve exact row order and source merge math.
        count = min(64, batch-start)
        tokens = await read(batch_start=start, batch_count=count)
        value = await tokens.raw()
        _bound_payload(value)
        if value.ndim != 3 or value.shape[0] != count:
            raise ValueError('Wan native vision token rows do not match encoded image batch')
        projected = batch*value.shape[1]*value.shape[2]*value.element_size()
        # Check total projected work after the first bounded window and before
        # requesting the rest/concatenating; no implicit pack quota increase.
        if projected*8 > MAX_PAYLOAD_BYTES:
            raise ValueError('Wan native vision projected token work exceeds 64 MiB')
        if pieces and (value.shape[1:] != pieces[0].shape[1:]
                or value.dtype != pieces[0].dtype or value.device != pieces[0].device):
            raise ValueError('Wan native vision token windows have inconsistent metadata')
        pieces.append(value)
    return pieces[0] if len(pieces) == 1 else torch.cat(pieces, dim=0)


async def _tiled(vision, image, tiles, ratio):
    embeds = await _encode_tokens(vision, image, last=True)
    tiles = min(tiles, 16)
    if tiles > 1:
        image_split = split_tiles(image, tiles)
        # Intentional pinned quirk: hasattr(dict, 'last_hidden_state') is false,
        # so every loop iteration overwrites; only the final image's tiles remain.
        encoded = None
        for row in image_split:
            encoded = await _encode_tokens(vision, row, last=True)
        merged = merge_hiddenstates(encoded, tiles)
        if embeds.shape[0] > 1:
            embeds = embeds*ratio + merged*(1-ratio)
        else:
            # Pinned single-image behavior does not scale merged by (1-ratio).
            embeds = torch.cat([embeds*ratio, merged])
    return embeds


async def encode_native_vision(vision, image_1, strength_1=1.0, strength_2=1.0,
        force_offload=True, crop='center', combine_embeds='average', image_2=None,
        negative_image=None, tiles=0, ratio=1.0):
    """Bounded native branch only, not a complete WanVideoClipVisionEncode port.

    Caller must supply a public canonical ClipVisionRef. No visual/model/raw
    encoder recovery, custom-encoder fallback, or device-policy guessing.
    """
    first = await image_1.raw()
    second = await image_2.raw() if image_2 is not None else None
    negative = await negative_image.raw() if negative_image is not None else None
    _bound_payload((first, second, negative))
    _preflight_images(first, tiles)
    if second is not None:
        _preflight_images(second, tiles)
        if first.shape[0]+second.shape[0] > 64:
            raise ValueError('Wan native vision combined batch exceeds 64')
        if (first.numel()+second.numel())*max(first.element_size(), second.element_size())*3 > MAX_PAYLOAD_BYTES:
            raise ValueError('Wan native vision projected joined work exceeds 64 MiB')
    if negative is not None:
        _preflight_images(negative, tiles)
    image = torch.cat([first, second], dim=0) if second is not None else first
    embeds = await _tiled(vision, image, tiles, ratio) if tiles > 0 else await _encode_tokens(vision, image, last=False)
    negative_embeds = None
    if negative is not None:
        negative_embeds = await _tiled(vision, negative, tiles, ratio) if tiles > 0 else await _encode_tokens(vision, negative, last=False)
    weighted = [embeds[0:1]*strength_1]
    if embeds.shape[0] > 1:
        weighted.append(embeds[1:2]*strength_2)
        weighted.extend(embeds[index:index+1] for index in range(2, embeds.shape[0]))
        if combine_embeds == 'average':
            embeds = torch.mean(torch.stack(weighted), dim=0)
        elif combine_embeds == 'sum':
            embeds = torch.sum(torch.stack(weighted), dim=0)
        elif combine_embeds == 'concat':
            embeds = torch.cat(weighted, dim=1)
        elif combine_embeds == 'batch':
            embeds = torch.cat(weighted, dim=0)
        # Unknown direct mode preserves unweighted multi-row upstream output.
    else:
        embeds = weighted[0]
    result = {'clip_embeds': embeds, 'negative_clip_embeds': negative_embeds}
    _bound_payload(result)
    if force_offload:
        await vision.offload()
    return result
