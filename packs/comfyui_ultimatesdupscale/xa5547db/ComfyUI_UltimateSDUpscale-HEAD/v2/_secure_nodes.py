"""Secure Nodes 2.0 implementation of Ultimate SD Upscale.

The tile planner, masks, crop sizing, ordering, and compositing remain pack
code.  Only model-owned operations (upscale-model inference, VAE work, and
diffusion sampling) cross the V2 SDK as opaque references.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import torch
import torch.nn.functional as F

from ._secure_runtime import SCHEMAS, bind_node, sdk


_ROUNDING = 8
_MAX_PIXELS = 67_108_864


def _ctx():
    return sdk.ctx()


def _one(value: Any) -> tuple[Any]:
    return (value,)


def _image4(value: Any) -> torch.Tensor:
    image = torch.as_tensor(value)
    if image.ndim != 4 or image.shape[-1] < 3:
        raise ValueError("Ultimate SD Upscale requires a BHWC RGB image")
    if not 1 <= int(image.shape[0]) <= 64:
        raise ValueError("Ultimate SD Upscale image batch must be in [1, 64]")
    if image.shape[1] < 1 or image.shape[2] < 1:
        raise ValueError("Ultimate SD Upscale received an empty image")
    if int(image.shape[0] * image.shape[1] * image.shape[2]) > _MAX_PIXELS:
        raise ValueError("Ultimate SD Upscale input exceeds the pixel limit")
    return torch.nan_to_num(image[..., :3].detach().cpu().float()).clamp(0.0, 1.0)


def _round_length(value: float) -> int:
    return max(_ROUNDING, int(round(float(value) / _ROUNDING) * _ROUNDING))


def _resize(image: torch.Tensor, width: int, height: int) -> torch.Tensor:
    width, height = int(width), int(height)
    if width < 1 or height < 1 or width * height * image.shape[0] > _MAX_PIXELS:
        raise ValueError("Ultimate SD Upscale target exceeds the pixel limit")
    if tuple(image.shape[1:3]) == (height, width):
        return image.clone()
    source = image.movedim(-1, 1)
    result = F.interpolate(
        source, size=(height, width), mode="bicubic",
        align_corners=False, antialias=True,
    )
    return result.movedim(1, -1).clamp(0.0, 1.0)


def _blur(mask: torch.Tensor, radius: int) -> torch.Tensor:
    radius = int(radius)
    if radius <= 0 or not bool(mask.any()):
        return mask.clone()
    sigma = max(0.5, float(radius))
    half = max(1, min(192, int(math.ceil(3.0 * sigma))))
    coordinates = torch.arange(-half, half + 1, dtype=torch.float32)
    kernel = torch.exp(-(coordinates.square()) / (2.0 * sigma * sigma))
    kernel /= kernel.sum()
    value = mask[None, None].float()
    value = F.pad(value, (half, half, 0, 0), mode="replicate")
    value = F.conv2d(value, kernel.view(1, 1, 1, -1))
    value = F.pad(value, (0, 0, half, half), mode="replicate")
    value = F.conv2d(value, kernel.view(1, 1, -1, 1))
    return value[0, 0].clamp(0.0, 1.0)


def _rectangle_mask(
    height: int, width: int, left: int, top: int, right: int, bottom: int,
) -> torch.Tensor:
    mask = torch.zeros((height, width), dtype=torch.float32)
    left, right = max(0, int(left)), min(width, int(right))
    top, bottom = max(0, int(top)), min(height, int(bottom))
    if left < right and top < bottom:
        mask[top:bottom, left:right] = 1.0
    return mask


def _paste_mask(
    canvas_height: int, canvas_width: int, patch: torch.Tensor,
    left: int, top: int,
) -> torch.Tensor:
    result = torch.zeros((canvas_height, canvas_width), dtype=torch.float32)
    patch_height, patch_width = map(int, patch.shape)
    destination_left = max(0, int(left))
    destination_top = max(0, int(top))
    destination_right = min(canvas_width, int(left) + patch_width)
    destination_bottom = min(canvas_height, int(top) + patch_height)
    if destination_left >= destination_right or destination_top >= destination_bottom:
        return result
    source_left = destination_left - int(left)
    source_top = destination_top - int(top)
    result[
        destination_top:destination_bottom,
        destination_left:destination_right,
    ] = patch[
        source_top:source_top + destination_bottom - destination_top,
        source_left:source_left + destination_right - destination_left,
    ]
    return result


def _tent(height: int, width: int, axis: str) -> torch.Tensor:
    if axis == "vertical":
        length = max(1, height)
    else:
        length = max(1, width)
    center = (length - 1) / 2.0
    denominator = max(1.0, center)
    values = 1.0 - (
        torch.arange(length, dtype=torch.float32) - center
    ).abs() / denominator
    values = values.clamp(0.0, 1.0)
    if axis == "vertical":
        return values[:, None].expand(height, width).clone()
    return values[None, :].expand(height, width).clone()


def _radial(height: int, width: int) -> torch.Tensor:
    ys = torch.linspace(-1.0, 1.0, max(1, height))[:, None]
    xs = torch.linspace(-1.0, 1.0, max(1, width))[None, :]
    return (1.0 - torch.sqrt(xs.square() + ys.square())).clamp(0.0, 1.0)


def _mask_bounds(
    mask: torch.Tensor, padding: int,
) -> tuple[int, int, int, int] | None:
    selected = torch.nonzero(mask > 0.0, as_tuple=False)
    if selected.numel() == 0:
        return None
    height, width = map(int, mask.shape)
    pad = max(0, int(padding))
    top = max(0, int(selected[:, 0].min()) - pad)
    bottom = min(height, int(selected[:, 0].max()) + 1 + pad)
    left = max(0, int(selected[:, 1].min()) - pad)
    right = min(width, int(selected[:, 1].max()) + 1 + pad)
    return left, top, right, bottom


def _expand_crop(
    crop: tuple[int, int, int, int], canvas_width: int, canvas_height: int,
    target_width: int, target_height: int,
) -> tuple[int, int, int, int]:
    left, top, right, bottom = crop
    actual_width, actual_height = right - left, bottom - top

    difference = int(target_width) - actual_width
    right = min(right + difference // 2, canvas_width)
    difference = int(target_width) - (right - left)
    left = max(left - difference, 0)
    difference = int(target_width) - (right - left)
    right = min(right + difference, canvas_width)

    difference = int(target_height) - actual_height
    bottom = min(bottom + difference // 2, canvas_height)
    difference = int(target_height) - (bottom - top)
    top = max(top - difference, 0)
    difference = int(target_height) - (bottom - top)
    bottom = min(bottom + difference, canvas_height)
    if right <= left or bottom <= top:
        raise ValueError("Ultimate SD Upscale produced an empty crop")
    return left, top, right, bottom


@dataclass(frozen=True)
class _Job:
    mask: torch.Tensor
    process_width: int
    process_height: int
    padding: int
    blur: int
    denoise: float


@dataclass
class _Prepared:
    crop: tuple[int, int, int, int]
    process_width: int
    process_height: int
    pixels: torch.Tensor
    mask: torch.Tensor


def _prepare_job(
    images: torch.Tensor, job: _Job, force_uniform: bool,
) -> _Prepared | None:
    height, width = map(int, images.shape[1:3])
    crop = _mask_bounds(job.mask, job.padding)
    if crop is None:
        return None
    left, top, right, bottom = crop
    crop_width, crop_height = right - left, bottom - top
    if force_uniform:
        ratio = max(1, int(job.process_width)) / max(1, int(job.process_height))
        if crop_width / crop_height > ratio:
            target_width = crop_width
            target_height = max(1, round(crop_width / ratio))
        else:
            target_width = max(1, round(crop_height * ratio))
            target_height = crop_height
        crop = _expand_crop(
            crop, width, height, target_width, target_height)
        process_width = max(_ROUNDING, int(job.process_width))
        process_height = max(_ROUNDING, int(job.process_height))
    else:
        process_width = max(_ROUNDING, math.ceil(crop_width / 8) * 8)
        process_height = max(_ROUNDING, math.ceil(crop_height / 8) * 8)
        crop = _expand_crop(
            crop, width, height, process_width, process_height)
    left, top, right, bottom = crop
    pixels = _resize(
        images[:, top:bottom, left:right, :], process_width, process_height)
    blended_mask = _blur(job.mask, job.blur)[top:bottom, left:right]
    return _Prepared(
        crop=crop,
        process_width=process_width,
        process_height=process_height,
        pixels=pixels,
        mask=blended_mask,
    )


async def _crop_condition(
    conditioning: Any,
    crop: tuple[int, int, int, int],
    original_size: tuple[int, int],
    canvas_size: tuple[int, int],
    process_size: tuple[int, int],
):
    if conditioning is None:
        return None
    original_width, original_height = original_size
    canvas_width, canvas_height = canvas_size
    source_width = max(1, math.ceil(original_width / 8))
    source_height = max(1, math.ceil(original_height / 8))
    left, top, right, bottom = crop
    x = max(0, min(source_width - 1, math.floor(
        left * source_width / canvas_width)))
    y = max(0, min(source_height - 1, math.floor(
        top * source_height / canvas_height)))
    crop_right = max(x + 1, min(source_width, math.ceil(
        right * source_width / canvas_width)))
    crop_bottom = max(y + 1, min(source_height, math.ceil(
        bottom * source_height / canvas_height)))
    return await conditioning.spatial_crop(
        x=x, y=y, width=crop_right - x, height=crop_bottom - y,
        source_width=source_width, source_height=source_height,
        target_width=max(1, math.ceil(process_size[0] / 8)),
        target_height=max(1, math.ceil(process_size[1] / 8)),
    )


async def _sample_tile(
    latent: Any,
    *,
    model: Any,
    positive: Any,
    negative: Any,
    seed: int,
    steps: int,
    cfg: float,
    sampler_name: str,
    scheduler: str,
    denoise: float,
    custom_sampler: Any = None,
    custom_sigmas: Any = None,
    guider: Any = None,
):
    if guider is not None:
        return await _ctx().sample(
            latent=latent,
            steps=1,
            guider=guider,
            sampler=custom_sampler,
            sigmas=custom_sigmas,
            seed=int(seed),
            denoise=float(denoise),
        )
    kwargs: dict[str, Any] = {}
    if custom_sampler is not None and custom_sigmas is not None:
        kwargs.update(sampler=custom_sampler, sigmas=custom_sigmas)
    return await _ctx().sample(
        latent=latent,
        steps=max(1, int(steps)),
        model=model,
        positive=positive,
        negative=negative,
        cfg=float(cfg),
        seed=int(seed),
        sampler_name=str(sampler_name),
        scheduler=str(scheduler),
        denoise=float(denoise),
        **kwargs,
    )


async def _run_group(
    images: torch.Tensor,
    jobs: list[_Job],
    *,
    force_uniform: bool,
    original_size: tuple[int, int],
    model: Any,
    positive: Any,
    negative: Any,
    vae: Any,
    seed: int,
    steps: int,
    cfg: float,
    sampler_name: str,
    scheduler: str,
    tiled_decode: bool,
    custom_sampler: Any = None,
    custom_sigmas: Any = None,
    guider: Any = None,
) -> torch.Tensor:
    prepared = [
        value for job in jobs
        if (value := _prepare_job(images, job, force_uniform)) is not None
    ]
    if not prepared:
        return images
    sizes = {(item.process_width, item.process_height) for item in prepared}
    requires_individual = len(sizes) != 1
    if len(prepared) > 1 and guider is None and not requires_individual:
        # Plain text conditioning broadcasts safely over a tile batch. Spatial
        # hints do not: each crop has a different origin. Preserve correctness
        # by sampling those tiles independently while keeping batching for the
        # common text-only path and for guider-owned conditioning.
        for conditioning in (positive, negative):
            if (
                conditioning is not None
                and await conditioning.has_spatial_metadata()
            ):
                requires_individual = True
                break
    if requires_individual:
        current = images
        for job in jobs:
            current = await _run_group(
                current, [job], force_uniform=force_uniform,
                original_size=original_size, model=model,
                positive=positive, negative=negative, vae=vae, seed=seed,
                steps=steps, cfg=cfg, sampler_name=sampler_name,
                scheduler=scheduler, tiled_decode=tiled_decode,
                custom_sampler=custom_sampler, custom_sigmas=custom_sigmas,
                guider=guider,
            )
        return current

    batch = int(images.shape[0])
    tile_ref = latent = sampled = decoded = None
    sampling_model = sampling_guider = None
    positive_tile = negative_tile = None
    try:
        tile_ref = await sdk.ImageRef._from_raw(torch.cat(
            [item.pixels for item in prepared], dim=0))
        latent = await vae.encode(tile_ref)
        if guider is None:
            positive_tile = await _crop_condition(
                positive, prepared[0].crop, original_size,
                (int(images.shape[2]), int(images.shape[1])),
                (prepared[0].process_width, prepared[0].process_height),
            )
            negative_tile = await _crop_condition(
                negative, prepared[0].crop, original_size,
                (int(images.shape[2]), int(images.shape[1])),
                (prepared[0].process_width, prepared[0].process_height),
            )
            sampling_model = await model.spatial_crop_inputs(
                regions=[item.crop for item in prepared],
                source_width=int(images.shape[2]),
                source_height=int(images.shape[1]),
                target_width=prepared[0].process_width,
                target_height=prepared[0].process_height,
            )
        else:
            sampling_guider = await guider.spatial_crop_inputs(
                regions=[item.crop for item in prepared],
                source_width=int(images.shape[2]),
                source_height=int(images.shape[1]),
                target_width=prepared[0].process_width,
                target_height=prepared[0].process_height,
            )
        sampled = await _sample_tile(
            latent,
            model=sampling_model,
            positive=positive_tile,
            negative=negative_tile,
            seed=seed,
            steps=steps,
            cfg=cfg,
            sampler_name=sampler_name,
            scheduler=scheduler,
            denoise=jobs[0].denoise,
            custom_sampler=custom_sampler,
            custom_sigmas=custom_sigmas,
            guider=sampling_guider,
        )
        decoded = (
            await vae.decode_tiled(sampled, tile_size=512)
            if tiled_decode else await vae.decode(sampled)
        )
        decoded_pixels = _image4(await decoded.raw()).clone()
    finally:
        released: set[str] = set()
        for ref in (
            decoded, sampled, sampling_guider, sampling_model,
            negative_tile, positive_tile, latent, tile_ref,
        ):
            if ref is not None and ref.id not in released:
                released.add(ref.id)
                await ref.release()

    expected = batch * len(prepared)
    if int(decoded_pixels.shape[0]) != expected:
        raise ValueError(
            "Ultimate SD Upscale decoder changed the tile batch size")
    result = images.clone()
    for index, item in enumerate(prepared):
        left, top, right, bottom = item.crop
        tile = decoded_pixels[index * batch:(index + 1) * batch]
        tile = _resize(tile, right - left, bottom - top)
        blend = item.mask[None, :, :, None].to(dtype=result.dtype)
        destination = result[:, top:bottom, left:right, :]
        destination.copy_(destination * (1.0 - blend) + tile * blend)
    return result.clamp(0.0, 1.0)


def _redraw_jobs(
    height: int, width: int, mode: str, tile_width: int, tile_height: int,
    padding: int, blur: int, denoise: float,
) -> list[_Job]:
    if str(mode) == "None":
        return []
    rows = math.ceil(height / tile_height)
    columns = math.ceil(width / tile_width)
    coordinates = [
        (column, row)
        for row in range(rows)
        for column in range(columns)
    ]
    if str(mode) == "Chess":
        coordinates = [
            *[item for item in coordinates if sum(item) % 2 == 0],
            *[item for item in coordinates if sum(item) % 2 == 1],
        ]
    process_width = _round_length(tile_width + padding)
    process_height = _round_length(tile_height + padding)
    return [
        _Job(
            _rectangle_mask(
                height, width,
                column * tile_width, row * tile_height,
                (column + 1) * tile_width, (row + 1) * tile_height,
            ),
            process_width, process_height, padding, blur, denoise,
        )
        for column, row in coordinates
    ]


def _seam_jobs(
    height: int, width: int, mode: str, tile_width: int, tile_height: int,
    seam_width: int, padding: int, blur: int, denoise: float,
) -> list[_Job]:
    if str(mode) == "None":
        return []
    rows = math.ceil(height / tile_height)
    columns = math.ceil(width / tile_width)
    jobs: list[_Job] = []
    if str(mode) == "Band Pass":
        band = max(0, int(seam_width))
        if band == 0:
            return []
        vertical = _tent(height, band, "horizontal")
        horizontal = _tent(band, width, "vertical")
        for column in range(1, columns):
            jobs.append(_Job(
                _paste_mask(
                    height, width, vertical,
                    column * tile_width - band // 2, 0,
                ),
                _round_length(band + padding * 2),
                _round_length(height),
                padding, 0, denoise,
            ))
        for row in range(1, rows):
            jobs.append(_Job(
                _paste_mask(
                    height, width, horizontal,
                    0, row * tile_height - band // 2,
                ),
                _round_length(width),
                _round_length(band + padding * 2),
                padding, 0, denoise,
            ))
        return jobs

    row_patch = _tent(tile_height, tile_width, "vertical")
    column_patch = _tent(tile_height, tile_width, "horizontal")
    for row in range(rows - 1):
        for column in range(columns):
            jobs.append(_Job(
                _paste_mask(
                    height, width, row_patch,
                    column * tile_width,
                    row * tile_height + tile_height // 2,
                ),
                tile_width, tile_height, padding, blur, denoise,
            ))
    for row in range(rows):
        for column in range(columns - 1):
            jobs.append(_Job(
                _paste_mask(
                    height, width, column_patch,
                    column * tile_width + tile_width // 2,
                    row * tile_height,
                ),
                tile_width, tile_height, padding, blur, denoise,
            ))
    if str(mode) == "Half Tile + Intersections":
        intersection = _radial(tile_height, tile_width)
        for row in range(rows - 1):
            for column in range(columns - 1):
                jobs.append(_Job(
                    _paste_mask(
                        height, width, intersection,
                        column * tile_width + tile_width // 2,
                        row * tile_height + tile_height // 2,
                    ),
                    tile_width, tile_height, 0, blur, denoise,
                ))
    return jobs


async def _process_jobs(
    images: torch.Tensor,
    jobs: list[_Job],
    *,
    batch_size: int,
    force_uniform: bool,
    progress: list[int],
    **sampling: Any,
) -> torch.Tensor:
    current = images
    for start in range(0, len(jobs), max(1, int(batch_size))):
        group = jobs[start:start + max(1, int(batch_size))]
        current = await _run_group(
            current, group, force_uniform=force_uniform, **sampling)
        progress[0] += len(group)
        await _ctx().progress.update(progress[0], max(1, progress[1]))
    return current


async def _ultimate(
    image: Any,
    *,
    vae: Any,
    upscale_by: float,
    seed: int,
    mode_type: str,
    tile_width: int,
    tile_height: int,
    mask_blur: int,
    tile_padding: int,
    seam_fix_mode: str,
    seam_fix_denoise: float,
    seam_fix_width: int,
    seam_fix_mask_blur: int,
    seam_fix_padding: int,
    force_uniform_tiles: bool,
    tiled_decode: bool,
    batch_size: int = 1,
    upscale_model: Any = None,
    model: Any = None,
    positive: Any = None,
    negative: Any = None,
    steps: int = 1,
    cfg: float = 1.0,
    sampler_name: str = "euler",
    scheduler: str = "normal",
    denoise: float = 1.0,
    custom_sampler: Any = None,
    custom_sigmas: Any = None,
    guider: Any = None,
) -> Any:
    pixels = _image4(await image.raw())
    original_size = (int(pixels.shape[2]), int(pixels.shape[1]))
    factor = float(upscale_by)
    if not math.isfinite(factor) or not 0.05 <= factor <= 4.0:
        raise ValueError("upscale_by must be finite and in [0.05, 4]")
    tile_width, tile_height = int(tile_width), int(tile_height)
    if not 8 <= tile_width <= 8192 or not 8 <= tile_height <= 8192:
        raise ValueError("tile dimensions must be in [8, 8192]")
    batch_size = int(batch_size)
    if not 1 <= batch_size <= 4096:
        raise ValueError("tile batch_size must be in [1, 4096]")
    if batch_size > 1 and not bool(force_uniform_tiles):
        raise ValueError(
            "batch_size greater than 1 requires force_uniform_tiles")

    target_width = _round_length(original_size[0] * factor)
    target_height = _round_length(original_size[1] * factor)
    if upscale_model is not None and factor != 1.0:
        upscaled_ref = await upscale_model.upscale(image)
        try:
            pixels = _image4(await upscaled_ref.raw())
        finally:
            await upscaled_ref.release()
    pixels = _resize(pixels, target_width, target_height)
    height, width = map(int, pixels.shape[1:3])

    redraw = _redraw_jobs(
        height, width, mode_type, tile_width, tile_height,
        int(tile_padding), int(mask_blur), float(denoise),
    )
    seams = _seam_jobs(
        height, width, seam_fix_mode, tile_width, tile_height,
        int(seam_fix_width), int(seam_fix_padding),
        int(seam_fix_mask_blur), float(seam_fix_denoise),
    )
    progress = [0, len(redraw) + len(seams)]
    sampling = dict(
        original_size=original_size,
        model=model,
        positive=positive,
        negative=negative,
        vae=vae,
        seed=int(seed),
        steps=max(1, int(steps)),
        cfg=float(cfg),
        sampler_name=str(sampler_name),
        scheduler=str(scheduler),
        tiled_decode=bool(tiled_decode),
        custom_sampler=custom_sampler,
        custom_sigmas=custom_sigmas,
        guider=guider,
    )
    pixels = await _process_jobs(
        pixels, redraw, batch_size=batch_size,
        force_uniform=bool(force_uniform_tiles), progress=progress,
        **sampling,
    )
    pixels = await _process_jobs(
        pixels, seams, batch_size=1,
        force_uniform=bool(force_uniform_tiles), progress=progress,
        **sampling,
    )
    return await sdk.ImageRef._from_raw(pixels)


async def _upscale(**kwargs: Any):
    return _one(await _ultimate(**kwargs))


async def _no_upscale(upscaled_image: Any, **kwargs: Any):
    return _one(await _ultimate(
        image=upscaled_image, upscale_by=1.0, upscale_model=None, **kwargs))


async def _custom(**kwargs: Any):
    return _one(await _ultimate(**kwargs))


async def _guider(
    image: Any, guider: Any, sampler: Any, sigmas: Any, **kwargs: Any,
):
    return _one(await _ultimate(
        image=image,
        guider=guider,
        custom_sampler=sampler,
        custom_sigmas=sigmas,
        model=None,
        positive=None,
        negative=None,
        steps=1,
        cfg=1.0,
        sampler_name="euler",
        scheduler="normal",
        denoise=1.0,
        **kwargs,
    ))


NODE_CLASS_MAPPINGS = {
    "UltimateSDUpscale": bind_node(
        "UltimateSDUpscale", _upscale, permissions=("raw", "sample")),
    "UltimateSDUpscaleNoUpscale": bind_node(
        "UltimateSDUpscaleNoUpscale", _no_upscale,
        permissions=("raw", "sample")),
    "UltimateSDUpscaleCustomSample": bind_node(
        "UltimateSDUpscaleCustomSample", _custom,
        permissions=("raw", "sample")),
    "UltimateSDUpscaleGuider": bind_node(
        "UltimateSDUpscaleGuider", _guider,
        permissions=("raw", "sample")),
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "UltimateSDUpscale": "Ultimate SD Upscale",
    "UltimateSDUpscaleNoUpscale": "Ultimate SD Upscale (No Upscale)",
    "UltimateSDUpscaleCustomSample": "Ultimate SD Upscale (Custom Sample)",
    "UltimateSDUpscaleGuider": "Ultimate SD Upscale (Guider)",
}


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "SCHEMAS"]
