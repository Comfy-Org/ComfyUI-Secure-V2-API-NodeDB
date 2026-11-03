"""Tier-1 parity: comfyui-art-venture ORIGINAL vs V2 for the converted nodes (gate only, CPU, synthetic inputs).

* Original side: the pristine package imported in this process. Heavy dependencies the gate lacks are import stubs
  (import_stubs.py, labelled test adaptation); the converted nodes' code paths use none of them, and any use of a stub
  raises.
* V2 side: each node runs in a REAL guest (comfy_secure_nodes GuestSession through the production entry order) with
  exactly its declared permissions.
* RandomInt / RandomFloat use torch's unseeded global RNG, as upstream intends, and are converted verbatim.
  For an exact comparison both sides' global RNG is seeded identically before the call: torch.manual_seed on the
  original side, a fresh guest started through _artv_seeded_guest_entry.py on the V2 side.
* Comparisons are type-strict; tensors compare by dtype, shape and bits. Errors must match in type on both sides.
Writes /results/parity.json; exit 1 on any difference or harness failure.
Run: run_in_gate.sh <comfyui-art-venture-HEAD with v2> <v2/tests> <out> test_artv_parity.py
"""
import asyncio
import importlib
import importlib.util
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
from comfy_api.latest import _execution_metadata, _sdk  # noqa: E402
from comfy_execution.graph import DynamicPrompt  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402

PACK = Path(os.environ.get("ARTV_PACK", "/pack"))
V2 = PACK / "v2"
RESULTS = Path(os.environ.get("ARTV_RESULTS", "/results"))
TMP = Path(tempfile.mkdtemp(prefix="artv-parity-"))
CKPT = TMP / "models" / "checkpoints"
CKPT.mkdir(parents=True)
(CKPT / "model_a.safetensors").write_bytes(b"synthetic checkpoint name only\n")
folder_paths.folder_names_and_paths["checkpoints"] = ([str(CKPT)], set(folder_paths.supported_pt_extensions))


def tiny_upscale_model():
    """A seeded 2x RealESRGAN-Compact upscaler (8 features, 2 convs), loaded through Core's own UpscaleModelLoader,
    so both sides get the object a real graph passes (spandrel descriptor + Core's patcher)."""
    from safetensors.torch import save_file
    from spandrel.architectures.Compact import Compact
    import comfy_extras.nodes_upscale_model as upscale_nodes

    net = Compact(num_in_ch=3, num_out_ch=3, num_feat=8, num_conv=2, upscale=2, act_type="prelu")
    gen = torch.Generator().manual_seed(11)
    with torch.no_grad():
        for parameter in net.parameters():
            parameter.copy_(torch.randn(parameter.shape, generator=gen) * 0.1)
    folder = TMP / "models" / "upscale_models"
    folder.mkdir(parents=True)
    save_file({k: v.contiguous() for k, v in net.state_dict().items()}, str(folder / "tiny_x2.safetensors"))
    folder_paths.folder_names_and_paths["upscale_models"] = ([str(folder)], set(folder_paths.supported_pt_extensions))
    return upscale_nodes.UpscaleModelLoader.execute("tiny_x2.safetensors").result[0]


UPSCALE_MODEL = tiny_upscale_model()
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
SEED_FILE = Path("/tmp/artv-guest-seed")
ROWS = []
PIDS = set()


class EntryGuestSession(GuestSession):
    """Production entry order (limits, fixr1_compat, main), with the optional RNG seed (see the entry's docstring)."""

    def _guest_command(self, python):
        return [python, str(Path(__file__).resolve().parent / "_artv_seeded_guest_entry.py")]


SESSION = {"plain": None}


