"""Impact Pack fidelity repair r3 (SEGS chain): parity in the lane gate.

DEPS=<the unpacked Impact dependency-profile wheels; upstream-only test needs (piexif, dill) under _orig_only/> \
run_in_gate.sh <root holding ComfyUI-Impact-Pack-HEAD/> <Impact v2/tests> <results> test_segs_repair_r3.py

  M  MaskToSEGS -> SegsToCombinedMask on synthetic masks (blobs, holes, soft values, edges, batches, empty) and
     every combination of combined / crop_factor / bbox_fill / drop_size / contour_fill. Original: the pristine
     Impact Pack segs_nodes.MaskToSEGS.doit and SegsToCombinedMask.doit under Core. v2: the repaired handlers,
     their SEGS and masks passed through the overlay's wire encoder (tensors as refs), then JSON and decode.
  L  the switch lazy check (ImpactSwitch / LatentSwitch / SEGSSwitch). Core calls check_lazy_status with each
     Autogrow value tagged as (value, original input name) (execution.py, create_dynamic_tuple) and expects that
     name back for an unevaluated selected input. The tagged values cross the wire both with tuples preserved and
     as lists (a guest wire without the containers feature).
"""
import asyncio
import glob
import hashlib
import importlib.abc
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
MASKS = ["rect", "two", "ring", "soft", "tiny", "empty", "edge", "noise", "batch"]


def make_mask(kind):
    import torch
    m = torch.zeros((80, 96))
    if kind == "rect":
        m[20:50, 30:70] = 1.0
    elif kind == "two":
        m[5:25, 5:30] = 1.0
        m[40:75, 50:90] = 1.0
    elif kind == "ring":
        m[10:70, 10:80] = 1.0
        m[25:55, 30:60] = 0.0
    elif kind == "soft":
        m[10:40, 10:40] = 0.5
        m[45:70, 50:85] = 1.0
    elif kind == "tiny":
        m[3:6, 3:6] = 1.0
        m[30:60, 40:44] = 1.0
        m[70:78, 10:40] = 1.0
    elif kind == "edge":
        m[0:30, 0:20] = 1.0
        m[60:80, 80:96] = 1.0
    elif kind == "noise":
        g = torch.Generator().manual_seed(3)
        m = (torch.rand((80, 96), generator=g) > 0.93).float()
        m[30:45, 30:50] = 1.0
    elif kind == "batch":
        b = torch.zeros((2, 80, 96))
        b[0, 10:30, 10:40] = 1.0
        b[1, 40:70, 50:90] = 1.0
        return b
    return m.unsqueeze(0)


def cases():
    out = []
    for kind in MASKS:
        for combined in (True, False):
            for crop_factor in (1.0, 1.4, 3.0):
                for bbox_fill in (False, True):
                    for drop_size in (1, 10):
                        for contour_fill in (False, True):
                            out.append({"mask": kind, "combined": combined, "crop_factor": crop_factor,
                                        "bbox_fill": bbox_fill, "drop_size": drop_size, "contour_fill": contour_fill})
    return out


def digest(value):
    import numpy as np
    value = np.ascontiguousarray(np.asarray(value, dtype=np.float32))
    return [list(value.shape), hashlib.sha256(value.tobytes()).hexdigest()]


def segs_record(shape, items):
    import numpy as np
    import torch
    rows = []
    for item in items:
        mask = item[1]
        mask = mask.detach().cpu().numpy() if isinstance(mask, torch.Tensor) else np.asarray(mask)
        if mask.ndim == 3 and mask.shape[0] == 1:
            mask = mask[0]
        rows.append({"mask": digest(mask), "confidence": float(np.asarray(item[2]).reshape(-1)[0]),
                     "crop_region": [int(v) for v in item[3]], "bbox": [float(v) for v in item[4]],
                     "label": str(item[5])})
    return {"shape": [int(v) for v in shape], "items": rows}


def mask_record(mask):
    import torch
    mask = torch.as_tensor(mask)
    if mask.ndim == 2:
        mask = mask.unsqueeze(0)
    return digest(mask.float().numpy())


def outcome(fn):
    try:
        return ["value", fn()]
    except Exception as exc:
        return ["error", type(exc).__name__, str(exc)]


