"""Deterministic stand-ins for the model-owned operations, shared by both sides of the parity test.

The original pack (V1) and the V2 port run with identical fake VAE, sampler, guider and upscale-model behaviour, so
any output difference comes from the pack-side tile pipeline: crops, masks, blurs, resizes, compositing and ordering.
Every model-owned call is recorded (inputs and outputs by digest) so the two call sequences can be compared too.
"""
from __future__ import annotations

import hashlib

import torch
import torch.nn.functional as F

CALLS: list = []      # model-owned calls, comparable between V1 and V2
BOUNDARY: list = []   # V2-only boundary arguments (tile sizes, crop regions) for the report


def digest(value) -> str:
    t = torch.as_tensor(value).detach().cpu().contiguous()
    return hashlib.sha256(t.numpy().tobytes()).hexdigest()[:16] + f":{tuple(t.shape)}:{str(t.dtype)}"


def text_tag(value) -> float:
    return (sum((i + 1) * ord(c) for i, c in enumerate(str(value))) % 997) / 997.0


def tensor_tag(t) -> float:
    return round(float(torch.as_tensor(t).double().sum()), 6)


def encode(pixels):
    """VAE encode stand-in: crop to multiples of 8 (as ComfyUI's VAE does), 8x8 average pool, 4 channels."""
    x = torch.as_tensor(pixels)[..., :3].movedim(-1, 1).float()
    h, w = x.shape[-2] // 8 * 8, x.shape[-1] // 8 * 8
    x = x[..., :h, :w]
    pooled = F.avg_pool2d(x, 8)
    out = torch.cat([pooled * 2 - 1, pooled.mean(dim=1, keepdim=True)], dim=1).contiguous()
    CALLS.append(("encode", digest(pixels), digest(out)))
    return out


def sample(kind, latent, seed, steps, cfg, sampler_name, scheduler, denoise, positive_tag, negative_tag,
           extra_tag=0.0):
    """Sampler stand-in: seeded noise mixed in by denoise; every parameter moves the result."""
    latent = torch.as_tensor(latent).float()
    g = torch.Generator().manual_seed(int(seed))
    noise = torch.randn(tuple(latent.shape), generator=g)
    d = float(denoise)
    out = (latent * (1 - 0.35 * d) + noise * 0.25 * d + 0.01 * float(cfg) + 0.002 * int(steps)
           + 0.03 * text_tag(sampler_name) - 0.04 * text_tag(scheduler)
           + 0.05 * positive_tag - 0.05 * negative_tag + 0.01 * extra_tag).contiguous()
    CALLS.append(("sample", kind, int(seed), int(steps), float(cfg), str(sampler_name), str(scheduler), round(d, 6),
                  positive_tag, negative_tag, round(float(extra_tag), 6), digest(latent), digest(out)))
    return out


def decode(latent, tiled=False):
    """VAE decode stand-in: bilinear x8 upsample of 3 latent channels to BHWC in [0, 1]."""
    x = torch.as_tensor(latent)[:, :3].float()
    up = F.interpolate(x, scale_factor=8, mode="bilinear", align_corners=False)
    img = ((up + 1) / 2).clamp(0, 1).movedim(1, -1).contiguous()
    if tiled:
        img = (img * 0.999 + 0.0005).clamp(0, 1).contiguous()
    CALLS.append(("decode", "tiled" if tiled else "plain", digest(latent), digest(img)))
    return img


def upscale(image):
    """Upscale-model stand-in: x4 bicubic, clamped (ImageUpscaleWithModel clamps its output)."""
    x = torch.as_tensor(image)[..., :3].movedim(-1, 1).float()
    up = F.interpolate(x, scale_factor=4, mode="bicubic", align_corners=False).clamp(0, 1)
    out = up.movedim(1, -1).contiguous()
    CALLS.append(("upscale", digest(image), digest(out)))
    return out


# --------------------------------------------------------------------------------------------------------------------
# V1 side: replacements for the ComfyUI objects the original modules call
# --------------------------------------------------------------------------------------------------------------------
class V1Model:
    def __init__(self, tag):
        self.tag = tag
        self.model_options = {}

    def clone(self):
        return V1Model(self.tag)


