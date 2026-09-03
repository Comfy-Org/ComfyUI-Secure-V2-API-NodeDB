"""Secure Nodes V2 bindings for the pinned vsLinx node pack.

The image, mask, tiling, colour-transfer, filename, prompt and workflow
algorithms remain in this pack.  The V2 SDK is used only for opaque ComfyUI
objects, bounded catalogues, user interaction, model execution and explicitly
permissioned raw tensor computation.
"""
from __future__ import annotations

import hashlib
import io as bytes_io
import json
import math
import re
from pathlib import PurePosixPath
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageFilter, ImageOps, ImageSequence

from . import _onnx_detector
from ._secure_runtime import SCHEMAS, bind_node, materialize, sdk
from .nodes import boolean_operator as boolean_alg
from .nodes import bypass_helper as bypass_alg
from .nodes import group_bookmarks as bookmarks_alg
from .nodes import image_to_pixel_art as pixel_alg
from .nodes import impact_multiline_wildcard_text as wildcard_alg
from .nodes import inpaint_helper as inpaint_alg
from .nodes import lora_save_helper as lora_alg
from .nodes import pipe_utils as pipe_alg
from . import _anima_algorithms as anima_alg


_MAX_BATCH = 64
_MAX_PIXELS = 67_108_864
_MAX_FILES = 256
_MAX_TEXT = 1_048_576
_IMAGE_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif",
    ".tiff", ".ppm",
}
_LAST_IMAGE_SUFFIXES = _IMAGE_SUFFIXES - {".ppm"}
_ANNOTATION = re.compile(r"\s*\[([^\]]+)\]\s*$")


def _ctx():
    return sdk.ctx()


def _checked_image(value: Any, name: str = "image") -> torch.Tensor:
    if not isinstance(value, torch.Tensor):
        raise TypeError(f"{name} must materialize as a torch tensor")
    if value.ndim != 4 or not 1 <= int(value.shape[-1]) <= 4:
        raise ValueError(f"{name} must be a BHWC image tensor")
    batch, height, width = map(int, value.shape[:3])
    if not 1 <= batch <= _MAX_BATCH:
        raise ValueError(f"{name} batch must be in [1, {_MAX_BATCH}]")
    if height <= 0 or width <= 0 or height * width > _MAX_PIXELS:
        raise ValueError(f"{name} exceeds the secure image bound")
    return value


def _checked_vae_tensor(
    value: Any, name: str = "decoded VAE tensor",
) -> torch.Tensor:
    if not isinstance(value, torch.Tensor):
        raise TypeError(f"{name} must materialize as a torch tensor")
    if value.ndim != 4:
        raise ValueError(f"{name} must be BHWC")
    batch, height, width, channels = map(int, value.shape)
    if not 1 <= batch <= _MAX_BATCH:
        raise ValueError(f"{name} batch must be in [1, {_MAX_BATCH}]")
    if height <= 0 or width <= 0 or height * width > _MAX_PIXELS:
        raise ValueError(f"{name} exceeds the secure image bound")
    if not 1 <= channels <= 4096:
        raise ValueError(f"{name} channel count is invalid")
    return value


async def _raw_image(value: Any, name: str = "image") -> torch.Tensor:
    if isinstance(value, sdk.ImageRef):
        value = await value.raw()
    return _checked_image(value, name)


async def _raw_mask(value: Any, name: str = "mask") -> torch.Tensor:
    if isinstance(value, sdk.MaskRef):
        value = await value.raw()
    if not isinstance(value, torch.Tensor):
        raise TypeError(f"{name} must materialize as a torch tensor")
    if value.ndim == 4 and value.shape[1] == 1:
        value = value[:, 0]
    elif value.ndim == 4 and value.shape[-1] == 1:
        value = value[..., 0]
    if value.ndim == 2:
        value = value.unsqueeze(0)
    if value.ndim != 3:
        raise ValueError(f"{name} must be BHW")
    if int(value.shape[0]) > _MAX_BATCH:
        raise ValueError(f"{name} batch exceeds {_MAX_BATCH}")
    if int(value.shape[-1]) * int(value.shape[-2]) > _MAX_PIXELS:
        raise ValueError(f"{name} exceeds the secure image bound")
    return value.float()


async def _deep_materialize(value: Any) -> Any:
    if isinstance(value, sdk.TensorRef):
        return await value.raw()
    if isinstance(value, sdk.ValueRef):
        return await _deep_materialize(await value.value())
    if isinstance(value, list):
        return [await _deep_materialize(item) for item in value]
    if isinstance(value, tuple):
        return tuple([await _deep_materialize(item) for item in value])
    if isinstance(value, dict):
        return {key: await _deep_materialize(item) for key, item in value.items()}
    return value


def _legacy_raw(node_id: str, klass: type, method: str):
    async def handler(**kwargs):
        values = {key: await _deep_materialize(value)
                  for key, value in kwargs.items()}
        return getattr(klass(), method)(**values)

    handler.__name__ = f"secure_{method}_{node_id.lower()}"
    return handler


async def _forward(any=None, **_kwargs):
    return (any,)


async def _state_forward(any=None, **_kwargs):
    return (any,)


async def _bookmarks(**_kwargs):
    return ()


async def _pack_pipe(slot_1=None, slot_2=None, slot_3=None, slot_4=None,
                     slot_5=None, **_kwargs):
    return ((slot_1, slot_2, slot_3, slot_4, slot_5),)


async def _unpack_pipe(pipe=None, **_kwargs):
    value = await materialize(pipe)
    if not isinstance(value, (list, tuple)) or len(value) != 5:
        raise TypeError("VSLINX_PIPE must contain five values")
    return tuple(value)


async def _append_loras(
    text="", id=0, node_title="", powerloraloader_model=None,
    only_enabled=False, debug=False, extra_pnginfo=None, prompt=None,
    unique_id=0, **_kwargs,
):
    # The connected MODEL is deliberately left opaque: this node only uses the
    # graph link and prompt metadata, never model internals.
    del powerloraloader_model
    extra_pnginfo = await materialize(extra_pnginfo)
    prompt = await materialize(prompt)
    return lora_alg.vsLinx_AppendLorasFromNodeToString().run(
        text=text, id=int(id), node_title=str(node_title),
        only_enabled=bool(only_enabled), debug=bool(debug),
        extra_pnginfo=extra_pnginfo, prompt=prompt, unique_id=unique_id,
    )


def _append_loras_fingerprint(
    id=0, node_title="", powerloraloader_model=None, **_kwargs,
):
    if powerloraloader_model is not None and (int(id) != 0 or node_title != ""):
        return float("nan")
    return None


_append_loras.fingerprint_inputs = _append_loras_fingerprint


def _parse_relative_names(value: str) -> list[str]:
    text = str(value or "").strip()
    if len(text) > _MAX_TEXT:
        raise ValueError("selected_paths exceeds 1 MiB")
    if not text:
        return []
    try:
        decoded = json.loads(text)
        names = (
            decoded if isinstance(decoded, list)
            else [line.strip() for line in text.splitlines() if line.strip()]
        )
    except json.JSONDecodeError:
        names = [line.strip() for line in text.splitlines() if line.strip()]
    result = []
    seen = set()
    for raw in names:
        name = str(raw).replace("\\", "/").strip()
        path = PurePosixPath(name)
        if (not name or path.is_absolute() or "\x00" in name
                or any(part in {"", ".", ".."} for part in path.parts)
                or path.suffix.lower() not in _IMAGE_SUFFIXES):
            if name not in seen:
                result.append((name, None))
                seen.add(name)
            continue
        if name not in seen:
            result.append((name, name))
            seen.add(name)
        if len(result) > _MAX_FILES:
            raise ValueError(f"at most {_MAX_FILES} images may be selected")
    return result


def _pil_rgb_tensor(image: Image.Image) -> torch.Tensor:
    image = ImageOps.exif_transpose(image)
    if image.mode not in {"RGB", "RGBA"}:
        image = image.convert("RGB")
    array = np.asarray(image)
    if array.ndim == 2:
        array = np.repeat(array[..., None], 3, axis=-1)
    array = np.asarray(array[..., :3], dtype=np.float32) / 255.0
    return torch.from_numpy(array.copy()).unsqueeze(0)


def _display_name(name: str, mode: str) -> str:
    stem = PurePosixPath(name).stem
    if mode == "deduped filename":
        stem = re.sub(r"\s+\(\d+\)$", "", stem)
    return stem


async def _selected_images(
    selected_paths="", fail_if_empty=True,
    filename_handling="full filename", *, as_batch: bool,
    **_kwargs,
):
    if filename_handling not in {"full filename", "deduped filename"}:
        raise ValueError("unknown filename_handling")
    parsed = _parse_relative_names(selected_paths)
    tensors: list[torch.Tensor] = []
    pil_images: list[Image.Image] = []
    names: list[str] = []
    missing: list[str] = []
    for shown, safe in parsed:
        if safe is None:
            missing.append(shown)
            continue
        if not await _ctx().assets.exists("input", safe):
            missing.append(shown)
            continue
        asset = await _ctx().assets.resolve("input", safe)
        payload = await _ctx().assets.read_bytes(asset)
        try:
            with Image.open(bytes_io.BytesIO(payload)) as image:
                if as_batch:
                    image.load()
                    pil_images.append(image.copy())
                else:
                    tensors.append(_pil_rgb_tensor(image))
            names.append(_display_name(safe, filename_handling))
        except (OSError, ValueError):
            missing.append(shown)
    if not (pil_images if as_batch else tensors):
        if fail_if_empty:
            hint = ", ".join(missing[:5])
            raise RuntimeError(
                "No valid selected input images were found"
                + (f": {hint}" if hint else "")
            )
        if as_batch:
            return torch.zeros((0, 64, 64, 3)), ""
        return [], []
    if not as_batch:
        return tensors, names
    width, height = pil_images[0].size
    resized = [
        image if image.size == (width, height)
        else image.resize((width, height), Image.Resampling.LANCZOS)
        for image in pil_images
    ]
    return torch.cat([_pil_rgb_tensor(image) for image in resized]), ", ".join(names)


