"""Tier-1 parity for the loaders: comfyui-art-venture AV_LoraLoader and AV_VAELoader, ORIGINAL vs V2 (gate only, CPU).

No real weights are used. All fixtures are seeded and synthetic, built here:
* MODEL: a tiny SD1.5-shaped UNet;
* CLIP: a tiny SD1 text encoder (Core's SD1 tokenizer files, a 2-layer, width-32 text model);
* LoRA files: built from Core's own LoRA key maps (comfy/lora.py model_lora_keys_unet / model_lora_keys_clip);
* VAE files: TAESD-format state dicts with seeded weights, which Core's VAE recognises by key.
The original runs in-process. V2 runs in a REAL guest with exactly its declared permissions; the host operations
(model.apply_lora, models.load_vae, assets.*) run in this process, as the host would run them.
Compared:
* returned MODEL/CLIP: the same base model, and equal patches (strengths, offsets, functions, adapter tensors bitwise);
* pass-through cases (disabled, zero strengths): the very same objects;
* returned VAE: model class, state dict bitwise, latent channels and scale ratios, the patcher's cached init, and a
  decode of a fixed latent bitwise;
* the warning the original prints for an unknown override (stdout of each side);
* errors: the same exception type on both sides.
A negative control must turn the comparator red. Writes /results/loaders.json; exit 1 on any difference.
Run: run_in_gate.sh <comfyui-art-venture-HEAD with v2> <v2/tests> <out> test_artv_loaders.py
"""
import asyncio
import contextlib
import importlib
import importlib.util
import io as pyio
import json
import os
import shutil
import sys
import tempfile
import traceback
import types
from pathlib import Path

CORE = Path(os.environ.get("COMFY_CORE_ROOT", "/core"))
sys.path[:0] = [str(CORE), "/overlay", str(Path(__file__).resolve().parent)]

from comfy.cli_args import args  # noqa: E402

args.cpu = True
import torch  # noqa: E402
from safetensors.torch import save_file  # noqa: E402

import folder_paths  # noqa: E402
import server  # noqa: E402
from aiohttp import web  # noqa: E402

server.PromptServer.instance = types.SimpleNamespace(
    routes=web.RouteTableDef(), supports={"custom_nodes_from_web"}, send_sync=lambda *a, **k: None,
    client_id=None, last_node_id=None)

import import_stubs  # noqa: E402

STUBBED = import_stubs.install(["cv2", "timm", "fairscale", "pycocoevalcap", "qrcode", "pytorch_lightning", "kornia",
                                "segment_anything", "omegaconf", "boto3", "botocore", "transformers", "skimage",
                                "onnxruntime"])
import comfy.lora  # noqa: E402
import comfy.model_base as mb  # noqa: E402
import comfy.model_patcher as mp  # noqa: E402
import comfy.sd  # noqa: E402
import comfy.sd1_clip  # noqa: E402
import comfy.supported_models as sm  # noqa: E402
import comfy.supported_models_base  # noqa: E402
import comfy.taesd.taesd  # noqa: E402
from comfy_api.latest import _execution_metadata, _sdk  # noqa: E402
from comfy_execution.graph import DynamicPrompt  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402

PACK = Path(os.environ.get("ARTV_PACK", "/pack"))
V2 = PACK / "v2"
RESULTS = Path(os.environ.get("ARTV_RESULTS", "/results"))
TMP = Path(tempfile.mkdtemp(prefix="artv-loaders-"))
SEED = 20261103
ROWS = []
PIDS = set()


# --------------------------------------------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------------------------------------------- #
def seeded_(module, seed, scale=0.02):
    gen = torch.Generator().manual_seed(seed)
    with torch.no_grad():
        for p in module.parameters():
            p.copy_(torch.randn(p.shape, generator=gen) * scale)
    return module


def tiny_model():
    unet_config = {
        "use_checkpoint": False, "image_size": 32, "out_channels": 4, "use_spatial_transformer": True,
        "legacy": False, "adm_in_channels": None, "in_channels": 4, "model_channels": 32,
        "num_res_blocks": [1, 1], "transformer_depth": [1, 1], "channel_mult": [1, 2],
        "transformer_depth_middle": 1, "use_linear_in_transformer": False, "context_dim": 32,
        "transformer_depth_output": [1, 1, 1, 1], "use_temporal_attention": False, "use_temporal_resblock": False,
    }
    config = sm.SD15(unet_config)
    config.set_inference_dtype(torch.float32, None)
    model = mb.BaseModel(config, model_type=mb.ModelType.EPS, device=torch.device("cpu"))
    seeded_(model.diffusion_model, SEED)
    return mp.ModelPatcher(model, load_device=torch.device("cpu"), offload_device=torch.device("cpu"))


