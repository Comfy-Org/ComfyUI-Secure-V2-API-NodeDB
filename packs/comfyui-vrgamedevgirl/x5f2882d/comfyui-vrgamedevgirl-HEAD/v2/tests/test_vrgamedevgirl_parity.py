"""comfyui-vrgamedevgirl to-50% conversion (pin 5f2882d835bf): tier-1 parity in the lane gate.

run_in_gate.sh <pack root with v2/> <v2/tests> <results> test_vrgamedevgirl_parity.py [generate-manifest]

  generate-manifest  write /results/secure-nodes.json from the v2 classes with the real encoder
                     (comfy_secure_nodes.packmanifest, /overlay).
  (default)          parity:
    U  the six converted nodes, original vs v2, on seeded fixtures: tensors by torch.equal (dtype, shape and
       bytes), strings by equality, exceptions by type and message. The originals are imported from the
       pristine pack (a /tmp copy) with inert stubs only for libraries the gate lacks (librosa,
       torchaudio, cv2, imageio, demucs), imported only by pack files. FastFilmGrain's noise is
       unseeded upstream; both sides run after the same torch.manual_seed. ColorMatchToReference: the
       original calls kornia 0.8.3 from the gate image; v2 calls the vendored copy. VRGDG_LUTS: fixture
       .cube files placed in the original's LUTS folder and served to v2 by a fake vrgdg_luts asset kind.
    S  the 258 unconverted nodes: each schema round-trips to its frozen form; validate_inputs returns
       "<pack>/<node> is not yet converted to Secure Nodes V2"; execute raises the same message.
    M  v2/secure-nodes.json equals the real encoder's output for the v2 classes.
    N  negative control: one perturbed converted output must be caught.
    G  guest import guard, installed before v2 loads and kept for the whole run: an import executed by v2 code
       (module-level or function-local) must be in the standard library, the sealed guest base
       (guest_common.lock) or the v2 package itself; anything else is blocked and fails the run.
"""
import asyncio
import copy
import glob
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import json
import math
import os
import random
import shutil
import sys
import types
import warnings

sys.dont_write_bytecode = True
warnings.simplefilter("ignore")
PACK = "/pack"
V2 = "/pack/v2"
RESULTS = "/results"
BASE = glob.glob("/bases/0cd9adec*/common-site-packages")[0]
# Guest SDK first (comfy_api 0.37.0; its _io/_io_public/_sdk/__init__ are byte-identical to Core's copy),
# then Core for the original pack's host imports, then the overlay for the encoder.
sys.path.insert(0, BASE)
sys.path.insert(1, "/core")
sys.path.insert(2, "/overlay")
os.environ.setdefault("HOME", "/tmp")

import comfy.cli_args  # noqa: E402  (CPU-only gate)
comfy.cli_args.args.cpu = True
import torch  # noqa: E402

USED = ["FastFilmGrain", "ColorMatchToReference", "FastUnsharpSharpen", "FastLaplacianSharpen", "VRGDG_LUTS",
        "VRGDG_MultiStringConcat"]
PACK_ID = "comfyui-vrgamedevgirl"

# Top-level modules of the sealed guest base: the 41 pins of guest_common.lock (sha256 333e9487246431a7...), the
# prepared sealed bundle's requirements.lock. The gate image has more (kornia, scipy, ...); a guest does not.
GUEST_LOCK_MODULES = {
    "av", "blake3", "comfy_api", "comfy_secure_nodes", "comfy_secure_sdk", "filelock", "fsspec", "iniconfig", "jinja2",
    "markupsafe", "mpmath", "networkx", "numpy", "nvidia", "packaging", "PIL", "pluggy", "psutil", "pygments", "pytest",
    "_pytest", "py", "pytest_asyncio", "safetensors", "setuptools", "pkg_resources", "_distutils_hack", "sympy",
    "torch", "functorch", "torchgen", "triton", "typing_extensions", "wheel",
}
GUARD = {"blocked": []}