# ---------------------------------------------------------------- original side
def run_original(plan, out_path):
    sys.path.insert(0, os.path.join(DEPS, "_orig_only"))
    import comfy.cli_args
    comfy.cli_args.args.cpu = True
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
    root = "/tmp/orig-impact"
    shutil.copytree(IMPACT, root, ignore=shutil.ignore_patterns("v2", "__pycache__", ".git"))
    sys.path.insert(0, os.path.join(root, "modules"))
    import impact.config  # noqa: F401  (upstream __init__ order)
    import impact.impact_server  # noqa: F401
    import impact.segs_nodes as segs_nodes
    records = []
    for case in plan:
        def run():
            (segs,) = segs_nodes.MaskToSEGS.doit(make_mask(case["mask"]), case["combined"], case["crop_factor"],
                                                 case["bbox_fill"], case["drop_size"], case["contour_fill"])
            (mask,) = segs_nodes.SegsToCombinedMask().doit(segs)
            return {"segs": segs_record(segs[0], segs[1]), "combined_mask": mask_record(mask)}
        records.append(outcome(run))
    with open(out_path, "w") as handle:
        json.dump({"records": records}, handle)


# ---------------------------------------------------------------- v2 side
GUEST_BASE = {"av", "blake3", "comfy_api", "comfy_secure_nodes", "comfy_secure_sdk", "filelock", "fsspec", "iniconfig",
              "jinja2", "markupsafe", "mpmath", "networkx", "numpy", "nvidia", "packaging", "PIL", "pluggy", "psutil",
              "pygments", "pytest", "_pytest", "py", "pytest_asyncio", "safetensors", "setuptools", "pkg_resources",
              "_distutils_hack", "sympy", "torch", "functorch", "torchgen", "triton", "typing_extensions", "wheel"}


class GuestImports(importlib.abc.MetaPathFinder):
    def __init__(self, allowed):
        self.allowed, self.blocked = allowed, set()

    def find_spec(self, fullname, path, target=None):
        top = fullname.split(".")[0]
        if top in sys.stdlib_module_names or top in self.allowed or top.startswith("_"):
            return None
        frame = sys._getframe(1)
        while frame and frame.f_code.co_filename.startswith("<frozen"):
            frame = frame.f_back
        if frame is not None and not frame.f_code.co_filename.startswith(("/pack/", DEPS)):
            return None
        self.blocked.add(fullname)
        raise ModuleNotFoundError(f"blocked in guest emulation: {fullname}", name=fullname)


