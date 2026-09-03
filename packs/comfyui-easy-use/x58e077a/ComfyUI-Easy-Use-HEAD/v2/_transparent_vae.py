from __future__ import annotations

import asyncio
import math
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

import torch
from comfy_api.latest import sdk


_EXPECTED_WEIGHTS = {
    "sd1": "layer_sd15_vae_transparent_decoder.safetensors",
    "sdxl": "vae_transparent_decoder.safetensors",
}
_MAX_BATCH = 64
_MAX_PIXELS = 67_108_864


@dataclass
class _Entry:
    decoder: Any
    family: str
    lock: threading.Lock = field(default_factory=threading.Lock)


_CACHE: "OrderedDict[tuple[str, str], _Entry]" = OrderedDict()


def _recipe(weight: str, family: str) -> dict[str, str]:
    if family not in _EXPECTED_WEIGHTS:
        raise ValueError("transparent VAE decoder family must be sd1 or sdxl")
    if not isinstance(weight, str) or not weight:
        raise ValueError("transparent VAE decoding requires a managed weight")
    if weight.rsplit("/", 1)[-1].lower() != _EXPECTED_WEIGHTS[family].lower():
        raise ValueError(
            f"{family} transparent VAE decoding requires "
            f"{_EXPECTED_WEIGHTS[family]!r}"
        )
    return {
        "kind": "easy-use.transparent-vae-decoder",
        "weight": weight,
        "family": family,
    }


def _validated_recipe(value: Any) -> dict[str, str]:
    if (
        not isinstance(value, dict)
        or set(value) != {"kind", "weight", "family"}
        or value.get("kind") != "easy-use.transparent-vae-decoder"
    ):
        raise TypeError("Layer Diffusion requires its transparent VAE decoder")
    return _recipe(value["weight"], value["family"])


def _zero_module(module: Any) -> Any:
    for parameter in module.parameters():
        parameter.detach().zero_()
    return module


