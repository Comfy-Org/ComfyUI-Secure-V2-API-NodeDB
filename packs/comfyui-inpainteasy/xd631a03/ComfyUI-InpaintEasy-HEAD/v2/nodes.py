"""Secure Nodes V2 conversion of ComfyUI-InpaintEasy."""

from __future__ import annotations

import numpy as np
import torch
import torch.nn.functional as F
from comfy_api.latest import ComfyExtension, io
from PIL import Image

UPSCALE_METHODS = ["nearest-exact", "bilinear", "area", "bicubic", "lanczos"]
CROP_METHODS = [
    "disabled",
    "center",
    "top_left",
    "top_right",
    "bottom_left",
    "bottom_right",
]
MAX_TENSOR_ELEMENTS = 67_108_864


def _validate_tensor(value, *, name: str, dimensions: int) -> None:
    if not isinstance(value, torch.Tensor) or value.ndim != dimensions:
        raise TypeError(f"{name} must be a {dimensions}D tensor")
    if value.numel() < 1 or value.numel() > MAX_TENSOR_ELEMENTS:
        raise ValueError(f"{name} exceeds the secure tensor-size bound")


class InpaintEasyModel(io.ComfyNode):
    """Build core inpaint conditioning, optionally followed by ControlNet."""

    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="InpaintEasyModel",
            display_name="Inpaint Model",
            category="InpaintEasy",
            description="InpaintEasy- 用来处理控制模块",
            inputs=[
                io.Conditioning.Input("positive"),
                io.Conditioning.Input("negative"),
                io.Image.Input("inpaint_image"),
                io.Mask.Input("mask"),
                io.Vae.Input("vae"),
                io.Float.Input("strength", default=0.5, min=0.0, max=10.0, step=0.01),
                io.Float.Input(
                    "start_percent", default=0.0, min=0.0, max=1.0, step=0.001
                ),
                io.Float.Input(
                    "end_percent", default=1.0, min=0.0, max=1.0, step=0.001
                ),
                io.ControlNet.Input("control_net", optional=True),
                io.Image.Input("control_image", optional=True),
            ],
            outputs=[
                io.Conditioning.Output("positive"),
                io.Conditioning.Output("negative"),
                io.Latent.Output("latent"),
            ],
        )

    @classmethod
    async def execute(
        cls,
        positive,
        negative,
        inpaint_image,
        mask,
        vae,
        strength=1.0,
        start_percent=0.0,
        end_percent=1.0,
        control_net=None,
        control_image=None,
    ) -> io.NodeOutput:
        positive, negative, latent = await vae.encode_inpaint_conditioning(
            inpaint_image,
            mask,
            positive,
            negative,
            noise_mask=True,
        )
        if strength != 0 and control_net is not None and control_image is not None:
            positive, negative = await control_net.apply(
                positive,
                negative,
                control_image,
                strength,
                start_percent,
                end_percent,
                vae,
            )
        return io.NodeOutput(positive, negative, latent)


