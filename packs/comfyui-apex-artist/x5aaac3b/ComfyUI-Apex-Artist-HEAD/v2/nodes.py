"""Secure adapters for Apex Artist's tensor, prompt, and LoRA nodes."""
from __future__ import annotations

from typing import Any

import torch

from comfy_api.latest import io, sdk

from .apex_blur import ApexBlur as _BlurImplementation
from .apex_depth_to_normal import ApexDepthToNormal as _DepthImplementation
from .apex_layer_blend import ApexLayerBlend as _BlendImplementation
from .apex_prompt import ApexPromptPreset as _PromptImplementation
from .apex_sharpen import ApexSharpen as _SharpenImplementation


_MAX_ELEMENTS = 134_217_728
_PROMPT_INPUTS = _PromptImplementation.INPUT_TYPES()


def _bounded_tensor(value: torch.Tensor, label: str) -> torch.Tensor:
    if not isinstance(value, torch.Tensor):
        raise TypeError(f"{label} must be a tensor")
    if value.numel() > _MAX_ELEMENTS:
        raise ValueError(f"{label} exceeds the bounded raw-compute limit")
    return value


async def _image_value(value: sdk.ImageRef, label: str) -> torch.Tensor:
    return _bounded_tensor(await value.raw(), label)


async def _mask_value(value: sdk.MaskRef | None, label: str) -> torch.Tensor | None:
    if value is None:
        return None
    return _bounded_tensor(await value.raw(), label)


async def _image_output(value: torch.Tensor) -> sdk.ImageRef:
    return await sdk.ImageRef._from_raw(_bounded_tensor(value, "output image"))


class ApexDepthToNormal(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)
    SDK_REQUIRED_WEIGHTS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ApexDepthToNormal",
            display_name="Apex Depth to Normal",
            category="Apex Artist/Image/Composite",
            inputs=[
                io.Image.Input("depth_map"),
                io.Float.Input("strength", default=12.0, min=0.1, max=30.0, step=0.1),
                io.Boolean.Input("invert", default=False, optional=True),
                io.Boolean.Input("auto_invert_depth", default=False, optional=True),
                io.Float.Input("blur", default=0.0, min=0.0, max=3.0, step=0.1, optional=True),
                io.Float.Input("enhance_details", default=0.0, min=0.0, max=3.0, step=0.1, optional=True),
            ],
            outputs=[
                io.Image.Output("normal_map", display_name="normal_map"),
                io.String.Output("info", display_name="info"),
            ],
        )

    @classmethod
    async def execute(
        cls,
        depth_map: sdk.ImageRef,
        strength: float,
        invert: bool = False,
        auto_invert_depth: bool = False,
        blur: float = 0.0,
        enhance_details: float = 0.0,
    ) -> io.NodeOutput:
        image = await _image_value(depth_map, "depth map")
        with torch.no_grad():
            result, info = _DepthImplementation().depth_to_normal(
                image, strength, invert, auto_invert_depth, blur, enhance_details
            )
        return io.NodeOutput(await _image_output(result), info)


class ApexBlur(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)
    SDK_REQUIRED_WEIGHTS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ApexBlur",
            display_name="Apex Blur",
            category="Apex Artist/Image/Filters",
            inputs=[
                io.Image.Input("image"),
                io.Combo.Input(
                    "blur_type",
                    options=[
                        "gaussian", "strong_gaussian", "box", "motion",
                        "radial", "surface", "lens", "spin", "zoom", "depth",
                    ],
                    default="gaussian",
                ),
                io.Float.Input("radius", default=10.0, min=0.5, max=100.0, step=0.1),
                io.Float.Input("strength", default=1.0, min=0.0, max=1.0, step=0.01),
                io.Float.Input("angle", default=0.0, min=-180.0, max=180.0, step=1.0, optional=True),
                io.Float.Input("center_x", default=0.5, min=0.0, max=1.0, step=0.01, optional=True),
                io.Float.Input("center_y", default=0.5, min=0.0, max=1.0, step=0.01, optional=True),
                io.Float.Input("edge_threshold", default=0.1, min=0.01, max=1.0, step=0.01, optional=True),
                io.Mask.Input("mask", optional=True),
                io.Mask.Input("depth", optional=True),
            ],
            outputs=[
                io.Image.Output("blurred_image", display_name="blurred_image"),
                io.String.Output("blur_info", display_name="blur_info"),
            ],
        )

    @classmethod
    async def execute(
        cls,
        image: sdk.ImageRef,
        blur_type: str,
        radius: float,
        strength: float,
        angle: float = 0.0,
        center_x: float = 0.5,
        center_y: float = 0.5,
        edge_threshold: float = 0.1,
        mask: sdk.MaskRef | None = None,
        depth: sdk.MaskRef | None = None,
    ) -> io.NodeOutput:
        raw_image = await _image_value(image, "image")
        raw_mask = await _mask_value(mask, "mask")
        raw_depth = await _mask_value(depth, "depth")
        with torch.no_grad():
            result, info = _BlurImplementation().apply_blur(
                raw_image, blur_type, radius, strength, angle, center_x,
                center_y, edge_threshold, raw_mask, raw_depth,
            )
        return io.NodeOutput(await _image_output(result), info)


