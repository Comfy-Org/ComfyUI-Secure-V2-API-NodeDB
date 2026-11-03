"""comfyui-dynamicprompts to-50% conversion (pin 3f2fff32358c): tier-1 parity in the lane gate.

DEPS=<the unpacked dynamicprompts 0.30.2, pyparsing 3.3.3 and pyyaml 6.0.3 wheels> \
run_in_gate.sh <pack root with v2/> <v2/tests> <results> test_dynamicprompts_parity.py [generate-manifest]

  generate-manifest  write /results/secure-nodes.json from the v2 classes with the real encoder
                     (comfy_secure_nodes.packmanifest, /overlay).
  (default)          parity:
    R  runs. A scenario is a sequence of node runs (node type, node id, inputs) over a synthetic
       wildcard folder. The original and v2 sides each run every scenario in their own subprocess,
       and seed the library's shared DEFAULT_RANDOM and Python's random module with the same values
       at the start of each scenario.
         original  the pristine pack (a /tmp copy) under Core. folder_paths.base_path is a folder whose
                   wildcards/ holds the fixtures. There is one instance per (node id, node type), as
                   Core's object cache keeps them, and each run calls FUNCTION with the inputs as
                   keywords.
         v2        the v2 classes with a fake SDK context. graph.current_node_id answers the run's node
                   id. assets lists the same fixture folder with Core's folder_paths.get_filename_list,
                   as the host lists an asset kind, and reads the same bytes.
       Outcomes compare as returned strings, or as exception type and message.
    F  fingerprint_inputs equals the original IS_CHANGED (NaN equals NaN).
    D  designed differences. DPMagicPrompt and DPFeelingLucky refuse by name. With no wildcard asset
       kind, a run that samples a wildcard raises WildcardsUnavailableError, and every other run still
       equals the original's run over an empty wildcard folder.
    W  _walk_order on a crafted listing.
    S  object_info of all six nodes: Core's own V1 node_info (server.py) for the originals, against the
       v2 classes, after the representational normalization in canon_spec / info_diff.
    M  v2/secure-nodes.json equals the real encoder's output for the v2 classes.
    N  negative control: one perturbed v2 outcome must be caught.
"""
import ast
import asyncio
import copy
import glob
import importlib.util
import json
import math
import os
import random
import shutil
import signal
import subprocess
import sys
import textwrap
import types
import warnings

sys.dont_write_bytecode = True
warnings.simplefilter("ignore")
PACK = "/pack"
V2 = "/pack/v2"
RESULTS = "/results"
DEPS = "/deps"
BASE = glob.glob("/bases/0cd9adec*/common-site-packages")[0]
# The pinned dependency wheels first, then the guest SDK (comfy_api 0.37.0), then Core for the original
# pack's host imports and the harness, then the overlay for the encoder.
for _index, _path in enumerate((DEPS, BASE, "/core", "/overlay")):
    sys.path.insert(_index, _path)
os.environ.setdefault("HOME", "/tmp")

PACK_ID = "comfyui-dynamicprompts"
PIN = "3f2fff32358cf39e21b8b440ca87eac9a8e2bade"
KIND = "dynamicprompts_wildcards"
LIST_MAX = 4096  # the host's assets.list limit (transport/host.py ASSET_LIST_MAX)
SAMPLERS = ("DPRandomGenerator", "DPCombinatorialGenerator")

