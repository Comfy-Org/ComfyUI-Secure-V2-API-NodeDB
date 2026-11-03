"""ComfyUI_JPS-Nodes (pin 0e2a9aca02b1): tier-1 parity in the lane gate, original vs Secure Nodes V2.

run_in_gate.sh <pack root ComfyUI_JPS-Nodes-HEAD (pristine + v2/)> <v2/tests> <results> test_jps_nodes_parity.py
       [generate-manifest]

Original: the pristine jps_nodes.py imported under Core. v2: the converted classes with a fake SDK context, imports
restricted to the guest base. Both sides run every converted node on the same generated cases with the clock frozen at
one instant, and compare exactly: strings, numbers (float.hex), outputs in order, error type and message, and the
Get Date Time String change fingerprint. The committed secure-nodes.json must equal the real encoder's output.
Engine boundary (Lora Loader): the LoRA file is a synthetic safetensors fixture read with Core's load_torch_file on both
sides; comfy.sd.load_lora_for_models (original) and the trusted ModelRef.apply_lora's call to it (v2) are one stand-in
that tags MODEL and CLIP with the LoRA's keys and strengths. The v2 apply_lora stand-in repeats the trusted argument
checks of base 0cd9adec (keywords skip_zero / allow_extended_strengths) and, in a second run, of base 0b86765f (no
keywords), where strengths outside [-100, 100] are refused by name.
Negative control: a mutant v2 run (SDXL Resolutions returns height, width) must turn the comparison red.
"""
import asyncio
import datetime as _real_datetime
import glob
import importlib.abc
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import types
import warnings

sys.dont_write_bytecode = True
warnings.simplefilter("ignore")
PACK = "/pack"
RESULTS = "/results"
BASE = glob.glob("/bases/0cd9adec*/common-site-packages")[0]
for _index, _path in enumerate((BASE, "/core", "/overlay")):
    sys.path.insert(_index, _path)
os.environ.setdefault("HOME", "/tmp")
FROZEN = _real_datetime.datetime(2026, 11, 3, 4, 5, 6)
FX = "/tmp/fx"
LORA = "Lora Loader (JPS)"