class ApexSharpen(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)
    SDK_REQUIRED_WEIGHTS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ApexSharpen",
            display_name="Apex Sharpen",
            category="Apex Artist/Image/Filters",
            inputs=[
                io.Image.Input("image"),
                io.Combo.Input(
                    "algorithm",
                    options=[
                        "Unsharp Mask", "High Pass Filter", "Edge Enhancement",
                        "Structure Aware", "Laplacian Sharpen",
                        "Multi-Scale Sharpen", "Luminance Sharpen",
                        "Detail Enhancement",
                    ],
                    default="Unsharp Mask",
                ),
                io.Float.Input("strength", default=1.0, min=0.0, max=5.0, step=0.1),
                io.Float.Input("radius", default=1.0, min=0.1, max=10.0, step=0.1, optional=True),
                io.Float.Input("threshold", default=0.0, min=0.0, max=1.0, step=0.01, optional=True),
                io.Boolean.Input("preserve_highlights", default=True, optional=True),
                io.Boolean.Input("preserve_shadows", default=True, optional=True),
                io.Float.Input("edge_protection", default=0.0, min=0.0, max=1.0, step=0.1, optional=True),
                io.Float.Input("fine_detail", default=1.0, min=0.0, max=3.0, step=0.1, optional=True),
                io.Mask.Input("mask", optional=True),
            ],
            outputs=[
                io.Image.Output("sharpened_image", display_name="sharpened_image"),
                io.String.Output("sharpen_info", display_name="sharpen_info"),
            ],
        )

    @classmethod
    async def execute(
        cls,
        image: sdk.ImageRef,
        algorithm: str,
        strength: float,
        radius: float = 1.0,
        threshold: float = 0.0,
        preserve_highlights: bool = True,
        preserve_shadows: bool = True,
        edge_protection: float = 0.0,
        fine_detail: float = 1.0,
        mask: sdk.MaskRef | None = None,
    ) -> io.NodeOutput:
        raw_image = await _image_value(image, "image")
        raw_mask = await _mask_value(mask, "mask")
        with torch.no_grad():
            result, info = _SharpenImplementation().apply_sharpening(
                raw_image, algorithm, strength, radius, threshold,
                preserve_highlights, preserve_shadows, edge_protection,
                fine_detail, raw_mask,
            )
        return io.NodeOutput(await _image_output(result), info)


class ApexLayerBlend(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)
    SDK_REQUIRED_WEIGHTS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ApexLayerBlend",
            display_name="Apex Layer Blend",
            category="Apex Artist/Image/Composite",
            inputs=[
                io.Image.Input("base_image"),
                io.Image.Input("overlay_image"),
                io.Combo.Input(
                    "blend_mode",
                    options=[
                        "normal", "dissolve", "darken", "multiply",
                        "color_burn", "linear_burn", "darker_color", "lighten",
                        "screen", "color_dodge", "linear_dodge", "lighter_color",
                        "overlay", "soft_light", "hard_light", "vivid_light",
                        "linear_light", "pin_light", "hard_mix", "difference",
                        "exclusion", "subtract", "divide", "hue", "saturation",
                        "color", "luminosity",
                    ],
                    default="normal",
                ),
                io.Float.Input("opacity", default=1.0, min=0.0, max=1.0, step=0.01),
                io.Mask.Input("mask", optional=True),
            ],
            outputs=[
                io.Image.Output("blended_image", display_name="blended_image"),
                io.String.Output("blend_info", display_name="blend_info"),
            ],
        )

    @classmethod
    async def execute(
        cls,
        base_image: sdk.ImageRef,
        overlay_image: sdk.ImageRef,
        blend_mode: str,
        opacity: float,
        mask: sdk.MaskRef | None = None,
    ) -> io.NodeOutput:
        base = await _image_value(base_image, "base image")
        overlay = await _image_value(overlay_image, "overlay image")
        raw_mask = await _mask_value(mask, "mask")
        with torch.no_grad():
            result, info = _BlendImplementation().blend_layers(
                base, overlay, blend_mode, opacity, raw_mask
            )
        return io.NodeOutput(await _image_output(result), info)


