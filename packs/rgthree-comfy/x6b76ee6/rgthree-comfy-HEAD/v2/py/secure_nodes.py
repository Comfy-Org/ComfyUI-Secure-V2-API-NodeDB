"""Secure Nodes 2.0 implementations for rgthree-comfy's default node set."""
from __future__ import annotations

import json
import math
import os.path
import random
import re
import time
from typing import Any

import torch

from ._secure import io, materialize, node, sdk
from .image_ops import common_upscale
from .safe_puter import Evaluator, is_nondeterministic, update_code


ORIGINAL_CONTEXT_FIELDS = (
    "model", "clip", "vae", "positive", "negative", "latent", "images", "seed",
)
ALL_CONTEXT_FIELDS = ORIGINAL_CONTEXT_FIELDS + (
    "steps", "step_refiner", "cfg", "ckpt_name", "sampler", "scheduler",
    "clip_width", "clip_height", "text_pos_g", "text_pos_l", "text_neg_g",
    "text_neg_l", "mask", "control_net",
)
_LORA_PATTERN = re.compile(r"<lora:([^:>]*?)(?::(-?\d*(?:\.\d*)?))?>")
_seed_rng = random.Random(time.time_ns())


def _context_empty(value: Any) -> bool:
    return not value or (
        isinstance(value, dict) and all(item is None for item in value.values())
    )


def _context_result(context: dict[str, Any] | None, fields: tuple[str, ...]):
    return (context,) + tuple(
        context.get(field) if context is not None else None for field in fields
    )


async def _any_switch(cls, **kwargs):
    value = None
    for name, candidate in kwargs.items():
        if not name.startswith("any_"):
            continue
        empty_context = (
            isinstance(candidate, dict)
            and "model" in candidate
            and "clip" in candidate
            and _context_empty(candidate)
        )
        if candidate is not None and not empty_context:
            value = candidate
            break
    return io.NodeOutput(value)


async def _context(cls, *, big: bool = False, base_ctx=None, **kwargs):
    fields = ALL_CONTEXT_FIELDS if big else ORIGINAL_CONTEXT_FIELDS
    base = base_ctx if isinstance(base_ctx, dict) else {}
    result = {
        field: kwargs.get(field)
        if kwargs.get(field) is not None
        else base.get(field)
        for field in ALL_CONTEXT_FIELDS
    }
    return io.NodeOutput(*_context_result(result, fields))


async def _context_small(cls, base_ctx=None, **kwargs):
    return await _context(cls, big=False, base_ctx=base_ctx, **kwargs)


async def _context_big(cls, base_ctx=None, **kwargs):
    return await _context(cls, big=True, base_ctx=base_ctx, **kwargs)


async def _context_switch(cls, *, big: bool = False, **kwargs):
    selected = None
    for name, candidate in kwargs.items():
        if name.startswith("ctx_") and not _context_empty(candidate):
            selected = candidate
            break
    fields = ALL_CONTEXT_FIELDS if big else ORIGINAL_CONTEXT_FIELDS
    return io.NodeOutput(*_context_result(selected, fields))


async def _context_switch_small(cls, **kwargs):
    return await _context_switch(cls, big=False, **kwargs)


async def _context_switch_big(cls, **kwargs):
    return await _context_switch(cls, big=True, **kwargs)


async def _context_merge(cls, *, big: bool = False, **kwargs):
    contexts = [
        value for name, value in kwargs.items()
        if name.startswith("ctx_") and not _context_empty(value)
    ]
    merged = {}
    for field in ALL_CONTEXT_FIELDS:
        merged[field] = next(
            (
                context.get(field)
                for context in reversed(contexts)
                if context.get(field) is not None
            ),
            None,
        )
    fields = ALL_CONTEXT_FIELDS if big else ORIGINAL_CONTEXT_FIELDS
    return io.NodeOutput(*_context_result(merged, fields))


async def _context_merge_small(cls, **kwargs):
    return await _context_merge(cls, big=False, **kwargs)


