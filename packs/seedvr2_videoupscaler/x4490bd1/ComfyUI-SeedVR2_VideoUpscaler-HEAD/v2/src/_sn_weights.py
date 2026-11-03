"""Declared, sha256-pinned SeedVR2 weights for Secure Nodes V2.

Every safetensors checkpoint in the pack's model registry (src/utils/model_registry.py) is an
on-demand weight declaration here, with the registry's sha256. The secure upscaler node fetches
the two checkpoints a run needs through the SDK and supplies their tensors. Upstream's loader
(load_quantized_state_dict) reads them in place of a file on disk, and download_weight only checks
that they were supplied.

The pack's two text embeddings (pos_emb.pt and neg_emb.pt) are declared safetensors weights holding
the same tensors. Every run needs both, so they are required rather than on demand, and upstream's
load_text_embeddings receives their tensors instead of reading the pack's files.

GGUF checkpoints are not supplied: the pack's GGUF reader needs a file path, and a guest receives
tensors. Those options are refused by name.
"""

import contextlib
import contextvars
import os

from comfy_api.latest import sdk

NUMZ = ("numz/SeedVR2_comfyUI", "09ced71023636e9bc8cdf9cdecfb2625d1e691e8")
AINVFX = ("AInVFX/SeedVR2_comfyUI", "ac66d6d98fa49975d893b58c55bff7677191c862")

# filename -> (repo_id, revision, folder, sha256), in upstream registry order.
FILES = {
    "seedvr2_ema_3b_fp8_e4m3fn.safetensors": (*NUMZ, "diffusion_models",
        "3bf1e43ebedd570e7e7a0b1b60d6a02e105978f505c8128a241cde99a8240cff"),
    "seedvr2_ema_3b_fp16.safetensors": (*NUMZ, "diffusion_models",
        "2fd0e03a3dad24e07086750360727ca437de4ecd456f769856e960ae93e2b304"),
    "seedvr2_ema_7b_fp8_e4m3fn_mixed_block35_fp16.safetensors": (*AINVFX, "diffusion_models",
        "3d68b5ec0b295ae28092e355c8cad870edd00b817b26587d0cb8f9dd2df19bb2"),
    "seedvr2_ema_7b_fp16.safetensors": (*NUMZ, "diffusion_models",
        "7b8241aa957606ab6cfb66edabc96d43234f9819c5392b44d2492d9f0b0bbe4a"),
    "seedvr2_ema_7b_sharp_fp8_e4m3fn_mixed_block35_fp16.safetensors": (*AINVFX, "diffusion_models",
        "0d2c5b8be0fda94351149c5115da26aef4f4932a7a2a928c6f184dda9186e0be"),
    "seedvr2_ema_7b_sharp_fp16.safetensors": (*NUMZ, "diffusion_models",
        "20a93e01ff24beaeebc5de4e4e5be924359606c356c9c51509fba245bd2d77dd"),
    "ema_vae_fp16.safetensors": (*NUMZ, "vae",
        "20678548f420d98d26f11442d3528f8b8c94e57ee046ef93dbb7633da8612ca1"),
}
GGUF = ("seedvr2_ema_3b-Q4_K_M.gguf", "seedvr2_ema_3b-Q8_0.gguf", "seedvr2_ema_7b-Q4_K_M.gguf",
        "seedvr2_ema_7b_sharp-Q4_K_M.gguf")

WEIGHTS = {
    name: sdk.HuggingFaceWeight(repo_id=repo, filename=name, folder=folder, revision=revision,
                                sha256=digest, on_demand=True)
    for name, (repo, revision, folder, digest) in FILES.items()
}

# The pack's text embeddings: pack file -> (declared filename, tensor key, sha256).
EMBEDDINGS_REPO = ("gerald-test-local/seedvr2-embeddings-converted", "65f24803292a0815ee1304d97d10906318f324d4")
EMBEDDINGS = {
    "pos_emb.pt": ("pos_emb.safetensors", "pos_emb",
                   "dd2c63c6bd8df2f0c7e5baa4e71616592f6fb67b54068c05588107b4a1a465c9"),
    "neg_emb.pt": ("neg_emb.safetensors", "neg_emb",
                   "1f6afefcb104aa92d2d9ecdf6eb7999bcf1840d38626c241db1a1dd6f22563d0"),
}
EMBEDDING_WEIGHTS = {
    name: sdk.HuggingFaceWeight(repo_id=EMBEDDINGS_REPO[0], filename=filename, folder="embeddings",
                                revision=EMBEDDINGS_REPO[1], sha256=digest)
    for name, (filename, _key, digest) in EMBEDDINGS.items()
}