# ---------------------------------------------------------------- synthetic fixtures
FIXTURES = {
    "empty": {},
    "full": {
        "colors.txt": b"red\ngreen\nblue\n# a comment\n\n  yellow  \n",
        "animals/mammals.txt": b"cat\ndog\nhorse\ncat\n",
        "animals/birds.txt": b"crow\r\nrobin\r\nowl\r\n",
        "animals/sea/fish.txt": b"cod\ntuna\n",
        "styles/painters.txt": b"{monet|manet}\n__colors__ abstract\n",
        "chain.txt": b"__animals/mammals__ and __colors__\n",
        "weights.json": json.dumps({
            "weighted": ["2::heavy", "1::light", "0.5::feather", "plain", "x::bad"],
            "nested": {"deep": ["x", "y"]},
            "objs": [{"text": "alpha", "weight": 3}, {"content": "beta"}, {"text": ""}, 7],
        }).encode(),
        "pantry/stuff.yaml": b"fruit:\n  - apple\n  - 3::banana\nveg:\n  green:\n    - kale\n    - pea\n",
        "flat.json": b'["one", "two", 3, "three"]',
        "latin1.txt": b"caf\xe9\nna\xefve\nplain\n",
        "latin1.json": b'["caf\xe9"]',
        "unicode.txt": "café\nnaïve\n日本\n".encode(),
        "bom.txt": b"\xef\xbb\xbfbom1\nbom2\n",
        "cr.txt": b"m1\rm2\rm3",
        "empty.txt": b"",
        "bad.json": b"{not json",
        "bad.yaml": b"a: [unclosed\n",
        ".hidden/secret.txt": b"nope\n",
        ".dotfile.txt": b"dotvalue\n",
        "readme.md": b"ignored\n",
        "UPPER.TXT": b"ignored\n",
        "deep/a/b/c/leaf.txt": b"leaf1\nleaf2\n",
        "glob/one.txt": b"g1\n",
        "glob/two.txt": b"g2\n",
        "spaces in name.txt": b"s1\ns2\n",
    },
}

TEMPLATES = [
    "a photo of a cat",
    "{red|green|blue} {cat|dog}",
    "{0.1::rare|0.9::common|plain}",
    "{2$$a|b|c|d}",
    "{1-3$$ and $$a|b|c|d}",
    "{3$$a|b}",
    "{0$$a|b}",
    "{a {x|y}|b {p|q|r}}",
    "{@one|two|three}",
    "{~one|two|three} fixed",
    "a {b|} c",
    "unicode {ü|ö} 日本",
    "${animal={cat|dog|bird}} ${animal} and ${animal}",
    "${animal=!{cat|dog|bird}} ${animal} and ${animal}",
    "__colors__",
    "__animals/*__",
    "__animals/mammals__ with __animals/birds__",
    "__animals/sea/fish__ {x|y}",
    "__styles/painters__",
    "__chain__",
    "__weighted__",
    "__nested/deep__ __objs__",
    "__pantry/fruit__ __pantry/veg/green__",
    "__flat__ __bad__ __UPPER__ __readme__",
    "__latin1__ __unicode__",
    "__bom__ __cr__",
    "__empty__ __missing__",
    "__leaf__",
    "__glob/*__",
    "__secret__ __.dotfile__",
    "__spaces in name__",
    "{2$$__colors__}",
    "{2$$ and $$__animals/*__}",
    "{a|__colors__}",
    "",
    "   ",
    "{a|b",
    "{a|b}}",
]

JINJA = [
    "{{ 1 + 2 }}",
    "{% for x in ['a', 'b'] %}{{ x }} {% endfor %}",
    "{{ choice('a', 'b', 'c') }} {{ choice('x', 'y') }}",
    "{{ weighted_choice(('a', 1), ('b', 3)) }}",
    "{{ random() }}",
    "{{ randint(1, 100) }}",
    "{{ permutations(['a', 'b', 'c'], 2) }}",
    "{{ permutations(['a', 'b', 'c'], 1, 2) }}",
    "{{ all_combinations('{a|b} {c|d}') }}",
    "{{ wildcard('colors') }}",
    "{% prompt %}first {{ choice('p', 'q') }}{% endprompt %}{% prompt %}second{% endprompt %}",
    "{{ missing_var }}",
    "{{ x",
    "{% for %}",
    "plain text",
    "",
    "{{ random_sample('{only}') }}",
    "{{ 'x' * 3 }}",
    "{% set v = choice('m', 'n') %}{{ v }}{{ v }}",
]


def run(node_type, node_id, **inputs):
    return [node_type, node_id, inputs]


