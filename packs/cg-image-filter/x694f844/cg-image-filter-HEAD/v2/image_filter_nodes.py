"""Secure Nodes V2 implementations of cg-image-filter's interactive nodes."""
from __future__ import annotations

import hashlib
from io import BytesIO
import json
import math
from pathlib import PurePosixPath
import random
from typing import Any

import numpy as np
from PIL import Image
import torch

from comfy_api.latest import io, sdk

from ._secure_runtime import (
    image_value,
    latent_value,
    mask_value,
    output_image,
    output_latent,
    output_mask,
)
from .image_filter_messaging import (
    InteractionTimeout,
    bounded_extras,
    bounded_text,
    interrupt,
    preview_identity,
    preview_images,
    request,
    safe_sound,
)


async def _request_until_final(
    kind: str,
    payload: dict[str, Any],
    timeout: int | float,
) -> Any:
    """Restart the closed interaction when the user resets its timer."""
    while True:
        response = await request(kind, payload, timeout)
        if isinstance(response, dict) and set(response) == {"reset"}:
            if response["reset"] is not True:
                raise TypeError("interaction reset must be true")
            continue
        return response


def _response_extras(response: Any, defaults: tuple[str, str, str]) -> tuple[str, str, str]:
    if not isinstance(response, dict) or "extras" not in response:
        return defaults
    values = bounded_extras(response["extras"])
    return values[0], values[1], values[2]


def _tensor_hash(hasher: Any, value: torch.Tensor | None) -> None:
    if value is None:
        hasher.update(b"none\0")
        return
    tensor = value.detach().cpu().contiguous()
    hasher.update(str(tuple(tensor.shape)).encode("ascii"))
    hasher.update(b"\0")
    hasher.update(str(tensor.dtype).encode("ascii"))
    hasher.update(b"\0")
    try:
        hasher.update(tensor.numpy().tobytes(order="C"))
    except TypeError:
        hasher.update(tensor.to(torch.float32).numpy().tobytes(order="C"))


def _mask_state_key(graph_id: Any, unique_id: Any) -> str:
    identity = f"{graph_id}\0{unique_id}".encode("utf-8", "replace")
    return "cg-mask:" + hashlib.sha256(identity).hexdigest()


def _mask_input_fingerprint(
    image: torch.Tensor,
    mask: torch.Tensor | None,
    *values: Any,
) -> str:
    digest = hashlib.sha256()
    _tensor_hash(digest, image)
    _tensor_hash(digest, mask)
    digest.update(json.dumps(values, ensure_ascii=False, default=str).encode("utf-8"))
    return digest.hexdigest()


