"""Tier-1 parity for RES4LYF's small nodes: the ORIGINAL in-process vs V2 in a real guest (gate only).

Nodes: TextBox1, TextBox2, TextConcatenate, SetImageSize, SetImageSizeWithScale; the sigma nodes "Sigmas Power",
"Sigmas From Text", "Sigmas Split Value", "Sigmas Rescale", "Sigmas Easing" and "Sigmas Resample"; the image nodes
"Film Grain", "Image Grain Add" and "Frames Slice"; and "Image Sharpen FS", which V2 refuses by name.

* Original side: the pristine package imported in this process. Its module-level imports of matplotlib, cv2, pywt
  and opensimplex come from DEPS when mounted, else from labelled import stubs (import_stubs.py), which these nodes
  never use.
* V2 side: each node runs in a real guest (GuestSession through _res4_sealed_guest_entry.py: the production entry
  order, with the guest import audit on) with exactly its declared permissions.
* Film Grain, Image Grain Add and Sigmas Resample's "model" mode draw from torch's global generator, which upstream
  never seeds. For an exact comparison both sides are seeded identically before the call: torch.manual_seed on the
  original side, a fresh guest seeded before it serves anything on the V2 side. Both sides run these calls with one
  torch thread: upstream's grain writes many random values to random positions with one indexed assignment, and with
  more threads, which of several values for one position wins depends on thread timing, so the original is not
  repeatable even for a fixed seed (recorded in the results as upstream_film_grain_repeatable_multithreaded).
* Comparisons are type-strict. Tensors compare by dtype, shape and bits, NaNs by position. Errors must occur on both
  sides (BOTH_FAIL), except where V2 refuses by name as designed (REFUSED_AS_DESIGNED, listed in the summary).
* Negative controls: a 1-ulp change to one V2 output must compare unequal, and a seeded node run with different seeds
  on the two sides must differ (so the seeded matches are not vacuous).
Writes /results/simple.json; exit 1 on any difference.
Run: run_in_gate.sh <RES4LYF-HEAD with v2> <v2/tests> <out> test_res4lyf_simple.py   (DEPS optional)
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
sys.path[:0] = [str(CORE), "/overlay"]
if Path("/deps").is_dir():
    sys.path.append("/deps")

from comfy.cli_args import args  # noqa: E402

args.cpu = True
import torch  # noqa: E402

import folder_paths  # noqa: E402,F401
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

STUBBED = import_stubs.install(["matplotlib", "cv2", "pywt", "opensimplex"],  # only those genuinely absent
                               noop_calls=["matplotlib.use"])  # the original calls it at import (see import_stubs)
PACK = Path(os.environ.get("RES4_PACK", "/pack"))
V2 = PACK / "v2"
RESULTS = Path(os.environ.get("RES4_RESULTS", "/results"))
TMP = Path(tempfile.mkdtemp(prefix="res4-simple-"))
GUARD_LOG = TMP / "import-guard.jsonl"
shutil.copytree(PACK, TMP / "RES4LYF", ignore=shutil.ignore_patterns("v2"))
sys.path.insert(0, str(TMP))
ORIGINAL = dict(importlib.import_module("RES4LYF").NODE_CLASS_MAPPINGS)


def import_package(name, root):
    spec = importlib.util.spec_from_file_location(name, root / "__init__.py", submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


SECURE = dict(import_package("res4lyf_secure", V2).NODE_CLASS_MAPPINGS)
GUEST = {"session": None, "pids": set()}
ROWS = []
# V2 refusals by design: the node id and a phrase its message must contain
DESIGNED_REFUSALS = {
    "Frames Slice": "a V2 IMAGE cannot be empty",
    "Image Sharpen FS": "Image Sharpen FS: not converted to Secure Nodes V2 yet (it blurs with OpenCV",
    "Image Gaussian Blur": "Image Gaussian Blur: not converted to Secure Nodes V2 yet (it blurs with OpenCV",
    "Latent to Cuda": "Latent to Cuda: not converted to Secure Nodes V2 yet (it moves the latent's tensors",
}


class SealedEntryGuestSession(GuestSession):
    """The production entry order with the guest import audit on (and an optional seed); see the entry's docstring."""

    seed = None

    def _guest_command(self, python):
        return [python, str(TESTS / "_res4_sealed_guest_entry.py")]

    def _adjust_guest_env(self, env):
        super()._adjust_guest_env(env)
        env["RES4_GUARD_ROOT"] = str(self.guest_runtime_root)
        env["RES4_GUARD_LOG"] = str(GUARD_LOG)
        if self.seed is not None:
            env["RES4_GUEST_SEED"] = str(self.seed)
            env["RES4_GUEST_THREADS"] = "1"