async def run_v2(node_id, inputs, seed=None):
    cls = SECURE[node_id]
    permissions = tuple(cls.SDK_PERMISSIONS)
    refs = _sdk.InProcessRefResolver()
    scope = _execution_metadata.ExecutionMetadataScope("artv-parity", DynamicPrompt({}), None, observe=True)
    scope.__enter__()
    guest = None
    try:
        plan = _sdk.ExecutionPlan(
            prompt_id="artv-parity", node_id="9", node_type=cls.__name__, tier="sandbox", node_module=cls.__module__,
            inputs=dict(inputs), input_mode="refs" if getattr(cls, "SDK_REFS", False) else "values",
            method="execute", permissions=permissions, prompt=None, extra_pnginfo=None,
            dynamic_prompt=DynamicPrompt({}), execution_metadata=scope)
        runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
        plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
        if seed is None:
            if SESSION["plain"] is None:
                SEED_FILE.unlink(missing_ok=True)
                SESSION["plain"] = await EntryGuestSession("artv-parity", guest_runtime_root=V2).start()
            guest = SESSION["plain"]
        else:  # a fresh guest whose global RNG was seeded before it served anything
            SEED_FILE.write_text(str(seed))
            guest = await EntryGuestSession(f"artv-seed-{seed}", guest_runtime_root=V2).start()
            SEED_FILE.unlink(missing_ok=True)
        result = await guest.execute(plan, runtime, capabilities=permissions, tenant="artv-parity")
        if guest.last_guest_pid:
            PIDS.add(guest.last_guest_pid)
        return tuple([await refs.resolve(v) if isinstance(v, _sdk.Ref) else v for v in (result.result or ())])
    finally:
        scope.__exit__(None, None, None)
        if seed is not None and guest is not None:
            await guest.kill()


def run_original(node_id, inputs, seed=None):
    cls = ORIGINAL[node_id]
    if seed is not None:
        torch.manual_seed(seed)
    return tuple(getattr(cls(), cls.FUNCTION)(**{k: (v.clone() if isinstance(v, torch.Tensor) else v)
                                                for k, v in inputs.items()}))


def same(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, torch.Tensor):
        return a.dtype == b.dtype and a.shape == b.shape and torch.equal(a, b)
    if isinstance(a, float):
        return a.hex() == b.hex()
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def show(value):
    if isinstance(value, torch.Tensor):
        return {"dtype": str(value.dtype), "shape": list(value.shape), "sum": float(value.double().sum())}
    if isinstance(value, (list, tuple)):
        return [show(v) for v in value]
    if isinstance(value, float):
        return value.hex()
    return value


def image(batch, height, width, channels, seed):
    gen = torch.Generator().manual_seed(seed)
    return torch.rand((batch, height, width, channels), generator=gen, dtype=torch.float32)


def cases():
    out = []
    for text in ("0", "42", "-7", " 12 ", "123456789012345678901234567890", "1e3", "abc", ""):
        out.append(("StringToInt", {"string": text}, None))
    for value in (False, True):
        for reverse in (False, True):
            out.append(("BooleanPrimitive", {"value": value, "reverse": reverse}, None))
    for mode in (True, False):
        out.append(("SeedSelector", {"mode": mode, "seed": 5, "fixed_seed": 0xFFFFFFFFFFFFFFFF}, None))
    for ratio in ("1:1", "2:3", "3:4", "5:8", "9:16", "9:19", "9:21", "3:2", "4:3", "8:5", "16:9", "19:9", "21:9"):
        out.append(("SDXLAspectRatioSelector", {"aspect_ratio": ratio}, None))
    for ratio in ("1:1", "2:3", "3:4", "9:16", "3:2", "4:3", "16:9"):
        out.append(("AspectRatioSelector", {"aspect_ratio": ratio}, None))
    rgb = image(2, 64, 48, 3, 1)
    rgba = image(1, 40, 72, 4, 2)
    for scale in (0.5, 0.33, 1.0, 0.75):
        out.append(("ImageScaleDownBy", {"images": rgb, "scale_by": scale}, None))
    out.append(("ImageScaleDownBy", {"images": rgba, "scale_by": 0.5}, None))
    for size in (32, 100):
        for mode in (True, False):
            out.append(("ImageScaleDownToSize", {"images": rgb, "size": size, "mode": mode}, None))
    for megapixels in (0.001, 0.0025, 0.0031, 0.004, 0.02):
        out.append(("ImageScaleToMegapixels", {"images": rgb, "megapixels": megapixels}, None))
    # With an upscale model: >= 1.2x goes through the model (Core's ImageUpscaleWithModel in the original), then the
    # original's centre-crop LANCZOS scale-down; < 1.2x stays bicubic. RGBA covers the colour-only model input.
    small_rgb = image(1, 24, 20, 3, 4)
    small_batch = image(2, 24, 20, 3, 5)
    small_rgba = image(1, 24, 20, 4, 6)
    for images, megapixels in ((small_rgb, 0.001), (small_rgb, 0.0035), (small_batch, 0.002), (small_rgba, 0.0015),
                               (small_rgb, 0.0006)):
        out.append(("ImageScaleToMegapixels", {"images": images, "megapixels": megapixels,
                                               "upscale_model_opt": UPSCALE_MODEL}, None))
    for radius in (1, 3):
        out.append(("ImageGaussianBlur", {"images": rgb, "radius": radius}, None))
    mask = torch.rand((64, 48), generator=torch.Generator().manual_seed(3))
    for channel in ("R", "G", "B", "A"):
        out.append(("ImageApplyChannel", {"images": rgb, "channel_data": mask, "channel": channel}, None))
    out.append(("CheckpointNameSelector", {"ckpt_name": "model_a.safetensors"}, None))
    for seed in (1, 2, 12345):
        for low, high in ((0, 100), (5, 6), (0, 0xFFFFFFFF)):
            out.append(("RandomInt", {"min": low, "max": high}, seed))
        for low, high in ((0.0, 1.0), (2.5, 7.5)):
            out.append(("RandomFloat", {"min": low, "max": high}, seed))
    return out