def _stored_state(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        state = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(state, dict):
        return None
    fingerprint = state.get("fingerprint")
    shape = state.get("shape")
    identity = state.get("mask")
    extras = state.get("extras")
    if (
        not isinstance(fingerprint, str)
        or len(fingerprint) != 64
        or not isinstance(shape, list)
        or len(shape) != 3
        or any(type(value) is not int or value < 1 for value in shape)
        or not isinstance(identity, dict)
    ):
        return None
    try:
        normalized = preview_identity(identity)
        checked_extras = bounded_extras(extras)
    except (TypeError, ValueError):
        return None
    return {
        "fingerprint": fingerprint,
        "shape": shape,
        "mask": normalized,
        "extras": checked_extras,
    }


def _logical_name(identity: dict[str, str]) -> tuple[str, str]:
    normalized = preview_identity(identity)
    path = PurePosixPath(normalized["subfolder"]) / normalized["filename"]
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("mask identity escapes its catalogue")
    return normalized["type"], path.as_posix()


async def _read_mask(
    identity: dict[str, str],
    *,
    width: int,
    height: int,
) -> torch.Tensor:
    folder, name = _logical_name(identity)
    asset = await sdk.ctx().assets.resolve(folder, name)
    data = await sdk.ctx().assets.read_bytes(asset)
    if not isinstance(data, (bytes, bytearray, memoryview)) or len(data) > 16 * 1024 * 1024:
        raise ValueError("edited mask exceeds the 16 MiB bound")
    with Image.open(BytesIO(bytes(data))) as opened:
        if opened.width < 1 or opened.height < 1 or opened.width * opened.height > 67_108_864:
            raise ValueError("edited mask dimensions are outside the safe bound")
        image = opened.convert("L")
        if image.size != (width, height):
            image = image.resize((width, height), Image.Resampling.NEAREST)
        array = np.asarray(image, dtype=np.float32).copy() / 255.0
    return torch.from_numpy(array).unsqueeze(0)


class FilterNodeBase:
    SDK_REFS = True

    @classmethod
    def fingerprint_inputs(cls, **_kwargs):
        return random.random()

    @staticmethod
    def parse_picklist(pick_list: str, batch: int = 1) -> list[int]:
        if not pick_list:
            return []
        if batch < 1:
            raise ValueError("cannot select from an empty image batch")
        return [int(value.strip()) % batch for value in pick_list.split(",")]

    @staticmethod
    def stack_tensor(value: torch.Tensor | None, indices: list[int]) -> torch.Tensor | None:
        if value is None:
            return None
        try:
            return torch.stack([value[index] for index in indices])
        except IndexError:
            print(f"cg-image-filter: index error selecting {indices}")
            return None

    @staticmethod
    def stack_latent(value: dict[str, Any] | None, indices: list[int]) -> dict[str, Any] | None:
        if value is None:
            return None
        samples = value.get("samples")
        if not isinstance(samples, torch.Tensor):
            raise TypeError("latents must contain a tensor named samples")
        selected = FilterNodeBase.stack_tensor(samples, indices)
        return None if selected is None else {"samples": selected}


class ImageFilter(FilterNodeBase, io.ComfyNode):
    SDK_PERMISSIONS = ("raw", "ui", "ui.interact", "execution.interrupt")

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Image Filter",
            display_name="Image Filter",
            category="image_filter",
            inputs=[
                io.Image.Input("images"),
                io.Latent.Input("latents", optional=True, tooltip="optional"),
                io.Mask.Input("masks", optional=True, tooltip="optional"),
                io.Int.Input("timeout", default=600, min=1, max=1_000_000, tooltip="timeout in seconds"),
                io.Combo.Input("ontimeout", options=["send none", "send all", "send first", "send last"]),
                io.String.Input("tip", default="", optional=True),
                io.String.Input("extra1", default="", optional=True),
                io.String.Input("extra2", default="", optional=True),
                io.String.Input("extra3", default="", optional=True),
                io.Int.Input("pick_list_start", advanced=True, optional=True, default=0, tooltip="The index of the first image (normally 0 or 1)"),
                io.String.Input("pick_list", advanced=True, optional=True, default="", tooltip="If a comma separated list of integers is provided, the images with these indices will be selected automatically."),
                io.Int.Input("video_frames", advanced=True, optional=True, default=1, tooltip="Treat each block of n images as a video"),
                io.String.Input("audiofile", advanced=True, optional=True, default="", tooltip="Bundled sound name (ding.mp3, beep.mp3, or honk.mp3)"),
                io.String.Input("graph_id", default=""),
            ],
            outputs=[
                io.Image.Output("images", display_name="images"),
                io.Latent.Output("latents", display_name="latents"),
                io.Mask.Output("masks", display_name="masks"),
                io.String.Output("extra1", display_name="extra1"),
                io.String.Output("extra2", display_name="extra2"),
                io.String.Output("extra3", display_name="extra3"),
                io.String.Output("indexes", display_name="indexes"),
            ],
        )

    @classmethod
    def fingerprint_inputs(cls, pick_list: str = "", **_kwargs):
        try:
            parsed = cls.parse_picklist(pick_list)
            if parsed:
                return ",".join(str(value) for value in parsed)
        except (TypeError, ValueError):
            pass
        return random.random()

    @classmethod
    async def execute(
        cls,
        images,
        latents=None,
        masks=None,
        timeout=600,
        ontimeout="send none",
        graph_id="",
        tip="",
        extra1="",
        extra2="",
        extra3="",
        pick_list_start=0,
        pick_list="",
        video_frames=1,
        audiofile="",
        **_kwargs,
    ) -> io.NodeOutput:
        image_tensor = await image_value(images)
        latent_dict = await latent_value(latents)
        mask_tensor = await mask_value(masks)
        if image_tensor is None or image_tensor.ndim != 4 or image_tensor.shape[0] < 1:
            raise ValueError("Image Filter needs a non-empty IMAGE batch")

        batch = int(image_tensor.shape[0])
        frames = max(1, int(video_frames))
        if frames > batch:
            frames = 1
        groups = max(1, math.ceil(batch / frames))
        try:
            selected = cls.parse_picklist(str(pick_list), batch)
        except (TypeError, ValueError) as error:
            print(f"cg-image-filter: {error} parsing pick_list; opening chooser")
            selected = []

        out_extras = (
            bounded_text(extra1), bounded_text(extra2), bounded_text(extra3)
        )
        if not selected:
            all_same = all(torch.equal(image_tensor[index], image_tensor[0]) for index in range(1, batch))
            display = await sdk.ctx().ui.preview_images(images)
            payload = {
                "variant": "cg-image-filter.image-choice-v1",
                "images": preview_images(display),
                "count": groups,
                "allsame": bool(all_same),
                "extras": list(out_extras),
                "tip": bounded_text(tip, maximum=16_384),
                "video_frames": frames,
                "graph_id": bounded_text(graph_id),
                "sound": safe_sound(audiofile),
            }
            try:
                response = await _request_until_final(
                    "image-choice", payload, timeout)
            except InteractionTimeout:
                policies = {
                    "send none": [],
                    "send all": list(range(groups)),
                    "send first": [0],
                    "send last": [groups - 1],
                }
                selected = policies.get(str(ontimeout), [])
            else:
                if not isinstance(response, dict):
                    raise TypeError("image-choice response must be an object")
                if response.get("cancelled"):
                    await interrupt("Image Filter selection was cancelled")
                values = response.get("selected", [])
                if not isinstance(values, list) or len(values) > groups:
                    raise TypeError("image-choice selection must be a bounded index list")
                selected = []
                for value in values:
                    if type(value) is not int or not 0 <= value < groups:
                        raise ValueError("image-choice returned an invalid index")
                    if value not in selected:
                        selected.append(value)
                out_extras = _response_extras(response, out_extras)

        if not selected:
            await interrupt("Image Filter produced no selection")

        if frames > 1:
            selected = [
                index
                for group in selected
                for index in range(group * frames, min((group + 1) * frames, batch))
            ]

        image_out = cls.stack_tensor(image_tensor, selected)
        latent_out = cls.stack_latent(latent_dict, selected)
        mask_out = cls.stack_tensor(mask_tensor, selected)
        offset = int(pick_list_start)
        indexes = ",".join(str(index + offset) for index in selected)
        return io.NodeOutput(
            await output_image(image_out),
            await output_latent(latent_out),
            await output_mask(mask_out),
            *out_extras,
            indexes,
        )