async def run_v2(node_id, inputs, seed=None):
    cls = SECURE[node_id]
    permissions = tuple(cls.SDK_PERMISSIONS)
    refs = _sdk.InProcessRefResolver()
    scope = _execution_metadata.ExecutionMetadataScope("res4-simple", DynamicPrompt({}), None, observe=True)
    scope.__enter__()
    guest = None
    try:
        plan = _sdk.ExecutionPlan(
            prompt_id="res4-simple", node_id="9", node_type=cls.__name__, tier="sandbox", node_module=cls.__module__,
            inputs=dict(inputs), input_mode="refs" if getattr(cls, "SDK_REFS", False) else "values",
            method="execute", permissions=permissions, prompt=None, extra_pnginfo=None,
            dynamic_prompt=DynamicPrompt({}), execution_metadata=scope)
        runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
        plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
        if seed is None:
            if GUEST["session"] is None:
                GUEST["session"] = await SealedEntryGuestSession("res4-simple", guest_runtime_root=V2).start()
            guest = GUEST["session"]
        else:  # a fresh guest whose global generator was seeded before it served anything
            guest = SealedEntryGuestSession(f"res4-simple-seed-{seed}", guest_runtime_root=V2)
            guest.seed = seed
            await guest.start()
        result = await guest.execute(plan, runtime, capabilities=permissions, tenant="res4-simple")
        if guest.last_guest_pid:
            GUEST["pids"].add(guest.last_guest_pid)
        return tuple([await refs.resolve(v) if isinstance(v, _sdk.Ref) else v for v in (result.result or ())])
    finally:
        scope.__exit__(None, None, None)
        if seed is not None and guest is not None:
            await guest.kill()


def run_original(node_id, inputs, seed=None, threads=1):
    cls = ORIGINAL[node_id]

    def call():
        return tuple(getattr(cls(), cls.FUNCTION)(**{k: (v.clone() if isinstance(v, torch.Tensor) else v)
                                                    for k, v in inputs.items()}))
    if seed is None:
        return call()
    previous = torch.get_num_threads()
    torch.set_num_threads(threads)  # seeded calls: one thread, as in the seeded guest (see the module docstring)
    try:
        torch.manual_seed(seed)
        return call()
    finally:
        torch.set_num_threads(previous)


INT_VIEW = {torch.float16: torch.int16, torch.bfloat16: torch.int16, torch.float32: torch.int32,
            torch.float64: torch.int64}


def same_tensor(a, b):
    if a.dtype != b.dtype or a.shape != b.shape or a.device != b.device:
        return False
    if a.dtype in INT_VIEW:  # bitwise (so -0.0 != 0.0), NaNs by position
        nan_a, nan_b = torch.isnan(a), torch.isnan(b)
        if not torch.equal(nan_a, nan_b):
            return False
        bits_a, bits_b = a.contiguous().view(INT_VIEW[a.dtype]), b.contiguous().view(INT_VIEW[b.dtype])
        return torch.equal(bits_a[~nan_a], bits_b[~nan_b])
    return torch.equal(a, b)


def same(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, torch.Tensor):
        return same_tensor(a, b)
    if isinstance(a, float):
        return a.hex() == b.hex()
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    return a == b


def show(value):
    if isinstance(value, torch.Tensor):
        flat = value.detach().double().flatten()
        return {"dtype": str(value.dtype), "shape": list(value.shape),
                "values": [float(v).hex() for v in flat.tolist()][:8] if value.numel() <= 64 else None,
                "sum": float(flat.nansum()) if value.numel() else 0.0}
    if isinstance(value, (list, tuple)):
        return [show(v) for v in value]
    if isinstance(value, dict):
        return {str(k): show(v) for k, v in value.items()}
    return value if not isinstance(value, str) or len(value) < 80 else value[:77] + "..."