class FrozenDateTime(_real_datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(*FROZEN.timetuple()[:6])


def write_fixtures():
    import torch
    from safetensors.torch import save_file
    os.makedirs(os.path.join(FX, "loras", "sub"), exist_ok=True)
    save_file({"lora_unet_a.alpha": torch.tensor(4.0), "lora_unet_a.lora_down.weight": torch.ones(2, 3)},
              os.path.join(FX, "loras", "fx_lora.safetensors"))
    save_file({"lora_te_b.alpha": torch.tensor(1.0)}, os.path.join(FX, "loras", "sub", "fx_te.safetensors"))


def stub_lora(model, clip, lora, strength_model, strength_clip):
    """Stand-in for comfy.sd.load_lora_for_models: a patched clone is tagged; a missing MODEL or CLIP stays None."""
    keys = ",".join(sorted(lora))
    new_model = None if model is None else f"{model}|lora[{keys}]x{float(strength_model).hex()}"
    new_clip = None if clip is None else f"{clip}|lora[{keys}]x{float(strength_clip).hex()}"
    return new_model, new_clip


def image(h, w, batch=1):
    import torch
    return torch.zeros((batch, h, w, 3))


def lora_case(switch, lora_name, strength_model, strength_clip, clip="base-clip"):
    return {"node": LORA, "args": {"model": "base-model", "clip": clip, "switch": switch, "lora_name": lora_name,
                                   "strength_model": strength_model, "strength_clip": strength_clip}}


def cases():
    out = []
    for res in ("square - 1024x1024 (1:1)", "landscape - 1152x896 (4:3)", "landscape - 1216x832 (3:2)",
                "landscape - 1344x768 (16:9)", "landscape - 1536x640 (21:9)", "portrait - 896x1152 (3:4)",
                "portrait - 832x1216 (2:3)", "portrait - 768x1344 (9:16)", "portrait - 640x1536 (9:21)", "other"):
        out.append({"node": "SDXL Resolutions (JPS)", "args": {"resolution": res}})
    for text in ("", "a cat", "multi\nline {a|b} __w__"):
        out.append({"node": "Text Prompt (JPS)", "args": {"text": text}})
        out.append({"node": "Text Prompt Combo (JPS)", "args": {"pos": text, "neg": text[::-1]}})
    for handling in ("Copy to Both if Empty", "Use Positive_G + Positive_L", "Copy Positive_G to Both",
                     "Copy Positive_L to Both", "Ignore Positive_G Input", "Ignore Positive_L Input",
                     "Combine Positive_G + Positive_L", "Combine Positive_L + Positive_G"):
        for g, l in (("big g", "small l"), ("", "only l"), ("only g", ""), ("", "")):
            out.append({"node": "SDXL Prompt Handling (JPS)", "args": {"handling": handling, "pos_g": g, "pos_l": l}})
    for w, h, f in ((1024, 1024, 2), (832, 1216, 3), (256, 8192, 8)):
        out.append({"node": "Resolution Multiply (JPS)", "args": {"width": w, "height": h, "factor": f}})
    for a, b in ((1, 2), (5, 3), (7, 7), (-4, -9), (2 ** 40, -1)):
        out.append({"node": "Largest Int (JPS)", "args": {"int_a": a, "int_b": b}})
    for a, b in ((3, 1.5), (7, 0.1), (-5, 2.25), (1024, 1.333333), (0, -3.5), (3, 1)):
        out.append({"node": "Multiply Int Float (JPS)", "args": {"int_a": a, "float_b": b}})
    texts = {"text1": "a", "text2": "", "text3": "c d", "text5": "e"}
    for delimiter in ("none", "space", "comma"):
        out.append({"node": "Text Concatenate (JPS)", "args": {"delimiter": delimiter, **texts}})
        out.append({"node": "Text Concatenate (JPS)", "args": {"delimiter": delimiter}})
        out.append({"node": "Text Concatenate (JPS)", "args": {"delimiter": delimiter, "text4": "only four"}})
    for style in ("%Y%m%d%H%M%S", "%Y%m%d%H%M", "%Y%m%d", "%Y-%m-%d-%H_%M_%S", "%Y-%m-%d-%H_%M", "%Y-%m-%d",
                  "%Y-%m-%d %H_%M_%S", "%Y-%m-%d %H_%M", "%H%M", "%H%M%S", "%H_%M", "%H_%M_%S"):
        out.append({"node": "Get Date Time String (JPS)", "args": {"style": style}})
        out.append({"node": "Get Date Time String (JPS)", "fingerprint": True, "args": {"style": style}})
    for sampler, scheduler in (("euler", "normal"), ("dpmpp_2m_sde_gpu", "karras"), ("uni_pc_bh2", "beta")):
        out.append({"node": "Sampler Scheduler Settings (JPS)", "args": {"sampler_name": sampler, "scheduler": scheduler}})
    for select in (0, 1, 2, 3, 5, 6):
        out.append({"node": "Integer Switch (JPS)", "args": {"select": select, "int_1": 11, "int_2": 22, "int_3": 33,
                                                            "int_4": 44, "int_5": 55}})
        out.append({"node": "Integer Switch (JPS)", "args": {"select": select, "int_2": 22}})
        out.append({"node": "Model Switch (JPS)", "args": {"select": select, "model_1": "m1", "model_3": "m3"}})
        out.append({"node": "Latent Switch (JPS)", "args": {"select": select, "latent_2": "l2", "latent_5": "l5"}})
    out.append({"node": "Model Switch (JPS)", "args": {"select": 2, "model_2": "m2"}})  # the original needs model_1
    for h, w, batch in ((64, 96, 1), (1216, 832, 2), (1, 7, 1)):
        out.append({"node": "Get Image Size (JPS)", "args": {"image": [h, w, batch]}})
    for switch in ("Off", "On"):
        for lora in ("None", "fx_lora.safetensors", "sub/fx_te.safetensors"):
            for sm, sc in ((0.0, 0.0), (1.0, 0.5), (-2.0, 3.0), (0.0, 1.0), (-0.0, 0.0)):
                out.append(lora_case(switch, lora, sm, sc))
    # Linked strengths are not held to the widget range [-10, 10]; and a CLIP output may be None.
    for sm, sc in ((150.0, 1.0), (1.0, -250.0), (float("nan"), 1.0), (float("inf"), 0.0), (-1e9, 1e9)):
        out.append(lora_case("On", "fx_lora.safetensors", sm, sc))
    for sm, sc in ((1.0, 2.0), (0.0, 2.0), (1.5, 0.0), (500.0, 1.0)):
        out.append(lora_case("On", "fx_lora.safetensors", sm, sc, clip=None))
    return out


def digest(value):
    if isinstance(value, float):
        return ["float", value.hex()]
    if isinstance(value, bool):
        return ["bool", value]
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


# ---------------------------------------------------------------- original side
def run_original(plan, out_path):
    import comfy.cli_args
    comfy.cli_args.args.cpu = True
    import comfy.sd
    import comfy.samplers  # noqa: F401  (Sampler_Scheduler_Settings reads it in its class body)
    import folder_paths
    write_fixtures()
    folder_paths.folder_names_and_paths["loras"] = ([os.path.join(FX, "loras")], {".safetensors"})
    root = "/tmp/orig-jps"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2", "__pycache__", ".git"))
    spec = importlib.util.spec_from_file_location("orig_jps", os.path.join(root, "__init__.py"),
                                                  submodule_search_locations=[root])
    package = importlib.util.module_from_spec(spec)
    sys.modules["orig_jps"] = package
    spec.loader.exec_module(package)
    jps = sys.modules["orig_jps.jps_nodes"]
    jps.datetime = FrozenDateTime
    comfy.sd.load_lora_for_models = stub_lora
    classes = jps.NODE_CLASS_MAPPINGS
    records = []
    for case in plan:
        node, args = case["node"], dict(case["args"])

        def run():
            cls = classes[node]
            if node == "Get Image Size (JPS)":
                args["image"] = image(*args["image"])
            if case.get("fingerprint"):
                return digest(cls.IS_CHANGED(**args)[0])
            return digest(getattr(cls(), cls.FUNCTION)(**args))
        records.append(outcome(run))
    with open(out_path, "w") as handle:
        json.dump({"records": records, "ids": list(classes)}, handle)


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
        if frame is not None and not frame.f_code.co_filename.startswith("/pack/"):
            return None
        self.blocked.add(fullname)
        raise ModuleNotFoundError(f"blocked in guest emulation: {fullname}", name=fullname)


class FakeRef:
    def __init__(self, value):
        self.value = value


class FakeAsset:
    def __init__(self, path):
        self.path = path


def trusted_apply_lora(model, asset, clip, strength_model, strength_clip, skip_zero, allow_extended_strengths):
    """The trusted ModelRef.apply_lora (comfy_api/latest/_sdk.py _model_apply_lora, base 0cd9adec; base 0b86765f has
    the same steps without the two keywords): argument checks, the CLIP rule, the zero skip, then
    comfy.utils.load_torch_file(path, safe_load=True, return_metadata=True) and load_lora_for_models (the stand-in)."""
    import comfy.utils
    if type(skip_zero) is not bool:
        raise TypeError("skip_zero must be a boolean")
    if type(allow_extended_strengths) is not bool:
        raise TypeError("allow_extended_strengths must be a boolean")
    strengths = {}
    for name, value in {"strength_model": strength_model, "strength_clip": strength_clip}.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a number")
        checked = float(value)
        if not allow_extended_strengths and (not math.isfinite(checked) or not -100.0 <= checked <= 100.0):
            raise ValueError(f"{name} must be finite and in [-100, 100]")
        strengths[name] = checked
    if not isinstance(model, FakeRef):
        raise TypeError("LoRA application needs a MODEL ref")
    if not isinstance(asset, FakeAsset):
        raise TypeError("LoRA application needs an ASSET ref")
    if clip is None and strengths["strength_clip"] != 0.0:
        raise ValueError("strength_clip must be zero when clip is None")
    if skip_zero and strengths["strength_model"] == 0.0 and strengths["strength_clip"] == 0.0:
        return model, clip
    state_dict, _metadata = comfy.utils.load_torch_file(asset.path, safe_load=True, return_metadata=True)
    new_model, new_clip = stub_lora(model.value, None if clip is None else clip.value, state_dict,
                                    strengths["strength_model"], strengths["strength_clip"])
    return type(model)(new_model), None if new_clip is None else FakeRef(new_clip)


class FakeModelRef(FakeRef):
    """Base 0cd9adec's ModelRef.apply_lora signature."""
    async def apply_lora(self, asset, clip, strength_model, strength_clip, *, skip_zero=True,
                         allow_extended_strengths=False):
        return trusted_apply_lora(self, asset, clip, strength_model, strength_clip, skip_zero,
                                  allow_extended_strengths)


class FakeModelRef0b(FakeRef):
    """Base 0b86765f's ModelRef.apply_lora signature (no keywords; zero skip and range check always on)."""
    async def apply_lora(self, asset, clip, strength_model, strength_clip):
        return trusted_apply_lora(self, asset, clip, strength_model, strength_clip, True, False)


def run_v2(plan, out_path, variant):
    write_fixtures()
    finder = GuestImports(GUEST_BASE | {"jps_v2"})
    sys.meta_path.insert(0, finder)
    v2 = os.path.join(PACK, "v2")
    spec = importlib.util.spec_from_file_location("jps_v2", os.path.join(v2, "__init__.py"),
                                                  submodule_search_locations=[v2])
    package = importlib.util.module_from_spec(spec)
    sys.modules["jps_v2"] = package
    spec.loader.exec_module(package)
    used = sys.modules["jps_v2._secure_used"]
    upstream = sys.modules["jps_v2._jps_upstream"]
    sys.meta_path.remove(finder)  # the stand-ins below use Core's helpers (the engine side)
    from comfy_api.latest import sdk as public_sdk
    wire_spec = importlib.util.spec_from_file_location("overlay_wire", "/overlay/comfy_secure_nodes/transport/wire.py")
    wire = importlib.util.module_from_spec(wire_spec)
    wire_spec.loader.exec_module(wire)
    upstream.datetime = FrozenDateTime
    model_ref = FakeModelRef0b if variant == "v2-base0b" else FakeModelRef
    if variant == "v2-mutant":
        original_method = upstream.SDXL_Resolutions.get_resolutions
        upstream.SDXL_Resolutions.get_resolutions = lambda self, resolution: original_method(self, resolution)[::-1]

    class Assets:
        async def resolve(self, folder, name):
            assert folder == "loras"
            path = os.path.join(FX, "loras", name)
            if not os.path.isfile(path):
                raise FileNotFoundError(f"no loras asset named {name!r}")
            return FakeAsset(path)

    context = types.SimpleNamespace(assets=Assets())
    used.sdk = types.SimpleNamespace(ctx=lambda: context)

    def unref(value):
        return value.value if isinstance(value, FakeRef) else value

    def through_wire(value):
        def refs(v):
            if isinstance(v, FakeRef):
                return public_sdk.ImageRef(kind="IMAGE", id="t")
            if isinstance(v, (list, tuple)):
                return [refs(x) for x in v]
            return v
        return wire.decode(json.loads(json.dumps(wire.encode(refs(value)))))

    records, wire_failures = [], []
    for index, case in enumerate(plan):
        node, args = case["node"], dict(case["args"])
        cls = used.NODE_CLASS_MAPPINGS[node]

        def run():
            if node == "Get Image Size (JPS)":
                args["image"] = image(*args["image"])
            if node in ("Model Switch (JPS)", "Latent Switch (JPS)"):
                for key in list(args):
                    if key != "select":
                        args[key] = FakeRef(args[key])
            if node == LORA:
                args["model"] = model_ref(args["model"])
                args["clip"] = None if args["clip"] is None else FakeRef(args["clip"])
            if case.get("fingerprint"):
                return digest(cls.fingerprint_inputs(**args))
            outputs = tuple(asyncio.run(cls.execute(**args)).args)
            try:
                through_wire(outputs)
            except Exception as exc:
                wire_failures.append([index, f"{type(exc).__name__}: {exc}"])
            return digest(tuple(unref(v) for v in outputs))
        records.append(outcome(run))
    # every other declared node: validation and execute both refuse by name
    refusals = []
    for node_id, cls in sys.modules["jps_v2._secure_unconverted"].NODE_CLASS_MAPPINGS.items():
        message = f"comfyui_jps-nodes/{node_id} is not yet converted to Secure Nodes V2"
        validated = outcome(lambda: cls.validate_inputs())
        executed = outcome(lambda: asyncio.run(cls.execute()))
        refusals.append({"node": node_id, "validate": validated, "execute": executed,
                         "ok": validated == ["value", message] and executed == ["error", "NotConvertedError", message]})
    with open(out_path, "w") as handle:
        json.dump({"records": records, "wire_failures": wire_failures, "blocked_imports": sorted(finder.blocked),
                   "ids": list(package.NODE_CLASS_MAPPINGS), "refusals": refusals}, handle)


def expected_base0b(case, want):
    """Base 0b86765f (apply_lora without keywords) differs from the original only where the call is reached with an
    effective strength outside [-100, 100] (refused by name) or with both effective strengths zero (the inputs come
    back; the original's zero-strength clone computes the same values). The effective CLIP strength is zero without a
    CLIP. Returns (expected record, designed label or None)."""
    a = case["args"]
    if (case["node"] != LORA or want[0] != "value" or a["switch"] == "Off" or a["lora_name"] == "None"
            or (a["strength_model"] == 0 and a["strength_clip"] == 0)):
        return want, None
    strengths = {"strength_model": a["strength_model"], "strength_clip": a["strength_clip"] if a["clip"] else 0.0}
    for name, value in strengths.items():
        if not math.isfinite(value) or not -100.0 <= value <= 100.0:
            return ["error", "ValueError", f"{name} must be finite and in [-100, 100]"], "refused: strength range"
    if strengths["strength_model"] == 0 and strengths["strength_clip"] == 0:
        return ["value", [a["model"], a["clip"]]], "inputs returned: both effective strengths zero"
    return want, None


def compare(plan, original, v2):
    by_node, mismatches = {}, []
    for case, want, got in zip(plan, original, v2, strict=True):
        row = by_node.setdefault(case["node"], {"cases": 0, "mismatches": 0, "errors": 0})
        row["cases"] += 1
        row["errors"] += want[0] == "error"
        if want != got:
            row["mismatches"] += 1
            mismatches.append({"case": case, "original": want, "v2": got})
    for row in by_node.values():
        row["verdict"] = "EXACT" if not row["mismatches"] else "MISMATCH"
    return by_node, mismatches


def manifest_text():
    """secure-nodes.json from the v2 classes with the real encoder (comfy_secure_nodes.packmanifest, /overlay)."""
    import copy
    import comfy.cli_args
    comfy.cli_args.args.cpu = True
    from comfy_secure_nodes.packmanifest import FORMAT, encode_schema, encode_validation_inputs
    from comfy_secure_nodes.packruntime import manifest_declaration
    v2 = os.path.join(PACK, "v2")
    spec = importlib.util.spec_from_file_location("jps_v2", os.path.join(v2, "__init__.py"),
                                                  submodule_search_locations=[v2])
    package = importlib.util.module_from_spec(spec)
    sys.modules["jps_v2"] = package
    spec.loader.exec_module(package)
    nodes = {}
    for node_id, cls in package.NODE_CLASS_MAPPINGS.items():
        row = {
            "class": cls.__name__,
            "methods": {name: name in cls.__dict__ for name in ("check_lazy_status", "fingerprint_inputs", "validate_inputs")},
            "module": cls.__module__.removeprefix("jps_v2."),
            "permissions": list(cls.SDK_PERMISSIONS),
            "schema": encode_schema(copy.deepcopy(cls.GET_SCHEMA())),
            "sdk_refs": cls.SDK_REFS is True,
        }
        if "validate_inputs" in cls.__dict__:
            row["validation_inputs"] = encode_validation_inputs(cls)
        nodes[node_id] = row
    manifest = {"format": FORMAT, "nodes": nodes, "runtime": manifest_declaration(v2)}
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


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
    committed = os.path.join(PACK, "v2", "secure-nodes.json")
    manifest_equal = os.path.exists(committed) and open(committed, encoding="utf-8").read() == open(
        "/tmp/secure-nodes.json", encoding="utf-8").read()
    plan = cases()
    with open("/tmp/plan.json", "w") as handle:
        json.dump(plan, handle)
    sides = {}
    for side in ("original", "v2", "v2-base0b", "v2-mutant"):
        with open(os.path.join(RESULTS, f"side-{side}.log"), "w") as log:
            proc = subprocess.run([sys.executable, "-I", "-B", os.path.abspath(__file__), "side", side, "/tmp/plan.json",
                                   f"/tmp/out-{side}.json"], stdout=log, stderr=subprocess.STDOUT, timeout=3000)
        if proc.returncode != 0:
            print(f"side {side} failed ({proc.returncode}); see side-{side}.log")
            return 1
        sides[side] = json.load(open(f"/tmp/out-{side}.json"))
        shutil.copyfile(f"/tmp/out-{side}.json", os.path.join(RESULTS, f"outcomes-{side}.json"))
    original = sides["original"]["records"]
    by_node, mismatches = compare(plan, original, sides["v2"]["records"])
    # base 0b86765f fallback: identical except the designed cases, each with its exact expected record
    expected0b, designed0b = [], []
    for case, want in zip(plan, original):
        expected, label = expected_base0b(case, want)
        expected0b.append(expected)
        if label:
            designed0b.append({"case": case, "designed": label, "original": want, "expected_v2": expected})
    _, mismatches0b = compare(plan, expected0b, sides["v2-base0b"]["records"])
    mutant_nodes, mutant_mismatches = compare(plan, original, sides["v2-mutant"]["records"])
    mutant_red = {node for node, row in mutant_nodes.items() if row["mismatches"]} == {"SDXL Resolutions (JPS)"}
    wire_failures = {side: sides[side]["wire_failures"] for side in ("v2", "v2-base0b")}
    blocked = sorted(set(sides["v2"]["blocked_imports"]) | set(sides["v2-base0b"]["blocked_imports"]))
    unexpected = sorted(set(blocked) - {"accimage", "defusedxml"})
    refusals = sides["v2"]["refusals"]
    ids_equal = (sorted(sides["v2"]["ids"]) == sorted(sides["original"]["ids"])
                 and len(set(sides["v2"]["ids"])) == len(sides["v2"]["ids"]))
    refusals_ok = (all(r["ok"] for r in refusals) and len(refusals) + len(by_node) == len(sides["original"]["ids"])
                   and not {r["node"] for r in refusals} & set(by_node))
    ok = (not mismatches and not mismatches0b and not any(wire_failures.values()) and not unexpected and manifest_equal
          and mutant_red and ids_equal and refusals_ok)
    parity = {"status": "PASS" if ok else "FAIL", "cases": len(plan), "nodes": by_node,
              "manifest_equals_real_encoder": manifest_equal,
              "node_ids_equal_original": ids_equal,
              "refused_by_name": {"nodes": len(refusals), "all_ok": refusals_ok,
                                  "failures": [r for r in refusals if not r["ok"]]},
              "base_0b86765f_fallback": {"cases": len(plan), "mismatches": len(mismatches0b),
                                         "designed": len(designed0b), "designed_cases": designed0b},
              "wire_failures": wire_failures, "guest_blocked_imports": blocked,
              "guest_blocked_imports_unexpected": unexpected,
              "negative_control": {"mutation": "SDXL_Resolutions.get_resolutions returns (height, width)",
                                   "mismatches": len(mutant_mismatches), "turned_red_only_there": mutant_red}}
    with open(os.path.join(RESULTS, "parity.json"), "w") as handle:
        json.dump(parity, handle, indent=1, sort_keys=True)
        handle.write("\n")
    with open(os.path.join(RESULTS, "mismatches.json"), "w") as handle:
        json.dump({"v2": mismatches[:40], "v2-base0b": mismatches0b[:40]}, handle, indent=1)
        handle.write("\n")
    print(json.dumps({k: parity[k] for k in ("status", "cases", "nodes", "manifest_equals_real_encoder", "wire_failures",
                                             "node_ids_equal_original", "refused_by_name",
                                             "guest_blocked_imports_unexpected", "negative_control")}, indent=1))
    print(json.dumps({"base_0b86765f_fallback": {k: v for k, v in parity["base_0b86765f_fallback"].items()
                                                 if k != "designed_cases"}}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
