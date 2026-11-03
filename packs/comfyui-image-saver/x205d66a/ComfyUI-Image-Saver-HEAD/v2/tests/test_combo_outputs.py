"""Tier-1 COMBO-output parity: comfyui-image-saver ORIGINAL vs V2 (CPU, no weights, synthetic fixtures).

The original's selectors return Core's own choice lists as their output types (nodes_selectors.py:86, 106,
126, 146, 167; nodes_pipe.py:208). Core accepts such a list linked into a list-typed input when the lists
share a value (comfy_execution/validation.py). V2 declares those outputs as COMBO outputs with the same
options; a Core whose Combo.Output reports declared options as its type serves them like the original.

Run in the gate (DEPS = piexif, which the original's saver imports):
  DEPS=<piexif> run_in_gate.sh <pack> <pack>/v2/tests <results> test_combo_outputs.py
once on each Core:
  * Core whose Combo.Output reports declared options (comfy_api/latest/_io.py with Combo.Output.get_io_type);
  * Core without it, where every COMBO output is the plain string "COMBO" (reported, expected to differ).

Checks:
  A. object_info outputs of every node: original (V1 class) vs the V2 host proxy that packdb builds from
     v2/secure-nodes.json, as served.
  B. Core's validate_prompt on synthetic prompts, with the original classes and then the V2 proxies
     registered under the same ids: same verdict, same node errors (type, input), same good outputs.
  C. Returned values: every choice of every selector, and Input Parameters, in a REAL guest vs the original.
  D. Negative controls: the comparisons must flag an output without its options and a disjoint link.
Writes /results/combo-outputs.json. Exit 0 only when everything equals the original.
"""
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

CORE = Path(os.environ.get("COMFY_CORE_ROOT", "/core"))
PACK = Path(os.environ.get("IMAGESAVER_PACK", "/pack"))
V2 = PACK / "v2"
RESULTS = Path(os.environ.get("IMAGESAVER_RESULTS", "/results"))
sys.path[:0] = [str(CORE), "/overlay"] + (["/deps"] if Path("/deps").is_dir() else [])

from comfy.cli_args import args  # noqa: E402

args.cpu = True
import folder_paths  # noqa: E402
import nodes as core_nodes  # noqa: E402
import execution  # noqa: E402
from comfy_api.latest import _execution_metadata, _sdk, io  # noqa: E402
from comfy_execution.graph import DynamicPrompt  # noqa: E402
from comfy_secure_nodes import packdb  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="imagesaver-combo-"))
CKPT = TMP / "models" / "checkpoints"
CKPT.mkdir(parents=True)
(CKPT / "model_a.safetensors").write_bytes(b"synthetic checkpoint name only\n")
folder_paths.folder_names_and_paths["checkpoints"] = ([str(CKPT)], set(folder_paths.supported_pt_extensions))
CORE_PROJECTS_OPTIONS = "get_io_type" in vars(io.Combo.Output)
ROWS = []