def scenarios():
    out = []

    def add(name, steps, fixtures="full", kind=True, designed=None):
        out.append({"name": name, "fixtures": fixtures, "kind": kind, "designed": designed,
                    "rng": 1000 + len(out), "steps": steps})

    seeds = [5, 5, 0, 7, 0, 123456789012, -3]
    for node_type in SAMPLERS:
        for index, text in enumerate(TEMPLATES):
            add(f"{node_type} seeded t{index}", [run(node_type, "7", text=text, seed=s, autorefresh="No") for s in seeds])
            add(f"{node_type} unseeded t{index}", [run(node_type, "7", text=text, seed=0, autorefresh="Yes") for _ in range(8)])
            if "__" in text:
                add(f"{node_type} empty folder t{index}", [run(node_type, "7", text=text, seed=s, autorefresh="No") for s in seeds[:4]],
                    fixtures="empty")
        # quirks of the original, kept as they are
        add(f"{node_type} parse error after a template", [run(node_type, "3", text=t, seed=s, autorefresh="No") for t, s in
                                                         (("{a|b|c}", 0), ("{a|b", 0), ("{a|b", 4), ("{c|d}", 0), ("{c|d}", 0))])
        add(f"{node_type} parse error first", [run(node_type, "3", text="{a|b", seed=s, autorefresh="No") for s in (0, 2, 0)])
        add(f"{node_type} empty text between", [run(node_type, "3", text=t, seed=0, autorefresh="No") for t in
                                                ("{a|b|c}", "", "   ", "{a|b|c}", "{a|b|c}")])
        add(f"{node_type} text changes", [run(node_type, "3", text=t, seed=0, autorefresh="No") for t in
                                          ["{a|b|c} __colors__"] * 3 + ["{x|y} {1|2}"] * 3 + ["{a|b|c} __colors__"] * 2])
        add(f"{node_type} exhaustion", [run(node_type, "3", text="{a|b|c}", seed=0, autorefresh="No") for _ in range(7)])
    add("combinatorial long", [run("DPCombinatorialGenerator", "8", text="{a|b|c} {1|2|3|4} {x|y|z|w|v}", seed=0,
                                   autorefresh="No") for _ in range(70)])
    steps = []
    for k in range(6):
        steps.append(run("DPRandomGenerator", "1", text="{red|green|blue} __colors__ {@x|y|z}", seed=11, autorefresh="No"))
        steps.append(run("DPRandomGenerator", "2", text="{red|green|blue} __colors__ {@x|y|z}", seed=0, autorefresh="No"))
        steps.append(run("DPCombinatorialGenerator", "3", text="{a|b|c} __animals/mammals__ {~p|q}", seed=0, autorefresh="No"))
        steps.append(run("DPJinja", "4", text="{{ choice('a', 'b', 'c') }}", autorefresh="No"))
    add("interleaved nodes share the library RNG", steps)
    add("one node id, two node types", [run(t, "5", text="{a|b|c|d} {x|y}", seed=s, autorefresh="No")
                                        for t, s in [(SAMPLERS[0], 0), (SAMPLERS[1], 0)] * 4])
    for index, text in enumerate(JINJA):
        add(f"DPJinja j{index}", [run("DPJinja", "9", text=text, autorefresh=a) for a in ("No", "Yes", "No")])
    add("DPOutput", [run("DPOutput", "6", text=t) for t in ("hello", "")])
    # D: no wildcard asset kind on the host. The original's closest state is an empty wildcard folder.
    for node_type in SAMPLERS:
        for index, text in enumerate(TEMPLATES):
            add(f"{node_type} no kind t{index}", [run(node_type, "7", text=text, seed=s, autorefresh="No") for s in seeds[:4]],
                fixtures="empty", kind=False, designed="wildcards-unavailable")
    return out


FINGERPRINT_CASES = [
    run(SAMPLERS[0], "1", text="x", seed=1, autorefresh="No"),
    run(SAMPLERS[0], "1", text="", seed=0, autorefresh="Yes"),
    run(SAMPLERS[1], "1", text="{a|b}", seed=3, autorefresh="No"),
    run("DPJinja", "1", text="{{ 1 }}", autorefresh="Yes"),
    run("DPJinja", "1", text="{{ 1 }}", autorefresh="No"),
]