def install_guest_import_guard():
    """Block imports executed by v2 code that a guest would not have. builtins.__import__ sees every import statement,
    including ones already in sys.modules and function-local ones, and the caller's frame tells v2 code apart from
    the original pack (/tmp/orig), Core and this test."""
    import builtins
    real_import = builtins.__import__

    def guarded(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0:
            caller = sys._getframe(1).f_code.co_filename
            if caller.startswith(V2 + "/") and not caller.startswith(V2 + "/tests/"):
                top = name.split(".")[0]
                if top not in sys.stdlib_module_names and top not in GUEST_LOCK_MODULES and top != "_vrgdg_v2":
                    GUARD["blocked"].append(f"{os.path.relpath(caller, V2)}: {name}")
                    raise ModuleNotFoundError(f"guest import guard: {name!r} is not in the guest", name=name)
        return real_import(name, globals, locals, fromlist, level)
    GUARD["code"] = guarded.__code__  # _PackScopedStubs looks past this frame to the importing file
    builtins.__import__ = guarded


def guard_negative_control():
    """The guard must block kornia, which the gate image has and the guest does not, when v2 code imports it."""
    before = len(GUARD["blocked"])
    code = compile("import kornia\n", os.path.join(V2, "_guard_probe.py"), "exec")
    try:
        exec(code, {"__name__": "_vrgdg_v2._guard_probe"})
        caught = False
    except ModuleNotFoundError:
        caught = True
    probe = GUARD["blocked"][before:]
    del GUARD["blocked"][before:]
    return caught and probe == ["_guard_probe.py: kornia"]


def load_v2():
    spec = importlib.util.spec_from_file_location("_vrgdg_v2", os.path.join(V2, "__init__.py"), submodule_search_locations=[V2])
    package = importlib.util.module_from_spec(spec)
    sys.modules["_vrgdg_v2"] = package
    spec.loader.exec_module(package)
    return package


def manifest_text(package):
    from comfy_secure_nodes.packmanifest import FORMAT, encode_schema, encode_validation_inputs
    from comfy_secure_nodes.packruntime import manifest_declaration
    nodes = {}
    for node_id, cls in package.NODE_CLASS_MAPPINGS.items():
        row = {
            "class": cls.__name__,
            "methods": {name: name in cls.__dict__ for name in ("check_lazy_status", "fingerprint_inputs", "validate_inputs")},
            "module": cls.__module__.removeprefix("_vrgdg_v2."),
            "permissions": list(cls.SDK_PERMISSIONS),
            "schema": encode_schema(copy.deepcopy(cls.GET_SCHEMA())),
            "sdk_refs": cls.SDK_REFS is True,
        }
        if "validate_inputs" in cls.__dict__:
            row["validation_inputs"] = encode_validation_inputs(cls)
        nodes[node_id] = row
    manifest = {"asset_directories": {"vrgdg_luts": "LUTS"}, "format": FORMAT, "nodes": nodes,
                "runtime": manifest_declaration(V2)}
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


# ---------------------------------------------------------------- the original pack
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

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return False


class _Inert(types.ModuleType):
    def __init__(self, name):
        super().__init__(name)
        self.__path__ = []

    def __getattr__(self, attr):
        if attr.startswith("__") and attr.endswith("__"):
            raise AttributeError(attr)
        return _InertValue(f"{self.__name__}.{attr}")


class _PackScopedStubs(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    ALLOW = {"librosa", "torchaudio", "cv2", "imageio", "demucs"}

    def __init__(self, root):
        self.root = root

    def find_spec(self, fullname, path, target=None):
        top = fullname.split(".")[0]
        if top not in self.ALLOW:
            return None
        frame = sys._getframe(1)
        while frame is not None and (frame.f_code.co_filename.startswith("<frozen importlib")
                                     or frame.f_code is GUARD.get("code")):
            frame = frame.f_back
        if frame is None or not frame.f_code.co_filename.startswith(self.root):
            return None
        return importlib.machinery.ModuleSpec(fullname, self, is_package=True)

    def create_module(self, spec):
        return _Inert(spec.name)

    def exec_module(self, module):
        return None


def load_original():
    import folder_paths
    for setter, path in (("set_output_directory", "/tmp/out"), ("set_input_directory", "/tmp/in"), ("set_temp_directory", "/tmp/temp")):
        os.makedirs(path, exist_ok=True)
        getattr(folder_paths, setter)(path)
    root = "/tmp/orig/comfyui_vrgamedevgirl_original"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns(".git", "v2", "__pycache__"))
    for name in os.listdir(os.path.join(root, "LUTS")):
        if name.lower().endswith(".cube"):
            raise SystemExit("pristine LUTS folder unexpectedly has .cube files")
    _install_prompt_server_stub()
    sys.meta_path.append(_PackScopedStubs(root))
    pspec = importlib.util.spec_from_file_location("_vrgdg_original", os.path.join(root, "__init__.py"), submodule_search_locations=[root])
    package = importlib.util.module_from_spec(pspec)
    sys.modules["_vrgdg_original"] = package
    pspec.loader.exec_module(package)
    return package, root


def _install_prompt_server_stub():
    # Same no-op server instance as generate_pack_schema_data.py's _install_prompt_server_stub.
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


# ---------------------------------------------------------------- comparison helpers
def outcome(fn):
    try:
        value = fn()
    except Exception as exc:
        return ("error", type(exc).__name__, str(exc))
    return ("value", value)


def same(a, b):
    if a[0] != b[0]:
        return False
    if a[0] == "error":
        return a[1:] == b[1:]
    x, y = a[1], b[1]
    if isinstance(x, tuple):
        x = x[0] if len(x) == 1 else x
    if isinstance(y, tuple):
        y = y[0] if len(y) == 1 else y
    if isinstance(x, torch.Tensor):
        return isinstance(y, torch.Tensor) and x.dtype == y.dtype and x.shape == y.shape and torch.equal(x, y)
    return x == y


def run_v2(cls, **kwargs):
    async def call():
        return await cls.execute(**kwargs)
    result = asyncio.run(call())
    return tuple(result.result)


def images(seed, shape, low=0.0, high=1.0):
    g = torch.Generator().manual_seed(seed)
    return (torch.rand(shape, generator=g) * (high - low) + low).to(torch.float32)


def cube_text(size, *, title=True, domain=None, crlf=False, comment=True, extra=None, rng_seed=0):
    rng = random.Random(rng_seed)
    lines = []
    if comment:
        lines.append("# fixture LUT")
    if title:
        lines.append('TITLE "fixture"')
    lines.append(f"LUT_3D_SIZE {size}")
    if domain:
        lines.append("DOMAIN_MIN {} {} {}".format(*domain[0]))
        lines.append("DOMAIN_MAX {} {} {}".format(*domain[1]))
    for b in range(size):
        for g in range(size):
            for r in range(size):
                lines.append(" ".join(f"{min(1.0, max(0.0, v + rng.uniform(-0.05, 0.05))):.6f}"
                                      for v in (r / max(1, size - 1), g / max(1, size - 1), b / max(1, size - 1))))
    if extra:
        lines.extend(extra)
    return ("\r\n" if crlf else "\n").join(lines) + "\n"


def main(argv):
    install_guest_import_guard()
    package = load_v2()
    text = manifest_text(package)
    if argv[:1] == ["generate-manifest"]:
        with open(os.path.join(RESULTS, "secure-nodes.json"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        print(f"wrote /results/secure-nodes.json ({len(package.NODE_CLASS_MAPPINGS)} nodes)")
        return 0

    original, original_root = load_original()
    O = original.NODE_CLASS_MAPPINGS
    V = package.NODE_CLASS_MAPPINGS
    used_mod = sys.modules["_vrgdg_v2._secure_used"]
    results = {name: {"cases": 0, "mismatches": [], "values": 0, "errors": {}} for name in USED}
    perturb = {"done": False}

    def record(name, label, want, got):
        results[name]["cases"] += 1
        if want[0] == "value":
            results[name]["values"] += 1
        else:
            results[name]["errors"][want[1]] = results[name]["errors"].get(want[1], 0) + 1
        if not same(want, got):
            results[name]["mismatches"].append({"case": label, "original": repr(want)[:300], "v2": repr(got)[:300]})

    # FastFilmGrain
    for shape in [(1, 32, 32, 3), (5, 16, 24, 3), (3, 17, 23, 3), (2, 8, 8, 4)]:
        for gi in (0.001, 0.04, 0.5, 1.0):
            for sm in (0.0, 0.5, 1.0):
                for bs in (0, 1, 2, 4, 500):
                    img = images(hash((shape, gi, sm, bs)) & 0xFFFF, shape)
                    torch.manual_seed(1234)
                    want = outcome(lambda: O["FastFilmGrain"]().apply_grain(img.clone(), gi, sm, bs))
                    torch.manual_seed(1234)
                    got = outcome(lambda: run_v2(V["FastFilmGrain"], images=img.clone(), grain_intensity=gi, saturation_mix=sm, batch_size=bs))
                    record("FastFilmGrain", f"{shape} gi={gi} sm={sm} bs={bs}", want, got)
    # ColorMatchToReference
    for shape, rshape in [((1, 24, 24, 3), (1, 24, 24, 3)), ((3, 16, 20, 3), (1, 32, 32, 3)), ((4, 12, 12, 3), (2, 12, 12, 3)),
                          ((2, 9, 13, 4), (1, 9, 13, 3))]:
        for ms in (0.0, 0.25, 1.0):
            for bs in (1, 2, 500):
                img, ref = images(7 + bs, shape), images(11 + bs, rshape)
                want = outcome(lambda: O["ColorMatchToReference"]().match_color(img.clone(), ref.clone(), ms, bs))
                got = outcome(lambda: run_v2(V["ColorMatchToReference"], images=img.clone(), reference_image=ref.clone(), match_strength=ms, batch_size=bs))
                record("ColorMatchToReference", f"{shape} ref={rshape} ms={ms} bs={bs}", want, got)
    # FastUnsharpSharpen / FastLaplacianSharpen
    for node, method, strengths in (("FastUnsharpSharpen", "apply_unsharp", (0.0, 0.5, 2.0, 10.0)),
                                    ("FastLaplacianSharpen", "apply_laplacian", (0.0, 0.5, 1.3, 2.0))):
        for shape in [(1, 16, 16, 3), (3, 7, 11, 3), (2, 1, 1, 3), (1, 5, 9, 4)]:
            for st in strengths:
                for gpu in (False, True):
                    for low, high in ((0.0, 1.0), (-0.2, 1.3)):
                        img = images(31 + int(st * 10), shape, low, high)
                        want = outcome(lambda: getattr(O[node](), method)(img.clone(), st, gpu))
                        got = outcome(lambda: run_v2(V[node], images=img.clone(), strength=st, use_gpu=gpu))
                        if not perturb["done"] and node == "FastUnsharpSharpen" and got[0] == "value":
                            perturb["case"] = (want, ("value", (got[1][0] + 1e-7,)))
                            perturb["done"] = True
                        record(node, f"{shape} st={st} gpu={gpu} range={low},{high}", want, got)
    # VRGDG_MultiStringConcat
    rng = random.Random(20261102)
    pool = ["", "a", "Hello", "multi\nline", "  spaced  ", "é ✓", "x" * 200, "\\n", "tab\there"]
    delimiters = ["\\n\\n", "", ", ", "\\t", "\\r\\n", "\\\\n", " | ", None]
    for case in range(400):
        count = rng.choice([1, 2, 3, 5, 10, 20, 0, 25, -3])
        delim = rng.choice(delimiters)
        strings = {f"string_{i}": rng.choice(pool + [None]) for i in range(1, 21)}
        want = outcome(lambda: O["VRGDG_MultiStringConcat"]().concat(count, delim, **strings))
        got = outcome(lambda: run_v2(V["VRGDG_MultiStringConcat"], string_count=count, delimiter=delim, **strings))
        record("VRGDG_MultiStringConcat", f"case{case} count={count} delim={delim!r}", want, got)
    # VRGDG_LUTS
    luts_dir = os.path.join(original_root, "LUTS")
    fixtures = {
        "basic.cube": cube_text(5), "crlf.CUBE": cube_text(4, crlf=True), "domain.cube": cube_text(3, domain=((0.1, 0.0, 0.0), (0.9, 1.0, 1.0))),
        "notitle.cube": cube_text(2, title=False, comment=False), "big.cube": cube_text(17, rng_seed=5),
        "bad_size.cube": "LUT_3D_SIZE 3 9\n0 0 0\n", "short.cube": cube_text(3)[:-30] + "\n",
        "nosize.cube": "0 0 0\n1 1 1\n", "one_d.cube": "LUT_1D_SIZE 4\n0 0 0\n",
        "junk.cube": cube_text(2, extra=["0.1 0.2", "garbage line here now", "0.1 0.2 0.3 0.4"]),
    }
    for name, body in fixtures.items():
        with open(os.path.join(luts_dir, name), "w", encoding="utf-8", newline="") as handle:
            handle.write(body)
    store = {name: body.encode("utf-8") for name, body in fixtures.items()}

    class FakeAssets:
        async def exists(self, kind, name):
            assert kind == "vrgdg_luts"
            return name in store

        async def resolve(self, kind, name):
            assert kind == "vrgdg_luts" and name in store
            return ("asset", name)

        async def read_bytes(self, ref):
            return store[ref[1]]

        async def digest(self, ref, algorithm="sha256"):
            import hashlib
            return hashlib.sha256(store[ref[1]]).hexdigest()

    class FakeImageRef:
        def __init__(self, value):
            self.value = value

        async def raw(self):
            return self.value

    async def from_value(value):
        return value
    used_mod.sdk = types.SimpleNamespace(ctx=lambda: types.SimpleNamespace(assets=FakeAssets()),
                                         ImageRef=types.SimpleNamespace(from_value=from_value))

    def lut_message(result, name):
        if result[0] == "error":
            return ("error", result[1], result[2].replace(os.path.join(luts_dir, name), name).replace(luts_dir, "LUTS"))
        return result
    lut_names = sorted(fixtures) + ["No LUT files found"]
    for name in lut_names:
        for device in ("auto", "cpu", "cuda"):
            for strength in (0.0, 2.5, 10.0, 11.0, -1.0):
                for shape in [(1, 12, 12, 3), (2, 6, 9, 4)]:
                    img = images(53, shape)
                    want = lut_message(outcome(lambda: O["VRGDG_LUTS"]().apply_lut(img.clone(), name, device, strength)), name)
                    got = outcome(lambda: run_v2(V["VRGDG_LUTS"], image=FakeImageRef(img.clone()), lut_name=name, device=device, strength=strength))
                    record("VRGDG_LUTS", f"{name} device={device} strength={strength} {shape}", want, got)
    lut_validation = {
        "present": asyncio.run(V["VRGDG_LUTS"].validate_inputs(lut_name="basic.cube")),
        "sentinel": asyncio.run(V["VRGDG_LUTS"].validate_inputs(lut_name="No LUT files found")),
        "missing": asyncio.run(V["VRGDG_LUTS"].validate_inputs(lut_name="Kodak.cube")),
    }
    lut_validation_ok = lut_validation["present"] is True and lut_validation["sentinel"] is True and \
        lut_validation["missing"] == ("comfyui-vrgamedevgirl/VRGDG_LUTS: LUT 'Kodak.cube' is not in the host's vrgdg_luts asset "
                                      "folder (the original read it from the pack's own LUTS folder)")

    # S: refusal stubs and schema round trips
    from comfy_secure_nodes.packmanifest import encode_schema
    frozen = json.load(open(os.path.join(V2, "_frozen_schemas.json"), encoding="utf-8"))
    roundtrip_bad = [n for n, cls in V.items() if encode_schema(copy.deepcopy(cls.GET_SCHEMA())) != frozen[n]]
    stub_bad = []
    unconverted = sys.modules["_vrgdg_v2._secure_unconverted"]
    for node_id, cls in unconverted.NODE_CLASS_MAPPINGS.items():
        message = f"{PACK_ID}/{node_id} is not yet converted to Secure Nodes V2"
        params = [i.id for i in cls.GET_SCHEMA().inputs]
        try:
            answer = cls.validate_inputs(**{p: None for p in params})
        except TypeError:
            answer = cls.validate_inputs()
        try:
            asyncio.run(cls.execute())
            raised = None
        except unconverted.NotConvertedError as exc:
            raised = str(exc)
        if answer != message or raised != message:
            stub_bad.append(node_id)
    registered = set(V)
    frozen_ids = set(frozen)
    # Original schema check for the used nodes: v2 inputs equal the original INPUT_TYPES names, in order.
    order_bad = []
    for node_id in USED:
        declared = O[node_id].INPUT_TYPES()
        names = list(declared.get("required", {})) + list(declared.get("optional", {}))
        if [i.id for i in V[node_id].GET_SCHEMA().inputs] != names:
            order_bad.append(node_id)

    with open(os.path.join(V2, "secure-nodes.json"), encoding="utf-8") as handle:
        manifest_equal = handle.read() == text
    negative_red = perturb.get("done") and not same(*perturb["case"])
    nodes = {}
    for name in USED:
        r = results[name]
        nodes[name] = {"verdict": "EXACT" if r["cases"] and not r["mismatches"] else "MISMATCH", "cases": r["cases"],
                       "mismatches": len(r["mismatches"]), "original_values": r["values"], "original_errors": r["errors"]}
    nodes["VRGDG_LUTS"]["validation"] = {"ok": lut_validation_ok, **{k: v if v is True else str(v) for k, v in lut_validation.items()}}
    if not lut_validation_ok:
        nodes["VRGDG_LUTS"]["verdict"] = "MISMATCH"
    unconverted_ids = sorted(unconverted.NODE_CLASS_MAPPINGS)
    guard_red = guard_negative_control()
    ok = all(v["verdict"] == "EXACT" for v in nodes.values()) and not stub_bad and not roundtrip_bad and manifest_equal \
        and registered == frozen_ids and not order_bad and not GUARD["blocked"] and guard_red
    parity = {
        "pack": PACK_ID, "pin": "5f2882d835bfa616feed7b73ab102775ab8de64d",
        "status": "PASS" if ok else "FAIL",
        "nodes": nodes,
        "unconverted": {"verdict": "REFUSED-AS-DESIGNED" if not stub_bad else "MISMATCH", "count": len(unconverted_ids),
                        "bad": stub_bad, "ids": unconverted_ids},
        "schema_roundtrip_mismatches": roundtrip_bad,
        "used_input_order_mismatches": order_bad,
        "registered_equals_frozen": registered == frozen_ids,
        "manifest_equals_real_encoder": manifest_equal,
        "negative_control": {"perturbation": "FastUnsharpSharpen output + 1e-7 for one case", "turned_red": bool(negative_red)},
        "guest_import_guard": {"base": "guest_common.lock (41 pins)", "blocked": GUARD["blocked"],
                               "negative_control_kornia_blocked": guard_red},
        "environment": {"guest_sdk_base": BASE, "original_kornia": importlib.import_module("kornia").__version__, "torch": torch.__version__},
    }
    with open(os.path.join(RESULTS, "parity.json"), "w", encoding="utf-8") as handle:
        json.dump(parity, handle, indent=1, sort_keys=True)
        handle.write("\n")
    with open(os.path.join(RESULTS, "mismatches.json"), "w", encoding="utf-8") as handle:
        json.dump({k: v["mismatches"][:20] for k, v in results.items()}, handle, indent=1, sort_keys=True)
        handle.write("\n")
    summary = {k: parity[k] for k in ("status", "nodes", "schema_roundtrip_mismatches", "manifest_equals_real_encoder",
                                      "registered_equals_frozen", "negative_control", "guest_import_guard")}
    summary["unconverted"] = {k: parity["unconverted"][k] for k in ("verdict", "count", "bad")}
    print(json.dumps(summary, indent=1))
    return 0 if ok and negative_red else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
