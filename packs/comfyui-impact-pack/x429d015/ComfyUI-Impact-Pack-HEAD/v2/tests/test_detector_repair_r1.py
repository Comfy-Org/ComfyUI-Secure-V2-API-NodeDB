"""Impact Pack + Impact Subpack, fidelity repair r1 (Ultralytics detectors): parity in the lane gate.

DEPS=<the unpacked Impact dependency-profile wheels, plus dill for the original Subpack import> \
run_in_gate.sh <root holding ComfyUI-Impact-Pack-HEAD/ and ComfyUI-Impact-Subpack-HEAD/> <Impact v2/tests> <results> \
    test_detector_repair_r1.py [generate-manifests]

Fixtures are synthetic: Ultralytics models built from Ultralytics' packaged yolov8n / yolov8n-seg yaml with a
fixed seed (class biases raised so detections occur), stored as fp16 safetensors with the metadata a converted
checkpoint carries (top_class, yaml, names, train_args), and synthetic images. No upstream media or model.

  original  the pristine Impact Subpack modules (subcore, subpack_nodes) under Core, with upstream Impact Pack's
            BboxDetectorForEach / SegmDetectorForEach / *Combined logic. The one boundary: subcore.load_yolo (a
            pickle load) returns the in-memory model, built from the packaged yaml and the fp16 weights and set up
            the way ultralytics' load_checkpoint and Model._load set up a loaded checkpoint.
  v2        Impact Subpack v2's provider and Impact v2's detector handlers, with a fake SDK context. Its assets
            domain lists the same catalogues, and load_state_dict returns the converted safetensors (tensors +
            metadata) for a .pt name, as the engine's translation does. Imports outside the standard library, the
            sealed guest base, /deps and the packs are blocked, as in a guest.
Every v2 output also goes through the overlay's wire encoder (transport/wire.py), with tensors replaced by refs as
Impact v2's SEGS wrap does, then JSON and decode.
Compared: SEGS (shape, and per SEG: cropped image and mask bytes, confidence, crop region, bbox, label), combined
masks, provider outputs and errors, and the rebuilt model against the in-memory one (every tensor, args, names,
stride, task).
"""
import asyncio
import glob
import hashlib
import importlib.abc
import importlib.machinery
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
SUBPACK = os.path.join(ROOT, "ComfyUI-Impact-Subpack-HEAD")
RESULTS = "/results"
DEPS = "/deps"
BASE = glob.glob("/bases/0cd9adec*/common-site-packages")[0]
for _index, _path in enumerate((DEPS, BASE, "/core", "/overlay")):
    sys.path.insert(_index, _path)
os.environ.update({"HOME": "/tmp", "YOLO_AUTOINSTALL": "False", "YOLO_OFFLINE": "True", "YOLO_CONFIG_DIR": "/tmp/yolo",
                   "YOLO_VERBOSE": "False"})
FX = "/tmp/fx"
MODELS = {  # fixture model -> (packaged yaml, nc, names, seed, train_args)
    "face_hand": ("yolov8n.yaml", 2, {"0": "face", "1": "hand"}, 1234, {"imgsz": 640, "task": "detect", "data": "fx.yaml", "single_cls": False}),
    "small": ("yolov8n.yaml", 1, {"0": "face"}, 99, {"imgsz": 320, "task": "detect", "data": "fx.yaml", "single_cls": False}),
    "person_seg": ("yolov8n-seg.yaml", 1, {"0": "person"}, 4321, {"imgsz": 640, "task": "segment", "data": "fx.yaml", "single_cls": False}),
}
CATALOGUES = {  # catalogue -> {menu file name: fixture model}
    "ultralytics_bbox": {"face_hand.pt": "face_hand", "face_hand.safetensors": "face_hand", "small.pt": "small"},
    "ultralytics_segm": {"person_seg.pt": "person_seg"},
    "ultralytics": {"bbox/rooted.pt": "face_hand"},
}


def build_model(fixture):
    import torch
    from ultralytics.nn.tasks import DetectionModel, SegmentationModel, yaml_model_load
    yaml_name, nc, _names, seed, _args = MODELS[fixture]
    cfg = yaml_model_load(yaml_name)
    cfg["nc"] = nc
    torch.manual_seed(seed)
    model = (SegmentationModel if "seg" in yaml_name else DetectionModel)(cfg, verbose=False)
    with torch.no_grad():
        for branch in model.model[-1].cv3:
            branch[-1].bias += 6.0  # raise class logits so a random model detects at ordinary thresholds
    return model