# ---------------------------------------------------------------- helpers
STEP_SECONDS = 5


class StepTimeout(BaseException):
    """A run that has not returned after STEP_SECONDS. A BaseException, so that no `except Exception`
    inside the library can swallow it and keep looping."""


def _alarm(_signum, _frame):
    raise StepTimeout(f"no result within {STEP_SECONDS} s")


def outcome(fn):
    signal.alarm(STEP_SECONDS)
    try:
        value = fn()
    except StepTimeout as exc:
        return ["timeout", type(exc).__name__, str(exc)]
    except Exception as exc:
        return ["error", type(exc).__name__, str(exc)]
    finally:
        signal.alarm(0)
    return ["value", [v if isinstance(v, (str, int, float, bool, type(None))) else repr(v) for v in value]]


def same(a, b):
    return a == b


def json_safe(value):
    if isinstance(value, float) and math.isnan(value):
        return "NaN"
    return value


def write_folder(root, files):
    os.makedirs(root, exist_ok=True)
    for name, data in files.items():
        path = os.path.join(root, *name.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(data)
    return root


def core_node_info(mappings, display):
    """Core's own node_info (server.py), run for the given mappings."""
    from comfy_api.internal import _ComfyNodeInternal

    source = open("/core/server.py", encoding="utf-8").read()
    lines = source.splitlines(keepends=True)
    found = [n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == "node_info"]
    assert len(found) == 1, "server.py must define one node_info"
    segment = textwrap.dedent("".join(lines[found[0].lineno - 1:found[0].end_lineno]))
    namespace = {"nodes": types.SimpleNamespace(NODE_CLASS_MAPPINGS=mappings, NODE_DISPLAY_NAME_MAPPINGS=display),
                 "_ComfyNodeInternal": _ComfyNodeInternal}
    exec(compile(segment, f"/core/server.py:{found[0].lineno}", "exec"), namespace)
    return {name: json.loads(json.dumps(namespace["node_info"](name), default=list)) for name in mappings}, \
        f"server.py L{found[0].lineno}-{found[0].end_lineno}"


def side_setup():
    import comfy.cli_args
    comfy.cli_args.args.cpu = True
    import folder_paths
    return folder_paths


# ---------------------------------------------------------------- one side, in its own process
def run_side(side, scenario_path, out_path):
    signal.signal(signal.SIGALRM, _alarm)
    folder_paths = side_setup()
    from dynamicprompts.constants import DEFAULT_RANDOM

    plan = json.load(open(scenario_path, encoding="utf-8"))
    folders = {name: write_folder(f"/tmp/{side}-fixtures/{name}/wildcards", files_) for name, files_ in
               {k: v for k, v in FIXTURES.items()}.items()}
    record = {"side": side, "scenarios": [], "fingerprints": [], "extra": {}}
    if side == "original":
        root = "/tmp/orig/comfyui_dynamicprompts_original"
        shutil.copytree(PACK, root, ignore=shutil.ignore_patterns(".git", "v2", "__pycache__"))
        spec = importlib.util.spec_from_file_location("_dp_original", os.path.join(root, "__init__.py"),
                                                      submodule_search_locations=[root])
        package = importlib.util.module_from_spec(spec)
        sys.modules["_dp_original"] = package
        spec.loader.exec_module(package)
        classes = package.NODE_CLASS_MAPPINGS
        for scenario in plan:
            folder_paths.base_path = os.path.dirname(folders[scenario["fixtures"]])
            DEFAULT_RANDOM.seed(scenario["rng"])
            random.seed(scenario["rng"] + 1)
            instances = {}
            results = []
            for node_type, node_id, inputs in scenario["steps"]:
                def call():
                    key = (node_id, node_type)
                    if key not in instances:
                        instances[key] = classes[node_type]()
                    obj = instances[key]
                    return getattr(obj, obj.FUNCTION)(**inputs)
                results.append(outcome(call))
            record["scenarios"].append(results)
        for node_type, _node_id, inputs in FINGERPRINT_CASES:
            record["fingerprints"].append(json_safe(classes[node_type].IS_CHANGED(**inputs)))
        record["extra"]["node_info"], record["extra"]["node_info_source"] = core_node_info(classes, package.NODE_DISPLAY_NAME_MAPPINGS)
        record["extra"]["has_fingerprint"] = {k: hasattr(v, "IS_CHANGED") for k, v in classes.items()}
    else:
        spec = importlib.util.spec_from_file_location("_dp_v2", os.path.join(V2, "__init__.py"), submodule_search_locations=[V2])
        package = importlib.util.module_from_spec(spec)
        sys.modules["_dp_v2"] = package
        spec.loader.exec_module(package)
        secure = sys.modules["_dp_v2._secure_dp"]
        classes = package.NODE_CLASS_MAPPINGS

        class FakeGraph:
            node_id = None

            async def current_node_id(self):
                return self.node_id

        class FakeAssets:
            async def list(self, folder, prefix="", recursive=True):
                assert folder == KIND and prefix == "" and recursive is True
                # As the in-process SDK's AssetsDomain.list does for a catalogue folder (_sdk.py).
                names = sorted(str(name).replace("\\", "/") for name in folder_paths.get_filename_list(folder))
                if len(names) > LIST_MAX:
                    raise ValueError(f"asset catalogue exceeds {LIST_MAX} names")
                return names

            async def resolve(self, folder, name):
                assert folder == KIND
                for base in folder_paths.get_folder_paths(folder):
                    path = os.path.join(base, name)
                    if os.path.isfile(path):
                        return ("asset", path)
                raise FileNotFoundError(f"no {folder} asset named {name!r}")

            async def read_bytes(self, ref):
                with open(ref[1], "rb") as handle:
                    return handle.read()

        context = types.SimpleNamespace(graph=FakeGraph(), assets=FakeAssets())
        secure.sdk = types.SimpleNamespace(ctx=lambda: context)
        for scenario in plan:
            folder_paths.filename_list_cache.clear()
            if scenario["kind"]:
                folder_paths.folder_names_and_paths[KIND] = ([folders[scenario["fixtures"]]], set())
            else:
                folder_paths.folder_names_and_paths.pop(KIND, None)
            secure._INSTANCES.clear()
            secure._SHARED_FOLDER.update(key=None, manager=None)
            DEFAULT_RANDOM.seed(scenario["rng"])
            random.seed(scenario["rng"] + 1)
            results = []
            for node_type, node_id, inputs in scenario["steps"]:
                def call():
                    context.graph.node_id = node_id
                    return asyncio.run(classes[node_type].execute(**inputs)).result
                results.append(outcome(call))
            record["scenarios"].append(results)
        for node_type, _node_id, inputs in FINGERPRINT_CASES:
            record["fingerprints"].append(json_safe(classes[node_type].fingerprint_inputs(**inputs)))
        record["extra"]["node_info"], record["extra"]["node_info_source"] = core_node_info(classes, package.NODE_DISPLAY_NAME_MAPPINGS)
        record["extra"]["has_fingerprint"] = {k: "fingerprint_inputs" in v.__dict__ for k, v in classes.items()}
        refusals = {}
        for node_id, expected in (("DPMagicPrompt", secure.MAGIC_PROMPT_REFUSAL), ("DPFeelingLucky", secure.FEELING_LUCKY_REFUSAL)):
            cls = classes[node_id]
            refusals[node_id] = {
                "validate_inputs": cls.validate_inputs(text="x", seed=1, autorefresh="No"),
                "execute": outcome(lambda: asyncio.run(cls.execute(text="x", seed=1, autorefresh="No"))),
                "expected": expected,
            }
        record["extra"]["refusals"] = refusals
        listing = ["b.txt", "a/z.txt", "a.txt", ".h/x.txt", "c.md", "a/.d/y.txt", "B.TXT", "a/b/c.json", "a/m.yaml",
                   ".t.txt", "z/.txt"]
        record["extra"]["walk_order"] = {"listing": listing, "got": secure._walk_order(listing),
                                         "expected": [".t.txt", "a.txt", "b.txt", "a/m.yaml", "a/z.txt", "a/b/c.json"]}
    import dynamicprompts
    import jinja2
    import pyparsing
    import yaml
    record["extra"]["environment"] = {
        "python": sys.version.split()[0],
        "dynamicprompts": [importlib.metadata.version("dynamicprompts"), dynamicprompts.__file__],
        "pyparsing": [pyparsing.__version__, pyparsing.__file__],
        "pyyaml": [yaml.__version__, yaml.__file__],
        "jinja2": [jinja2.__version__, jinja2.__file__],
    }
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False)
    return 0


