"""Global Seed (Inspire) round 2: the V2 frontend control matches the original's server control (gate).

    run_in_gate.sh <snapshot dir xd23db9a, or the pack folder> <.../v2/tests> <results> test_global_seed.py
    (a node.js binary must be reachable: $NODE, /deps/bin/node, or PATH)

The original's seed control is the on-prompt handler in inspire/inspire_server.py (prompt_seed_update +
workflow_seed_update, with control_seed, SeedGenerator and max_seed) plus js/seed.js, which applies the
"inspire-global-seed" event to the widgets. This test runs those exact functions, taken from the pristine
source with ast and executed here (the module itself needs the Impact Pack and a running server at import),
on the same graphs that tests/global_seed_harness.mjs runs v2/web/global_seed.js on. For every run it
compares the prompt that executes, the workflow embedded in the outputs, and the widgets afterwards.
Scenarios: control before and after generate, every deterministic action, wrap-around at 0 and max_seed,
muted/bypassed/connected/converted seed widgets, a frontend-only node with a "seed" widget, a muted
GlobalSeed, and "$GlobalSeed.value$" in a prompt text. Random actions are compared by their rules.
It also checks the node: schema == the original's INPUT_TYPES, validation and a guest execution (no outputs,
no UI, as the original's doit returns {}).
Writes /results/global_seed.json; exits 1 on any failed check.
"""

import ast
import asyncio
import copy
import importlib.util
import json
import os
import random
import shutil
import subprocess
import sys
import traceback
import types
from enum import Enum
from pathlib import Path

sys.path[:0] = ["/core", "/overlay", "/tests"]

from comfy.cli_args import args  # noqa: E402

args.cpu = True

import comfy.samplers  # noqa: E402,F401
import execution  # noqa: E402
import nodes as core_nodes  # noqa: E402
from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402

PACK_FOLDER = "ComfyUI-Inspire-Pack-HEAD"
NODE_ID = "GlobalSeed //Inspire"
MAX_SEED = 2 ** 32 - 1
PLACEHOLDER = "$GlobalSeed.value$"
V1_FUNCTIONS = ("max_seed", "SGmode", "SeedGenerator", "control_seed", "prompt_seed_update", "workflow_seed_update")
DEFS = {
    NODE_ID: ["value", "mode", "action", "last_seed"],
    "KSampler": ["model", "seed", "steps", "cfg", "sampler_name", "scheduler", "positive", "negative",
                 "latent_image", "denoise"],
    "KSamplerAdvanced": ["model", "add_noise", "noise_seed", "steps", "cfg", "sampler_name", "scheduler",
                         "positive", "negative", "latent_image", "start_at_step", "end_at_step",
                         "return_with_leftover_noise"],
    "CLIPTextEncode": ["text", "clip"],
    "SaveImage": ["images", "filename_prefix"],
}
checks = []


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
    snap = Path("/tmp/gs-snapshot")
    if not (snap / PACK_FOLDER).is_dir():
        shutil.copytree(root, snap / PACK_FOLDER, ignore=shutil.ignore_patterns("__pycache__"))
    return snap


# ---------------------------------------------------------------- the original, from its source
def original_seed_control(head: Path):
    """max_seed, SGmode, SeedGenerator, control_seed, prompt_seed_update, workflow_seed_update, verbatim."""
    path = head / "inspire" / "inspire_server.py"
    source = path.read_text(encoding="utf-8")
    pieces, found = [], set()
    for node in ast.parse(source).body:
        name = getattr(node, "name", None)
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
        if name in V1_FUNCTIONS:
            pieces.append(ast.get_source_segment(source, node))
            found.add(name)
    missing = set(V1_FUNCTIONS) - found
    if missing:
        raise RuntimeError(f"inspire_server.py lacks {sorted(missing)}")
    events = []
    server = types.SimpleNamespace(PromptServer=types.SimpleNamespace(
        instance=types.SimpleNamespace(send_sync=lambda event, data, *rest: events.append((event, copy.deepcopy(data))))))
    namespace = {"random": random, "Enum": Enum, "server": server, "__name__": "inspire_server_v1"}
    exec(compile("\n\n".join(pieces), str(path), "exec"), namespace)  # noqa: S102 - the pristine pack's own code
    return namespace, events