def import_package(name, root):
    spec = importlib.util.spec_from_file_location(name, root / "__init__.py", submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PRISTINE = TMP / "pristine" / "ComfyUI-Image-Saver-HEAD"
shutil.copytree(PACK, PRISTINE, ignore=shutil.ignore_patterns("v2"))
ORIGINAL = dict(import_package("imagesaver_original", PRISTINE).NODE_CLASS_MAPPINGS)
SECURE = dict(import_package("imagesaver_secure", V2).NODE_CLASS_MAPPINGS)


def host_proxies():
    """The classes the runtime registers: packdb proxies built from v2/secure-nodes.json."""
    snap = TMP / "snap" / "comfyui-image-saver" / "x205d66a"
    shutil.copytree(PACK, snap / PACK.name)
    return dict(packdb.load_pack(snap, mount_name="custom_nodes.imagesaver_combo_check").node_mappings)


PROXIES = host_proxies()


def plain(value):
    return json.loads(json.dumps(value, default=list))


def record(check, case, ok, **details):
    ROWS.append({"check": check, "case": case, "ok": bool(ok), **details})
    if not ok:
        print("DIFF", check, case, json.dumps(details, default=str)[:700], flush=True)


# --------------------------------------------------------------------------------------------------------------- #
# A. object_info outputs
# --------------------------------------------------------------------------------------------------------------- #
def v1_outputs(cls):
    """server.py node_info for a V1 class, output fields only."""
    output = list(cls.RETURN_TYPES)
    info = {
        "output": output,
        "output_is_list": list(cls.OUTPUT_IS_LIST) if hasattr(cls, "OUTPUT_IS_LIST") else [False] * len(output),
        "output_name": list(cls.RETURN_NAMES) if hasattr(cls, "RETURN_NAMES") else output,
        "output_tooltips": list(cls.OUTPUT_TOOLTIPS) if hasattr(cls, "OUTPUT_TOOLTIPS") else None,
    }
    return plain(info)


def served_outputs(cls):
    info = cls.GET_NODE_INFO_V1()
    return plain({key: info.get(key) for key in ("output", "output_is_list", "output_name", "output_tooltips")})


def normal(info):
    """V3 serves output_tooltips as a list with None for absent entries; V1 omits the key when undeclared."""
    tips = info.get("output_tooltips")
    if not tips or all(tip is None for tip in tips):
        tips = None
    return {**info, "output_tooltips": tips}


def object_info_outputs(proxies, label):
    combo_outputs = 0
    for node_id in sorted(ORIGINAL):
        original = normal(v1_outputs(ORIGINAL[node_id]))
        try:
            served = normal(served_outputs(proxies[node_id]))
        except Exception as error:  # noqa: BLE001
            record("A_object_info_outputs", f"{label}:{node_id}", False, error=f"{type(error).__name__}: {error}")
            continue
        lists = [index for index, value in enumerate(original["output"]) if isinstance(value, list)]
        combo_outputs += len(lists)
        details = {"list_outputs": lists}
        if original != served:
            details["original"] = {k: (v if k != "output" else [x if not isinstance(x, list) else f"list[{len(x)}]"
                                                             for x in v]) for k, v in original.items()}
            details["v2"] = {k: (v if k != "output" else [x if not isinstance(x, list) else f"list[{len(x)}]"
                                                       for x in v]) for k, v in served.items()}
            details["differing_keys"] = sorted(k for k in original if original[k] != served.get(k))
        record("A_object_info_outputs", f"{label}:{node_id}", original == served, **details)
    return combo_outputs


# --------------------------------------------------------------------------------------------------------------- #
# B. core's validate_prompt, original vs V2 under the same ids
# --------------------------------------------------------------------------------------------------------------- #
def defaults(node_id, sections=("required",)):
    """Widget values for the ORIGINAL's declared inputs: its default, else the first choice."""
    spec = ORIGINAL[node_id].INPUT_TYPES()
    values = {}
    for section in sections:
        for name, entry in (spec.get(section) or {}).items():
            kind = entry[0]
            opts = entry[1] if len(entry) > 1 and isinstance(entry[1], dict) else {}
            if isinstance(kind, (list, tuple)):
                values[name] = opts.get("default", kind[0]) if opts.get("default") in kind else kind[0]
            elif kind in ("INT", "FLOAT", "STRING", "BOOLEAN"):
                values[name] = opts.get("default", {"INT": 0, "FLOAT": 0.0, "STRING": "", "BOOLEAN": False}[kind])
    return values


def stock():
    return {
        "ckpt": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "model_a.safetensors"}},
        "pos": {"class_type": "CLIPTextEncode", "inputs": {"text": "a", "clip": ["ckpt", 1]}},
        "neg": {"class_type": "CLIPTextEncode", "inputs": {"text": "b", "clip": ["ckpt", 1]}},
        "lat": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
        "ks": {"class_type": "KSampler", "inputs": {
            "model": ["ckpt", 0], "positive": ["pos", 0], "negative": ["neg", 0], "latent_image": ["lat", 0],
            "seed": 1, "steps": 1, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0}},
        "dec": {"class_type": "VAEDecode", "inputs": {"samples": ["ks", 0], "vae": ["ckpt", 2]}},
        "out": {"class_type": "PreviewImage", "inputs": {"images": ["dec", 0]}},
    }


