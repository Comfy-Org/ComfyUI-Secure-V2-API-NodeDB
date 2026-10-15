"""Dense CPU noise math from the pinned original ComfyUI comfy/sample.py (GPL-3.0)."""
import torch
import numpy as np

def prepare_noise_inner(latent_image, generator, noise_inds=None):
    if noise_inds is None:
        return torch.randn(latent_image.size(), dtype=torch.float32, layout=latent_image.layout, generator=generator, device="cpu").to(dtype=latent_image.dtype)

    unique_inds, inverse = np.unique(noise_inds, return_inverse=True)
    noises = []
    for i in range(unique_inds[-1]+1):
        noise = torch.randn([1] + list(latent_image.size())[1:], dtype=torch.float32, layout=latent_image.layout, generator=generator, device="cpu").to(dtype=latent_image.dtype)
        if i in unique_inds:
            noises.append(noise)
    noises = [noises[i] for i in inverse]
    return torch.cat(noises, axis=0)

def prepare_noise(latent_image, seed, noise_inds=None):
    if latent_image.is_nested:
        raise TypeError('Nested tensors are outside this raw TensorRef adapter scope')
    generator = torch.manual_seed(seed)
    return prepare_noise_inner(latent_image, generator, noise_inds)
