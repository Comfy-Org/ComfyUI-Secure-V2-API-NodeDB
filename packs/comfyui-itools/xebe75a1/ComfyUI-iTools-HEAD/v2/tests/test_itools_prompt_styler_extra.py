"""Regression test for the iTools repair: Prompt Styler Extra returns the original's strings (gate).

    run_in_gate.sh <snapshot dir xebe75a1, or the pack folder> <.../v2/tests> <results> \
        test_itools_prompt_styler_extra.py

The original (iTools_nodes.IToolsPromptStylerExtra, imported from the pristine pack with a stand-in route
table) and V2 run on the same inputs, V2 both in-process (the V3 class) and through a real guest (host
proxy from secure-nodes.json, the pack's asset folders registered as the secure loader does). The cases:
  * a secondary template carrying "{prompt}" with every other style "none" (the guarded case);
  * every style "none";
  * a full set from the default files with prompt text, including "of {prompt}" templates and negatives;
  * styles from files other than the default ones, including "PHOTO | ..." names;
  * a negative prompt without a base negative, and a base negative with the text negative prepended.
All three outputs must equal the original's (type and value). Validation through core, against the
original: a cross-file style set is accepted, an unknown file is refused, and an unknown style passes
validation and then fails at execution with the original's message.
Writes /results/prompt_styler_extra.json; exits 1 on any failed check.
"""

import asyncio
import importlib
import importlib.util
import json
import os
import shutil
import sys
import traceback
import types
from pathlib import Path

sys.path[:0] = ["/core", "/overlay", "/tests"]

from comfy.cli_args import args  # noqa: E402

args.cpu = True

import comfy.samplers  # noqa: E402,F401
import execution  # noqa: E402
import folder_paths  # noqa: E402
import nodes as core_nodes  # noqa: E402
from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402

PACK_FOLDER = "ComfyUI-iTools-HEAD"
NODE = "iToolsPromptStylerExtra"
DEFAULTS = dict(text_positive="", text_negative="", base_file="basic.yaml", base_style="none",
                second_file="camera.yaml", second_style="none", third_file="artist.yaml", third_style="none",
                fourth_file="mood.yaml", fourth_style="none")
