import torch
import torch.nn.functional as F
from contextlib import nullcontext

from comfy_api.latest import io, sdk

from .depth_anything_v2.dpt import DepthAnythingV2

# Upstream downloaded weights with an unpinned ``snapshot_download`` into
# ``models/depthanything`` and read the file back off disk. Neither half
# survives: a guest has no filesystem, and an unpinned download is not a
# reproducible artifact.
#
# The purpose does survive, in the ordinary declared-weight shape used by the
# Impact Subpack and Florence2 conversions: every checkpoint this node offers
# is declared below with a pinned repository revision and a SHA-256, fetched on
# demand, verified, and cached once by the host. The architecture stays HERE,
# in the pack, where it already lived.
#
# The digests are the Hugging Face LFS object ids for each file at the pinned
# revision -- the publisher's own hashes, not something computed locally.

_KIJAI = "Kijai/DepthAnythingV2-safetensors"
_KIJAI_REVISION = "5aa7ab578df757d94c743998b157a0204ff29215"
_NAP = "Nap/depth_anything_v2_vitg"
_NAP_REVISION = "0abc42090032bad02d95d47256ba9f4ffd8ebdf0"

_WEIGHTS = {
    name: sdk.HuggingFaceWeight(
        repo_id=repo,
        filename=name,
        # Upstream wrote to an arbitrary models/depthanything
        # directory. The secure catalogue is a fixed host-owned
        # set; depth estimation belongs to geometry_estimation.
        folder="geometry_estimation",
        revision=revision,
        sha256=digest,
        on_demand=True,
    )
    for name, repo, revision, digest in (
        ("depth_anything_v2_vits_fp16.safetensors", _KIJAI, _KIJAI_REVISION,
         "a7c1a8c8cdd7885fb8391069cd1eee789126c8d896f7de6750499b1097f817ea"),
        ("depth_anything_v2_vits_fp32.safetensors", _KIJAI, _KIJAI_REVISION,
         "cb2d537ed6e45921f27f61f0b605dcfafb6b97c7d1a15e551280bdd867605c86"),
        ("depth_anything_v2_vitb_fp16.safetensors", _KIJAI, _KIJAI_REVISION,
         "386758cbd2a2cac62ca62286d3ba810734561b3097d86a585dd3dac357153941"),
        ("depth_anything_v2_vitb_fp32.safetensors", _KIJAI, _KIJAI_REVISION,
         "faf1f5673511fb897525781a177c5001fc790c266cff518b95e516f4912cc42b"),
        ("depth_anything_v2_vitl_fp16.safetensors", _KIJAI, _KIJAI_REVISION,
         "f075a9099f94bae54a5bfe21a1423346429309bae40abb85b9935985b1f35a09"),
        ("depth_anything_v2_vitl_fp32.safetensors", _KIJAI, _KIJAI_REVISION,
         "203aba6a1b551aa6a1818652b92ac9a43a50fdc7daef9780eb265e4ee9c7521e"),
        ("depth_anything_v2_vitg_fp32.safetensors", _NAP, _NAP_REVISION,
         "fe4a9216b261e676f549609f2f2316faabb0ea6a516073f1f22b5afdcf91d515"),
        ("depth_anything_v2_metric_hypersim_vitl_fp32.safetensors", _KIJAI,
         _KIJAI_REVISION,
         "76bc12f47f4fc543d67d4c3b695d09ae5399aa2f212382a204965a9aca4dc8bd"),
        ("depth_anything_v2_metric_vkitti_vitl_fp32.safetensors", _KIJAI,
         _KIJAI_REVISION,
         "eebc4c27a8067bf904c26c51e648dd17d47cada7cff61267393eda06cd8b649b"),
    )
}