class V1Tagged:
    def __init__(self, tag):
        self.tag = tag


class V1Guider:
    def __init__(self, tag):
        self.tag = tag
        self.model_patcher = V1Model(tag)


def v1_cond(tensor):
    return [[tensor, {}]]


def v1_cond_tag(cond):
    return tensor_tag(cond[0][0])


class V1VAEEncode:
    def encode(self, vae, pixels):
        return ({"samples": encode(pixels)},)


class V1VAEDecode:
    def decode(self, vae, samples):
        return (decode(samples["samples"]),)


class V1VAEDecodeTiled:
    def decode(self, vae, samples, tile_size, overlap=64, temporal_size=64, temporal_overlap=8):
        CALLS.append(("decode_tiled_args", int(tile_size), int(overlap), int(temporal_size), int(temporal_overlap)))
        return (decode(samples["samples"], tiled=True),)


def v1_common_ksampler(model, seed, steps, cfg, sampler_name, scheduler, positive, negative, latent, denoise=1.0,
                       disable_noise=False, start_step=None, last_step=None, force_full_denoise=False):
    assert not disable_noise and start_step is None and last_step is None and not force_full_denoise
    out = sample("ksampler", latent["samples"], seed, steps, cfg, sampler_name, scheduler, denoise,
                 v1_cond_tag(positive), v1_cond_tag(negative), extra_tag=model.tag)
    return ({"samples": out},)


class V1SamplerCustom:
    @staticmethod
    def execute(model, add_noise, noise_seed, cfg, positive, negative, sampler, sigmas, latent_image):
        assert add_noise is True
        out = sample("custom", latent_image["samples"], noise_seed, 0, cfg, "", "", 1.0,
                     v1_cond_tag(positive), v1_cond_tag(negative), extra_tag=model.tag + sampler.tag + sigmas.tag)
        return ({"samples": out}, None)


def v1_sample_with_guider(guider, sampler, sigmas, seed, latent):
    out = sample("guider", latent["samples"], seed, 0, 0.0, "", "", 1.0, 0.0, 0.0,
                 extra_tag=guider.tag + sampler.tag + sigmas.tag)
    return {"samples": out}


class V1ImageUpscaleWithModel:
    @staticmethod
    def execute(upscale_model, image):
        return (upscale(image),)


# --------------------------------------------------------------------------------------------------------------------
# V2 side: fake SDK references with the host's argument checks
# --------------------------------------------------------------------------------------------------------------------
RELEASED: list = []
PROGRESS: list = []


class Ref:
    _count = 0

    def __init__(self, kind, value=None, tag=0.0):
        Ref._count += 1
        self.id = f"{kind}-{Ref._count}"
        self.kind = kind
        self.value = value
        self.tag = tag

    async def raw(self):
        return self.value

    async def release(self):
        RELEASED.append(self.id)


def _check_image(value):
    t = torch.as_tensor(value)
    assert t.ndim == 4 and t.shape[-1] in (1, 3, 4), f"IMAGE must be BHWC, got {tuple(t.shape)}"
    assert bool(torch.isfinite(t).all()), "IMAGE pixels must be finite"
    return t


async def image_ref(value):
    return Ref("IMAGE", _check_image(value))


class V2Vae(Ref):
    def __init__(self):
        super().__init__("VAE")

    async def encode(self, image):
        assert isinstance(image, Ref) and image.kind == "IMAGE"
        return Ref("LATENT", encode(image.value))

    async def decode(self, latent, *, allow_extended_range=False):
        assert latent.kind == "LATENT" and allow_extended_range is False
        return Ref("IMAGE", decode(latent.value))

    async def decode_tiled(self, latent, tile_size=512, overlap=64, temporal_size=64, temporal_overlap=8, *,
                           allow_extended_range=False):
        assert latent.kind == "LATENT" and allow_extended_range is False
        CALLS.append(("decode_tiled_args", int(tile_size), int(overlap), int(temporal_size), int(temporal_overlap)))
        return Ref("IMAGE", decode(latent.value, tiled=True))


