"""Secure Nodes 2.0 implementations for LayerStyle's pinned node surface."""
from __future__ import annotations

import colorsys
import datetime as _datetime
import importlib
import io as _bytes_io
import math
import random
import re
from pathlib import PurePosixPath
from typing import Any

import numpy as np
import torch
import torch.nn.functional as torch_functional
from PIL import Image, ImageOps, ImageSequence

from . import _vitmatte, _vqa
from ._secure_runtime import (
    SCHEMAS,
    bind_node,
    has_tensor_io,
    materialize,
    sdk,
)


_IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff",
}
_MAX_IMAGE_BYTES = 256 * 1024 * 1024
_MAX_IMAGE_PIXELS = 67_108_864
_LEGACY_INSTANCES: dict[str, Any] = {}


def _ctx():
    return sdk.ctx()


def _safe_relative(value: Any, *, allow_empty: bool = False) -> str:
    name = str(value or "").replace("\\", "/").strip().strip("/")
    if not name and allow_empty:
        return ""
    path = PurePosixPath(name)
    if (
        not name
        or path.is_absolute()
        or any(part in ("", ".", "..") for part in path.parts)
        or ":" in path.parts[0]
        or "://" in name
    ):
        raise ValueError("the name must stay inside ComfyUI's managed directory")
    return path.as_posix()


def _legacy_handler(node_id: str):
    definition = SCHEMAS[node_id]

    async def execute(**kwargs: Any):
        module = importlib.import_module(f".{definition['module']}", __package__)
        instance = _LEGACY_INSTANCES.get(node_id)
        if instance is None:
            instance = getattr(module, definition["class"])()
            _LEGACY_INSTANCES[node_id] = instance
        values = {key: await materialize(value) for key, value in kwargs.items()}
        return getattr(instance, definition["method"])(**values)

    return execute


def _remove_empty_lines(value: Any) -> str:
    return "\n".join(line for line in str(value).splitlines() if line.strip())


def _timestamped(value: str, timestamp: str, now: _datetime.datetime) -> str:
    value = str(value).replace("%date", now.strftime("%Y-%m-%d"))
    value = value.replace("%time", now.strftime("%H-%M-%S"))
    if timestamp == "millisecond":
        return f"{value}_{now.strftime('%Y-%m-%d_%H-%M-%S-%f')[:-3]}"
    if timestamp == "second":
        return f"{value}_{now.strftime('%Y-%m-%d_%H-%M-%S')}"
    return value