def in_prompt(record_):
    return record_.get("mode", "always") not in ("never", "bypass") and record_["type"] in DEFS


def build_prompt(graph):
    """The prompt the frontend builds from the graph (same rules as the harness's host double)."""
    prompt = {}

    def add(item, node_id):
        inputs = {}
        for name in DEFS[item["type"]]:
            if name in item.get("connected", []):
                inputs[name] = ["999", 0]
            else:
                widget = next((w for w in item["widgets"] if w["name"] == name), None)
                if widget is not None:
                    inputs[name] = widget["value"]
        prompt[node_id] = {"class_type": item["type"], "inputs": inputs}

    for item in graph["nodes"]:
        if in_prompt(item):
            add(item, str(item["id"]))
    for item in graph.get("subgraph_nodes", []):
        if in_prompt(item):
            add(item, f"sg:{item['id']}")
    return prompt


def original_run(namespace, events, before):
    """One queue in the original: js/prompt.js map, the on-prompt handler, then js/seed.js on the widgets."""
    graph = copy.deepcopy(before)
    widget_idx_map = {}
    for item in graph["nodes"]:  # js/prompt.js queuePrompt_with_widget_idxs (app.graph._nodes_by_id)
        for index, widget in enumerate(item["widgets"]):
            if widget["name"] in ("seed", "noise_seed", "sampler_name", "scheduler") and not widget.get("hidden"):
                widget_idx_map.setdefault(str(item["id"]), {})[widget["name"]] = index
    workflow = {"nodes": [{"id": item["id"], "type": item["type"],
                           "widgets_values": [w["value"] for w in item["widgets"]]} for item in graph["nodes"]],
                "widget_idx_map": widget_idx_map}
    json_data = {"prompt": build_prompt(graph), "extra_data": {"extra_pnginfo": {"workflow": workflow}}}
    events.clear()
    is_changed, mode = namespace["prompt_seed_update"](json_data)  # inspire_server.onprompt, seed part
    if is_changed:
        namespace["workflow_seed_update"](json_data, mode)
    for event, detail in events:  # js/seed.js globalSeedHandler
        if event != "inspire-global-seed":
            continue
        for item in graph["nodes"]:
            if item["type"] == NODE_ID:
                value = next(w for w in item["widgets"] if w["name"] == "value")
                last = next(w for w in item["widgets"] if w["name"] == "last_seed")
                last["value"] = value["value"]
                if detail["value"] is not None:
                    value["value"] = detail["value"]
            else:
                widget = next((w for w in item["widgets"] if w["name"] in ("seed", "noise_seed")
                               and isinstance(w["value"], int) and not w.get("hidden")), None)
                if widget is not None and str(item["id"]) in detail["seed_map"]:
                    widget["value"] = detail["seed_map"][str(item["id"])]
    workflow.pop("widget_idx_map")
    return {"prompt": json_data["prompt"], "workflow": workflow, "after": graph}


# ---------------------------------------------------------------- scenarios
def gs(node_id, value, before, action, last="", mode="always"):
    return {"id": node_id, "type": NODE_ID, "mode": mode,
            "widgets": [{"name": "value", "value": value}, {"name": "mode", "value": before},
                        {"name": "action", "value": action}, {"name": "last_seed", "value": last}]}


def ks(node_id, seed, mode="always", connected=(), hidden=False):
    return {"id": node_id, "type": "KSampler", "mode": mode, "connected": list(connected),
            "widgets": [{"name": "seed", "value": seed, "hidden": hidden},
                        {"name": "control_after_generate", "value": "fixed"}, {"name": "steps", "value": 20},
                        {"name": "cfg", "value": 8.0}, {"name": "sampler_name", "value": "euler"},
                        {"name": "scheduler", "value": "normal"}, {"name": "denoise", "value": 1.0}]}