class TextImageFilter(FilterNodeBase, io.ComfyNode):
    SDK_PERMISSIONS = ("raw", "ui", "ui.interact", "execution.interrupt")

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Text Image Filter",
            display_name="Text Image Filter",
            category="image_filter",
            inputs=[
                io.Image.Input("image"),
                io.String.Input("text", default=""),
                io.Int.Input("timeout", default=600, min=1, max=1_000_000, tooltip="timeout in seconds"),
                io.Mask.Input("mask", optional=True, tooltip="optional"),
                io.String.Input("tip", default="", optional=True),
                io.String.Input("extra1", default="", optional=True),
                io.String.Input("extra2", default="", optional=True),
                io.String.Input("extra3", default="", optional=True),
                io.Int.Input("textareaheight", default=150, min=30, max=500),
                io.String.Input("audiofile", advanced=True, optional=True, default="", tooltip="Bundled sound name (ding.mp3, beep.mp3, or honk.mp3)"),
                io.String.Input("graph_id", default=""),
            ],
            outputs=[
                io.Image.Output("images", display_name="images"),
                io.String.Output("text", display_name="text"),
                io.String.Output("extra1", display_name="extra1"),
                io.String.Output("extra2", display_name="extra2"),
                io.String.Output("extra3", display_name="extra3"),
            ],
        )

    @classmethod
    async def execute(
        cls,
        image,
        text,
        timeout,
        graph_id,
        extra1="",
        extra2="",
        extra3="",
        mask=None,
        tip="",
        textareaheight=150,
        audiofile="",
        **_kwargs,
    ) -> io.NodeOutput:
        image_tensor = await image_value(image)
        if image_tensor is None:
            image_tensor = torch.zeros((1, 64, 64, 3), dtype=torch.float32)
            image = await output_image(image_tensor)
        if image_tensor.ndim != 4 or image_tensor.shape[0] < 1:
            raise ValueError("Text Image Filter needs a non-empty IMAGE batch")
        extras = (bounded_text(extra1), bounded_text(extra2), bounded_text(extra3))
        display = await sdk.ctx().ui.preview_images(image)
        payload: dict[str, Any] = {
            "variant": "cg-image-filter.text-edit-v1",
            "images": preview_images(display),
            "text": bounded_text(text, maximum=64 * 1024),
            "extras": list(extras),
            "tip": bounded_text(tip, maximum=16_384),
            "textareaheight": max(30, min(int(textareaheight), 500)),
            "graph_id": bounded_text(graph_id),
            "sound": safe_sound(audiofile),
        }
        if mask is not None:
            mask_display = await sdk.ctx().ui.preview_mask(mask)
            payload["mask_images"] = preview_images(mask_display)
        try:
            response = await _request_until_final(
                "prompt-await", payload, timeout)
        except InteractionTimeout:
            return io.NodeOutput(image, str(text), *extras)
        if not isinstance(response, dict):
            raise TypeError("text-edit response must be an object")
        if response.get("cancelled"):
            await interrupt("Text Image Filter edit was cancelled")
        edited = bounded_text(response.get("text", text), maximum=64 * 1024)
        return io.NodeOutput(image, edited, *_response_extras(response, extras))