class ImageAndMaskResizeNode(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ImageAndMaskResizeNode",
            display_name="Image and Mask Resize",
            category="InpaintEasy",
            description="InpaintEasy- 同时调整图片和蒙版的大小",
            inputs=[
                io.Image.Input("image"),
                io.Mask.Input("mask"),
                io.Int.Input("width", default=512, min=64, max=8192, step=8),
                io.Int.Input("height", default=512, min=64, max=8192, step=8),
                io.Combo.Input(
                    "resize_method", options=UPSCALE_METHODS, default="lanczos"
                ),
                io.Combo.Input("crop", options=CROP_METHODS, default="disabled"),
                io.Int.Input("mask_blur_radius", default=10, min=0, max=64, step=1),
            ],
            outputs=[io.Image.Output("image"), io.Mask.Output("mask")],
        )

    @classmethod
    def execute(
        cls,
        image,
        mask,
        width,
        height,
        resize_method="lanczos",
        crop="disabled",
        mask_blur_radius=0,
    ) -> io.NodeOutput:
        _validate_tensor(image, name="image", dimensions=4)
        _validate_tensor(mask, name="mask", dimensions=3)
        if width == 0 and height == 0:
            return io.NodeOutput(image, mask)

        samples = image.movedim(-1, 1)
        if width == 0:
            width = max(1, round(samples.shape[3] * height / samples.shape[2]))
        elif height == 0:
            height = max(1, round(samples.shape[2] * width / samples.shape[3]))

        if crop != "disabled":
            old_width = samples.shape[3]
            old_height = samples.shape[2]
            scale = max(width / old_width, height / old_height)
            scaled_width = int(old_width * scale)
            scaled_height = int(old_height * scale)
            samples = cls._common_upscale(
                samples,
                scaled_width,
                scaled_height,
                resize_method,
                crop="disabled",
            )
            mask = F.interpolate(
                mask.reshape((-1, 1, mask.shape[-2], mask.shape[-1])),
                size=(scaled_height, scaled_width),
                mode="bilinear",
                align_corners=True,
            )
            crop_x = 0
            crop_y = 0
            if crop == "center":
                crop_x = (scaled_width - width) // 2
                crop_y = (scaled_height - height) // 2
            elif crop == "top_right":
                crop_x = scaled_width - width
            elif crop == "bottom_left":
                crop_y = scaled_height - height
            elif crop == "bottom_right":
                crop_x = scaled_width - width
                crop_y = scaled_height - height
            samples = samples[:, :, crop_y : crop_y + height, crop_x : crop_x + width]
            mask = mask[:, :, crop_y : crop_y + height, crop_x : crop_x + width]
        else:
            samples = cls._common_upscale(
                samples, width, height, resize_method, crop="disabled"
            )
            mask = F.interpolate(
                mask.reshape((-1, 1, mask.shape[-2], mask.shape[-1])),
                size=(height, width),
                mode="bilinear",
                align_corners=True,
            )

        image_resized = samples.movedim(1, -1)
        mask_resized = mask.squeeze(1)
        if mask_blur_radius > 0:
            kernel_size = mask_blur_radius * 2 + 1
            x = torch.arange(
                kernel_size, dtype=torch.float32, device=mask_resized.device
            )
            x = x - (kernel_size - 1) / 2
            gaussian = torch.exp(-(x**2) / (2 * (mask_blur_radius / 3) ** 2))
            gaussian = gaussian / gaussian.sum()
            gaussian_2d = gaussian.view(1, -1) * gaussian.view(-1, 1)
            gaussian_2d = gaussian_2d.view(1, 1, kernel_size, kernel_size)
            mask_for_blur = mask_resized.unsqueeze(1)
            padding = kernel_size // 2
            mask_padded = F.pad(
                mask_for_blur,
                (padding, padding, padding, padding),
                mode="reflect",
            )
            mask_resized = F.conv2d(
                mask_padded, gaussian_2d.to(mask_resized.device), padding=0
            ).squeeze(1)
            mask_resized = torch.clamp(mask_resized, 0, 1)
        return io.NodeOutput(image_resized, mask_resized)

    @staticmethod
    def _common_upscale(samples, width, height, method, crop="disabled"):
        """Mirror the current core common_upscale interpolation behavior."""
        if crop == "center":
            old_height = samples.shape[2]
            old_width = samples.shape[3]
            old_aspect = old_width / old_height
            new_aspect = width / height
            x = 0
            y = 0
            if old_aspect > new_aspect:
                x = round((old_width - old_width * (new_aspect / old_aspect)) / 2)
            elif old_aspect < new_aspect:
                y = round((old_height - old_height * (old_aspect / new_aspect)) / 2)
            samples = samples[:, :, y : old_height - y, x : old_width - x]
        if method == "lanczos":
            return cls_lanczos(samples, width, height)
        return F.interpolate(samples, size=(height, width), mode=method)


def cls_lanczos(samples, width: int, height: int):
    """Mirror comfy.utils.lanczos, including its uint8 quantization."""
    device = samples.device
    dtype = samples.dtype
    source = samples.squeeze(1) if samples.shape[1] == 1 else samples.movedim(1, -1)
    images = [
        Image.fromarray(np.clip(255.0 * image.cpu().numpy(), 0, 255).astype(np.uint8))
        for image in source
    ]
    images = [
        image.resize((width, height), resample=Image.Resampling.LANCZOS)
        for image in images
    ]
    tensors = []
    for image in images:
        value = np.array(image).astype(np.float32) / 255.0
        tensors.append(
            torch.from_numpy(value).movedim(-1, 0)
            if value.ndim == 3
            else torch.from_numpy(value)
        )
    return torch.stack(tensors).to(device, dtype)