async def _image_tagger_save(
    image,
    tag_text="",
    custom_path="",
    filename_prefix="comfyui",
    timestamp="None",
    format="png",
    quality=80,
    preview=True,
    custom_filename="",
    remove_custom_filename_ext=True,
    **_kwargs,
):
    now = _datetime.datetime.now()
    subfolder = _safe_relative(
        _timestamped(custom_path, "None", now), allow_empty=True)
    prefix = str(custom_filename or filename_prefix or "comfyui")
    if custom_filename and remove_custom_filename_ext:
        prefix = PurePosixPath(prefix.replace("\\", "/")).stem
    prefix = _safe_relative(_timestamped(prefix, timestamp, now))
    raw = await image.raw()
    if not isinstance(raw, torch.Tensor) or raw.ndim != 4 or len(raw) == 0:
        raise ValueError("ImageTaggerSave requires a non-empty BHWC image batch")
    first = await sdk.ImageRef._from_raw(raw[:1])
    result = await _ctx().output.save_images(
        first,
        filename_prefix=prefix,
        subfolder=subfolder,
        compress_level=max(0, min(9, (100 - int(quality)) // 10)),
        caption=_remove_empty_lines(tag_text),
        caption_extension=".txt",
        image_format=str(format).lower(),
        quality=int(quality),
    )
    return {"ui": result if bool(preview) else {"images": []}}


async def _mask_preview(mask, **_kwargs):
    raw = await mask.raw()
    if raw.ndim == 2:
        raw = raw.unsqueeze(0)
    elif raw.ndim == 4 and raw.shape[1] == 1:
        raw = raw[:, 0]
    elif raw.ndim == 4 and raw.shape[-1] == 1:
        raw = raw[..., 0]
    if raw.ndim != 3:
        raise ValueError("MaskPreview requires a BHW mask batch")
    preview = raw.unsqueeze(-1).expand(-1, -1, -1, 3).float()
    image = await sdk.ImageRef._from_raw(preview)
    return {
        "ui": await _ctx().ui.preview_mask(mask),
        "result": (image,),
    }


def _decode_asset_images(data: bytes) -> tuple[torch.Tensor, torch.Tensor]:
    if len(data) > _MAX_IMAGE_BYTES:
        raise ValueError("input image exceeds 256 MiB")
    images = []
    masks = []
    with Image.open(_bytes_io.BytesIO(data)) as source:
        expected_size = None
        for frame in ImageSequence.Iterator(source):
            frame = ImageOps.exif_transpose(frame)
            if frame.width * frame.height > _MAX_IMAGE_PIXELS:
                raise ValueError("input image exceeds 67108864 pixels")
            if expected_size is None:
                expected_size = frame.size
            if frame.size != expected_size:
                continue
            rgba = frame.convert("RGBA")
            array = np.asarray(rgba, dtype=np.float32) / 255.0
            images.append(torch.from_numpy(array[..., :3].copy()).unsqueeze(0))
            masks.append(torch.from_numpy((1.0 - array[..., 3]).copy()).unsqueeze(0))
    if not images:
        raise ValueError("input asset contains no decodable image frames")
    return torch.cat(images), torch.cat(masks)


async def _load_images_from_path(
    path="", image_load_cap=0, select_every_nth=1, **_kwargs,
):
    prefix = _safe_relative(path, allow_empty=True)
    if prefix:
        prefix = prefix.rstrip("/") + "/"
    names = await _ctx().assets.list("input", prefix=prefix, recursive=False)
    names = [
        name for name in names
        if PurePosixPath(name).suffix.lower() in _IMAGE_EXTENSIONS
    ]
    step = max(1, int(select_every_nth or 1))
    cap = max(0, int(image_load_cap or 0))
    selected = names[::step]
    if cap:
        selected = selected[:cap]
    if not selected:
        raise ValueError("the selected managed input folder contains no images")
    images = []
    masks = []
    filenames = []
    for name in selected:
        asset = await _ctx().assets.resolve("input", name)
        size = int(await _ctx().assets.size(asset))
        if not 0 <= size <= _MAX_IMAGE_BYTES:
            raise ValueError(f"input image {name!r} exceeds 256 MiB")
        image, mask = _decode_asset_images(await _ctx().assets.read_bytes(asset))
        images.append(image)
        masks.append(mask)
        filenames.append(PurePosixPath(name).name)
    return images, masks, filenames, len(images)


async def _queue_stop(any=None, mode="stop", stop=True, **_kwargs):
    if str(mode) == "stop" and bool(stop):
        await _ctx().graph.block("LayerStyle QueueStop requested termination")
    return (any,)


async def _purge_vram(
    anything=None, purge_cache=True, purge_models=True, return_value=False,
    **_kwargs,
):
    await _ctx().models.memory_cleanup(
        empty_cache=bool(purge_cache),
        collect_cycles=True,
        unload_all_models=bool(purge_models),
    )
    return (anything,) if return_value else ()


async def _purge_vram_v1(**kwargs):
    return await _purge_vram(**kwargs, return_value=False)


async def _purge_vram_v2(**kwargs):
    return await _purge_vram(**kwargs, return_value=True)


async def _image_list_to_batch(image=None, **_kwargs):
    batches = await materialize(image)
    if isinstance(batches, torch.Tensor):
        batches = [batches]
    if not isinstance(batches, list) or not batches:
        raise ValueError("ImageListToBatch requires at least one image batch")
    first = batches[0]
    if not isinstance(first, torch.Tensor) or first.ndim != 4:
        raise TypeError("ImageListToBatch expects BHWC tensors")
    height, width = first.shape[1:3]
    resized = []
    for batch in batches:
        if not isinstance(batch, torch.Tensor) or batch.ndim != 4:
            raise TypeError("ImageListToBatch expects BHWC tensors")
        if batch.shape[1:3] != (height, width):
            batch = torch_functional.interpolate(
                batch.movedim(-1, 1),
                size=(height, width),
                mode="bicubic",
                align_corners=False,
            ).movedim(1, -1)
        resized.append(batch)
    return (torch.cat(resized),)


async def _light_leak(
    image, light="random", corner="left_top", hue=0, saturation=0,
    opacity=100, **_kwargs,
):
    pixels = await image.raw()
    if not isinstance(pixels, torch.Tensor) or pixels.ndim != 4:
        raise TypeError("LightLeak expects a BHWC image tensor")
    height, width = pixels.shape[1:3]
    if str(light) == "random":
        index = random.randrange(32)
    else:
        index = max(0, min(31, int(light) - 1))
    angle = 2.0 * math.pi * index / 32.0
    base_hue = (angle / (2.0 * math.pi) + float(hue) / 255.0) % 1.0
    base_saturation = min(1.0, max(0.0, 0.72 + float(saturation) / 255.0))
    color = torch.tensor(
        colorsys.hsv_to_rgb(base_hue, base_saturation, 1.0),
        dtype=pixels.dtype,
        device=pixels.device,
    )
    y = torch.linspace(0.0, 1.0, height, dtype=pixels.dtype, device=pixels.device)
    x = torch.linspace(0.0, 1.0, width, dtype=pixels.dtype, device=pixels.device)
    yy, xx = torch.meshgrid(y, x, indexing="ij")
    corner = str(corner)
    origin_x = 1.0 if "right" in corner else 0.0
    origin_y = 1.0 if "bottom" in corner else 0.0
    distance = torch.sqrt((xx - origin_x) ** 2 + (yy - origin_y) ** 2)
    falloff = torch.clamp(1.2 - distance, 0.0, 1.0) ** (1.4 + index % 5 * 0.2)
    band = 0.65 + 0.35 * torch.cos((xx + yy) * math.pi * (2 + index % 4) + angle)
    alpha = (falloff * band * min(1.0, max(0.0, float(opacity) / 100.0))).unsqueeze(-1)
    rgb = pixels[..., :3].clamp(0.0, 1.0)
    leak = color.view(1, 1, 1, 3) * alpha.view(1, height, width, 1)
    blended = 1.0 - (1.0 - rgb) * (1.0 - leak)
    if pixels.shape[-1] > 3:
        blended = torch.cat((blended, pixels[..., 3:]), dim=-1)
    return (blended,)


_CLOTHES_FIELDS = {
    "hat": 1,
    "hair": 2,
    "sunglass": 3,
    "upper_clothes": 4,
    "skirt": 5,
    "pants": 6,
    "dress": 7,
    "belt": 8,
    "left_shoe": 9,
    "right_shoe": 10,
    "face": 11,
    "left_leg": 12,
    "right_leg": 13,
    "left_arm": 14,
    "right_arm": 15,
    "bag": 16,
    "scarf": 17,
}
_FASHION_FIELDS = {
    name: index for index, name in enumerate((
        "shirt", "top", "sweater", "cardigan", "jacket", "vest", "pants",
        "shorts", "skirt", "coat", "dress", "jumpsuit", "cape", "glasses",
        "hat", "hairaccessory", "tie", "glove", "watch", "belt", "legwarmer",
        "tights", "sock", "shoe", "bagwallet", "scarf", "umbrella", "hood",
        "collar", "lapel", "epaulette", "sleeve", "pocket", "neckline",
        "buckle", "zipper", "applique", "bead", "bow", "flower", "fringe",
        "ribbon", "rivet", "ruffle", "sequin", "tassel",
    ), start=1)
}


def _segformer_setting(fields: dict[str, int], model_name: str, kwargs: dict[str, Any]):
    labels_to_keep = [0]
    labels_to_keep.extend(
        label for name, label in fields.items() if not bool(kwargs.get(name, False))
    )
    return {"labels_to_keep": labels_to_keep, "model_name": model_name}


async def _clothes_pipeline(model="segformer_b3_clothes", **kwargs):
    return (_segformer_setting(_CLOTHES_FIELDS, str(model), kwargs),)


async def _fashion_pipeline(model="segformer_b3_fashion", **kwargs):
    return (_segformer_setting(_FASHION_FIELDS, str(model), kwargs),)


async def _clothes_setting(**kwargs):
    return (_segformer_setting(_CLOTHES_FIELDS, "segformer_b3_clothes", kwargs),)


async def _fashion_setting(**kwargs):
    return (_segformer_setting(_FASHION_FIELDS, "segformer_b3_fashion", kwargs),)


_SEGFORMER_MODELS = {
    "segformer_b2_clothes": ("b2", 18),
    "segformer_b3_clothes": ("b3", 18),
    "segformer_b3_fashion": ("b3", 47),
}


async def _download_weight(weight):
    return await _ctx().models.download_huggingface_weights(
        weight.repo_id,
        weight.filename,
        weight.folder,
        revision=weight.revision,
        sha256=weight.sha256,
    )


async def _load_segformer_model(model_name="segformer_b3_clothes", device="cpu", **_kwargs):
    name = str(model_name)
    if name not in _SEGFORMER_MODELS:
        raise ValueError(f"unknown LayerStyle SegFormer model {name!r}")
    variant, labels = _SEGFORMER_MODELS[name]
    logical = await _download_weight(_SEGFORMER_WEIGHTS[name])
    model = await _ctx().models.load_segformer(logical, variant, labels)
    return ({"model": model, "device": str(device), "model_name": name},)


_SEGFORMER_WEIGHTS = {
    "segformer_b2_clothes": sdk.HuggingFaceWeight(
        repo_id="mattmdjaga/segformer_b2_clothes",
        filename="model.safetensors",
        folder="semantic_segmentation",
        revision="584abc1e1d260e23c0fc627c5217a09b2b461046",
        sha256="8f86fd90c567afd4370b3cc3a7e81ed767a632b2832a738331af660acc0c4c68",
        on_demand=True,
    ),
    "segformer_b3_clothes": sdk.HuggingFaceWeight(
        repo_id="sayeed99/segformer_b3_clothes",
        filename="model.safetensors",
        folder="semantic_segmentation",
        revision="6c12f0e4edd353fb65d4e3f9d90fdabaefea6d9e",
        sha256="f70ae566c5773fb335796ebaa8acc924ac25eb97222c2b2967d44d2fc11568e6",
        on_demand=True,
    ),
    "segformer_b3_fashion": sdk.HuggingFaceWeight(
        repo_id="sayeed99/segformer-b3-fashion",
        filename="model.safetensors",
        folder="semantic_segmentation",
        revision="e2474a9e7643d349ac6c525549b736b736e7e216",
        sha256="f3f5b30179f1480d329224d089f6d286580142c2b12846d08de814a48a81f42f",
        on_demand=True,
    ),
}
_BACKGROUND_WEIGHT = sdk.HuggingFaceWeight(
    repo_id="briaai/RMBG-2.0",
    filename="model.safetensors",
    folder="background_removal",
    revision="5df4c9c76d8170882c34f6986e848ee07fd0ba43",
    sha256="566ed80c3d95f87ada6864d4cbe2290a1c5eb1c7bb0b123e984f60f76b02c3a7",
    on_demand=True,
)


async def _load_vqa_model(
    model="blip-vqa-base",
    precision="fp16",
    device="cuda",
    **_kwargs,
):
    name = str(model)
    if name not in _vqa.WEIGHTS:
        raise ValueError(f"unknown LayerStyle VQA model {name!r}")
    logical = await _download_weight(_vqa.WEIGHTS[name])
    loaded = await _vqa.load(
        _ctx(), logical, name, str(precision), str(device),
    )
    return (loaded,)


async def _vqa_prompt(image, vqa_model, question="", **_kwargs):
    model_data = await materialize(vqa_model)
    questions = re.findall(r"\{([^}]*)\}", str(question))
    raw = await image.raw()
    answers = []
    for index in range(len(raw)):
        text = str(question)
        for prompt in questions:
            answer = await _vqa.answer(
                _ctx(), model_data, raw[index:index + 1], prompt,
            )
            text = text.replace("{" + prompt + "}", answer)
        answers.append(text)
    return (answers,)


_DETAIL_METHODS = {
    "VITMatte",
    "VITMatte(local)",
    "vitmatte-base-composition-1k",
    "PyMatting",
    "GuidedFilter",
}


def _imagefunc():
    return importlib.import_module(".py.imagefunc", __package__)


async def _image_tensor(image) -> torch.Tensor:
    value = await image.raw()
    if (
        not isinstance(value, torch.Tensor)
        or value.ndim != 4
        or value.shape[-1] < 3
        or len(value) == 0
    ):
        raise ValueError("LayerStyle requires a non-empty BHWC image batch")
    return value.detach().cpu().float()


async def _mask_tensor(mask) -> torch.Tensor:
    value = await mask.raw()
    if not isinstance(value, torch.Tensor):
        raise TypeError("LayerStyle masks must be tensors")
    if value.ndim == 2:
        value = value.unsqueeze(0)
    elif value.ndim == 4 and value.shape[1] == 1:
        value = value[:, 0]
    elif value.ndim == 4 and value.shape[-1] == 1:
        value = value[..., 0]
    if value.ndim != 3 or len(value) == 0:
        raise ValueError("LayerStyle masks must be a non-empty BHW batch")
    return value.detach().cpu().float()


async def _load_vitmatte(method: str):
    method = str(method)
    if method not in _DETAIL_METHODS:
        raise ValueError(f"unknown LayerStyle detail method {method!r}")
    if method in {"GuidedFilter", "PyMatting"}:
        return None
    variant = (
        "base" if method == "vitmatte-base-composition-1k" else "small")
    logical = await _download_weight(_vitmatte.WEIGHTS[variant])
    return await _vitmatte.load(_ctx(), logical, variant)


async def _refine_detail(
    image: torch.Tensor,
    mask: torch.Tensor,
    method: str,
    erode: int,
    dilate: int,
    black_point: float,
    white_point: float,
    max_megapixels: float,
    matting_model,
    *,
    add_one: bool,
):
    func = _imagefunc()
    detail_range = int(erode) + int(dilate)
    if method == "GuidedFilter":
        radius = detail_range // 6 + int(add_one)
        refined = func.guided_filter_alpha(image, mask, radius)
        return func.tensor2pil(func.histogram_remap(
            refined, float(black_point), float(white_point))).convert("L")
    if method == "PyMatting":
        radius = detail_range // 8 + int(add_one)
        refined = func.mask_edge_detail(
            image, mask, radius, float(black_point), float(white_point))
        return func.tensor2pil(refined).convert("L")
    if matting_model is None:
        raise RuntimeError("ViTMatte was not loaded for the selected method")
    trimap_image = func.generate_VITMatte_trimap(
        mask, int(erode), int(dilate))
    trimap = func.image2mask(trimap_image)
    refined = await _vitmatte.refine(
        _ctx(), matting_model, image, trimap,
        max_megapixels=float(max_megapixels))
    refined = func.histogram_remap(
        refined, float(black_point), float(white_point))
    return func.tensor2pil(refined).convert("L")


def _rgba_result(func, image: Image.Image, mask: Image.Image):
    rgba = func.RGB2RGBA(image.convert("RGB"), mask.convert("L"))
    return func.pil2tensor(rgba), func.image2mask(mask.convert("L"))


async def _mask_edge_ultra_detail_v2(
    image, mask, method="VITMatte", mask_grow=0, fix_gap=0,
    fix_threshold=0.75, edge_erode=6, edte_dilate=6,
    black_point=0.01, white_point=0.99, device="cuda",
    max_megapixels=2.0, **_kwargs,
):
    del device
    pixels = await _image_tensor(image)
    masks = await _mask_tensor(mask)
    if (
        len(pixels) != len(masks)
        or tuple(pixels.shape[1:3]) != tuple(masks.shape[1:3])
    ):
        return pixels, masks
    method = str(method)
    matting = await _load_vitmatte(method)
    func = _imagefunc()
    images_out = []
    masks_out = []
    for index in range(len(pixels)):
        original = func.tensor2pil(pixels[index:index + 1]).convert("RGB")
        source = func.pil2tensor(original)
        working = masks[index:index + 1]
        if int(mask_grow):
            working = func.expand_mask(
                working, int(mask_grow), int(mask_grow) // 2)
        if int(fix_gap):
            working = func.mask_fix(
                working, 1, int(fix_gap),
                float(fix_threshold), float(fix_threshold))
        refined = await _refine_detail(
            source, working, method, int(edge_erode), int(edte_dilate),
            float(black_point), float(white_point), float(max_megapixels),
            matting, add_one=False)
        rgba, alpha = _rgba_result(func, original, refined)
        images_out.append(rgba)
        masks_out.append(alpha)
    return torch.cat(images_out), torch.cat(masks_out)


async def _mask_edge_ultra_detail_v3(
    image, mask, method="VITMatte", mask_grow=0, fix_gap=0,
    fix_threshold=0.75, mask_edge_erode=6, mask_edge_dilate=4,
    transparent_trimap_erode=72, transparent_trimap_dilate=64,
    trimap_blur=4, black_point=0.01, white_point=0.99,
    spread_mask_grow=0, device="cuda", max_megapixels=3.0,
    transparent_trimap=None, **_kwargs,
):
    del device
    pixels = await _image_tensor(image)
    masks = await _mask_tensor(mask)
    transparent = (
        None if transparent_trimap is None
        else await _mask_tensor(transparent_trimap))
    if (
        len(pixels) != len(masks)
        or tuple(pixels.shape[1:3]) != tuple(masks.shape[1:3])
    ):
        return pixels, masks
    if transparent is not None and (
        len(transparent) != len(pixels)
        or tuple(transparent.shape[1:3]) != tuple(pixels.shape[1:3])
    ):
        raise ValueError("transparent trimap must match the image batch")
    method = str(method)
    matting = await _load_vitmatte(method)
    func = _imagefunc()
    images_out = []
    masks_out = []
    for index in range(len(pixels)):
        original = func.tensor2pil(pixels[index:index + 1]).convert("RGB")
        source = func.pil2tensor(original)
        working = masks[index:index + 1]
        if int(mask_grow):
            working = func.expand_mask(
                working, int(mask_grow), int(mask_grow) // 2)
        if int(fix_gap):
            working = func.mask_fix(
                working, 1, int(fix_gap),
                float(fix_threshold), float(fix_threshold))
        refined = await _refine_detail(
            source, working, method,
            int(mask_edge_erode), int(mask_edge_dilate),
            float(black_point), float(white_point), float(max_megapixels),
            matting, add_one=False)
        if transparent is not None:
            alternate = await _refine_detail(
                source, working, method,
                int(transparent_trimap_erode),
                int(transparent_trimap_dilate),
                float(black_point), float(white_point),
                float(max_megapixels), matting, add_one=False)
            selection = func.tensor2pil(
                transparent[index:index + 1]).convert("L")
            if int(trimap_blur) > 0:
                selection = func.gaussian_blur(selection, int(trimap_blur))
            refined.paste(alternate, mask=selection)
        if int(spread_mask_grow):
            spread = func.expand_mask(
                func.image2mask(refined), int(spread_mask_grow), 0)
            spread = func.mask2image(spread)
        else:
            spread = refined
        spread_image = func.pixel_spread(
            original.convert("RGB"), spread.convert("RGB"))
        rgba, alpha = _rgba_result(func, spread_image, refined)
        images_out.append(rgba)
        masks_out.append(alpha)
    return torch.cat(images_out), torch.cat(masks_out)


async def _background_mask(image):
    logical = await _download_weight(_BACKGROUND_WEIGHT)
    model = await _ctx().models.load_background_removal_model(logical)
    mask = await model.mask(image)
    value = await mask.raw()
    if not isinstance(value, torch.Tensor) or value.ndim != 3:
        raise RuntimeError("background removal returned an invalid mask")
    return value.detach().cpu().float()


async def _rembg_ultra(
    image, detail_range=8, black_point=0.01, white_point=0.99,
    process_detail=True, **_kwargs,
):
    pixels = await _image_tensor(image)
    masks = await _background_mask(image)
    func = _imagefunc()
    images_out = []
    masks_out = []
    for index in range(len(pixels)):
        original = func.tensor2pil(pixels[index:index + 1]).convert("RGB")
        source = func.pil2tensor(original)
        working = masks[index:index + 1]
        if bool(process_detail):
            working = func.mask_edge_detail(
                source, working, int(detail_range),
                float(black_point), float(white_point))
            refined = func.tensor2pil(working).convert("L")
        else:
            refined = func.mask2image(working).convert("L")
        rgba, alpha = _rgba_result(func, original, refined)
        images_out.append(rgba)
        masks_out.append(alpha)
    return torch.cat(images_out), torch.cat(masks_out)


async def _rmbg_ultra_v2(
    image, detail_method="VITMatte", detail_erode=6, detail_dilate=6,
    black_point=0.01, white_point=0.99, process_detail=True,
    device="cuda", max_megapixels=2.0, **_kwargs,
):
    del device
    pixels = await _image_tensor(image)
    masks = await _background_mask(image)
    method = str(detail_method)
    matting = await _load_vitmatte(method) if bool(process_detail) else None
    func = _imagefunc()
    images_out = []
    masks_out = []
    for index in range(len(pixels)):
        original = func.tensor2pil(pixels[index:index + 1]).convert("RGB")
        source = func.pil2tensor(original)
        working = masks[index:index + 1]
        if bool(process_detail):
            refined = await _refine_detail(
                source, working, method,
                int(detail_erode), int(detail_dilate),
                float(black_point), float(white_point),
                float(max_megapixels), matting, add_one=True)
        else:
            refined = func.mask2image(working).convert("L")
        rgba, alpha = _rgba_result(func, original, refined)
        images_out.append(rgba)
        masks_out.append(alpha)
    return torch.cat(images_out), torch.cat(masks_out)


async def _segformer_foreground(image, model_name, labels_to_keep):
    if model_name not in _SEGFORMER_MODELS:
        raise ValueError(f"unknown LayerStyle SegFormer model {model_name!r}")
    labels = []
    for value in labels_to_keep:
        value = int(value)
        if value not in labels:
            labels.append(value)
    variant, count = _SEGFORMER_MODELS[model_name]
    if not labels or any(value < 0 or value >= count for value in labels):
        raise ValueError("SegFormer settings do not match the selected model")
    logical = await _download_weight(_SEGFORMER_WEIGHTS[model_name])
    model = await _ctx().models.load_segformer(logical, variant, count)
    union = await model.mask(image, labels)
    value = await union.raw()
    return 1.0 - value.detach().cpu().float().clamp(0.0, 1.0)


async def _segformer_ref_foreground(image, model, labels_to_keep):
    labels = []
    for value in labels_to_keep:
        value = int(value)
        if value not in labels:
            labels.append(value)
    union = await model.mask(image, labels)
    value = await union.raw()
    return 1.0 - value.detach().cpu().float().clamp(0.0, 1.0)


async def _render_segmented(
    image, foreground, detail_method, detail_erode, detail_dilate,
    black_point, white_point, process_detail, max_megapixels,
    *, brighten: bool,
):
    pixels = await _image_tensor(image)
    if tuple(foreground.shape) != (
        len(pixels), pixels.shape[1], pixels.shape[2],
    ):
        raise RuntimeError("SegFormer returned a mask with the wrong shape")
    method = str(detail_method)
    matting = await _load_vitmatte(method) if bool(process_detail) else None
    func = _imagefunc()
    images_out = []
    masks_out = []
    for index in range(len(pixels)):
        original = func.tensor2pil(pixels[index:index + 1]).convert("RGB")
        source = func.pil2tensor(original)
        working = foreground[index:index + 1]
        if brighten:
            mask_image = func.mask2image(working).convert("L")
            mask_image = func.ImageEnhance.Brightness(mask_image).enhance(1.08)
            working = func.image2mask(mask_image)
        if bool(process_detail):
            refined = await _refine_detail(
                source, working, method,
                int(detail_erode), int(detail_dilate),
                float(black_point), float(white_point),
                float(max_megapixels), matting, add_one=True)
        else:
            refined = func.mask2image(working).convert("L")
        rgba, alpha = _rgba_result(func, original, refined)
        images_out.append(rgba)
        masks_out.append(alpha)
    return torch.cat(images_out), torch.cat(masks_out)


async def _segformer_b2_clothes_ultra(image, **kwargs):
    labels = [0]
    fields = {
        "hat": [1], "hair": [2], "sunglass": [3],
        "upper_clothes": [4], "skirt": [5], "pants": [6],
        "dress": [7], "belt": [8], "shoe": [9, 10], "face": [11],
        "left_leg": [12], "right_leg": [13], "left_arm": [14],
        "right_arm": [15], "bag": [16], "scarf": [17],
    }
    for name, values in fields.items():
        if not bool(kwargs.get(name, False)):
            labels.extend(values)
    foreground = await _segformer_foreground(
        image, "segformer_b2_clothes", labels)
    return await _render_segmented(
        image, foreground,
        kwargs.get("detail_method", "VITMatte"),
        kwargs.get("detail_erode", 12), kwargs.get("detail_dilate", 6),
        kwargs.get("black_point", 0.15), kwargs.get("white_point", 0.99),
        kwargs.get("process_detail", True),
        kwargs.get("max_megapixels", 2.0), brighten=False)


async def _segformer_ultra_v2(
    image, segformer_pipeline, detail_method="VITMatte",
    detail_erode=8, detail_dilate=6, black_point=0.01,
    white_point=0.99, process_detail=True, device="cuda",
    max_megapixels=2.0, **_kwargs,
):
    del device
    pipeline = await materialize(segformer_pipeline)
    if not isinstance(pipeline, dict):
        raise TypeError("SegformerUltraV2 requires a secure pipeline setting")
    model_name = str(pipeline.get("model_name", ""))
    labels = pipeline.get("labels_to_keep")
    if not isinstance(labels, list):
        raise TypeError("SegFormer pipeline labels must be a list")
    foreground = await _segformer_foreground(image, model_name, labels)
    return await _render_segmented(
        image, foreground, detail_method, detail_erode, detail_dilate,
        black_point, white_point, process_detail, max_megapixels,
        brighten=True)


async def _segformer_ultra_v3(
    image, segformer_model, segformer_setting, detail_method="VITMatte",
    detail_erode=8, detail_dilate=6, black_point=0.01,
    white_point=0.99, process_detail=True, max_megapixels=2.0,
    **_kwargs,
):
    model_data = await materialize(segformer_model)
    setting = await materialize(segformer_setting)
    if not isinstance(model_data, dict) or not isinstance(setting, dict):
        raise TypeError("SegformerUltraV3 requires secure model and settings")
    model = model_data.get("model")
    if not isinstance(model, sdk.SemanticSegmentationRef):
        raise TypeError("SegformerUltraV3 requires a secure SegFormer model")
    model_name = str(model_data.get("model_name", ""))
    setting_name = str(setting.get("model_name", ""))
    if model_name.rsplit("_", 1)[-1] != setting_name.rsplit("_", 1)[-1]:
        raise TypeError("Segformer Model and Segformer Setting are different.")
    labels = setting.get("labels_to_keep")
    if not isinstance(labels, list):
        raise TypeError("SegFormer setting labels must be a list")
    foreground = await _segformer_ref_foreground(image, model, labels)
    return await _render_segmented(
        image, foreground, detail_method, detail_erode, detail_dilate,
        black_point, white_point, process_detail, max_megapixels,
        brighten=True)


async def _icmask(**kwargs):
    result = await _legacy_handler("LayerUtility: ICMask")(**kwargs)
    image, mask, value = result
    fields = {
        name: int(getattr(value, name))
        for name in (
            "x_offset", "y_offset", "target_width", "target_height",
            "total_width", "total_height", "orig_width", "orig_height",
        )
    }
    return image, mask, fields


async def _icmask_crop_back(image, icmask_data, **_kwargs):
    if not isinstance(icmask_data, dict):
        raise TypeError("ICMaskCropBack requires secure ICMask data")
    module = importlib.import_module(".py.ic_mask", __package__)
    names = (
        "x_offset", "y_offset", "target_width", "target_height",
        "total_width", "total_height", "orig_width", "orig_height",
    )
    try:
        value = module.ICMask_Data(*[int(icmask_data[name]) for name in names])
    except KeyError as exc:
        raise ValueError("ICMask data is incomplete") from exc
    pixels = await materialize(image)
    instance = _LEGACY_INSTANCES.get("LayerUtility: ICMaskCropBack")
    if instance is None:
        instance = module.LS_ICMask_CropBack()
        _LEGACY_INSTANCES["LayerUtility: ICMaskCropBack"] = instance
    return instance.crop_back(pixels, value)


async def _image_reel(**kwargs):
    result = await _legacy_handler("LayerUtility: ImageReel")(**kwargs)
    reel = result[0]
    frames = []
    for frame in getattr(reel, "reels", ()):
        image = _imagefunc().pil2tensor(frame.image)
        image_ref = await sdk.ImageRef._from_raw(image)
        frames.append({
            "image": image_ref,
            "texts": [list(item) for item in frame.texts],
            "reel_height": int(frame.reel_height),
            "reel_border": int(frame.reel_border),
        })
    if not frames:
        raise RuntimeError("ImageReel produced no frames")
    return ({"frames": frames},)


def _reel_from_value(module, value):
    if not isinstance(value, dict) or not isinstance(value.get("frames"), list):
        raise TypeError("ImageReelComposit requires secure Reel data")
    reel = module.ImageReelPipeline()
    for item in value["frames"]:
        if not isinstance(item, dict) or not isinstance(item.get("image"), torch.Tensor):
            raise TypeError("secure Reel frames must contain image tensors")
        frame = module.ImageReelPipeline()
        frame.image = _imagefunc().tensor2pil(item["image"]).convert("RGBA")
        frame.texts = [list(text) for text in item.get("texts", [])]
        frame.reel_height = int(item.get("reel_height", frame.image.height))
        frame.reel_border = int(item.get("reel_border", 0))
        reel.reels.append(frame)
    if reel.reels:
        reel.image = reel.reels[0].image
        reel.texts = reel.reels[0].texts
        reel.reel_height = reel.reels[0].reel_height
        reel.reel_border = reel.reels[0].reel_border
    return reel


async def _image_reel_composit(
    reel_1, font_file, font_size=40, border=32, color_theme="light",
    reel_2=None, reel_3=None, reel_4=None, **_kwargs,
):
    module = importlib.import_module(".py.image_reel", __package__)
    values = []
    for value in (reel_1, reel_2, reel_3, reel_4):
        values.append(
            None if value is None
            else _reel_from_value(module, await materialize(value)))
    instance = _LEGACY_INSTANCES.get("LayerUtility: ImageReelComposit")
    if instance is None:
        instance = module.ImageReelComposit()
        _LEGACY_INSTANCES["LayerUtility: ImageReelComposit"] = instance
    return instance.image_reel_composit(
        values[0], str(font_file), int(font_size), int(border),
        str(color_theme), values[1], values[2], values[3])


_HANDLERS = {node_id: _legacy_handler(node_id) for node_id in SCHEMAS}
_HANDLERS.update({
    "LayerFilter: LightLeak": _light_leak,
    "LayerMask: MaskPreview": _mask_preview,
    "LayerUtility: ImageListToBatch": _image_list_to_batch,
    "LayerUtility: ICMask": _icmask,
    "LayerUtility: ICMaskCropBack": _icmask_crop_back,
    "LayerUtility: ImageReel": _image_reel,
    "LayerUtility: ImageReelComposit": _image_reel_composit,
    "LayerUtility: ImageTaggerSave": _image_tagger_save,
    "LayerUtility: ImageTaggerSaveV2": _image_tagger_save,
    "LayerUtility: LoadImagesFromPath": _load_images_from_path,
    "LayerUtility: QueueStop": _queue_stop,
    "LayerUtility: PurgeVRAM": _purge_vram_v1,
    "LayerUtility: PurgeVRAM V2": _purge_vram_v2,
    "LayerMask: SegformerClothesPipelineLoader": _clothes_pipeline,
    "LayerMask: SegformerFashionPipelineLoader": _fashion_pipeline,
    "LayerMask: SegformerClothesSetting": _clothes_setting,
    "LayerMask: SegformerFashionSetting": _fashion_setting,
    "LayerMask: LoadSegformerModel": _load_segformer_model,
    "LayerUtility: LoadVQAModel": _load_vqa_model,
    "LayerUtility: VQAPrompt": _vqa_prompt,
})


_MODEL_IMAGE_NODES = {
    "LayerMask: MaskEdgeUltraDetail V2",
    "LayerMask: MaskEdgeUltraDetail V3",
    "LayerMask: RemBgUltra",
    "LayerMask: RmBgUltra V2",
    "LayerMask: SegformerB2ClothesUltra",
    "LayerMask: SegformerUltraV2",
    "LayerMask: SegformerUltraV3",
}
_HANDLERS.update({
    "LayerMask: MaskEdgeUltraDetail V2": _mask_edge_ultra_detail_v2,
    "LayerMask: MaskEdgeUltraDetail V3": _mask_edge_ultra_detail_v3,
    "LayerMask: RemBgUltra": _rembg_ultra,
    "LayerMask: RmBgUltra V2": _rmbg_ultra_v2,
    "LayerMask: SegformerB2ClothesUltra": _segformer_b2_clothes_ultra,
    "LayerMask: SegformerUltraV2": _segformer_ultra_v2,
    "LayerMask: SegformerUltraV3": _segformer_ultra_v3,
})


_PERMISSIONS: dict[str, tuple[str, ...]] = {
    node_id: (("raw",) if has_tensor_io(node_id) else ())
    for node_id in SCHEMAS
}
_PERMISSIONS.update({
    "LayerMask: MaskPreview": ("ui", "raw"),
    "LayerUtility: ImageTaggerSave": ("output", "raw"),
    "LayerUtility: ImageTaggerSaveV2": ("output", "raw"),
    "LayerUtility: LoadImagesFromPath": ("assets", "raw"),
    "LayerUtility: QueueStop": ("graph.block",),
    "LayerUtility: PurgeVRAM": ("models.manage",),
    "LayerUtility: PurgeVRAM V2": ("models.manage",),
    "LayerMask: LoadSegformerModel": ("models", "models.download"),
    "LayerUtility: LoadVQAModel": ("assets", "models.download"),
    "LayerUtility: VQAPrompt": ("assets", "raw"),
})
for _node_id in _MODEL_IMAGE_NODES:
    _PERMISSIONS[_node_id] = ("models", "models.download", "raw")


_REQUIRED_WEIGHTS: dict[str, tuple[sdk.HuggingFaceWeight, ...]] = {
    "LayerMask: LoadSegformerModel": tuple(_SEGFORMER_WEIGHTS.values()),
    "LayerUtility: LoadVQAModel": tuple(_vqa.WEIGHTS.values()),
    "LayerMask: RemBgUltra": (_BACKGROUND_WEIGHT,),
    "LayerMask: RmBgUltra V2": (_BACKGROUND_WEIGHT, *_vitmatte.WEIGHTS.values()),
    "LayerMask: MaskEdgeUltraDetail V2": tuple(_vitmatte.WEIGHTS.values()),
    "LayerMask: MaskEdgeUltraDetail V3": tuple(_vitmatte.WEIGHTS.values()),
    "LayerMask: SegformerB2ClothesUltra": (
        _SEGFORMER_WEIGHTS["segformer_b2_clothes"],
        *_vitmatte.WEIGHTS.values(),
    ),
    "LayerMask: SegformerUltraV2": (
        *_SEGFORMER_WEIGHTS.values(),
        *_vitmatte.WEIGHTS.values(),
    ),
    "LayerMask: SegformerUltraV3": tuple(_vitmatte.WEIGHTS.values()),
}


# ViTMatte is loaded inside this pack, so its nodes resolve the weight asset
# themselves instead of asking the host to load a model for them.
_VITMATTE_WEIGHT_IDS = {id(_w) for _w in _vitmatte.WEIGHTS.values()}
for _node_id, _weights in _REQUIRED_WEIGHTS.items():
    if any(id(_w) in _VITMATTE_WEIGHT_IDS for _w in _weights):
        _PERMISSIONS[_node_id] = tuple(dict.fromkeys(
            _PERMISSIONS.get(_node_id, ()) + ("assets",)))


if set(_HANDLERS) != set(SCHEMAS):
    raise RuntimeError("LayerStyle secure handler census does not match frozen schemas")


NODE_CLASS_MAPPINGS = {
    node_id: bind_node(
        node_id,
        handler,
        permissions=_PERMISSIONS[node_id],
        required_weights=_REQUIRED_WEIGHTS.get(node_id, ()),
    )
    for node_id, handler in _HANDLERS.items()
}
NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: SCHEMAS[node_id]["schema"]["attrs"]["display_name"]
    for node_id in SCHEMAS
}


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