class V2UpscaleModel(Ref):
    def __init__(self, tag):
        super().__init__("UPSCALE_MODEL", tag=tag)

    async def upscale(self, images, per_batch=16, downscale_ratio=1.0, downscale_method="lanczos",
                      precision="float32", tile_size=None, channels_last=False):
        BOUNDARY.append(("upscale_args", per_batch, downscale_ratio, downscale_method, precision, tile_size,
                         channels_last))
        return Ref("IMAGE", upscale(images.value))


class V2Cond(Ref):
    def __init__(self, tensor):
        super().__init__("CONDITIONING", tensor)

    async def has_spatial_metadata(self):
        return False

    async def spatial_crop(self, **kwargs):
        BOUNDARY.append(("cond_spatial_crop", tuple(sorted(kwargs.items()))))
        return V2Cond(self.value)


def _check_regions(regions, source_width, source_height, target_width, target_height):
    assert isinstance(regions, list) and 1 <= len(regions) <= 4096
    for region in regions:
        assert isinstance(region, (list, tuple)) and len(region) == 4
        assert all(type(v) is int for v in region), f"regions must be ints: {region!r}"
        left, top, right, bottom = region
        assert 0 <= left < right <= source_width and 0 <= top < bottom <= source_height, (region, source_width,
                                                                                        source_height)
    for v in (source_width, source_height, target_width, target_height):
        assert type(v) is int and v >= 1


class V2Model(Ref):
    def __init__(self, tag):
        super().__init__("MODEL", tag=tag)

    async def spatial_crop_inputs(self, *, regions, source_width, source_height, target_width, target_height):
        _check_regions(regions, source_width, source_height, target_width, target_height)
        BOUNDARY.append(("model_crop", tuple(map(tuple, regions)), source_width, source_height, target_width,
                         target_height))
        return V2Model(self.tag)


class V2Guider(Ref):
    def __init__(self, tag):
        super().__init__("GUIDER", tag=tag)

    async def spatial_crop_inputs(self, *, regions, source_width, source_height, target_width, target_height):
        _check_regions(regions, source_width, source_height, target_width, target_height)
        BOUNDARY.append(("guider_crop", tuple(map(tuple, regions)), source_width, source_height, target_width,
                         target_height))
        return V2Guider(self.tag)


class _Progress:
    async def update(self, value, total, preview=None):
        PROGRESS.append((value, total))


class V2Ctx:
    progress = _Progress()

    async def sample(self, latent, steps, on_step=None, model=None, positive=None, negative=None, cfg=8.0, seed=0,
                     sampler_name="euler", scheduler="normal", denoise=1.0, sampler=None, sigmas=None, guider=None,
                     **extra):
        # The host's checks (comfy_secure_nodes/transport/host.py _h_sample).
        assert not extra, extra
        assert type(steps) is int and 1 <= steps <= 10000, steps
        assert type(seed) is int and 0 <= seed <= (1 << 64) - 1, seed
        assert isinstance(cfg, float) and isinstance(denoise, float) and 0.0 <= denoise <= 1.0
        assert not (guider is not None and model is not None)
        assert guider is None or (sampler is not None and sigmas is not None)
        assert sigmas is None or sampler is not None
        assert isinstance(sampler_name, str) and isinstance(scheduler, str)
        if guider is not None:
            out = sample("guider", latent.value, seed, 0, 0.0, "", "", 1.0, 0.0, 0.0,
                         extra_tag=guider.tag + sampler.tag + sigmas.tag)
        elif sampler is not None:
            out = sample("custom", latent.value, seed, 0, cfg, "", "", 1.0, tensor_tag(positive.value),
                         tensor_tag(negative.value), extra_tag=model.tag + sampler.tag + sigmas.tag)
        else:
            out = sample("ksampler", latent.value, seed, steps, cfg, sampler_name, scheduler, denoise,
                         tensor_tag(positive.value), tensor_tag(negative.value), extra_tag=model.tag)
        return Ref("LATENT", out)


CTX = V2Ctx()


def reset():
    CALLS.clear()
    BOUNDARY.clear()
    RELEASED.clear()
    PROGRESS.clear()