# ---------------------------------------------------------------- comparisons in the parent
def canon_spec(spec):
    """A V1 list-of-options combo and a V3 COMBO with "options" are the same frontend input, and
    multiselect False is the V3 default."""
    kind = spec[0]
    options = dict(spec[1]) if len(spec) > 1 else {}
    if isinstance(kind, list):
        options["options"] = kind
        kind = "COMBO"
    if kind == "COMBO" and options.get("multiselect") is False:
        del options["multiselect"]
    return [kind, options]


MISSING = "<missing>"


def defaultish(value):
    return value in (MISSING, None, False, [], "") or (isinstance(value, list) and all(v is None for v in value))


V3_OUTPUT_HIDDEN = {"prompt": ["PROMPT"], "extra_pnginfo": ["EXTRA_PNGINFO"]}


def info_diff(v1, v3):
    """Differences between the original's and v2's object_info. Returns (allowed, substantive)."""
    allowed, substantive = {}, {}
    v1, v3 = copy.deepcopy(v1), copy.deepcopy(v3)
    if v3.get("output_node") and v3.get("input", {}).get("hidden") == V3_OUTPUT_HIDDEN and "hidden" not in v1.get("input", {}):
        # V3 gives every output node these two hidden inputs (no widget, filled by Core).
        del v3["input"]["hidden"]
        v3.get("input_order", {}).pop("hidden", None)
        allowed["hidden"] = "V3 adds hidden prompt and extra_pnginfo to output nodes"
    for key in sorted(set(v1) | set(v3)):
        a, b = v1.get(key, MISSING), v3.get(key, MISSING)
        if key == "input":
            ca = {s: {n: canon_spec(x) for n, x in a.get(s, {}).items()} for s in ("required", "optional", "hidden")}
            cb = {s: {n: canon_spec(x) for n, x in b.get(s, {}).items()} for s in ("required", "optional", "hidden")}
            if ca != cb:
                substantive[key] = [a, b]
            elif a != b:
                allowed[key] = "list-of-options combo vs COMBO with options (same input)"
            continue
        if a == b:
            continue
        if key == "python_module":
            allowed[key] = [a, b]
        elif defaultish(a) and defaultish(b):
            allowed[key] = [a, b]
        else:
            substantive[key] = [a, b]
    return allowed, substantive