async def _context_merge_big(cls, **kwargs):
    return await _context_merge(cls, big=True, **kwargs)


async def _display_any(cls, source=None, **_kwargs):
    if isinstance(source, sdk.Ref) and not isinstance(
        source, (sdk.TensorRef, sdk.ValueRef)
    ):
        value = f"<{source.kind} ref>"
    else:
        source = await materialize(source)
        if isinstance(source, str):
            value = source
        elif isinstance(source, (int, float, bool)):
            value = str(source)
        elif source is None:
            value = "None"
        else:
            try:
                value = json.dumps(source)
            except (TypeError, ValueError):
                value = str(source)
    return io.NodeOutput(ui={"text": [value]})


async def _display_int(cls, input=None):
    return io.NodeOutput(ui={"text": [input]})


async def _image_comparer(cls, image_a=None, image_b=None, **_kwargs):
    ui = {"a_images": [], "b_images": []}
    if image_a is not None:
        preview = await sdk.ctx().ui.preview_images(image_a)
        ui["a_images"] = list(preview.get("images", []))
    if image_b is not None:
        preview = await sdk.ctx().ui.preview_images(image_b)
        ui["b_images"] = list(preview.get("images", []))
    # PreviewImage's inherited V1 declaration includes one IMAGE output even
    # though rgthree's method returned UI only. Preserve that empty result slot.
    return io.NodeOutput(None, ui=ui)


async def _image_inset_crop(
    cls, image, measurement, left, right, top, bottom
):
    value = await image.raw()
    _, height, width, _ = value.shape
    if measurement == "Percentage":
        left = int(width - width * (100 - left) / 100)
        right = int(width - width * (100 - right) / 100)
        top = int(height - height * (100 - top) / 100)
        bottom = int(height - height * (100 - bottom) / 100)
    left, right, top, bottom = (
        int(item) // 8 * 8 for item in (left, right, top, bottom)
    )
    if not any((left, right, top, bottom)):
        return io.NodeOutput(image)
    x1, x2 = left, width - right
    y1, y2 = top, height - bottom
    if y1 > y2:
        raise ValueError(f"Invalid cropping dimensions top ({y1}) exceeds bottom ({y2})")
    if x1 > x2:
        raise ValueError(f"Invalid cropping dimensions left ({x1}) exceeds right ({x2})")
    cropped = value[:, y1:y2, x1:x2, :]
    return io.NodeOutput(await sdk.ImageRef._from_raw(cropped))


