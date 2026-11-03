"""Impact Pack fidelity repair r5 (PreviewBridge, no painted mask): parity in the lane gate.

DEPS=<the unpacked Impact dependency-profile wheels; upstream-only test needs (piexif, dill) under _orig_only/> \
run_in_gate.sh <root holding ComfyUI-Impact-Pack-HEAD/> <Impact v2/tests> <results> test_preview_bridge_repair_r5.py

Each case is a first run of a PreviewBridge node (a new node id, no mask painted in the mask editor), for every
block / restore_mask combination and two image sizes. Original: the pristine Impact Pack bridge_nodes.PreviewBridge
under Core (previews saved to a /tmp temp directory). v2: the repaired handler with a fake SDK context (ui previews and
graph.block). Compared: the pixels, the mask (in (1, H, W) layout) and whether both outputs are blocked.
"""
import asyncio
import glob
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import types
import warnings

sys.dont_write_bytecode = True
warnings.simplefilter("ignore")
ROOT = "/pack"
IMPACT = os.path.join(ROOT, "ComfyUI-Impact-Pack-HEAD")
RESULTS = "/results"
DEPS = "/deps"
BASE = glob.glob("/bases/0cd9adec*/common-site-packages")[0]
for _index, _path in enumerate((DEPS, BASE, "/core", "/overlay")):
    sys.path.insert(_index, _path)
os.environ.setdefault("HOME", "/tmp")


def cases():
    return [{"uid": f"pb{i}", "block": block, "restore_mask": restore, "size": size}
            for i, (block, restore, size) in enumerate((b, r, s) for b in (False, True)
                                                        for r in ("never", "always", "if_same_size")
                                                        for s in ((64, 96), (32, 32)))]


def make_image(size):
    import torch
    g = torch.Generator().manual_seed(size[0] * 1000 + size[1])
    return torch.rand((1, size[0], size[1], 3), generator=g)


def digest(value):
    import numpy as np
    import torch
    value = torch.as_tensor(value)
    if value.ndim == 2:
        value = value.unsqueeze(0)
    value = np.ascontiguousarray(value.detach().cpu().float().numpy())
    return [list(value.shape), hashlib.sha256(value.tobytes()).hexdigest()]


def outcome(fn):
    try:
        return ["value", fn()]
    except Exception as exc:
        return ["error", type(exc).__name__, str(exc)]


def run_original(plan, out_path):
    sys.path.insert(0, os.path.join(DEPS, "_orig_only"))
    import comfy.cli_args
    comfy.cli_args.args.cpu = True
    import folder_paths
    import server

    class Routes:
        def __getattr__(self, _name):
            return lambda *_args, **_kwargs: lambda function: function

    class Instance:
        routes = Routes()
        prompt_queue = types.SimpleNamespace(currently_running={})

        def __getattr__(self, _name):
            return lambda *_args, **_kwargs: None

    server.PromptServer.instance = Instance()
    os.makedirs("/tmp/pb-temp", exist_ok=True)
    folder_paths.set_temp_directory("/tmp/pb-temp")
    root = "/tmp/orig-impact"
    shutil.copytree(IMPACT, root, ignore=shutil.ignore_patterns("v2", "__pycache__", ".git"))
    sys.path.insert(0, os.path.join(root, "modules"))
    import impact.config  # noqa: F401  (upstream __init__ order)
    import impact.impact_server  # noqa: F401
    import impact.bridge_nodes as bridge_nodes
    from comfy_execution.graph import ExecutionBlocker
    records = []
    for case in plan:
        def run():
            out = bridge_nodes.PreviewBridge().doit(make_image(case["size"]), "", case["uid"], case["block"],
                                                    case["restore_mask"])
            pixels, mask = out["result"]
            if isinstance(pixels, ExecutionBlocker) and isinstance(mask, ExecutionBlocker):
                return "BLOCKED"
            return {"pixels": digest(pixels), "mask": digest(mask)}
        records.append(outcome(run))
    with open(out_path, "w") as handle:
        json.dump({"records": records}, handle)