async def main():
    for node_id, inputs, seed in cases():
        label = ",".join(
            f"{k}=" + ("tensor" + "x".join(map(str, v.shape)) if isinstance(v, torch.Tensor)
                       else repr(v) if isinstance(v, (str, int, float, bool, type(None))) else type(v).__name__)
            for k, v in inputs.items())
        case = f"{node_id}:{label}" + (f":seed={seed}" if seed is not None else "")
        try:
            expected, expected_error = run_original(node_id, inputs, seed), None
        except Exception as error:  # noqa: BLE001
            expected, expected_error = None, type(error).__name__
        try:
            actual, actual_error = await run_v2(node_id, inputs, seed), None
        except Exception as error:  # noqa: BLE001
            actual, actual_error = None, f"{type(error).__name__}: {error}"[:300]
        if expected_error or actual_error:
            ok = bool(expected_error) and bool(actual_error) and expected_error in actual_error
            verdict = "BOTH_FAIL" if ok else "MISMATCH"
        else:
            verdict = "EXACT" if same(expected, actual) else "MISMATCH"
        ROWS.append({"node": node_id, "case": case, "verdict": verdict, "expected": show(expected),
                     "actual": show(actual), "expected_error": expected_error, "actual_error": actual_error})
        if verdict != "EXACT":
            print(verdict, case, expected_error, actual_error, flush=True)
    # negative control: the comparator must go red on a one-ulp change of one output value
    sample = run_original("ImageGaussianBlur", {"images": image(1, 16, 16, 3, 9), "radius": 2})
    tampered = sample[0].clone()
    flat = tampered.view(-1)
    flat[0] = torch.nextafter(flat[0], torch.tensor(float("inf")))
    negative_control_red = not same(sample, (tampered,))
    if SESSION["plain"] is not None:
        await SESSION["plain"].kill()
    await asyncio.sleep(0.5)
    alive = [pid for pid in PIDS if Path(f"/proc/{pid}").exists()]
    totals = {}
    for row in ROWS:
        totals.setdefault(row["node"], {}).setdefault(row["verdict"], 0)
        totals[row["node"]][row["verdict"]] += 1
    import PIL
    doc = {"totals": totals, "negative_control_red": negative_control_red, "stubbed_imports_original_side": STUBBED,
           "guest_pids": sorted(PIDS), "alive_after_kill": alive, "torch": torch.__version__,
           "pillow": PIL.__version__, "rows": ROWS}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "parity.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: doc[k] for k in ("totals", "negative_control_red", "stubbed_imports_original_side",
                                         "alive_after_kill", "pillow")}, indent=1))
    return 1 if any(r["verdict"] == "MISMATCH" for r in ROWS) or alive or not negative_control_red else 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except Exception:
        traceback.print_exc()
        sys.exit(2)
