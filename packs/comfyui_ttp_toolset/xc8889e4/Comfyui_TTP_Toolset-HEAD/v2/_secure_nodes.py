"""Secure Nodes V2 bindings for the pinned TTP Toolset release.

The tiling, prompt, ranking, blending, colour, and LTX keyframe algorithms stay
in this pack.  V2 is used only at authority boundaries: opaque model/VAE refs,
managed input assets, output persistence, and permissioned raw tensors.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from io import BytesIO
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageDraw

from . import TTP_toolsets as alg
from ._secure_runtime import SCHEMAS, bind_node, materialize, sdk


_MAX_BATCH = 64
_MAX_IMAGE_PIXELS = 67_108_864
_MAX_TILE_PIXELS = 268_435_456
_MAX_TEXT = 1_048_576
_LOOP_SESSIONS: dict[str, dict[str, Any]] = {}
_PROMPT_CACHE: dict[str, dict[str, Any]] = {}


def _ctx():
    return sdk.ctx()


def _checked_image_tensor(value: Any, name: str = "image") -> torch.Tensor:
    if not isinstance(value, torch.Tensor):
        raise TypeError(f"{name} must materialize as a torch tensor")
    if value.ndim != 4 or value.shape[-1] < 1:
        raise ValueError(f"{name} must be a BHWC image tensor")
    batch, height, width = map(int, value.shape[:3])
    if not 1 <= batch <= _MAX_BATCH:
        raise ValueError(f"{name} batch must be in [1, {_MAX_BATCH}]")
    if height <= 0 or width <= 0 or height * width > _MAX_IMAGE_PIXELS:
        raise ValueError(f"{name} dimensions exceed the secure image bound")
    return value


async def _raw_image(value: Any, name: str = "image") -> torch.Tensor:
    if isinstance(value, sdk.ImageRef):
        value = await value.raw()
    return _checked_image_tensor(value, name)


def _validate_materialized_tree(value: Any, *, tensors: list[int]) -> None:
    if isinstance(value, torch.Tensor):
        tensors[0] += int(value.numel())
        if tensors[0] > _MAX_TILE_PIXELS * 4:
            raise ValueError("materialized tile data exceeds the secure tensor bound")
        return
    if isinstance(value, dict):
        if len(value) > 4096:
            raise ValueError("pack value dictionary exceeds 4096 entries")
        for child in value.values():
            _validate_materialized_tree(child, tensors=tensors)
        return
    if isinstance(value, (list, tuple)):
        if len(value) > 4096:
            raise ValueError("pack value sequence exceeds 4096 entries")
        for child in value:
            _validate_materialized_tree(child, tensors=tensors)
        return
    if isinstance(value, str) and len(value) > _MAX_TEXT:
        raise ValueError("pack text value exceeds 1 MiB")


async def _values(kwargs: dict[str, Any]) -> dict[str, Any]:
    result = {key: await materialize(value) for key, value in kwargs.items()}
    _validate_materialized_tree(result, tensors=[0])
    return result


async def _structured(value: Any) -> Any:
    """Materialize structured values while retaining opaque tensor handles."""
    if isinstance(value, sdk.TensorRef):
        return value
    if isinstance(value, sdk.ValueRef):
        return await _structured(await value.value())
    if isinstance(value, list):
        return [await _structured(item) for item in value]
    if isinstance(value, tuple):
        return tuple([await _structured(item) for item in value])
    if isinstance(value, dict):
        return {key: await _structured(item) for key, item in value.items()}
    return value


async def _structured_values(kwargs: dict[str, Any]) -> dict[str, Any]:
    result = {key: await _structured(value) for key, value in kwargs.items()}
    _validate_materialized_tree(result, tensors=[0])
    return result


def _legacy_handler(
    node_id: str,
    legacy_class: type,
    method: str,
    *,
    raw: bool = True,
):
    async def handler(**kwargs):
        values = await (_values(kwargs) if raw else _structured_values(kwargs))
        result = getattr(legacy_class(), method)(**values)
        if node_id == "TTP_Image_Assy":
            image = result[0]
            if isinstance(image, torch.Tensor) and image.ndim == 5 and image.shape[0] == 1:
                result = (image.squeeze(0),)
        elif node_id == "TTP_Expand_And_Mask":
            image, mask = result
            if isinstance(mask, torch.Tensor) and mask.ndim == 4 and mask.shape[1] == 1:
                mask = mask[:, 0]
            result = image, mask
        return result

    handler.__name__ = f"secure_{method}_{node_id.lower()}"
    return handler


_LEGACY = {
    "TTPlanet_Tile_Preprocessor_Simple": (
        alg.TTPlanet_Tile_Preprocessor_Simple, "process_image", True),
    "TTP_Image_Tile_Batch": (alg.TTP_Image_Tile_Batch, "tile_image", True),
    "TTP_Image_Assy": (alg.TTP_Image_Assy, "assemble_image", True),
    "TTP_CoordinateSplitter": (
        alg.TTP_CoordinateSplitter, "split_coordinates", False),
    "TTP_Tile_image_size": (alg.Tile_imageSize, "image_width_height", True),
    "TTP_Expand_And_Mask": (
        alg.TTP_Expand_And_Mask, "expand_and_mask", True),
    "TTP_text_mix": (alg.TTP_text_mix, "mix_texts", False),
    "TTP_Smart_Tile_Set_Preview_Experimental": (
        alg.TTP_Smart_Tile_Set_Preview_Experimental, "preview_tile_set", True),
    "TTP_Smart_Tile_Prompt_Override_Experimental": (
        alg.TTP_Smart_Tile_Prompt_Override_Experimental,
        "override_prompts", False),
    "TTP_Smart_Tile_Composite_Override_Experimental": (
        alg.TTP_Smart_Tile_Composite_Override_Experimental,
        "override_composite", False),
    "TTP_Smart_Tile_Stack_Order_Experimental": (
        alg.TTP_Smart_Tile_Stack_Order_Experimental,
        "apply_stack_order", False),
    "TTP_Smart_Tile_Semantic_Rank_Experimental": (
        alg.TTP_Smart_Tile_Semantic_Rank_Experimental, "rank_tiles", False),
    "TTP_Smart_Tile_Assemble_Experimental": (
        alg.TTP_Smart_Tile_Assemble_Experimental, "assemble_tiles", True),
}


async def _conditioning_batch(conditionings, **_kwargs):
    if not isinstance(conditionings, (list, tuple)) or not conditionings:
        raise ValueError("conditionings must be a non-empty input list")
    combined: list[Any] = []
    for conditioning in conditionings:
        value = await materialize(conditioning)
        if not isinstance(value, list):
            raise TypeError("each CONDITIONING must materialize as a list")
        combined.extend(value)
    return (combined,)


def _set_conditioning_area(item: Any, coord: Any, strength: float):
    if not isinstance(item, (list, tuple)) or len(item) < 2:
        raise TypeError("conditioning entries must be [embedding, metadata]")
    if not isinstance(coord, (list, tuple)) or len(coord) != 4:
        raise ValueError("each coordinate must contain x, y, width, height")
    x, y, width, height = [int(value) for value in coord]
    metadata = dict(item[1])
    metadata.update({
        "area": (height // 8, width // 8, y // 8, x // 8),
        "strength": float(strength),
        "set_area_to_bounds": False,
    })
    return [item[0], metadata]


async def _conditioning_areas(
    conditioning_batch, coordinates, strength, **_kwargs,
):
    conditioning = await materialize(conditioning_batch)
    coordinates = await materialize(coordinates)
    if len(coordinates) != len(conditioning):
        raise ValueError(
            f"The number of coordinates ({len(coordinates)}) does not match "
            f"the number of conditionings ({len(conditioning)})")
    return ([
        _set_conditioning_area(item, coord, strength)
        for item, coord in zip(conditioning, coordinates, strict=True)
    ],)


async def _conditioning_areas_grouped(
    conditioning_batch, coordinates, group_size, strength, **_kwargs,
):
    conditioning = list(await materialize(conditioning_batch))
    coordinates = list(await materialize(coordinates))
    group_size = int(group_size)
    if group_size < 1 or not conditioning:
        raise ValueError("group_size and conditioning batch must be non-empty")
    groups = math.ceil(len(conditioning) / group_size)
    if len(coordinates) > groups:
        multiplier = math.ceil(len(coordinates) * group_size / len(conditioning))
        conditioning *= multiplier
        groups = math.ceil(len(conditioning) / group_size)
    if len(coordinates) != groups:
        raise ValueError(
            f"The number of coordinates ({len(coordinates)}) does not match "
            f"the required number ({groups}) based on group size ({group_size}) "
            f"and conditioning length ({len(conditioning)})")
    output = []
    index = 0
    for coord in coordinates:
        for item in conditioning[index:index + group_size]:
            output.append(_set_conditioning_area(item, coord, strength))
        index += group_size
    return (output,)


async def _load_input_pil(name: str) -> Image.Image:
    logical = str(name or "").strip()
    if not logical:
        raise ValueError(
            "No image was selected. Upload/select an input image or connect "
            "source_image.")
    asset = await _ctx().assets.resolve("input", logical)
    size = await _ctx().assets.size(asset)
    if size <= 0 or size > 256 * 1024 * 1024:
        raise ValueError("input image asset must be between 1 byte and 256 MiB")
    data = await _ctx().assets.read_bytes(asset)
    image = Image.open(BytesIO(data))
    image.load()
    if image.width * image.height > _MAX_IMAGE_PIXELS:
        raise ValueError("input image exceeds 67,108,864 decoded pixels")
    return image.convert("RGB")


def _qwen_model_parts(value: Any):
    if isinstance(value, sdk.ClipRef):
        return value, ""
    if isinstance(value, dict) and value.get("type") == "ttp_qwenvl3_model":
        clip = value.get("clip")
        if not isinstance(clip, sdk.ClipRef):
            raise TypeError("QwenVL model payload does not contain a CLIP ref")
        return clip, str(value.get("model_file", ""))
    raise ValueError(
        "Connect TTP QwenVL3 Local Loader to qwen_vl_model first.")


async def _qwen_loader(model_file, model_family="auto", device="default", **_kwargs):
    model_file = str(model_file or "").replace("\\", "/").strip("/")
    if (not model_file or "\x00" in model_file
            or any(part in ("", ".", "..") for part in model_file.split("/"))
            or not model_file.lower().endswith((".safetensors", ".sft"))):
        raise ValueError("model_file must be a logical SafeTensors catalogue name")
    if model_family not in {"auto", "qwen_vl"}:
        raise ValueError("model_family must be auto or qwen_vl")
    if device not in {"default", "cpu"}:
        raise ValueError("device must be default or cpu")
    # This pinned pack used Comfy's QWEN_IMAGE loader for its QwenVL3 file.
    # Loading/caching stays host-owned; the guest receives only a ClipRef.
    clip = await _ctx().models.load_text_encoder(
        model_file, model_type="qwen_image", device=str(device))
    payload = {
        "type": "ttp_qwenvl3_model",
        "model_file": model_file,
        "model_family": str(model_family),
        "clip_type": "QWEN_IMAGE",
        "clip": clip,
    }
    return payload, f"Loaded local QwenVL model: {model_file} ({device})"


async def _qwen_chat(
    model: Any,
    prompt: str,
    image: Image.Image,
    *,
    max_new_tokens: int,
    temperature: float,
    seed: int,
) -> str:
    clip, _model_file = _qwen_model_parts(model)
    image_ref = await sdk.ImageRef._from_raw(alg.pil2tensor(image.convert("RGB")))
    do_sample = float(temperature) > 0.0
    raw = await clip.generate_text(
        str(prompt),
        image_ref,
        max_length=int(max_new_tokens),
        do_sample=do_sample,
        temperature=max(1e-6, float(temperature)) if do_sample else 1.0,
        top_k=50,
        top_p=0.95,
        min_p=0.0,
        repetition_penalty=1.0,
        seed=int(seed),
        presence_penalty=0.0,
        thinking=False,
        use_default_template=True,
    )
    return alg._ttp_clean_qwen_vl_response(str(raw), str(prompt))


async def _qwen_auto_layout(
    pil_image: Image.Image,
    qwen_vl_model: Any,
    auto_prompt: str,
    default_pad: int,
    default_blend: int,
    object_padding: int,
    mask_expand: int,
    max_tiles: int,
    allow_object_overlap: bool,
    paint_mask_payload: str,
):
    image_width, image_height = pil_image.size
    prompt = "\n".join([
        alg._TTP_QWENVL_PRESETS["bbox_detect"]["system"],
        alg._TTP_QWENVL_PRESETS["bbox_detect"]["instruction"],
        f"User focus prompt: {auto_prompt}",
        "Prioritize faces, eyes, hands, text, foreground subjects, and small details.",
        "Return 3 to 8 useful regions when visible. Avoid one full-image box.",
        "Return only the JSON list. No markdown or explanation.",
    ])
    inference_image = alg._ttp_resize_pil_for_qwen(
        pil_image, 1024, 1_048_576)
    raw = await _qwen_chat(
        qwen_vl_model,
        prompt,
        inference_image,
        max_new_tokens=1024,
        temperature=0.0,
        seed=0,
    )
    boxes = alg._ttp_qwen_bbox_items(raw, image_width, image_height)
    raw_count = len(boxes)
    boxes, expanded = alg._ttp_expand_single_large_qwen_bbox(
        boxes, image_width, image_height, int(max_tiles))
    paint_mask = alg._ttp_decode_interactive_paint_mask(
        paint_mask_payload, image_width, image_height)
    paint_items, paint_masks = alg._ttp_paint_mask_to_items(
        paint_mask, image_width, image_height)
    if not boxes and not paint_items:
        snippet = alg._ttp_compact_text(str(raw).replace("\n", " "), 300)
        raise RuntimeError(
            f"QwenVL3 Auto Tile did not return bbox JSON. Raw: {snippet}")
    layout = alg._ttp_boxes_to_auto_layout(
        boxes + paint_items,
        image_width,
        image_height,
        default_pad=int(default_pad),
        default_blend=int(default_blend),
        object_padding=int(object_padding),
        mask_expand=int(mask_expand),
        max_tiles=int(max_tiles),
        include_background=False,
        allow_object_overlap=bool(allow_object_overlap),
        masks=[Image.new("L", (image_width, image_height), 0) for _ in boxes]
        + paint_masks,
    )
    note = " Expanded one large region into detail tiles." if expanded else ""
    return layout, (
        f"QwenVL3 created {len(boxes)} tile region(s) from {raw_count} "
        f"detected object(s) and {len(paint_items)} painted region(s).{note}")


async def _interactive_crop(
    image,
    layout_json,
    default_pad=128,
    default_blend=64,
    include_full_image=False,
    round_to=8,
    auto_detect_mode="none",
    auto_detect_request=0,
    auto_prompt="person, face, hands, eyes, text, foreground object, important object",
    allow_object_overlap=True,
    auto_object_padding=96,
    auto_mask_expand=16,
    auto_max_tiles=16,
    auto_paint_mask="",
    source_image=None,
    vision_model=None,
    vision_conditioning=None,
    clip=None,
    qwen_vl_model=None,
    unique_id=None,
    **_kwargs,
):
    if source_image is not None:
        source = await _raw_image(source_image, "source_image")
        pil_image = alg.tensor2pil(source[0].unsqueeze(0)).convert("RGB")
    else:
        pil_image = await _load_input_pil(str(image or ""))
    image_width, image_height = pil_image.size
    mode = str(auto_detect_mode or "none").strip().lower()
    has_paint = bool(str(auto_paint_mask or "").strip())
    ok = True
    message = "manual layout"
    if int(auto_detect_request or 0) > 0 and (mode != "none" or has_paint):
        try:
            if mode == "qwenvl3":
                layout_json, message = await _qwen_auto_layout(
                    pil_image, qwen_vl_model, str(auto_prompt or ""),
                    int(default_pad), int(default_blend),
                    int(auto_object_padding), int(auto_mask_expand),
                    int(auto_max_tiles), bool(allow_object_overlap),
                    str(auto_paint_mask or ""),
                )
            elif mode == "sam3.1":
                layout_json, message = await _sam3_auto_layout(
                    pil_image, vision_model, vision_conditioning, clip,
                    str(auto_prompt or ""), int(default_pad),
                    int(default_blend), int(auto_object_padding),
                    int(auto_mask_expand), int(auto_max_tiles),
                    bool(allow_object_overlap), str(auto_paint_mask or ""),
                )
            elif has_paint:
                layout_json, message = alg._ttp_run_paint_mask_auto_layout(
                    pil_image, str(auto_paint_mask or ""), int(default_pad),
                    int(default_blend), int(auto_object_padding),
                    int(auto_mask_expand), int(auto_max_tiles),
                    bool(allow_object_overlap),
                )
            else:
                raise ValueError(f"Unsupported auto detect mode: {mode}")
        except Exception as exc:
            ok = False
            message = str(exc)

    normalized = alg._ttp_interactive_layout_with_defaults(
        layout_json, int(default_pad), int(default_blend),
        bool(include_full_image))
    tiles_meta = alg._ttp_parse_smart_tile_layout(
        normalized, image_width, image_height)
    tile_set = alg._ttp_crop_smart_tile_set_from_meta(
        pil_image, [dict(tile) for tile in tiles_meta], int(round_to))
    tiles, tile_meta, positions, preview = alg._ttp_crop_smart_tiles_from_meta(
        pil_image, tiles_meta, int(round_to))
    ui = {
        "ttp_smart_tile_layout": [{
            "node_id": str(unique_id or ""),
            "ok": bool(ok),
            "message": str(message),
            "layout_json": normalized,
        }]
    }
    return {
        "result": (
            alg.pil2tensor(pil_image), tiles, tile_set, tile_meta,
            positions, preview, normalized,
        ),
        "ui": ui,
    }


async def _interactive_fingerprint(image="", source_image=None, **kwargs):
    digest = None
    if source_image is None and str(image or "").strip():
        asset = await _ctx().assets.resolve("input", str(image).strip())
        digest = await _ctx().assets.digest(asset)
    payload = {
        "image": str(image or ""),
        "image_digest": digest,
        "source_ref": getattr(source_image, "id", None),
        **{
            key: value for key, value in kwargs.items()
            if key not in {"prompt", "extra_pnginfo"}
        },
    }
    return json.dumps(payload, sort_keys=True, default=str)


async def _interactive_validate(image="", source_image=None, **_kwargs):
    if source_image is not None or not str(image or "").strip():
        return True
    return True if await _ctx().assets.exists("input", str(image).strip()) else (
        f"Invalid input image asset: {image}")


_interactive_crop.fingerprint_inputs = _interactive_fingerprint
_interactive_crop.validate_inputs = _interactive_validate


def _sheet_for_qwen(images: list[Image.Image], labels: list[str]) -> Image.Image:
    if len(images) == 1:
        return images[0]
    sheet = alg._ttp_make_contact_sheet(images, labels, thumb_size=256, columns=2)
    if sheet is None:
        raise ValueError("Qwen visual context contains no images")
    return sheet


async def _prompt_builder(
    reference_image_mode="contact_sheet",
    system_prompt="",
    tile_instruction="",
    global_prompt="",
    prompt_merge_mode="global_plus_label_plus_caption",
    output_language="english",
    max_new_tokens=512,
    temperature=0.2,
    prompt_preset="tile_img2img_prompt",
    qwen_max_side=768,
    qwen_max_pixels=786432,
    use_tile_cache=True,
    global_negative="",
    qwen_seed=123,
    tile_set=None,
    reference_image=None,
    qwen_vl_model=None,
    **kwargs,
):
    raw_tile_set = await materialize(tile_set)
    raw_reference = (
        await _raw_image(reference_image, "reference_image")
        if reference_image is not None else None)
    if qwen_vl_model is None:
        return alg.TTP_Smart_Tile_QwenVL_Prompt_Set_Builder_Experimental().build_prompt_set(
            tile_set=raw_tile_set,
            reference_image_mode=reference_image_mode,
            system_prompt=system_prompt,
            tile_instruction=tile_instruction,
            global_prompt=global_prompt,
            prompt_merge_mode=prompt_merge_mode,
            output_language=output_language,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            prompt_preset=prompt_preset,
            qwen_max_side=qwen_max_side,
            qwen_max_pixels=qwen_max_pixels,
            use_tile_cache=use_tile_cache,
            global_negative=global_negative,
            qwen_seed=qwen_seed,
            reference_image=raw_reference,
            qwen_vl_model=None,
            **kwargs,
        )

    _clip, model_file = _qwen_model_parts(qwen_vl_model)
    tile_images, _tile_meta, _tiles = alg._ttp_validate_tile_set(raw_tile_set)
    if not 1 <= len(tile_images) <= _MAX_BATCH:
        raise ValueError(f"prompt builder supports 1..{_MAX_BATCH} tiles")
    next_tile_set = alg._ttp_clone_tile_set(raw_tile_set)
    next_tiles = next_tile_set["tile_meta"]["tiles"]

    reference_image_mode = str(reference_image_mode or "contact_sheet")
    if reference_image_mode not in {"none", "first_message", "every_tile", "contact_sheet"}:
        reference_image_mode = "contact_sheet"
    prompt_preset = str(prompt_preset or "tile_img2img_prompt")
    if prompt_preset not in alg._TTP_QWENVL_PRESETS:
        prompt_preset = "tile_img2img_prompt"
    if prompt_merge_mode not in {
        "caption_only", "global_plus_caption", "global_plus_label_plus_caption",
    }:
        prompt_merge_mode = "global_plus_label_plus_caption"
    if output_language not in {"english", "chinese", "bilingual"}:
        output_language = "english"
    max_new_tokens = alg._ttp_safe_int(max_new_tokens, 512, 32, 4096)
    temperature = alg._ttp_safe_float(temperature, 0.2, 0.0, 2.0)
    qwen_max_side = alg._ttp_safe_int(qwen_max_side, 768, 0, 4096)
    qwen_max_pixels = alg._ttp_safe_int(
        qwen_max_pixels, 786432, 0, 16_777_216)
    qwen_seed = alg._ttp_safe_int(qwen_seed, 123, 0, 2_147_483_647)

    preset = alg._TTP_QWENVL_PRESETS[prompt_preset]
    effective_system = str(system_prompt or "").strip() or preset["system"]
    effective_instruction = str(tile_instruction or "").strip() or preset["instruction"]
    reference_pil = None
    if raw_reference is not None:
        reference_pil = alg._ttp_resize_pil_for_qwen(
            alg._ttp_image_tensor_to_pil(raw_reference[0]),
            qwen_max_side,
            qwen_max_pixels,
        )

    contact_sheet = None
    if reference_image_mode == "contact_sheet":
        contact_images = [
            alg._ttp_resize_pil_for_qwen(
                alg._ttp_image_tensor_to_pil(image), 256, 0)
            for image in tile_images
        ]
        contact_sheet = _sheet_for_qwen(
            contact_images,
            [f"{index}: {tile.get('label', tile.get('name', 'tile'))}"
             for index, tile in enumerate(next_tiles)],
        )
        contact_sheet = alg._ttp_resize_pil_for_qwen(
            contact_sheet, qwen_max_side, qwen_max_pixels)

    reference_context = ""
    if reference_image_mode == "first_message" and reference_pil is not None:
        reference_context = await _qwen_chat(
            qwen_vl_model,
            "\n".join([
                effective_system,
                "Analyze this reference for identity, style, lighting, material, "
                "camera perspective, and global consistency. Return one concise paragraph.",
            ]),
            reference_pil,
            max_new_tokens=min(512, max_new_tokens),
            temperature=temperature,
            seed=qwen_seed,
        )
        reference_context = alg._ttp_compact_text(reference_context, 900)
    elif contact_sheet is not None:
        reference_context = await _qwen_chat(
            qwen_vl_model,
            "\n".join([
                effective_system,
                "Summarize this labeled tile contact sheet's global subject, style, "
                "lighting, identity, and relation to the whole image in under 100 words.",
            ]),
            contact_sheet,
            max_new_tokens=min(512, max_new_tokens),
            temperature=temperature,
            seed=qwen_seed,
        )
        reference_context = alg._ttp_compact_text(reference_context, 1000)

    language_hint = {
        "english": "Write prompt fields in English.",
        "chinese": "Write prompt fields in Chinese.",
        "bilingual": "Write prompt fields in English and Chinese.",
    }[output_language]
    prompt_records = []
    for index, (image_tensor, tile) in enumerate(zip(
        tile_images, next_tiles, strict=True,
    )):
        tile_pil = alg._ttp_resize_pil_for_qwen(
            alg._ttp_image_tensor_to_pil(image_tensor),
            qwen_max_side,
            qwen_max_pixels,
        )
        visual_images = [tile_pil]
        visual_labels = [f"tile {index}"]
        if reference_image_mode == "every_tile" and reference_pil is not None:
            visual_images.insert(0, reference_pil)
            visual_labels.insert(0, "reference")
        elif contact_sheet is not None:
            visual_images.insert(0, contact_sheet)
            visual_labels.insert(0, "global contact sheet")
        visual = _sheet_for_qwen(visual_images, visual_labels)
        visual = alg._ttp_resize_pil_for_qwen(
            visual, qwen_max_side, qwen_max_pixels)
        user_prompt = "\n".join([
            effective_system,
            effective_instruction,
            language_hint,
            "Return one compact JSON object only with label, caption, prompt, negative.",
            "Caption under 45 words, prompt under 75, negative under 30.",
            f"Tile index: {index}. Existing label: "
            f"{tile.get('label', tile.get('name', 'tile'))}.",
            f"Global prompt: {alg._ttp_compact_text(global_prompt, 900)}",
            f"Global negative: {alg._ttp_compact_text(global_negative, 600)}",
            f"Reference context: {alg._ttp_compact_text(reference_context, 700)}",
        ])
        tile_hash = alg._ttp_tile_hash(image_tensor)
        cache_key = json.dumps({
            "model": model_file,
            "tile": index,
            "hash": tile_hash,
            "prompt": user_prompt,
            "seed": qwen_seed,
            "temperature": temperature,
            "visual_size": visual.size,
        }, sort_keys=True, ensure_ascii=False)
        cached = _PROMPT_CACHE.get(cache_key) if bool(use_tile_cache) else None
        raw = cached.get("raw", "") if cached else await _qwen_chat(
            qwen_vl_model,
            user_prompt,
            visual,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            seed=qwen_seed,
        )
        retry_raw = cached.get("retry_raw", "") if cached else ""
        if cached:
            record = dict(cached["record"])
        else:
            try:
                parsed = alg._ttp_parse_qwen_tile_record(raw, index)
            except RuntimeError:
                retry_raw = await _qwen_chat(
                    qwen_vl_model,
                    "Return strict JSON only: "
                    '{"label":"...","caption":"...","prompt":"...","negative":"..."}.',
                    visual,
                    max_new_tokens=max_new_tokens,
                    temperature=0.0,
                    seed=qwen_seed,
                )
                parsed = alg._ttp_parse_qwen_tile_record(retry_raw, index)
            caption = parsed.get("caption", "")
            positive = parsed.get("prompt", "")
            negative = parsed.get("negative", global_negative) or global_negative
            label = parsed.get(
                "label", tile.get("label", tile.get("name", "tile")))
            if not positive:
                positive, negative = alg._ttp_compose_tile_prompt(
                    {**tile, "label": label}, caption, global_prompt,
                    negative, prompt_merge_mode)
            record = {
                "label": str(label),
                "caption": str(caption),
                "prompt": str(positive),
                "negative": str(negative),
            }
            if bool(use_tile_cache):
                if len(_PROMPT_CACHE) >= 4096:
                    _PROMPT_CACHE.pop(next(iter(_PROMPT_CACHE)))
                _PROMPT_CACHE[cache_key] = {
                    "raw": raw, "retry_raw": retry_raw,
                    "record": dict(record),
                }
        tile.update({
            **record,
            "prompt_tag": tile.get(
                "prompt_tag", f"tile_{index}_{record['label']}"),
            "prompt_source": "qwen_vl_local",
            "prompt_preset": prompt_preset,
            "qwen_model": model_file,
            "tile_hash": tile_hash,
            "qwen_input_size": [visual.width, visual.height],
            "qwen_cache": "hit" if cached else "miss",
        })
        if raw:
            tile["qwen_raw"] = raw
        if retry_raw:
            tile["qwen_raw_retry"] = retry_raw
        prompt_records.append({
            "index": index,
            "name": tile.get("name", f"tile_{index}"),
            "label": tile["label"],
            "caption": tile["caption"],
            "prompt": tile["prompt"],
            "negative": tile["negative"],
            "prompt_tag": tile["prompt_tag"],
        })

    prompt_set_json = json.dumps({
        "type": "ttp_smart_tile_prompt_set",
        "mode": "qwen_vl_local",
        "reference_image_mode": reference_image_mode,
        "prompt_preset": prompt_preset,
        "qwen_seed": qwen_seed,
        "model_file": model_file,
        "qwen_max_side": qwen_max_side,
        "qwen_max_pixels": qwen_max_pixels,
        "tiles": prompt_records,
    }, ensure_ascii=False, indent=2)
    summary = "\n".join([
        f"mode=qwen_vl_local model={model_file or 'unknown'} "
        f"tiles={len(prompt_records)}",
        *[
            f"{item['index']}: {item['label']} -> {item['prompt']}"
            for item in prompt_records
        ],
    ])
    return next_tile_set, prompt_set_json, summary


async def _sam3_auto_layout(
    pil_image: Image.Image,
    vision_model: Any,
    vision_conditioning: Any,
    clip: Any,
    auto_prompt: str,
    default_pad: int,
    default_blend: int,
    object_padding: int,
    mask_expand: int,
    max_tiles: int,
    allow_object_overlap: bool,
    paint_mask_payload: str,
):
    if not isinstance(vision_model, sdk.ModelRef):
        raise ValueError(
            "Connect an official SAM3/SAM3.1 model to vision_model before "
            "inference.")
    max_tiles = max(1, min(_MAX_BATCH, int(max_tiles)))
    prompt_source = "external conditioning"
    conditioning = vision_conditioning
    if conditioning is None:
        if not isinstance(clip, sdk.ClipRef):
            raise ValueError(
                "Connect CLIP to this node, or connect SAM3 text conditioning "
                "to vision_conditioning, before SAM3 text-prompt inference.")
        terms = alg._ttp_split_prompt_terms(auto_prompt)
        if not terms:
            terms = ["foreground object"]
        per_prompt_max = max(1, max_tiles // len(terms))
        # SAM3's own text encoder accepts the conventional ``term:N`` form and
        # emits the multi-prompt conditioning metadata. Prompt splitting and
        # the per-prompt budget remain this pack's policy.
        conditioning = await clip.encode(
            ", ".join(f"{term}:{per_prompt_max}" for term in terms))
        prompt_source = "internal auto_prompt CLIP encode"
    if not isinstance(conditioning, sdk.CondRef):
        raise TypeError("vision_conditioning must be a CONDITIONING reference")

    image_ref = await sdk.ImageRef._from_raw(
        alg.pil2tensor(pil_image.convert("RGB")))
    masks_ref, bboxes = await vision_model.ground_image(
        image_ref,
        conditioning,
        threshold=0.5,
        refine_iterations=2,
        individual_masks=True,
        max_detections=max_tiles,
    )
    masks = await masks_ref.raw()
    image_width, image_height = pil_image.size
    paint_mask = alg._ttp_decode_interactive_paint_mask(
        paint_mask_payload, image_width, image_height)
    paint_items, paint_masks = alg._ttp_paint_mask_to_items(
        paint_mask, image_width, image_height)
    detected_items = alg._ttp_flatten_bboxes(bboxes)
    detected_masks = alg._ttp_mask_tensor_to_pil_list(
        masks, image_width, image_height)
    while len(detected_masks) < len(detected_items):
        detected_masks.append(Image.new("L", (image_width, image_height), 0))
    layout_json = alg._ttp_boxes_to_auto_layout(
        detected_items + paint_items,
        image_width,
        image_height,
        default_pad=int(default_pad),
        default_blend=int(default_blend),
        object_padding=int(object_padding),
        mask_expand=int(mask_expand),
        max_tiles=max_tiles,
        include_background=False,
        allow_object_overlap=bool(allow_object_overlap),
        masks=detected_masks + paint_masks,
    )
    paint_note = (
        f", plus {len(paint_items)} paint mask region(s)" if paint_items else "")
    return layout_json, (
        f"SAM3 inference created an auto tile layout from "
        f"{len(detected_items)} detected object(s){paint_note}, {prompt_source}.")


def _bounded_session_key(value: Any) -> str:
    key = str(value or "default")
    if not key or len(key) > 128 or "\x00" in key:
        raise ValueError("session_id must contain 1..128 non-NUL characters")
    return key


def _store_loop_session(key: str, value: dict[str, Any]) -> None:
    if key not in _LOOP_SESSIONS and len(_LOOP_SESSIONS) >= 64:
        _LOOP_SESSIONS.pop(next(iter(_LOOP_SESSIONS)))
    _LOOP_SESSIONS[key] = value


async def _loop_source(
    tile_set,
    session_id="default",
    restart_request=0,
    loop_request=0,
    clip=None,
    unique_id=None,
    **_kwargs,
):
    del loop_request
    tile_set = await _structured(tile_set)
    tile_images, _tile_meta, tiles_info = alg._ttp_validate_tile_set(tile_set)
    if not 1 <= len(tile_images) <= _MAX_BATCH:
        raise ValueError(f"loop source supports 1..{_MAX_BATCH} tiles")
    key = _bounded_session_key(session_id)
    fingerprint = alg._ttp_tile_set_fingerprint(tile_set)
    session = _LOOP_SESSIONS.get(key)
    should_restart = (
        session is None
        or session.get("fingerprint") != fingerprint
        or int(session.get("restart_request", -1)) != int(restart_request)
    )
    if should_restart:
        session = {
            "fingerprint": fingerprint,
            "restart_request": int(restart_request),
            "source_node_id": str(unique_id or "")[:128],
            "source_tile_set": alg._ttp_clone_tile_set(tile_set),
            "processed_tile_set": alg._ttp_clone_tile_set(tile_set),
            "index": 0,
            "done": False,
        }
        _store_loop_session(key, session)

    count = len(tile_images)
    index = alg._ttp_clamp(
        int(session.get("index", 0)), 0, max(0, count - 1))
    done = bool(session.get("done", False))
    if done:
        index = count - 1
    current = tiles_info[index]
    task = {
        "type": "ttp_smart_tile_task",
        "session_id": key,
        "source_node_id": str(
            unique_id or session.get("source_node_id", ""))[:128],
        "index": int(index),
        "count": int(count),
        "done": bool(done),
        "tile_meta": dict(current),
    }
    prompt = str(current.get("prompt", ""))
    negative = str(current.get("negative", ""))
    if clip is None:
        # No CLIP means no conditioning output.  Returning ``None`` preserves
        # that semantic without manufacturing an empty host value merely to
        # cross the wire (which would otherwise require the raw tier).
        positive_conditioning: Any = None
        negative_conditioning: Any = None
    else:
        if not isinstance(clip, sdk.ClipRef):
            raise TypeError("clip must be a CLIP reference")
        positive_conditioning = await clip.encode(prompt)
        negative_conditioning = await clip.encode(negative)
    status = "done" if done else f"tile {index + 1}/{count}"
    ui = {"ttp_smart_tile_loop": [{
        "source_node_id": task["source_node_id"],
        "session_id": key,
        "index": int(index),
        "count": int(count),
        "done": bool(done),
        "message": status,
    }]}
    return {
        "result": (
            tile_images[index], task, int(index), int(count), bool(done),
            status, prompt, negative, str(current.get("caption", "")),
            str(current.get("label", current.get("name", ""))),
            str(current.get("prompt_tag", "")),
            positive_conditioning, negative_conditioning,
        ),
        "ui": ui,
    }


async def _loop_source_fingerprint(
    tile_set=None, session_id="default", restart_request=0,
    loop_request=0, clip=None, **_kwargs,
):
    tile_set = await _structured(tile_set)
    key = _bounded_session_key(session_id)
    session = _LOOP_SESSIONS.get(key, {})
    fingerprint = (
        alg._ttp_tile_set_fingerprint(tile_set)
        if isinstance(tile_set, dict) else None)
    return json.dumps({
        "session_id": key,
        "restart_request": int(restart_request),
        "loop_request": int(loop_request),
        "fingerprint": fingerprint,
        "index": session.get("index", 0),
        "done": session.get("done", False),
        "clip": isinstance(clip, sdk.ClipRef),
    }, sort_keys=True)


_loop_source.fingerprint_inputs = _loop_source_fingerprint


async def _loop_collect(tile_task, processed_image, **_kwargs):
    task = await _structured(tile_task)
    if not isinstance(task, dict) or task.get("type") != "ttp_smart_tile_task":
        raise ValueError("tile_task must come from TTP Smart Tile Loop Source")
    session_id = _bounded_session_key(task.get("session_id", "default"))
    session = _LOOP_SESSIONS.get(session_id)
    if session is None:
        raise ValueError(f"Smart Tile loop session not found: {session_id}")
    processed = await _raw_image(processed_image, "processed_image")
    processed_tile_set = session["processed_tile_set"]
    tile_images, _tile_meta, _tiles_info = alg._ttp_validate_tile_set(
        processed_tile_set)
    count = len(tile_images)
    index = alg._ttp_clamp(
        int(task.get("index", 0)), 0, max(0, count - 1))
    if not bool(task.get("done", False)) and count > 0:
        tile_images[index] = alg._ttp_first_image_tensor(processed)
    next_index = index + 1
    done = next_index >= count
    session["index"] = min(next_index, max(0, count - 1))
    session["done"] = bool(done)
    status = "done" if done else f"next tile {next_index + 1}/{count}"
    ui = {"ttp_smart_tile_loop": [{
        "source_node_id": str(task.get("source_node_id", ""))[:128],
        "session_id": session_id,
        "index": int(session["index"]),
        "count": int(count),
        "done": bool(done),
        "message": status,
    }]}
    return {
        "result": (
            alg._ttp_clone_tile_set(processed_tile_set), bool(done),
            int(next_index), status,
        ),
        "ui": ui,
    }


async def _loop_collect_fingerprint(tile_task=None, **_kwargs):
    task = await _structured(tile_task)
    session_id = (
        _bounded_session_key(task.get("session_id", "default"))
        if isinstance(task, dict) else "")
    session = _LOOP_SESSIONS.get(session_id, {})
    return json.dumps({
        "session_id": session_id,
        "task_index": task.get("index") if isinstance(task, dict) else None,
        "session_index": session.get("index", 0),
        "done": session.get("done", False),
    }, sort_keys=True)


_loop_collect.fingerprint_inputs = _loop_collect_fingerprint


async def _upscale_tile(
    image,
    scale=2.0,
    round_to=8,
    resampling="lanczos",
    max_megapixels=0.0,
    use_upscale_model=True,
    upscale_model=None,
    **_kwargs,
):
    if not 0.1 <= float(scale) <= 16.0:
        raise ValueError("scale must be in [0.1, 16]")
    if not 1 <= int(round_to) <= 256:
        raise ValueError("round_to must be in [1, 256]")
    if str(resampling) not in {
        "lanczos", "bicubic", "bilinear", "area", "nearest-exact", "nearest",
    }:
        raise ValueError("unsupported resampling method")
    if not 0.0 <= float(max_megapixels) <= 64.0:
        raise ValueError("max_megapixels must be in [0, 64]")
    source = await _raw_image(image)
    tile = alg._ttp_first_image_tensor(source)
    width, height = alg._ttp_image_tensor_size(tile[0])
    target_width, target_height, capped = alg._ttp_smart_upscale_target_size(
        width, height, float(scale), int(round_to), float(max_megapixels))
    if target_width * target_height > _MAX_IMAGE_PIXELS:
        raise ValueError("upscale target exceeds 67,108,864 pixels")
    model_used = bool(use_upscale_model and upscale_model is not None)
    if model_used:
        if not isinstance(upscale_model, sdk.UpscaleModelRef):
            raise TypeError("upscale_model must be an UPSCALE_MODEL reference")
        tile_ref = await sdk.ImageRef._from_raw(tile)
        upscaled_ref = await upscale_model.upscale(tile_ref)
        upscaled = await _raw_image(upscaled_ref, "upscaled image")
        if alg._ttp_image_tensor_size(upscaled[0]) != (
            target_width, target_height,
        ):
            upscaled = alg._ttp_resize_image_tensor(
                upscaled, target_width, target_height, str(resampling))
    else:
        upscaled = alg._ttp_resize_image_tensor(
            tile, target_width, target_height, str(resampling))
    scale_x = target_width / max(1, width)
    scale_y = target_height / max(1, height)
    info = (
        f"{width}x{height} -> {target_width}x{target_height} "
        f"requested_scale={float(scale):g} "
        f"effective_scale={scale_x:.4g}x{scale_y:.4g} "
        f"round_to={int(round_to)} max_megapixels={float(max_megapixels):g}"
        f"{' capped' if capped else ''} "
        f"method={'model' if model_used else str(resampling)}")
    return upscaled, info


async def _shape_only_image(value: Any, name: str) -> torch.Tensor:
    if isinstance(value, sdk.ImageRef):
        height, width = await value.spatial_shape()
        batch = await value.batch_size()
        if not 1 <= int(batch) <= _MAX_BATCH:
            raise ValueError(f"{name} batch exceeds {_MAX_BATCH}")
        return torch.empty(
            (int(batch), int(height), int(width), 3), device="meta")
    return _checked_image_tensor(value, name)


async def _output_size_estimate(
    tile_set, scale_strategy="median", source_image=None, done=None, **_kwargs,
):
    tile_set = await _structured(tile_set)
    if not isinstance(tile_set, dict):
        raise TypeError("tile_set must be a structured Smart Tile value")
    shape_tile_set = alg._ttp_clone_tile_set(tile_set)
    shape_tile_set["tile_images"] = [
        await _shape_only_image(value, f"tile_images[{index}]")
        for index, value in enumerate(tile_set.get("tile_images", []))
    ]
    shape_source = (
        await _shape_only_image(source_image, "source_image")
        if source_image is not None else None)
    return alg.TTP_Smart_Tile_Output_Size_Estimate_Experimental().estimate_output_size(
        shape_tile_set,
        scale_strategy=str(scale_strategy),
        source_image=shape_source,
        done=done,
    )


async def _save_final_image(
    images, done=True, filename_prefix="TTP_Smart_Tile",
    prompt=None, extra_pnginfo=None, **_kwargs,
):
    if not bool(done):
        return {"ui": {"images": []}}
    raw = await _raw_image(images, "images")
    last = await sdk.ImageRef._from_raw(raw[-1:].contiguous())
    extra = dict(extra_pnginfo) if isinstance(extra_pnginfo, dict) else {}
    if prompt is not None:
        extra.setdefault("prompt", prompt)
    saved = await _ctx().output.save_images(
        last,
        filename_prefix=str(filename_prefix or "TTP_Smart_Tile"),
        compress_level=4,
        save_metadata=True,
        extra_metadata=extra,
    )
    return {"ui": saved}


def _checked_video_latent(value: Any, name: str = "latent") -> dict[str, Any]:
    if not isinstance(value, dict) or "samples" not in value:
        raise TypeError(f"{name} must contain samples")
    samples = value["samples"]
    if not isinstance(samples, torch.Tensor) or samples.ndim != 5:
        raise ValueError(f"{name} samples must be [B,C,T,H,W]")
    if int(samples.numel()) > _MAX_TILE_PIXELS * 4:
        raise ValueError(f"{name} exceeds the secure tensor bound")
    if min(map(int, samples.shape)) < 1:
        raise ValueError(f"{name} dimensions must be non-empty")
    return value


async def _vae_scale_factors(vae: Any) -> tuple[int, int]:
    if not isinstance(vae, sdk.VaeRef):
        raise TypeError("vae must be a VAE reference")
    formula = await vae.downscale_index_formula()
    if (not isinstance(formula, (tuple, list)) or len(formula) != 3
            or int(formula[1]) < 1 or int(formula[2]) < 1):
        raise ValueError("VAE does not publish a valid downscale index formula")
    return int(formula[1]), int(formula[2])


def _center_resize_bhwc(
    pixels: torch.Tensor, target_height: int, target_width: int,
) -> torch.Tensor:
    pixels = _checked_image_tensor(pixels)
    source_height, source_width = map(int, pixels.shape[1:3])
    target_aspect = target_width / max(1, target_height)
    source_aspect = source_width / max(1, source_height)
    if source_aspect > target_aspect:
        crop_width = max(1, int(round(source_height * target_aspect)))
        left = max(0, (source_width - crop_width) // 2)
        pixels = pixels[:, :, left:left + crop_width]
    elif source_aspect < target_aspect:
        crop_height = max(1, int(round(source_width / target_aspect)))
        top = max(0, (source_height - crop_height) // 2)
        pixels = pixels[:, top:top + crop_height]
    if tuple(map(int, pixels.shape[1:3])) != (target_height, target_width):
        pixels = F.interpolate(
            pixels.movedim(-1, 1),
            size=(target_height, target_width),
            mode="bilinear",
            align_corners=False,
        ).movedim(1, -1)
    return pixels


async def _encode_ltx_image(
    vae: Any, image: Any, target_height: int, target_width: int,
) -> torch.Tensor:
    pixels = await _raw_image(image)
    pixels = _center_resize_bhwc(pixels, target_height, target_width)[..., :3]
    image_ref = await sdk.ImageRef._from_raw(pixels.contiguous())
    encoded_ref = await vae.encode(image_ref)
    encoded = _checked_video_latent(await encoded_ref.value(), "encoded latent")
    return encoded["samples"]


async def _ltx_middle_frame(
    image, position=0.5, strength=1.0, middle_frames=None, **_kwargs,
):
    if not isinstance(image, sdk.ImageRef):
        image = await sdk.ImageRef._from_raw(await _raw_image(image))
    position = float(position)
    strength = float(strength)
    if not 0.0 <= position <= 1.0 or not 0.0 <= strength <= 1.0:
        raise ValueError("position and strength must be in [0, 1]")
    current = await _structured(middle_frames) if middle_frames is not None else None
    frames = [] if current is None else list(current.get("frames", []))
    if len(frames) >= 64:
        raise ValueError("middle_frames supports at most 64 entries")
    frames.append({
        "image": image, "position": position, "strength": strength,
    })
    return ({"frames": frames},)


async def _ltx_first_last(
    vae,
    latent,
    first_strength=1.0,
    last_strength=1.0,
    first_image=None,
    last_image=None,
    middle_frames=None,
    **_kwargs,
):
    first_strength = float(first_strength)
    last_strength = float(last_strength)
    if not 0.0 <= first_strength <= 1.0 or not 0.0 <= last_strength <= 1.0:
        raise ValueError("first_strength and last_strength must be in [0, 1]")
    middle = await _structured(middle_frames) if middle_frames is not None else None
    frames = list(middle.get("frames", [])) if isinstance(middle, dict) else []
    if len(frames) > 64:
        raise ValueError("middle_frames supports at most 64 entries")
    if first_image is None and last_image is None and not frames:
        return (latent,)
    raw_latent = _checked_video_latent(await materialize(latent))
    samples = raw_latent["samples"].clone()
    batch, _channels, latent_frames, latent_height, latent_width = map(
        int, samples.shape)
    height_scale, width_scale = await _vae_scale_factors(vae)
    target_height = latent_height * height_scale
    target_width = latent_width * width_scale
    noise_mask = torch.ones(
        (batch, 1, latent_frames, 1, 1),
        dtype=torch.float32,
        device=samples.device,
    )

    if first_image is not None and first_strength > 0.0:
        encoded = await _encode_ltx_image(
            vae, first_image, target_height, target_width)
        count = min(int(encoded.shape[2]), latent_frames)
        samples[:, :, :count] = encoded[:, :, :count]
        noise_mask[:, :, :count] = 1.0 - first_strength
    if last_image is not None and last_strength > 0.0:
        encoded = await _encode_ltx_image(
            vae, last_image, target_height, target_width)
        count = min(int(encoded.shape[2]), latent_frames)
        samples[:, :, latent_frames - count:] = encoded[:, :, :count]
        noise_mask[:, :, latent_frames - count:] = 1.0 - last_strength
    for frame in frames:
        if not isinstance(frame, dict):
            raise TypeError("each middle frame must be a mapping")
        strength = float(frame.get("strength", 1.0))
        position = float(frame.get("position", 0.5))
        if not 0.0 <= strength <= 1.0 or not 0.0 <= position <= 1.0:
            raise ValueError("middle frame position and strength must be in [0, 1]")
        if strength <= 0.0:
            continue
        encoded = await _encode_ltx_image(
            vae, frame.get("image"), target_height, target_width)
        count = min(int(encoded.shape[2]), latent_frames)
        index = round(position * (latent_frames - 1))
        index = max(0, min(index, latent_frames - count))
        samples[:, :, index:index + count] = encoded[:, :, :count]
        current = noise_mask[:, :, index:index + count]
        noise_mask[:, :, index:index + count] = torch.minimum(
            current, torch.full_like(current, 1.0 - strength))
    return ({"samples": samples, "noise_mask": noise_mask},)


async def _ltx_context(
    previous_video,
    vae,
    latent,
    context_latent_frames,
    context_strength=1.0,
    **_kwargs,
):
    context_latent_frames = int(context_latent_frames)
    context_strength = float(context_strength)
    if not 2 <= context_latent_frames <= 20:
        raise ValueError("context_latent_frames must be in [2, 20]")
    if not 0.0 <= context_strength <= 1.0:
        raise ValueError("context_strength must be in [0, 1]")
    previous = await _raw_image(previous_video, "previous_video")
    raw_latent = _checked_video_latent(await materialize(latent))
    samples = raw_latent["samples"].clone()
    batch, _channels, latent_frames, latent_height, latent_width = map(
        int, samples.shape)
    height_scale, width_scale = await _vae_scale_factors(vae)
    target_height = latent_height * height_scale
    target_width = latent_width * width_scale
    required_frames = (context_latent_frames - 1) * 8 + 1
    context = previous[max(0, int(previous.shape[0]) - required_frames):]
    encoded = await _encode_ltx_image(
        vae, context, target_height, target_width)
    count = min(int(encoded.shape[2]), latent_frames)
    samples[:, :, :count] = encoded[:, :, :count]
    noise_mask = torch.ones(
        (batch, 1, latent_frames, 1, 1),
        dtype=torch.float32,
        device=samples.device,
    )
    noise_mask[:, :, :count] = 1.0 - context_strength
    return ({"samples": samples, "noise_mask": noise_mask},)


async def _teacache_sampler(
    noise,
    guider,
    sampler,
    sigmas,
    latent_image,
    speedup="Fast (1.6x)",
    enable_custom_speed=False,
    custom_speed=1.0,
    **_kwargs,
):
    thresholds = {
        "Original (1x)": 0.0,
        "Fast (1.6x)": 0.1,
        "Faster (2.1x)": 0.15,
        "Ultra Fast (3.2x)": 0.25,
        "Shapeless Fast (4.4x)": 0.35,
    }
    if bool(enable_custom_speed):
        custom_speed = float(custom_speed)
        if not 1.0 <= custom_speed <= 4.4:
            raise ValueError("Custom speed must be between 1.0 and 4.4")
        threshold = float(np.interp(
            custom_speed,
            [1.0, 1.6, 2.1, 3.2, 4.4],
            [0.0, 0.1, 0.15, 0.25, 0.35],
        ))
    else:
        if speedup not in thresholds:
            raise ValueError(f"Unsupported speedup option: {speedup}")
        threshold = thresholds[speedup]
    if not isinstance(sigmas, sdk.SigmasRef):
        raise TypeError("sigmas must be a SIGMAS reference")
    steps = await sigmas.steps()
    return await _ctx().sample(
        latent_image,
        steps,
        guider=guider,
        sampler=sampler,
        sigmas=sigmas,
        noise=noise,
        cache={
            "kind": "easycache",
            "reuse_threshold": threshold,
            "start_percent": 0.0,
            "end_percent": 1.0,
        },
        return_denoised=True,
    )


_HANDLERS: dict[str, Any] = {
    node_id: _legacy_handler(node_id, klass, method, raw=raw)
    for node_id, (klass, method, raw) in _LEGACY.items()
}
_HANDLERS.update({
    "TTP_condtobatch": _conditioning_batch,
    "TTP_condsetarea_merge": _conditioning_areas,
    "TTP_condsetarea_merge_test": _conditioning_areas_grouped,
    "TTP_Smart_Tile_Interactive_Crop_Experimental": _interactive_crop,
    "TTP_QwenVL3_Local_Loader_Experimental": _qwen_loader,
    "TTP_Smart_Tile_QwenVL_Prompt_Set_Builder_Experimental": _prompt_builder,
    "TTP_Smart_Tile_Loop_Source_Experimental": _loop_source,
    "TTP_Smart_Tile_Loop_Collect_Experimental": _loop_collect,
    "TTP_Smart_Tile_Image_Upscale_Prep_Experimental": _upscale_tile,
    "TTP_Smart_Tile_Output_Size_Estimate_Experimental": _output_size_estimate,
    "TTP_Smart_Tile_Save_Final_Image_Experimental": _save_final_image,
    "LTXVMiddleFrame_TTP": _ltx_middle_frame,
    "LTXVFirstLastFrameControl_TTP": _ltx_first_last,
    "LTXVContext_TTP": _ltx_context,
    "TeaCacheHunyuanVideoSampler": _teacache_sampler,
})


_RAW_IDS = {
    "TTPlanet_Tile_Preprocessor_Simple",
    "TTP_Image_Tile_Batch",
    "TTP_Image_Assy",
    "TTP_Tile_image_size",
    "TTP_Expand_And_Mask",
    "TTP_Smart_Tile_Set_Preview_Experimental",
    "TTP_Smart_Tile_Assemble_Experimental",
    "TTP_condtobatch",
    "TTP_condsetarea_merge",
    "TTP_condsetarea_merge_test",
    "TTP_Smart_Tile_Interactive_Crop_Experimental",
    "TTP_Smart_Tile_QwenVL_Prompt_Set_Builder_Experimental",
    "TTP_Smart_Tile_Loop_Collect_Experimental",
    "TTP_Smart_Tile_Image_Upscale_Prep_Experimental",
    "TTP_Smart_Tile_Save_Final_Image_Experimental",
    "LTXVFirstLastFrameControl_TTP",
    "LTXVContext_TTP",
}
_MODEL_IDS = {
    "TTP_Smart_Tile_Interactive_Crop_Experimental",
    "TTP_QwenVL3_Local_Loader_Experimental",
    "TTP_Smart_Tile_QwenVL_Prompt_Set_Builder_Experimental",
    "TTP_Smart_Tile_Loop_Source_Experimental",
    "TTP_Smart_Tile_Image_Upscale_Prep_Experimental",
    "LTXVFirstLastFrameControl_TTP",
    "LTXVContext_TTP",
}


def _permissions(node_id: str) -> tuple[str, ...]:
    permissions: list[str] = []
    if node_id in _RAW_IDS:
        permissions.append("raw")
    if node_id in _MODEL_IDS:
        permissions.append("models")
    if node_id == "TTP_Smart_Tile_Interactive_Crop_Experimental":
        permissions.append("assets")
    if node_id == "TTP_Smart_Tile_Save_Final_Image_Experimental":
        permissions.append("output")
    if node_id == "TeaCacheHunyuanVideoSampler":
        permissions.append("sample")
    return tuple(permissions)


NODE_CLASS_MAPPINGS = {
    node_id: bind_node(node_id, _HANDLERS[node_id], permissions=_permissions(node_id))
    for node_id in SCHEMAS
}
NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: value["schema"]["attrs"]["display_name"]
    for node_id, value in SCHEMAS.items()
}


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
