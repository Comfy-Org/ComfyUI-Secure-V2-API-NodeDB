"""Secure Nodes V2 implementation of the pinned quadMoons node pack."""
from __future__ import annotations

import hashlib
import io as pyio
import json
import math
import random
import re
from pathlib import PurePosixPath
from typing import Any, Callable

import numpy as np
import torch
from PIL import Image

from ._image_ops import common_upscale
from ._secure_runtime import SCHEMAS, bind_node, materialize, sdk
from .prompt_weighting import encode_prompt


_CONFIG_KEY = "quadmoons/smart-nodes-v1"
_EMPTY_CONFIG = {
    "none": [{"prompt": "", "negative": "", "other_data": "----NONE----"}],
}
_COMPARISONS: dict[str, Callable[[int, int], bool]] = {
    "Eq": lambda a, b: a == b,
    "Neq": lambda a, b: a != b,
    "Gt": lambda a, b: a > b,
    "Lt": lambda a, b: a < b,
    "Geq": lambda a, b: a >= b,
    "Leq": lambda a, b: a <= b,
}


def _ctx():
    return sdk.ctx()


def _asset_name(value: Any) -> str:
    name = str(value or "").replace("\\", "/").strip()
    path = PurePosixPath(name)
    if (
        not name or path.is_absolute() or "//" in name or ":" in path.parts[0]
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError("asset names must come from a managed host catalogue")
    return path.as_posix()


def _trigger(value: Any) -> tuple[str, str]:
    digest, separator, checkpoint = str(value).partition("|")
    if not separator or not re.fullmatch(r"[0-9a-f]{64}", digest) or not checkpoint:
        raise ValueError("SMART_TRIGGER must come from quadmoonModelLoader")
    return digest, checkpoint


def _bounded_text(value: Any, *, maximum: int = 131_072) -> str:
    text = str(value or "")
    if "\x00" in text or len(text) > maximum:
        raise ValueError("Smart Nodes text exceeds its bounded storage format")
    return text


def _validate_config(value: Any) -> dict[str, list[dict[str, str]]]:
    if not isinstance(value, dict) or len(value) > 256:
        raise ValueError("Smart Nodes config must be a bounded object")
    result: dict[str, list[dict[str, str]]] = {}
    total = 0
    for key, rows in value.items():
        if not isinstance(key, str) or len(key) > 128 or not isinstance(rows, list):
            raise ValueError("Smart Nodes config has an invalid model entry")
        if len(rows) > 256:
            raise ValueError("Smart Nodes config has too many named presets")
        converted = []
        for row in rows:
            total += 1
            if total > 2048 or not isinstance(row, dict):
                raise ValueError("Smart Nodes config exceeds its preset limit")
            converted.append({
                "prompt": _bounded_text(row.get("prompt")),
                "negative": _bounded_text(row.get("negative")),
                "other_data": _bounded_text(row.get("other_data"), maximum=1024),
            })
        result[key] = converted
    return result


async def _load_config() -> dict[str, list[dict[str, str]]]:
    raw = await _ctx().storage.get(_CONFIG_KEY)
    if raw is None:
        value = json.loads(json.dumps(_EMPTY_CONFIG))
        await _ctx().storage.set(_CONFIG_KEY, json.dumps(value, separators=(",", ":")))
        return value
    try:
        return _validate_config(json.loads(raw))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("stored Smart Nodes config is malformed") from error


async def _store_config(value: dict[str, list[dict[str, str]]]) -> None:
    normalized = _validate_config(value)
    encoded = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > 2_097_152:
        raise ValueError("Smart Nodes config exceeds 2 MiB")
    await _ctx().storage.set(_CONFIG_KEY, encoded)


def _config_names(value: dict[str, list[dict[str, str]]]) -> list[str]:
    return [
        row["other_data"]
        for rows in value.values() for row in rows if row.get("other_data")
    ]


def _update_config(
    value: dict[str, list[dict[str, str]]], digest: str, other_data: str,
    *, prompt: str = "", negative: str = "",
) -> None:
    rows = value.setdefault(digest, [])
    for row in rows:
        if row.get("other_data") == other_data:
            if prompt != "":
                row["prompt"] = prompt
            if negative != "":
                row["negative"] = negative
            return
    rows.append({"prompt": prompt, "negative": negative, "other_data": other_data})


async def _int_to_string(integer_input):
    if not isinstance(integer_input, int):
        raise ValueError("Input is not an integer.")
    return (str(integer_input),)


async def _float_to_string(float_input):
    if not isinstance(float_input, float):
        raise ValueError("Input is not a float.")
    return (str(float_input),)


async def _number_to_string(number_input):
    if not isinstance(number_input, (int, float)):
        raise ValueError("Input is not a number.")
    return (str(number_input),)


async def _bool_to_string(boolean_input):
    if not isinstance(boolean_input, bool):
        raise ValueError("Input is not a boolean.")
    return (str(boolean_input),)


def _sd_dimensions(height: int, width: int, attention: str, orientation: str, size: int):
    if height > width:
        divisor = height / size if attention == "minimize" else width / size
    else:
        divisor = width / size if attention == "minimize" else height / size
    new_height, new_width = int(height / divisor), int(width / divisor)
    if ((orientation == "portrait" and new_width > new_height)
            or (orientation == "landscape" and new_height > new_width)):
        new_height, new_width = new_width, new_height
    return new_height, new_width, divisor


def _flux_dimensions(height: int, width: int, orientation: str):
    pixels = height * width
    ratio = math.sqrt(pixels / 1_048_576.0)
    new_height, new_width = height / ratio, width / ratio
    portrait_sizes = [896.0, 832.0, 768.0, 640.0]
    landscape_sizes = [1152.0, 1216.0, 1344.0, 1536.0]
    short = min(new_height, new_width)
    closest_short = min(portrait_sizes, key=lambda x: abs(short - x))
    if short == new_height:
        new_height, new_width = closest_short, new_width * (closest_short / new_height)
    else:
        new_height, new_width = new_height * (closest_short / new_width), closest_short
    long = max(new_height, new_width)
    if long > min(landscape_sizes):
        closest_long = min(landscape_sizes, key=lambda x: abs(long - x))
        if long == new_height:
            new_height, new_width = closest_long, new_width * (closest_long / new_height)
        else:
            new_height, new_width = new_height * (closest_long / new_width), closest_long
    if ((orientation == "portrait" and new_width > new_height)
            or (orientation == "landscape" and new_height > new_width)):
        new_height, new_width = new_width, new_height
    aspect_error = abs(1 - (new_height / new_width if new_height > new_width else new_width / new_height))
    if aspect_error < 0.1:
        if new_height > new_width:
            new_height, new_width = 1024, new_width * (1024 / new_height)
        else:
            new_height, new_width = new_height * (1024 / new_width), 1024
    divisor = math.sqrt(pixels / (new_height * new_width))
    return round(new_height), round(new_width), divisor


async def _normalize_hw(image, platform, orientation, attention):
    pixels = await image.raw()
    if not isinstance(pixels, torch.Tensor) or pixels.ndim != 4:
        raise TypeError("Normalize H/W requires a BHWC image tensor")
    height, width = map(int, pixels.shape[1:3])
    if platform == "SD1.5":
        new_height, new_width, divisor = _sd_dimensions(height, width, str(attention), str(orientation), 512)
    elif platform == "XL":
        new_height, new_width, divisor = _sd_dimensions(height, width, str(attention), str(orientation), 1024)
    elif platform == "FLUX":
        new_height, new_width, divisor = _flux_dimensions(height, width, str(orientation))
    else:
        raise ValueError(f"unknown platform {platform!r}")
    method = "area" if divisor > 1 else "bicubic"
    output = common_upscale(pixels.movedim(-1, 1), new_width, new_height, method, "disabled")
    return (output.movedim(1, -1),)


async def _image_to_prompt(image):
    asset = await _ctx().assets.resolve("input", _asset_name(image))
    payload = await _ctx().assets.read_bytes(asset)
    with Image.open(pyio.BytesIO(payload)) as source:
        parameters = source.info.get("parameters")
    if not isinstance(parameters, str):
        raise ValueError("image has no A1111 parameters metadata")
    prompt = parameters.split("Negative prompt:")[0].strip()
    match = re.search(r"Negative prompt: (.+?)(?=Steps:)", parameters, re.DOTALL)
    negative = match.group(1).strip() if match else None
    match = re.search(r'Hires prompt: "(.+?)"', parameters, re.DOTALL)
    hires = match.group(1).strip() if match else None
    def field(pattern: str, default: str):
        found = re.search(pattern, parameters)
        return found.group(1) if found else default
    size = re.search(r"Size:\s*(\d+)x(\d+)", parameters)
    width, height = size.groups() if size else ("512", "512")
    return (
        prompt, negative, hires,
        int(field(r"Seed: (\d+)", "0")),
        int(field(r"Steps: (\d+)", "20")),
        float(field(r"CFG scale: ([\d.]+)", "7.0")),
        int(height), int(width), -int(field(r"Clip skip: (\d+)", "1")),
    )


async def _int_compare(int_a, int_b, op, if_true_return):
    try:
        result = _COMPARISONS[str(op)](int(int_a), int(int_b))
    except KeyError as error:
        raise ValueError(f"unknown integer comparison {op!r}") from error
    choose_a = str(if_true_return) == "a"
    return (int_a if result == choose_a else int_b,)


async def _clip_encode(clip, text):
    return (await clip.encode(str(text)),)


async def _clip_encode_advanced(
    clip, clip_skip, POSITIVE_PROMPT, NEGATIVE_PROMPT, weight_interpretation,
):
    work = await clip.set_last_layer(int(clip_skip))
    positive = await encode_prompt(work, str(POSITIVE_PROMPT), str(weight_interpretation))
    negative = await encode_prompt(work, str(NEGATIVE_PROMPT), str(weight_interpretation))
    return positive, negative


async def _model_loader(ckpt_name):
    logical = _asset_name(ckpt_name)
    model, clip, vae = await _ctx().models.load_checkpoint(logical)
    if clip is None or vae is None:
        raise RuntimeError("quadmoonModelLoader requires checkpoint CLIP and VAE outputs")
    trigger = hashlib.sha256(logical.encode()).hexdigest() + "|" + logical
    return model, clip, vae, trigger


async def _save_negative(negative, trigger, config_name):
    digest, checkpoint = _trigger(trigger)
    name = checkpoint + " - " + _bounded_text(config_name, maximum=512)
    data = await _load_config()
    _update_config(data, digest, name, negative=_bounded_text(negative))
    await _store_config(data)
    return {"ui": {"config_names": _config_names(data)}, "result": (negative,)}


async def _save_prompt(prompt_start, image_content, prompt_end, trigger, config_name):
    digest, checkpoint = _trigger(trigger)
    start, content, end = map(_bounded_text, (prompt_start, image_content, prompt_end))
    output = start + ", " + content + ", " + end
    template = start + ", " + str(trigger) + ", " + end
    name = checkpoint + " - " + _bounded_text(config_name, maximum=512)
    data = await _load_config()
    _update_config(data, digest, name, prompt=template)
    await _store_config(data)
    return {
        "ui": {"config_names": _config_names(data)},
        "result": (output, content),
    }


def _stored_value(data, digest: str, name: str, key: str) -> str:
    for row in data.get(digest, []):
        if row.get("other_data") == name:
            return str(row.get(key) or "")
    return ""


async def _smart_prompt(prompt_text, config_name, trigger, clip):
    digest, _checkpoint = _trigger(trigger)
    data = await _load_config()
    template = _stored_value(data, digest, str(config_name), "prompt")
    prompt = str(prompt_text) if template == "" else re.sub(
        r"\b{}\b".format(re.escape(digest)), str(prompt_text), template,
    )
    return (await clip.encode(prompt),)


async def _smart_negative(trigger, config_name, clip, optional_text=None):
    digest, _checkpoint = _trigger(trigger)
    data = await _load_config()
    negative = _stored_value(data, digest, str(config_name), "negative")
    if not negative:
        negative = str(optional_text or "")
    # Upstream emits an invalid STRING on this CONDITIONING socket. Secure V2
    # normalizes that broken edge to the equivalent empty-prompt conditioning.
    return (await clip.encode(negative),)


async def _load_configs(config_names):
    # The schema's remote combo supplies the selected value; storage is read
    # to keep the pack's scoped config initialized and bounded.
    await _load_config()
    return (str(config_names),)


async def _button():
    return ()


async def _sample_once(
    *, model, positive, negative, latent, seed, steps, cfg,
    sampler_name, scheduler, denoise=1.0, disable_noise=False,
    start_step=None, last_step=None, force_full_denoise=False, noise=None,
):
    return await _ctx().sample(
        latent=latent, steps=int(steps), model=model, positive=positive,
        negative=negative, cfg=float(cfg), seed=int(seed),
        sampler_name=str(sampler_name), scheduler=str(scheduler),
        denoise=float(denoise), disable_noise=bool(disable_noise),
        start_step=None if start_step is None else int(start_step),
        last_step=None if last_step is None else int(last_step),
        force_full_denoise=bool(force_full_denoise), noise=noise,
    )


async def _upscale_latent(latent, enabled, method="nearest-exact", ratio=1.5):
    if str(enabled) != "Yes":
        return latent
    height, width = await latent.spatial_shape()
    return await latent.resize(round(width * float(ratio)), round(height * float(ratio)), str(method))


async def _ksampler(
    model, seed, steps, cfg, sampler_name, scheduler, positive, negative,
    latent_image, denoise, upscale_latent, upscale_method="nearest-exact", ratio=1.5,
):
    sampled = await _sample_once(
        model=model, positive=positive, negative=negative, latent=latent_image,
        seed=seed, steps=steps, cfg=cfg, sampler_name=sampler_name,
        scheduler=scheduler, denoise=denoise,
    )
    upscaled = await _upscale_latent(sampled, upscale_latent, upscale_method, ratio)
    return model, positive, negative, seed, sampled, upscaled


async def _ksampler_advanced(
    model, add_noise, noise_seed, steps, cfg, sampler_name, scheduler,
    positive, negative, latent_image, start_at_step, end_at_step,
    return_with_leftover_noise,
):
    sampled = await _sample_once(
        model=model, positive=positive, negative=negative, latent=latent_image,
        seed=noise_seed, steps=steps, cfg=cfg, sampler_name=sampler_name,
        scheduler=scheduler, disable_noise=str(add_noise) == "disable",
        start_step=start_at_step, last_step=end_at_step,
        force_full_denoise=str(return_with_leftover_noise) != "enable",
    )
    return model, positive, negative, noise_seed, sampled


def _rotational_prompt(prompt: str):
    choices: list[list[str]] = []
    def replace(match):
        choices.append(match.group(1).split("|"))
        return f"qmRot{len(choices) - 1}"
    return re.sub(r"\[([^\[]+\|[^\]]+)\]", replace, prompt), choices


async def _rotational_sampler(
    prompt, negPrompt, model, clip, seed, steps, cfg, image_advance, weight,
    new_seed_after_steps, sampler_name, scheduler, latent_image,
    upscale_latent, upscale_method="nearest-exact", ratio=1.5,
):
    base, choices = _rotational_prompt(str(prompt))
    current = latent_image
    seed_value = int(seed)
    if choices:
        negative = await clip.encode(str(negPrompt))
        for index in range(int(steps)):
            current_prompt = base
            choice_index = index % 2
            for choice_number, values in enumerate(choices):
                if len(values) < 2:
                    raise ValueError("rotational prompt alternatives require two values")
                current_prompt = current_prompt.replace(f"qmRot{choice_number}", values[choice_index])
            positive = await clip.encode(current_prompt)
            last_step = index + 1 + int(image_advance) if index < int(steps) * float(weight) else index + 2
            current = await _sample_once(
                model=model, positive=positive, negative=negative, latent=current,
                seed=seed_value, steps=steps, cfg=cfg, sampler_name=sampler_name,
                scheduler=scheduler, start_step=index + 1,
                last_step=min(last_step, int(steps)), force_full_denoise=True,
            )
            if index % int(new_seed_after_steps) == 0:
                seed_value = random.randint(0, 0xFFFFFFFFFFFFFFFF)
    else:
        current = await _sample_once(
            model=model, positive=await clip.encode(str(prompt)),
            negative=await clip.encode(str(negPrompt)), latent=current,
            seed=seed_value, steps=steps, cfg=cfg, sampler_name=sampler_name,
            scheduler=scheduler,
        )
    current = await _upscale_latent(current, upscale_latent, upscale_method, ratio)
    return current, str(prompt), str(negPrompt)


async def _latent_image(width, height, batch_size, orientation):
    width, height = int(width), int(height)
    if str(orientation) == "force-landscape" and height > width:
        width, height = height, width
    elif str(orientation) == "force-portrait" and width > height:
        width, height = height, width
    return (await sdk.LatentRef.empty(width, height, int(batch_size)),)


async def _batch_from_latent(latent, batch_size=1):
    value = await materialize(latent)
    samples = value.get("samples") if isinstance(value, dict) else None
    if not isinstance(samples, torch.Tensor) or samples.ndim != 4:
        raise TypeError("Batch From Latent needs a four-dimensional sample tensor")
    single = samples.view(1, *samples.shape[1:])
    return ({"samples": single.repeat(int(batch_size), 1, 1, 1)},)


async def _ksampler_batched(
    model, seed, steps, cfg, sampler_name, scheduler, positive, negative,
    latent_image, denoise,
):
    value = await materialize(latent_image)
    samples = value.get("samples") if isinstance(value, dict) else None
    mask = value.get("noise_mask") if isinstance(value, dict) else None
    if not isinstance(samples, torch.Tensor) or samples.ndim != 4:
        raise TypeError("batched sampler needs a four-dimensional LATENT")
    if not isinstance(mask, torch.Tensor) or mask.shape[0] != samples.shape[0]:
        raise TypeError("batched sampler requires one noise mask per latent")
    generator = torch.manual_seed(int(seed))
    noise = torch.randn(samples.size(), dtype=samples.dtype, layout=samples.layout, generator=generator, device="cpu")
    processed = []
    for index in range(samples.shape[0]):
        single = dict(value)
        single["samples"] = samples[index:index + 1]
        single["noise_mask"] = mask[index:index + 1]
        latent_ref = await sdk.LatentRef.from_value(single)
        noise_ref = await sdk.TensorRef._from_raw(noise[index:index + 1])
        result = await _sample_once(
            model=model, positive=positive, negative=negative, latent=latent_ref,
            seed=seed, steps=steps, cfg=cfg, sampler_name=sampler_name,
            scheduler=scheduler, denoise=denoise, noise=noise_ref,
        )
        processed.append((await result.value())["samples"])
    out = dict(value)
    out["samples"] = torch.cat(processed, dim=0)
    return model, positive, negative, seed, out


def _segment(value: Any) -> tuple[Any, Any]:
    if isinstance(value, dict):
        return value.get("cropped_mask"), value.get("crop_region")
    if isinstance(value, (tuple, list)) and len(value) == 7:
        return value[1], value[3]
    raise TypeError("SEGS entries must use Impact Pack's seven-field layout")


async def _mask_from_segs(value: Any) -> torch.Tensor:
    segs = await materialize(value)
    if not isinstance(segs, (tuple, list)) or len(segs) != 2:
        raise TypeError("SEGS must be a (shape, segments) pair")
    height, width = map(int, segs[0])
    if not (1 <= height <= 16_384 and 1 <= width <= 16_384):
        raise ValueError("SEGS dimensions are out of bounds")
    mask = np.zeros((height, width), dtype=np.uint8)
    for entry in segs[1]:
        cropped, region = _segment(entry)
        left, top, right, bottom = map(int, region)
        array = torch.as_tensor(cropped).detach().cpu().numpy()
        while array.ndim > 2:
            array = array[0]
        target = (array * 255).astype(np.uint8)
        expected = (bottom - top, right - left)
        if target.shape != expected or not (0 <= left < right <= width and 0 <= top < bottom <= height):
            raise ValueError("SEGS crop mask does not match its region")
        mask[top:bottom, left:right] |= target
    return torch.from_numpy(mask.astype(np.float32) / 255.0).unsqueeze(0)


async def _change_background(
    model, model_2, positive, positive_2, negative, negative_2, image, vae,
    segs_from_SEGM_Detector, seed, steps, steps_2, cfg, sampler_name,
    scheduler, denoise, denoise_2,
):
    foreground = await _mask_from_segs(segs_from_SEGM_Detector)
    background = await sdk.MaskRef._from_raw(1.0 - foreground)
    latent = await vae.encode_for_inpaint(image, background, grow_mask_by=6)
    first = await _sample_once(
        model=model, positive=positive, negative=negative, latent=latent,
        seed=seed, steps=steps, cfg=cfg, sampler_name=sampler_name,
        scheduler=scheduler, denoise=denoise,
    )
    second = await _sample_once(
        model=model_2, positive=positive_2, negative=negative_2, latent=first,
        seed=seed, steps=steps_2, cfg=cfg, sampler_name=sampler_name,
        scheduler=scheduler, denoise=denoise_2,
    )
    return (await vae.decode(second),)


NODE_CLASS_MAPPINGS = {
    "quadmoonThebutton": bind_node("quadmoonThebutton", _button),
    "quadmoonCLIPTextEncode": bind_node("quadmoonCLIPTextEncode", _clip_encode),
    "quadmoonCLIPTextEncode2": bind_node("quadmoonCLIPTextEncode2", _clip_encode_advanced, permissions=("raw",)),
    "quadmoonConvertIntToString": bind_node("quadmoonConvertIntToString", _int_to_string),
    "quadmoonConvertFloatToString": bind_node("quadmoonConvertFloatToString", _float_to_string),
    "quadmoonConvertBoolToString": bind_node("quadmoonConvertBoolToString", _bool_to_string),
    "quadmoonConvertNumberToString": bind_node("quadmoonConvertNumberToString", _number_to_string),
    "quadmoonConvertImageToPrompt": bind_node("quadmoonConvertImageToPrompt", _image_to_prompt, permissions=("assets",)),
    "quadmoonINTConditionalOperation": bind_node("quadmoonINTConditionalOperation", _int_compare),
    "quadmoonConvertNormalizeHW": bind_node("quadmoonConvertNormalizeHW", _normalize_hw, permissions=("raw",)),
    "quadmoonKSampler": bind_node("quadmoonKSampler", _ksampler, permissions=("sample",)),
    "quadmoonKSamplerAdvanced": bind_node("quadmoonKSamplerAdvanced", _ksampler_advanced, permissions=("sample",)),
    "quadmoonRotationalSampler": bind_node("quadmoonRotationalSampler", _rotational_sampler, permissions=("sample",)),
    "quadmoonModelLoader": bind_node("quadmoonModelLoader", _model_loader, permissions=("models",)),
    "quadmoonLoadConfigs": bind_node("quadmoonLoadConfigs", _load_configs, permissions=("storage",)),
    "quadmoonSmartPrompt": bind_node("quadmoonSmartPrompt", _smart_prompt, permissions=("storage",)),
    "quadmoonSmartNeg": bind_node("quadmoonSmartNeg", _smart_negative, permissions=("storage",)),
    "quadmoonSavePrompt": bind_node("quadmoonSavePrompt", _save_prompt, permissions=("storage",)),
    "quadmoonSaveNeg": bind_node("quadmoonSaveNeg", _save_negative, permissions=("storage",)),
    "quadmoonChangeBackground": bind_node("quadmoonChangeBackground", _change_background, permissions=("raw", "sample")),
    "quadmoonLatentImage": bind_node("quadmoonLatentImage", _latent_image),
    "quadmoonBatchFromLatent": bind_node("quadmoonBatchFromLatent", _batch_from_latent, permissions=("raw",)),
    "quadmoonKSamplerBatched": bind_node("quadmoonKSamplerBatched", _ksampler_batched, permissions=("raw", "sample")),
}

NODE_DISPLAY_NAME_MAPPINGS = {}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "SCHEMAS"]
