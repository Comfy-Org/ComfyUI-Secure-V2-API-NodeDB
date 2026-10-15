"""Exact native reference-video noise, preserving device/dtype and RNG draws.

Actual Torch is required. The source uses the current per-device generator via
randn_like: no local generator, reseed, epsilon, sentinel or broadcast fix.
Runtime RNG/isolation/admission must be qualified; none is provided here.
"""
import torch

def add_noise_to_reference_video(image, ratio=None):
    sigma = torch.ones((image.shape[0],)).to(image.device, image.dtype) * ratio
    image_noise = torch.randn_like(image) * sigma[:, None, None, None]
    image_noise = torch.where(image==-1, torch.zeros_like(image), image_noise)
    image = image + image_noise
    return image