async def _selected_list(**kwargs):
    return await _selected_images(as_batch=False, **kwargs)


async def _selected_batch(**kwargs):
    return await _selected_images(as_batch=True, **kwargs)


def _black_image():
    return (
        torch.zeros((1, 512, 512, 3), dtype=torch.float32),
        torch.zeros((1, 512, 512), dtype=torch.float32),
    )


def _annotated_asset(value: str) -> tuple[str, str] | None:
    raw = str(value or "").strip()
    if not raw or raw == "(None)":
        return None
    match = _ANNOTATION.search(raw)
    annotation = match.group(1).lower() if match else "output"
    name = _ANNOTATION.sub("", raw).strip().replace("\\", "/")
    if name.startswith("clipspace/"):
        annotation = "input"
    folder = annotation if annotation in {"input", "output", "temp"} else "output"
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or "\x00" in name
            or any(part in {"", ".", ".."} for part in path.parts)
            or path.suffix.lower() not in _LAST_IMAGE_SUFFIXES):
        return None
    return folder, name


def _decode_image_and_mask(payload: bytes):
    images: list[torch.Tensor] = []
    masks: list[torch.Tensor] = []
    with Image.open(bytes_io.BytesIO(payload)) as source:
        size = None
        for frame in ImageSequence.Iterator(source):
            frame = ImageOps.exif_transpose(frame)
            if frame.mode == "I":
                frame = frame.point(lambda value: value * (1 / 255))
            rgb = frame.convert("RGB")
            if size is None:
                size = rgb.size
            if rgb.size != size:
                continue
            images.append(_pil_rgb_tensor(rgb))
            if "A" in frame.getbands() or (
                frame.mode == "P" and "transparency" in frame.info
            ):
                alpha = np.asarray(frame.convert("RGBA").getchannel("A"),
                                   dtype=np.float32) / 255.0
                masks.append((1.0 - torch.from_numpy(alpha.copy())).unsqueeze(0))
            else:
                masks.append(torch.zeros((1, rgb.height, rgb.width)))
            if source.format == "MPO":
                break
    if not images:
        return _black_image()
    return torch.cat(images), torch.cat(masks)


async def _load_last(image="", auto_refresh=True, **_kwargs):
    del auto_refresh
    selected = _annotated_asset(image)
    if selected is None:
        name = await _ctx().assets.latest("output")
        selected = _annotated_asset(str(name or ""))
    if selected is None:
        return _black_image()
    folder, name = selected
    if not await _ctx().assets.exists(folder, name):
        return _black_image()
    asset = await _ctx().assets.resolve(folder, name)
    payload = await _ctx().assets.read_bytes(asset)
    try:
        return _decode_image_and_mask(payload)
    except (OSError, ValueError):
        return _black_image()


async def _load_last_fingerprint(image="", auto_refresh=True, **_kwargs):
    del auto_refresh
    selected = _annotated_asset(image)
    if selected is None:
        return float("nan")
    if not await _ctx().assets.exists(*selected):
        return float("nan")
    asset = await _ctx().assets.resolve(*selected)
    return await _ctx().assets.digest(asset)


def _always_valid(**_kwargs):
    return True


_load_last.fingerprint_inputs = _load_last_fingerprint
_load_last.validate_inputs = _always_valid


def _resize_images(
    images: torch.Tensor, width: int, height: int, method: str = "bilinear",
) -> torch.Tensor:
    images = _checked_image(images)
    width, height = int(width), int(height)
    if width <= 0 or height <= 0 or width * height > _MAX_PIXELS:
        raise ValueError("target image dimensions exceed the secure bound")
    if tuple(images.shape[1:3]) == (height, width):
        return images
    if method == "lanczos":
        result = []
        for item in images.detach().cpu().clamp(0, 1):
            array = np.clip(item.numpy() * 255.0, 0, 255).astype(np.uint8)
            pil = Image.fromarray(array[..., :3], "RGB")
            result.append(_pil_rgb_tensor(
                pil.resize((width, height), Image.Resampling.LANCZOS)))
        return torch.cat(result)
    modes = {
        "nearest-exact": "nearest-exact",
        "nearest": "nearest",
        "bilinear": "bilinear",
        "area": "area",
        "bicubic": "bicubic",
    }
    if method not in modes:
        raise ValueError(f"unsupported image resize method {method!r}")
    mode = modes[method]
    kwargs = {"align_corners": False} if mode in {"bilinear", "bicubic"} else {}
    return F.interpolate(
        images.movedim(-1, 1), size=(height, width), mode=mode, **kwargs,
    ).movedim(1, -1)


async def _upscale(upscale_model, image, upscale_method, factor, **_kwargs):
    if not isinstance(upscale_model, sdk.UpscaleModelRef):
        raise TypeError("upscale_model must be an UPSCALE_MODEL reference")
    if not isinstance(image, sdk.ImageRef):
        raise TypeError("image must be an IMAGE reference")
    factor = float(factor)
    if not math.isfinite(factor) or not 0.1 <= factor <= 8.0:
        raise ValueError("factor must be in [0.1, 8.0]")
    height, width = await image.spatial_shape()
    target_width = max(1, int(width * factor))
    target_height = max(1, int(height * factor))
    upscaled = await upscale_model.upscale(image)
    pixels = (await _raw_image(upscaled, "upscaled image")).clamp(0, 1)
    return (_resize_images(
        pixels, target_width, target_height, str(upscale_method)),)


async def _latent_value(samples: Any) -> dict[str, Any]:
    if isinstance(samples, sdk.LatentRef):
        value = await samples.value()
    else:
        value = await materialize(samples)
    if not isinstance(value, dict) or not isinstance(value.get("samples"), torch.Tensor):
        raise TypeError("samples must be a LATENT containing a samples tensor")
    tensor = value["samples"]
    if tensor.ndim < 3 or not 1 <= int(tensor.shape[0]) <= 4096:
        raise ValueError("latent batch is invalid")
    if (not getattr(tensor, "is_nested", False)
            and tensor.numel() > _MAX_PIXELS * 64):
        raise ValueError("latent tensor exceeds the secure raw-compute bound")
    return value


async def _decode_batched(
    vae, samples, batch_size=1, *, tiled=False, tile_size=512, overlap=64,
    temporal_size=64, temporal_overlap=8, **_kwargs,
):
    if not isinstance(vae, sdk.VaeRef):
        raise TypeError("vae must be a VAE reference")
    value = await _latent_value(samples)
    latent = value["samples"]
    amount = max(1, int(batch_size))
    total = int(latent.shape[0])

    async def decode(source):
        return (
            await vae.decode_tiled(
                source, tile_size=int(tile_size), overlap=int(overlap),
                temporal_size=int(temporal_size),
                temporal_overlap=int(temporal_overlap),
            )
            if tiled else await vae.decode(source)
        )

    if getattr(latent, "is_nested", False) or total <= 1 or amount >= total:
        source = (
            samples if isinstance(samples, sdk.LatentRef)
            else await sdk.LatentRef.from_value(value)
        )
        return (await _raw_image(await decode(source), "decoded image"),)
    decoded: list[torch.Tensor] = []
    for start in range(0, total, amount):
        chunk = dict(value)
        chunk["samples"] = latent[start:start + amount]
        chunk_ref = await sdk.LatentRef.from_value(chunk)
        image_ref = await decode(chunk_ref)
        decoded.append(await _raw_image(image_ref, "decoded image"))
    return (torch.cat(decoded, dim=0),)


async def _decode_plain(**kwargs):
    return await _decode_batched(tiled=False, **kwargs)


async def _decode_tiled(**kwargs):
    return await _decode_batched(tiled=True, **kwargs)


def _tile_count(rows: int, columns: int) -> tuple[int, int]:
    rows, columns = int(rows), int(columns)
    if not 1 <= rows <= 256 or not 1 <= columns <= 256:
        raise ValueError("rows and columns must be in [1, 256]")
    if rows * columns > 256:
        raise ValueError("the secure tiling bound is 256 tiles")
    return rows, columns


async def _sample(
    latent, model, positive, negative, seed, steps, cfg, sampler_name,
    scheduler, denoise,
):
    return await _ctx().sample(
        latent=latent,
        model=model,
        positive=positive,
        negative=negative,
        seed=int(seed),
        steps=max(1, int(steps)),
        cfg=float(cfg),
        sampler_name=str(sampler_name),
        scheduler=str(scheduler),
        denoise=float(denoise),
    )


async def _patch_spatial_tiles(
    model, rows, columns, overlap, overlap_x, overlap_y,
):
    rows, columns = _tile_count(rows, columns)
    return await model.patch(
        "spatial_tiled_evaluation",
        rows=rows,
        columns=columns,
        overlap=float(overlap),
        # The core primitive consumes latent cells.  Upstream's public node
        # expresses these two additive overlaps in image pixels.
        overlap_x=int(overlap_x) // 8,
        overlap_y=int(overlap_y) // 8,
        blend="linear",
        preserve_existing=True,
    )


async def _decode_sampled(
    vae, latent, *, tiled: bool, tile_size: int,
) -> sdk.ImageRef:
    # MultiDiffusion advertises compatibility with channel-packed upscale VAEs
    # from ComfyUI-VAE-Utils.  Keep the interpretation in this pack: core only
    # performs the bounded VAE decode and returns an opaque tensor.
    decoded_ref = (
        await vae.decode_tensor_tiled(
            latent, tile_size=int(tile_size), overlap=64,
            temporal_size=64, temporal_overlap=8)
        if tiled else await vae.decode_tensor(latent)
    )
    decoded = _checked_vae_tensor(await decoded_ref.raw())
    channels = int(decoded.shape[-1])
    if channels <= 4:
        return await sdk.ImageRef._from_raw(decoded)

    packed = channels // 3 if channels % 3 == 0 else 0
    upscale = math.isqrt(packed)
    if upscale <= 1 or upscale * upscale != packed:
        raise ValueError(
            "upscale VAE output channels must be RGB or exactly 3*k^2")

    # VAE-Utils applies this guard when the custom VAE's process_output hook
    # did not convert the decoder's native [-1, 1] range.
    if float(decoded.amin()) < -0.1:
        decoded = ((decoded.float() + 1.0) / 2.0).clamp(0.0, 1.0)
    decoded = F.pixel_shuffle(
        decoded.movedim(-1, 1), upscale_factor=upscale,
    ).movedim(1, -1)
    return await sdk.ImageRef._from_raw(decoded)


