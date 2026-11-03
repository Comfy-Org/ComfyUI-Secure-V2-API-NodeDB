"""Tier-1 parity: every converted wlsh_nodes node, the ORIGINAL in-process vs V2 in a real guest (gate only, CPU).

* Original side: the pristine package imported in this process. Its module-level `import piexif` comes from DEPS
  when mounted, else from a labelled import stub (import_stubs.py); no converted node uses piexif.
* V2 side: each node runs in a real guest (GuestSession through _wlsh_sealed_guest_entry.py: the production entry
  order, with the guest import audit on) with exactly its declared permissions.
* Fixtures, all synthetic and seeded:
  - Upscale by Factor with Model: a 2x RealESRGAN-Compact model (8 features, 2 convs), loaded through Core's own
    UpscaleModelLoader so both sides get what a real graph passes; images that fit one 192-pixel tile and images that
    need several (both axes, batches);
  - KSamplerAdvanced (WLSH): a tiny SD1.5-shaped UNet with seeded weights and synthetic conditioning;
  - Checkpoint Loader w/Name: Core's comfy.sd.load_checkpoint_guess_config is replaced, in this process, by a
    recorder that returns fixed stand-in objects. Both sides reach it (the original directly, V2 through the host's
    loader), so the test compares the Core call itself (every bound argument) and the returned objects (identity).
* Comparisons are type-strict; tensors compare by dtype, shape and bits. Errors must occur on both sides (BOTH_FAIL).
  A 1-ulp change to one V2 output must compare unequal (negative control).
Writes /results/parity.json; exit 1 on any difference.
Run: run_in_gate.sh <wlsh_nodes-HEAD with v2> <v2/tests> <out> test_wlsh_parity.py   (DEPS optional)
"""
import asyncio
import importlib
import importlib.util
import inspect
import json
import os
import shutil
import sys
import tempfile
import traceback
import types
from pathlib import Path

CORE = Path(os.environ.get("COMFY_CORE_ROOT", "/core"))
sys.path[:0] = [str(CORE), "/overlay"]
if Path("/deps").is_dir():
    sys.path.append("/deps")

from comfy.cli_args import args  # noqa: E402

args.cpu = True
import torch  # noqa: E402

import comfy.model_base as mb  # noqa: E402
import comfy.model_patcher as mp  # noqa: E402
import comfy.sd  # noqa: E402
import comfy.supported_models as sm  # noqa: E402
import folder_paths  # noqa: E402
import server  # noqa: E402
from aiohttp import web  # noqa: E402

server.PromptServer.instance = types.SimpleNamespace(
    routes=web.RouteTableDef(), supports={"custom_nodes_from_web"}, send_sync=lambda *a, **k: None,
    client_id=None, last_node_id=None)

from comfy_api.latest import _execution_metadata, _sdk  # noqa: E402
from comfy_execution.graph import DynamicPrompt  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
import import_stubs  # noqa: E402

STUBBED = import_stubs.install(["piexif"])  # only if genuinely absent
PACK = Path(os.environ.get("WLSH_PACK", "/pack"))
V2 = PACK / "v2"
RESULTS = Path(os.environ.get("WLSH_RESULTS", "/results"))
TMP = Path(tempfile.mkdtemp(prefix="wlsh-parity-"))
GUARD_LOG = TMP / "import-guard.jsonl"


# --------------------------------------------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------------------------------------------- #
def tiny_upscale_model():
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


def tiny_model():
    """A tiny SD1.5-shaped UNet with seeded random weights (EPS)."""
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
    gen = torch.Generator().manual_seed(1234)
    with torch.no_grad():
        for p in model.diffusion_model.parameters():
            p.copy_(torch.randn(p.shape, generator=gen) * 0.02)
    return mp.ModelPatcher(model, load_device=torch.device("cpu"), offload_device=torch.device("cpu"))