def tiny_clip():
    """Core's SD1 text encoder, shrunk through Core's own config override (model_options["clip_l_model_config"],
    comfy/sd1_clip.py SDClipModel), with the SD1 tokenizer files Core ships."""
    target = comfy.supported_models_base.ClipTarget(comfy.sd1_clip.SD1Tokenizer, comfy.sd1_clip.SD1ClipModel)
    clip = comfy.sd.CLIP(target=target, model_options={
        "load_device": torch.device("cpu"), "offload_device": torch.device("cpu"), "dtype": torch.float32,
        "clip_l_model_config": {"hidden_size": 32, "intermediate_size": 64, "num_attention_heads": 2,
                                "num_hidden_layers": 2, "projection_dim": 32}})
    seeded_(clip.cond_stage_model, SEED + 1)
    return clip


def lora_file(path, model, clip, seed, rank=4, per_side=3):
    """A kohya-style LoRA for a few 2-D weights of each side, named through Core's own key maps."""
    gen = torch.Generator().manual_seed(seed)
    tensors = {}
    for key_map, state in ((comfy.lora.model_lora_keys_unet(model.model, {}), model.model.state_dict()),
                           (comfy.lora.model_lora_keys_clip(clip.cond_stage_model, {}),
                            clip.cond_stage_model.state_dict())):
        chosen = []
        for lora_key, target in sorted(key_map.items()):
            if not isinstance(target, str) or not lora_key.startswith(("lora_unet_", "lora_te_")):
                continue
            weight = state.get(target if target in state else target.replace("diffusion_model.", "", 1))
            if weight is None or weight.ndim != 2:
                continue
            chosen.append((lora_key, weight.shape))
            if len(chosen) == per_side:
                break
        assert len(chosen) == per_side, (len(chosen), path)
        for lora_key, (out_features, in_features) in chosen:
            tensors[f"{lora_key}.lora_up.weight"] = torch.randn((out_features, rank), generator=gen) * 0.1
            tensors[f"{lora_key}.lora_down.weight"] = torch.randn((rank, in_features), generator=gen) * 0.1
            tensors[f"{lora_key}.alpha"] = torch.tensor(float(rank / 2))
    path.parent.mkdir(parents=True, exist_ok=True)
    save_file(tensors, str(path))
    return sorted(k for k in tensors if k.endswith(".lora_up.weight"))


def vae_file(path, seed):
    module = seeded_(comfy.taesd.taesd.TAESD(latent_channels=4), seed, scale=0.05)
    path.parent.mkdir(parents=True, exist_ok=True)
    save_file({k: v.contiguous() for k, v in module.state_dict().items()}, str(path))


MODEL = tiny_model()
CLIP = tiny_clip()
LORAS = TMP / "models" / "loras"
VAES = TMP / "models" / "vae"
LORA_KEYS = {name: lora_file(LORAS / name, MODEL, CLIP, seed)
             for name, seed in (("lora_a.safetensors", 1), ("lora_b.safetensors", 2), ("sub/lora_c.safetensors", 3))}
for name, seed in (("vae_a.safetensors", 4), ("vae_b.safetensors", 5)):
    vae_file(VAES / name, seed)
folder_paths.folder_names_and_paths["loras"] = ([str(LORAS)], set(folder_paths.supported_pt_extensions))
folder_paths.folder_names_and_paths["vae"] = ([str(VAES)], set(folder_paths.supported_pt_extensions))
(TMP / "models" / "checkpoints").mkdir(parents=True)
folder_paths.folder_names_and_paths["checkpoints"] = ([str(TMP / "models" / "checkpoints")],
                                                      set(folder_paths.supported_pt_extensions))

shutil.copytree(PACK, TMP / "comfyui_art_venture", ignore=shutil.ignore_patterns("v2"))
sys.path.insert(0, str(TMP))
ORIGINAL = dict(importlib.import_module("comfyui_art_venture").NODE_CLASS_MAPPINGS)


