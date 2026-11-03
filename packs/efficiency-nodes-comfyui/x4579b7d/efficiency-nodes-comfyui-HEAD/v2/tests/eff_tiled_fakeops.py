"""Deterministic stand-ins for the model-owned work of the Tiled Upscaler Script, shared by both sides of
test_efficiency_tiled_parity.py.

The original (py/bnk_tiled_samplers.py TiledKSampler) and the V2 port (_secure_nodes._sample_tiled) both run on the
same real ComfyUI scheduling code: comfy.samplers.KSampler sigma schedules, denoise and start/last-step slicing,
comfy.sample.prepare_noise and comfy.sampler_helpers.prepare_mask. Only the diffusion step itself
(comfy.samplers.sample) and the VAE are stand-ins. So an output difference can only come from the pack-side control
flow: noise, the pre-noise sigma, tiles, step ranges, masks and write-back.
On the V2 side, ctx.sample and the ModelRef/CondRef queries follow the host's implementations
(comfy_secure_nodes transport/host.py _h_sample; comfy_api latest _sdk.py _model_sampling_sigma_delta,
_model_latent_scale_factor, _model_family, _cond_has_spatial_metadata), including the guest wire rule that only refs,
JSON scalars and containers cross. Both sides run on top of the same real core code.
Every diffusion call is recorded, with its arguments and result by digest, so the two call sequences can be compared.
"""
from __future__ import annotations

import hashlib
import math

import torch
import torch.nn.functional as F

CALLS: list = []      # diffusion and VAE calls, comparable between V1 and V2
BOUNDARY: list = []   # V2-only host-call arguments, for the report


def digest(value) -> str:
    t = torch.as_tensor(value).detach().cpu().contiguous()
    return hashlib.sha256(t.numpy().tobytes()).hexdigest()[:16] + f":{tuple(t.shape)}:{str(t.dtype)}"


def text_tag(value) -> float:
    return (sum((i + 1) * ord(c) for i, c in enumerate(str(value))) % 997) / 997.0


def cond_tag(cond) -> float:
    total = 0.0
    for row in cond:
        total += float(torch.as_tensor(row[0]).double().sum())
        total += text_tag(sorted((k, repr(v)) for k, v in row[1].items() if k in ("area", "strength")))
    return round(total, 6)


# --------------------------------------------------------------------------------------------------------------------
# Model stand-in: real latent formats and a real discrete sampling schedule, no weights
# --------------------------------------------------------------------------------------------------------------------
class FakeBaseModel:
    def __init__(self, family: str, tag: float):
        import comfy.latent_formats
        import comfy.model_sampling

        class _Sampling(comfy.model_sampling.ModelSamplingDiscrete, comfy.model_sampling.EPS):
            pass

        self.family = family
        self.tag = float(tag)
        self.latent_format = {"sdxl": comfy.latent_formats.SDXL, "flux": comfy.latent_formats.Flux}.get(
            family, comfy.latent_formats.SD15)()
        self.model_sampling = _Sampling(None)

    def process_latent_out(self, latent):
        return self.latent_format.process_out(latent)

    def process_latent_in(self, latent):
        return self.latent_format.process_in(latent)


class FakePatcher:
    """What comfy.sample.sample, comfy.samplers.KSampler and the original's sample_common read from a ModelPatcher."""

    def __init__(self, base, load_device=None, offload_device=None, model_options=None):
        self.model = base
        self.model_options = {} if model_options is None else model_options
        self.load_device = torch.device("cpu")

    def get_model_object(self, name):
        return getattr(self.model, name)

    def model_dtype(self):
        return torch.float32

    def memory_required(self, shape):
        return 0


