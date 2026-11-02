"""Declared, verified weights for the converted frame-interpolation nodes.

Upstream downloaded its checkpoints at run time from GitHub releases or
Hugging Face mirrors, unpinned and unhashed (vfi_utils.py:14-40, :80-95). It
then unpickled them (`torch.load(weights_only=False)` for RIFE, `torch.load`
for IFRNet) or loaded a TorchScript archive (`torch.jit.load` for FILM).

Here, each pinned upstream file (source sha256 below) was converted offline by
GERALD to safetensors in an isolated, network-less container. Each conversion
was verified tensor-equal (names, dtypes, shapes, values). Receipts:
GERALD-CONVERSION-RECEIPTS-20261102.jsonl (sha 0ded1dfe...).
- RIFE, IFRNet: loaded with weights_only=True.
- FILM: the TorchScript module's state_dict.
A guest receives the tensors through the brokered asset API only.

PLACEHOLDER HOSTING: REPO_ID and REVISION name GERALD's test-runtime registry
copies, not a public repository. Production hosting needs Ben's decision; see
HANDOFF.md.
"""

import contextlib
import contextvars

from comfy_api.latest import sdk

REPO_ID = "gerald-test-local/frame-interpolation-converted"  # PLACEHOLDER: test runtime only
REVISION = "0ded1dfec262aa44342e4d437ff2522fbb9f626c"          # PLACEHOLDER: receipts sha, first 40 hex
FOLDER = "frame_interpolation"

# (upstream model type folder, upstream ckpt_name) -> (converted file, sha256, upstream source sha256)
FILES = {
    ("rife", "sudo_rife4_269.662_testV1_scale1.pth"): (
        "sudo_rife4_269.662_testV1_scale1.safetensors",
        "94c95053352974cfc4b1c14e1bc2be49c94dd9280bfac0d539fa3558a66f1ba5",
        "1c9dff599a1c05c38cdc52930a739e7144ce8210fdd098a364e0155c1d23c27c"),
    ("rife", "rife47.pth"): (
        "rife47.safetensors",
        "e9066087e39b287445fe1575d3ad83e331b3f97c98a208f1131c26d67b9cdc80",
        "6a8a825ab2750558bdd20dcced386fd82b7222c7ba58c11d3b611d9c44f1be63"),
    ("rife", "rife49.pth"): (
        "rife49.safetensors",
        "ee9d43496be4a7e77da40b0aaee3f68e1ee94c51f74b4a09d612836430fa36d9",
        "e55fd00f3cc184e3c65961f4bb827a9da022e78eed36b055242c0ac30000d533"),
    ("rife", "rife417.pth"): (
        "rife417.safetensors",
        "591e407203ffda374c150637500bba222d034292db56531293552bcfe16c3b92",
        "f6b1561354dda3b31606190cba1d1009ea001558c1b9c9cef2d03939bb381ee5"),
    ("rife", "rife426.pth"): (
        "rife426.safetensors",
        "89c7efdcd47ffca3df50cab605d390e5ca474040ad5186bd6bde1abd841904cf",
        "606421fe2148a9fdeca14e58d94dc339e87b87e0ebcc5dec84a50d6f488cfe7b"),
    ("film", "film_net_fp32.pt"): (
        "film_net_fp32.safetensors",
        "17f5d86e17dd6d0e424dc0d28042541b206ceac6b030e8b27de0ea2011b17646",
        "10aadc0d25ad586e3af7dd7703f75ec1186fbfe2e11c0d219d30ecfe2db10aa3"),
    ("ifrnet", "IFRNet_S_Vimeo90K.pth"): (
        "IFRNet_S_Vimeo90K.safetensors",
        "99d5826fc3d9cc6b4f11ba6b9dfe2b2ec38423e7a362d471b03991df13aed321",
        "be31e04898d85b7ce3991d941d4399ab0bd775b07c20023377ea5226e6522571"),
    ("ifrnet", "IFRNet_L_Vimeo90K.pth"): (
        "IFRNet_L_Vimeo90K.safetensors",
        "87929f1fb224692928d7312b4ebae83b0171c2a4527e7927903fbca2f6ad1847",
        "b5116185ad5fa7a06ae9b0c219b345a2808d598c9853eb2fb77c6cf5801a6219"),
}

WEIGHTS = {
    key: sdk.HuggingFaceWeight(
        repo_id=REPO_ID, filename=filename, folder=FOLDER, revision=REVISION,
        sha256=digest, on_demand=True)
    for key, (filename, digest, _source) in FILES.items()
}


class WeightsNotBrokered(RuntimeError):
    """A checkpoint this Secure Nodes V2 conversion does not supply."""


def declared_for(model_type):
    """The on-demand weight declarations one node is allowed to request."""
    return tuple(weight for (kind, _name), weight in WEIGHTS.items() if kind == model_type)


async def load(model_type, ckpt_name):
    """Install (or reuse) the declared file, check its digest, return its tensors."""
    weight = WEIGHTS.get((model_type, ckpt_name))
    if weight is None:
        raise WeightsNotBrokered(
            f"comfyui-frame-interpolation: {model_type}/{ckpt_name} is not one of the "
            "declared, verified checkpoints of this Secure Nodes V2 conversion")
    ctx = sdk.ctx()
    installed = await ctx.models.download_huggingface_weights(
        repo_id=weight.repo_id, filename=weight.filename, folder=weight.folder,
        revision=weight.revision, sha256=weight.sha256)
    asset = await ctx.assets.resolve(weight.folder, installed)
    if await ctx.assets.digest(asset) != weight.sha256:
        raise WeightsNotBrokered(
            f"comfyui-frame-interpolation: {weight.filename} digest differs from the declaration")
    return await ctx.assets.load_state_dict(asset)


# The async node loads the tensors through the broker, then calls upstream's
# synchronous node body. That body asks for them by (model type, ckpt name) at
# the line where it used to download and unpickle. Scoped to one call.
_SUPPLIED = contextvars.ContextVar("frame_interpolation_state_dicts", default=None)


@contextlib.contextmanager
def supplied(model_type, ckpt_name, state_dict):
    token = _SUPPLIED.set({(model_type, ckpt_name): state_dict})
    try:
        yield
    finally:
        _SUPPLIED.reset(token)


def brokered_state_dict(model_type, ckpt_name):
    loaded = _SUPPLIED.get()
    if not loaded or (model_type, ckpt_name) not in loaded:
        raise WeightsNotBrokered(
            f"comfyui-frame-interpolation: no brokered weights were supplied for "
            f"{model_type}/{ckpt_name}")
    return loaded[(model_type, ckpt_name)]