def _build_decoder(state: dict[str, torch.Tensor], device: torch.device) -> Any:
    try:
        from diffusers.configuration_utils import ConfigMixin, register_to_config
        from diffusers.models.modeling_utils import ModelMixin
        from diffusers.models.unets.unet_2d_blocks import (
            UNetMidBlock2D,
            get_down_block,
            get_up_block,
        )
    except ImportError as error:
        raise RuntimeError(
            "transparent VAE decoding requires the pack's Diffusers dependency"
        ) from error

    class TransparentUNet(ModelMixin, ConfigMixin):
        @register_to_config
        def __init__(self):
            super().__init__()
            block_channels = (32, 32, 64, 128, 256, 512, 512)
            down_types = (
                "DownBlock2D",
                "DownBlock2D",
                "DownBlock2D",
                "DownBlock2D",
                "AttnDownBlock2D",
                "AttnDownBlock2D",
                "AttnDownBlock2D",
            )
            up_types = (
                "AttnUpBlock2D",
                "AttnUpBlock2D",
                "AttnUpBlock2D",
                "UpBlock2D",
                "UpBlock2D",
                "UpBlock2D",
                "UpBlock2D",
            )
            self.conv_in = torch.nn.Conv2d(3, block_channels[0], 3, padding=1)
            self.latent_conv_in = _zero_module(
                torch.nn.Conv2d(4, block_channels[2], 1)
            )
            self.down_blocks = torch.nn.ModuleList()
            output_channel = block_channels[0]
            for index, block_type in enumerate(down_types):
                input_channel = output_channel
                output_channel = block_channels[index]
                self.down_blocks.append(get_down_block(
                    block_type,
                    num_layers=2,
                    in_channels=input_channel,
                    out_channels=output_channel,
                    temb_channels=None,
                    add_downsample=index != len(block_channels) - 1,
                    resnet_eps=1e-5,
                    resnet_act_fn="silu",
                    resnet_groups=4,
                    attention_head_dim=8,
                    downsample_padding=1,
                    resnet_time_scale_shift="default",
                    downsample_type="conv",
                    dropout=0.0,
                ))
            self.mid_block = UNetMidBlock2D(
                in_channels=block_channels[-1],
                temb_channels=None,
                dropout=0.0,
                resnet_eps=1e-5,
                resnet_act_fn="silu",
                output_scale_factor=1,
                resnet_time_scale_shift="default",
                attention_head_dim=8,
                resnet_groups=4,
                attn_groups=None,
                add_attention=True,
            )
            self.up_blocks = torch.nn.ModuleList()
            reversed_channels = list(reversed(block_channels))
            output_channel = reversed_channels[0]
            for index, block_type in enumerate(up_types):
                previous_output = output_channel
                output_channel = reversed_channels[index]
                input_channel = reversed_channels[
                    min(index + 1, len(block_channels) - 1)
                ]
                self.up_blocks.append(get_up_block(
                    block_type,
                    num_layers=3,
                    in_channels=input_channel,
                    out_channels=output_channel,
                    prev_output_channel=previous_output,
                    temb_channels=None,
                    add_upsample=index != len(block_channels) - 1,
                    resnet_eps=1e-5,
                    resnet_act_fn="silu",
                    resnet_groups=4,
                    attention_head_dim=8,
                    resnet_time_scale_shift="default",
                    upsample_type="conv",
                    dropout=0.0,
                ))
            self.conv_norm_out = torch.nn.GroupNorm(
                4, block_channels[0], eps=1e-5
            )
            self.conv_act = torch.nn.SiLU()
            self.conv_out = torch.nn.Conv2d(
                block_channels[0], 4, 3, padding=1
            )

        def forward(self, pixels: torch.Tensor, latent: torch.Tensor) -> torch.Tensor:
            latent_sample = self.latent_conv_in(latent)
            sample = self.conv_in(pixels)
            residuals = (sample,)
            for index, block in enumerate(self.down_blocks):
                if index == 3:
                    sample = sample + latent_sample
                sample, block_residuals = block(hidden_states=sample, temb=None)
                residuals += block_residuals
            sample = self.mid_block(sample, None)
            for block in self.up_blocks:
                block_residuals = residuals[-len(block.resnets):]
                residuals = residuals[:-len(block.resnets)]
                sample = block(sample, block_residuals, None)
            return self.conv_out(self.conv_act(self.conv_norm_out(sample)))

    model = TransparentUNet()
    model.load_state_dict(state, strict=True)
    dtype = torch.float16 if device.type == "cuda" else torch.float32
    model.eval().to(device=device, dtype=dtype)
    return model


async def _entry(ctx: Any, value: Any) -> tuple[_Entry, dict[str, str]]:
    recipe = _validated_recipe(value)
    key = (recipe["weight"], recipe["family"])
    cached = _CACHE.pop(key, None)
    if cached is not None:
        _CACHE[key] = cached
        return cached, recipe

    asset = await ctx.assets.resolve("vae", recipe["weight"])
    state = await ctx.assets.load_state_dict(asset)
    if not isinstance(state, dict) or not state or any(
        not isinstance(name, str) or not isinstance(tensor, torch.Tensor)
        for name, tensor in state.items()
    ):
        raise ValueError("transparent VAE weights must contain only tensors")
    state = {name: tensor.detach().cpu() for name, tensor in state.items()}
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    loaded = _Entry(
        decoder=await asyncio.to_thread(_build_decoder, state, device),
        family=recipe["family"],
    )
    while len(_CACHE) >= 2:
        _old_key, old = _CACHE.popitem(last=False)
        old.decoder.to("cpu")
    _CACHE[key] = loaded
    return loaded, recipe


async def load(ctx: Any, weight: str, family: str) -> dict[str, str]:
    recipe = _recipe(weight, family)
    await _entry(ctx, recipe)
    return recipe