class CropByMask(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="CropByMask",
            display_name="Crop By Mask",
            category="InpaintEasy",
            inputs=[
                io.Image.Input("image"),
                io.Mask.Input("mask"),
                io.Int.Input(
                    "padding",
                    default=64,
                    min=0,
                    max=512,
                    step=8,
                    display_mode="slider",
                    extra_dict={"display_step": 8},
                ),
            ],
            outputs=[
                io.Image.Output("image"),
                io.Mask.Output("mask"),
                io.Int.Output("crop_x"),
                io.Int.Output("crop_y"),
                io.Int.Output("original_width"),
                io.Int.Output("original_height"),
            ],
        )

    @classmethod
    def execute(cls, image, mask, padding) -> io.NodeOutput:
        _validate_tensor(image, name="image", dimensions=4)
        _validate_tensor(mask, name="mask", dimensions=3)
        mask_np = mask.squeeze(0).cpu().numpy()
        nonzero_indices = np.nonzero(mask_np)
        if len(nonzero_indices[0]) == 0:
            raise ValueError("Mask is empty")
        min_y, max_y = np.min(nonzero_indices[0]), np.max(nonzero_indices[0])
        min_x, max_x = np.min(nonzero_indices[1]), np.max(nonzero_indices[1])
        mask_size = max(max_x - min_x + 1, max_y - min_y + 1)
        original_height, original_width = mask_np.shape
        target_size = mask_size + (2 * padding)
        target_size = ((target_size + 7) // 8) * 8
        crop_width = min(target_size, original_width)
        crop_height = min(target_size, original_height)
        center_x = (min_x + max_x) // 2
        center_y = (min_y + max_y) // 2
        crop_x = center_x - (crop_width // 2)
        crop_y = center_y - (crop_height // 2)
        crop_x = max(0, min(crop_x, original_width - crop_width))
        crop_y = max(0, min(crop_y, original_height - crop_height))
        cropped_image = image[
            :, crop_y : crop_y + crop_height, crop_x : crop_x + crop_width, :
        ]
        cropped_mask = mask[
            :, crop_y : crop_y + crop_height, crop_x : crop_x + crop_width
        ]
        return io.NodeOutput(
            cropped_image,
            cropped_mask,
            int(crop_x),
            int(crop_y),
            int(crop_width),
            int(crop_height),
        )


class ImageCropMerge(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ImageCropMerge",
            display_name="Image Crop Merge",
            category="InpaintEasy",
            description="InpaintEasy- 图片与裁剪覆合,将裁剪的图片合并回原图中",
            inputs=[
                io.Image.Input("cropped_image"),
                io.Image.Input("original_image"),
                io.Int.Input("crop_x", default=0, min=0, max=4096, force_input=True),
                io.Int.Input("crop_y", default=0, min=0, max=4096, force_input=True),
                io.Int.Input(
                    "cropped_original_width",
                    default=512,
                    min=1,
                    max=4096,
                    force_input=True,
                ),
                io.Int.Input(
                    "cropped_original_height",
                    default=512,
                    min=1,
                    max=4096,
                    force_input=True,
                ),
                io.Combo.Input(
                    "resize_method", options=UPSCALE_METHODS, default="lanczos"
                ),
            ],
            outputs=[io.Image.Output()],
        )

    @classmethod
    def execute(
        cls,
        cropped_image,
        original_image,
        cropped_original_width,
        cropped_original_height,
        crop_x,
        crop_y,
        resize_method,
    ) -> io.NodeOutput:
        _validate_tensor(cropped_image, name="cropped_image", dimensions=4)
        _validate_tensor(original_image, name="original_image", dimensions=4)
        samples = cropped_image.movedim(-1, 1)
        resized_image = ImageAndMaskResizeNode._common_upscale(
            samples,
            cropped_original_width,
            cropped_original_height,
            resize_method,
            "disabled",
        ).movedim(1, -1)
        result = original_image.clone()
        result[
            :,
            crop_y : crop_y + cropped_original_height,
            crop_x : crop_x + cropped_original_width,
        ] = resized_image
        return io.NodeOutput(result)


NODE_CLASS_MAPPINGS = {
    "InpaintEasyModel": InpaintEasyModel,
    "ImageAndMaskResizeNode": ImageAndMaskResizeNode,
    "CropByMask": CropByMask,
    "ImageCropMerge": ImageCropMerge,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "InpaintEasyModel": "Inpaint Model",
    "ImageAndMaskResizeNode": "Image and Mask Resize",
    "CropByMask": "Crop By Mask",
    "ImageCropMerge": "Image Crop Merge",
}


class InpaintEasyExtension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint() -> InpaintEasyExtension:
    return InpaintEasyExtension()
