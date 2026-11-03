"""Regression test for whiterabbit repair r1 (gate).

    DEPS=<torchlanc 1.1.1 unpacked> run_in_gate.sh <snapshot dir x4815da4, or the pack folder> \
        <.../v2/tests> <results> test_whiterabbit_watermark_chain.py

The case that was BLOCKED in deployment: BatchResizeWithLanczos -> BatchWatermarkSingle ->
AutocropToLoop -> PrepareLoopFrames, with the graph's own parameters, on synthetic frames and a synthetic
watermark staged in a temporary input folder. Checks:
  * loader: every class secure-nodes.json names is a module attribute of v2/_secure_nodes.py;
  * validation through core and a real guest: the staged watermark is accepted, and a missing one is
    refused with core's "Value not in list" text;
  * each of the four nodes, in-process (core's V3 refs path) and through the real guest, returns exactly
    the original node's outputs for the same inputs (each node fed the original's upstream outputs).
Writes /results/chain.json; exits 1 on any failed check.
"""

import asyncio
import importlib
import importlib.util
import inspect
import json
import os
import shutil
import sys
import traceback
import types
from pathlib import Path

sys.path[:0] = ["/core", "/overlay", "/tests"]
sys.path.append("/deps")

from comfy.cli_args import args  # noqa: E402

args.cpu = True

import comfy.samplers  # noqa: E402,F401
import execution  # noqa: E402
import folder_paths  # noqa: E402
import nodes as core_nodes  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
from PIL import Image  # noqa: E402
from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402

PACK_FOLDER = "WhiteRabbit-HEAD"
INPUT = Path("/tmp/wr-input")
checks = []
WATERMARK = "plain_mask_768.png"
PARAMS = {
    "BatchResizeWithLanczos": dict(crop_position="top-left", divisible_by=8, height=192, width=256,
                                   max_batch_size=2, pad_color="16, 32, 48", precision="fp32",
                                   resize_mode="Pad (Fit + Pad)", sinc_window=4),
    "BatchWatermarkSingle": dict(max_batch_size=2, optical_padding=True, optical_strength=60, padding_x=7,
                                 padding_y=9, position="bottom-right", precision="fp32", rotation=17,
                                 scale=25, sinc_window=4, transparency=65, watermark=WATERMARK),
    "AutocropToLoop": dict(accelerate_with_gpu=True, distance_metric="MSE", include_first_step=True,
                           include_global_median_step=True, include_last_step=True, max_end_crop_frames=1,
                           score_in_8bit=True, seam_window_frames=1, ssim_downsample_scales="1,2",
                           use_exposure_guard=True, use_flow_guard=False, use_mixed_precision=False,
                           use_ssim_similarity=True, weight_exposure=0.15, weight_flow=0.0,
                           weight_similarity=0.25, weight_step_size=0.6),
    "PrepareLoopFrames": dict(),
}
INPUT_NAME = {"BatchResizeWithLanczos": "image", "BatchWatermarkSingle": "image",
              "AutocropToLoop": "clip_frames", "PrepareLoopFrames": "images"}
CHAIN = ["BatchResizeWithLanczos", "BatchWatermarkSingle", "AutocropToLoop", "PrepareLoopFrames"]


def record(name, ok, detail=None):
    checks.append({"check": name, "ok": bool(ok), "detail": None if ok else str(detail)[:1500]})
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": {str(detail)[:400]}"), flush=True)


def pack_head() -> Path:
    root = Path("/pack")
    if (root / "v2").is_dir():
        return root
    return [d for d in sorted(root.iterdir()) if d.is_dir() and not d.name.startswith(".")][0]


def snapshot_dir() -> Path:
    root = Path("/pack")
    if not (root / "v2").is_dir():
        return root
    snap = Path("/tmp/wr-snapshot")
    if not (snap / PACK_FOLDER).is_dir():
        shutil.copytree(root, snap / PACK_FOLDER, ignore=shutil.ignore_patterns("__pycache__"))
    return snap