def manifest_text(package):
    from comfy_secure_nodes.packmanifest import FORMAT, encode_schema, encode_validation_inputs
    from comfy_secure_nodes.packruntime import manifest_declaration
    nodes = {}
    for node_id, cls in package.NODE_CLASS_MAPPINGS.items():
        row = {
            "class": cls.__name__,
            "methods": {name: name in cls.__dict__ for name in ("check_lazy_status", "fingerprint_inputs", "validate_inputs")},
            "module": cls.__module__.removeprefix("_dp_v2."),
            "permissions": list(cls.SDK_PERMISSIONS),
            "schema": encode_schema(copy.deepcopy(cls.GET_SCHEMA())),
            "sdk_refs": cls.SDK_REFS is True,
        }
        if "validate_inputs" in cls.__dict__:
            row["validation_inputs"] = encode_validation_inputs(cls)
        nodes[node_id] = row
    manifest = {"format": FORMAT, "nodes": nodes, "runtime": manifest_declaration(V2)}
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def load_v2_here():
    side_setup()
    spec = importlib.util.spec_from_file_location("_dp_v2", os.path.join(V2, "__init__.py"), submodule_search_locations=[V2])
    package = importlib.util.module_from_spec(spec)
    sys.modules["_dp_v2"] = package
    spec.loader.exec_module(package)
    return package


