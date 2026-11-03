"""ComfyUI_Mira (pin dfb1c847, V3-native): tier-1 parity in the lane gate, original vs Secure Nodes V2.

run_in_gate.sh <pack root ComfyUI_Mira-HEAD (pristine + v2/)> <v2/tests> <results> test_comfyui_mira_parity.py
       [generate-manifest]

Original: the pristine pack imported under Core (cv2 and piexif, which the gate lacks, are inert stubs for pack
imports only), its nodes taken from its own comfy_entrypoint(). v2: the converted classes, behind a guest import
guard (sealed guest_common.lock modules + stdlib + v2 itself) installed before v2 loads and kept while the cases run.
Both sides run every converted node on the same generated cases; outputs are compared exactly (tensors by dtype, shape
and bytes; numbers by float.hex; strings; error type and message). Also, for all 82 ids: the encoded V3 schema and the
V1 projection (INPUT_TYPES(), what /object_info serves) of v2 equal the original's; every refused id refuses by name at
validation and in execute; Image Color Transfer's OpenCV methods refuse by name; the committed secure-nodes.json
equals the real encoder's output. Engine boundary: UpscaleImageByModelThenResize's upscale model is a stand-in model;
the original runs it through its own upscale() (Core's tiled_scale), and v2's UpscaleModelRef.upscale(images,
tile_size=512) stand-in runs the engine's steps (Core's tiled_scale with 512 tiles and 32 overlap, then clamp).
Negative control: a mutant v2 run (Fixeight rounds to the next multiple of 8 one step later) must turn red.
"""
import asyncio
import copy
import glob
import hashlib
import importlib.abc
import importlib.machinery
import importlib.util
import inspect
import json
import os
import shutil
import subprocess
import sys
import types
import warnings

sys.dont_write_bytecode = True
warnings.simplefilter("ignore")
PACK = "/pack"
V2 = "/pack/v2"
RESULTS = "/results"
BASE = glob.glob("/bases/0cd9adec*/common-site-packages")[0]
for _index, _path in enumerate((BASE, "/core", "/overlay")):
    sys.path.insert(_index, _path)
os.environ.setdefault("HOME", "/tmp")
PACK_ID = "comfyui_mira"
CONVERTED = ["CanvasCreatorAdvanced", "CanvasCreatorSimple", "ImageColorTransferMira", "ImageContrast", "ImageSharpness",
             "IntToFloatMultiplication", "NumeralToString", "SeedGeneratorMira", "StepsAndCfg", "TextBoxMira",
             "TextCombinerSix", "TextCombinerTwo", "UpscaleImageByModelThenResize", "illustrious_character_select_en"]
# Top-level modules of the sealed guest base: the 41 pins of guest_common.lock (sha256 333e9487...).
GUEST_LOCK_MODULES = {
    "av", "blake3", "comfy_api", "comfy_secure_nodes", "comfy_secure_sdk", "filelock", "fsspec", "iniconfig", "jinja2",
    "markupsafe", "mpmath", "networkx", "numpy", "nvidia", "packaging", "PIL", "pluggy", "psutil", "pygments", "pytest",
    "_pytest", "py", "pytest_asyncio", "safetensors", "setuptools", "pkg_resources", "_distutils_hack", "sympy",
    "torch", "functorch", "torchgen", "triton", "typing_extensions", "wheel",
}


# ---------------------------------------------------------------- shared fixtures and stand-ins
def image(seed, b, h, w, c=3):
    import torch
    g = torch.Generator().manual_seed(seed)
    return torch.rand((b, h, w, c), generator=g, dtype=torch.float32)


class StandInUpscaleModel:
    """An upscale model as the original's upscale() and the engine see it: .model, .scale, .to(), called on NCHW."""

    def __init__(self, scale=2):
        import torch
        self.scale = scale
        self.model = torch.nn.Identity()

    def to(self, *args, **kwargs):
        return self

    def __call__(self, a):
        import torch
        up = torch.nn.functional.interpolate(a, scale_factor=self.scale, mode="nearest")
        return up * 0.9 + 0.05