def ksa(node_id, seed):
    return {"id": node_id, "type": "KSamplerAdvanced", "mode": "always",
            "widgets": [{"name": "add_noise", "value": "enable"}, {"name": "noise_seed", "value": seed},
                        {"name": "control_after_generate", "value": "fixed"}, {"name": "steps", "value": 20},
                        {"name": "cfg", "value": 8.0}, {"name": "sampler_name", "value": "euler"},
                        {"name": "scheduler", "value": "normal"}, {"name": "start_at_step", "value": 0},
                        {"name": "end_at_step", "value": 10000}, {"name": "return_with_leftover_noise",
                                                                    "value": "disable"}]}


def text(node_id, value):
    return {"id": node_id, "type": "CLIPTextEncode", "mode": "always", "widgets": [{"name": "text", "value": value}]}


def primitive(node_id, value):
    return {"id": node_id, "type": "PrimitiveNode", "mode": "always", "widgets": [{"name": "seed", "value": value}]}


def graph_with(controller):
    """A graph exercising every eligibility rule around one GlobalSeed.

    Seed widgets start at values no control step can produce here, so "reseeded" is visible. Node 8's seed
    is converted to a socket and connected, which in the original's frontend is a converted (hidden) widget.
    """
    return [ks(2, 700002), controller, ks(3, 700003), ksa(4, 700004), ks(6, 700006, mode="never"),
            ks(7, 700007, mode="bypass"), ks(8, 700008, connected=["seed"], hidden=True), primitive(9, 700009),
            text(10, f"a photo, seed {PLACEHOLDER}."), ks(12, 700012), ks(13, 700013, hidden=True), ks(21, 700021)]


SCENARIOS = [
    {"name": "before, increment for each node", "runs": 2,
     "nodes": graph_with(gs(5, 10, True, "increment for each node")),
     "subgraph_nodes": [text(30, f"inside {PLACEHOLDER}")]},
    {"name": "before, fixed", "runs": 2, "nodes": graph_with(gs(5, 42, True, "fixed", last="7"))},
    {"name": "before, increment at max_seed", "runs": 2, "nodes": graph_with(gs(5, MAX_SEED, True, "increment"))},
    {"name": "before, decrement for each node from 1", "runs": 2,
     "nodes": graph_with(gs(5, 1, True, "decrement for each node"))},
    {"name": "after, decrement from 0", "runs": 3, "nodes": graph_with(gs(5, 0, False, "decrement"))},
    {"name": "after, increment for each node", "runs": 2,
     "nodes": graph_with(gs(5, 123, False, "increment for each node"))},
    {"name": "after, fixed", "runs": 2, "nodes": graph_with(gs(5, 9, False, "fixed"))},
    {"name": "muted GlobalSeed", "runs": 1, "nodes": graph_with(gs(5, 10, True, "increment", mode="never"))},
    {"name": "no GlobalSeed", "runs": 1, "nodes": [ks(3, 700003), text(10, f"x {PLACEHOLDER}")]},
]
RANDOM_SCENARIOS = [
    {"name": "before, randomize", "runs": 2, "nodes": graph_with(gs(5, 10, True, "randomize"))},
    {"name": "after, randomize for each node", "runs": 2,
     "nodes": graph_with(gs(5, 10, False, "randomize for each node"))},
]


# ---------------------------------------------------------------- comparisons
def widget_values(graph):
    return {(str(item["id"]), w["name"]): w["value"] for item in graph["nodes"] for w in item["widgets"]}


def workflow_values(run):
    return {(str(n["id"]), i): value for n in run["workflow"]["nodes"] for i, value in enumerate(n["widgets_values"])}