def write_fixtures():
    import torch
    from safetensors.torch import save_file
    os.makedirs(os.path.join(FX, "models"), exist_ok=True)
    for fixture, (yaml_name, _nc, names, _seed, args) in MODELS.items():
        model = build_model(fixture)
        state = {k: (v.half() if v.is_floating_point() else v).contiguous() for k, v in model.state_dict().items()}
        top = "SegmentationModel" if "seg" in yaml_name else "DetectionModel"
        save_file(state, os.path.join(FX, "models", f"{fixture}.safetensors"), metadata={
            "top_class": f"ultralytics.nn.tasks.{top}", "yaml": json.dumps(model.yaml), "names": json.dumps(names),
            "train_args": json.dumps(args), "converter": "synthetic-fixture"})


def cases():
    out = []
    images = [(11, 96, 128), (12, 160, 120), (13, 257, 333)]
    for model_name in ("bbox/face_hand.pt", "bbox/face_hand.safetensors", "bbox/small.pt", "bbox/rooted.pt",
                       "segm/person_seg.pt", "bbox/missing.pt", "segm/missing.pt", "missing.pt"):
        out.append({"node": "provider", "model_name": model_name})
    # Designed difference: the V2 menu lists the ultralytics_bbox catalogue's bare names (a host menu cannot add
    # upstream's "bbox/" prefix), so v2 resolves a bare name as a bbox model; upstream has no bare names.
    out.append({"node": "provider", "model_name": "face_hand.pt", "designed": "bare-name"})
    for model_name, nodes in (("bbox/face_hand.pt", ("bbox_segs", "bbox_combined")),
                              ("bbox/small.pt", ("bbox_segs", "bbox_combined")),
                              ("segm/person_seg.pt", ("bbox_segs", "segm_segs", "segm_combined"))):
        for node in nodes:
            for image in images:
                for threshold in (0.1, 0.3, 0.5):
                    for dilation in (0, 4, -3):
                        base = {"node": node, "model_name": model_name, "image": image, "threshold": threshold,
                                "dilation": dilation}
                        if node.endswith("combined"):
                            out.append(base)
                            continue
                        for crop_factor, drop_size, labels in ((3.0, 10, "all"), (1.0, 1, "face"), (1.5, 30, "hand,face"),
                                                               (2.0, 5, ""), (3.0, 10, "person"), (1.2, 10, "eyes")):
                            out.append({**base, "crop_factor": crop_factor, "drop_size": drop_size, "labels": labels})
    return out


def make_image(spec):
    import torch
    seed, height, width = spec
    g = torch.Generator().manual_seed(seed)
    base = torch.rand((1, height, width, 3), generator=g)
    ramp = torch.linspace(0, 1, width).view(1, 1, width, 1)
    return (0.6 * base + 0.4 * ramp).clamp(0, 1).float()


def digest(array):
    import numpy as np
    value = np.ascontiguousarray(np.asarray(array, dtype=np.float32))
    return [list(value.shape), hashlib.sha256(value.tobytes()).hexdigest()]


def seg_record(shape, items, v2):
    import numpy as np
    rows = []
    for item in items:
        mask = item.cropped_mask.squeeze(0).numpy() if v2 else item.cropped_mask
        image = item.cropped_image.numpy() if item.cropped_image is not None else None
        rows.append({"cropped_image": None if image is None else digest(image), "cropped_mask": digest(mask),
                     "confidence": float(np.asarray(item.confidence, dtype=np.float32).reshape(-1)[0]),
                     "crop_region": [int(v) for v in item.crop_region], "bbox": [float(v) for v in item.bbox],
                     "label": str(item.label)})
    return {"shape": [int(shape[0]), int(shape[1])], "items": rows}


def outcome(fn):
    try:
        return ["value", fn()]
    except Exception as exc:
        return ["error", type(exc).__name__, str(exc)]