def import_package(name, root):
    spec = importlib.util.spec_from_file_location(name, root / "__init__.py", submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


SECURE = dict(import_package("artv_secure", V2).NODE_CLASS_MAPPINGS)


# --------------------------------------------------------------------------------------------------------------- #
# Running both sides
# --------------------------------------------------------------------------------------------------------------- #
class EntryGuestSession(GuestSession):
    """Production entry order (limits, fixr1_compat, main); no seed file is written, so no RNG seeding happens."""

    def _guest_command(self, python):
        return [python, str(Path(__file__).resolve().parent / "_artv_seeded_guest_entry.py")]


SESSION = {"guest": None}


async def run_v2(node_id, inputs):
    cls = SECURE[node_id]
    permissions = tuple(cls.SDK_PERMISSIONS)
    refs = _sdk.InProcessRefResolver()
    scope = _execution_metadata.ExecutionMetadataScope("artv-loaders", DynamicPrompt({}), None, observe=True)
    scope.__enter__()
    try:
        plan = _sdk.ExecutionPlan(
            prompt_id="artv-loaders", node_id="9", node_type=cls.__name__, tier="sandbox", node_module=cls.__module__,
            inputs=dict(inputs), input_mode="refs" if getattr(cls, "SDK_REFS", False) else "values",
            method="execute", permissions=permissions, prompt=None, extra_pnginfo=None,
            dynamic_prompt=DynamicPrompt({}), execution_metadata=scope)
        runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
        plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
        if SESSION["guest"] is None:
            Path("/tmp/artv-guest-seed").unlink(missing_ok=True)
            SESSION["guest"] = await EntryGuestSession("artv-loaders", guest_runtime_root=V2).start()
        guest = SESSION["guest"]
        result = await guest.execute(plan, runtime, capabilities=permissions, tenant="artv-loaders")
        if guest.last_guest_pid:
            PIDS.add(guest.last_guest_pid)
        values = tuple([await refs.resolve(v) if isinstance(v, _sdk.Ref) else v for v in (result.result or ())])
        return values, guest.last_stdout or ""
    finally:
        scope.__exit__(None, None, None)


def run_original(node_id, inputs):
    cls = ORIGINAL[node_id]
    out = pyio.StringIO()
    with contextlib.redirect_stdout(out):
        values = tuple(getattr(cls(), cls.FUNCTION)(**inputs))
    return values, out.getvalue()


# --------------------------------------------------------------------------------------------------------------- #
# Comparison
# --------------------------------------------------------------------------------------------------------------- #
def deep_equal(a, b, path="", seen=None):
    """Structural, bitwise equality. Returns the first differing path, or None."""
    seen = set() if seen is None else seen
    if type(a) is not type(b):
        return f"{path}: type {type(a).__name__} != {type(b).__name__}"
    if isinstance(a, torch.Tensor):
        if a.dtype != b.dtype or a.shape != b.shape or not torch.equal(a, b):
            return f"{path}: tensor differs"
        return None
    if isinstance(a, float):
        return None if a.hex() == b.hex() else f"{path}: {a!r} != {b!r}"
    if isinstance(a, (str, int, bool, type(None), torch.dtype, torch.device)) or callable(a) and not hasattr(a, "__dict__"):
        return None if a == b else f"{path}: {a!r} != {b!r}"
    if isinstance(a, (list, tuple)):
        if len(a) != len(b):
            return f"{path}: length {len(a)} != {len(b)}"
        for index, (x, y) in enumerate(zip(a, b)):
            found = deep_equal(x, y, f"{path}[{index}]", seen)
            if found:
                return found
        return None
    if isinstance(a, (set, frozenset)):
        return None if a == b else f"{path}: sets differ"
    if isinstance(a, dict):
        if set(a) != set(b):
            return f"{path}: keys {sorted(map(str, set(a) ^ set(b)))[:6]}"
        for key in a:
            found = deep_equal(a[key], b[key], f"{path}.{key}", seen)
            if found:
                return found
        return None
    if a is b:
        return None
    if (id(a), id(b)) in seen:
        return None
    seen.add((id(a), id(b)))
    if hasattr(a, "__dict__"):
        return deep_equal(vars(a), vars(b), f"{path}<{type(a).__name__}>", seen)
    return None if a == b else f"{path}: {type(a).__name__} differs"


def compare_patched(expected, actual):
    """MODEL (ModelPatcher) or CLIP outputs of a LoRA application."""
    if isinstance(expected, mp.ModelPatcher):
        if expected.model is not actual.model:
            return "MODEL: a different base model"
        return (deep_equal(expected.patches, actual.patches, "MODEL.patches")
                or deep_equal(expected.object_patches, actual.object_patches, "MODEL.object_patches")
                or deep_equal(expected.model_options, actual.model_options, "MODEL.model_options"))
    if isinstance(expected, comfy.sd.CLIP):
        if expected.cond_stage_model is not actual.cond_stage_model:
            return "CLIP: a different text encoder"
        return deep_equal(expected.patcher.patches, actual.patcher.patches, "CLIP.patches")
    return "unexpected output type"


LATENT = torch.randn((1, 4, 8, 8), generator=torch.Generator().manual_seed(SEED + 9))


def compare_vae(expected, actual):
    if type(expected.first_stage_model) is not type(actual.first_stage_model):
        return "VAE: model class differs"
    found = deep_equal(expected.first_stage_model.state_dict(), actual.first_stage_model.state_dict(), "VAE.sd")
    if found:
        return found
    for attribute in ("latent_channels", "downscale_ratio", "upscale_ratio", "output_channels", "vae_dtype"):
        found = deep_equal(getattr(expected, attribute, None), getattr(actual, attribute, None), f"VAE.{attribute}")
        if found:
            return found
    init_a = getattr(expected.patcher, "cached_patcher_init", None)
    init_b = getattr(actual.patcher, "cached_patcher_init", None)
    if (init_a is None) != (init_b is None) or (init_a is not None and (
            init_a[0] is not init_b[0] or deep_equal(init_a[1], init_b[1]))):
        return f"VAE.cached_patcher_init: {init_a!r} != {init_b!r}"
    with torch.no_grad():
        if not torch.equal(expected.decode(LATENT.clone()), actual.decode(LATENT.clone())):
            return "VAE: decode differs"
    return None


def compare(node_id, expected, actual, identity):
    if len(expected) != len(actual):
        return f"output count {len(expected)} != {len(actual)}"
    for index, (a, b) in enumerate(zip(expected, actual)):
        if identity:
            if a is not b:
                return f"output {index}: not the same object as the original's"
            continue
        found = compare_vae(a, b) if isinstance(a, comfy.sd.VAE) else compare_patched(a, b)
        if found:
            return f"output {index}: {found}"
    return None


# --------------------------------------------------------------------------------------------------------------- #
# Cases
# --------------------------------------------------------------------------------------------------------------- #
def lora(lora_name="lora_a.safetensors", sm_=1.0, sc=1.0, **extra):
    return {"model": MODEL, "clip": CLIP, "lora_name": lora_name, "strength_model": sm_, "strength_clip": sc, **extra}


def cases():
    out = [
        ("AV_LoraLoader", "disabled", lora(enabled=False), True),
        ("AV_LoraLoader", "zero strengths", lora(sm_=0.0, sc=0.0), True),
        ("AV_LoraLoader", "a 1/1", lora(), False),
        ("AV_LoraLoader", "a 0.5/0 (clip strength zero)", lora(sm_=0.5, sc=0.0), False),
        ("AV_LoraLoader", "a 0/0.75 (model strength zero)", lora(sm_=0.0, sc=0.75), False),
        ("AV_LoraLoader", "a -1.25/2", lora(sm_=-1.25, sc=2.0), False),
        ("AV_LoraLoader", "a linked strength 150 (outside the widget range)", lora(sm_=150.0, sc=1.0), False),
        ("AV_LoraLoader", "subfolder c", lora("sub/lora_c.safetensors"), False),
        ("AV_LoraLoader", "override b present", lora(lora_override="lora_b.safetensors"), False),
        ("AV_LoraLoader", "override subfolder c present", lora(lora_override="sub/lora_c.safetensors"), False),
        ("AV_LoraLoader", "override missing (warning, then a)", lora(lora_override="missing.safetensors"), False),
        ("AV_LoraLoader", "override 'None'", lora(lora_override="None"), False),
        ("AV_LoraLoader", "unknown lora_name (error)", lora("missing.safetensors"), False),
        ("AV_VAELoader", "vae a", {"vae_name": "vae_a.safetensors"}, False),
        ("AV_VAELoader", "override b present", {"vae_name": "vae_a.safetensors", "vae_override": "vae_b.safetensors"},
         False),
        ("AV_VAELoader", "override missing (warning, then a)",
         {"vae_name": "vae_a.safetensors", "vae_override": "missing.safetensors"}, False),
        ("AV_VAELoader", "pixel_space", {"vae_name": "pixel_space"}, False),
        ("AV_VAELoader", "unknown vae_name (error)", {"vae_name": "missing.safetensors"}, False),
    ]
    return out


async def main():
    for node_id, label, inputs, identity in cases():
        case = f"{node_id}:{label}"
        try:
            (expected, expected_out), expected_error = run_original(node_id, dict(inputs)), None
        except Exception as error:  # noqa: BLE001
            expected, expected_out, expected_error = None, "", type(error).__name__
        try:
            (actual, actual_out), actual_error = await run_v2(node_id, dict(inputs)), None
        except Exception as error:  # noqa: BLE001
            actual, actual_out, actual_error = None, "", f"{type(error).__name__}: {error}"[:300]
        difference = None
        if expected_error or actual_error:
            ok = bool(expected_error) and bool(actual_error) and expected_error in actual_error
            verdict = "BOTH_FAIL" if ok else "MISMATCH"
        else:
            difference = compare(node_id, expected, actual, identity)
            if difference is None and expected_out.strip() != actual_out.strip():
                difference = f"stdout differs: {expected_out.strip()!r} != {actual_out.strip()!r}"
            verdict = "EXACT" if difference is None else "MISMATCH"
        patched = {}
        if node_id == "AV_LoraLoader" and not identity and expected is not None:
            # Guard against a vacuous match: an applied strength must have patched weights on that side.
            patched = {"model_keys": len(expected[0].patches), "clip_keys": len(expected[1].patcher.patches)}
            if verdict == "EXACT" and ((inputs["strength_model"] != 0 and not patched["model_keys"])
                                       or (inputs["strength_clip"] != 0 and not patched["clip_keys"])):
                verdict, difference = "MISMATCH", f"vacuous: no patched weights for an applied strength {patched}"
        ROWS.append({"node": node_id, "case": case, "verdict": verdict, "difference": difference, "patched": patched,
                     "identity_case": identity, "stdout_original": expected_out.strip()[:300],
                     "stdout_v2": actual_out.strip()[:300], "expected_error": expected_error,
                     "actual_error": actual_error})
        print(verdict, case, difference or "", expected_error or "", actual_error or "", flush=True)
    # Negative control: the comparator must go red when one LoRA patch tensor changes by one ulp.
    expected, _ = run_original("AV_LoraLoader", lora())
    tampered, _ = run_original("AV_LoraLoader", lora())
    key = sorted(tampered[0].patches)[0]
    strength, adapter, *rest = tampered[0].patches[key][0]
    weights = list(getattr(adapter, "weights", adapter[1] if isinstance(adapter, tuple) else ()))
    first = next(i for i, w in enumerate(weights) if isinstance(w, torch.Tensor))
    bumped = weights[first].clone()
    bumped.view(-1)[0] = torch.nextafter(bumped.view(-1)[0], torch.tensor(float("inf")))
    weights[first] = bumped
    if hasattr(adapter, "weights"):
        adapter.weights = tuple(weights)
    negative_control_red = compare("AV_LoraLoader", expected, tampered, False) is not None
    if SESSION["guest"] is not None:
        await SESSION["guest"].kill()
    await asyncio.sleep(0.5)
    alive = [pid for pid in PIDS if Path(f"/proc/{pid}").exists()]
    totals = {}
    for row in ROWS:
        totals.setdefault(row["node"], {}).setdefault(row["verdict"], 0)
        totals[row["node"]][row["verdict"]] += 1
    doc = {"totals": totals, "negative_control_red": negative_control_red, "stubbed_imports_original_side": STUBBED,
           "lora_keys": {k: len(v) for k, v in LORA_KEYS.items()}, "guest_pids": sorted(PIDS),
           "alive_after_kill": alive, "torch": torch.__version__, "rows": ROWS}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "loaders.json").write_text(json.dumps(doc, indent=1, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: doc[k] for k in ("totals", "negative_control_red", "lora_keys", "alive_after_kill")},
                     indent=1))
    return 1 if any(r["verdict"] == "MISMATCH" for r in ROWS) or alive or not negative_control_red else 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