def run_v2(plan, out_path):
    import torch
    deps_top = {n[:-3] if n.endswith(".py") else n for n in os.listdir(DEPS) if not n.endswith((".dist-info", ".data", ".libs"))}
    finder = GuestImports(GUEST_BASE | deps_top | {"impact_v2"})
    sys.meta_path.insert(0, finder)
    spec = importlib.util.spec_from_file_location("impact_v2", os.path.join(IMPACT, "v2", "__init__.py"),
                                                  submodule_search_locations=[os.path.join(IMPACT, "v2")])
    package = importlib.util.module_from_spec(spec)
    sys.modules["impact_v2"] = package
    spec.loader.exec_module(package)
    nodes = sys.modules["impact_v2._secure_nodes"]
    from comfy_api.latest import sdk as public_sdk
    wire_spec = importlib.util.spec_from_file_location("overlay_wire", "/overlay/comfy_secure_nodes/transport/wire.py")
    wire = importlib.util.module_from_spec(wire_spec)
    wire_spec.loader.exec_module(wire)
    counter = [0]

    def ref(cls, kind):
        counter[0] += 1
        return cls(kind=kind, id=f"t{counter[0]}")

    def through_wire(value, preserve_tuples=False):
        if isinstance(value, tuple) and len(value) == 2 and isinstance(value[1], list):
            value = (tuple(value[0]), [tuple([None if item[0] is None else ref(public_sdk.ImageRef, "IMAGE"),
                                              ref(public_sdk.MaskRef, "MASK"), *item[2:]]) for item in value[1]])
        elif isinstance(value, torch.Tensor):
            value = ref(public_sdk.MaskRef, "MASK")
        return wire.decode(json.loads(json.dumps(wire.encode(value, preserve_tuples=preserve_tuples))),
                           preserve_tuples=preserve_tuples)

    records, wire_failures = [], []
    for index, case in enumerate(plan):
        def run():
            (segs,) = asyncio.run(nodes._mask_to_segs_upstream(make_mask(case["mask"]), case["combined"],
                                                               case["crop_factor"], case["bbox_fill"],
                                                               case["drop_size"], case["contour_fill"]))
            through_wire(segs)
            (mask,) = asyncio.run(nodes._segs_to_combined_mask_upstream(segs))
            through_wire(mask)
            return {"segs": segs_record(segs[0], segs[1]), "combined_mask": mask_record(mask)}
        try:
            records.append(outcome(run))
        except Exception as exc:
            records.append(["error", type(exc).__name__, str(exc)])
            wire_failures.append(index)

    # L: the lazy contract, through the wire both ways
    lazy = []
    for preserve in (True, False):
        for select in (1, 2, 3):
            for evaluated in (True, False):
                values = {"input1": None, "input2": None, "input3": None}
                if evaluated:
                    values[f"input{select}"] = [0, 1]
                # execution.py: build_nested_inputs with create_dynamic_tuple tags each value (value, flat key)
                tagged = {k: (v, f"inputs.{k}") for k, v in values.items()}
                sent = through_wire({"select": select, "inputs": tagged}, preserve_tuples=preserve)
                got = asyncio.run(nodes._switch_lazy(**sent))
                want = [] if evaluated else [f"inputs.input{select}"]
                lazy.append({"wire_tuples": preserve, "select": select, "evaluated": evaluated, "got": got, "want": want,
                             "ok": got == want})
        sent = through_wire({"select": 1, "inputs": ({}, "inputs")}, preserve_tuples=preserve)
        got = outcome(lambda: asyncio.run(nodes._switch_lazy(**sent)))
        lazy.append({"wire_tuples": preserve, "select": 1, "empty_group": True, "got": got, "want": ["value", []],
                     "ok": got == ["value", []]})
    with open(out_path, "w") as handle:
        json.dump({"records": records, "wire_failures": wire_failures, "lazy": lazy,
                   "blocked_imports": sorted(finder.blocked)}, handle)


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
                                   f"/tmp/out-{side}.json"], stdout=log, stderr=subprocess.STDOUT, timeout=3000)
        if proc.returncode != 0:
            print(f"side {side} failed ({proc.returncode}); see side-{side}.log")
            return 1
        sides[side] = json.load(open(f"/tmp/out-{side}.json"))
        shutil.copyfile(f"/tmp/out-{side}.json", os.path.join(RESULTS, f"outcomes-{side}.json"))
    original, v2 = sides["original"], sides["v2"]
    mismatches = [{"case": c, "original": w, "v2": g} for c, w, g in zip(plan, original["records"], v2["records"]) if w != g]
    values = sum(1 for w in original["records"] if w[0] == "value")
    segs_items = sum(len(w[1]["segs"]["items"]) for w in original["records"] if w[0] == "value")
    lazy_ok = all(item["ok"] for item in v2["lazy"])
    unexpected = sorted(set(v2["blocked_imports"]) - {"accimage", "defusedxml"})
    probe = next((g for w, g in zip(original["records"], v2["records"]) if w[0] == "value" and w[1]["segs"]["items"]), None)
    perturbed = json.loads(json.dumps(probe))
    perturbed[1]["segs"]["items"][0]["crop_region"][0] += 1
    negative_red = perturbed != probe
    ok = not mismatches and not v2["wire_failures"] and lazy_ok and not unexpected
    parity = {"status": "PASS" if ok else "FAIL",
              "MaskToSEGS_SegsToCombinedMask": {"verdict": "EXACT" if not mismatches else "MISMATCH", "cases": len(plan),
                                                "values": values, "errors": len(plan) - values, "segs_items": segs_items,
                                                "mismatches": len(mismatches)},
              "switch_lazy": {"ok": lazy_ok, "checks": v2["lazy"]}, "wire_failures": v2["wire_failures"],
              "guest_blocked_imports": v2["blocked_imports"], "guest_blocked_imports_unexpected": unexpected,
              "negative_control": {"perturbation": "one crop_region + 1", "turned_red": negative_red}}
    with open(os.path.join(RESULTS, "parity.json"), "w") as handle:
        json.dump(parity, handle, indent=1, sort_keys=True)
        handle.write("\n")
    with open(os.path.join(RESULTS, "mismatches.json"), "w") as handle:
        json.dump(mismatches[:60], handle, indent=1)
        handle.write("\n")
    print(json.dumps({k: parity[k] for k in ("status", "MaskToSEGS_SegsToCombinedMask", "wire_failures",
                                             "guest_blocked_imports_unexpected", "negative_control")}, indent=1))
    print(json.dumps({"switch_lazy_ok": lazy_ok, "fails": [c for c in v2["lazy"] if not c["ok"]][:6]}))
    return 0 if ok and negative_red else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