async def _image_resize(cls, image, measurement, width, height, method, fit):
    value = await image.raw()
    _, source_height, source_width, _ = value.shape
    width = int(width)
    height = int(height)
    if measurement == "percentage":
        width = round(width * source_width / 100)
        height = round(height * source_height / 100)
    if (width == 0 and height == 0) or (
        width == source_width and height == source_height
    ):
        return io.NodeOutput(image, source_width, source_height)
    if width == 0 or height == 0:
        width = round(height / source_height * source_width) if width == 0 else width
        height = round(width / source_width * source_height) if height == 0 else height
        fit = "contain"
    if width <= 0 or height <= 0:
        raise ValueError("Image Resize dimensions must be positive")

    resized_width, resized_height = width, height
    if fit == "crop":
        if height / source_height * source_width > width:
            resized_width = round(height / source_height * source_width)
        elif width / source_width * source_height > height:
            resized_height = round(width / source_width * source_height)
    elif fit in ("contain", "pad"):
        if height / source_height * source_width > width:
            resized_height = round(width / source_width * source_height)
        elif width / source_width * source_height > height:
            resized_width = round(height / source_height * source_width)

    output = common_upscale(
        value.clone().movedim(-1, 1),
        resized_width,
        resized_height,
        method,
        "disabled",
    ).movedim(1, -1)
    batch, out_height, out_width, channels = output.shape
    if fit != "contain":
        if out_width > width:
            output = output.narrow(-2, (out_width - width) // 2, width)
        if out_height > height:
            output = output.narrow(-3, (out_height - height) // 2, height)
        batch, out_height, out_width, channels = output.shape
        if out_width != width or out_height != height:
            padded = torch.zeros(
                (batch, height, width, channels),
                dtype=value.dtype,
                device=value.device,
            )
            x = (width - out_width) // 2
            y = (height - out_height) // 2
            padded[:, y:y + out_height, x:x + out_width, :] = output
            output = padded
    return io.NodeOutput(
        await sdk.ImageRef._from_raw(output), output.shape[2], output.shape[1]
    )


async def _image_or_latent_size(cls, **kwargs):
    value = kwargs.get("input")
    value = await materialize(value)
    if isinstance(value, dict) and "samples" in value:
        _, _, height, width = value["samples"].shape
        return io.NodeOutput(width * 8, height * 8)
    if value is None or not hasattr(value, "shape") or len(value.shape) < 3:
        raise ValueError("Image or Latent Size needs an IMAGE, MASK, or LATENT input")
    height, width = value.shape[-3:-1] if len(value.shape) >= 4 else value.shape[-2:]
    return io.NodeOutput(int(width), int(height))


async def _ksampler_config(
    cls, steps_total, refiner_step, cfg, sampler_name, scheduler
):
    return io.NodeOutput(steps_total, refiner_step, cfg, sampler_name, scheduler)


def _lora_match(name: str, catalogue: list[str]) -> str | None:
    name = str(name).replace("\\", "/")
    if name in catalogue:
        return name
    without_ext = [os.path.splitext(item)[0] for item in catalogue]
    if name in without_ext:
        return catalogue[without_ext.index(name)]
    forced_no_ext = os.path.splitext(name)[0]
    if forced_no_ext in without_ext:
        return catalogue[without_ext.index(forced_no_ext)]
    filenames = [os.path.basename(item) for item in catalogue]
    if name in filenames:
        return catalogue[filenames.index(name)]
    forced_filename = os.path.basename(name)
    if forced_filename in filenames:
        return catalogue[filenames.index(forced_filename)]
    stems = [os.path.splitext(item)[0] for item in filenames]
    if name in stems:
        return catalogue[stems.index(name)]
    forced_stem = os.path.splitext(forced_filename)[0]
    if forced_stem in stems:
        return catalogue[stems.index(forced_stem)]
    return next((item for item in catalogue if name in item), None)


async def _apply_lora(model, clip, name, strength_model, strength_clip, catalogue):
    if model is None:
        return model, clip
    matched = _lora_match(name, catalogue)
    if matched is None:
        return model, clip
    if clip is None:
        strength_clip = 0.0
    asset = await sdk.ctx().assets.resolve("loras", matched)
    return await model.apply_lora(
        asset, clip, float(strength_model), float(strength_clip)
    )


async def _lora_stack(cls, model, clip, **kwargs):
    catalogue = await sdk.ctx().assets.list("loras")
    for index in range(1, 5):
        name = kwargs[f"lora_{index:02d}"]
        strength = kwargs[f"strength_{index:02d}"]
        if name != "None" and float(strength) != 0.0:
            model, clip = await _apply_lora(
                model, clip, name, strength, strength, catalogue
            )
    return io.NodeOutput(model, clip)


async def _power_lora_loader(cls, model=None, clip=None, **kwargs):
    catalogue = await sdk.ctx().assets.list("loras") if model is not None else []
    for name, value in kwargs.items():
        if not name.upper().startswith("LORA_") or not isinstance(value, dict):
            continue
        if not {"on", "lora", "strength"}.issubset(value) or not value["on"]:
            continue
        strength_model = float(value["strength"])
        strength_clip = float(value.get("strengthTwo", strength_model))
        if clip is None:
            strength_clip = 0.0
        if model is not None and (strength_model != 0.0 or strength_clip != 0.0):
            model, clip = await _apply_lora(
                model,
                clip,
                value["lora"],
                strength_model,
                strength_clip,
                catalogue,
            )
    return io.NodeOutput(model, clip)


def _cast_bool(value: Any) -> bool:
    try:
        return bool(float(value))
    except (TypeError, ValueError):
        return str(value).lower() not in {"0", "false", "null", "none", ""}


async def _power_primitive(cls, **kwargs):
    value = kwargs.get("value")
    if isinstance(value, (sdk.TensorRef, sdk.ValueRef)):
        value = await materialize(value)
    output_type = re.sub(r"\s*\([^)]*\)\s*$", "", str(kwargs.get("type", "")))
    if output_type == "STRING":
        try:
            value = "" if value is None else str(value)
        except (TypeError, ValueError):
            value = ""
    elif output_type == "FLOAT":
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = 0.0
    elif output_type == "INT":
        try:
            value = int(float(value))
        except (TypeError, ValueError):
            value = 0
    elif output_type in ("BOOL", "BOOLEAN"):
        value = _cast_bool(value)
    else:
        raise ValueError(f"Unsupported Power Primitive type {output_type!r}")
    return io.NodeOutput(value)


def _parse_loras(prompt: str, catalogue: list[str]):
    found = []
    skipped = []
    missing = []
    for match in _LORA_PATTERN.findall(prompt):
        name, strength_text = match
        strength = float(strength_text) if strength_text else 1.0
        item = {"lora": name, "strength": strength}
        if strength == 0.0:
            skipped.append(item)
            continue
        matched = _lora_match(name, catalogue)
        if matched is None:
            missing.append(item)
        else:
            found.append({"lora": matched, "strength": strength})
    return _LORA_PATTERN.sub("", prompt), found, skipped, missing


async def _power_prompt_impl(
    prompt, opt_model=None, opt_clip=None, insert_lora=None
):
    has_tags = bool(_LORA_PATTERN.search(prompt))
    if has_tags:
        catalogue = await sdk.ctx().assets.list("loras")
        stripped, loras, _skipped, _missing = _parse_loras(prompt, catalogue)
        # This follows the actual upstream method: all three branches strip
        # tags, including the branch whose old log text claimed otherwise.
        prompt = stripped
        if insert_lora != "DISABLE LORAS" and opt_model is not None and opt_clip is not None:
            for item in loras:
                opt_model, opt_clip = await _apply_lora(
                    opt_model,
                    opt_clip,
                    item["lora"],
                    item["strength"],
                    item["strength"],
                    catalogue,
                )
    conditioning = await opt_clip.encode(prompt) if opt_clip is not None else None
    return conditioning, opt_model, opt_clip, prompt


async def _power_prompt(
    cls,
    prompt,
    opt_model=None,
    opt_clip=None,
    insert_lora=None,
    **_kwargs,
):
    values = await _power_prompt_impl(prompt, opt_model, opt_clip, insert_lora)
    return io.NodeOutput(*values)


async def _power_prompt_simple(cls, prompt, opt_clip=None, **_kwargs):
    conditioning = await opt_clip.encode(prompt) if opt_clip is not None else None
    return io.NodeOutput(conditioning, prompt)


async def _sdxl_encode(
    clip,
    prompt_g,
    prompt_l,
    width,
    height,
    target_width,
    target_height,
    crop_width,
    crop_height,
):
    if clip is None:
        return None
    if not width or not height:
        return await clip.encode(f"{prompt_g or ''}\n{prompt_l or ''}")
    width, height = int(width), int(height)
    target_width = int(target_width) if target_width and target_width > 0 else width
    target_height = int(target_height) if target_height and target_height > 0 else height
    crop_width = int(crop_width) if crop_width and crop_width > 0 else 0
    crop_height = int(crop_height) if crop_height and crop_height > 0 else 0
    try:
        tokens = await clip.tokenize(prompt_g)
        local = await clip.tokenize(prompt_l)
        tokens["l"] = local["l"]
        if len(tokens["l"]) != len(tokens["g"]):
            empty = await clip.tokenize("")
            while len(tokens["l"]) < len(tokens["g"]):
                tokens["l"] += empty["l"]
            while len(tokens["l"]) > len(tokens["g"]):
                tokens["g"] += empty["g"]
        return await clip.encode_from_tokens_scheduled(
            tokens,
            add_dict={
                "width": width,
                "height": height,
                "crop_w": crop_width,
                "crop_h": crop_height,
                "target_width": target_width,
                "target_height": target_height,
            },
        )
    except Exception:
        return await clip.encode(f"{prompt_g or ''}\n{prompt_l or ''}")


async def _sdxl_positive(
    cls,
    prompt_g,
    prompt_l,
    opt_model=None,
    opt_clip=None,
    opt_clip_width=None,
    opt_clip_height=None,
    insert_lora=None,
    target_width=-1,
    target_height=-1,
    crop_width=-1,
    crop_height=-1,
    **_kwargs,
):
    has_tags = bool(_LORA_PATTERN.search(prompt_g) or _LORA_PATTERN.search(prompt_l))
    if has_tags:
        catalogue = await sdk.ctx().assets.list("loras")
        prompt_g, loras_g, _, _ = _parse_loras(prompt_g, catalogue)
        prompt_l, loras_l, _, _ = _parse_loras(prompt_l, catalogue)
        if insert_lora != "DISABLE LORAS" and opt_model is not None and opt_clip is not None:
            for item in loras_g + loras_l:
                opt_model, opt_clip = await _apply_lora(
                    opt_model,
                    opt_clip,
                    item["lora"],
                    item["strength"],
                    item["strength"],
                    catalogue,
                )
    conditioning = await _sdxl_encode(
        opt_clip,
        prompt_g,
        prompt_l,
        opt_clip_width,
        opt_clip_height,
        target_width,
        target_height,
        crop_width,
        crop_height,
    )
    return io.NodeOutput(conditioning, opt_model, opt_clip, prompt_g, prompt_l)


async def _sdxl_simple(
    cls,
    prompt_g,
    prompt_l,
    opt_clip=None,
    opt_clip_width=None,
    opt_clip_height=None,
    target_width=-1,
    target_height=-1,
    crop_width=-1,
    crop_height=-1,
    **_kwargs,
):
    conditioning = await _sdxl_encode(
        opt_clip,
        prompt_g,
        prompt_l,
        opt_clip_width,
        opt_clip_height,
        target_width,
        target_height,
        crop_width,
        crop_height,
    )
    return io.NodeOutput(conditioning, prompt_g, prompt_l)


async def _sdxl_empty_latent(cls, dimensions, clip_scale, batch_size):
    width_text, remainder = dimensions.split("x", 1)
    width = int(width_text.strip())
    height = int(remainder.strip().split(" ", 1)[0])
    latent = {
        "samples": torch.zeros(
            [int(batch_size), 4, height // 8, width // 8], dtype=torch.float32
        )
    }
    return io.NodeOutput(
        await sdk.LatentRef.from_value(latent),
        int(width * float(clip_scale)),
        int(height * float(clip_scale)),
    )


def _new_random_seed() -> int:
    return _seed_rng.randint(1, 1125899906842624)


def _seed_fingerprint(cls, seed, **_kwargs):
    return _new_random_seed() if seed in (-1, -2, -3) else seed


async def _seed(cls, seed=0, **_kwargs):
    if seed in (-1, -2, -3):
        seed = _new_random_seed()
    return io.NodeOutput(seed)


async def _materialize_puter_value(
    value: Any, tensor_refs: dict[int, sdk.TensorRef]
) -> Any:
    """Materialize Power Puter data and remember exact tensor pass-throughs."""
    if isinstance(value, sdk.TensorRef):
        raw = await value.raw()
        tensor_refs[id(raw)] = value
        return raw
    if isinstance(value, sdk.ValueRef):
        return await value.value()
    if isinstance(value, dict):
        return {
            key: await _materialize_puter_value(item, tensor_refs)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            await _materialize_puter_value(item, tensor_refs)
            for item in value
        ]
    if isinstance(value, tuple):
        return tuple([
            await _materialize_puter_value(item, tensor_refs)
            for item in value
        ])
    return value


async def _wrap_puter_value(
    value: Any, tensor_refs: dict[int, sdk.TensorRef]
) -> Any:
    if value is None or isinstance(value, sdk.Ref):
        return value
    if isinstance(value, torch.Tensor):
        original = tensor_refs.get(id(value))
        if original is not None:
            return original
        ref_type = sdk.MaskRef if value.ndim in (2, 3) else sdk.ImageRef
        return await ref_type._from_raw(value)
    if isinstance(value, dict):
        if "samples" in value and isinstance(value["samples"], torch.Tensor):
            return await sdk.LatentRef.from_value(value)
        return {
            key: await _wrap_puter_value(item, tensor_refs)
            for key, item in value.items()
        }
    if isinstance(value, list):
        if (
            value
            and isinstance(value[0], (list, tuple))
            and len(value[0]) == 2
            and isinstance(value[0][0], torch.Tensor)
            and isinstance(value[0][1], dict)
        ):
            return await sdk.CondRef.from_value(value)
        return [await _wrap_puter_value(item, tensor_refs) for item in value]
    if isinstance(value, tuple):
        return tuple([
            await _wrap_puter_value(item, tensor_refs) for item in value
        ])
    return value


def _puter_fingerprint(cls, **kwargs):
    code = update_code(str(kwargs.get("code", "")))
    return time.time() if is_nondeterministic(code) else 42


async def _power_puter(cls, **kwargs):
    output_spec = kwargs.get("outputs")
    if isinstance(output_spec, dict):
        outputs = list(output_spec.get("outputs") or [])
    elif isinstance(output_spec, str):
        outputs = [output_spec]
    else:
        outputs = [kwargs.get("output") or "STRING"]
    if not 1 <= len(outputs) <= 10:
        raise ValueError("Power Puter needs between one and ten outputs")

    values = {}
    tensor_refs: dict[int, sdk.TensorRef] = {}
    for letter in "abcdefghijklmnopqrstuvwxyz":
        value = kwargs.get(letter)
        # A custom CONTEXT socket can carry nested IMAGE/LATENT data refs and
        # opaque MODEL/CLIP refs together. Materialize only the data-capable
        # leaves and retain the opaque handles.
        values[letter] = await _materialize_puter_value(value, tensor_refs)
    evaluator = Evaluator(
        code=str(kwargs.get("code", "")),
        values=values,
        prompt=kwargs.get("prompt"),
        unique_id=str(kwargs.get("unique_id", "")),
    )
    result = evaluator.execute()
    if len(outputs) > 1 and not isinstance(result, tuple):
        raise ValueError(
            "Power Puter code must return a tuple when multiple outputs are selected"
        )
    values_out = (result,) if len(outputs) == 1 else result
    response = []
    for index, output in enumerate(outputs):
        value = values_out[index] if index < len(values_out) else None
        if value is not None:
            if output == "INT":
                value = int(value)
            elif output == "FLOAT":
                value = float(value)
            elif output in ("BOOL", "BOOLEAN"):
                value = bool(value)
            elif output == "STRING":
                value = (
                    json.dumps(value, indent=2)
                    if isinstance(value, (dict, list))
                    else str(value)
                )
            elif output != "*":
                raise ValueError(f"Unsupported Power Puter output type {output!r}")
        response.append(await _wrap_puter_value(value, tensor_refs))
    response.extend([None] * (10 - len(response)))
    return io.NodeOutput(*response)


NODE_CLASS_MAPPINGS = {
    "Any Switch (rgthree)": node(
        "Any Switch (rgthree)", _any_switch, class_name="RgthreeAnySwitch"
    ),
    "Context (rgthree)": node(
        "Context (rgthree)", _context_small, class_name="RgthreeContext"
    ),
    "Context Big (rgthree)": node(
        "Context Big (rgthree)", _context_big, class_name="RgthreeBigContext"
    ),
    "Context Merge (rgthree)": node(
        "Context Merge (rgthree)", _context_merge_small, class_name="RgthreeContextMerge"
    ),
    "Context Merge Big (rgthree)": node(
        "Context Merge Big (rgthree)", _context_merge_big, class_name="RgthreeContextMergeBig"
    ),
    "Context Switch (rgthree)": node(
        "Context Switch (rgthree)", _context_switch_small, class_name="RgthreeContextSwitch"
    ),
    "Context Switch Big (rgthree)": node(
        "Context Switch Big (rgthree)", _context_switch_big, class_name="RgthreeContextSwitchBig"
    ),
    "Display Any (rgthree)": node(
        "Display Any (rgthree)", _display_any, class_name="RgthreeDisplayAny",
        permissions=("raw",),
    ),
    "Display Int (rgthree)": node(
        "Display Int (rgthree)", _display_int, class_name="RgthreeDisplayInt"
    ),
    "Image Comparer (rgthree)": node(
        "Image Comparer (rgthree)", _image_comparer,
        class_name="RgthreeImageComparer", permissions=("ui",),
    ),
    "Image Inset Crop (rgthree)": node(
        "Image Inset Crop (rgthree)", _image_inset_crop,
        class_name="RgthreeImageInsetCrop", permissions=("raw",),
    ),
    "Image Resize (rgthree)": node(
        "Image Resize (rgthree)", _image_resize,
        class_name="RgthreeImageResize", permissions=("raw",),
    ),
    "Image or Latent Size (rgthree)": node(
        "Image or Latent Size (rgthree)", _image_or_latent_size,
        class_name="RgthreeImageOrLatentSize", permissions=("raw",),
    ),
    "KSampler Config (rgthree)": node(
        "KSampler Config (rgthree)", _ksampler_config,
        class_name="RgthreeKSamplerConfig",
    ),
    "Lora Loader Stack (rgthree)": node(
        "Lora Loader Stack (rgthree)", _lora_stack,
        class_name="RgthreeLoraLoaderStack", permissions=("assets",),
    ),
    "Power Lora Loader (rgthree)": node(
        "Power Lora Loader (rgthree)", _power_lora_loader,
        class_name="RgthreePowerLoraLoader", permissions=("assets",),
    ),
    "Power Primitive (rgthree)": node(
        "Power Primitive (rgthree)", _power_primitive,
        class_name="RgthreePowerPrimitive", permissions=("raw",),
    ),
    "Power Prompt (rgthree)": node(
        "Power Prompt (rgthree)", _power_prompt,
        class_name="RgthreePowerPrompt", permissions=("assets",),
    ),
    "Power Prompt - Simple (rgthree)": node(
        "Power Prompt - Simple (rgthree)", _power_prompt_simple,
        class_name="RgthreePowerPromptSimple",
    ),
    "Power Puter (rgthree)": node(
        "Power Puter (rgthree)", _power_puter,
        class_name="RgthreePowerPuter", permissions=("raw",),
        fingerprint=_puter_fingerprint,
    ),
    "SDXL Empty Latent Image (rgthree)": node(
        "SDXL Empty Latent Image (rgthree)", _sdxl_empty_latent,
        class_name="RgthreeSDXLEmptyLatentImage", permissions=("raw",),
    ),
    "SDXL Power Prompt - Positive (rgthree)": node(
        "SDXL Power Prompt - Positive (rgthree)", _sdxl_positive,
        class_name="RgthreeSDXLPowerPromptPositive", permissions=("assets",),
    ),
    "SDXL Power Prompt - Simple / Negative (rgthree)": node(
        "SDXL Power Prompt - Simple / Negative (rgthree)", _sdxl_simple,
        class_name="RgthreeSDXLPowerPromptSimple",
    ),
    "Seed (rgthree)": node(
        "Seed (rgthree)", _seed, class_name="RgthreeSeed",
        fingerprint=_seed_fingerprint,
    ),
}

NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: node_id for node_id in NODE_CLASS_MAPPINGS
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