def load_package(name, folder):
    spec = importlib.util.spec_from_file_location(name, folder / "__init__.py",
                                                  submodule_search_locations=[str(folder)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def stage_inputs():
    """Synthetic stand-ins: a 768x768 RGBA mask-style watermark and a 4-frame clip."""
    if INPUT.exists():
        shutil.rmtree(INPUT)
    INPUT.mkdir(parents=True)
    folder_paths.set_input_directory(str(INPUT))
    alpha = np.zeros((768, 768), dtype=np.uint8)
    alpha[200:568, 150:618] = 255
    rgba = np.dstack([np.full((768, 768), 255, np.uint8)] * 3 + [alpha])
    Image.fromarray(rgba, "RGBA").save(INPUT / WATERMARK)
    Image.fromarray(np.zeros((8, 8, 3), np.uint8)).save(INPUT / "other.jpg")
    (INPUT / "notes.txt").write_text("not an image")
    g = torch.Generator().manual_seed(11)
    base = torch.rand(1, 200, 300, 3, generator=g)
    inverse = 1.0 - base
    frame_b = base * 0.85 + inverse * 0.15
    frame_c = base * 0.65 + inverse * 0.35
    return torch.cat([base, frame_b, frame_c, frame_b], dim=0)


def pristine_classes(head):
    parent = types.ModuleType("wr_pristine")
    parent.__path__ = [str(head)]
    sys.modules["wr_pristine"] = parent
    scaling = importlib.import_module("wr_pristine.whiterabbit.nodes_v3.scaling")
    watermark = importlib.import_module("wr_pristine.whiterabbit.nodes_v3.watermark")
    autocrop = importlib.import_module("wr_pristine.whiterabbit.nodes_v3.loop_autocrop")
    looping = importlib.import_module("wr_pristine.whiterabbit.nodes_v3.looping")
    return {"BatchResizeWithLanczos": scaling.BatchResizeWithLanczosV3,
            "BatchWatermarkSingle": watermark.BatchWatermarkSingleV3,
            "AutocropToLoop": autocrop.AutocropToLoopV3,
            "PrepareLoopFrames": looping.PrepareLoopFramesV3}


def same(a, b):
    if isinstance(a, torch.Tensor) or isinstance(b, torch.Tensor):
        if not (isinstance(a, torch.Tensor) and isinstance(b, torch.Tensor)):
            return False, f"{type(a).__name__} vs {type(b).__name__}"
        if a.dtype != b.dtype or a.shape != b.shape:
            return False, f"{a.dtype}/{tuple(a.shape)} vs {b.dtype}/{tuple(b.shape)}"
        if not torch.equal(a.cpu(), b.cpu()):
            return False, f"max abs {(a.double().cpu() - b.double().cpu()).abs().max().item()!r}"
        return True, None
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return False, f"len {len(a)} vs {len(b)}"
        for index, (x, y) in enumerate(zip(a, b)):
            ok, detail = same(x, y)
            if not ok:
                return False, f"[{index}] {detail}"
        return True, None
    return (a == b and type(a) is type(b)), f"{a!r} vs {b!r}"


async def core_output(obj, node_id, inputs):
    """A node through core's full output path; returns its outputs (first value of each list)."""
    if hasattr(obj, "GET_SCHEMA"):
        obj.GET_SCHEMA()
    output, _ui, _sub, _pending = await execution.get_output_data(
        "wr-chain", node_id, obj, {key: [value] for key, value in inputs.items()})
    return tuple(values[0] for values in output)


async def run_chain(classes, frames, label, original):
    """Each node gets the original's upstream output, so every comparison has identical inputs."""
    upstream = frames
    for index, node in enumerate(CHAIN):
        inputs = dict(PARAMS[node], **{INPUT_NAME[node]: upstream})
        try:
            got = await core_output(classes[node], str(40 + index), inputs)
            ok, detail = same(tuple(original[node]), got)
        except Exception:  # noqa: BLE001
            ok, detail = False, traceback.format_exc()[-1200:]
        record(f"{label}: {node} == original", ok, detail)
        upstream = original[node][0]


async def run() -> dict:
    facts = {}
    head = pack_head()
    v2 = head / "v2"
    frames = stage_inputs()

    manifest = json.loads((v2 / "secure-nodes.json").read_bytes())
    package = load_package("wr_v2", v2)
    module = sys.modules["wr_v2._secure_nodes"]
    missing = [row["class"] for row in manifest["nodes"].values() if not hasattr(module, row["class"])]
    record("loader: every manifest class is a module attribute", not missing, missing)

    P = pristine_classes(head)
    original = {}
    upstream = frames
    for node in CHAIN:
        inputs = dict(PARAMS[node], **{INPUT_NAME[node]: upstream})
        result = P[node].execute(**inputs)
        if inspect.isawaitable(result):
            result = await result
        original[node] = tuple(result.result if hasattr(result, "result") else result)
        upstream = original[node][0]
    facts["original_shapes"] = {n: [tuple(v.shape) if isinstance(v, torch.Tensor) else v for v in original[n]]
                                for n in CHAIN}

    v2_classes = {node: package.NODE_CLASS_MAPPINGS[node] for node in CHAIN}
    await run_chain(v2_classes, frames, "in-process", original)

    loaded = packdb.load_pack(snapshot_dir(), mount_name="custom_nodes.wr_guest_proxy",
                              pack_id="whiterabbit/x4815da4")
    proxies = loaded.node_mappings
    session = await GuestSession("wr-guest", guest_runtime_root=Path("/deps")).start()
    facts["sandbox_kind"] = session.sandbox_kind

    class Backend:
        async def dispatch(self, plan, local_call, runtime):
            caps = set(plan.permissions or ())
            if getattr(plan, "input_mode", "refs") == "values":
                caps.add("raw")
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
            return await session.execute(plan, runtime, capabilities=frozenset(caps), tenant="wr-guest")

    previous = _sdk.providers.execution_backend
    _sdk.providers.register_execution_backend(Backend())
    saved = {node: core_nodes.NODE_CLASS_MAPPINGS.get(node) for node in list(proxies) + ["EmptyImage"]}
    for node_id, proxy in proxies.items():
        core_nodes.NODE_CLASS_MAPPINGS[node_id] = proxy
    core_nodes.NODE_CLASS_MAPPINGS.setdefault("EmptyImage", core_nodes.EmptyImage)
    try:
        def prompt(watermark):
            # The image comes from core's EmptyImage, which validates without any file.
            return {"10": {"class_type": "EmptyImage",
                           "inputs": {"width": 64, "height": 64, "batch_size": 1, "color": 0}},
                    "39": {"class_type": "BatchWatermarkSingle",
                           "inputs": dict(PARAMS["BatchWatermarkSingle"], image=["10", 0], watermark=watermark)}}
        validated = {}
        ok_flag, errors, _ = await execution.validate_inputs("wr-guest", prompt(WATERMARK), "39", validated)
        record("validation (guest): the staged watermark is accepted", ok_flag is True and not errors,
               {"ok": repr(ok_flag), "errors": errors, "upstream": validated.get("10")})
        ok_flag, errors, _ = await execution.validate_inputs("wr-guest", prompt("nope.png"), "39", {})
        want = f"Value not in list: watermark: 'nope.png' not in {['other.jpg', WATERMARK]}"
        record("validation (guest): a missing watermark is refused with core's text",
               ok_flag is False and any(want in (e.get("details") or "") for e in errors), errors)
        await run_chain(proxies, frames, "guest", original)
    finally:
        for node_id, cls in saved.items():
            if cls is None:
                core_nodes.NODE_CLASS_MAPPINGS.pop(node_id, None)
            else:
                core_nodes.NODE_CLASS_MAPPINGS[node_id] = cls
        _sdk.providers.register_execution_backend(previous)
        facts["guest_pid"] = session.last_guest_pid
        await session.kill()
    record("guest: out-of-process", facts.get("guest_pid") not in (None, os.getpid()), facts.get("guest_pid"))
    return facts


def main() -> int:
    try:
        facts = asyncio.run(run())
    except Exception:  # noqa: BLE001
        facts = {"error": traceback.format_exc()}
        record("session", False, facts["error"])
    failed = [c["check"] for c in checks if not c["ok"]]
    result = {"pack": "whiterabbit", "repair": "r1", "checks": checks, "failed": failed, "facts": facts,
              "verdict": "PASS" if not failed else "FAIL"}
    Path("/results/chain.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({"verdict": result["verdict"], "failed": failed}))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