def fake_inner_sample(model, noise, positive, negative, cfg, device, sampler, sigmas, model_options={},
                      latent_image=None, denoise_mask=None, callback=None, disable_pbar=False, seed=None):
    """Stand-in for comfy.samplers.sample: every argument moves the result; the mask is prepared by core."""
    import comfy.sampler_helpers

    sig = sigmas.detach().cpu().float()
    base = latent_image.detach().cpu().float()
    n = noise.detach().cpu().float()
    mask = None
    if denoise_mask is not None:
        mask = comfy.sampler_helpers.prepare_mask(denoise_mask, noise.shape, "cpu").float()
    name = getattr(getattr(sampler, "sampler_function", None), "__name__", repr(sampler))
    ptag, ntag = cond_tag(positive), cond_tag(negative)
    g = torch.Generator().manual_seed(int(seed))
    x = base + n * sig[0]
    for i in range(len(sig) - 1):
        step = float(sig[i] - sig[i + 1]) / (1.0 + float(sig[i]))
        eps = torch.randn(tuple(x.shape), generator=g)
        x = (x * (1.0 - 0.1 * step) + 0.01 * float(cfg) + 0.003 * ptag - 0.002 * ntag + 0.004 * text_tag(name)
             + 0.005 * model.model.tag + 0.01 * eps * float(sig[i + 1]))
        if mask is not None:
            x = x * mask + (base + n * sig[i + 1]) * (1.0 - mask)
    x = x.contiguous()
    CALLS.append(("sample", name, [round(float(s), 6) for s in sig], round(float(cfg), 6), int(seed), ptag, ntag,
                  digest(noise), digest(latent_image), digest(mask) if mask is not None else None, digest(x)))
    return x


def install_core_fakes():
    """Both sides: the diffusion step is the stand-in; loading models is a no-op."""
    import comfy.model_management
    import comfy.samplers

    comfy.samplers.sample = fake_inner_sample
    comfy.model_management.load_models_gpu = lambda *a, **k: None
    comfy.model_management.load_model_gpu = lambda *a, **k: None


# --------------------------------------------------------------------------------------------------------------------
# VAE stand-in (both sides)
# --------------------------------------------------------------------------------------------------------------------
def encode(pixels):
    """VAE encode stand-in: crop to multiples of 8, 8x8 average pool, 4 channels."""
    x = torch.as_tensor(pixels)[..., :3].movedim(-1, 1).float()
    h, w = x.shape[-2] // 8 * 8, x.shape[-1] // 8 * 8
    pooled = F.avg_pool2d(x[..., :h, :w], 8)
    out = torch.cat([pooled * 2 - 1, pooled.mean(dim=1, keepdim=True)], dim=1).contiguous()
    CALLS.append(("encode", digest(pixels), digest(out)))
    return out


def decode(latent, tiled=False):
    """VAE decode stand-in: bilinear x8 upsample of 3 latent channels to BHWC in [0, 1]."""
    x = torch.as_tensor(latent)[:, :3].float()
    img = ((F.interpolate(x, scale_factor=8, mode="bilinear", align_corners=False) + 1) / 2).clamp(0, 1)
    img = img.movedim(1, -1).contiguous()
    if tiled:
        img = (img * 0.999 + 0.0005).clamp(0, 1).contiguous()
    CALLS.append(("decode", "tiled" if tiled else "plain", digest(latent), digest(img)))
    return img


class V1Vae:
    """What core's VAEDecode / VAEEncode / VAEDecodeTiled nodes call on a VAE."""

    def decode(self, samples):
        return decode(samples)

    def encode(self, pixels):
        return encode(pixels)

    def temporal_compression_decode(self):
        return None

    def spacial_compression_decode(self):
        return 8

    def decode_tiled(self, samples, tile_x=None, tile_y=None, overlap=None, tile_t=None, overlap_t=None):
        BOUNDARY.append(("v1_decode_tiled", tile_x, tile_y, overlap, tile_t, overlap_t))
        return decode(samples, tiled=True)


# --------------------------------------------------------------------------------------------------------------------
# V2 side: fake refs with the host's behaviour
# --------------------------------------------------------------------------------------------------------------------
_JSON = (str, int, float, bool, type(None))