def run_v2(plan, out_path):
    spec = importlib.util.spec_from_file_location("impact_v2", os.path.join(IMPACT, "v2", "__init__.py"),
                                                  submodule_search_locations=[os.path.join(IMPACT, "v2")])
    package = importlib.util.module_from_spec(spec)
    sys.modules["impact_v2"] = package
    spec.loader.exec_module(package)
    nodes = sys.modules["impact_v2._secure_nodes"]
    blocked = object()

    class Ui:
        async def preview_images(self, reference):
            return {"images": []}

    class Graph:
        async def block(self, reason=None):
            return blocked

    async def from_raw(value):
        return ("image-ref", tuple(value.shape))

    context = types.SimpleNamespace(ui=Ui(), graph=Graph())
    nodes.sdk = types.SimpleNamespace(ctx=lambda: context, ImageRef=types.SimpleNamespace(_from_raw=from_raw))
    records = []
    for case in plan:
        def run():
            out = asyncio.run(nodes._preview_bridge(make_image(case["size"]), image="", block=case["block"],
                                                    restore_mask=case["restore_mask"]))
            pixels, mask = out["result"]
            if pixels is blocked and mask is blocked:
                return "BLOCKED"
            return {"pixels": digest(pixels), "mask": digest(mask)}
        records.append(outcome(run))
    with open(out_path, "w") as handle:
        json.dump({"records": records}, handle)


def main(argv):
    if argv[:1] == ["side"]:
        plan = json.load(open(argv[2]))
        return (run_original if argv[1] == "original" else run_v2)(plan, argv[3]) or 0
    plan = cases()
    with open("/tmp/plan.json", "w") as handle:
        json.dump(plan, handle)
    sides = {}
    for side in ("original", "v2"):
        with open(os.path.join(RESULTS, f"side-{side}.log"), "w") as log:
            proc = subprocess.run([sys.executable, "-I", "-B", os.path.abspath(__file__), "side", side, "/tmp/plan.json",
                                   f"/tmp/out-{side}.json"], stdout=log, stderr=subprocess.STDOUT, timeout=1800)
        if proc.returncode != 0:
            print(f"side {side} failed ({proc.returncode}); see side-{side}.log")
            return 1
        sides[side] = json.load(open(f"/tmp/out-{side}.json"))
        shutil.copyfile(f"/tmp/out-{side}.json", os.path.join(RESULTS, f"outcomes-{side}.json"))
    original, v2 = sides["original"], sides["v2"]
    mismatches = [{"case": c, "original": w, "v2": g} for c, w, g in zip(plan, original["records"], v2["records"]) if w != g]
    blocked = sum(1 for w in original["records"] if w == ["value", "BLOCKED"])
    probe = next(g for w, g in zip(original["records"], v2["records"]) if isinstance(w[1], dict))
    negative_red = json.loads(json.dumps(probe)) != ["value", {"pixels": probe[1]["pixels"], "mask": [[1, 1, 1], "0"]}]
    ok = not mismatches and all(w[0] == "value" for w in original["records"])
    parity = {"status": "PASS" if ok else "FAIL",
              "PreviewBridge": {"verdict": "EXACT" if not mismatches else "MISMATCH", "cases": len(plan),
                                "blocked_cases": blocked, "mismatches": len(mismatches)},
              "negative_control": {"perturbation": "mask digest replaced", "turned_red": negative_red}}
    with open(os.path.join(RESULTS, "parity.json"), "w") as handle:
        json.dump(parity, handle, indent=1, sort_keys=True)
        handle.write("\n")
    with open(os.path.join(RESULTS, "mismatches.json"), "w") as handle:
        json.dump(mismatches, handle, indent=1)
        handle.write("\n")
    print(json.dumps(parity, indent=1))
    return 0 if ok and negative_red else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