def engine_upscale(model, pixels, tile=512, overlap=32):
    """The engine's UpscaleModelRef.upscale(images, tile_size=512) steps for one batch (comfy_api _sdk.py
    _upscale_model_upscale, tiled path): Core's tiled_scale over NCHW tiles, then clamp to [0, 1] in NHWC."""
    import comfy.utils
    import torch
    current = pixels.movedim(-1, -3)
    out = comfy.utils.tiled_scale(current, model, tile_x=tile, tile_y=tile, overlap=overlap,
                                  upscale_amount=float(model.scale))
    return torch.clamp(out.movedim(-3, -1), min=0, max=1.0)


def characters():
    rows = open(os.path.join(PACK, "json", "waiIllustriousSDXL_v160_characters.csv"), encoding="utf-8").readlines()
    return ["random"] + [line.split(",")[1].strip() for line in rows]


def cases():
    out = []
    for w, h, land in ((576, 1024, False), (576, 1024, True), (8, 2000, False), (4096, 16, True)):
        out.append({"node": "CanvasCreatorSimple", "args": {"Width": w, "Height": h, "Landscape": land}})
    for w, h, b, land, m in ((576, 1024, 1, False, 1.5), (577, 1023, 0, True, 0.5), (1000, 800, 4, False, 2.25),
                             (16, 16, 16, True, 8.0), (100, 100, 1, False, 1.3333)):
        out.append({"node": "CanvasCreatorAdvanced", "args": {"Width": w, "Height": h, "Batch": b, "Landscape": land,
                                                             "HiResMultiplier": m}})
    for seed in (0, 123, 2 ** 63 + 5, 0xffffffffffffffff):
        out.append({"node": "SeedGeneratorMira", "args": {"seed": seed}})
    for a, b in ((3, 1.5), (-7, 0.1), (1024, 1.333333), (0, -2.5)):
        out.append({"node": "IntToFloatMultiplication", "args": {"int_value": a, "multiply_value": b}})
    for value in (5, 3.25, -0.0, True, "text"):
        out.append({"node": "NumeralToString", "args": {"numeral": value}})
    for steps, cfg in ((20, 7.5), (1, 0.0)):
        out.append({"node": "StepsAndCfg", "args": {"steps": steps, "cfg": cfg}})
    for text in ("", "hello\nworld"):
        out.append({"node": "TextBoxMira", "args": {"text": text}})
    out.append({"node": "TextCombinerSix", "args": {f"text{i}": t for i, t in enumerate(["a", "", "c ", "\n", "é", "f"], 1)}})
    out.append({"node": "TextCombinerTwo", "args": {"text1": "left,", "text2": " right"}})
    names = characters()
    picks = [names[5], names[len(names) // 2], names[-1]]
    for character in ["random"] + picks:
        for seed in ((0, 1, 2, len(names) - 1, len(names), 12345) if character == "random" else (7,)):
            for weight, custom, before in ((1.0, "", False), (1.25, "smile", True), (0.5, "a, b,", False)):
                out.append({"node": "illustrious_character_select_en", "args": {
                    "character": character, "random_action_seed": seed, "character_weight": weight,
                    "insert_before_character": before, "custom_prompt": custom}})
    for node, levels in (("ImageContrast", (0.0, 0.5, 1.0, 1.7, 10.0)), ("ImageSharpness", (0.0, 1.0, 2.5, 100.0))):
        for shape in ((1, 24, 32), (2, 16, 16)):
            for level in levels:
                out.append({"node": node, "args": {"src_image": ["image", 11, *shape], "level": level}})
    for method in ("Mean", "Pdf"):
        for src, ref in (((1, 24, 32), (1, 20, 20)), ((2, 16, 24), (1, 16, 24)), ((2, 16, 24), (2, 12, 12))):
            out.append({"node": "ImageColorTransferMira", "args": {"src_image": ["image", 21, *src],
                                                                  "ref_image": ["image", 22, *ref], "method": method}})
    out.append({"node": "ImageColorTransferMira", "args": {"src_image": ["image", 23, 3, 8, 8],
                                                          "ref_image": ["image", 24, 2, 8, 8], "method": "Mean"}})
    for method in ("Lab", "Pdf+Regrain"):
        out.append({"node": "ImageColorTransferMira", "designed": "opencv",
                    "args": {"src_image": ["image", 25, 1, 8, 8], "ref_image": ["image", 26, 1, 8, 8], "method": method}})
    for shape in ((1, 24, 32), (2, 20, 28), (1, 40, 700)):
        for scale in (0.5, 1.5, 2.0):
            for method in ("lanczos", "nearest", "nearest-exact", "bilinear", "bicubic", "box", "hamming"):
                if shape == (1, 40, 700) and method not in ("lanczos", "bilinear"):
                    continue
                out.append({"node": "UpscaleImageByModelThenResize", "args": {
                    "upscale_model": "standin-x2", "image": ["image", 31, *shape], "resize_scale": scale,
                    "resize_method": method}})
    return out


def materialize(value):
    if isinstance(value, list) and value and value[0] == "image":
        return image(*value[1:])
    return value


def digest(value):
    import torch
    if isinstance(value, torch.Tensor):
        t = value.detach().cpu().contiguous()
        return ["tensor", str(t.dtype), list(t.shape), hashlib.sha256(t.numpy().tobytes()).hexdigest()]
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, float):
        return ["float", value.hex()]
    if isinstance(value, int):
        return ["int", value]
    if isinstance(value, (list, tuple)):
        return [digest(v) for v in value]
    return value


def outcome(fn):
    try:
        return ["value", fn()]
    except Exception as exc:
        return ["error", type(exc).__name__, str(exc)]


def plain(value):
    return json.loads(json.dumps(value, default=lambda v: getattr(v, "value", repr(v))))


def schema_records(classes):
    from comfy_secure_nodes.packmanifest import encode_schema
    records = {}
    for cls in classes:
        schema = cls.GET_SCHEMA()
        records[schema.node_id] = {"schema": encode_schema(copy.deepcopy(schema)), "v1": plain(cls.INPUT_TYPES())}
    return records


# ---------------------------------------------------------------- original side
class _InertValue:
    def __init__(self, name):
        self._name = name

    def __getattr__(self, attr):
        if attr.startswith("__") and attr.endswith("__"):
            raise AttributeError(attr)
        return _InertValue(f"{self._name}.{attr}")

    def __call__(self, *args, **kwargs):
        return _InertValue(f"{self._name}()")

    def __mro_entries__(self, bases):
        return (object,)


class _Inert(types.ModuleType):
    def __init__(self, name):
        super().__init__(name)
        self.__path__ = []

    def __getattr__(self, attr):
        if attr.startswith("__") and attr.endswith("__"):
            raise AttributeError(attr)
        return _InertValue(f"{self.__name__}.{attr}")


class _PackScopedStubs(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    ALLOW = {"cv2", "piexif"}

    def __init__(self, root):
        self.root = root

    def find_spec(self, fullname, path, target=None):
        if fullname.split(".")[0] not in self.ALLOW:
            return None
        frame = sys._getframe(1)
        while frame is not None and frame.f_code.co_filename.startswith("<frozen importlib"):
            frame = frame.f_back
        if frame is None or not frame.f_code.co_filename.startswith(self.root):
            return None
        return importlib.machinery.ModuleSpec(fullname, self, is_package=True)

    def create_module(self, spec):
        return _Inert(spec.name)

    def exec_module(self, module):
        return None


def run_original(plan, out_path):
    import comfy.cli_args
    comfy.cli_args.args.cpu = True
    import folder_paths
    for setter, path in (("set_output_directory", "/tmp/out"), ("set_input_directory", "/tmp/in"),
                         ("set_temp_directory", "/tmp/temp")):
        os.makedirs(path, exist_ok=True)
        getattr(folder_paths, setter)(path)
    root = "/tmp/orig-mira"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2", "__pycache__", ".git"))
    sys.meta_path.append(_PackScopedStubs(root))
    spec = importlib.util.spec_from_file_location("orig_mira", os.path.join(root, "__init__.py"),
                                                  submodule_search_locations=[root])
    package = importlib.util.module_from_spec(spec)
    sys.modules["orig_mira"] = package
    spec.loader.exec_module(package)
    classes = asyncio.run(asyncio.run(package.comfy_entrypoint()).get_node_list())
    by_id = {cls.GET_SCHEMA().node_id: cls for cls in classes}
    records = []
    for case in plan:
        if case.get("designed"):
            records.append(["designed", case["designed"]])
            continue
        node, args = case["node"], {k: materialize(v) for k, v in case["args"].items()}
        if node == "UpscaleImageByModelThenResize":
            args["upscale_model"] = StandInUpscaleModel()

        def run():
            result = by_id[node].execute(**args)
            result = getattr(result, "args", result)
            return digest(tuple(result))
        records.append(outcome(run))
    with open(out_path, "w") as handle:
        json.dump({"records": records, "schemas": schema_records(classes), "ids": list(by_id)}, handle)


# ---------------------------------------------------------------- v2 side
GUARD = {"blocked": []}


def install_guest_import_guard():
    """Block imports executed by v2 code that a guest would not have (builtins.__import__ sees every import statement,
    module-level and function-local, also for modules already in sys.modules)."""
    import builtins
    real_import = builtins.__import__

    def guarded(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0:
            caller = sys._getframe(1).f_code.co_filename
            if caller.startswith(V2 + "/") and not caller.startswith(V2 + "/tests/"):
                top = name.split(".")[0]
                if top not in sys.stdlib_module_names and top not in GUEST_LOCK_MODULES and top != "mira_v2":
                    GUARD["blocked"].append(f"{os.path.relpath(caller, V2)}: {name}")
                    raise ModuleNotFoundError(f"guest import guard: {name!r} is not in the guest", name=name)
        return real_import(name, globals, locals, fromlist, level)
    builtins.__import__ = guarded


class FakeImageRef:
    def __init__(self, value):
        self.value = value

    async def raw(self):
        return self.value

    @classmethod
    async def from_value(cls, value):
        return cls(value)


class FakeUpscaleModelRef:
    def __init__(self):
        self.model = StandInUpscaleModel()

    async def upscale(self, images, tile_size=None):
        assert tile_size == 512
        return FakeImageRef(engine_upscale(self.model, images.value, tile=tile_size))


def run_v2(plan, out_path, variant):
    install_guest_import_guard()
    spec = importlib.util.spec_from_file_location("mira_v2", os.path.join(V2, "__init__.py"),
                                                  submodule_search_locations=[V2])
    package = importlib.util.module_from_spec(spec)
    sys.modules["mira_v2"] = package
    spec.loader.exec_module(package)
    used = sys.modules["mira_v2._secure_used"]
    used.sdk = types.SimpleNamespace(ImageRef=FakeImageRef)
    if variant == "v2-mutant":
        util = sys.modules["mira_v2._mira_util"]
        original_fix = util.Fixeight
        util.Fixeight = lambda num: original_fix(num) + 8
    records = []
    for case in plan:
        node, args = case["node"], {k: materialize(v) for k, v in case["args"].items()}
        cls = used.NODE_CLASS_MAPPINGS[node]
        if node == "UpscaleImageByModelThenResize":
            args["upscale_model"] = FakeUpscaleModelRef()
            args["image"] = FakeImageRef(args["image"])

        def run():
            result = cls.execute(**args)
            if inspect.iscoroutine(result):
                result = asyncio.run(result)
            values = [v.value if isinstance(v, FakeImageRef) else v for v in result.args]
            return digest(tuple(values))
        records.append(outcome(run))
    unconverted = sys.modules["mira_v2._secure_unconverted"]
    refusals = []
    for node_id, cls in unconverted.NODE_CLASS_MAPPINGS.items():
        message = f"{PACK_ID}/{node_id} is not yet converted to Secure Nodes V2"
        validated = outcome(lambda: cls.validate_inputs())
        executed = outcome(lambda: asyncio.run(cls.execute()))
        refusals.append({"node": node_id, "ok": validated == ["value", message]
                         and executed == ["error", "NotConvertedError", message]})
    with open(out_path, "w") as handle:
        json.dump({"records": records, "schemas": schema_records(package.NODE_CLASS_MAPPINGS.values()),
                   "ids": list(package.NODE_CLASS_MAPPINGS), "refusals": refusals, "guard_blocked": GUARD["blocked"]},
                  handle)


def manifest_text():
    """secure-nodes.json from the v2 classes with the real encoder (comfy_secure_nodes.packmanifest, /overlay)."""
    import comfy.cli_args
    comfy.cli_args.args.cpu = True
    from comfy_secure_nodes.packmanifest import FORMAT, encode_schema, encode_validation_inputs
    from comfy_secure_nodes.packruntime import manifest_declaration
    spec = importlib.util.spec_from_file_location("mira_v2", os.path.join(V2, "__init__.py"),
                                                  submodule_search_locations=[V2])
    package = importlib.util.module_from_spec(spec)
    sys.modules["mira_v2"] = package
    spec.loader.exec_module(package)
    nodes = {}
    for node_id, cls in package.NODE_CLASS_MAPPINGS.items():
        row = {
            "class": cls.__name__,
            "methods": {name: name in cls.__dict__ for name in ("check_lazy_status", "fingerprint_inputs", "validate_inputs")},
            "module": cls.__module__.removeprefix("mira_v2."),
            "permissions": list(cls.SDK_PERMISSIONS),
            "schema": encode_schema(copy.deepcopy(cls.GET_SCHEMA())),
            "sdk_refs": cls.SDK_REFS is True,
        }
        if "validate_inputs" in cls.__dict__:
            row["validation_inputs"] = encode_validation_inputs(cls)
        nodes[node_id] = row
    manifest = {"format": FORMAT, "nodes": nodes, "runtime": manifest_declaration(V2)}
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def compare(plan, original, v2):
    by_node, mismatches, designed = {}, [], []
    for case, want, got in zip(plan, original, v2, strict=True):
        row = by_node.setdefault(case["node"], {"cases": 0, "mismatches": 0, "errors": 0, "designed": 0})
        row["cases"] += 1
        if want[0] == "designed":
            row["designed"] += 1
            ok = got[0] == "error" and got[1] == "SecureConversionRefusal" and "OpenCV" in got[2]
            designed.append({"case": case, "v2": got, "ok": ok})
            if not ok:
                row["mismatches"] += 1
            continue
        row["errors"] += want[0] == "error"
        if want != got:
            row["mismatches"] += 1
            mismatches.append({"case": case, "original": want, "v2": got})
    for row in by_node.values():
        row["verdict"] = "EXACT" if not row["mismatches"] else "MISMATCH"
    return by_node, mismatches, designed


def main(argv):
    if argv[:1] == ["side"]:
        plan = json.load(open(argv[2]))
        if argv[1] == "original":
            return run_original(plan, argv[3]) or 0
        return run_v2(plan, argv[3], argv[1]) or 0
    if argv[:1] in (["generate-manifest"], ["manifest-only"]):
        text = manifest_text()
        out = os.path.join("/tmp" if argv[0] == "manifest-only" else RESULTS, "secure-nodes.json")
        with open(out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        print(f"wrote {out}")
        return 0
    with open(os.path.join(RESULTS, "manifest-check.log"), "w") as log:
        subprocess.run([sys.executable, "-I", "-B", os.path.abspath(__file__), "manifest-only"], stdout=log,
                       stderr=subprocess.STDOUT, timeout=600, check=True)
    committed = os.path.join(V2, "secure-nodes.json")
    manifest_equal = os.path.exists(committed) and open(committed, encoding="utf-8").read() == open(
        "/tmp/secure-nodes.json", encoding="utf-8").read()
    plan = cases()
    with open("/tmp/plan.json", "w") as handle:
        json.dump(plan, handle)
    sides = {}
    for side in ("original", "v2", "v2-mutant"):
        with open(os.path.join(RESULTS, f"side-{side}.log"), "w") as log:
            proc = subprocess.run([sys.executable, "-I", "-B", os.path.abspath(__file__), "side", side, "/tmp/plan.json",
                                   f"/tmp/out-{side}.json"], stdout=log, stderr=subprocess.STDOUT, timeout=3000)
        if proc.returncode != 0:
            print(f"side {side} failed ({proc.returncode}); see side-{side}.log")
            return 1
        sides[side] = json.load(open(f"/tmp/out-{side}.json"))
        shutil.copyfile(f"/tmp/out-{side}.json", os.path.join(RESULTS, f"outcomes-{side}.json"))
    original = sides["original"]["records"]
    by_node, mismatches, designed = compare(plan, original, sides["v2"]["records"])
    mutant_nodes, mutant_mismatches, _ = compare(plan, original, sides["v2-mutant"]["records"])
    mutant_red = {n for n, r in mutant_nodes.items() if r["mismatches"]} == {"CanvasCreatorAdvanced",
                                                                             "UpscaleImageByModelThenResize"}
    o_schemas, v_schemas = sides["original"]["schemas"], sides["v2"]["schemas"]
    schema_diffs = sorted(n for n in o_schemas if o_schemas[n]["schema"] != v_schemas.get(n, {}).get("schema"))
    option_diffs = sorted(n for n in o_schemas if o_schemas[n]["v1"] != v_schemas.get(n, {}).get("v1"))
    ids_equal = sorted(sides["original"]["ids"]) == sorted(sides["v2"]["ids"])
    refusals = sides["v2"]["refusals"]
    refusals_ok = all(r["ok"] for r in refusals) and len(refusals) + len(CONVERTED) == len(sides["original"]["ids"])
    guard = sides["v2"]["guard_blocked"]
    ok = (not mismatches and all(d["ok"] for d in designed) and manifest_equal and mutant_red and not schema_diffs
          and not option_diffs and ids_equal and refusals_ok and not guard)
    parity = {"status": "PASS" if ok else "FAIL", "pack": PACK_ID, "pin": "dfb1c847097cf1f69055c46c24b723a5a55f2e09",
              "cases": len(plan), "nodes": by_node, "designed_refusals": designed,
              "manifest_equals_real_encoder": manifest_equal, "node_ids_equal_original": ids_equal,
              "all_nodes": {"count": len(o_schemas), "schema_mismatches": schema_diffs,
                            "v1_option_mismatches": option_diffs},
              "refused_by_name": {"nodes": len(refusals), "all_ok": refusals_ok,
                                  "failures": [r for r in refusals if not r["ok"]]},
              "guest_import_guard": {"base": "guest_common.lock (41 pins)", "blocked": guard},
              "negative_control": {"mutation": "Fixeight returns 8 more", "mismatches": len(mutant_mismatches),
                                   "turned_red_only_there": mutant_red}}
    with open(os.path.join(RESULTS, "parity.json"), "w") as handle:
        json.dump(parity, handle, indent=1, sort_keys=True)
        handle.write("\n")
    with open(os.path.join(RESULTS, "mismatches.json"), "w") as handle:
        json.dump(mismatches[:40], handle, indent=1)
        handle.write("\n")
    print(json.dumps({k: parity[k] for k in ("status", "cases", "nodes", "manifest_equals_real_encoder",
                                             "node_ids_equal_original", "all_nodes", "refused_by_name",
                                             "guest_import_guard", "negative_control")}, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