def image(batch, height, width, channels, seed):
    return torch.rand((batch, height, width, channels), generator=torch.Generator().manual_seed(seed))


SCHEDULES = {
    "karras_f32": torch.tensor([14.614642, 7.4930, 3.5961, 1.5761, 0.6146, 0.2068, 0.0291675, 0.0],
                               dtype=torch.float32),
    "karras_f64": torch.tensor([14.614642, 7.4930, 3.5961, 1.5761, 0.6146, 0.2068, 0.0291675, 0.0],
                               dtype=torch.float64),
    "flow_f32": torch.linspace(1.0, 0.0, 9, dtype=torch.float32),
    "no_zero_f32": torch.tensor([10.0, 5.0, 2.5, 1.25, 0.6], dtype=torch.float32),
}


def cases():
    """(node id, inputs, seed or None, label)."""
    out = []
    add = lambda node, inputs, seed=None, label=None: out.append((node, inputs, seed, label))  # noqa: E731
    texts = ("", "a", "multi\nline ☀ \U0001d11e", "  spaced  ", "x" * 10000)
    for text in texts:
        add("TextBox1", {"text1": text})
    for text1, text2 in (("", ""), ("a", "b"), ("multi\nline", "☀ \U0001d11e"), ("  ", "x" * 5000)):
        add("TextBox2", {"text1": text1, "text2": text2})
    for inputs in ({}, {"separator": ", "}, {"text_1": "a"}, {"text_2": "b", "separator": "-"},
                   {"text_1": "a", "text_2": "b"}, {"text_1": "a", "text_2": "b", "separator": ", "},
                   {"text_1": "line 1", "text_2": "line 2", "separator": "\n"},
                   {"text_1": "☀", "text_2": "\U0001d11e", "separator": " é "},
                   {"text_1": "x" * 4000, "text_2": "y" * 4000, "separator": "|"}):
        add("TextConcatenate", inputs)
    for width, height in ((1024, 1024), (1, 1), (10000, 7), (513, 777)):
        add("SetImageSize", {"width": width, "height": height})
    for width, height, scale in ((1024, 1024, 1.0), (1000, 777, 1.5), (512, 768, 0.333), (1, 1, 0.0),
                                 (10000, 10000, 10000.0), (833, 1217, 2.71828), (7, 3, 0.9999999), (640, 480, 0.1)):
        add("SetImageSizeWithScale", {"width": width, "height": height, "scale_by": scale})
    for name, sigmas in SCHEDULES.items():
        for power in (1.0, 2.0, 0.5, 3.7, 0.0, -1.0, -0.5, 100.0):
            add("Sigmas Power", {"sigmas": sigmas.clone(), "power": power}, label=name)
    for text in ("", "1.0, 0.5, 0", "14.614642 7.4930 3.5961 1.5761 0.6146 0.2068 0.0291675 0", "1e-3 2e5",
                 "nan inf -inf", "1,,2", "  3 ,4 ", "abc", "1;2", " ".join(str(i / 7) for i in range(1000, 0, -1))):
        add("Sigmas From Text", {"text": text}, label=f"{len(text)}ch")
    split_schedules = {**SCHEDULES, "single_f32": torch.tensor([1.0]), "empty_f32": torch.tensor([])}
    for name, sigmas in split_schedules.items():
        for split in (0.0, 0.875, 1.0, 1.5761, 5.0, 100.0):
            for bias in (False, True):
                add("Sigmas Split Value", {"sigmas": sigmas.clone(), "split_value": split, "bias_split_up": bias},
                    label=name)
    constant = torch.full((6,), 2.5)
    for name, sigmas in {**SCHEDULES, "constant_f32": constant}.items():
        for start, end in ((1.0, 0.0), (0.0, 1.0), (14.61, 0.03), (-5.0, 5.0), (10000.0, -10000.0)):
            add("Sigmas Rescale", {"start": start, "end": end, "sigmas": sigmas.clone()}, label=name)
    easing_types = ("sine", "quad", "cubic", "quart", "quint", "expo", "circ", "back", "elastic", "bounce")
    for easing_type in easing_types:
        for mode in ("in", "out", "in_out"):
            for normalize_input in (True, False):
                for normalize_output in (True, False):
                    add("Sigmas Easing", {"sigmas": SCHEDULES["karras_f32"].clone(), "easing_type": easing_type,
                                          "easing_mode": mode, "normalize_input": normalize_input,
                                          "normalize_output": normalize_output, "strength": 1.0}, label="karras_f32")
        for strength in (0.1, 2.5, 10.0):
            add("Sigmas Easing", {"sigmas": SCHEDULES["flow_f32"].clone(), "easing_type": easing_type,
                                  "easing_mode": "in_out", "normalize_input": True, "normalize_output": True,
                                  "strength": strength}, label="flow_f32")
        add("Sigmas Easing", {"sigmas": SCHEDULES["karras_f64"].clone(), "easing_type": easing_type,
                              "easing_mode": "out", "normalize_input": False, "normalize_output": True,
                              "strength": 1.0}, label="karras_f64")
        add("Sigmas Easing", {"sigmas": constant.clone(), "easing_type": easing_type, "easing_mode": "in",
                              "normalize_input": True, "normalize_output": True, "strength": 1.0}, label="constant")
    for name in ("karras_f32", "karras_f64", "no_zero_f32"):
        for mode in ("linear", "nearest", "exponential", "power"):
            for length in (5, 10, 33):
                for rescale in (True, False):
                    add("Sigmas Resample", {"sigmas_in": SCHEDULES[name].clone(), "output_length": length,
                                            "mode": mode, "order": 8, "rescale_after": rescale}, label=name)
        for length in (5, 33):
            for order in (1, 3, 8):
                for rescale in (True, False):
                    add("Sigmas Resample", {"sigmas_in": SCHEDULES[name].clone(), "output_length": length,
                                            "mode": "polynomial", "order": order, "rescale_after": rescale},
                        label=name)
    add("Sigmas Resample", {"sigmas_in": SCHEDULES["karras_f32"].clone(), "output_length": 0, "mode": "linear",
                            "order": 8, "rescale_after": True}, label="karras_f32")
    for seed, length in ((1, 10), (2, 20)):
        add("Sigmas Resample", {"sigmas_in": SCHEDULES["karras_f32"].clone(), "output_length": length,
                                "mode": "model", "order": 8, "rescale_after": True}, seed=seed, label="karras_f32")
    grain_images = {"rgb_1x32x48": image(1, 32, 48, 3, 1), "rgb_2x24x20": image(2, 24, 20, 3, 2),
                    "rgba_1x16x16": image(1, 16, 16, 4, 3), "gray_1x16x24": image(1, 16, 24, 1, 4)}
    film = [("rgb_1x32x48", 1.0, 1.0, 1.0, 4, 1, 11), ("rgb_1x32x48", 0.25, 0.5, 1.5, 2, 1, 12),
            ("rgb_2x24x20", 0.6, 0.3, 0.9, 1, 3, 13), ("rgb_2x24x20", 0.01, 1.0, 255.0, 8, 1, 14),
            ("rgba_1x16x16", 1.0, 1.0, 1.0, 4, 1, 15), ("gray_1x16x24", 1.0, 1.0, 1.0, 4, 1, 16)]
    for name, density, intensity, highlights, supersample, repeats, seed in film:
        add("Film Grain", {"image": grain_images[name].clone(), "density": density, "intensity": intensity,
                           "highlights": highlights, "supersample_factor": supersample, "repeats": repeats},
            seed=seed, label=name)
    for name, weight, seed in (("rgb_1x32x48", 0.5, 21), ("rgb_2x24x20", -3.0, 22), ("rgb_1x32x48", 10000.0, 23),
                               ("rgba_1x16x16", 0.5, 24)):
        add("Image Grain Add", {"image": grain_images[name].clone(), "weight": weight}, seed=seed, label=name)
    frames = {"rgb_5x8x12": image(5, 8, 12, 3, 5), "rgba_3x6x6": image(3, 6, 6, 4, 6),
              "gray_4x5x7": image(4, 5, 7, 1, 7)}
    for name, start, stop in (("rgb_5x8x12", 0, 1), ("rgb_5x8x12", 1, 3), ("rgb_5x8x12", 2, 10),
                              ("rgb_5x8x12", 4, 5), ("rgb_5x8x12", 0, 10000), ("rgba_3x6x6", 1, 2),
                              ("gray_4x5x7", 0, 4), ("rgb_5x8x12", 5, 6), ("rgb_5x8x12", 3, 3),
                              ("rgb_5x8x12", 7, 9)):
        add("Frames Slice", {"frames": frames[name].clone(), "start": start, "stop": stop}, label=name)
    add("Image Sharpen FS", {"images": image(1, 16, 16, 3, 8), "method": "hard", "type": "median",
                             "intensity": 6}, label="rgb_1x16x16")
    # round 4
    for seed in (0, 1, 12345, 2**63 - 1, 2**64 - 2, 2**64 - 1):
        add("SeedGenerator", {"seed": seed})
    for name, sigmas in SCHEDULES.items():
        for multiplier in (1, 1.0, 0.5, -2.0, 0.0, 10000.0, 0.001):
            add("Sigmas Mult", {"sigmas": sigmas.clone(), "multiplier": multiplier}, label=name)
    for first, second in (("karras_f32", "karras_f64"), ("karras_f64", "karras_f32"), ("karras_f32", "karras_f32"),
                          ("flow_f32", "flow_f32"), ("karras_f32", "flow_f32"), ("no_zero_f32", "karras_f32")):
        for multiplier in (1.0, 0.75):
            add("Sigmas Mult", {"sigmas": SCHEDULES[first].clone(), "multiplier": multiplier,
                                "sigmas2": SCHEDULES[second].clone()}, label=f"{first}*{second}")
    for name, select in (("rgb_5x8x12", 0), ("rgb_5x8x12", 2), ("rgb_5x8x12", 4), ("rgb_5x8x12", 5),
                         ("rgb_5x8x12", 10000), ("rgba_3x6x6", 1), ("gray_4x5x7", 3)):
        add("Frame Select", {"frames": frames[name].clone(), "select": select}, label=name)
    tiles = {"rgb_1x8x12": image(1, 8, 12, 3, 9), "rgb_2x5x7": image(2, 5, 7, 3, 10),
             "rgba_1x6x6": image(1, 6, 6, 4, 11), "gray_1x7x5": image(1, 7, 5, 1, 12)}
    for name in tiles:
        for width, height in ((30, 20), (12, 8), (100, 7), (5, 3), (1, 1), (64, 64)):
            for crop in (True, False):
                add("Image Repeat Tile To Size", {"image": tiles[name].clone(), "width": width, "height": height,
                                                  "crop": crop}, label=name)
    for width, height in ((24, 24), (1024, 1024), (1000, 777), (1, 1), (7, 9)):
        for mode in ("sdxl", "cascade_b", "cascade_c", "exact", "default"):
            add("EmptyLatentImageCustom", {"width": width, "height": height, "batch_size": 1, "channels": "4",
                                           "mode": mode, "compression": 42, "precision": "fp32"})
    for channels, precision, compression, batch in (("16", "fp16", 4, 3), ("16", "fp64", 128, 2),
                                                    ("4", "fp16", 42, 4), ("16", "fp32", 32, 1)):
        add("EmptyLatentImageCustom", {"width": 512, "height": 768, "batch_size": batch, "channels": channels,
                                       "mode": "cascade_c", "compression": compression, "precision": precision})
    add("Image Gaussian Blur", {"images": image(1, 16, 16, 3, 13), "size": 6}, label="rgb_1x16x16")
    add("Latent to Cuda", {"latent": {"samples": torch.zeros((1, 4, 8, 8))}, "to_cuda": True,
                           "full_latent": True})
    return out


