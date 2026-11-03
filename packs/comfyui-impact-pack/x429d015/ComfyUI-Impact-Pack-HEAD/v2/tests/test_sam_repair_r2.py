"""Impact Pack fidelity repair r2 (SAM in the guest): parity in the lane gate.

DEPS=<the unpacked Impact dependency-profile wheels; upstream-only test needs (piexif, dill) under _orig_only/> \
run_in_gate.sh <root holding ComfyUI-Impact-Pack-HEAD/> <Impact v2/tests> <results> test_sam_repair_r2.py [generate-manifests]

Fixtures are synthetic: a segment-anything vit_b with seeded random weights, stored as fp32 safetensors, synthetic
images and synthetic SEGS (float32 Ultralytics-style boxes and integer boxes). No upstream media or model.

  original  the pristine Impact Pack modules (impact.core, impact.impact_pack, impact.utils) under Core: SAMLoader,
            make_sam_mask, make_sam_mask_segmented and segs_bitwise_and_mask as upstream runs them. The one boundary:
            segment_anything's build_sam reads its checkpoint with torch.load (a pickle), so SAMLoader's
            sam_model_registry builds the model with checkpoint=None and loads the fixture's tensors.
  v2        Impact v2's SAM handlers with a fake SDK context (assets.resolve / load_state_dict / size / exists; a .pth
            name reads the converted safetensors, as the engine translation does). Imports outside the standard
            library, the sealed guest base, /deps and the pack are blocked, as in a guest.
Every v2 output also crosses the overlay's wire encoder (transport/wire.py) with tensors replaced by refs.
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
FX = "/tmp/fx"
SAM_FILE = os.path.join(FX, "models", "fx_sam.safetensors")
SAMS = {"fx_sam.safetensors": SAM_FILE, "fx_sam.pth": SAM_FILE}  # catalogue name -> tensors (engine translation)
HINTS = ["center-1", "horizontal-2", "vertical-2", "rect-4", "diamond-4", "mask-area", "mask-points",
         "mask-point-bbox", "none"]


def write_fixtures():
    import torch
    from safetensors.torch import save_file
    from segment_anything import sam_model_registry
    os.makedirs(os.path.dirname(SAM_FILE), exist_ok=True)
    torch.manual_seed(7)
    model = sam_model_registry["vit_b"](checkpoint=None)
    save_file({k: v.contiguous() for k, v in model.state_dict().items()}, SAM_FILE)


def seg_specs(kind):
    # (crop_region, bbox, mask rectangle inside the crop, confidence, label)
    if kind == "float":
        return [([10, 8, 70, 60], [22.75, 17.5, 58.25, 49.125], (12, 9, 48, 41), 0.8125, "face"),
                ([80, 30, 150, 110], [95.5, 41.25, 133.375, 97.0], (15, 11, 53, 67), 0.625, "face")]
    if kind == "int":
        return [([5, 5, 60, 55], [15, 12, 48, 44], (10, 7, 43, 39), 1.0, "A"),
                ([70, 40, 140, 112], [84, 52, 128, 101], (14, 12, 58, 61), 1.0, "B")]
    return [([20, 20, 40, 44], [24.5, 26.0, 31.5, 38.25], (4, 6, 12, 18), 0.5, "tiny")]  # bbox narrower than 10


def make_segs(kind, v2):
    import numpy as np
    import torch
    items = []
    for crop, bbox, (x0, y0, x1, y1), confidence, label in seg_specs(kind):
        mask = np.zeros((crop[3] - crop[1], crop[2] - crop[0]), dtype=np.float32)
        mask[y0:y1, x0:x1] = 1.0
        if v2:
            items.append((None, torch.from_numpy(mask).unsqueeze(0), float(confidence), list(crop),
                          tuple(float(v) for v in bbox) if kind != "int" else tuple(bbox), label, None))
        else:
            items.append((None, mask, np.array([confidence], dtype=np.float32), list(crop),
                          np.array(bbox, dtype=np.float32) if kind != "int" else list(bbox), label, None))
    return (120, 160), items


def make_image(seed):
    import torch
    g = torch.Generator().manual_seed(seed)
    return torch.rand((1, 120, 160, 3), generator=g)


def make_full_mask(kind):
    import torch
    mask = torch.zeros((1, 120, 160))
    if kind == "binary":
        mask[:, 20:90, 15:120] = 1.0
    else:
        mask[:, 10:100, 30:150] = 0.6
    return mask


def cases():
    out = [{"node": "loader", "model_name": n, "device_mode": "AUTO"} for n in ("fx_sam.safetensors", "fx_sam.pth")]
    out.append({"node": "loader", "model_name": "fx_sam.safetensors", "device_mode": "CPU"})
    for name in ("missing.pth", "ESAM", "sam2_hiera_tiny.pt", "sam_hq_vit_b.pth", "fx_sam.bin"):
        out.append({"node": "loader", "model_name": name, "device_mode": "AUTO", "designed": "refused"})
    base = {"segs": "float", "dilation": 0, "threshold": 0.93, "bbox_expansion": 0, "mask_hint_threshold": 0.7}
    for hint in HINTS:
        for negative in ("False", "Small", "Outter"):
            out.append({"node": "combined", **base, "detection_hint": hint, "mask_hint_use_negative": negative})
    for segs, dilation, threshold, expansion, hint_threshold in (("float", 3, 0.93, 0, 0.7), ("float", -2, 0.5, 10, 0.7),
                                                                  ("float", 0, 0.0, 5, 0.2), ("int", 0, 0.93, 0, 0.7),
                                                                  ("int", 4, 0.5, 8, 0.4), ("small", 0, 0.93, 0, 0.7)):
        for hint, negative in (("center-1", "False"), ("mask-points", "Small"), ("mask-area", "Small")):
            out.append({"node": "combined", "segs": segs, "dilation": dilation, "threshold": threshold,
                        "bbox_expansion": expansion, "mask_hint_threshold": hint_threshold, "detection_hint": hint,
                        "mask_hint_use_negative": negative})
    for hint in ("center-1", "mask-area", "mask-points", "rect-4", "none"):
        out.append({"node": "segmented", **base, "detection_hint": hint, "mask_hint_use_negative": "False"})
    for segs in ("float", "int", "small"):
        for full in ("binary", "soft"):
            out.append({"node": "and_mask", "segs": segs, "mask": full})
    return out


def digest(value):
    import numpy as np
    if value is None:
        return None
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    value = np.ascontiguousarray(np.asarray(value))
    return [list(value.shape), str(value.dtype), hashlib.sha256(value.tobytes()).hexdigest()]


def mask_record(value):
    import numpy as np
    import torch
    mask = torch.as_tensor(value)
    while mask.ndim > 3 and mask.shape[1] == 1:
        mask = mask.squeeze(1)
    if mask.ndim == 2:
        mask = mask.unsqueeze(0)
    return digest(mask.float().numpy().astype(np.float32))


def segs_record(segs):
    import numpy as np
    import torch
    shape, items = segs
    rows = []
    for item in items:
        mask = item[1]
        mask = mask.detach().cpu().numpy() if isinstance(mask, torch.Tensor) else np.asarray(mask)
        if mask.ndim == 3 and mask.shape[0] == 1:
            mask = mask[0]
        rows.append({"mask": digest(mask.astype(np.float32)), "confidence": float(np.asarray(item[2]).reshape(-1)[0]),
                     "crop_region": [int(v) for v in item[3]], "bbox": [float(v) for v in item[4]], "label": item[5],
                     "control_net_wrapper": item[6]})
    return {"shape": [int(v) for v in shape], "items": rows}


def outcome(fn):
    try:
        return ["value", fn()]
    except Exception as exc:
        return ["error", type(exc).__name__, str(exc)]


# ---------------------------------------------------------------- original side
def run_original(plan, out_path):
    # Upstream Impact's own requirements that the guest profile does not carry (piexif for impact_pack.py's EXIF
    # saving): on the original side only, never visible to the v2 side.
    sys.path.insert(0, os.path.join(DEPS, "_orig_only"))
    import comfy.cli_args
    comfy.cli_args.args.cpu = True
    import folder_paths
    import torch
    from safetensors.torch import load_file
    from segment_anything import sam_model_registry as real_registry

    root = "/tmp/orig-impact"
    shutil.copytree(IMPACT, root, ignore=shutil.ignore_patterns("v2", "__pycache__", ".git"))
    sys.path.insert(0, os.path.join(root, "modules"))
    sams_dir = os.path.join(FX, "orig", "sams")
    os.makedirs(sams_dir, exist_ok=True)
    for name in ("fx_sam.safetensors", "fx_sam.pth"):
        open(os.path.join(sams_dir, name), "wb").close()
    folder_paths.folder_names_and_paths["sams"] = ([sams_dir], set(folder_paths.supported_pt_extensions))
    import server

    class Routes:  # a no-op PromptServer instance: upstream modules register routes at import
        def __getattr__(self, _name):
            return lambda *_args, **_kwargs: lambda function: function

    class Instance:
        routes = Routes()
        prompt_queue = types.SimpleNamespace(currently_running={})

        def __getattr__(self, _name):
            return lambda *_args, **_kwargs: None

    server.PromptServer.instance = Instance()
    # Upstream __init__.py's order: impact.config, then impact.impact_server (which pulls in impact_pack and resolves
    # the impact_pack <-> impact_server cycle), then the node modules.
    import impact.config  # noqa: F401
    import impact.impact_server  # noqa: F401
    import impact.core as core
    import impact.impact_pack as impact_pack

    def build(kind):
        def builder(checkpoint=None):
            # The boundary: build_sam(checkpoint=path) would torch.load the file; this loads the fixture's tensors.
            model = real_registry[kind](checkpoint=None)
            if checkpoint is not None:
                model.load_state_dict(load_file(SAM_FILE))
            return model
        return builder
    impact_pack.sam_model_registry = {kind: build(kind) for kind in ("vit_b", "vit_l", "vit_h", "default")}
    loader = impact_pack.SAMLoader()
    sams = {}
    records = []
    for case in plan:
        if case.get("designed"):
            records.append(["skipped", "designed refusal: only v2's named error is checked"])
            continue

        def run():
            if case["node"] == "loader":
                (sam,) = loader.load_model(case["model_name"], case["device_mode"])
                sams[(case["model_name"], case["device_mode"])] = sam
                return type(sam.sam_wrapper).__name__
            if case["node"] == "and_mask":
                segs = make_segs(case["segs"], False)
                segs = (segs[0], [core.SEG(*item) for item in segs[1]])
                return segs_record(core.segs_bitwise_and_mask(segs, make_full_mask(case["mask"])))
            sam = sams.get(("fx_sam.safetensors", "AUTO")) or loader.load_model("fx_sam.safetensors", "AUTO")[0]
            sams[("fx_sam.safetensors", "AUTO")] = sam
            segs = make_segs(case["segs"], False)
            segs = (segs[0], [core.SEG(*item) for item in segs[1]])
            args = (sam, segs, make_image(5), case["detection_hint"], case["dilation"], case["threshold"],
                    case["bbox_expansion"], case["mask_hint_threshold"], case["mask_hint_use_negative"])
            if case["node"] == "segmented":
                combined, batch = core.make_sam_mask_segmented(*args)
                return [mask_record(combined), None if batch is None else mask_record(batch)]
            return mask_record(core.make_sam_mask(*args))
        records.append(outcome(run))
    model = sams[("fx_sam.safetensors", "AUTO")]
    with open(out_path, "w") as handle:
        json.dump({"records": records, "model": digest_state(model)}, handle)


def digest_state(model):
    import numpy as np
    h = hashlib.sha256()
    state = model.state_dict()
    for key in sorted(state):
        h.update(key.encode())
        h.update(np.ascontiguousarray(state[key].detach().cpu().float().numpy()).tobytes())
    return [h.hexdigest(), len(state), bool(model.training)]


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
    from safetensors.torch import load_file
    spec = importlib.util.spec_from_file_location("impact_v2", os.path.join(IMPACT, "v2", "__init__.py"),
                                                  submodule_search_locations=[os.path.join(IMPACT, "v2")])
    package = importlib.util.module_from_spec(spec)
    sys.modules["impact_v2"] = package
    spec.loader.exec_module(package)
    nodes = sys.modules["impact_v2._secure_nodes"]

    class Assets:
        async def resolve(self, folder, name):
            if folder != "sams" or name not in SAMS:
                raise FileNotFoundError(f"no {folder} asset named {name!r}")
            return ("asset", name)

        async def load_state_dict(self, ref, return_metadata=False):
            state = load_file(SAMS[ref[1]])  # a .pth name reads its converted safetensors (engine translation)
            return (state, None) if return_metadata else state

        async def size(self, ref):
            return os.path.getsize(SAMS[ref[1]])

    context = types.SimpleNamespace(assets=Assets())
    nodes.sdk = types.SimpleNamespace(ctx=lambda: context, SamModelRef=type("NoSamModelRef", (), {}),
                                      ImageRef=type("NoImageRef", (), {}))
    from comfy_api.latest import sdk as public_sdk
    wire_spec = importlib.util.spec_from_file_location("overlay_wire", "/overlay/comfy_secure_nodes/transport/wire.py")
    wire = importlib.util.module_from_spec(wire_spec)
    wire_spec.loader.exec_module(wire)
    counter = [0]

    def ref(cls, kind):
        counter[0] += 1
        return cls(kind=kind, id=f"t{counter[0]}")

    def through_wire(value):
        if isinstance(value, tuple) and len(value) == 2 and isinstance(value[1], list):
            value = (tuple(value[0]), [tuple([None if item[0] is None else ref(public_sdk.ImageRef, "IMAGE"),
                                              ref(public_sdk.MaskRef, "MASK"), *item[2:]]) for item in value[1]])
        elif isinstance(value, torch.Tensor):
            value = ref(public_sdk.MaskRef, "MASK")
        return wire.decode(json.loads(json.dumps(wire.encode(value))))

    descriptors, records, wire_failures = {}, [], []
    for index, case in enumerate(plan):
        def run():
            if case["node"] == "loader":
                (descriptor,) = asyncio.run(nodes._sam_loader(case["model_name"], case["device_mode"]))
                through_wire(descriptor)
                descriptors[(case["model_name"], case["device_mode"])] = descriptor
                return "SAMWrapper"
            if case["node"] == "and_mask":
                (segs,) = asyncio.run(nodes._segs_apply_mask(make_segs(case["segs"], True), mask=make_full_mask(case["mask"])))
                through_wire(segs)
                return segs_record(segs)
            descriptor = descriptors.get(("fx_sam.safetensors", "AUTO"))
            if descriptor is None:
                (descriptor,) = asyncio.run(nodes._sam_loader("fx_sam.safetensors", "AUTO"))
                descriptors[("fx_sam.safetensors", "AUTO")] = descriptor
            kwargs = dict(sam_model=descriptor, segs=make_segs(case["segs"], True), image=make_image(5),
                          detection_hint=case["detection_hint"], dilation=case["dilation"], threshold=case["threshold"],
                          bbox_expansion=case["bbox_expansion"], mask_hint_threshold=case["mask_hint_threshold"],
                          mask_hint_use_negative=case["mask_hint_use_negative"])
            if case["node"] == "segmented":
                combined, batch = asyncio.run(nodes._sam_detector_segmented(**kwargs))
                through_wire(combined)
                if batch is not None:
                    through_wire(batch)
                return [mask_record(combined), None if batch is None else mask_record(batch)]
            (combined,) = asyncio.run(nodes._sam_detector_combined(**kwargs))
            through_wire(combined)
            return mask_record(combined)
        try:
            records.append(outcome(run))
        except Exception as exc:
            records.append(["error", type(exc).__name__, str(exc)])
            wire_failures.append(index)
    runtime = sys.modules["impact_v2._sam_runtime"]
    model = runtime._SAMS[("fx_sam.safetensors", "AUTO")]
    with open(out_path, "w") as handle:
        json.dump({"records": records, "model": digest_state(model), "wire_failures": wire_failures,
                   "blocked_imports": sorted(finder.blocked)}, handle)


# ---------------------------------------------------------------- manifest rows (real encoder)
def manifests():
    import copy
    sys.path.insert(0, "/overlay")
    import comfy.cli_args
    comfy.cli_args.args.cpu = True
    from comfy_secure_nodes.packmanifest import encode_schema, encode_validation_inputs
    spec = importlib.util.spec_from_file_location("impact_v2", os.path.join(IMPACT, "v2", "__init__.py"),
                                                  submodule_search_locations=[os.path.join(IMPACT, "v2")])
    package = importlib.util.module_from_spec(spec)
    sys.modules["impact_v2"] = package
    spec.loader.exec_module(package)
    rows = {}
    for node_id in ("SAMLoader", "SAMDetectorCombined", "SAMDetectorSegmented"):
        cls = package.NODE_CLASS_MAPPINGS[node_id]
        row = {"class": cls.__name__,
               "methods": {n: n in cls.__dict__ for n in ("check_lazy_status", "fingerprint_inputs", "validate_inputs")},
               "module": cls.__module__.removeprefix("impact_v2."), "permissions": list(cls.SDK_PERMISSIONS),
               "schema": encode_schema(copy.deepcopy(cls.GET_SCHEMA())), "sdk_refs": cls.SDK_REFS is True}
        if "validate_inputs" in cls.__dict__:
            row["validation_inputs"] = encode_validation_inputs(cls)
        rows[node_id] = row
    return rows


def main(argv):
    if argv[:1] == ["side"]:
        plan = json.load(open(argv[2]))
        return (run_original if argv[1] == "original" else run_v2)(plan, argv[3]) or 0
    if argv[:1] == ["generate-manifests"]:
        with open(os.path.join(RESULTS, "impact-sam-rows.json"), "w", newline="\n") as handle:
            json.dump(manifests(), handle, indent=1)
            handle.write("\n")
        print("wrote rows")
        return 0
    write_fixtures()
    plan = cases()
    with open("/tmp/plan.json", "w") as handle:
        json.dump(plan, handle)
    sides = {}
    for side in ("original", "v2"):
        with open(os.path.join(RESULTS, f"side-{side}.log"), "w") as log:
            proc = subprocess.run([sys.executable, "-I", "-B", os.path.abspath(__file__), "side", side, "/tmp/plan.json",
                                   f"/tmp/out-{side}.json"], stdout=log, stderr=subprocess.STDOUT, timeout=5400)
        if proc.returncode != 0:
            print(f"side {side} failed ({proc.returncode}); see side-{side}.log")
            return 1
        sides[side] = json.load(open(f"/tmp/out-{side}.json"))
        shutil.copyfile(f"/tmp/out-{side}.json", os.path.join(RESULTS, f"outcomes-{side}.json"))
    original, v2 = sides["original"], sides["v2"]
    by_node, mismatches, designed = {}, [], []
    for case, want, got in zip(plan, original["records"], v2["records"]):
        if case.get("designed") == "refused":
            designed.append({"model_name": case["model_name"], "original": want, "v2": got,
                             "ok": got[0] == "error" and got[1] == "SamWeightError"})
            continue
        r = by_node.setdefault(case["node"], {"cases": 0, "mismatches": 0, "values": 0, "errors": 0})
        r["cases"] += 1
        r["values" if want[0] == "value" else "errors"] += 1
        if want != got:
            r["mismatches"] += 1
            mismatches.append({"case": case, "original": want, "v2": got})
    known_optional = {"accimage", "defusedxml", "envwrap"}  # optional imports their importers catch (torchvision, tqdm)
    unexpected = sorted(set(v2["blocked_imports"]) - known_optional)
    probe = next((g for w, g in zip(original["records"], v2["records"]) if w[0] == "value" and isinstance(w[1], list)
                  and len(w[1]) == 3), None)
    negative_red = probe is not None and json.loads(json.dumps(probe)) != [probe[1][0], probe[1][1], "0" * 64]
    ok = (not mismatches and original["model"] == v2["model"] and not v2["wire_failures"] and not unexpected
          and all(d["ok"] for d in designed) and all(r["cases"] for r in by_node.values()))
    parity = {"status": "PASS" if ok else "FAIL",
              "nodes": {k: {"verdict": "EXACT" if not v["mismatches"] else "MISMATCH", **v} for k, v in by_node.items()},
              "designed_refusals": designed, "rebuilt_sam_equals_checkpoint_model": original["model"] == v2["model"],
              "models": {"original": original["model"], "v2": v2["model"]}, "wire_failures": v2["wire_failures"],
              "guest_blocked_imports": v2["blocked_imports"], "guest_blocked_imports_unexpected": unexpected,
              "negative_control": {"perturbation": "one mask digest replaced", "turned_red": negative_red}}
    with open(os.path.join(RESULTS, "parity.json"), "w") as handle:
        json.dump(parity, handle, indent=1, sort_keys=True)
        handle.write("\n")
    with open(os.path.join(RESULTS, "mismatches.json"), "w") as handle:
        json.dump(mismatches[:60], handle, indent=1)
        handle.write("\n")
    print(json.dumps({k: parity[k] for k in ("status", "nodes", "rebuilt_sam_equals_checkpoint_model", "wire_failures",
                                             "guest_blocked_imports_unexpected", "negative_control")}, indent=1))
    print(json.dumps([[d["model_name"], d["ok"], d["v2"][:2]] for d in designed]))
    return 0 if ok and negative_red else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