def model_record(model):
    import numpy as np
    state = model.state_dict()
    tensors = hashlib.sha256()
    for key in sorted(state):
        tensors.update(key.encode())
        tensors.update(np.ascontiguousarray(state[key].detach().cpu().float().numpy()).tobytes())
    args = getattr(model, "args", {})
    return {"tensors": tensors.hexdigest(), "keys": len(state), "names": {str(k): v for k, v in model.names.items()},
            "stride": [float(s) for s in model.stride], "task": model.task,
            "args": {k: args.get(k) for k in ("imgsz", "task", "data", "single_cls", "conf", "iou", "max_det")}}


# ---------------------------------------------------------------- original side
def run_original(plan, out_path):
    import comfy.cli_args
    comfy.cli_args.args.cpu = True
    import folder_paths
    import torch
    from ultralytics import YOLO
    from ultralytics.cfg import DEFAULT_CFG_DICT
    from ultralytics.engine.model import Model
    from ultralytics.nn import tasks

    for catalogue, files in CATALOGUES.items():
        root = os.path.join(FX, "orig", catalogue)
        for name in files:
            os.makedirs(os.path.dirname(os.path.join(root, name)), exist_ok=True)
            open(os.path.join(root, name), "wb").close()  # upstream only needs the path to exist
        folder_paths.folder_names_and_paths[catalogue] = ([root], set(folder_paths.supported_pt_extensions))
    root = "/tmp/orig-subpack"
    shutil.copytree(SUBPACK, root, ignore=shutil.ignore_patterns("v2", "__pycache__"))
    # modules/ has no __init__.py upstream: load it as a package directory so its relative imports resolve.
    spec = importlib.machinery.ModuleSpec("impact_subpack_original", None, is_package=True)
    package = importlib.util.module_from_spec(spec)
    package.__path__ = [os.path.join(root, "modules")]
    sys.modules[spec.name] = package
    from safetensors.torch import load_file
    loaded = {}

    def checkpoint_model(path):
        # The boundary: the file's model, as ultralytics' YOLO(path) would hold it, without unpickling a file.
        fixture = None
        for catalogue, files in CATALOGUES.items():
            for name, value in files.items():
                if os.path.realpath(path) == os.path.realpath(os.path.join(FX, "orig", catalogue, name)):
                    fixture = value
        if fixture not in loaded:
            yaml_name, _nc, names, _seed, train_args = MODELS[fixture]
            model = build_model(fixture)
            model.load_state_dict(load_file(os.path.join(FX, "models", f"{fixture}.safetensors")), strict=True)
            model = model.float()  # load_checkpoint: candidate.float()
            model.args = {**DEFAULT_CFG_DICT, **train_args}
            model.pt_path = str(path)
            model.task = getattr(model, "task", tasks.guess_model_task(model))
            model.names = {int(k): v for k, v in names.items()}
            model = model.eval()
            for m in model.modules():
                if hasattr(m, "inplace"):
                    m.inplace = True
            yolo = YOLO(yaml_name)
            yolo.model, yolo.ckpt, yolo.cfg = model, {}, None
            yolo.task = model.task
            yolo.overrides = model.args = Model._reset_ckpt_args(model.args)
            yolo.ckpt_path = model.pt_path
            yolo.overrides["model"] = str(path)
            yolo.overrides["task"] = yolo.task
            yolo.model_name = str(path)
            loaded[fixture] = yolo
        return loaded[fixture]

    subcore = importlib.import_module("impact_subpack_original.subcore")
    subcore.load_yolo = checkpoint_model
    nodes = importlib.import_module("impact_subpack_original.subpack_nodes")
    provider = nodes.UltralyticsDetectorProvider()
    records, models = [], {}
    for case in plan:
        def run():
            if case["node"] == "provider":
                bbox, segm = provider.doit(case["model_name"])
                return [type(bbox).__name__, type(segm).__name__]
            bbox, segm = provider.doit(case["model_name"])
            detector = segm if case["node"].startswith("segm") else bbox
            image = make_image(case["image"])
            if case["node"].endswith("combined"):
                # Impact Pack detectors.py BboxDetectorCombined / SegmDetectorCombined.doit
                mask = detector.detect_combined(image, case["threshold"], case["dilation"])
                if mask is None:
                    mask = torch.zeros((image.shape[1], image.shape[2]), dtype=torch.float32, device="cpu")
                return digest(mask.unsqueeze(0).numpy())
            # Impact Pack detectors.py BboxDetectorForEach / SegmDetectorForEach.doit (no detailer hook)
            segs = detector.detect(image, case["threshold"], case["dilation"], case["crop_factor"], case["drop_size"], None)
            labels = case["labels"]
            if labels is not None and labels != '':
                labels = labels.split(',')
                if len(labels) > 0:
                    segs, _ = label_filter(segs, labels)
            return seg_record(segs[0], segs[1], False)
        records.append(outcome(run))
    for fixture in MODELS:
        models[fixture] = model_record(loaded[fixture].model) if fixture in loaded else None
    with open(out_path, "w") as handle:
        json.dump({"records": records, "models": models}, handle)