class WeightsNotBrokered(RuntimeError):
    """A checkpoint this Secure Nodes V2 conversion does not supply."""


def gguf_refusal(name):
    return (f"seedvr2_videoupscaler: the GGUF checkpoint {name!r} is not available in Secure Nodes "
            "V2 yet. Its reader needs a model file on disk, and a Secure Nodes guest receives "
            "verified tensors, not files. Use a .safetensors model "
            "(e.g. seedvr2_ema_3b_fp8_e4m3fn.safetensors).")


async def _fetch(weight):
    """Install (or reuse) a declared weight, check its digest, return its tensors."""
    ctx = sdk.ctx()
    installed = await ctx.models.download_huggingface_weights(
        repo_id=weight.repo_id, filename=weight.filename, folder=weight.folder,
        revision=weight.revision, sha256=weight.sha256)
    asset = await ctx.assets.resolve(weight.folder, installed)
    if await ctx.assets.digest(asset) != weight.sha256:
        raise WeightsNotBrokered(
            f"seedvr2_videoupscaler: {weight.filename} digest differs from the declaration")
    return await ctx.assets.load_state_dict(asset)


async def load(name):
    """The declared checkpoint's tensors."""
    if name in GGUF:
        raise WeightsNotBrokered(gguf_refusal(name))
    weight = WEIGHTS.get(name)
    if weight is None:
        raise WeightsNotBrokered(
            f"seedvr2_videoupscaler: {name!r} is not one of the declared, verified SeedVR2 "
            "checkpoints of this Secure Nodes V2 conversion")
    return await _fetch(weight)


async def load_embeddings():
    """Both declared text embeddings' tensors, keyed by the pack's file names."""
    tensors = {}
    for name, weight in EMBEDDING_WEIGHTS.items():
        key = EMBEDDINGS[name][1]
        state = await _fetch(weight)
        if list(state) != [key]:
            raise WeightsNotBrokered(
                f"seedvr2_videoupscaler: {weight.filename} must hold exactly the tensor {key!r}")
        tensors[name] = state[key]
    return tensors


# One upscaler call's supplied tensors, keyed by file name. Each checkpoint is handed to upstream's
# loader once and then dropped, so it is not held while the model runs.
_SUPPLIED = contextvars.ContextVar("seedvr2_supplied_state_dicts", default=None)


@contextlib.contextmanager
def supplied(state_dicts):
    token = _SUPPLIED.set(dict(state_dicts))
    try:
        yield
    finally:
        _SUPPLIED.reset(token)


def require_supplied(*names):
    current = _SUPPLIED.get() or {}
    missing = [name for name in names if name not in current]
    if missing:
        raise WeightsNotBrokered(
            f"seedvr2_videoupscaler: no brokered weights were supplied for {missing}")


def brokered_state_dict(checkpoint_path, device="cpu"):
    """Upstream reads load_safetensors_file(checkpoint_path, device=...); this returns the same
    tensors from the broker, moved to the same device."""
    current = _SUPPLIED.get() or {}
    name = os.path.basename(checkpoint_path)
    if name not in current:
        raise WeightsNotBrokered(
            f"seedvr2_videoupscaler: no brokered weights were supplied for {name!r}")
    state = current.pop(name)
    return {key: value.to(device) for key, value in state.items()}


def brokered_tensor(filename):
    """Upstream torch.loads <pack>/<filename>; this returns a fresh copy of the same tensor from the
    broker. The entry is kept, because upstream loads the embeddings again if a run drops them."""
    current = _SUPPLIED.get() or {}
    if filename not in current:
        raise WeightsNotBrokered(
            f"seedvr2_videoupscaler: no brokered tensor was supplied for {filename!r}")
    return current[filename].clone()