CASES = {
    "secondary template with {prompt}": dict(DEFAULTS, third_style="Silvestro Lega"),
    "all none": dict(DEFAULTS),
    "default files, full set": dict(DEFAULTS, text_positive="a red fox in fresh snow", text_negative="blurry",
                                    base_style="3D Model", second_style="Canon EOS 90D",
                                    third_style="A.J.Casson", fourth_style="Aggressive"),
    "other files, PHOTO | names": dict(DEFAULTS, text_positive="an old lighthouse", base_file="nexus.yaml",
                                       base_style="PHOTO | Cinematic Noir", second_file="nexus.yaml",
                                       second_style="PHOTO | Hyper-Realistic Macro", third_file="camera.yaml",
                                       third_style="Canon EOS M50", fourth_file="original.yaml",
                                       fourth_style="ads-advertising"),
    "text negative, no base negative": dict(DEFAULTS, text_positive="portrait", text_negative="lowres",
                                            fourth_style="Abyssal Silence"),
    "base negative prepended": dict(DEFAULTS, text_positive="city at dusk", text_negative="text, watermark",
                                    base_style="Analog", second_style="Canon EOS M50 Mark II"),
}
VALIDATION = {
    "styles from other files": CASES["other files, PHOTO | names"],
    "unknown file": dict(DEFAULTS, base_file="nope.yaml"),
    "unknown style": dict(DEFAULTS, third_style="No Such Style"),
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
    snap = Path("/tmp/it-snapshot")
    if not (snap / PACK_FOLDER).is_dir():
        shutil.copytree(root, snap / PACK_FOLDER, ignore=shutil.ignore_patterns("__pycache__"))
    return snap


def original_class(head: Path):
    """The pristine node class. Its loader finds the pack as custom_nodes/ComfyUI-iTools, and its route
    decorators need PromptServer.instance.routes; both are provided here, nothing else is stubbed."""
    from aiohttp import web

    custom = Path("/tmp/it-custom")
    custom.mkdir(parents=True, exist_ok=True)
    link = custom / "ComfyUI-iTools"
    if not link.exists():
        link.symlink_to(head)
    folder_paths.folder_names_and_paths["custom_nodes"][0].insert(0, str(custom))
    server = sys.modules.get("server")
    if server is None:
        server = types.ModuleType("server")
        server.PromptServer = type("PromptServer", (), {})
        sys.modules["server"] = server
    if getattr(server.PromptServer, "instance", None) is None:
        server.PromptServer.instance = types.SimpleNamespace(routes=web.RouteTableDef())
    parent = types.ModuleType("it_pristine")
    parent.__path__ = [str(head)]
    sys.modules["it_pristine"] = parent
    return importlib.import_module("it_pristine.iTools_nodes").IToolsPromptStylerExtra


async def core_output(obj, inputs):
    if hasattr(obj, "GET_SCHEMA"):
        obj.GET_SCHEMA()
    output, _ui, _sub, _pending = await execution.get_output_data(
        "it-styler", "1", obj, {key: [value] for key, value in inputs.items()})
    return tuple(values[0] for values in output)


def run_v1(V1, inputs):
    try:
        return ("ok", tuple(V1().prompt_styler_extra(**inputs)))
    except Exception as error:  # noqa: BLE001
        return ("error", f"{type(error).__name__}: {error}")


async def run_v2(cls, inputs):
    try:
        return ("ok", await core_output(cls, inputs))
    except Exception as error:  # noqa: BLE001
        return ("error", f"{type(error).__name__}: {error}")


def compare(label, want, got):
    if want[0] == "ok":
        same = (got[0] == "ok" and len(got[1]) == 3
                and all(type(a) is type(b) and a == b for a, b in zip(want[1], got[1])))
        record(label, same, f"V1 {want[1]!r} vs V2 {got[1]!r}")
    else:
        # The original's exception text, e.g. "ValueError: No template found with name 'X'.", must appear
        # in V2's error (in a guest it arrives wrapped by the transport).
        record(label, got[0] == "error" and want[1] in got[1], f"V1 {want[1]!r} vs V2 {got[1]!r}")


async def validation_result(cls, inputs):
    saved = core_nodes.NODE_CLASS_MAPPINGS.get(NODE)
    core_nodes.NODE_CLASS_MAPPINGS[NODE] = cls
    try:
        ok_flag, errors, _ = await execution.validate_inputs(
            "it-styler", {"1": {"class_type": NODE, "inputs": dict(inputs)}}, "1", {})
        return bool(ok_flag), sorted({(e.get("type"), (e.get("extra_info") or {}).get("input_name")) for e in errors})
    finally:
        if saved is None:
            core_nodes.NODE_CLASS_MAPPINGS.pop(NODE, None)
        else:
            core_nodes.NODE_CLASS_MAPPINGS[NODE] = saved


async def check_validation(label, V1, cls):
    for name, inputs in VALIDATION.items():
        title = f"validation ({label}) {name}: same outcome as V1"
        try:
            want = await validation_result(V1, inputs)
            got = await validation_result(cls, inputs)
            record(title, want == got, f"V1 {want} vs V2 {got}")
        except Exception:  # noqa: BLE001
            record(title, False, traceback.format_exc()[-1200:])


async def run() -> dict:
    facts = {}
    head = pack_head()
    for name, setter in (("temp", folder_paths.set_temp_directory), ("output", folder_paths.set_output_directory)):
        Path(f"/tmp/it-{name}").mkdir(parents=True, exist_ok=True)
        setter(f"/tmp/it-{name}")
    V1 = original_class(head)
    wants = {name: run_v1(V1, inputs) for name, inputs in CASES.items()}
    wants["unknown style (execution)"] = run_v1(V1, VALIDATION["unknown style"])
    facts["v1_outputs"] = wants
    record("V1: the guarded case keeps the secondary template's {prompt}",
           wants["secondary template with {prompt}"][0] == "ok"
           and "{prompt}" in wants["secondary template with {prompt}"][1][0], wants["secondary template with {prompt}"])

    loaded = packdb.load_pack(snapshot_dir(), mount_name="custom_nodes.it_styler_proxy",
                              pack_id="comfyui-itools/xebe75a1")
    for folder, directory in loaded.asset_directories.items():
        folder_paths.add_model_folder_path(folder, str(directory))
    proxy = loaded.node_mappings[NODE]

    spec = importlib.util.spec_from_file_location(
        "it_v2", head / "v2" / "__init__.py", submodule_search_locations=[str(head / "v2")])
    package = importlib.util.module_from_spec(spec)
    sys.modules["it_v2"] = package
    spec.loader.exec_module(package)
    v2_cls = package.NODE_CLASS_MAPPINGS[NODE]
    try:
        from comfy_secure_nodes import packmanifest

        row = json.loads((head / "v2" / "secure-nodes.json").read_text(encoding="utf-8"))["nodes"][NODE]
        encoded = packmanifest.encode_validation_inputs(v2_cls)
        record("manifest: validation_inputs == the encoder's reading of the class (V1's argument list)",
               row["methods"].get("validate_inputs") is True and row.get("validation_inputs") == encoded
               == {"args": ["cls", "base_style", "second_style", "third_style", "fourth_style"], "kwargs": False},
               f"manifest {row['methods']} {row.get('validation_inputs')} vs encoder {encoded}")
    except Exception:  # noqa: BLE001
        record("manifest: validation_inputs == the encoder's reading of the class (V1's argument list)", False,
               traceback.format_exc()[-1200:])
    for name, inputs in CASES.items():
        compare(f"in-process {name}: outputs == V1", wants[name], await run_v2(v2_cls, inputs))
    compare("in-process unknown style: execution error == V1", wants["unknown style (execution)"],
            await run_v2(v2_cls, VALIDATION["unknown style"]))
    await check_validation("in-process", V1, v2_cls)

    session = await GuestSession("it-styler").start()
    facts["sandbox_kind"] = session.sandbox_kind

    class Backend:
        async def dispatch(self, plan, local_call, runtime=None):
            # As CloudExecutionBackend: core's own nodes run in the host; pack nodes go to the guest.
            if not str(getattr(plan, "node_module", "") or "").startswith("custom_nodes."):
                return await local_call()
            caps = set(plan.permissions or ())
            if getattr(plan, "input_mode", "refs") == "values":
                caps.add("raw")
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
            return await session.execute(plan, runtime, capabilities=frozenset(caps), tenant="it-styler")

    previous = _sdk.providers.execution_backend
    _sdk.providers.register_execution_backend(Backend())
    try:
        for name, inputs in CASES.items():
            compare(f"guest {name}: outputs == V1", wants[name], await run_v2(proxy, inputs))
        compare("guest unknown style: execution error == V1", wants["unknown style (execution)"],
                await run_v2(proxy, VALIDATION["unknown style"]))
        await check_validation("guest", V1, proxy)
    finally:
        _sdk.providers.register_execution_backend(previous)
        facts["guest_pid"] = session.last_guest_pid
        await session.kill()
    record("guest: out-of-process", facts.get("guest_pid") not in (None, os.getpid()), facts.get("guest_pid"))
    return facts


def main() -> int:
    try:
        facts = asyncio.run(run())
    except Exception:  # noqa: BLE001
        facts = {"error": traceback.format_exc()}
        record("session", False, facts["error"])
    failed = [c["check"] for c in checks if not c["ok"]]
    result = {"pack": "comfyui-itools", "repair": "r1 (Prompt Styler Extra follows the original)",
              "checks": checks, "failed": failed, "facts": facts, "verdict": "PASS" if not failed else "FAIL"}
    Path("/results/prompt_styler_extra.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({"verdict": result["verdict"], "failed": failed}))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