async def compare(node_id, inputs, seed, label, v2_seed=None):
    case = f"{node_id}:{label + ':' if label else ''}" + ",".join(
        f"{k}={v if not isinstance(v, (torch.Tensor, str)) else (len(v) if isinstance(v, str) else 'tensor')}"
        for k, v in inputs.items()) + (f":seed={seed}" if seed is not None else "")
    try:
        expected, expected_error = run_original(node_id, inputs, seed), None
    except Exception as error:  # noqa: BLE001
        expected, expected_error = None, f"{type(error).__name__}: {error}"[:300]
    try:
        actual, actual_error = await run_v2(node_id, inputs, seed if v2_seed is None else v2_seed), None
    except Exception as error:  # noqa: BLE001
        actual, actual_error = None, f"{type(error).__name__}: {error}"[:400]
    designed = DESIGNED_REFUSALS.get(node_id)
    if actual_error and designed and designed in actual_error:
        verdict = "REFUSED_AS_DESIGNED"
    elif expected_error or actual_error:
        verdict = "BOTH_FAIL" if expected_error and actual_error else "MISMATCH"
    else:
        verdict = "EXACT" if same(expected, actual) else "MISMATCH"
    return {"node": node_id, "case": case, "verdict": verdict, "seed": seed, "expected": show(expected),
            "actual": show(actual), "expected_error": expected_error, "actual_error": actual_error}, expected, actual