async def _multidiffusion(
    image, model, positive, negative, vae, seed, steps, cfg, sampler_name,
    scheduler, denoise, rows, columns, overlap, overlap_x, overlap_y,
    vae_decode_tiled=False, vae_decode_tile_size=512, **_kwargs,
):
    if not all((isinstance(image, sdk.ImageRef), isinstance(model, sdk.ModelRef),
                isinstance(positive, sdk.CondRef), isinstance(negative, sdk.CondRef),
                isinstance(vae, sdk.VaeRef))):
        raise TypeError("multidiffusion requires typed IMAGE/MODEL/CONDITIONING/VAE refs")
    pixels = await _raw_image(image)
    results = []
    for frame_index, frame in enumerate(pixels):
        frame_ref = await sdk.ImageRef._from_raw(frame.unsqueeze(0))
        latent = await vae.encode(frame_ref)
        tiled_model = await _patch_spatial_tiles(
            model, rows, columns, overlap, overlap_x, overlap_y)
        sampled = await _sample(
            latent, tiled_model, positive, negative, seed, steps, cfg,
            sampler_name, scheduler, denoise)
        decoded = await _decode_sampled(
            vae, sampled, tiled=bool(vae_decode_tiled),
            tile_size=int(vae_decode_tile_size))
        results.append(await _raw_image(decoded))
        await _ctx().progress.update(frame_index + 1, len(pixels))
    return (torch.cat(results),)


def _controlnet_name(value: str) -> str:
    name = str(value or "").replace("\\", "/").strip()
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or "\x00" in name
            or any(part in {"", ".", ".."} for part in path.parts)
            or path.suffix.lower() not in {".safetensors", ".sft"}):
        raise ValueError("Anima LLLite weights must be a relative SafeTensors asset")
    return name


async def _anima_apply(
    model, weights, image, strength, start_percent, end_percent,
    preserve_wrapper,
):
    return await _ctx().integrations.call(
        "anima",
        "apply_lllite",
        model=model,
        weights=weights,
        image=image,
        strength=float(strength),
        start_percent=float(start_percent),
        end_percent=float(end_percent),
        preserve_wrapper=bool(preserve_wrapper),
    )


async def _anima_loader(lllite_name, **_kwargs):
    return (_controlnet_name(lllite_name),)


async def _anima_sampler(
    image, model, positive, negative, vae, sampling_mode, seed, steps, cfg,
    sampler_name, scheduler, denoise, lllite_name, strength, start_percent,
    end_percent, preserve_wrapper, rows, columns, overlap, overlap_x,
    overlap_y, method, color_match="none", color_match_strength=1.0,
    vae_decode_tiled=False, vae_decode_tile_size=512, **_kwargs,
):
    if not all((isinstance(image, sdk.ImageRef), isinstance(model, sdk.ModelRef),
                isinstance(positive, sdk.CondRef), isinstance(negative, sdk.CondRef),
                isinstance(vae, sdk.VaeRef))):
        raise TypeError("Anima sampler requires typed IMAGE/MODEL/CONDITIONING/VAE refs")
    rows, columns = _tile_count(rows, columns)
    name = _controlnet_name(lllite_name)
    weights = await _ctx().assets.resolve("controlnet", name)
    pixels = await _raw_image(image)
    strength_value = float(color_match_strength)
    if not 0.0 <= strength_value <= 1.0:
        raise ValueError("color_match_strength must be in [0, 1]")
    results: list[torch.Tensor] = []

    if str(sampling_mode) == "multidiffusion":
        for frame_index, frame in enumerate(pixels):
            frame_ref = await sdk.ImageRef._from_raw(frame.unsqueeze(0))
            patched = await _anima_apply(
                model, weights, frame_ref, strength, start_percent,
                end_percent, preserve_wrapper)
            patched = await _patch_spatial_tiles(
                patched, rows, columns, overlap, overlap_x, overlap_y)
            latent = await vae.encode(frame_ref)
            sampled = await _sample(
                latent, patched, positive, negative, seed, steps, cfg,
                sampler_name, scheduler, denoise)
            decoded = await _decode_sampled(
                vae, sampled, tiled=bool(vae_decode_tiled),
                tile_size=int(vae_decode_tile_size))
            results.append(await _raw_image(decoded))
            await _ctx().progress.update(frame_index + 1, len(pixels))
        return (torch.cat(results),)

    if str(sampling_mode) != "per_tile":
        raise ValueError("sampling_mode must be per_tile or multidiffusion")
    progress_value = 0
    progress_total = len(pixels) * rows * columns
    for frame in pixels:
        source = frame.unsqueeze(0)
        tiles, _tile_width, _tile_height, ov_w, ov_h = anima_alg._tile_image(
            source, rows, columns, float(overlap), int(overlap_x), int(overlap_y))
        output_tiles = []
        for tile in tiles:
            tile = tile.unsqueeze(0)
            tile_ref = await sdk.ImageRef._from_raw(tile)
            patched = await _anima_apply(
                model, weights, tile_ref, strength, start_percent,
                end_percent, preserve_wrapper)
            latent = await vae.encode(tile_ref)
            sampled = await _sample(
                latent, patched, positive, negative, seed, steps, cfg,
                sampler_name, scheduler, denoise)
            decoded = await _raw_image(await vae.decode(sampled))
            decoded = _resize_images(
                decoded, int(tile.shape[2]), int(tile.shape[1]), str(method))
            if color_match == "mean_std":
                matched = anima_alg._color_match_meanstd(decoded, tile)
            elif color_match == "wavelet":
                matched = anima_alg._color_match_wavelet(decoded, tile)
            elif color_match == "none":
                matched = decoded
            else:
                raise ValueError("unknown color_match mode")
            if color_match != "none":
                decoded = (
                    decoded * (1.0 - strength_value)
                    + matched.clamp(0, 1) * strength_value
                )
            output_tiles.append(decoded)
            progress_value += 1
            await _ctx().progress.update(progress_value, progress_total)
        results.append(anima_alg._untile_image(
            torch.cat(output_tiles), ov_w, ov_h, rows, columns))
    return (torch.cat(results),)


def _expand_box(
    box: tuple[int, int, int, int], factor: float, width: int, height: int,
) -> tuple[int, int, int, int]:
    left, top, right, bottom = box
    crop_width = max(1.0, (right - left) * float(factor))
    crop_height = max(1.0, (bottom - top) * float(factor))

    def normalize(limit: int, start: int, size: float) -> tuple[int, int]:
        if start < 0:
            normalized_start, normalized_end = 0, min(limit, size)
        elif start + size > limit:
            normalized_start = max(0, limit - size)
            normalized_end = limit
        else:
            normalized_start, normalized_end = start, min(limit, start + size)
        return int(normalized_start), int(normalized_end)

    center_x, center_y = left + (right - left) / 2, top + (bottom - top) / 2
    left, right = normalize(width, int(center_x - crop_width / 2), crop_width)
    top, bottom = normalize(height, int(center_y - crop_height / 2), crop_height)
    return left, top, right, bottom


def _dilate_mask(mask: torch.Tensor, amount: int) -> torch.Tensor:
    amount = int(amount)
    if amount == 0:
        return mask
    radius = abs(amount)
    kernel = radius * 2 + 1
    source = mask.unsqueeze(1)
    if amount > 0:
        return F.max_pool2d(source, kernel, stride=1, padding=radius)[:, 0]
    return -F.max_pool2d(-source, kernel, stride=1, padding=radius)[:, 0]


def _blur_mask(mask: torch.Tensor, radius: int) -> torch.Tensor:
    radius = int(radius)
    if radius <= 0:
        return mask
    sigma = max(0.5, radius / 3.0)
    x = torch.arange(-radius, radius + 1, dtype=torch.float32)
    kernel = torch.exp(-(x * x) / (2 * sigma * sigma))
    kernel /= kernel.sum()
    source = mask.unsqueeze(1)
    horizontal = kernel.view(1, 1, 1, -1)
    vertical = kernel.view(1, 1, -1, 1)
    source = F.pad(source, (radius, radius, 0, 0), mode="replicate")
    source = F.conv2d(source, horizontal)
    source = F.pad(source, (0, 0, radius, radius), mode="replicate")
    return F.conv2d(source, vertical)[:, 0]


def _box_segment(
    box: list[float] | tuple[float, ...], score: float, label: str,
    *, width: int, height: int, crop_factor: float, dilation: int,
    drop_size: int,
) -> dict[str, Any] | None:
    if len(box) != 4:
        return None
    left = max(0, min(width, math.floor(float(box[0]))))
    top = max(0, min(height, math.floor(float(box[1]))))
    right = max(0, min(width, math.ceil(float(box[2]))))
    bottom = max(0, min(height, math.ceil(float(box[3]))))
    if right - left <= int(drop_size) or bottom - top <= int(drop_size):
        return None
    bbox = (left, top, right, bottom)
    crop = _expand_box(bbox, crop_factor, width, height)
    crop_left, crop_top, crop_right, crop_bottom = crop
    mask = torch.zeros((1, crop_bottom - crop_top, crop_right - crop_left))
    mask[:, top - crop_top:bottom - crop_top,
         left - crop_left:right - crop_left] = 1.0
    mask = _dilate_mask(mask, dilation).clamp(0, 1)
    return {
        "bbox": bbox,
        "crop": crop,
        "mask": mask,
        "score": float(score),
        "label": str(label or "segment"),
    }


