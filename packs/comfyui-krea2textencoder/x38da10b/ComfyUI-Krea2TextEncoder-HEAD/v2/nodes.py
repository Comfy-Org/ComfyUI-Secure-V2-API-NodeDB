"""Secure V2 Krea 2 vision-aware text conditioning."""

from __future__ import annotations

import math
import re
from typing import Any

import torch
import torch.nn.functional as F

from comfy_api.latest import ComfyExtension, io, sdk


KREA2_SYSTEM_DEFAULT = (
    "Describe the image by detailing the color, shape, size, texture, quantity, "
    "text, spatial relationships of the objects and background:"
)
KREA2_INSTRUCT_SYSTEM = (
    "Describe the key features of the reference image (color, shape, size, "
    "texture, objects, background), then explain how the user's instruction "
    "should combine with or alter it, and generate a new image meeting the "
    "instruction while staying consistent with the reference where appropriate:"
)

MAX_REFERENCES = 16
MAX_TEXT_BYTES = 64 * 1024
MAX_IMAGE_DIMENSION = 8192
MAX_IMAGE_ELEMENTS = 268_435_456
MAX_MASK_ELEMENTS = 67_108_864


def _bounded_text(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if len(value.encode("utf-8")) > MAX_TEXT_BYTES:
        raise ValueError(f"{name} is too large")
    return value


def _validate_image(value: Any, name: str) -> torch.Tensor:
    if not isinstance(value, torch.Tensor) or value.ndim != 4:
        raise TypeError(f"{name} must be a BHWC tensor")
    batch, height, width, channels = map(int, value.shape)
    if not 1 <= batch <= 64:
        raise ValueError(f"{name} batch must be in [1, 64]")
    if (
        not 1 <= height <= MAX_IMAGE_DIMENSION
        or not 1 <= width <= MAX_IMAGE_DIMENSION
        or not 3 <= channels <= 4
    ):
        raise ValueError(f"{name} has unsupported dimensions")
    if value.numel() > MAX_IMAGE_ELEMENTS:
        raise ValueError(f"{name} is too large")
    return value


def _validate_mask(value: Any, name: str) -> torch.Tensor:
    if not isinstance(value, torch.Tensor) or value.ndim not in (2, 3, 4):
        raise TypeError(f"{name} must be a 2D, BHW, or B1HW tensor")
    if value.numel() > MAX_MASK_ELEMENTS:
        raise ValueError(f"{name} is too large")
    if any(int(size) < 1 or int(size) > MAX_IMAGE_DIMENSION for size in value.shape[-2:]):
        raise ValueError(f"{name} has unsupported dimensions")
    return value


def crop_to_mask(
    image: torch.Tensor,
    mask: torch.Tensor | None,
    padding: float = 0.0,
) -> torch.Tensor:
    """Match the pinned pack's union-mask bounding-box crop exactly."""
    if mask is None:
        return image
    if mask.dim() == 2:
        mask = mask.unsqueeze(0)
    elif mask.dim() == 4:
        mask = mask.reshape(-1, mask.shape[-2], mask.shape[-1])

    height, width = int(image.shape[1]), int(image.shape[2])
    if tuple(mask.shape[-2:]) != (height, width):
        mask = F.interpolate(
            mask.unsqueeze(1), size=(height, width), mode="bilinear")[:, 0]

    presence = (mask > 0.5).any(dim=0)
    if not bool(presence.any()):
        return image
    rows = torch.where(torch.any(presence, dim=1))[0]
    columns = torch.where(torch.any(presence, dim=0))[0]
    y0, y1 = int(rows[0]), int(rows[-1])
    x0, x1 = int(columns[0]), int(columns[-1])
    if padding > 0.0:
        pad_x = round(padding * width)
        pad_y = round(padding * height)
        x0 = max(0, x0 - pad_x)
        x1 = min(width - 1, x1 + pad_x)
        y0 = max(0, y0 - pad_y)
        y1 = min(height - 1, y1 + pad_y)
    return image[:, y0:y1 + 1, x0:x1 + 1, :]


def prepare_vision_tensor(
    image: torch.Tensor,
    mask: torch.Tensor | None,
    vision_megapixels: float,
    mask_padding: float,
) -> torch.Tensor:
    cropped = crop_to_mask(image, mask, mask_padding)
    samples = cropped.movedim(-1, 1)
    total = int(vision_megapixels * 1024 * 1024)
    scale_by = min(
        1.0,
        math.sqrt(total / (int(samples.shape[3]) * int(samples.shape[2]))),
    )
    width = max(1, round(int(samples.shape[3]) * scale_by))
    height = max(1, round(int(samples.shape[2]) * scale_by))
    resized = F.interpolate(samples, size=(height, width), mode="area")
    return resized.movedim(1, -1)[..., :3].contiguous()


def build_text(
    system_prompt: str,
    prompt: str,
    image_prompt: str,
    vision_position: str,
) -> tuple[str, str]:
    system = system_prompt.strip() or KREA2_SYSTEM_DEFAULT
    template = (
        "<|im_start|>system\n" + system + "<|im_end|>\n"
        "<|im_start|>user\n{}<|im_end|>\n<|im_start|>assistant\n"
    )
    text = prompt + image_prompt if vision_position == "after prompt" else image_prompt + prompt
    return text, template


class TextEncodeKrea2(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="TextEncodeKrea2",
            display_name="Text Encode (Krea2)",
            category="model/conditioning/krea2",
            description=(
                "Krea2 (K2) text conditioning with optional vision prompting. "
                "Reference images are fed through the Qwen3-VL vision path; an "
                "optional per-image mask crops the image to the masked region. "
                "No VAE is used (Krea2 has no reference-latent pathway)."),
            accept_all_inputs=True,
            inputs=[
                io.Clip.Input("clip"),
                io.String.Input(
                    "prompt", multiline=True, dynamic_prompts=True),
                io.String.Input(
                    "system_prompt", optional=True, force_input=True,
                    tooltip=(
                        "Optional system-instruction input. Wire a text node to "
                        "override how the VLM frames the reference + your "
                        "prompt; leave unconnected to use Krea2's trained "
                        "descriptor (in-distribution). Use an instruct/edit-"
                        "style instruction (see README) to fuse the prompt with "
                        "the image. The node adds the chat-template scaffolding; "
                        "provide just the instruction text.")),
                io.Image.Input("image1", optional=True),
                io.Mask.Input("mask1", optional=True),
                io.Float.Input(
                    "vision_megapixels", optional=True, default=1.0,
                    min=0.1, max=8.0, step=0.1,
                    tooltip=(
                        "Maximum size (in megapixels) for each reference before "
                        "the Qwen3-VL vision encoder. References larger than "
                        "this are downscaled; smaller ones (e.g. a tight mask "
                        "crop) are kept at native size, never upscaled.")),
                io.Float.Input(
                    "mask_padding", optional=True, default=0.0,
                    min=0.0, max=1.0, step=0.02,
                    tooltip=(
                        "Context kept around the mask before cropping, as a "
                        "fraction of the image size added on EACH side. 0 = "
                        "tight crop to the mask; 0.1 = ~10% margin of "
                        "surroundings. Only applies when a mask is connected.")),
                io.Combo.Input(
                    "vision_position", options=["before prompt", "after prompt"],
                    optional=True, default="before prompt",
                    tooltip=(
                        "Where the image (vision) tokens sit in the user turn "
                        "relative to your text. 'before prompt' = image then "
                        "text (default); 'after prompt' = text then image. No "
                        "effect without an image. Experimental.")),
                io.Boolean.Input(
                    "print_prompt", optional=True, default=False,
                    tooltip=(
                        "Print the full assembled prompt sent to the Qwen3-VL "
                        "encoder (system instruction + vision placeholders + "
                        "your text) to the ComfyUI console.")),
            ],
            outputs=[io.Conditioning.Output(display_name="CONDITIONING")],
        )

    @classmethod
    async def execute(
        cls,
        clip: sdk.ClipRef,
        prompt: str,
        system_prompt: str = KREA2_SYSTEM_DEFAULT,
        image1: sdk.ImageRef | None = None,
        mask1: sdk.MaskRef | None = None,
        vision_megapixels: float = 1.0,
        mask_padding: float = 0.0,
        vision_position: str = "before prompt",
        print_prompt: bool = False,
        **kwargs: Any,
    ) -> io.NodeOutput:
        prompt = _bounded_text(prompt, "prompt")
        system_prompt = _bounded_text(system_prompt, "system_prompt")
        vision_megapixels = float(vision_megapixels)
        mask_padding = float(mask_padding)
        if not math.isfinite(vision_megapixels) or not 0.1 <= vision_megapixels <= 8.0:
            raise ValueError("vision_megapixels must be finite and in [0.1, 8.0]")
        if not math.isfinite(mask_padding) or not 0.0 <= mask_padding <= 1.0:
            raise ValueError("mask_padding must be finite and in [0.0, 1.0]")
        if vision_position not in {"before prompt", "after prompt"}:
            raise ValueError("invalid vision_position")
        if type(print_prompt) is not bool:
            raise TypeError("print_prompt must be a boolean")

        dynamic: dict[str, Any] = {"image1": image1, "mask1": mask1}
        for name, value in kwargs.items():
            if re.fullmatch(r"(?:image|mask)\d+", str(name)) is None:
                raise ValueError(f"unexpected dynamic input {name!r}")
            dynamic[str(name)] = value
        images = {
            int(match.group(1)): value
            for name, value in dynamic.items()
            if value is not None
            and (match := re.fullmatch(r"image(\d+)", name)) is not None
        }
        masks = {
            int(match.group(1)): value
            for name, value in dynamic.items()
            if value is not None
            and (match := re.fullmatch(r"mask(\d+)", name)) is not None
        }
        if any(index < 1 or index > MAX_REFERENCES for index in images | masks):
            raise ValueError(f"reference indexes must be in [1, {MAX_REFERENCES}]")
        if len(images) > MAX_REFERENCES:
            raise ValueError(f"at most {MAX_REFERENCES} references are supported")

        prepared_refs: list[sdk.ImageRef] = []
        ordered = sorted(images)
        for index in ordered:
            image = _validate_image(await images[index].raw(), f"image{index}")
            mask_ref = masks.get(index)
            mask = None
            if mask_ref is not None:
                mask = _validate_mask(await mask_ref.raw(), f"mask{index}")
            prepared = prepare_vision_tensor(
                image, mask, vision_megapixels, mask_padding)
            prepared_refs.append(await sdk.ImageRef._from_raw(prepared))

        if len(ordered) > 1:
            image_prompt = "".join(
                f"Picture {slot}: <|vision_start|><|image_pad|><|vision_end|>"
                for slot in range(1, len(ordered) + 1)
            )
        elif ordered:
            image_prompt = "<|vision_start|><|image_pad|><|vision_end|>"
        else:
            image_prompt = ""
        text, template = build_text(
            system_prompt, prompt, image_prompt, vision_position)
        if print_prompt:
            print("\n========== Text Encode (Krea2) -> Qwen3-VL prompt ==========")
            print(template.replace("{}", text, 1))
            print(f"---- references: {len(prepared_refs)} ----")
            print("===========================================================\n")

        try:
            conditioning = await clip.encode(
                text,
                images=prepared_refs,
                llama_template=template,
            )
        except Exception as exc:
            if prepared_refs and "Float8" in str(exc):
                raise RuntimeError(
                    "Krea2 vision references need a bf16/fp16 Qwen3-VL text "
                    "encoder; the FP8 vision path is unsupported.") from exc
            raise
        return io.NodeOutput(conditioning)


class Krea2SystemPrompt(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Krea2SystemPrompt",
            display_name="Krea2 System Prompt",
            category="model/conditioning/krea2",
            description=(
                "Text node preloaded with an instruct-style system prompt for "
                "Text Encode (Krea2). Wire its output into the encoder's "
                "system_prompt input."),
            inputs=[
                io.String.Input(
                    "text", multiline=True, default=KREA2_INSTRUCT_SYSTEM,
                    tooltip=(
                        "System instruction for Krea2's VLM. Defaults to an "
                        "instruct/edit-style framing that fuses your prompt with "
                        "the reference image. Edit as needed; paste the plain "
                        "descriptor to fall back to default behavior.")),
            ],
            outputs=[io.String.Output(display_name="system_prompt")],
        )

    @classmethod
    def execute(cls, text: str) -> io.NodeOutput:
        return io.NodeOutput(_bounded_text(text, "text"))


NODE_CLASS_MAPPINGS = {
    "TextEncodeKrea2": TextEncodeKrea2,
    "Krea2SystemPrompt": Krea2SystemPrompt,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "TextEncodeKrea2": "Text Encode (Krea2)",
    "Krea2SystemPrompt": "Krea2 System Prompt",
}


class Krea2TextEncoderExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint() -> Krea2TextEncoderExtension:
    return Krea2TextEncoderExtension()


__all__ = [
    "KREA2_INSTRUCT_SYSTEM",
    "KREA2_SYSTEM_DEFAULT",
    "Krea2SystemPrompt",
    "Krea2TextEncoderExtension",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "TextEncodeKrea2",
    "build_text",
    "comfy_entrypoint",
    "crop_to_mask",
    "prepare_vision_tensor",
]