def compare_exact(name, index, v1, v2):
    tag = f"{name} run {index + 1}"
    # The GlobalSeed node's own inputs are inert (its doit ignores them); every other node must match.
    want = {k: v for k, v in v1["prompt"].items() if v["class_type"] != NODE_ID}
    got = {k: v for k, v in v2["prompt"].items() if v["class_type"] != NODE_ID}
    record(f"{tag}: prompt == the original's (every node but the inert GlobalSeed)", want == got,
           json.dumps({"v1": want, "v2": got}, sort_keys=True)[:1400])
    # Known difference: text holding "$GlobalSeed.value$" is replaced in the graph while the prompt is built,
    # so the embedded workflow carries the replaced text where the original's keeps the placeholder.
    widget_names = {(str(item["id"]), i): w["name"] for item in v2["before"]["nodes"] for i, w in enumerate(item["widgets"])}
    v1_values, v2_values = workflow_values(v1), workflow_values(v2)
    unexplained = {}
    for key in sorted(set(v1_values) | set(v2_values)):
        a, b = v1_values.get(key), v2_values.get(key)
        if a == b:
            continue
        prompt_text = v1["prompt"].get(key[0], {}).get("inputs", {}).get(widget_names.get(key))
        if isinstance(a, str) and PLACEHOLDER in a and b == prompt_text:
            continue
        unexplained[str(key)] = (a, b)
    record(f"{tag}: embedded workflow == the original's (placeholder text aside)", not unexplained, unexplained)
    want_after, got_after = widget_values(v1["after"]), widget_values(v2["after"])
    record(f"{tag}: widgets after the run == the original's", want_after == got_after,
           {str(k): (want_after.get(k), got_after.get(k)) for k in set(want_after) | set(got_after)
            if want_after.get(k) != got_after.get(k)})


def reseeded(run):
    """Prompt-order seeds that differ from the graph's own value before the run (no collision is possible
    for deterministic values; a random one equals the old value with probability 2**-32)."""
    before = {(str(item["id"]), w["name"]): w["value"] for item in run["before"]["nodes"] for w in item["widgets"]}
    out = []
    for node_id in sorted((k for k in run["prompt"] if k.isdigit()), key=int):
        inputs = run["prompt"][node_id]["inputs"]
        for name in ("seed", "noise_seed"):
            value = inputs.get(name)
            if isinstance(value, int) and value != before.get((node_id, name)):
                out.append((node_id, name, value))
    return out


def compare_random(name, index, v1, v2):
    """Random actions: the same widgets are reseeded, within [0, max_seed], by the same rule."""
    tag = f"{name} run {index + 1}"
    v1["before"] = v2["before"]
    a, b = reseeded(v1), reseeded(v2)
    record(f"{tag}: the same seed widgets are reseeded", [x[:2] for x in a] == [x[:2] for x in b], (a, b))
    record(f"{tag}: every seed is within [0, max_seed]", all(0 <= x[2] <= MAX_SEED for x in a + b), (a, b))
    action = next(w["value"] for item in v2["before"]["nodes"] if item["type"] == NODE_ID
                  for w in item["widgets"] if w["name"] == "action")
    base = next(w["value"] for item in v2["before"]["nodes"] if item["type"] == NODE_ID
                for w in item["widgets"] if w["name"] == "value")
    if action == "randomize":  # one random value, shared by every node (SeedGenerator FIX)
        rule = lambda seeds: len({x[2] for x in seeds}) == 1  # noqa: E731
    else:  # randomize for each node: the first node gets the base value, then a new value per node
        rule = lambda seeds: bool(seeds) and seeds[0][2] == base  # noqa: E731
    record(f"{tag}: the action's rule holds on both sides", rule(a) and rule(b), (a, b))
    # "$GlobalSeed.value$" becomes the value each side used: the shared random value, or the base value.
    texts = [(str(item["id"]), w["name"], w["value"]) for item in v2["before"]["nodes"] if in_prompt(item)
             for w in item["widgets"] if isinstance(w["value"], str) and PLACEHOLDER in w["value"]]

    def placeholders_ok(run, seeds):
        used = seeds[0][2] if action == "randomize" and seeds else base
        return all(run["prompt"][node_id]["inputs"].get(name) == text.replace(PLACEHOLDER, str(used))
                   for node_id, name, text in texts)
    record(f"{tag}: placeholders carry each side's own value", placeholders_ok(v1, a) and placeholders_ok(v2, b),
           [(run["prompt"][n]["inputs"].get(k)) for run in (v1, v2) for n, k, _ in texts])
    placeholder_nodes = {node_id for node_id, _, _ in texts}
    rest = lambda run: {k: v for k, v in run["prompt"].items()  # noqa: E731
                        if v["class_type"] not in (NODE_ID, "KSampler", "KSamplerAdvanced")
                        and k not in placeholder_nodes}
    record(f"{tag}: every other prompt input == the original's", rest(v1) == rest(v2), (rest(v1), rest(v2)))