class Recorder:
    """Stands in for comfy.sd.load_checkpoint_guess_config in this process; records every call's bound arguments."""

    def __init__(self, real):
        self.signature = inspect.signature(real)
        self.calls = []
        self.objects = {}

    def __call__(self, *a, **k):
        bound = self.signature.bind(*a, **k)
        bound.apply_defaults()
        self.calls.append({key: repr(value) for key, value in bound.arguments.items()})
        path = bound.arguments["ckpt_path"]
        if path not in self.objects:
            self.objects[path] = tuple(types.SimpleNamespace(role=role, path=path)
                                       for role in ("model", "clip", "vae", "clipvision"))
        return self.objects[path]


UPSCALE_MODEL = tiny_upscale_model()
MODEL = tiny_model()
CKPT = TMP / "models" / "checkpoints"
(CKPT / "sub").mkdir(parents=True)
for name in ("tiny.safetensors", "sub/model.v1.5.ckpt"):
    (CKPT / name).write_bytes(b"synthetic checkpoint name only\n")
folder_paths.folder_names_and_paths["checkpoints"] = ([str(CKPT)], set(folder_paths.supported_pt_extensions))
RECORDER = Recorder(comfy.sd.load_checkpoint_guess_config)
comfy.sd.load_checkpoint_guess_config = RECORDER

shutil.copytree(PACK, TMP / "wlsh_nodes", ignore=shutil.ignore_patterns("v2"))
sys.path.insert(0, str(TMP))
ORIGINAL = dict(importlib.import_module("wlsh_nodes").NODE_CLASS_MAPPINGS)


