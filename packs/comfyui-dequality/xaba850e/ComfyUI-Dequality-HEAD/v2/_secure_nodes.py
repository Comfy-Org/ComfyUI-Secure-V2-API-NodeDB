"""Bounded pack-side Pillow enhancement/noise/JPEG algorithm."""
import io as bytes_io
import math
import numpy as np
import torch
from PIL import Image, ImageEnhance
from comfy_api.latest import io

MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_OUTPUT_BYTES = 64 * 1024 * 1024
MAX_WORK_BYTES = 384 * 1024 * 1024

def preflight(pixels):
    if not isinstance(pixels, torch.Tensor) or pixels.layout != torch.strided or pixels.ndim not in (3, 4):
        raise ValueError("pixels must be dense HWC or BHWC")
    shape = tuple(pixels.shape)
    if len(shape) == 4:
        batch, height, width, channels = shape
    else:
        height, width, channels = shape
        batch = 1
    if batch > 64 or height > 4096 or width > 4096 or channels > 8:
        raise ValueError("image dimensions exceed admitted bounds")
    if max(pixels.numel() * pixels.element_size(), pixels.untyped_storage().nbytes()) > MAX_INPUT_BYTES:
        raise ValueError("input byte budget exceeded")
    count = batch * height * width * channels
    if count * 4 > MAX_OUTPUT_BYTES or count * 80 + height * width * 16 > MAX_WORK_BYTES:
        raise ValueError("output or workspace byte budget exceeded")

def validate_scalars(noise_level, jpeg_artifact_level, adjust_color, adjust_contrast, adjust_brightness, seed):
    for name, value in (("noise_level", noise_level), ("jpeg_artifact_level", jpeg_artifact_level),
                        ("adjust_color", adjust_color), ("adjust_contrast", adjust_contrast),
                        ("adjust_brightness", adjust_brightness), ("seed", seed)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(name + " must be an integer")
    if abs(seed) > 1125899906842624 or abs(noise_level) > 10000 or abs(jpeg_artifact_level) > 10000:
        raise ValueError("scalar workload bound exceeded")
    if any(abs(x) > 10000 for x in (adjust_color, adjust_contrast, adjust_brightness)):
        raise ValueError("adjustment workload bound exceeded")

def run_algorithm(pixels, noise_level, jpeg_artifact_level, adjust_color, adjust_contrast, adjust_brightness, seed, *, noise_rng=None):
    preflight(pixels)
    validate_scalars(noise_level, jpeg_artifact_level, adjust_color, adjust_contrast, adjust_brightness, seed)
    rng = np.random.default_rng(seed=abs(seed))
    img = Image.fromarray(np.clip(255. * pixels.cpu().numpy().squeeze(0), 0, 255).astype(np.uint8))
    if img.mode == "RGBA":
        img = img.convert("RGB")
    if adjust_brightness == 1:
        img = ImageEnhance.Brightness(img).enhance(rng.uniform(0.9, 1.1))
    if adjust_color == 1:
        img = ImageEnhance.Color(img).enhance(rng.uniform(0.9, 1.1))
    if adjust_contrast == 1:
        img = ImageEnhance.Contrast(img).enhance(rng.uniform(0.9, 1.1))
    if noise_level > 0:
        # Preserve unseeded legacy noise, but do not consume another node's RNG.
        draws = np.random.RandomState() if noise_rng is None else noise_rng
        level = noise_level / 1000
        arr = np.array(img)
        noise = draws.normal(0, 255 * level, arr.shape)
        variation = draws.normal(0, 255 * (level * 2), arr.shape)
        mask = draws.rand(*arr.shape[:2]) > 0.95
        noise[mask] += variation[mask]
        img = Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8))
    if jpeg_artifact_level < 100:
        with bytes_io.BytesIO() as stream:
            img.save(stream, "JPEG", quality=jpeg_artifact_level)
            stream.seek(0)
            with Image.open(stream) as final:
                return torch.from_numpy(np.array(final).astype(np.float32) / 255.0).unsqueeze(0)
    return torch.from_numpy(np.array(img).astype(np.float32) / 255.0).unsqueeze(0)

class DequalitySecure(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="Dequality", display_name="Dequality", category="image",
            inputs=[
                io.Image.Input("pixels"),
                io.Int.Input("jpeg_artifact_level", default=65, min=0, max=100, step=5),
                io.Int.Input("noise_level", default=8, min=0.0, max=100, step=1),
                io.Int.Input("adjust_brightness", default=1, min=0, max=1, step=1),
                io.Int.Input("adjust_color", default=1, min=0, max=1, step=1),
                io.Int.Input("adjust_contrast", default=1, min=0, max=1, step=1),
                io.Int.Input("seed", default=0, min=-1125899906842624, max=1125899906842624),
            ], outputs=[io.Image.Output()])
    @classmethod
    def execute(cls, pixels, noise_level, jpeg_artifact_level, adjust_color, adjust_contrast, adjust_brightness, seed):
        return io.NodeOutput(run_algorithm(pixels, noise_level, jpeg_artifact_level, adjust_color, adjust_contrast, adjust_brightness, seed))