# Upstream's dropdown order, preserved: a workflow saves the chosen STRING, so
# reordering is harmless, but the DEFAULT must stay the same entry.
MODEL_NAMES = [
    "depth_anything_v2_vits_fp16.safetensors",
    "depth_anything_v2_vits_fp32.safetensors",
    "depth_anything_v2_vitb_fp16.safetensors",
    "depth_anything_v2_vitb_fp32.safetensors",
    "depth_anything_v2_vitl_fp16.safetensors",
    "depth_anything_v2_vitl_fp32.safetensors",
    "depth_anything_v2_vitg_fp32.safetensors",
    "depth_anything_v2_metric_hypersim_vitl_fp32.safetensors",
    "depth_anything_v2_metric_vkitti_vitl_fp32.safetensors",
]

_MODEL_CONFIGS = {
    'vits': {'encoder': 'vits', 'features': 64,
             'out_channels': [48, 96, 192, 384]},
    'vitb': {'encoder': 'vitb', 'features': 128,
             'out_channels': [96, 192, 384, 768]},
    'vitl': {'encoder': 'vitl', 'features': 256,
             'out_channels': [256, 512, 1024, 1024]},
    'vitg': {'encoder': 'vitg', 'features': 384,
             'out_channels': [1536, 1536, 1536, 1536]},
}

_DTYPES = {
    "bf16": torch.bfloat16,
    "fp16": torch.float16,
    "fp32": torch.float32,
}

# Upstream's DAMODEL carried a live torch module between two nodes. That cannot
# cross a process boundary -- but it never needed to. What the second node
# actually needs is "which checkpoint, at what precision", which is plain data.
# The module is rebuilt (or reused) inside this guest, keyed by that same
# description. The guest process is per-pack and per-tenant, and this cache
# dies with it, so nothing is shared across tenants.
_LOADED: dict[tuple[str, str], object] = {}


def encoder_for(model_name):
    for encoder in ("vitg", "vitl", "vitb", "vits"):
        if encoder in model_name:
            return encoder
    raise ValueError(f"unknown DepthAnythingV2 checkpoint {model_name!r}")


def dtype_name_for(model_name, precision):
    """Upstream's precision resolution, kept exactly.

    ``auto`` follows the FILE's precision; every other choice is explicit.
    """
    if precision == "auto":
        return "fp16" if "fp16" in model_name else "fp32"
    if precision not in _DTYPES:
        raise ValueError(f"unknown precision {precision!r}")
    return precision


def model_config_for(model_name):
    config = dict(_MODEL_CONFIGS[encoder_for(model_name)])
    if "metric" in model_name:
        config["is_metric"] = True
        # Upstream's own thresholds: hypersim is indoor, vkitti outdoor.
        config["max_depth"] = 20.0 if "hypersim" in model_name else 80.0
    return config


async def _build(model_name):
    """Fetch the declared weight, verify it, and construct the architecture."""
    weight = _WEIGHTS[model_name]
    installed = await sdk.ctx().models.download_huggingface_weights(
        repo_id=weight.repo_id,
        filename=weight.filename,
        folder=weight.folder,
        revision=weight.revision,
        sha256=weight.sha256,
    )
    state_dict = await sdk.ctx().assets.load_state_dict(installed)

    model = DepthAnythingV2(**model_config_for(model_name))
    # strict=False matches upstream: the checkpoints carry extra keys.
    model.load_state_dict(state_dict, strict=False)
    model.eval()
    return model


async def _get_model(model_name, dtype_name):
    key = (model_name, dtype_name)
    model = _LOADED.get(key)
    if model is None:
        model = await _build(model_name)
        _LOADED[key] = model
    return model


class DownloadAndLoadDepthAnythingV2Model(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("models", "raw")

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DownloadAndLoadDepthAnythingV2Model",
            display_name="DownloadAndLoadDepthAnythingV2Model",
            category="DepthAnythingV2",
            description=(
                "Models autodownload to `ComfyUI/models/depthanything` from   \n"
                "https://huggingface.co/Kijai/DepthAnythingV2-safetensors/tree/main   \n"
                "   \nfp16 reduces quality by a LOT, not recommended.\n"
            ),
            inputs=[
                io.Combo.Input(
                    "model", options=MODEL_NAMES,
                    default="depth_anything_v2_vitl_fp32.safetensors"),
                io.Combo.Input(
                    "precision", options=["auto", "bf16", "fp16", "fp32"],
                    default="auto", optional=True),
            ],
            outputs=[io.Custom("DAMODEL").Output(display_name="da_v2_model")],
        )

    @classmethod
    async def execute(cls, model, precision="auto") -> io.NodeOutput:
        if model not in _WEIGHTS:
            raise ValueError(
                "DepthAnythingV2 accepts only its declared checkpoints; "
                f"unknown model {model!r}")
        dtype_name = dtype_name_for(model, precision)
        built = await _get_model(model, dtype_name)
        # A wire-safe description, not a live module.
        return io.NodeOutput({
            "model": model,
            "dtype": dtype_name,
            "is_metric": bool(built.is_metric),
        })


