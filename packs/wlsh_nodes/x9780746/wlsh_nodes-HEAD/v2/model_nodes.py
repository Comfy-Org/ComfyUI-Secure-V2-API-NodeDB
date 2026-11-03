"""Secure Nodes V2: wlsh_nodes' checkpoint loader and advanced sampler (upstream wallish77/wlsh_nodes 97807467).

- Checkpoint Loader w/Name (wlsh_nodes.py:40-69) loads through the host's checkpoint loader, which makes the same
  Core call (comfy.sd.load_checkpoint_guess_config with VAE and CLIP, and the embeddings folders). The name output is
  the original's own parse of the menu name. The menu is filled by the host from its checkpoints folder.
- KSamplerAdvanced (WLSH) (wlsh_nodes.py:72-110) samples through the host's sampler with the original's arguments,
  which is Core's common_ksampler on the host, and returns the same INFO dict. Like upstream, it never forces a full
  denoise (both branches set force_full_denoise to False, :100-102).
"""
from __future__ import annotations

from typing import Any

from comfy_api.latest import io, sdk

from ._secure_runtime import schema_for


def parse_name(ckpt_name):
    """wlsh_nodes.py:63-69 (WLSH_Checkpoint_Loader_Model_Name.parse_name), verbatim."""
    path = ckpt_name
    filename = path.split("/")[-1]
    filename = filename.split(".")[:-1]
    filename = ".".join(filename)
    return filename


class CheckpointLoaderWithNameV2(io.ComfyNode):
    """wlsh_nodes.py:40-69 (WLSH_Checkpoint_Loader_Model_Name.load_checkpoint)."""
    SDK_REFS = True
    SDK_PERMISSIONS = ("models",)

    @classmethod
    def define_schema(cls):
        return schema_for("Checkpoint Loader w/Name (WLSH)")

    @classmethod
    async def execute(cls, ckpt_name: str = "") -> io.NodeOutput:
        name = parse_name(ckpt_name)
        model, clip, vae = await sdk.ctx().models.load_checkpoint(ckpt_name)
        return io.NodeOutput(model, clip, vae, name)


class KSamplerAdvancedV2(io.ComfyNode):
    """wlsh_nodes.py:72-110 (WLSH_KSamplerAdvanced.sample)."""
    SDK_REFS = True
    SDK_PERMISSIONS = ("sample",)

    @classmethod
    def define_schema(cls):
        return schema_for("KSamplerAdvanced (WLSH)")

    @classmethod
    async def execute(cls, model: Any = None, add_noise: str = "enable", seed: int = 0, steps: int = 20,
                      cfg: float = 8.0, sampler_name: str = "euler", scheduler: str = "normal", positive: Any = None,
                      negative: Any = None, latent_image: Any = None, start_at_step: int = 0,
                      end_at_step: int = 10000, return_with_leftover_noise: str = "disable",
                      denoise: float = 1.0) -> io.NodeOutput:
        force_full_denoise = False
        if return_with_leftover_noise == "enable":
            force_full_denoise = False
        disable_noise = False
        if add_noise == "disable":
            disable_noise = True

        info = {"Seed: ": seed, "Steps: ": steps, "CFG scale: ": cfg, "Sampler: ": sampler_name,
                "Scheduler: ": scheduler, "Start at step: ": start_at_step, "End at step: ": end_at_step,
                "Denoising strength: ": denoise}
        start_step = start_at_step
        if start_at_step > end_at_step:
            # Core's KSampler returns the latent unsampled when the start is past the end (comfy/samplers.py,
            # KSampler.sample). The host checks start <= last, so ask for the same empty step range at the end.
            start_step = end_at_step
        samples = await sdk.ctx().sample(
            latent_image, steps, model=model, positive=positive, negative=negative, cfg=cfg, seed=seed,
            sampler_name=sampler_name, scheduler=scheduler, denoise=denoise, disable_noise=disable_noise,
            start_step=start_step, last_step=end_at_step, force_full_denoise=force_full_denoise)
        return io.NodeOutput(samples, info)


CONVERTED = {
    "Checkpoint Loader w/Name (WLSH)": CheckpointLoaderWithNameV2,
    "KSamplerAdvanced (WLSH)": KSamplerAdvancedV2,
}

__all__ = ["CONVERTED", "parse_name"]