def import_package(name, root):
    spec = importlib.util.spec_from_file_location(name, root / "__init__.py", submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


SECURE = dict(import_package("wlsh_secure", V2).NODE_CLASS_MAPPINGS)
GUEST = {"session": None, "pids": set()}


class SealedEntryGuestSession(GuestSession):
    """The production entry order with the guest import audit on; see the entry's docstring."""

    def _guest_command(self, python):
        return [python, str(TESTS / "_wlsh_sealed_guest_entry.py")]

    def _adjust_guest_env(self, env):
        super()._adjust_guest_env(env)
        env["WLSH_GUARD_ROOT"] = str(self.guest_runtime_root)
        env["WLSH_GUARD_LOG"] = str(GUARD_LOG)


async def run_v2(node_id, inputs):
    cls = SECURE[node_id]
    permissions = tuple(cls.SDK_PERMISSIONS)
    refs = _sdk.InProcessRefResolver()
    scope = _execution_metadata.ExecutionMetadataScope("wlsh-parity", DynamicPrompt({}), None, observe=True)
    scope.__enter__()
    try:
        plan = _sdk.ExecutionPlan(
            prompt_id="wlsh-parity", node_id="9", node_type=cls.__name__, tier="sandbox", node_module=cls.__module__,
            inputs=dict(inputs), input_mode="refs" if getattr(cls, "SDK_REFS", False) else "values",
            method="execute", permissions=permissions, prompt=None, extra_pnginfo=None,
            dynamic_prompt=DynamicPrompt({}), execution_metadata=scope)
        runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
        plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
        if GUEST["session"] is None:
            GUEST["session"] = await SealedEntryGuestSession("wlsh-parity", guest_runtime_root=V2).start()
        guest = GUEST["session"]
        result = await guest.execute(plan, runtime, capabilities=permissions, tenant="wlsh-parity")
        if guest.last_guest_pid:
            GUEST["pids"].add(guest.last_guest_pid)
        return tuple([await refs.resolve(v) if isinstance(v, _sdk.Ref) else v for v in (result.result or ())])
    finally:
        scope.__exit__(None, None, None)


def run_original(node_id, inputs):
    cls = ORIGINAL[node_id]
    return tuple(getattr(cls(), cls.FUNCTION)(**{k: (v.clone() if isinstance(v, torch.Tensor) else v)
                                                for k, v in inputs.items()}))


INT_VIEW = {torch.float16: torch.int16, torch.bfloat16: torch.int16, torch.float32: torch.int32,
            torch.float64: torch.int64}


def same(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, torch.Tensor):
        if a.dtype != b.dtype or a.shape != b.shape or a.device != b.device:
            return False
        if a.dtype in INT_VIEW:
            nan_a, nan_b = torch.isnan(a), torch.isnan(b)
            return torch.equal(nan_a, nan_b) and torch.equal(
                a.contiguous().view(INT_VIEW[a.dtype])[~nan_a], b.contiguous().view(INT_VIEW[b.dtype])[~nan_b])
        return torch.equal(a, b)
    if isinstance(a, float):
        return a.hex() == b.hex()
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        return list(a.keys()) == list(b.keys()) and all(same(a[k], b[k]) for k in a)
    return a == b


def show(value):
    if isinstance(value, torch.Tensor):
        flat = value.detach().double().flatten()
        return {"dtype": str(value.dtype), "shape": list(value.shape),
                "sum": float(flat.nansum()) if value.numel() else 0.0}
    if isinstance(value, (list, tuple)):
        return [show(v) for v in value]
    if isinstance(value, dict):
        return {str(k): show(v) for k, v in value.items()}
    if isinstance(value, types.SimpleNamespace):
        return f"<{value.role} {Path(value.path).name}>"
    return value if not isinstance(value, str) or len(value) < 80 else value[:77] + "..."


def image(batch, height, width, channels, seed):
    return torch.rand((batch, height, width, channels), generator=torch.Generator().manual_seed(seed))


def conditioning():
    gen = torch.Generator().manual_seed(7)
    pos = [[torch.randn((1, 8, 32), generator=gen), {}]]
    neg = [[torch.randn((1, 8, 32), generator=gen), {}]]
    return pos, neg


def latent(batch=1, mask=False, seed=8):
    samples = torch.randn((batch, 4, 8, 8), generator=torch.Generator().manual_seed(seed)) * 0.5
    out = {"samples": samples}
    if mask:
        m = torch.zeros((1, 8, 8))
        m[:, 2:6, 1:7] = 1.0
        out["noise_mask"] = m
    return out


def cases():
    out = []
    add = lambda node, inputs, label=None: out.append((node, inputs, label))  # noqa: E731
    for pre, base, total in ((3, 12, 20), (1, 1, 1), (10000, 5000, 1)):
        add("SDXL Steps (WLSH)", {"precondition": pre, "base": base, "total": total})
    for number, multiplier in ((2, 2), (1, 1), (10000, 10000), (7, 3)):
        add("Multiply Integer (WLSH)", {"number": number, "multiplier": multiplier})
    resolutions = ["1024x1024|1:1", "1152x896|9:7", "1216x832|19:13", "1344x768|7:4", "1536x640|12:5"]
    for resolution in resolutions:
        for direction in ("landscape", "portrait"):
            add("SDXL Resolutions (WLSH)", {"resolution": resolution, "direction": direction})
            for batch in (1, 2):
                add("SDXL Quick Empty Latent (WLSH)", {"resolution": resolution, "direction": direction,
                                                       "batch_size": batch})
    ratio_aspects = ["1:1", "6:5", "5:4", "4:3", "3:2", "16:10", "16:9", "21:9", "43:18", "2:1", "3:1", "4:1"]
    for aspect in ratio_aspects:
        for direction in ("landscape", "portrait"):
            for shortside in (64, 512, 960, 8192):
                add("Resolutions by Ratio (WLSH)", {"aspect": aspect, "direction": direction, "shortside": shortside})
    for aspect in ["1:1", "6:5", "5:4", "4:3", "3:2", "16:10", "16:9", "19:9", "21:9", "43:18", "2:1", "3:1", "4:1"]:
        for direction in ("landscape", "portrait"):
            for shortside, batch in ((64, 1), (512, 3)):
                add("Empty Latent by Ratio (WLSH)", {"aspect": aspect, "direction": direction, "shortside": shortside,
                                                     "batch_size": batch})
    for aspect in ["1:1", "5:4", "4:3", "3:2", "16:10", "16:9", "19:9", "21:9", "43:18", "2:1", "3:1", "4:1"]:
        for direction in ("landscape", "portrait"):
            for megapixels in (0.01, 1.0, 2.5):
                add("Empty Latent by Pixels (WLSH)", {"aspect": aspect, "direction": direction,
                                                      "megapixels": megapixels, "batch_size": 1})
    add("Empty Latent by Pixels (WLSH)", {"aspect": "16:9", "direction": "portrait", "megapixels": 16.0,
                                          "batch_size": 2})
    for width, height, batch in ((512, 512, 1), (16, 16, 1), (520, 776, 2), (8192, 64, 1), (64, 64, 4096)):
        add("Empty Latent by Size (WLSH)", {"width": width, "height": height, "batch_size": batch})
    for placement in ("after", "before"):
        for separator in ("comma", "space", "newline", "none"):
            add("Simple String Combine (WLSH)", {"addition": "add ☀", "placement": placement, "separator": separator,
                                                 "input_string": "base text"})
            add("Simple String Combine (WLSH)", {"addition": "add", "placement": placement, "separator": separator})
        add("Simple String Combine (WLSH)", {"addition": "", "placement": placement, "separator": "comma",
                                             "input_string": ""})
    shortside_images = {"rgb_1x48x64": image(1, 48, 64, 3, 1), "rgb_2x100x70": image(2, 100, 70, 3, 2),
                        "rgba_1x31x33": image(1, 31, 33, 4, 3), "gray_1x20x20": image(1, 20, 20, 1, 4)}
    for name, img in shortside_images.items():
        for method in ("nearest-exact", "bilinear", "area"):
            for shortside in (32, 64, 512):
                add("Image Scale by Shortside (WLSH)", {"original": img.clone(), "upscale_method": method,
                                                        "shortside": shortside}, name)
    upscale_images = {"one_tile_1x40x56": image(1, 40, 56, 3, 5), "tiles_1x300x210": image(1, 300, 210, 3, 6),
                      "tiles_2x200x200": image(2, 200, 200, 3, 7), "exact_tile_1x192x192": image(1, 192, 192, 3, 8),
                      "rgba_1x64x64": image(1, 64, 64, 4, 9)}
    for name, img in upscale_images.items():
        for method in ("nearest-exact", "bilinear", "area"):
            for factor in ((0.5, 2.0) if name.startswith("tiles") else (0.5, 1.0, 2.0, 3.3)):
                add("Upscale by Factor with Model (WLSH)", {"upscale_model": UPSCALE_MODEL, "image": img.clone(),
                                                            "upscale_method": method, "factor": factor}, name)
    pos, neg = conditioning()
    base = {"model": MODEL, "add_noise": "enable", "seed": 3, "steps": 6, "cfg": 5.5, "sampler_name": "euler",
            "scheduler": "normal", "positive": pos, "negative": neg, "start_at_step": 0, "end_at_step": 10000,
            "return_with_leftover_noise": "disable", "denoise": 1.0}
    sampler_cases = []
    for sampler in ("euler", "euler_ancestral", "dpmpp_2m", "heun"):
        for scheduler in ("normal", "karras"):
            sampler_cases.append({"sampler_name": sampler, "scheduler": scheduler})
    for add_noise in ("enable", "disable"):
        for start, end in ((0, 10000), (2, 5), (5, 2), (0, 3), (6, 10000), (3, 3)):
            for leftover in ("disable", "enable"):
                sampler_cases.append({"add_noise": add_noise, "start_at_step": start, "end_at_step": end,
                                      "return_with_leftover_noise": leftover})
    sampler_cases += [{"denoise": 0.6}, {"denoise": 0.0}, {"cfg": 1.0}, {"seed": 2 ** 40 + 17},
                      {"_latent": {"mask": True}}, {"_latent": {"batch": 2}}, {"_latent": {"mask": True},
                                                                               "denoise": 0.7}]
    for overrides in sampler_cases:
        inputs = dict(base)
        latent_args = overrides.pop("_latent", {})
        inputs.update(overrides)
        inputs["latent_image"] = latent(**latent_args)
        label = ",".join(f"{k}={v}" for k, v in {**overrides, **latent_args}.items())
        add("KSamplerAdvanced (WLSH)", inputs, label)
    for name in ("tiny.safetensors", "sub/model.v1.5.ckpt"):
        add("Checkpoint Loader w/Name (WLSH)", {"ckpt_name": name}, name)
    return out


def describe(inputs):
    parts = []
    for k, v in inputs.items():
        if isinstance(v, torch.Tensor):
            parts.append(f"{k}=tensor")
        elif isinstance(v, (str, int, float, bool)):
            parts.append(f"{k}={v if not isinstance(v, str) or len(v) < 30 else len(v)}")
    return ",".join(parts)


async def main():
    rows, perturb = [], None
    for node_id, inputs, label in cases():
        case = f"{node_id}:{label + ':' if label else ''}{describe(inputs)}"
        calls_before = len(RECORDER.calls)
        try:
            expected, expected_error = run_original(node_id, inputs), None
        except Exception as error:  # noqa: BLE001
            expected, expected_error = None, f"{type(error).__name__}: {error}"[:300]
        calls_mid = len(RECORDER.calls)
        try:
            actual, actual_error = await run_v2(node_id, inputs), None
        except Exception as error:  # noqa: BLE001
            actual, actual_error = None, f"{type(error).__name__}: {error}"[:400]
        extra = {}
        if node_id.startswith("Checkpoint Loader"):
            original_calls = RECORDER.calls[calls_before:calls_mid]
            v2_calls = RECORDER.calls[calls_mid:]
            extra = {"core_call_original": original_calls, "core_call_v2": v2_calls}
            if original_calls != v2_calls or len(original_calls) != 1:
                actual_error = (actual_error or "") + " | Core call differs"
        if expected_error or actual_error:
            verdict = "BOTH_FAIL" if expected_error and actual_error else "MISMATCH"
        else:
            verdict = "EXACT" if same(expected, actual) else "MISMATCH"
        rows.append({"node": node_id, "case": case, "verdict": verdict, "expected": show(expected),
                     "actual": show(actual), "expected_error": expected_error, "actual_error": actual_error, **extra})
        if verdict != "EXACT":
            print(verdict, case, expected_error, actual_error, flush=True)
        elif perturb is None and node_id.startswith("Upscale by Factor"):
            perturb = (expected, actual)
    expected, actual = perturb
    bumped = actual[0].clone()
    flat = bumped.view(-1)
    flat[0] = torch.nextafter(flat[0], torch.tensor(float("inf"), dtype=flat.dtype))
    ulp_red = not same(expected, (bumped,))
    if GUEST["session"] is not None:
        await GUEST["session"].kill()
    await asyncio.sleep(0.5)
    alive = [pid for pid in GUEST["pids"] if Path(f"/proc/{pid}").exists()]
    totals = {}
    for row in rows:
        totals.setdefault(row["node"], {}).setdefault(row["verdict"], 0)
        totals[row["node"]][row["verdict"]] += 1
    guard = [json.loads(line) for line in GUARD_LOG.read_text().splitlines()] if GUARD_LOG.exists() else []
    doc = {"totals": totals, "cases": len(rows), "negative_control_ulp_red": ulp_red,
           "guest_import_audit": {"on": True, "refused_imports": sorted({g["module"] for g in guard}),
                                  "refused_import_events": len(guard)},
           "guest_pids": len(GUEST["pids"]), "alive_after_kill": alive, "stubbed_imports_original_side": STUBBED,
           "rows": rows}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "parity.json").write_text(json.dumps(doc, indent=1, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: doc[k] for k in ("totals", "cases", "negative_control_ulp_red", "guest_import_audit",
                                          "guest_pids", "alive_after_kill")}, indent=1))
    bad = any(r["verdict"] == "MISMATCH" for r in rows) or alive or not ulp_red
    return 1 if bad else 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except Exception:
        traceback.print_exc()
        sys.exit(2)
