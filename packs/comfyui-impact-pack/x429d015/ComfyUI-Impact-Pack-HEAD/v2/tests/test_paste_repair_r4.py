"""Impact Pack fidelity repair r4 (SEGSPaste): parity in the lane gate.

DEPS=<the unpacked Impact dependency-profile wheels; upstream-only test needs (piexif, dill) under _orig_only/> \
run_in_gate.sh <root holding ComfyUI-Impact-Pack-HEAD/> <Impact v2/tests> <results> test_paste_repair_r4.py

SEGS come from MaskToSEGS on synthetic masks; each SEG gets a synthetic cropped image (the inverted crop of the
image, or a seeded pattern), and SEGSPaste puts them back: feather 0 / 3 / 10 / 60 (a kernel larger than a crop),
alpha 255 / 100 / 0, with and without ref_image_opt, batch 1 and 2, and SEGS made for half the image size (the
segs_scale_match path). Original: the pristine Impact Pack segs_nodes.SEGSPaste.doit under Core. v2: the repaired
handler, its output passed through the overlay's wire encoder. Outputs compare as exact tensor bytes.
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


def make_mask(kind, scale=1):
    import torch
    m = torch.zeros((80 * scale, 96 * scale))
    s = scale
    if kind == "two":
        m[5 * s:25 * s, 5 * s:30 * s] = 1.0
        m[40 * s:75 * s, 50 * s:90 * s] = 1.0
    elif kind == "edge":
        m[0:30 * s, 0:20 * s] = 1.0
        m[60 * s:80 * s, 80 * s:96 * s] = 1.0
    else:
        m[20 * s:50 * s, 30 * s:70 * s] = 1.0
    return m.unsqueeze(0)


def make_image(batch, scale=1, seed=9):
    import torch
    g = torch.Generator().manual_seed(seed)
    return torch.rand((batch, 80 * scale, 96 * scale, 3), generator=g)


def cases():
    out = []
    for mask in ("rect", "two", "edge"):
        for batch in (1, 2):
            for feather in (0, 3, 10, 60):
                for alpha in (255, 100, 0):
                    for crop_source in ("inverted", "pattern", "ref"):
                        out.append({"mask": mask, "batch": batch, "feather": feather, "alpha": alpha,
                                    "crop_source": crop_source, "scale": 1, "combined": False, "crop_factor": 1.4})
    for feather in (0, 5):
        out.append({"mask": "two", "batch": 1, "feather": feather, "alpha": 255, "crop_source": "inverted", "scale": 2,
                    "combined": True, "crop_factor": 3.0})
    return out


def crops_for(segs, image, case):
    """Synthetic 'enhanced' crops per SEG: the inverted crop of the image or a seeded pattern (None for 'ref')."""
    import torch
    out = []
    for index, item in enumerate(segs[1]):
        x1, y1, x2, y2 = (int(v) for v in item[3])
        if case["crop_source"] == "ref":
            out.append(None)
        elif case["crop_source"] == "inverted":
            out.append(1.0 - image[:, y1:y2, x1:x2, :])
        else:
            g = torch.Generator().manual_seed(100 + index)
            out.append(torch.rand((image.shape[0], y2 - y1, x2 - x1, 3), generator=g))
    return out


def digest(value):
    import numpy as np
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
            image = make_image(case["batch"], case["scale"])
            (segs,) = segs_nodes.MaskToSEGS.doit(make_mask(case["mask"]), case["combined"], case["crop_factor"], False,
                                                 1, False)
            base = make_image(case["batch"], 1) if case["scale"] != 1 else image
            crops = crops_for(segs, base, case)
            segs = (segs[0], [item._replace(cropped_image=crop) for item, crop in zip(segs[1], crops)])
            ref = image if case["crop_source"] == "ref" else None
            (result,) = segs_nodes.SEGSPaste.doit(image, segs, case["feather"], case["alpha"], ref)
            return digest(result)
        records.append(outcome(run))
    with open(out_path, "w") as handle:
        json.dump({"records": records}, handle)


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
    records, wire_failures = [], []
    for index, case in enumerate(plan):
        def run():
            image = make_image(case["batch"], case["scale"])
            (segs,) = asyncio.run(nodes._mask_to_segs_upstream(make_mask(case["mask"]), case["combined"],
                                                               case["crop_factor"], False, 1, False))
            base = make_image(case["batch"], 1) if case["scale"] != 1 else image
            crops = crops_for(segs, base, case)
            segs = (segs[0], [item._replace(cropped_image=crop) for item, crop in zip(segs[1], crops)])
            ref = image if case["crop_source"] == "ref" else None
            (result,) = asyncio.run(nodes._paste_segs(image, segs, case["feather"], case["alpha"], ref))
            wire.decode(json.loads(json.dumps(wire.encode(public_sdk.ImageRef(kind="IMAGE", id=f"t{index}")))))
            return digest(result)
        try:
            records.append(outcome(run))
        except Exception as exc:
            records.append(["error", type(exc).__name__, str(exc)])
            wire_failures.append(index)
    with open(out_path, "w") as handle:
        json.dump({"records": records, "wire_failures": wire_failures, "blocked_imports": sorted(finder.blocked)}, handle)


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
    unexpected = sorted(set(v2["blocked_imports"]) - {"accimage", "defusedxml", "envwrap"})
    probe = next(g for w, g in zip(original["records"], v2["records"]) if w[0] == "value")
    negative_red = [probe[0], [probe[1][0], "0" * 64]] != probe
    ok = not mismatches and not v2["wire_failures"] and not unexpected and values == len(plan)
    parity = {"status": "PASS" if ok else "FAIL",
              "SEGSPaste": {"verdict": "EXACT" if not mismatches else "MISMATCH", "cases": len(plan), "values": values,
                            "errors": len(plan) - values, "mismatches": len(mismatches)},
              "wire_failures": v2["wire_failures"], "guest_blocked_imports": v2["blocked_imports"],
              "guest_blocked_imports_unexpected": unexpected,
              "negative_control": {"perturbation": "one output digest replaced", "turned_red": negative_red}}
    with open(os.path.join(RESULTS, "parity.json"), "w") as handle:
        json.dump(parity, handle, indent=1, sort_keys=True)
        handle.write("\n")
    with open(os.path.join(RESULTS, "mismatches.json"), "w") as handle:
        json.dump(mismatches[:60], handle, indent=1)
        handle.write("\n")
    print(json.dumps(parity, indent=1))
    return 0 if ok and negative_red else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