def label_filter(segs, labels):
    # Impact Pack modules/impact/segs_nodes.py SEGSLabelFilter.filter, loaded from the pristine file.
    source = open(os.path.join(IMPACT, "modules", "impact", "segs_nodes.py"), encoding="utf-8").read()
    import ast
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "SEGSLabelFilter")
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "filter")
    lines = source.splitlines(keepends=True)[fn.lineno - 1:fn.end_lineno]
    import textwrap
    namespace = {}
    exec(compile(textwrap.dedent("".join(lines)), "segs_nodes.py:SEGSLabelFilter.filter", "exec"), namespace)
    return namespace["filter"](segs, labels)


# ---------------------------------------------------------------- v2 side
GUEST_BASE = {"av", "blake3", "comfy_api", "comfy_secure_nodes", "comfy_secure_sdk", "filelock", "fsspec", "iniconfig",
              "jinja2", "markupsafe", "mpmath", "networkx", "numpy", "nvidia", "packaging", "PIL", "pluggy", "psutil",
              "pygments", "pytest", "_pytest", "py", "pytest_asyncio", "safetensors", "setuptools", "pkg_resources",
              "_distutils_hack", "sympy", "torch", "functorch", "torchgen", "triton", "typing_extensions", "wheel"}


class GuestImports(importlib.abc.MetaPathFinder):
    """Blocks top-level imports a guest would not have (outside stdlib, guest base, /deps and the packs)."""

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
            return None  # the harness itself (Core, overlay) is not guest code
        self.blocked.add(fullname)
        raise ModuleNotFoundError(f"blocked in guest emulation: {fullname}", name=fullname)