# ---------------------------------------------------------------- the node itself
def original_input_types(head: Path):
    source = (head / "inspire" / "prompt_support.py").read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef) and node.name == "GlobalSeed":
            namespace = {}
            exec(compile(ast.get_source_segment(source, node), "prompt_support.py", "exec"), namespace)  # noqa: S102
            return namespace["GlobalSeed"]
    raise RuntimeError("prompt_support.py has no GlobalSeed")


def normalized(spec):
    out = {}
    for section, inputs in spec.items():
        for name, declaration in inputs.items():
            kind, options = declaration[0], dict(declaration[1]) if len(declaration) > 1 else {}
            if isinstance(kind, list) or kind == "COMBO":
                values = kind if isinstance(kind, list) else options.pop("options")
                options.pop("multiselect", None)
                kind = ("COMBO", tuple(values))
            if options.get("multiline") is False:
                options.pop("multiline")
            out[(section, name)] = (kind, options)
    return out


async def node_checks(head: Path):
    V1 = original_input_types(head)
    spec = importlib.util.spec_from_file_location(
        "gs_v2", head / "v2" / "__init__.py", submodule_search_locations=[str(head / "v2")])
    package = importlib.util.module_from_spec(spec)
    sys.modules["gs_v2"] = package
    spec.loader.exec_module(package)
    v2_cls = package.NODE_CLASS_MAPPINGS[NODE_ID]
    v2_cls.GET_SCHEMA()
    want, got = normalized(V1.INPUT_TYPES()), normalized(v2_cls.INPUT_TYPES())
    # Core's V3 schema gives every output node the hidden PROMPT and EXTRA_PNGINFO inputs (the server
    # fills them; this node ignores them, as the original's doit ignores everything).
    framework = {("hidden", "prompt"): ("PROMPT", {}), ("hidden", "extra_pnginfo"): ("EXTRA_PNGINFO", {})}
    record("node: INPUT_TYPES == the original's (plus V3's hidden prompt/extra_pnginfo of an output node)",
           {k: v for k, v in got.items() if k not in framework} == want
           and all(got.get(k) == v for k, v in framework.items()), {"v1": want, "v2": got})
    record("node: input order == the original's",
           list(V1.INPUT_TYPES()["required"]) == list(v2_cls.INPUT_TYPES()["required"]),
           (list(V1.INPUT_TYPES()["required"]), list(v2_cls.INPUT_TYPES()["required"])))
    record("node: no outputs, an output node, the original's category, description and display name",
           tuple(v2_cls.RETURN_TYPES) == tuple(V1.RETURN_TYPES) == () and v2_cls.OUTPUT_NODE is True
           and v2_cls.CATEGORY == V1.CATEGORY and (getattr(v2_cls, "DESCRIPTION", "") or "") == ""
           and not hasattr(V1, "DESCRIPTION")
           and package.NODE_DISPLAY_NAME_MAPPINGS.get(NODE_ID) == "Global Seed (Inspire)",
           (v2_cls.RETURN_TYPES, v2_cls.OUTPUT_NODE, v2_cls.CATEGORY, getattr(v2_cls, "DESCRIPTION", None)))

    loaded = packdb.load_pack(snapshot_dir(), mount_name="custom_nodes.gs_proxy", pack_id="comfyui-inspire-pack/xd23db9a")
    proxy = loaded.node_mappings[NODE_ID]
    record("manifest: declares the web directory with the control module",
           loaded.web_directory is not None and (Path(loaded.web_directory) / "global_seed.js").is_file(),
           loaded.web_directory)
    session = await GuestSession("gs").start()

    class Backend:
        async def dispatch(self, plan, local_call, runtime=None):
            if not str(getattr(plan, "node_module", "") or "").startswith("custom_nodes."):
                return await local_call()
            caps = set(plan.permissions or ())
            if getattr(plan, "input_mode", "refs") == "values":
                caps.add("raw")
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
            return await session.execute(plan, runtime, capabilities=frozenset(caps), tenant="gs")

    previous = _sdk.providers.execution_backend
    _sdk.providers.register_execution_backend(Backend())
    saved = core_nodes.NODE_CLASS_MAPPINGS.get(NODE_ID)
    try:
        for label, inputs, want in (
                ("valid inputs", dict(value=10, mode=True, action="increment", last_seed=""), True),
                ("an unknown action", dict(value=10, mode=True, action="sometimes", last_seed=""), False)):
            outcomes = []
            for cls in (V1, proxy):
                core_nodes.NODE_CLASS_MAPPINGS[NODE_ID] = cls
                ok_flag, errors, _ = await execution.validate_inputs(
                    "gs", {"5": {"class_type": NODE_ID, "inputs": inputs}}, "5", {})
                outcomes.append((bool(ok_flag), sorted(e.get("type") for e in errors)))
            record(f"validation (guest) {label}: same outcome as the original", outcomes[0] == outcomes[1]
                   and outcomes[0][0] is want, outcomes)
        proxy.GET_SCHEMA()
        output, ui, _sub, _pending = await execution.get_output_data(
            "gs", "5", proxy, {"value": [10], "mode": [True], "action": ["increment"], "last_seed": [""]})
        v1_output, v1_ui, _s, _p = await execution.get_output_data(
            "gs", "5", V1(), {"value": [10], "mode": [True], "action": ["increment"], "last_seed": [""]})
        record("guest execution: no outputs and no UI, as the original's doit", output == v1_output == []
               and not ui and not v1_ui, (output, ui, v1_output, v1_ui))
    finally:
        if saved is None:
            core_nodes.NODE_CLASS_MAPPINGS.pop(NODE_ID, None)
        else:
            core_nodes.NODE_CLASS_MAPPINGS[NODE_ID] = saved
        _sdk.providers.register_execution_backend(previous)
        pid = session.last_guest_pid
        await session.kill()
    record("guest: out-of-process", pid not in (None, os.getpid()), pid)


