"""A tiny, seeded SD1.x-architecture model, VAE and conditioning for gate tests (no checkpoint needed).

Core's own classes are used throughout, so encode, sample and decode run Core's real code paths: an SD15
model config (EPS, scaled-linear schedule, SD1 latent format) with a two-level UNet, an AutoencoderKL with
Core's 8x layout, and SD1-shaped conditioning. Weights are drawn from a fixed seed, so two processes build
byte-identical models (state_dict_digest() proves it). The numbers mean nothing; the code paths are real.
"""

import hashlib

import torch

UNET_CONFIG = {
    "use_checkpoint": False, "image_size": 32, "in_channels": 4, "out_channels": 4, "model_channels": 32,
    "num_res_blocks": [1, 1], "channel_mult": [1, 2], "transformer_depth": [1, 1], "transformer_depth_middle": 1,
    "transformer_depth_output": [1, 1, 1, 1], "use_spatial_transformer": True, "use_linear_in_transformer": False,
    "context_dim": 32, "num_heads": 2, "legacy": False, "adm_in_channels": None, "use_temporal_resblock": False,
    "use_temporal_attention": False,
}
VAE_DDCONFIG = {"double_z": True, "z_channels": 4, "resolution": 256, "in_channels": 3, "out_ch": 3, "ch": 32,
                "ch_mult": [1, 1, 1, 1], "num_res_blocks": 1, "attn_resolutions": [], "dropout": 0.0}


def _seed_parameters(module: torch.nn.Module, seed: int, scale: float) -> None:
    generator = torch.Generator(device="cpu").manual_seed(seed)
    with torch.no_grad():
        for name, tensor in sorted(module.state_dict(keep_vars=True).items()):
            if not tensor.is_floating_point():
                continue
            if name.endswith("weight") and tensor.ndim == 1:  # norms
                values = 1.0 + 0.05 * torch.randn(tensor.shape, generator=generator)
            elif name.endswith("bias"):
                values = 0.01 * torch.randn(tensor.shape, generator=generator)
            else:
                fan_in = max(1, tensor[0].numel()) if tensor.ndim > 1 else max(1, tensor.numel())
                values = torch.randn(tensor.shape, generator=generator) * (scale / fan_in ** 0.5)
            tensor.data.copy_(values.to(tensor.dtype))


def build_model(seed: int = 1):
    import comfy.model_patcher
    import comfy.supported_models

    config = comfy.supported_models.SD15(dict(UNET_CONFIG))
    model = config.get_model({}, "", device=torch.device("cpu"))
    model.diffusion_model.to(torch.float32)
    _seed_parameters(model.diffusion_model, seed, 1.0)
    model.eval()
    return comfy.model_patcher.ModelPatcher(model, load_device=torch.device("cpu"), offload_device=torch.device("cpu"))


def build_vae(seed: int = 2):
    import comfy.sd
    from comfy.ldm.models.autoencoder import AutoencoderKL

    template = AutoencoderKL(ddconfig=dict(VAE_DDCONFIG), embed_dim=4)
    _seed_parameters(template, seed, 1.0)
    state = {k: v.detach().clone().to(torch.float32) for k, v in template.state_dict().items()}
    return comfy.sd.VAE(sd=state, config={"params": {"ddconfig": dict(VAE_DDCONFIG), "embed_dim": 4}})


def build_conditioning(seed: int, tokens: int = 4):
    generator = torch.Generator(device="cpu").manual_seed(seed)
    return [[torch.randn((1, tokens, UNET_CONFIG["context_dim"]), generator=generator), {"pooled_output": None}]]


def state_dict_digest(module_or_patcher) -> str:
    module = getattr(module_or_patcher, "model", module_or_patcher)
    module = getattr(module, "first_stage_model", module)
    digest = hashlib.sha256()
    for name, tensor in sorted(module.state_dict().items()):
        digest.update(name.encode())
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()