def run_v2(plan, out_path):
    import torch
    deps_top = {n[:-3] if n.endswith(".py") else n for n in os.listdir(DEPS) if not n.endswith((".dist-info", ".data", ".libs"))}
    finder = GuestImports(GUEST_BASE | deps_top | {"impact_v2", "subpack_v2"})
    sys.meta_path.insert(0, finder)
    from safetensors import safe_open
    from safetensors.torch import load_file

    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, os.path.join(path, "__init__.py"), submodule_search_locations=[path])
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    subpack = load("subpack_v2", os.path.join(SUBPACK, "v2"))
    impact = load("impact_v2", os.path.join(IMPACT, "v2"))
    provider_mod = sys.modules["subpack_v2._secure_nodes"]
    nodes = sys.modules["impact_v2._secure_nodes"]

    class Assets:
        async def exists(self, folder, name):
            if folder not in CATALOGUES:
                raise KeyError(folder)  # an unregistered catalogue, as folder_paths raises
            return name in CATALOGUES[folder]

        async def resolve(self, folder, name):
            if not await self.exists(folder, name):
                raise FileNotFoundError(f"no {folder} asset named {name!r}")
            return ("asset", folder, name)

        async def load_state_dict(self, ref, return_metadata=False):
            # The engine translation: a known pickle-format name reads its converted safetensors file.
            fixture = CATALOGUES[ref[1]][ref[2]]
            path = os.path.join(FX, "models", f"{fixture}.safetensors")
            state = load_file(path)
            if not return_metadata:
                return state
            with safe_open(path, framework="pt") as handle:
                return state, handle.metadata()

    context = types.SimpleNamespace(assets=Assets())
    fake = types.SimpleNamespace(ctx=lambda: context)
    provider_mod.sdk = fake
    nodes.sdk = fake
    from comfy_api.latest import sdk as public_sdk
    wire_spec = importlib.util.spec_from_file_location("overlay_wire", "/overlay/comfy_secure_nodes/transport/wire.py")
    wire = importlib.util.module_from_spec(wire_spec)
    wire_spec.loader.exec_module(wire)
    counter = [0]

    def ref(cls, kind):
        counter[0] += 1
        return cls(kind=kind, id=f"t{counter[0]}")

    def through_wire(value):
        """Impact v2's SEGS wrap (cropped image/mask -> refs), then the wire encoder, JSON and decode."""
        if isinstance(value, tuple) and len(value) == 2 and isinstance(value[1], list):
            value = (tuple(value[0]), [tuple([ref(public_sdk.ImageRef, "IMAGE") if item[0] is not None else None,
                                              ref(public_sdk.MaskRef, "MASK"), *item[2:]]) for item in value[1]])
        elif isinstance(value, torch.Tensor):
            value = ref(public_sdk.MaskRef, "MASK")
        return wire.decode(json.loads(json.dumps(wire.encode(value))))

    records, wire_failures = [], []
    for index, case in enumerate(plan):
        def run():
            bbox, segm = asyncio.run(provider_mod.UltralyticsDetectorProvider.execute(model_name=case["model_name"])).result
            through_wire(bbox)
            through_wire(segm)
            if case["node"] == "provider":
                kinds = {"impact.ultralytics_bbox": "UltraBBoxDetector", "impact.ultralytics_segm": "UltraSegmDetector"}
                return [kinds[bbox["secure_kind"]], "NO_SEGM_DETECTOR" if segm is None else kinds[segm["secure_kind"]]]
            image = make_image(case["image"])
            detector = segm if case["node"].startswith("segm") else bbox
            if case["node"] == "bbox_combined":
                (mask,) = asyncio.run(nodes._bbox_detector_combined(detector, image, case["threshold"], case["dilation"]))
            elif case["node"] == "segm_combined":
                (mask,) = asyncio.run(nodes._segm_detector_combined(detector, image, case["threshold"], case["dilation"]))
            else:
                handler = nodes._segm_detector_segs if case["node"] == "segm_segs" else nodes._bbox_detector_segs
                (segs,) = asyncio.run(handler(detector, image, case["threshold"], case["dilation"], case["crop_factor"],
                                              case["drop_size"], labels=case["labels"], detailer_hook=None))
                decoded = through_wire(segs)
                record = seg_record(segs[0], segs[1], True)
                wired = [[float(item[2]), [int(v) for v in item[3]], [float(v) for v in item[4]], str(item[5])]
                         for item in decoded[1]]
                if wired != [[r["confidence"], r["crop_region"], r["bbox"], r["label"]] for r in record["items"]] \
                        or [int(v) for v in decoded[0]] != record["shape"]:
                    wire_failures.append(index)
                return record
            through_wire(mask)
            return digest(mask.numpy())
        try:
            records.append(outcome(run))
        except Exception as exc:  # a wire failure outside the node call
            records.append(["error", type(exc).__name__, str(exc)])
            wire_failures.append(index)
    detector_module = sys.modules["impact_v2._ultralytics_detector"]
    models = {}
    for (folder, name), yolo in detector_module._MODELS.items():
        models[CATALOGUES[folder][name]] = model_record(yolo.model)
    with open(out_path, "w") as handle:
        json.dump({"records": records, "models": models, "wire_failures": wire_failures,
                   "blocked_imports": sorted(finder.blocked)}, handle)


# ---------------------------------------------------------------- manifests (real encoder)
def manifests():
    import copy
    sys.path.insert(0, "/overlay")
    from comfy_secure_nodes.packmanifest import FORMAT, encode_schema, encode_validation_inputs
    from comfy_secure_nodes.packruntime import manifest_declaration
    out = {}
    spec = importlib.util.spec_from_file_location("subpack_v2", os.path.join(SUBPACK, "v2", "__init__.py"),
                                                  submodule_search_locations=[os.path.join(SUBPACK, "v2")])
    package = importlib.util.module_from_spec(spec)
    sys.modules["subpack_v2"] = package
    spec.loader.exec_module(package)
    rows = {}
    for node_id, cls in package.NODE_CLASS_MAPPINGS.items():
        row = {"class": cls.__name__,
               "methods": {n: n in cls.__dict__ for n in ("check_lazy_status", "fingerprint_inputs", "validate_inputs")},
               "module": cls.__module__.removeprefix("subpack_v2."), "permissions": list(cls.SDK_PERMISSIONS),
               "schema": encode_schema(copy.deepcopy(cls.GET_SCHEMA())), "sdk_refs": cls.SDK_REFS is True}
        if "validate_inputs" in cls.__dict__:
            row["validation_inputs"] = encode_validation_inputs(cls)
        rows[node_id] = row
    out["subpack"] = json.dumps({"format": FORMAT, "nodes": rows, "runtime": manifest_declaration(os.path.join(SUBPACK, "v2"))},
                                indent=2, sort_keys=True) + "\n"
    out["impact_runtime"] = manifest_declaration(
        os.path.join(IMPACT, "v2"), dependency_profile_sha256="dbef5022f4a2411dee515081a66216fd9678a497bd1d07f086d6f091a84bcd74")
    return out