def prompts():
    cases = {"control_stock_prompt": stock()}

    def with_nodes(extra, ks_links, base=None):
        prompt = base or stock()
        prompt.update(copy.deepcopy(extra))
        prompt["ks"]["inputs"].update(ks_links)
        return prompt

    cases["sampler_selector_to_ksampler"] = with_nodes(
        {"sel": {"class_type": "Sampler Selector (Image Saver)", "inputs": {"sampler_name": "euler"}}},
        {"sampler_name": ["sel", 0]})
    for node_id, label in (("Scheduler Selector (Image Saver)", "scheduler_selector"),
                           ("Scheduler Selector (inspire) (Image Saver)", "inspire_scheduler_selector"),
                           ("Scheduler Selector (Eff.) (Image Saver)", "eff_scheduler_selector")):
        cases[f"{label}_to_ksampler"] = with_nodes(
            {"sch": {"class_type": node_id, "inputs": {"scheduler": "karras"}}}, {"scheduler": ["sch", 0]})
    selectors = {
        "sel": {"class_type": "Sampler Selector (Image Saver)", "inputs": {"sampler_name": "dpmpp_2m"}},
        "sch": {"class_type": "Scheduler Selector (Image Saver)", "inputs": {"scheduler": "karras"}},
        "par": {"class_type": "Input Parameters (Image Saver)", "inputs": {
            "seed": 20261103, "steps": 2, "cfg": 5.0, "denoise": 1.0, "sampler": ["sel", 0], "scheduler": ["sch", 0]}},
    }
    parameter_links = {"seed": ["par", 0], "steps": ["par", 1], "cfg": ["par", 2], "sampler_name": ["par", 3],
                       "scheduler": ["par", 4], "denoise": ["par", 5]}
    cases["selectors_via_input_parameters_to_ksampler"] = with_nodes(selectors, parameter_links)
    pipe = {
        "scfg": {"class_type": "Make Image Saver Simple Config", "inputs": defaults("Make Image Saver Simple Config")},
        "mcfg": {"class_type": "Make Image Saver Metadata Config",
                 "inputs": {"sampler_name": "dpmpp_2m", "scheduler_name": "karras"}},
        "mk": {"class_type": "Make Image Saver Pipe",
               "inputs": {"simple_saver_config": ["scfg", 0], "metadata_config": ["mcfg", 0]}},
        "rd": {"class_type": "Read Image Saver Pipe", "inputs": {"pipe": ["mk", 0]}},
    }
    cases["read_pipe_to_ksampler"] = with_nodes(pipe, {"sampler_name": ["rd", 12], "scheduler": ["rd", 13]})
    # The shape of a common saving workflow: named checkpoint -> parameters -> KSampler -> Image Saver.
    saving = stock()
    del saving["ckpt"], saving["out"]
    saving.update(copy.deepcopy(selectors))
    saving["ckn"] = {"class_type": "Checkpoint Loader with Name (Image Saver)",
                     "inputs": {"ckpt_name": "model_a.safetensors"}}
    for node in ("pos", "neg"):
        saving[node]["inputs"]["clip"] = ["ckn", 1]
    saving["ks"]["inputs"].update(model=["ckn", 0], **parameter_links)
    saving["dec"]["inputs"]["vae"] = ["ckn", 2]
    saver_inputs = defaults("Image Saver")
    saver_inputs.update({"images": ["dec", 0], "modelname": ["ckn", 3], "sampler_name": ["sel", 1],
                         "scheduler_name": ["sch", 1], "seed_value": ["par", 0], "steps": ["par", 1],
                         "cfg": ["par", 2], "denoise": ["par", 5], "extension": "png"})
    saving["save"] = {"class_type": "Image Saver", "inputs": saver_inputs}
    cases["named_checkpoint_parameters_saver"] = saving
    # Negative controls: refused by the original too.
    cases["negative_scheduler_list_into_sampler_input"] = with_nodes(
        {"sch": {"class_type": "Scheduler Selector (Image Saver)", "inputs": {"scheduler": "karras"}}},
        {"sampler_name": ["sch", 0]})
    named = stock()
    named["ckn"] = {"class_type": "Checkpoint Loader with Name (Image Saver)",
                    "inputs": {"ckpt_name": "model_a.safetensors"}}
    named["ckpt"]["inputs"]["ckpt_name"] = ["ckn", 3]
    cases["negative_model_name_string_into_checkpoint_loader"] = named
    return cases