def _prompt_options(name: str) -> list[str]:
    return list(_PROMPT_INPUTS["optional"][name][0])


class ApexPromptPreset(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    SDK_REQUIRED_WEIGHTS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ApexPromptPreset",
            display_name="Apex Prompt",
            category="Apex Artist/Text",
            inputs=[
                io.String.Input("input_text", multiline=True, default=""),
                io.Int.Input("seed", default=0, min=0, max=0xFFFFFFFFFFFFFFFF),
                io.Combo.Input("environment_preset", options=_prompt_options("environment_preset"), default="Disabled", optional=True),
                io.Combo.Input("lighting_preset", options=_prompt_options("lighting_preset"), default="Disabled", optional=True),
                io.Combo.Input("style_preset", options=_prompt_options("style_preset"), default="Disabled", optional=True),
                io.Combo.Input("camera_lens_preset", options=_prompt_options("camera_lens_preset"), default="Disabled", optional=True),
            ],
            outputs=[
                io.String.Output("combined_prompt", display_name="combined_prompt"),
                io.String.Output("environment_text", display_name="environment_text"),
                io.String.Output("lighting_text", display_name="lighting_text"),
                io.String.Output("style_text", display_name="style_text"),
                io.String.Output("camera_lens_text", display_name="camera_lens_text"),
            ],
        )

    @classmethod
    async def execute(
        cls,
        input_text: str,
        seed: int,
        environment_preset: str = "Disabled",
        lighting_preset: str = "Disabled",
        style_preset: str = "Disabled",
        camera_lens_preset: str = "Disabled",
    ) -> io.NodeOutput:
        values = _PromptImplementation().combine_prompts(
            input_text, seed, environment_preset, lighting_preset,
            style_preset, camera_lens_preset,
        )
        return io.NodeOutput(*values)


class ApexLoraLoader(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets",)
    SDK_REQUIRED_WEIGHTS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ApexLoraLoader",
            display_name="Apex LoRA Loader",
            category="Apex Artist/Models",
            description=(
                "Load one catalogued LoRA with a shared model and optional CLIP "
                "strength. Filesystem paths and model weights remain host-owned."
            ),
            inputs=[
                io.Model.Input("model"),
                io.Combo.Input(
                    "lora_name",
                    options=[],
                    remote=io.RemoteOptions(route="/models/loras", refresh_button=True),
                ),
                io.Float.Input("strength", default=1.0, min=-10.0, max=10.0, step=0.01),
                io.Clip.Input("clip", optional=True),
            ],
            outputs=[
                io.Model.Output("model", display_name="model"),
                io.Clip.Output("clip", display_name="clip"),
            ],
        )

    @classmethod
    async def execute(
        cls,
        model: sdk.ModelRef,
        lora_name: str,
        strength: float,
        clip: sdk.ClipRef | None = None,
    ) -> io.NodeOutput:
        if float(strength) == 0.0:
            return io.NodeOutput(model, clip)
        asset = await sdk.ctx().assets.resolve("loras", str(lora_name))
        patched_model, patched_clip = await model.apply_lora(
            asset,
            clip,
            float(strength),
            float(strength) if clip is not None else 0.0,
        )
        return io.NodeOutput(patched_model, patched_clip)


NODE_CLASS_MAPPINGS = {
    "ApexDepthToNormal": ApexDepthToNormal,
    "ApexLayerBlend": ApexLayerBlend,
    "ApexBlur": ApexBlur,
    "ApexSharpen": ApexSharpen,
    "ApexPromptPreset": ApexPromptPreset,
    "ApexLoraLoader": ApexLoraLoader,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ApexDepthToNormal": "Apex Depth to Normal",
    "ApexLayerBlend": "Apex Layer Blend",
    "ApexBlur": "Apex Blur",
    "ApexSharpen": "Apex Sharpen",
    "ApexPromptPreset": "Apex Prompt",
    "ApexLoraLoader": "Apex LoRA Loader",
}


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