def node_binary():
    for candidate in (os.environ.get("NODE"), "/deps/bin/node", shutil.which("node")):
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError("no node.js binary (set NODE, mount it at /deps/bin/node, or put it on PATH)")


def frontend_checks(head: Path):
    namespace, events = original_seed_control(head)
    record("original: inspire_server.max_seed == 2**32 - 1", namespace["max_seed"] == MAX_SEED, namespace["max_seed"])
    work = Path("/tmp/gs-harness")
    work.mkdir(parents=True, exist_ok=True)
    scenarios = work / "scenarios.json"
    scenarios.write_text(json.dumps({"defs": DEFS, "scenarios": SCENARIOS + RANDOM_SCENARIOS}))
    binary = node_binary()
    env = {"TARGET_JS": str(head / "v2" / "web" / "global_seed.js"), "SCENARIOS": str(scenarios),
           "WORK": str(work), "PATH": "/usr/bin:/bin"}
    libs = Path(binary).parent.parent / "lib"  # a mounted node may bring the runtime libraries it needs
    if libs.is_dir():
        env["LD_LIBRARY_PATH"] = str(libs)
    completed = subprocess.run(
        [binary, str(Path(__file__).with_name("global_seed_harness.mjs"))], capture_output=True, text=True,
        timeout=120, env=env)
    if completed.returncode != 0:
        raise RuntimeError(f"harness failed: {completed.stderr[-2000:]}")
    results = json.loads(completed.stdout)
    for scenario in SCENARIOS + RANDOM_SCENARIOS:
        for index, v2_run in enumerate(results[scenario["name"]]):
            v1_run = original_run(namespace, events, v2_run["before"])
            if scenario in RANDOM_SCENARIOS:
                compare_random(scenario["name"], index, v1_run, v2_run)
            else:
                compare_exact(scenario["name"], index, v1_run, v2_run)


def main() -> int:
    head = pack_head()
    try:
        frontend_checks(head)
    except Exception:  # noqa: BLE001
        record("frontend session", False, traceback.format_exc())
    try:
        asyncio.run(node_checks(head))
    except Exception:  # noqa: BLE001
        record("node session", False, traceback.format_exc())
    failed = [c["check"] for c in checks if not c["ok"]]
    result = {"pack": "comfyui-inspire-pack", "round": "2 (Global Seed)", "checks": checks, "failed": failed,
              "verdict": "PASS" if not failed else "FAIL"}
    Path("/results/global_seed.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({"verdict": result["verdict"], "failed": failed}))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