def summary(result):
    valid, error, good, node_errors = result
    errors = {}
    for node_id, entry in sorted(node_errors.items()):
        errors[node_id] = sorted((item.get("type"), (item.get("extra_info") or {}).get("input_name"))
                                 for item in entry.get("errors", []))
    return {"valid": bool(valid), "error_type": (error or {}).get("type") if isinstance(error, dict) else error,
            "good_outputs": sorted(good), "node_errors": errors}


def details(result):
    return {node_id: [str(item.get("details"))[:160] for item in entry.get("errors", [])]
            for node_id, entry in sorted(result[3].items())}


async def validate_with(classes, prompt):
    saved = {node_id: core_nodes.NODE_CLASS_MAPPINGS.get(node_id) for node_id in classes}
    core_nodes.NODE_CLASS_MAPPINGS.update(classes)
    try:
        return await execution.validate_prompt("imagesaver-combo", copy.deepcopy(prompt), None)
    finally:
        for node_id, value in saved.items():
            if value is None:
                core_nodes.NODE_CLASS_MAPPINGS.pop(node_id, None)
            else:
                core_nodes.NODE_CLASS_MAPPINGS[node_id] = value


async def prompt_validation(proxies, label):
    for name, prompt in prompts().items():
        original = await validate_with(ORIGINAL, prompt)
        v2 = await validate_with(proxies, prompt)
        a, b = summary(original), summary(v2)
        row = {"original": a, "v2": b}
        if a != b:
            row["original_details"], row["v2_details"] = details(original), details(v2)
        if name.startswith("negative_"):
            row["control"] = "refused by the original as well" if not a["valid"] or a["node_errors"] else "UNEXPECTED"
        record("B_validate_prompt", f"{label}:{name}", a == b, **row)


# --------------------------------------------------------------------------------------------------------------- #
# C. Returned values in a real guest
# --------------------------------------------------------------------------------------------------------------- #
GUEST = {"session": None, "pids": set()}


async def run_v2(node_id, inputs):
    cls = SECURE[node_id]
    permissions = tuple(cls.SDK_PERMISSIONS)
    refs = _sdk.InProcessRefResolver()
    scope = _execution_metadata.ExecutionMetadataScope("imagesaver-combo", DynamicPrompt({}), None, observe=True)
    scope.__enter__()
    try:
        plan = _sdk.ExecutionPlan(
            prompt_id="imagesaver-combo", node_id="9", node_type=cls.__name__, tier="sandbox",
            node_module=cls.__module__, inputs=dict(inputs),
            input_mode="refs" if getattr(cls, "SDK_REFS", False) else "values",
            method="execute", permissions=permissions, prompt=None, extra_pnginfo=None,
            dynamic_prompt=DynamicPrompt({}), execution_metadata=scope)
        runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
        plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
        if GUEST["session"] is None:
            GUEST["session"] = await GuestSession("imagesaver-combo", guest_runtime_root=V2).start()
        guest = GUEST["session"]
        result = await guest.execute(plan, runtime, capabilities=permissions, tenant="imagesaver-combo")
        if guest.last_guest_pid:
            GUEST["pids"].add(guest.last_guest_pid)
        values = []
        for item in (result.result or ()):
            values.append(await refs.resolve(item) if isinstance(item, _sdk.Ref) else item)
        return tuple(values)
    finally:
        scope.__exit__(None, None, None)


def same(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, float):
        return a.hex() == b.hex()
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def run_original(node_id, inputs):
    cls = ORIGINAL[node_id]
    return tuple(getattr(cls(), cls.FUNCTION)(**inputs))