def _gaussian_mask(
    mask: torch.Tensor, radius: int, sigma: float,
) -> torch.Tensor:
    radius = max(0, int(radius))
    if radius == 0:
        return mask
    sigma = max(0.1, float(sigma))
    coordinates = torch.arange(
        -radius, radius + 1, dtype=mask.dtype, device=mask.device)
    kernel = torch.exp(-(coordinates * coordinates) / (2.0 * sigma * sigma))
    kernel /= kernel.sum()
    source = mask.unsqueeze(1)
    source = F.pad(source, (radius, radius, 0, 0), mode="replicate")
    source = F.conv2d(source, kernel.reshape(1, 1, 1, -1))
    source = F.pad(source, (0, 0, radius, radius), mode="replicate")
    return F.conv2d(source, kernel.reshape(1, 1, -1, 1))[:, 0]


def _connected_components(
    binary: np.ndarray,
) -> list[tuple[tuple[int, int, int, int], list[tuple[int, int]]]]:
    binary = np.asarray(binary, dtype=np.bool_)
    height, width = binary.shape
    seen = np.zeros_like(binary, dtype=np.bool_)
    result = []
    for y in range(height):
        for x in range(width):
            if not binary[y, x] or seen[y, x]:
                continue
            seen[y, x] = True
            stack = [(x, y)]
            pixels: list[tuple[int, int]] = []
            left = right = x
            top = bottom = y
            while stack:
                px, py = stack.pop()
                pixels.append((px, py))
                left, right = min(left, px), max(right, px)
                top, bottom = min(top, py), max(bottom, py)
                for nx, ny in (
                    (px - 1, py), (px + 1, py),
                    (px, py - 1), (px, py + 1),
                ):
                    if (0 <= nx < width and 0 <= ny < height
                            and binary[ny, nx] and not seen[ny, nx]):
                        seen[ny, nx] = True
                        stack.append((nx, ny))
            result.append(((left, top, right + 1, bottom + 1), pixels))
    return result


async def _clipseg_recipe_segments(
    recipe: dict[str, Any], image_ref, *, width: int, height: int,
    crop_factor: float, drop_size: int, bbox_fill: bool,
) -> list[dict[str, Any]]:
    model = recipe.get("model")
    if not isinstance(model, sdk.ClipSegRef):
        raise TypeError("Impact CLIPSeg detector recipe is invalid")
    blur = float(recipe.get("blur", 7.0))
    threshold = float(recipe.get("threshold", 0.4))
    dilation = int(recipe.get("dilation_factor", 4))
    if (not 0.0 <= blur <= 15.0 or not 0.0 <= threshold <= 1.0
            or not 0 <= dilation <= 10):
        raise ValueError("Impact CLIPSeg detector settings are invalid")
    prediction = await _raw_mask(await model.predict_mask(
        image_ref, str(recipe.get("text") or "face")))
    prediction = torch.where(
        prediction > threshold, prediction, torch.zeros_like(prediction))
    if blur > 0:
        prediction = _gaussian_mask(
            prediction, max(1, math.ceil(4.0 * blur)), blur)
    minimum, maximum = prediction.amin(), prediction.amax()
    span = maximum - minimum
    prediction = (
        (prediction - minimum) / span
        if float(span) > torch.finfo(prediction.dtype).eps
        else torch.zeros_like(prediction)
    )
    prediction = _dilate_mask(prediction, dilation)
    if tuple(prediction.shape[-2:]) != (height, width):
        prediction = F.interpolate(
            prediction.unsqueeze(1), size=(height, width), mode="bilinear",
            align_corners=False)[:, 0]
    components = _connected_components(
        (prediction.amax(dim=0) > 0.5).cpu().numpy())
    output = []
    for index, (bbox, component) in enumerate(components):
        left, top, right, bottom = bbox
        if right - left < drop_size or bottom - top < drop_size:
            continue
        crop = _expand_box(bbox, crop_factor, width, height)
        crop_left, crop_top, crop_right, crop_bottom = crop
        mask = torch.zeros((1, crop_bottom - crop_top, crop_right - crop_left))
        if bbox_fill:
            mask[:, top - crop_top:bottom - crop_top,
                 left - crop_left:right - crop_left] = 1.0
        else:
            for x, y in component:
                mask[:, y - crop_top, x - crop_left] = 1.0
        output.append({
            "bbox": bbox, "crop": crop, "mask": mask,
            "score": 1.0, "label": str(index + 1),
        })
    return output


async def _detect_segments(
    detector, image_ref, pixels, threshold, dilation, crop_factor, drop_size,
    *, segmentation: bool = False,
):
    height, width = map(int, pixels.shape[1:3])
    detections: list[dict[str, Any]] = []
    if _onnx_detector.is_recipe(detector):
        detections = list(
            await _onnx_detector.detect(_ctx(), detector, pixels))
    elif isinstance(detector, sdk.ObjectDetectorRef):
        batches = await detector.detect(
            image_ref, threshold=float(threshold), max_detections=64)
        detections = list(batches[0] if batches else [])
    else:
        detector = await materialize(detector)
        if (isinstance(detector, dict)
                and detector.get("secure_kind") == "impact.clipseg_bbox"):
            return await _clipseg_recipe_segments(
                detector, image_ref, width=width, height=height,
                crop_factor=float(crop_factor), drop_size=int(drop_size),
                bbox_fill=not segmentation)
        elif (isinstance(detector, dict)
              and detector.get("secure_kind") == "impact.ultralytics_bbox"):
            # The converted Impact provider exports a closed recipe.  Execute
            # it through the pack-local, pinned Ultralytics runtime; it never
            # receives a host path or an executable checkpoint.
            detections = await _ultralytics_recipe_detect(
                detector, image_ref, pixels, float(threshold))
        else:
            raise TypeError("unsupported secure BBOX_DETECTOR value")
    output = []
    for item in detections[:64]:
        score = float(item.get("score", item.get("confidence", 0.0)))
        if score <= float(threshold):
            continue
        segment = _box_segment(
            item.get("box", item.get("bbox", ())), score,
            str(item.get("label", "segment")), width=width, height=height,
            crop_factor=float(crop_factor), dilation=int(dilation),
            drop_size=int(drop_size),
        )
        if segment is not None:
            output.append(segment)
    return output


_YOLO_CACHE: dict[str, Any] = {}


async def _ultralytics_recipe_detect(
    recipe: dict[str, Any], image_ref, pixels: torch.Tensor, threshold: float,
) -> list[dict[str, Any]]:
    weight = str(recipe.get("weight", ""))
    classes = recipe.get("classes")
    size = int(recipe.get("input_size", 640))
    if (not weight.endswith((".safetensors", ".sft"))
            or recipe.get("architecture") != "yolov8x"
            or not isinstance(classes, list) or not classes
            or not all(isinstance(item, str) and item for item in classes)
            or not 64 <= size <= 2048):
        raise ValueError("Impact Ultralytics detector recipe is invalid")
    model = _YOLO_CACHE.get(weight)
    if model is None:
        from ultralytics.nn.tasks import DetectionModel

        asset = await _ctx().assets.resolve("detection", weight)
        state = await _ctx().assets.load_state_dict(asset)
        normalized = {}
        for key, tensor in state.items():
            if not isinstance(key, str) or not key.startswith("model."):
                raise ValueError("Ultralytics state keys must start with model.")
            normalized[key.removeprefix("model.")] = tensor.detach().cpu()
        model = DetectionModel(
            "yolov8x.yaml", ch=3, nc=len(classes), verbose=False)
        model.load_state_dict(normalized, strict=True)
        model.eval().requires_grad_(False)
        _YOLO_CACHE[weight] = model
    source_height, source_width = map(int, pixels.shape[1:3])
    scale = min(size / source_height, size / source_width)
    target_h = max(1, min(size, round(source_height * scale)))
    target_w = max(1, min(size, round(source_width * scale)))
    network = F.interpolate(
        pixels[..., :3].movedim(-1, 1), size=(target_h, target_w),
        mode="bilinear", align_corners=False)
    pad_x, pad_y = (size - target_w) // 2, (size - target_h) // 2
    network = F.pad(network, (
        pad_x, size - target_w - pad_x, pad_y, size - target_h - pad_y,
    ), value=114 / 255)
    with torch.inference_mode():
        prediction = model(network)
        if isinstance(prediction, (tuple, list)):
            prediction = prediction[0]
    from ultralytics.utils.ops import non_max_suppression

    selected = non_max_suppression(
        prediction, conf_thres=threshold, iou_thres=0.7,
        max_det=64, nc=len(classes))[0]
    result = []
    for row in selected.detach().cpu():
        left, top, right, bottom, score, index = row[:6].tolist()
        index = int(index)
        if not 0 <= index < len(classes):
            continue
        result.append({
            "box": [
                (left - pad_x) / scale, (top - pad_y) / scale,
                (right - pad_x) / scale, (bottom - pad_y) / scale,
            ],
            "score": float(score),
            "label": classes[index],
        })
    return result