async def main():
    perturb_source = None
    for node_id, inputs, seed, label in cases():
        row, expected, actual = await compare(node_id, inputs, seed, label)
        ROWS.append(row)
        if row["verdict"] != "EXACT":
            print(row["verdict"], row["case"], row["expected_error"], row["actual_error"], flush=True)
        elif perturb_source is None and node_id == "Sigmas Easing":
            perturb_source = (expected, actual)
    # negative control 1: one ulp changed in an EXACT V2 output must compare unequal
    expected, actual = perturb_source
    bumped = actual[0].clone()
    bumped[1] = torch.nextafter(bumped[1], torch.tensor(float("inf"), dtype=bumped.dtype))
    ulp_red = not same(expected, (bumped,))
    # negative control 2: Film Grain with seed 31 on the original side and 32 on the V2 side must differ
    seed_row, _e, _a = await compare("Film Grain", {
        "image": image(1, 32, 48, 3, 1), "density": 1.0, "intensity": 1.0, "highlights": 1.0,
        "supersample_factor": 4, "repeats": 1}, 31, "rgb_1x32x48:negative-control", v2_seed=32)
    seed_red = seed_row["verdict"] == "MISMATCH"
    # informational: upstream itself, same seed twice, with this process's default thread count
    grain = {"image": image(1, 32, 48, 3, 1), "density": 1.0, "intensity": 1.0, "highlights": 1.0,
             "supersample_factor": 4, "repeats": 1}
    threads = torch.get_num_threads()
    upstream_repeatable = {
        "threads": threads,
        "same_seed_twice_equal": same(run_original("Film Grain", grain, 11, threads),
                                      run_original("Film Grain", grain, 11, threads)),
        "same_seed_twice_equal_one_thread": same(run_original("Film Grain", grain, 11, 1),
                                                 run_original("Film Grain", grain, 11, 1))}
    if GUEST["session"] is not None:
        await GUEST["session"].kill()
    await asyncio.sleep(0.5)
    alive = [pid for pid in GUEST["pids"] if Path(f"/proc/{pid}").exists()]
    totals = {}
    for row in ROWS:
        totals.setdefault(row["node"], {}).setdefault(row["verdict"], 0)
        totals[row["node"]][row["verdict"]] += 1
    guard = [json.loads(line) for line in GUARD_LOG.read_text().splitlines()] if GUARD_LOG.exists() else []
    doc = {"totals": totals, "cases": len(ROWS),
           "refused_as_designed": [r["case"] for r in ROWS if r["verdict"] == "REFUSED_AS_DESIGNED"],
           "negative_control_ulp_red": ulp_red, "negative_control_seed_red": seed_red,
           "negative_control_seed_row": seed_row,
           "upstream_film_grain_repeatable_multithreaded": upstream_repeatable,
           "guest_import_audit": {"on": True, "refused_imports": sorted({g["module"] for g in guard}),
                                  "refused_import_events": len(guard)},
           "guest_pids": len(GUEST["pids"]), "alive_after_kill": alive,
           "stubbed_imports_original_side": STUBBED, "rows": ROWS}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "simple.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: doc[k] for k in ("totals", "cases", "refused_as_designed", "negative_control_ulp_red",
                                          "negative_control_seed_red", "upstream_film_grain_repeatable_multithreaded",
                                          "guest_import_audit", "guest_pids", "alive_after_kill")}, indent=1))
    bad = any(r["verdict"] == "MISMATCH" for r in ROWS) or alive or not ulp_red or not seed_red
    return 1 if bad else 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except Exception:
        traceback.print_exc()
        sys.exit(2)