async def returned_values():
    for node_id, name in (("Sampler Selector (Image Saver)", "sampler_name"),
                          ("Scheduler Selector (Image Saver)", "scheduler"),
                          ("Scheduler Selector (inspire) (Image Saver)", "scheduler"),
                          ("Scheduler Selector (Eff.) (Image Saver)", "scheduler")):
        choices = list(ORIGINAL[node_id].INPUT_TYPES()["required"][name][0])
        for value in choices:
            expected = run_original(node_id, {name: value})
            actual = await run_v2(node_id, {name: value})
            record("C_returned_values", f"{node_id}:{value}", same(expected, actual),
                   expected=list(expected), actual=list(actual))
    params = ORIGINAL["Input Parameters (Image Saver)"].INPUT_TYPES()["required"]
    samplers, schedulers = list(params["sampler"][0]), list(params["scheduler"][0])
    for seed, steps, cfg, sampler, scheduler, denoise in (
            (0, 1, 0.0, samplers[0], schedulers[0], 0.0),
            (20261103, 20, 7.0, "dpmpp_2m", "karras", 1.0),
            (0xffffffffffffffff, 10000, 100.0, samplers[-1], schedulers[-1], 0.55),
            (123, 7, 5.25, "euler_ancestral", "normal", 0.3)):
        inputs = {"seed": seed, "steps": steps, "cfg": cfg, "sampler": sampler, "scheduler": scheduler,
                  "denoise": denoise}
        expected = run_original("Input Parameters (Image Saver)", inputs)
        actual = await run_v2("Input Parameters (Image Saver)", inputs)
        record("C_returned_values", f"Input Parameters:{seed},{steps},{cfg},{sampler},{scheduler},{denoise}",
               same(expected, actual), expected=[str(v) for v in expected], actual=[str(v) for v in actual])


# --------------------------------------------------------------------------------------------------------------- #
# D. Negative controls
# --------------------------------------------------------------------------------------------------------------- #
def negative_controls():
    node_id = "Sampler Selector (Image Saver)"
    original = normal(v1_outputs(ORIGINAL[node_id]))
    stripped = copy.deepcopy(original)
    stripped["output"][0] = "COMBO"
    record("D_negative_control", "object_info comparison flags an output without its options",
           original != stripped)
    lists = ORIGINAL["Scheduler Selector (Image Saver)"].RETURN_TYPES[0]
    from comfy_execution.validation import validate_node_input
    ksampler = core_nodes.NODE_CLASS_MAPPINGS["KSampler"].INPUT_TYPES()["required"]
    record("D_negative_control", "Core refuses a disjoint list link (schedulers into sampler_name)",
           validate_node_input(list(lists), ksampler["sampler_name"][0]) is False)


async def main():
    started = asyncio.get_running_loop().time()
    report = {
        "core": {"path": str(CORE),
                 "io_py_sha256": hashlib.sha256((CORE / "comfy_api/latest/_io.py").read_bytes()).hexdigest(),
                 "combo_output_reports_options": CORE_PROJECTS_OPTIONS},
        "manifest_sha256": hashlib.sha256((V2 / "secure-nodes.json").read_bytes()).hexdigest(),
        "runtime_sha256": hashlib.sha256((V2 / "_secure_runtime.py").read_bytes()).hexdigest(),
        "classes": {"original": "pristine package imported in-process",
                    "v2_served": "packdb host proxies from v2/secure-nodes.json",
                    "v2_values": "GuestSession (real guest) running the V2 classes"},
    }
    try:
        report["list_outputs_in_original"] = object_info_outputs(PROXIES, "served")
        await prompt_validation(PROXIES, "served")
        await returned_values()
        negative_controls()
    except Exception:  # noqa: BLE001
        report["harness_error"] = traceback.format_exc()[-3000:]
    finally:
        if GUEST["session"] is not None:
            await GUEST["session"].kill()  # GuestSession teardown: process-group kill and state scrub
        alive = [pid for pid in GUEST["pids"] if Path(f"/proc/{pid}").exists()]
        report["guest_cleanup"] = {"guest_pids": sorted(GUEST["pids"]), "alive_after_close": alive}
        shutil.rmtree(TMP, ignore_errors=True)
    totals = {}
    for row in ROWS:
        bucket = totals.setdefault(row["check"], {"ok": 0, "differ": 0})
        bucket["ok" if row["ok"] else "differ"] += 1
    report["totals"] = totals
    report["seconds"] = round(asyncio.get_running_loop().time() - started, 1)
    report["rows"] = ROWS
    passed = (not report.get("harness_error") and all(row["ok"] for row in ROWS)
              and not report["guest_cleanup"]["alive_after_close"])
    report["verdict"] = "EQUAL_TO_ORIGINAL" if passed else "DIFFERS"
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "combo-outputs.json").write_text(json.dumps(report, indent=1, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: report[k] for k in ("core", "manifest_sha256", "totals", "guest_cleanup", "verdict", "seconds")},
                     indent=1, default=str))
    if report.get("harness_error"):
        print(report["harness_error"])
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