class DepthAnything_V2(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("models", "raw", "progress")

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DepthAnything_V2",
            display_name="Depth Anything V2",
            category="DepthAnythingV2",
            description="https://depth-anything-v2.github.io\n",
            inputs=[
                io.Custom("DAMODEL").Input("da_model"),
                io.Image.Input("images"),
            ],
            outputs=[io.Image.Output(display_name="image")],
        )

    @classmethod
    async def execute(cls, da_model, images) -> io.NodeOutput:
        model = await _get_model(da_model["model"], da_model["dtype"])
        dtype = _DTYPES[da_model["dtype"]]

        images = await images.raw()
        return io.NodeOutput(await sdk.ImageRef._from_raw(
            infer(model, images, dtype, bool(da_model["is_metric"]))))


def infer(model, images, dtype, is_metric):
    """Upstream's process() body, unchanged apart from device handling.

    Kept as a module-level function so the differential test can drive exactly
    this code against upstream's on identical inputs.
    """
    B, H, W, C = images.shape
    images = images.permute(0, 3, 1, 2)

    orig_H, orig_W = H, W
    if W % 14 != 0:
        W = W - (W % 14)
    if H % 14 != 0:
        H = H - (H % 14)
    if orig_H % 14 != 0 or orig_W % 14 != 0:
        images = F.interpolate(images, size=(H, W), mode="bilinear")

    # torchvision's Normalize, inlined: the pack should not carry a
    # torchvision dependency for one broadcast subtract-and-divide.
    mean = torch.tensor([0.485, 0.456, 0.406],
                        dtype=images.dtype, device=images.device)
    std = torch.tensor([0.229, 0.224, 0.225],
                       dtype=images.dtype, device=images.device)
    normalized_images = (images - mean.view(1, 3, 1, 1)) / std.view(1, 3, 1, 1)

    out = []
    device = normalized_images.device
    autocast_condition = dtype != torch.float32 and device.type != "mps"
    context = (torch.autocast(device.type, dtype=dtype)
               if autocast_condition else nullcontext())
    with context:
        for img in normalized_images:
            depth = model(img.unsqueeze(0))
            depth = (depth - depth.min()) / (depth.max() - depth.min())
            out.append(depth.cpu())

    depth_out = torch.cat(out, dim=0)
    depth_out = depth_out.unsqueeze(-1).expand(-1, -1, -1, 3).cpu().float()

    final_H = (orig_H // 2) * 2
    final_W = (orig_W // 2) * 2

    if depth_out.shape[1] != final_H or depth_out.shape[2] != final_W:
        depth_out = F.interpolate(
            depth_out.permute(0, 3, 1, 2), size=(final_H, final_W),
            mode="bilinear").permute(0, 2, 3, 1)
    depth_min = depth_out.min()
    depth_max = depth_out.max()
    depth_out = depth_out.sub(depth_min).div(depth_max - depth_min)
    depth_out = depth_out.clamp(0, 1)
    if is_metric:
        depth_out = 1 - depth_out
    return depth_out


NODE_CLASS_MAPPINGS = {
    "DepthAnything_V2": DepthAnything_V2,
    "DownloadAndLoadDepthAnythingV2Model": DownloadAndLoadDepthAnythingV2Model
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "DepthAnything_V2": "Depth Anything V2",
    "DownloadAndLoadDepthAnythingV2Model": "DownloadAndLoadDepthAnythingV2Model"
}