class MaskImageFilter(FilterNodeBase, io.ComfyNode):
    SDK_PERMISSIONS = (
        "raw", "ui", "ui.interact", "execution.interrupt", "assets", "storage",
    )

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Mask Image Filter",
            display_name="Mask Image Filter",
            category="image_filter",
            inputs=[
                io.Image.Input("image"),
                io.Int.Input("timeout", default=600, min=1, max=1_000_000, tooltip="timeout in seconds"),
                io.Combo.Input("if_no_mask", options=["cancel", "send blank"], default="send blank"),
                io.Combo.Input("if_inputs_unchanged", options=["Run normally", "Start with last output", "Resend last output", "Always start with last output"], default="Run normally"),
                io.Mask.Input("mask", optional=True, tooltip="optional"),
                io.String.Input("tip", default="", optional=True),
                io.String.Input("extra1", default="", optional=True),
                io.String.Input("extra2", default="", optional=True),
                io.String.Input("extra3", default="", optional=True),
                io.String.Input("audiofile", advanced=True, optional=True, default="", tooltip="Bundled sound name (ding.mp3, beep.mp3, or honk.mp3)"),
                io.String.Input("graph_id", default=""),
            ],
            hidden=[io.Hidden.unique_id],
            outputs=[
                io.Image.Output("image", display_name="image"),
                io.Mask.Output("mask", display_name="mask"),
                io.String.Output("extra1", display_name="extra1"),
                io.String.Output("extra2", display_name="extra2"),
                io.String.Output("extra3", display_name="extra3"),
            ],
        )

    @classmethod
    async def execute(
        cls,
        image,
        timeout,
        if_no_mask,
        graph_id,
        if_inputs_unchanged="Run normally",
        mask=None,
        audiofile="",
        extra1="",
        extra2="",
        extra3="",
        tip="",
        unique_id="",
        **_kwargs,
    ) -> io.NodeOutput:
        image_tensor = await image_value(image)
        input_mask = await mask_value(mask)
        if image_tensor is None or image_tensor.ndim != 4 or image_tensor.shape[0] < 1:
            raise ValueError("Mask Image Filter needs a non-empty IMAGE batch")
        _, height, width, _ = image_tensor.shape
        if width * height > 67_108_864 or width > 16_384 or height > 16_384:
            raise ValueError("Mask Image Filter image is too large for the bounded editor")
        extras = (bounded_text(extra1), bounded_text(extra2), bounded_text(extra3))
        fingerprint = _mask_input_fingerprint(
            image_tensor,
            input_mask,
            int(timeout),
            str(if_no_mask),
            str(graph_id),
            str(audiofile),
            *extras,
            str(tip),
        )
        state_key = _mask_state_key(graph_id, unique_id)
        state = _stored_state(await sdk.ctx().storage.get(state_key))
        same_inputs = state is not None and state["fingerprint"] == fingerprint
        same_shape = state is not None and state["shape"] == [int(image_tensor.shape[0]), height, width]

        initial_mask = input_mask
        if state is not None and same_shape and (
            str(if_inputs_unchanged) == "Always start with last output"
            or (same_inputs and str(if_inputs_unchanged) in {"Start with last output", "Resend last output"})
        ):
            initial_mask = await _read_mask(state["mask"], width=width, height=height)
            extras = tuple(state["extras"])
            if same_inputs and str(if_inputs_unchanged) == "Resend last output":
                return io.NodeOutput(
                    image,
                    await output_mask(initial_mask),
                    *extras,
                )

        image_display = await sdk.ctx().ui.preview_images(image)
        payload: dict[str, Any] = {
            "variant": "cg-image-filter.mask-edit-v1",
            "image": preview_images(image_display)[0],
            "extras": list(extras),
            "tip": bounded_text(tip, maximum=16_384),
        }
        sound = safe_sound(audiofile)
        if sound is not None:
            payload["sound"] = sound
        if initial_mask is not None:
            normalized_mask = initial_mask
            if normalized_mask.ndim == 2:
                normalized_mask = normalized_mask.unsqueeze(0)
            mask_ref = await output_mask(normalized_mask[:1])
            mask_display = await sdk.ctx().ui.preview_mask(mask_ref)
            payload["initial_mask"] = preview_images(mask_display)[0]

        timed_out = False
        try:
            response = await _request_until_final(
                "mask-edit", payload, timeout)
        except InteractionTimeout:
            timed_out = True
            response = {"cancelled": False}
        if not isinstance(response, dict):
            raise TypeError("mask-edit response must be an object")
        if response.get("cancelled"):
            await interrupt("Mask Image Filter edit was cancelled")

        identity = response.get("mask")
        if identity is None:
            edited_mask = (
                initial_mask.clone()
                if timed_out and initial_mask is not None
                else torch.zeros_like(image_tensor[..., 0])
            )
            stored_identity = None
        else:
            stored_identity = preview_identity(identity)
            edited_mask = await _read_mask(stored_identity, width=width, height=height)
        if str(if_no_mask) == "cancel" and not torch.any(edited_mask != 0):
            await interrupt("Mask Image Filter received no painted mask")

        out_extras = _response_extras(response, extras)
        if stored_identity is not None:
            await sdk.ctx().storage.set(
                state_key,
                json.dumps({
                    "fingerprint": fingerprint,
                    "shape": [int(image_tensor.shape[0]), height, width],
                    "mask": stored_identity,
                    "extras": list(out_extras),
                }, ensure_ascii=False, separators=(",", ":")),
            )
        return io.NodeOutput(image, await output_mask(edited_mask), *out_extras)
