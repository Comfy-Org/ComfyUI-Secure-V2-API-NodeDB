"""Secure Nodes V2: comfyui-art-venture's AV_LoraLoader and AV_VAELoader (upstream 210dc072, modules/nodes.py:66-107),
ported exactly onto the host's own loaders.

- AV_LoraLoader runs the original's enable and override logic, then Core's LoraLoader.load_lora through the host's
  ``model.apply_lora``. That operation loads the LoRA file with ``load_torch_file(safe_load=True)`` and applies
  ``comfy.sd.load_lora_for_models`` with the same strengths and metadata. Zero strengths return the inputs
  unchanged, as Core does. ``allow_extended_strengths`` lets linked strengths through unchanged, as the original
  does.
- AV_VAELoader runs the original's override logic, then Core's VAELoader.load_vae through ``ctx.models.load_vae``.
- Override names are checked against the host's catalogue (``ctx.assets.list``), as the original checks
  ``folder_paths.get_filename_list``. The warning the original prints is printed the same way.
"""
from __future__ import annotations

from typing import Any

from comfy_api.latest import io, sdk

from .utility_nodes import _FrozenSchema

PREFIX = "comfyui-art-venture"


class OutOfEnvelope(RuntimeError):
    """A path this port cannot take exactly; refused by name."""


async def _catalogue(folder: str, node_id: str) -> list:
    try:
        return await sdk.ctx().assets.list(folder)
    except ValueError as error:  # the host lists at most 4096 names per catalogue
        raise OutOfEnvelope(f"{PREFIX}/{node_id}: the host's {folder} catalogue cannot be listed for the override "
                            f"check ({error})") from None


class AVLoraLoaderV2(_FrozenSchema, io.ComfyNode):
    """modules/nodes.py:85-107, then Core's LoraLoader.load_lora."""
    NODE_ID = "AV_LoraLoader"
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets",)

    @classmethod
    async def execute(cls, model: Any = None, clip: Any = None, lora_name: str = "", strength_model: float = 1.0,
                      strength_clip: float = 1.0, lora_override: str = "None", enabled: bool = True) -> io.NodeOutput:
        if not enabled:
            return io.NodeOutput(model, clip)

        if lora_override != "None":
            if lora_override not in await _catalogue("loras", cls.NODE_ID):
                print(f"Warning: Not found Lora model {lora_override}. Use {lora_name} instead.")
            else:
                lora_name = lora_override

        if strength_model == 0 and strength_clip == 0:
            return io.NodeOutput(model, clip)
        asset = await sdk.ctx().assets.resolve("loras", lora_name)
        patched_model, patched_clip = await model.apply_lora(
            asset, clip, strength_model, strength_clip, allow_extended_strengths=True)
        return io.NodeOutput(patched_model, patched_clip)


class AVVAELoaderV2(_FrozenSchema, io.ComfyNode):
    """modules/nodes.py:66-82, then Core's VAELoader.load_vae."""
    NODE_ID = "AV_VAELoader"
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets", "models")

    @classmethod
    async def execute(cls, vae_name: str = "", vae_override: str = "None") -> io.NodeOutput:
        if vae_override != "None":
            if vae_override not in await _catalogue("vae", cls.NODE_ID):
                print(f"Warning: Not found VAE model {vae_override}. Use {vae_name} instead.")
            else:
                vae_name = vae_override

        return io.NodeOutput(await sdk.ctx().models.load_vae(vae_name))


CONVERTED = {cls.NODE_ID: cls for cls in (AVLoraLoaderV2, AVVAELoaderV2)}

__all__ = ["CONVERTED"]