def main(argv):
    if argv[:1] == ["side"]:
        return run_side(*argv[1:4])
    package = load_v2_here()
    text = manifest_text(package)
    if argv[:1] == ["generate-manifest"]:
        with open(os.path.join(RESULTS, "secure-nodes.json"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        print(f"wrote {RESULTS}/secure-nodes.json ({len(package.NODE_CLASS_MAPPINGS)} nodes)")
        return 0

    plan = scenarios()
    with open("/tmp/scenarios.json", "w", encoding="utf-8") as handle:
        json.dump(plan, handle, ensure_ascii=False)
    sides = {}
    for side in ("original", "v2"):
        out = f"/tmp/out-{side}.json"
        with open(os.path.join(RESULTS, f"side-{side}.log"), "w", encoding="utf-8") as log:
            proc = subprocess.run([sys.executable, "-I", "-B", os.path.abspath(__file__), "side", side, "/tmp/scenarios.json", out],
                                  stdout=log, stderr=subprocess.STDOUT, timeout=1800)
        if proc.returncode != 0:
            print(f"side {side} failed with {proc.returncode}; see side-{side}.log")
            return 1
        sides[side] = json.load(open(out, encoding="utf-8"))
        shutil.copyfile(out, os.path.join(RESULTS, f"outcomes-{side}.json"))
    original, v2 = sides["original"], sides["v2"]

    by_node = {}
    hangs = set()
    mismatches = []
    designed = {"wildcards-unavailable": {"steps": 0, "refused": 0, "equal": 0, "bad": 0, "original_hangs": 0}}
    expected_unavailable = {t: f"{PACK_ID}/{t}: this template samples a wildcard, but the host's {KIND} asset kind cannot be "
                               f"listed (KeyError: '{KIND}'). The original read wildcard files from the host file system, "
                               "which a Secure Nodes V2 guest cannot do." for t in SAMPLERS}
    for scenario, want_steps, got_steps in zip(plan, original["scenarios"], v2["scenarios"]):
        for index, ((node_type, node_id, inputs), want, got) in enumerate(zip(scenario["steps"], want_steps, got_steps)):
            if scenario["designed"] == "wildcards-unavailable":
                d = designed["wildcards-unavailable"]
                d["steps"] += 1
                if want[0] == "timeout":
                    # The library loops forever on this run over an empty folder (it does the same in the
                    # empty-folder scenarios above, on both sides); v2 refused earlier, so the states differ.
                    d["original_hangs"] += 1
                elif same(want, got):
                    d["equal"] += 1
                elif got == ["error", "WildcardsUnavailableError", expected_unavailable[node_type]] and "__" in inputs["text"]:
                    d["refused"] += 1
                else:
                    d["bad"] += 1
                    mismatches.append({"scenario": scenario["name"], "step": index, "inputs": inputs, "original": want, "v2": got})
                continue
            r = by_node.setdefault(node_type, {"cases": 0, "mismatches": 0, "values": 0, "errors": 0, "timeouts": 0})
            r["cases"] += 1
            r[{"value": "values", "error": "errors", "timeout": "timeouts"}[want[0]]] += 1
            if want[0] == "timeout" and same(want, got):
                hangs.add((node_type, inputs.get("text"), scenario["fixtures"]))
            if not same(want, got):
                r["mismatches"] += 1
                mismatches.append({"scenario": scenario["name"], "step": index, "inputs": inputs, "original": want, "v2": got})

    fingerprints_ok = original["fingerprints"] == v2["fingerprints"]
    has_fp = {k: [original["extra"]["has_fingerprint"][k], v2["extra"]["has_fingerprint"][k]] for k in package.NODE_CLASS_MAPPINGS}
    refusals = v2["extra"]["refusals"]
    refusals_ok = all(r["validate_inputs"] == r["expected"] and r["execute"] == ["error", "NotConvertedError", r["expected"]]
                      for r in refusals.values())
    walk = v2["extra"]["walk_order"]
    walk_ok = walk["got"] == walk["expected"]
    schema = {}
    for node_id in package.NODE_CLASS_MAPPINGS:
        allowed, substantive = info_diff(original["extra"]["node_info"][node_id], v2["extra"]["node_info"][node_id])
        schema[node_id] = {"equal_after_normalization": not substantive, "allowed": allowed, "substantive": substantive}
    schema_ok = all(s["equal_after_normalization"] for s in schema.values())
    with open(os.path.join(V2, "secure-nodes.json"), encoding="utf-8") as handle:
        manifest_equal = handle.read() == text

    probe = next((m for m in [(s, w, g) for s, ws, gs in zip(plan, original["scenarios"], v2["scenarios"])
                              if not s["designed"] for w, g in zip(ws, gs) if w[0] == "value" and w == g]), None)
    perturbed = copy.deepcopy(probe[2])
    perturbed[1][0] = perturbed[1][0] + " "
    negative_red = not same(probe[1], perturbed)

    nodes = {}
    for node_type in ("DPRandomGenerator", "DPCombinatorialGenerator", "DPJinja", "DPOutput"):
        r = by_node.get(node_type, {"cases": 0, "mismatches": 0, "values": 0, "errors": 0, "timeouts": 0})
        nodes[node_type] = {"verdict": "EXACT" if r["cases"] and not r["mismatches"] else "MISMATCH", **r}
    for node_type in ("DPMagicPrompt", "DPFeelingLucky"):
        nodes[node_type] = {"verdict": "REFUSED-AS-DESIGNED" if refusals_ok else "MISMATCH", **refusals[node_type]}
    d = designed["wildcards-unavailable"]
    designed_ok = d["bad"] == 0 and d["refused"] > 0 and d["equal"] > 0
    ok = all(n["verdict"] in ("EXACT", "REFUSED-AS-DESIGNED") for n in nodes.values()) and fingerprints_ok and walk_ok \
        and schema_ok and manifest_equal and designed_ok
    parity = {
        "pack": PACK_ID, "pin": PIN, "status": "PASS" if ok else "FAIL",
        "nodes": nodes,
        "scenarios": len(plan),
        "runs_that_hang_in_both": [{"node": n, "text": t, "fixtures": f} for n, t, f in sorted(hangs)],
        "fingerprints":{"equal": fingerprints_ok, "original": original["fingerprints"], "v2": v2["fingerprints"],
                         "declared": has_fp},
        "designed_differences": {"wildcards_unavailable": {**d, "ok": designed_ok}},
        "walk_order": {**walk, "ok": walk_ok},
        "object_info": {"core_node_info": original["extra"]["node_info_source"], "nodes": schema, "ok": schema_ok},
        "manifest_equals_real_encoder": manifest_equal,
        "negative_control": {"perturbation": "one v2 value with a trailing space", "turned_red": negative_red},
        "environment": {"original": original["extra"]["environment"], "v2": v2["extra"]["environment"],
                        "guest_sdk_base": BASE},
    }
    with open(os.path.join(RESULTS, "parity.json"), "w", encoding="utf-8") as handle:
        json.dump(parity, handle, indent=1, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
    with open(os.path.join(RESULTS, "mismatches.json"), "w", encoding="utf-8") as handle:
        json.dump(mismatches[:200], handle, indent=1, ensure_ascii=False)
        handle.write("\n")
    summary = {k: parity[k] for k in ("status", "scenarios", "manifest_equals_real_encoder", "negative_control")}
    summary["nodes"] = {k: {x: v[x] for x in ("verdict", "cases", "mismatches") if x in v} for k, v in nodes.items()}
    summary["fingerprints_equal"] = fingerprints_ok
    summary["designed"] = parity["designed_differences"]
    summary["walk_order_ok"] = walk_ok
    summary["object_info_ok"] = schema_ok
    summary["mismatch_count"] = len(mismatches)
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    return 0 if ok and negative_red else 1


if __name__ == "__main__":
    import importlib.metadata  # noqa: F401  (used by run_side)
    sys.exit(main(sys.argv[1:]))