def wire_check(value, where="argument"):
    """transport/wire.py encode: refs, JSON scalars and containers cross; anything else is a hard error."""
    if isinstance(value, Ref) or isinstance(value, _JSON):
        return
    if isinstance(value, (list, tuple)):
        for v in value:
            wire_check(v, where)
        return
    if isinstance(value, dict):
        for v in value.values():
            wire_check(v, where)
        return
    raise TypeError(f"value of type {type(value).__name__} cannot cross the guest wire; "
                    f"only refs, callbacks, JSON scalars and containers are marshalable ({where})")


def _crossed(value):
    """A value stored on or read back from the host is a copy, as across the real wire."""
    if isinstance(value, torch.Tensor):
        return value.detach().clone()
    if isinstance(value, dict):
        return {k: _crossed(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_crossed(v) for v in value]
    return value


class Ref:
    _count = 0

    def __init__(self, kind, value=None):
        Ref._count += 1
        self.id = f"{kind}-{Ref._count}"
        self.kind = kind
        self._value = value

    async def value(self):
        return _crossed(self._value)

    async def raw(self):
        return _crossed(self._value)


class LatentRef(Ref):
    def __init__(self, value):
        assert isinstance(value, dict) and isinstance(value.get("samples"), torch.Tensor), "LATENT must be a dict"
        super().__init__("LATENT", _crossed(value))

    @classmethod
    async def from_value(cls, value):
        return cls(value)

    async def random_noise(self, seed, source="cpu", batch_size=None):
        import comfy.sample
        assert source == "cpu"
        value = self._value
        return TensorRef(comfy.sample.prepare_noise(value["samples"], int(seed), value.get("batch_index")))


class TensorRef(Ref):
    def __init__(self, value):
        super().__init__("TENSOR", _crossed(value))

    @classmethod
    async def _from_raw(cls, value):
        return cls(value)


class ImageRef(Ref):
    def __init__(self, value):
        t = torch.as_tensor(value)
        assert t.ndim == 4 and t.shape[-1] in (1, 3, 4), f"IMAGE must be BHWC, got {tuple(t.shape)}"
        super().__init__("IMAGE", t)

    @classmethod
    async def _from_raw(cls, value):
        return cls(value)

    async def rgb(self):
        return ImageRef(self._value[..., :3])


class CondRef(Ref):
    def __init__(self, cond):
        super().__init__("CONDITIONING", cond)

    async def has_spatial_metadata(self):
        spatial = {"area", "mask", "gligen", "control", "reference_latents"}
        return any(spatial.intersection(row[1]) for row in self._value)

    async def spatial_crop(self, **kwargs):
        """Only the previous V2 (negative control) calls this; without spatial metadata a crop is the same cond."""
        assert not await self.has_spatial_metadata()
        BOUNDARY.append(("cond_spatial_crop", tuple(sorted(kwargs.items()))))
        return CondRef(self._value)


class ModelRef(Ref):
    def __init__(self, patcher):
        super().__init__("MODEL", patcher)

    async def family(self):
        return self._value.model.family

    async def latent_scale_factor(self):
        return float(self._value.model.latent_format.scale_factor)

    async def sampling_sigma_delta(self, *, steps, sampler_name, scheduler, start_step, end_step, denoise=1.0,
                                   sigma_schedule=None):
        """The host op (comfy_api latest _sdk.py _model_sampling_sigma_delta), on the same core code."""
        import comfy.samplers
        params = {"steps": int(steps), "sampler_name": str(sampler_name), "scheduler": str(scheduler),
                  "start_step": int(start_step), "end_step": int(end_step), "denoise": float(denoise),
                  "sigma_schedule": sigma_schedule}
        wire_check(params, "model.sampling_sigma_delta")
        BOUNDARY.append(("sampling_sigma_delta", tuple(sorted((k, repr(v)) for k, v in params.items()))))
        steps, start_step, end_step, denoise = (params["steps"], params["start_step"], params["end_step"],
                                                params["denoise"])
        if not 1 <= steps <= 10000:
            raise ValueError("steps must be in [1, 10000]")
        if not 0 <= start_step <= end_step <= steps:
            raise ValueError("sigma step range is outside the schedule")
        if not math.isfinite(denoise) or not 0.0 <= denoise <= 1.0:
            raise ValueError("denoise must be finite and in [0, 1]")
        if sampler_name not in comfy.samplers.KSampler.SAMPLERS:
            raise ValueError("unknown sampler name")
        if scheduler not in comfy.samplers.KSampler.SCHEDULERS:
            raise ValueError("unknown scheduler name")
        value = self._value
        if sigma_schedule is None:
            sigmas = comfy.samplers.KSampler(value, steps=steps, device=value.load_device, sampler=sampler_name,
                                             scheduler=scheduler, denoise=denoise,
                                             model_options=value.model_options).sigmas
        else:
            total_steps = steps if denoise > 0.9999 else int(steps / denoise)
            sigmas = schedule_sigmas(sigma_schedule, total_steps)
            if denoise <= 0.9999:
                sigmas = sigmas[-(steps + 1):]
        scale = float(value.model.latent_format.scale_factor)
        return float((sigmas[start_step] - sigmas[end_step]).detach().cpu()) / scale


def schedule_sigmas(sigma_schedule, total_steps):
    """The host's typed sigma schedules (host.py _h_sample run_sampling)."""
    kind = sigma_schedule.get("kind")
    if kind == "gits":
        assert set(sigma_schedule) == {"kind", "coeff", "denoise"}
        from comfy_extras.nodes_gits import GITSScheduler
        return GITSScheduler.execute(sigma_schedule["coeff"], total_steps, sigma_schedule["denoise"])[0]
    if kind == "ays":
        assert set(sigma_schedule) == {"kind", "model_type", "denoise"}
        from comfy_extras.nodes_align_your_steps import AlignYourStepsScheduler
        return AlignYourStepsScheduler().get_sigmas(sigma_schedule["model_type"], total_steps,
                                                    sigma_schedule["denoise"])[0]
    raise ValueError("sample sigma_schedule kind is not supported")


class V2Vae(Ref):
    def __init__(self):
        super().__init__("VAE")

    async def encode(self, image):
        assert isinstance(image, ImageRef)
        return LatentRef({"samples": encode(image._value)})

    async def decode(self, latent, *, allow_extended_range=False):
        assert isinstance(latent, LatentRef) and allow_extended_range is False
        return ImageRef(decode(latent._value["samples"]))

    async def decode_tiled(self, latent, tile_size=512, overlap=64, temporal_size=64, temporal_overlap=8, *,
                           allow_extended_range=False):
        assert isinstance(latent, LatentRef) and allow_extended_range is False
        BOUNDARY.append(("v2_decode_tiled", int(tile_size), int(overlap), int(temporal_size), int(temporal_overlap)))
        return ImageRef(decode(latent._value["samples"], tiled=True))


class V2Ctx:
    async def sample(self, latent, steps, on_step=None, *, model=None, positive=None, negative=None, cfg=8.0, seed=0,
                     sampler_name="euler", scheduler="normal", denoise=1.0, steer_cfg=False, disable_noise=False,
                     start_step=None, last_step=None, force_full_denoise=False, sampler=None, noise=None,
                     sigma_factor=1.0, sigma_schedule=None, sigmas=None, guider=None, cache=None,
                     return_denoised=False, fix_empty_latent=True):
        """Guest _RemoteSample marshalling, then the host's _h_sample on the same core code (comfy.sample.sample)."""
        import comfy.sample
        import comfy.samplers
        parameters = {
            "latent": latent, "steps": int(steps), "on_step": on_step, "model": model, "positive": positive,
            "negative": negative, "cfg": float(cfg), "seed": int(seed), "sampler_name": str(sampler_name),
            "scheduler": str(scheduler), "denoise": float(denoise), "steer_cfg": bool(steer_cfg),
            "disable_noise": bool(disable_noise), "start_step": start_step, "last_step": last_step,
            "force_full_denoise": bool(force_full_denoise), "sampler": sampler, "noise": noise,
            "sigma_factor": float(sigma_factor), "sigma_schedule": sigma_schedule, "sigmas": sigmas,
            "guider": guider, "cache": cache, "return_denoised": return_denoised}
        wire_check(parameters, "ctx.sample")
        BOUNDARY.append(("ctx.sample", tuple(sorted((k, v.id if isinstance(v, Ref) else repr(v))
                                                    for k, v in parameters.items()))))
        assert on_step is None and sampler is None and sigmas is None and guider is None and cache is None
        assert not return_denoised and parameters["sigma_factor"] == 1.0
        steps, seed, cfg, denoise = parameters["steps"], parameters["seed"], parameters["cfg"], parameters["denoise"]
        if not 1 <= steps <= 10000:
            raise ValueError("sample steps must be in [1, 10000]")
        if not 0 <= seed <= (1 << 64) - 1:
            raise ValueError("sample seed must be in the unsigned 64-bit range")
        if not math.isfinite(denoise) or not 0.0 <= denoise <= 1.0:
            raise ValueError("sample denoise must be finite and in [0, 1]")
        start_step = None if start_step is None else int(start_step)
        last_step = None if last_step is None else int(last_step)
        if start_step is not None and not 0 <= start_step <= 10000:
            raise ValueError("sample start_step must be in [0, 10000]")
        if last_step is not None and not 0 <= last_step <= 10000:
            raise ValueError("sample last_step must be in [0, 10000]")
        if start_step is not None and last_step is not None and start_step > last_step:
            raise ValueError("sample start_step must not exceed last_step")
        if noise is not None and disable_noise:
            raise ValueError("sample explicit noise cannot be combined with disable_noise")
        if sampler_name not in comfy.samplers.KSampler.SAMPLERS:
            raise ValueError(f"unknown sampler {sampler_name!r}")
        if scheduler not in comfy.samplers.KSampler.SCHEDULERS:
            raise ValueError(f"unknown scheduler {scheduler!r}")
        model_obj = model._value
        latent_dict = latent._value
        latent_image = latent_dict["samples"]
        if fix_empty_latent:
            latent_image = comfy.sample.fix_empty_latent_channels(model_obj, latent_image)
        if noise is not None:
            noise_obj = noise._value
            assert isinstance(noise_obj, torch.Tensor) and tuple(noise_obj.shape) == tuple(latent_image.shape)
            sampling_noise = noise_obj.to(device="cpu", dtype=latent_image.dtype).clone()
        else:
            sampling_noise = (torch.zeros_like(latent_image) if bool(disable_noise)
                              else comfy.sample.prepare_noise(latent_image, seed, latent_dict.get("batch_index")))
        custom_sigmas = None
        if sigma_schedule is not None:
            if denoise <= 0.0:
                return LatentRef(dict(latent_dict))
            total_steps = steps if denoise > 0.9999 else int(steps / denoise)
            if total_steps < 2:
                raise ValueError("custom sigma schedule needs at least 2 steps")
            custom_sigmas = schedule_sigmas(sigma_schedule, total_steps)
            if denoise <= 0.9999:
                custom_sigmas = custom_sigmas[-(steps + 1):]
            custom_sigmas = custom_sigmas * 1.0
        result = comfy.sample.sample(
            model_obj, sampling_noise, steps, cfg, sampler_name, scheduler, positive._value, negative._value,
            latent_image, denoise=denoise, disable_noise=disable_noise, start_step=start_step, last_step=last_step,
            force_full_denoise=force_full_denoise, noise_mask=latent_dict.get("noise_mask"), sigmas=custom_sigmas,
            callback=None, disable_pbar=True, seed=seed)
        out = dict(latent_dict)
        out["samples"] = result
        return LatentRef(out)


CTX = V2Ctx()


def reset():
    CALLS.clear()
    BOUNDARY.clear()