def main(argv):
    if argv[:1] == ["side"]:
        plan = json.load(open(argv[2]))
        return (run_original if argv[1] == "original" else run_v2)(plan, argv[3]) or 0
    if argv[:1] == ["generate-manifests"]:
        out = manifests()
        with open(os.path.join(RESULTS, "subpack-secure-nodes.json"), "w", newline="\n") as handle:
            handle.write(out["subpack"])
        with open(os.path.join(RESULTS, "impact-runtime.json"), "w", newline="\n") as handle:
            json.dump(out["impact_runtime"], handle, indent=1)
            handle.write("\n")
        print("wrote manifests")
        return 0
    write_fixtures()
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
    by_node, mismatches, designed = {}, [], {}
    for case, want, got in zip(plan, original["records"], v2["records"]):
        if case.get("designed") == "bare-name":
            designed["bare_name"] = {"original": want, "v2": got,
                                     "ok": want[0] == "error" and got == ["value", ["UltraBBoxDetector", "NO_SEGM_DETECTOR"]]}
            continue
        r = by_node.setdefault(case["node"], {"cases": 0, "mismatches": 0, "values": 0, "errors": 0, "segs_items": 0})
        r["cases"] += 1
        r["values" if want[0] == "value" else "errors"] += 1
        if want[0] == "value" and isinstance(want[1], dict):
            r["segs_items"] += len(want[1]["items"])
        if want != got:
            r["mismatches"] += 1
            mismatches.append({"case": case, "original": want, "v2": got})
    models_equal = {k: original["models"].get(k) == v2["models"].get(k) for k in MODELS}
    probe = next((g for w, g in zip(original["records"], v2["records"]) if w[0] == "value" and isinstance(w[1], dict)
                  and w[1]["items"]), None)
    perturbed = json.loads(json.dumps(probe))
    perturbed[1]["items"][0]["confidence"] += 1e-7
    negative_red = perturbed != probe
    # Optional imports their importers catch (torchvision: transforms/functional.py accimage, datasets/voc.py
    # defusedxml); anything else blocked means the guest lacks a module the detector path needs.
    known_optional = {"accimage", "defusedxml"}
    unexpected_blocked = sorted(set(v2["blocked_imports"]) - known_optional)
    ok = (not mismatches and all(models_equal.values()) and not v2["wire_failures"] and not unexpected_blocked
          and all(r["cases"] for r in by_node.values()) and all(d["ok"] for d in designed.values()))
    parity = {"status": "PASS" if ok else "FAIL", "nodes": {k: {"verdict": "EXACT" if not v["mismatches"] else "MISMATCH", **v}
                                                            for k, v in by_node.items()},
              "designed_differences": designed,
              "rebuilt_model_equals_checkpoint_model": models_equal, "models": {"original": original["models"], "v2": v2["models"]},
              "wire_failures": v2["wire_failures"], "guest_blocked_imports": v2["blocked_imports"],
              "guest_blocked_imports_unexpected": unexpected_blocked,
              "negative_control": {"perturbation": "one SEG confidence + 1e-7", "turned_red": negative_red}}
    with open(os.path.join(RESULTS, "parity.json"), "w") as handle:
        json.dump(parity, handle, indent=1, sort_keys=True)
        handle.write("\n")
    with open(os.path.join(RESULTS, "mismatches.json"), "w") as handle:
        json.dump(mismatches[:100], handle, indent=1)
        handle.write("\n")
    print(json.dumps({k: parity[k] for k in ("status", "nodes", "designed_differences", "rebuilt_model_equals_checkpoint_model",
                                             "wire_failures", "guest_blocked_imports", "negative_control")}, indent=1))
    return 0 if ok and negative_red else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