def _checked_inputs(
    latent_value: Any, pixels: Any, frames: int, sub_batch_size: int,
) -> tuple[torch.Tensor, torch.Tensor]:
    if isinstance(frames, bool) or not isinstance(frames, int) or not 1 <= frames <= 3:
        raise ValueError("transparent decoder frames must be in [1, 3]")
    if (
        isinstance(sub_batch_size, bool)
        or not isinstance(sub_batch_size, int)
        or not 1 <= sub_batch_size <= 64
    ):
        raise ValueError("transparent decoder sub_batch_size must be in [1, 64]")
    samples = latent_value.get("samples") if isinstance(latent_value, dict) else None
    if (
        not isinstance(samples, torch.Tensor)
        or samples.ndim != 4
        or not isinstance(pixels, torch.Tensor)
        or pixels.ndim != 4
        or pixels.shape[-1] < 3
        or not 1 <= len(pixels) <= _MAX_BATCH
        or len(samples) != len(pixels)
    ):
        raise ValueError(
            "transparent decoding needs matching BCHW latent and BHWC image batches"
        )
    height, width = map(int, pixels.shape[1:3])
    if (
        height <= 0
        or width <= 0
        or height % 64
        or width % 64
        or len(pixels) * height * width > _MAX_PIXELS
    ):
        raise ValueError(
            "transparent decoder image dimensions must be multiples of 64 "
            "within the bounded batch limit"
        )
    if len(pixels) % frames:
        raise ValueError("transparent decoder batch must be divisible by frames")
    return samples, pixels


async def decode(
    ctx: Any,
    value: Any,
    latent: sdk.LatentRef,
    image: sdk.ImageRef,
    frames: int = 1,
    sub_batch_size: int = 16,
) -> tuple[sdk.ImageRef, sdk.MaskRef]:
    entry, _used_recipe = await _entry(ctx, value)
    samples, pixels = _checked_inputs(
        await latent.value(), await image.raw(), frames, sub_batch_size
    )
    device = next(entry.decoder.parameters()).device
    dtype = next(entry.decoder.parameters()).dtype

    def run() -> tuple[torch.Tensor, torch.Tensor]:
        selected_pixels = pixels[::frames, ..., :3].movedim(-1, 1)
        selected_samples = samples[::frames]
        decoded = []
        with entry.lock, torch.no_grad():
            for start in range(0, len(selected_samples), sub_batch_size):
                source = selected_pixels[start:start + sub_batch_size]
                source_latent = selected_samples[start:start + sub_batch_size]
                predictions = []
                for flip in (False, True):
                    for rotations in range(4):
                        current_pixels = source.flip(3) if flip else source
                        current_latent = source_latent.flip(3) if flip else source_latent
                        current_pixels = torch.rot90(
                            current_pixels, rotations, (2, 3)
                        ).to(device=device, dtype=dtype)
                        current_latent = torch.rot90(
                            current_latent, rotations, (2, 3)
                        ).to(device=device, dtype=dtype)
                        prediction = entry.decoder(
                            current_pixels, current_latent
                        ).clamp(0.0, 1.0)
                        prediction = torch.rot90(prediction, -rotations, (2, 3))
                        if flip:
                            prediction = prediction.flip(3)
                        predictions.append(prediction)
                decoded.append(torch.stack(predictions).median(dim=0).values.cpu())
        result = torch.cat(decoded).movedim(1, -1)
        height, width = map(int, pixels.shape[1:3])
        if result.ndim != 4 or result.shape[-1] < 4 or result.shape[1:3] != (height, width):
            raise RuntimeError("transparent VAE decoder returned invalid pixels")
        decoded_rgb = result[..., 1:4].float().clamp(0.0, 1.0)
        alpha = (1.0 - result[..., 0]).float().clamp(0.0, 1.0)
        full_rgb = pixels[..., :3].cpu().float().clone()
        full_alpha = torch.ones((len(pixels), height, width), dtype=torch.float32)
        full_rgb[::frames] = decoded_rgb
        full_alpha[::frames] = alpha
        return torch.cat((full_rgb, full_alpha.unsqueeze(-1)), dim=-1), alpha

    rgba, alpha = await asyncio.to_thread(run)
    return (
        await sdk.ImageRef._from_raw(rgba),
        await sdk.MaskRef._from_raw(alpha),
    )