def _sam_mask_area_hints(
    segment: dict[str, Any], threshold: float, use_negative: bool,
) -> tuple[list[list[float]], list[int]]:
    left, top, _right, _bottom = map(int, segment["crop"])
    mask = torch.as_tensor(segment["mask"])[0]
    y_step = max(3, int(mask.shape[0]) // 20)
    x_step = max(3, int(mask.shape[1]) // 20)
    points: list[list[float]] = []
    labels: list[int] = []
    for y in range(0, int(mask.shape[0]), y_step):
        for x in range(0, int(mask.shape[1]), x_step):
            value = float(mask[y, x])
            if value > threshold:
                points.append([float(left + x), float(top + y)])
                labels.append(1)
            elif use_negative and value == 0.0:
                points.append([float(left + x), float(top + y)])
                labels.append(0)
    return points, labels


def _sam_outer_negative_hints(
    image_width: int, image_height: int,
    crop: tuple[int, int, int, int],
) -> tuple[list[list[float]], list[int]]:
    left, top, right, bottom = crop
    y_step = max(3, image_height // 20)
    x_step = max(3, image_width // 20)
    points = []
    for y in range(10, max(10, image_height - 10), y_step):
        for x in range(10, max(10, image_width - 10), x_step):
            if not (left - 10 <= x <= right + 10
                    and top - 10 <= y <= bottom + 10):
                points.append([float(x), float(y)])
    return points, [0] * len(points)


def _sam_detection_hints(
    segment: dict[str, Any], *, hint: str, image_width: int,
    image_height: int, bbox_expansion: int, mask_hint_threshold: float,
    mask_hint_use_negative: str,
) -> tuple[list[float], list[list[float]], list[int]]:
    if hint not in {
        "center-1", "horizontal-2", "vertical-2", "rect-4", "diamond-4",
        "mask-area", "mask-point-bbox", "none",
    }:
        raise ValueError(f"unknown SAM detection hint {hint!r}")
    if mask_hint_use_negative not in {"False", "Small", "Outter"}:
        raise ValueError("unknown SAM negative-hint mode")
    if not 0.0 <= mask_hint_threshold <= 1.0:
        raise ValueError("SAM mask hint threshold must be in [0, 1]")
    left, top, right, bottom = map(float, segment["bbox"])
    box = [
        max(0.0, left - bbox_expansion),
        max(0.0, top - bbox_expansion),
        min(float(image_width), right + bbox_expansion),
        min(float(image_height), bottom + bbox_expansion),
    ]
    x1, y1, x2, y2 = box
    center = [(left + right) / 2.0, (top + bottom) / 2.0]
    points: list[list[float]] = []
    labels: list[int] = []
    if hint in {"center-1", "mask-point-bbox"}:
        points, labels = [center], [1]
    elif hint == "horizontal-2":
        gap = (x2 - x1) / 3.0
        points = [[x1 + gap, center[1]], [x1 + 2 * gap, center[1]]]
        labels = [1, 1]
    elif hint == "vertical-2":
        gap = (y2 - y1) / 3.0
        points = [[center[0], y1 + gap], [center[0], y1 + 2 * gap]]
        labels = [1, 1]
    elif hint == "rect-4":
        x_gap, y_gap = (x2 - x1) / 3.0, (y2 - y1) / 3.0
        points = [
            [x1 + x_gap, center[1]], [x1 + 2 * x_gap, center[1]],
            [center[0], y1 + y_gap], [center[0], y1 + 2 * y_gap],
        ]
        labels = [1, 1, 1, 1]
    elif hint == "diamond-4":
        x_gap, y_gap = (x2 - x1) / 3.0, (y2 - y1) / 3.0
        points = [
            [x1 + x_gap, y1 + y_gap], [x1 + 2 * x_gap, y1 + y_gap],
            [x1 + x_gap, y1 + 2 * y_gap],
            [x1 + 2 * x_gap, y1 + 2 * y_gap],
        ]
        labels = [1, 1, 1, 1]
    elif hint == "mask-area":
        points, labels = _sam_mask_area_hints(
            segment, mask_hint_threshold,
            mask_hint_use_negative == "Small")
    if mask_hint_use_negative == "Outter":
        extra_points, extra_labels = _sam_outer_negative_hints(
            image_width, image_height, tuple(map(int, segment["crop"])))
        points.extend(extra_points)
        labels.extend(extra_labels)
    return box, points, labels


async def _refine_with_sam(
    segments: list[dict[str, Any]], sam_model, image_ref,
    *, hint: str, dilation: int, threshold: float, bbox_expansion: int,
    mask_hint_threshold: float, mask_hint_use_negative: str,
) -> list[dict[str, Any]]:
    if sam_model is None:
        return segments
    if not isinstance(sam_model, sdk.SamModelRef):
        raise TypeError("sam_model_opt must be a SAM_MODEL reference")
    if not segments:
        return segments
    height, width = await image_ref.spatial_shape()
    if hint == "mask-points":
        query_points = []
        query_labels = []
        for segment in segments:
            left, top, right, bottom = segment["bbox"]
            query_points.append([(left + right) / 2.0, (top + bottom) / 2.0])
            query_labels.append(
                0 if mask_hint_use_negative == "Small" and right - left < 10
                else 1)
        boxes: list[list[float] | None] = [None]
        points = [query_points]
        labels = [query_labels]
    else:
        boxes = []
        points = []
        labels = []
        for segment in segments:
            box, query_points, query_labels = _sam_detection_hints(
                segment, hint=hint, image_width=width, image_height=height,
                bbox_expansion=int(bbox_expansion),
                mask_hint_threshold=float(mask_hint_threshold),
                mask_hint_use_negative=str(mask_hint_use_negative))
            boxes.append(box)
            points.append(query_points)
            labels.append(query_labels)
    masks_ref, scores = await sam_model.segment(
        image_ref, boxes, point_coords=points, point_labels=labels,
        multimask_output=True)
    masks = torch.as_tensor(await masks_ref.raw()).float()
    if masks.ndim != 4 or masks.shape[0] != len(boxes):
        raise RuntimeError("SAM returned an invalid mask batch")
    if len(scores) != len(boxes):
        raise RuntimeError("SAM returned an invalid score batch")
    combined = torch.zeros((1, height, width), dtype=masks.dtype)
    for candidates, candidate_scores in zip(masks, scores, strict=True):
        if len(candidate_scores) != int(candidates.shape[0]) or not candidate_scores:
            raise RuntimeError("SAM returned invalid mask scores")
        accepted = [
            index for index, score in enumerate(candidate_scores)
            if float(score) >= float(threshold)
        ]
        if not accepted:
            accepted = [max(range(len(candidate_scores)),
                            key=lambda index: candidate_scores[index])]
        combined = torch.maximum(
            combined, candidates[accepted].amax(dim=0, keepdim=True).cpu())
    combined = _dilate_mask(combined, int(dilation)).clamp(0, 1)
    result = []
    for segment in segments:
        left, top, right, bottom = segment["crop"]
        cropped = (
            segment["mask"]
            * combined[:, top:bottom, left:right].to(segment["mask"].dtype)
        )
        if torch.any(cropped > 0):
            result.append({**segment, "mask": cropped})
    return result


def _segment_sort(segments: list[dict[str, Any]], mode: str):
    if mode == "left-right":
        return sorted(segments, key=lambda item: (item["bbox"][0], item["bbox"][1]))
    if mode == "top-bottom":
        return sorted(segments, key=lambda item: (item["bbox"][1], item["bbox"][0]))
    if mode == "largest-first":
        return sorted(segments, key=lambda item: (
            (item["bbox"][2] - item["bbox"][0])
            * (item["bbox"][3] - item["bbox"][1])
        ), reverse=True)
    if mode == "confidence":
        return sorted(segments, key=lambda item: item["score"], reverse=True)
    if mode == "detector":
        return list(segments)
    raise ValueError("unknown segment_order")


async def _preview_descriptor(image: torch.Tensor) -> dict[str, Any] | None:
    ref = await sdk.ImageRef._from_raw(image)
    display = await _ctx().ui.preview_images(ref)
    images = display.get("images", ()) if isinstance(display, dict) else ()
    return dict(images[0]) if images else None


async def _detailer_payload(
    pixels: torch.Tensor, segments: list[dict[str, Any]], unique_id: Any,
) -> dict[str, Any]:
    height, width = map(int, pixels.shape[1:3])
    scale = min(1.0, 1280 / max(width, height))
    overview = pixels
    if scale < 1.0:
        overview = _resize_images(
            pixels, max(1, round(width * scale)), max(1, round(height * scale)))
    payload_segments = []
    for index, segment in enumerate(segments):
        left, top, right, bottom = segment["crop"]
        crop = pixels[:, top:bottom, left:right]
        crop_scale = min(1.0, 320 / max(int(crop.shape[1]), int(crop.shape[2])))
        if crop_scale < 1.0:
            crop = _resize_images(
                crop, max(1, round(crop.shape[2] * crop_scale)),
                max(1, round(crop.shape[1] * crop_scale)))
        payload_segments.append({
            "index": index,
            "label": segment["label"],
            "confidence": round(float(segment["score"]), 3),
            "bbox": list(segment["bbox"]),
            "crop_region": list(segment["crop"]),
            "preview": await _preview_descriptor(crop),
        })
    return {
        "variant": "vslinx-segment-prompts-v1",
        "node_id": str(unique_id) if unique_id is not None else None,
        "image_width": width,
        "image_height": height,
        "overview": {
            "preview": await _preview_descriptor(overview),
            "scale": scale,
        },
        "segments": payload_segments,
    }


async def _crop_conditioning(
    conditioning, crop: tuple[int, int, int, int],
    source_width: int, source_height: int, target_width: int, target_height: int,
):
    if not isinstance(conditioning, sdk.CondRef):
        return conditioning
    left, top, right, bottom = crop
    return await conditioning.spatial_crop(
        x=left, y=top, width=right - left, height=bottom - top,
        source_width=source_width, source_height=source_height,
        target_width=max(1, math.ceil(target_width / 8)),
        target_height=max(1, math.ceil(target_height / 8)),
    )


async def _encode_detail(
    vae, image_ref, mask: torch.Tensor | None, positive, negative,
    *, inpaint_model: bool, tiled_encode: bool,
):
    if inpaint_model:
        if mask is None:
            raise ValueError("inpaint_model requires a noise mask")
        mask_ref = await sdk.MaskRef._from_raw(mask)
        return await vae.encode_inpaint_conditioning(
            image_ref, mask_ref, positive, negative, noise_mask=True)
    latent = (
        await vae.encode_tiled(image_ref, tile_x=512, tile_y=512, overlap=64)
        if tiled_encode else await vae.encode(image_ref)
    )
    if mask is not None:
        value = dict(await latent.value())
        value["noise_mask"] = mask
        latent = await sdk.LatentRef.from_value(value)
    return positive, negative, latent


_DETAILER_HOOK_KINDS = frozenset({
    "BlackPatchRetryHookProvider",
    "CoreMLDetailerHookProvider",
    "CustomSamplerDetailerHookProvider",
    "DenoiseSchedulerDetailerHookProvider",
    "LamaRemoverDetailerHookProvider",
    "NoiseInjectionDetailerHookProvider",
    "PreviewDetailerHookProvider",
    "SEGSLabelFilterDetailerHookProvider",
    "SEGSOrderedFilterDetailerHookProvider",
    "SEGSRangeFilterDetailerHookProvider",
    "UnsamplerDetailerHookProvider",
    "VariationNoiseDetailerHookProvider",
})


def _detailer_hook_recipes(hook: Any) -> list[dict[str, Any]]:
    """Flatten Impact Pack's closed, data-only hook language in order."""
    if hook is None:
        return []
    if not isinstance(hook, dict):
        raise TypeError("DETAILER_HOOK must be a secure declarative recipe")
    kind = hook.get("secure_kind")
    if kind == "detailer_hook_chain":
        items = hook.get("items")
        if not isinstance(items, list):
            raise TypeError("detailer hook chain must contain a recipe list")
        result: list[dict[str, Any]] = []
        for item in items:
            result.extend(_detailer_hook_recipes(item))
        return result
    if kind not in _DETAILER_HOOK_KINDS:
        raise TypeError(f"unknown secure detailer hook recipe {kind!r}")
    if not isinstance(hook.get("params"), dict):
        raise TypeError("detailer hook recipe params must be a mapping")
    return [hook]


def _sigma_schedule_recipe(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or value.get("secure_kind") != "gits_scheduler":
        raise TypeError("SCHEDULER_FUNC must come from the secure GITS provider")
    params = value.get("params")
    if not isinstance(params, dict):
        raise TypeError("GITS scheduler recipe params must be a mapping")
    coefficient = float(params.get("coeff", 1.2))
    denoise = float(params.get("denoise", 1.0))
    if not 0.8 <= coefficient <= 1.5 or not 0.0 <= denoise <= 1.0:
        raise ValueError("GITS scheduler values are outside their closed bounds")
    return {"kind": "gits", "coeff": coefficient, "denoise": denoise}


def _segment_metric(segment: dict[str, Any], target: str) -> float:
    left, top, right, bottom = map(float, segment["crop"])
    width, height = right - left, bottom - top
    values = {
        "area(=w*h)": width * height,
        "width": width,
        "height": height,
        "x1": left,
        "y1": top,
        "x2": right,
        "y2": bottom,
        "length_percent": max(height / max(width, 1.0),
                              width / max(height, 1.0)) * 100.0,
    }
    if target not in values:
        raise ValueError(f"unknown SEGS metric {target!r}")
    return values[target]


def _coreml_resolution(recipe: dict[str, Any]) -> tuple[int, int]:
    match = re.fullmatch(r"(512|768)x(512|768)",
                         str(recipe["params"].get("mode", "")))
    if match is None:
        raise ValueError("CoreML detailer mode must be a supported resolution")
    return int(match.group(1)), int(match.group(2))


def _coreml_crop(
    segment: dict[str, Any], image_width: int, image_height: int,
    target_width: int, target_height: int,
) -> dict[str, Any]:
    left, top, right, bottom = map(int, segment["crop"])
    bbox_left, bbox_top, bbox_right, bbox_bottom = map(int, segment["bbox"])
    left, top = max(0, left), max(0, top)
    right, bottom = min(image_width, right), min(image_height, bottom)
    crop_width, crop_height = right - left, bottom - top
    if crop_width <= 0 or crop_height <= 0:
        return segment
    target_ratio, crop_ratio = target_width / target_height, crop_width / crop_height
    new_left, new_top, new_right, new_bottom = left, top, right, bottom
    if crop_ratio < target_ratio:
        wanted = min(crop_height, max(
            bbox_bottom - bbox_top, round(crop_width / target_ratio)))
        removable = crop_height - wanted
        before, after = max(0, bbox_top - top), max(0, bottom - bbox_bottom)
        offset = round(removable * before / (before + after)) if before + after else removable // 2
        new_top = max(top, min(top + offset, bottom - wanted))
        new_bottom = new_top + wanted
    elif crop_ratio > target_ratio:
        wanted = min(crop_width, max(
            bbox_right - bbox_left, round(crop_height * target_ratio)))
        removable = crop_width - wanted
        before, after = max(0, bbox_left - left), max(0, right - bbox_right)
        offset = round(removable * before / (before + after)) if before + after else removable // 2
        new_left = max(left, min(left + offset, right - wanted))
        new_right = new_left + wanted
    if (new_left, new_top, new_right, new_bottom) == (left, top, right, bottom):
        return segment
    mask = _resize_images(
        segment["mask"].unsqueeze(-1), crop_width, crop_height,
        "bilinear")[..., 0]
    mask = mask[:, new_top - top:new_bottom - top,
                new_left - left:new_right - left].clone()
    return {**segment, "crop": (new_left, new_top, new_right, new_bottom),
            "mask": mask}


def _detailer_hook_post_detection(
    segments: list[dict[str, Any]], hook: Any, width: int, height: int,
) -> list[dict[str, Any]]:
    current = list(segments)
    recipes = _detailer_hook_recipes(hook)
    for recipe in recipes:
        if recipe["secure_kind"] == "CoreMLDetailerHookProvider":
            target_width, target_height = _coreml_resolution(recipe)
            current = [_coreml_crop(
                segment, width, height, target_width, target_height)
                for segment in current]
    for recipe in recipes:
        kind, params = recipe["secure_kind"], recipe["params"]
        if kind == "SEGSOrderedFilterDetailerHookProvider":
            current.sort(
                key=lambda item: _segment_metric(
                    item, str(params.get("target", "area(=w*h)"))),
                reverse=bool(params.get("order", True)))
            start = max(0, int(params.get("take_start", 0)))
            count = max(0, int(params.get("take_count", 1)))
            current = current[start:start + count]
        elif kind == "SEGSRangeFilterDetailerHookProvider":
            target = str(params.get("target", "area(=w*h)"))
            minimum, maximum = float(params.get("min_value", 0)), float(
                params.get("max_value", 67_108_864))
            inside_mode = bool(params.get("mode", True))
            current = [item for item in current if
                       (minimum <= _segment_metric(item, target) <= maximum)
                       == inside_mode]
        elif kind == "SEGSLabelFilterDetailerHookProvider":
            wanted = {str(params.get("preset", ""))} | {
                value.strip() for value in str(params.get("labels", "")).split(",")
            }
            wanted.discard("")
            if "all" not in wanted:
                aliases = {
                    "eyes": {"left_eye", "right_eye"},
                    "eyebrows": {"left_eyebrow", "right_eyebrow"},
                    "pupils": {"left_pupil", "right_pupil"},
                }
                current = [item for item in current if item["label"] in wanted
                           or any(item["label"] in aliases.get(name, ())
                                  for name in wanted)]
    return current


def _hook_scaled_size(hook: Any, width: int, height: int) -> tuple[int, int]:
    for recipe in _detailer_hook_recipes(hook):
        if recipe["secure_kind"] == "CoreMLDetailerHookProvider":
            width, height = _coreml_resolution(recipe)
    return width, height


def _hook_denoise(hook: Any, denoise: float, index: int, total: int) -> float:
    value = float(denoise)
    for recipe in _detailer_hook_recipes(hook):
        if recipe["secure_kind"] != "DenoiseSchedulerDetailerHookProvider":
            continue
        target = float(recipe["params"].get("target_denoise", 0.3))
        if not 0.0 <= target <= 1.0:
            raise ValueError("detailer target_denoise must be in [0, 1]")
        if total > 1:
            value += (target - value) * index / (total - 1)
    return value


def _hook_sampler(hook: Any):
    for recipe in _detailer_hook_recipes(hook):
        if recipe["secure_kind"] == "CustomSamplerDetailerHookProvider":
            sampler = recipe["params"].get("sampler")
            if not isinstance(sampler, sdk.SamplerRef):
                raise TypeError("custom detailer sampler must be a SAMPLER ref")
            return sampler
    return None


async def _hook_variation_noise(latent, hook: Any, seed: int):
    recipes = [item for item in _detailer_hook_recipes(hook)
               if item["secure_kind"] == "VariationNoiseDetailerHookProvider"]
    if not recipes:
        return None
    samples = torch.as_tensor((await latent.value())["samples"])
    generator = torch.Generator(device="cpu").manual_seed(int(seed))
    noise = torch.randn(samples.shape, generator=generator,
                        dtype=samples.dtype, device="cpu")
    for recipe in recipes:
        params = recipe["params"]
        strength = float(params.get("strength", 0.0))
        if not 0.0 <= strength <= 1.0:
            raise ValueError("variation-noise strength must be in [0, 1]")
        variation = torch.randn(
            samples.shape,
            generator=torch.Generator(device="cpu").manual_seed(
                int(params.get("seed", 0))),
            dtype=samples.dtype, device="cpu")
        scale = math.sqrt((1.0 - strength) ** 2 + strength ** 2)
        noise = ((1.0 - strength) * noise + strength * variation) / max(
            scale, torch.finfo(noise.dtype).eps)
    return await sdk.TensorRef._from_raw(noise)


async def _hook_cycle_latent(latent, hook: Any, index: int, total: int):
    current = latent
    for recipe in _detailer_hook_recipes(hook):
        kind, params = recipe["secure_kind"], recipe["params"]
        if kind not in {"NoiseInjectionDetailerHookProvider",
                        "UnsamplerDetailerHookProvider"}:
            continue
        from_start = "from_start" in str(params.get(
            "schedule_for_cycle", "skip_start"))
        if index == 0 and not from_start:
            continue
        step = index if from_start else index - 1
        span = total if from_start else total - 1
        if span <= 0:
            continue
        if kind == "UnsamplerDetailerHookProvider":
            start, end = int(params.get("start_end_at_step", 21)), int(
                params.get("end_end_at_step", 24))
            current = await _ctx().unsample(
                current, steps=int(params.get("steps", 25)),
                model=params.get("model"), positive=params.get("positive"),
                negative=params.get("negative"), cfg=float(params.get("cfg", 1.0)),
                sampler_name=str(params.get("sampler_name", "euler")),
                scheduler=str(params.get("scheduler", "normal")),
                end_at_step=int(start + (end - start) * step / span),
                normalize=str(params.get("normalize", "disable")) == "enable")
            continue
        start, end = float(params.get("start_strength", 2.0)), float(
            params.get("end_strength", 1.0))
        strength = start + (end - start) * step / span
        if not 0.0 <= strength <= 200.0:
            raise ValueError("detailer injected-noise strength is out of range")
        value = dict(await current.value())
        samples = torch.as_tensor(value["samples"])
        noise = torch.randn(
            samples.shape,
            generator=torch.Generator(device="cpu").manual_seed(
                int(params.get("seed", 0)) + step * 2),
            dtype=samples.dtype, device="cpu").to(samples.device)
        injected = samples + noise * strength
        if value.get("noise_mask") is not None:
            mask = torch.as_tensor(value["noise_mask"]).float()
            if mask.ndim == 3:
                mask = mask[:, None]
            mask = F.interpolate(mask, size=samples.shape[-2:], mode="bilinear",
                                 align_corners=False).to(samples.device, samples.dtype)
            injected = mask * injected + (1.0 - mask) * samples
        value["samples"] = injected
        current = await sdk.LatentRef.from_value(value)
    return current


async def _hook_coreml_batch(latent, hook: Any, *, before_decode: bool):
    count = sum(recipe["secure_kind"] == "CoreMLDetailerHookProvider"
                for recipe in _detailer_hook_recipes(hook))
    if count == 0:
        return latent
    value = dict(await latent.value())
    samples = torch.as_tensor(value["samples"])
    for _ in range(count):
        samples = samples[:1] if before_decode else samples.repeat(
            (2,) + (1,) * (samples.ndim - 1))
    value["samples"] = samples
    return await sdk.LatentRef.from_value(value)


def _hook_skip_sampling(hook: Any) -> bool:
    recipes = _detailer_hook_recipes(hook)
    return bool(recipes) and all(
        item["secure_kind"] == "LamaRemoverDetailerHookProvider"
        and item["params"].get("skip_sampling", True) is True
        for item in recipes)


async def _hook_post_upscale(image: torch.Tensor, mask: torch.Tensor | None,
                             hook: Any) -> torch.Tensor:
    current = image.cpu()
    for recipe in _detailer_hook_recipes(hook):
        if recipe["secure_kind"] != "LamaRemoverDetailerHookProvider":
            continue
        if mask is None:
            raise ValueError("LaMa detailer hook requires a noise mask")
        params, model = recipe["params"], recipe["params"].get("model")
        if not isinstance(model, sdk.InpaintModelRef):
            raise TypeError("LaMa detailer hook has no typed inpaint model")
        threshold, radius = int(params.get("mask_threshold", 250)), int(
            params.get("gaussblur_radius", 8))
        if not 0 <= threshold <= 255 or not 0 <= radius <= 20:
            raise ValueError("LaMa detailer mask settings are out of range")
        height, width = map(int, current.shape[1:3])
        prepared_masks = []
        for item in _resize_images(mask.unsqueeze(-1), width, height)[..., 0]:
            array = (item.clamp(0, 1) * 255).to(torch.uint8).cpu().numpy()
            pil = ImageOps.invert(Image.fromarray(array, mode="L"))
            pil = pil.filter(ImageFilter.GaussianBlur(radius=radius))
            pil = pil.point(lambda value: 0 if value > threshold else 255)
            prepared_masks.append(torch.from_numpy(
                np.asarray(pil).copy()).float() / 255.0)
        image_ref = await sdk.ImageRef._from_raw(current)
        mask_ref = await sdk.MaskRef._from_raw(torch.stack(prepared_masks))
        result = await model.inpaint(image_ref, mask_ref)
        current = (await _raw_image(result)).cpu()
    return current


async def _hook_post_paste(image: torch.Tensor, hook: Any,
                           value: int, total: int) -> None:
    for recipe in _detailer_hook_recipes(hook):
        if recipe["secure_kind"] != "PreviewDetailerHookProvider":
            continue
        quality = int(recipe["params"].get("quality", 95))
        if not 20 <= quality <= 100:
            raise ValueError("preview-hook quality must be in [20, 100]")
        await _ctx().progress.update(
            max(0, int(value)), max(1, int(total)),
            preview=await sdk.ImageRef._from_raw(image))


async def _detail_sample(
    latent, *, model, positive, negative, seed, steps, cfg, sampler_name,
    scheduler, denoise, cycle, detailer_hook, scheduler_func_opt,
):
    sigma_schedule = _sigma_schedule_recipe(scheduler_func_opt)
    current = latent
    total = max(1, int(cycle))
    sampler = _hook_sampler(detailer_hook)
    for index in range(total):
        current = await _hook_cycle_latent(current, detailer_hook, index, total)
        cycle_denoise = _hook_denoise(
            detailer_hook, float(denoise), index, total)
        if cycle_denoise <= 0:
            continue
        current = await _ctx().sample(
            latent=current, model=model, positive=positive, negative=negative,
            seed=int(seed) + index, steps=max(1, int(steps)), cfg=float(cfg),
            sampler_name=str(sampler_name), scheduler=str(scheduler),
            denoise=cycle_denoise, force_full_denoise=True,
            sampler=sampler,
            noise=await _hook_variation_noise(
                current, detailer_hook, int(seed) + index),
            sigma_schedule=sigma_schedule)
    return current


async def _detail_one(
    output: torch.Tensor, segment: dict[str, Any], prompt_text: str, *,
    model, clip, vae, positive, negative, guide_size, guide_size_for,
    max_size, seed, steps, cfg, sampler_name, scheduler, denoise, feather,
    noise_mask, force_inpaint, cycle, inpaint_model, noise_mask_feather,
    tiled_encode, tiled_decode, detailer_hook, scheduler_func_opt,
) -> tuple[torch.Tensor | None, torch.Tensor | None]:
    if prompt_text.strip() == "[SKIP]":
        return None, None
    left, top, right, bottom = segment["crop"]
    crop = output[:, top:bottom, left:right].clone()
    crop_height, crop_width = map(int, crop.shape[1:3])
    bbox = segment["bbox"]
    bbox_width, bbox_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
    if (not force_inpaint and bbox_width >= float(guide_size)
            and bbox_height >= float(guide_size)):
        return None, None
    basis = min(bbox_width, bbox_height) if guide_size_for else min(
        crop_width, crop_height)
    scale = float(guide_size) / max(1.0, float(basis))
    target_width, target_height = int(crop_width * scale), int(crop_height * scale)
    if max(target_width, target_height) > int(max_size):
        ratio = int(max_size) / max(target_width, target_height)
        target_width, target_height = int(target_width * ratio), int(target_height * ratio)
    if scale <= 1.0:
        if not force_inpaint:
            return None, None
        target_width, target_height = crop_width, crop_height
    target_width, target_height = max(8, target_width), max(8, target_height)
    target_width, target_height = _hook_scaled_size(
        detailer_hook, target_width, target_height)
    working = _resize_images(crop, target_width, target_height)
    mask = _resize_images(
        segment["mask"].unsqueeze(-1), target_width, target_height,
        "bilinear")[..., 0]
    sample_mask = _blur_mask(mask, int(noise_mask_feather)) if noise_mask else None
    paste_mask = _blur_mask(segment["mask"], int(feather))
    working = await _hook_post_upscale(working, sample_mask, detailer_hook)
    if _hook_skip_sampling(detailer_hook):
        enhanced = _resize_images(working, crop_width, crop_height)
        alpha = paste_mask[..., None]
        output[:, top:bottom, left:right, :3] = (
            output[:, top:bottom, left:right, :3] * (1.0 - alpha)
            + enhanced[..., :3] * alpha
        )
        return enhanced, torch.cat((enhanced[..., :3], alpha), dim=-1)
    local_positive = await _crop_conditioning(
        positive, segment["crop"], int(output.shape[2]), int(output.shape[1]),
        target_width, target_height)
    local_negative = await _crop_conditioning(
        negative, segment["crop"], int(output.shape[2]), int(output.shape[1]),
        target_width, target_height)
    prompt = prompt_text.strip()
    concat = prompt.startswith("[CONCAT]")
    if concat:
        prompt = prompt[len("[CONCAT]"):].strip()
    if prompt:
        encoded = await clip.encode(prompt)
        local_positive = (
            await local_positive.concat(encoded) if concat else encoded)
    working_ref = await sdk.ImageRef._from_raw(working)
    sampled_positive, sampled_negative, latent = await _encode_detail(
        vae, working_ref, sample_mask, local_positive, local_negative,
        inpaint_model=bool(inpaint_model), tiled_encode=bool(tiled_encode))
    latent = await _hook_coreml_batch(
        latent, detailer_hook, before_decode=False)
    current = await _detail_sample(
        latent, model=model, positive=sampled_positive,
        negative=sampled_negative, seed=int(seed), steps=int(steps),
        cfg=float(cfg), sampler_name=str(sampler_name),
        scheduler=str(scheduler), denoise=float(denoise), cycle=int(cycle),
        detailer_hook=detailer_hook,
        scheduler_func_opt=scheduler_func_opt)
    current = await _hook_coreml_batch(
        current, detailer_hook, before_decode=True)
    decoded_ref = (
        await vae.decode_tiled(current, tile_size=512, overlap=64)
        if tiled_decode else await vae.decode(current)
    )
    enhanced = _resize_images(
        await _raw_image(decoded_ref), crop_width, crop_height)
    alpha = paste_mask[..., None]
    output[:, top:bottom, left:right, :3] = (
        output[:, top:bottom, left:right, :3] * (1.0 - alpha)
        + enhanced[..., :3] * alpha
    )
    enhanced_alpha = torch.cat((enhanced[..., :3], alpha), dim=-1)
    return enhanced, enhanced_alpha


async def _interactive_detailer(
    image, model, clip, vae, guide_size, guide_size_for, max_size, seed,
    steps, cfg, sampler_name, scheduler, positive, negative, denoise, feather,
    noise_mask, force_inpaint, bbox_threshold, bbox_dilation,
    bbox_crop_factor, sam_detection_hint, sam_dilation, sam_threshold,
    sam_bbox_expansion, sam_mask_hint_threshold, sam_mask_hint_use_negative,
    drop_size, bbox_detector, cycle, segment_order, timeout_sec, on_timeout,
    always_ask, sam_model_opt=None, segm_detector_opt=None,
    detailer_hook=None, inpaint_model=False, noise_mask_feather=20,
    scheduler_func_opt=None, tiled_encode=False, tiled_decode=False,
    unique_id=None, **_kwargs,
):
    del always_ask
    detailer_hook = await materialize(detailer_hook)
    scheduler_func_opt = await materialize(scheduler_func_opt)
    _detailer_hook_recipes(detailer_hook)
    _sigma_schedule_recipe(scheduler_func_opt)
    if not all((isinstance(image, sdk.ImageRef), isinstance(model, sdk.ModelRef),
                isinstance(clip, sdk.ClipRef), isinstance(vae, sdk.VaeRef),
                isinstance(positive, sdk.CondRef), isinstance(negative, sdk.CondRef))):
        raise TypeError("Interactive Detailer requires typed model/image refs")
    pixels = await _raw_image(image)
    if int(pixels.shape[0]) != 1:
        raise ValueError("Interactive Detailer accepts one image at a time")
    segments = await _detect_segments(
        bbox_detector, image, pixels, bbox_threshold, bbox_dilation,
        bbox_crop_factor, drop_size)
    segments = _detailer_hook_post_detection(
        segments, detailer_hook, int(pixels.shape[2]), int(pixels.shape[1]))
    if sam_model_opt is None and segm_detector_opt is not None:
        # Mask-native Impact detector recipes are applied as a closed binary
        # intersection without invoking callback objects.
        segm_recipe = await materialize(segm_detector_opt)
        refined = await _detect_segments(
            segm_recipe, image, pixels, bbox_threshold, bbox_dilation,
            bbox_crop_factor, drop_size, segmentation=True)
        if refined:
            override = (
                isinstance(segm_recipe, dict)
                and bool(segm_recipe.get("override_bbox_by_segm", False))
                and (detailer_hook is None or (
                    isinstance(detailer_hook, dict)
                    and "override_bbox_by_segm" in detailer_hook))
            )
            if override:
                segments = refined
            else:
                union = torch.zeros((1, pixels.shape[1], pixels.shape[2]))
                for item in refined:
                    left, top, right, bottom = item["crop"]
                    union[:, top:bottom, left:right] = torch.maximum(
                        union[:, top:bottom, left:right], item["mask"])
                kept = []
                for item in segments:
                    left, top, right, bottom = item["crop"]
                    mask = item["mask"] * union[:, top:bottom, left:right]
                    if torch.any(mask > 0):
                        kept.append({**item, "mask": mask})
                segments = kept
    segments = await _refine_with_sam(
        segments, sam_model_opt, image, hint=str(sam_detection_hint),
        dilation=int(sam_dilation), threshold=float(sam_threshold),
        bbox_expansion=int(sam_bbox_expansion),
        mask_hint_threshold=float(sam_mask_hint_threshold),
        mask_hint_use_negative=str(sam_mask_hint_use_negative))
    segments = _segment_sort(segments, str(segment_order))
    combined = torch.zeros((1, pixels.shape[1], pixels.shape[2]))
    for item in segments:
        left, top, right, bottom = item["crop"]
        combined[:, top:bottom, left:right] = torch.maximum(
            combined[:, top:bottom, left:right], item["mask"])
    empty = torch.zeros((1, 64, 64, 3))
    if not segments:
        return pixels, [empty], [empty], combined, [empty], ""
    timeout_value = int(timeout_sec)
    if not 1 <= timeout_value <= 540:
        raise ValueError(
            "Interactive Detailer timeout_sec must be in [1, 540]; "
            "unbounded sandbox waits are not permitted")
    payload = await _detailer_payload(pixels, segments, unique_id)
    status = "ok"
    response = None
    try:
        response = await _ctx().interact.request(
            "prompt-await", payload,
            timeout=float(timeout_value))
    except TimeoutError:
        status = "timeout"
    if not isinstance(response, dict) or response.get("cancelled"):
        status = "timeout" if response is None else "cancelled"
    if status != "ok":
        if status == "cancelled" or on_timeout == "cancel run":
            raise RuntimeError("Interactive Detailer was cancelled")
        if on_timeout == "skip detailing":
            return pixels, [empty], [empty], combined, [empty], "(timed out - skipped)"
        prompts = [""] * len(segments)
    else:
        supplied = response.get("prompts", [])
        prompts = [str(value) if isinstance(value, str) else ""
                   for value in supplied[:len(segments)]]
        prompts.extend([""] * (len(segments) - len(prompts)))
    output = pixels.clone()
    enhanced: list[torch.Tensor] = []
    enhanced_alpha: list[torch.Tensor] = []
    for index, (segment, prompt) in enumerate(zip(segments, prompts, strict=True)):
        current, alpha = await _detail_one(
            output, segment, prompt,
            model=model, clip=clip, vae=vae, positive=positive,
            negative=negative, guide_size=guide_size,
            guide_size_for=guide_size_for, max_size=max_size,
            seed=int(seed) + index, steps=steps, cfg=cfg,
            sampler_name=sampler_name, scheduler=scheduler, denoise=denoise,
            feather=feather, noise_mask=noise_mask,
            force_inpaint=force_inpaint, cycle=cycle,
            inpaint_model=inpaint_model,
            noise_mask_feather=noise_mask_feather,
            tiled_encode=tiled_encode, tiled_decode=tiled_decode,
            detailer_hook=detailer_hook,
            scheduler_func_opt=scheduler_func_opt)
        if current is not None:
            enhanced.append(current)
            enhanced_alpha.append(alpha)
            await _hook_post_paste(
                output, detailer_hook, index + 1, len(segments))
    used = "\n".join(
        f"#{index + 1}: {prompt.strip() or '(base prompt)'}"
        for index, prompt in enumerate(prompts))
    return (
        output, enhanced or [empty], enhanced_alpha or [empty], combined,
        [empty], used,
    )


def _interactive_fingerprint(always_ask=True, **_kwargs):
    return float("nan") if bool(always_ask) else ""


_interactive_detailer.fingerprint_inputs = _interactive_fingerprint


_HANDLERS: dict[str, Any] = {
    "vsLinx_BooleanAndOperator": _legacy_raw(
        "vsLinx_BooleanAndOperator", boolean_alg.VSLinx_BooleanAndOperator,
        "compute"),
    "vsLinx_BooleanOrOperator": _legacy_raw(
        "vsLinx_BooleanOrOperator", boolean_alg.VSLinx_BooleanOrOperator,
        "compute"),
    "vsLinx_BooleanFlip": _legacy_raw(
        "vsLinx_BooleanFlip", boolean_alg.VSLinx_BooleanFlip, "compute"),
    "vsLinx_IntToBool": _legacy_raw(
        "vsLinx_IntToBool", boolean_alg.VSLinx_IntToBool, "compute"),
    "vsLinx_BypassOnBool": _forward,
    "vsLinx_MuteOnBool": _forward,
    "vsLinx_BypassMuteOnState": _state_forward,
    "vsLinx_GroupBookmarks": _bookmarks,
    "vsLinx_ImageToPixelArt": _legacy_raw(
        "vsLinx_ImageToPixelArt", pixel_alg.vsLinx_ImageToPixelArt,
        "convert"),
    "vsLinx_ImpactMultilineWildcardText": _legacy_raw(
        "vsLinx_ImpactMultilineWildcardText",
        wildcard_alg.vsLinx_ImpactMultilineWildcardText, "output"),
    "vsLinx_FitImageIntoBBoxMask": _legacy_raw(
        "vsLinx_FitImageIntoBBoxMask", inpaint_alg.vsLinx_FitImageIntoBBoxMask,
        "run"),
    "vsLinx_InteractiveDetailer": _interactive_detailer,
    "vsLinx_LoadLastGeneratedImage": _load_last,
    "vsLinx_AppendLorasFromNodeToString": _append_loras,
    "vsLinx_LoadSelectedImagesList": _selected_list,
    "vsLinx_LoadSelectedImagesBatch": _selected_batch,
    "vsLinx_MultiDiffusionTiledHiresFix": _multidiffusion,
    "vsLinx_AnyToPipe": _pack_pipe,
    "vsLinx_PipeToAny": _unpack_pipe,
    "vsLinx_UpscaleByFactorWithModel": _upscale,
    "vsLinx_VAEDecodeBatched": _decode_plain,
    "vsLinx_VAEDecodeTiledBatched": _decode_tiled,
    "vsLinx_AnimaLLLiteLoader": _anima_loader,
    "vsLinx_AnimaLLLiteTiledSampler": _anima_sampler,
}


_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "vsLinx_ImageToPixelArt": ("raw",),
    "vsLinx_FitImageIntoBBoxMask": ("raw",),
    "vsLinx_LoadSelectedImagesList": ("assets", "raw"),
    "vsLinx_LoadSelectedImagesBatch": ("assets", "raw"),
    "vsLinx_LoadLastGeneratedImage": ("assets", "raw"),
    "vsLinx_UpscaleByFactorWithModel": ("raw",),
    "vsLinx_VAEDecodeBatched": ("raw",),
    "vsLinx_VAEDecodeTiledBatched": ("raw",),
    "vsLinx_MultiDiffusionTiledHiresFix": ("raw", "sample"),
    "vsLinx_AnimaLLLiteTiledSampler": (
        "raw", "sample", "assets", "integrations.anima"),
    "vsLinx_InteractiveDetailer": (
        "raw", "sample", "assets", "ui", "ui.interact"),
}


NODE_CLASS_MAPPINGS = {
    node_id: bind_node(
        node_id, handler, permissions=_PERMISSIONS.get(node_id, ()))
    for node_id, handler in _HANDLERS.items()
}

NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: SCHEMAS[node_id]["schema"]["attrs"]["display_name"]
    for node_id in NODE_CLASS_MAPPINGS
}


if set(NODE_CLASS_MAPPINGS) != set(SCHEMAS):
    missing = sorted(set(SCHEMAS) - set(NODE_CLASS_MAPPINGS))
    extra = sorted(set(NODE_CLASS_MAPPINGS) - set(SCHEMAS))
    raise RuntimeError(f"vsLinx V2 census mismatch: missing={missing}, extra={extra}")


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
