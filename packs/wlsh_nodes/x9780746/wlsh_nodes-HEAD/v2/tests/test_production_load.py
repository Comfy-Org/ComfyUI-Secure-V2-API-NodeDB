"""Production load: every v2/secure-nodes.json row resolves the way the production guest resolves it (gate only).

The production guest imports ONLY the module a manifest row names. That module's ancestors are registered as bare
namespace packages, so the pack's __init__.py never runs (comfy_secure_nodes/guest/__init__.py, _import_pack).
The guest then looks the class up with getattr(module, class) and falls back to a scan of the module's vars by
__name__ (_execute_node). Each row is checked three ways, each with a fresh package name:

  A. bare namespace mount (a module object with __path__ = [v2], no __init__), then
     importlib.import_module(f"{pkg}.{row['module']}") and a STRICT getattr(module, row['class']) (no fallback).
     The class found must be the class the row describes: same node id, the same encoded schema, methods and
     validation inputs as the row. The package's __init__.py must not have run.
  B. the guest's own _import_pack, then the class lookup _execute_node does (copied below, because it is inline
     there).
  C. served, in a real guest process: the real loader (packdb.load_pack) builds the host proxies from the
     committed manifest; for each proxy, the plan is built the way core builds it (execution.py: node_type =
     proxy.__name__, node_module = proxy.__module__), with no inputs. A fresh guest serves each module's rows, so
     each module's import is the first in its guest. Refused rows must raise their own refusal message (the one the
     class raises in process); converted rows must reach their execute (a result or a named refusal). The guests
     start through _wlsh_sealed_guest_entry.py with its guest import audit on (pack code may import only the stdlib,
     the sealed guest lock or the declared profile); the result lists any import it refused.
Also checked: the frozen input names the refusal classes read without building a schema equal the schema's input
ids, for every frozen node.
Writes /results/production-load.json; exits 1 on any failure.
Run: run_in_gate.sh <Pack-HEAD with v2> <v2/tests> <out> test_production_load.py
"""
import asyncio
import copy
import importlib
import json
import os
import sys
import tempfile
import time
import traceback
import types
from collections import defaultdict
from pathlib import Path

CORE = Path(os.environ.get("COMFY_CORE_ROOT", "/core"))
sys.path[:0] = [str(CORE), "/overlay", str(Path(__file__).resolve().parent)]
from comfy.cli_args import args  # noqa: E402

args.cpu = True
from comfy_api.latest import _execution_metadata, _sdk  # noqa: E402
from comfy_execution.graph import DynamicPrompt  # noqa: E402
from comfy_secure_nodes import guest as guest_runtime  # noqa: E402
from comfy_secure_nodes import packmanifest  # noqa: E402
from comfy_secure_nodes.transport import wire  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402

import encode_manifest  # noqa: E402

PACK = Path(os.environ.get("PRODLOAD_PACK", "/pack"))
V2 = PACK / "v2"
RESULTS = Path(os.environ.get("PRODLOAD_RESULTS", "/results"))
GUEST_ENTRY = "/tests/_wlsh_sealed_guest_entry.py"
GUARD_LOG = Path(tempfile.mkdtemp(prefix="wlsh-prodload-")) / "import-guard.jsonl"
MANIFEST = json.loads((V2 / "secure-nodes.json").read_text())
ROWS = MANIFEST["nodes"]
CALL_TIMEOUT_S = 60


# --------------------------------------------------------------------------------------------------------------- #
# A. bare namespace mount + import_module + strict getattr
# --------------------------------------------------------------------------------------------------------------- #
def bare_mount(name: str, root: Path):
    package = types.ModuleType(name)
    package.__path__ = [str(root)]
    package.__package__ = name
    sys.modules[name] = package
    return package


def methods_of(cls):
    return {key: key in cls.__dict__ for key in ("check_lazy_status", "fingerprint_inputs", "validate_inputs")}


async def in_process_refusal(cls):
    try:
        await cls.execute()
    except NotImplementedError as error:
        return str(error)
    return None


def layer_a():
    pkg = "prodload_a"
    package = bare_mount(pkg, V2)
    rows, refusals = {}, {}
    for node_id, row in sorted(ROWS.items()):
        result = {"module": row["module"], "class": row["class"]}
        try:
            module = importlib.import_module(f"{pkg}.{row['module']}")
            cls = getattr(module, row["class"])  # strict: the production fallback scan is not used here
            schema = cls.GET_SCHEMA()
            result["node_id_matches"] = schema.node_id == node_id
            result["class_name_matches"] = cls.__name__ == row["class"]
            result["schema_matches_row"] = packmanifest.encode_schema(copy.deepcopy(schema)) == row["schema"]
            result["methods_match_row"] = methods_of(cls) == row["methods"]
            if row["methods"].get("validate_inputs"):
                result["validation_inputs_match_row"] = (packmanifest.encode_validation_inputs(cls)
                                                         == row.get("validation_inputs"))
            if row["class"].startswith("Refused_"):
                refusals[node_id] = asyncio.run(in_process_refusal(cls))
                result["refuses_in_process"] = refusals[node_id] is not None
            result["ok"] = all(value for key, value in result.items() if key not in ("module", "class"))
        except Exception:  # noqa: BLE001
            result.update(ok=False, error=traceback.format_exc()[-700:])
        rows[node_id] = result
    init_ran = hasattr(package, "NODE_CLASS_MAPPINGS") or hasattr(package, "__file__")
    runtime = sys.modules.get(f"{pkg}._secure_runtime")
    names = {}
    if runtime is not None and hasattr(runtime, "_input_names"):
        for node_id, entry in sorted(runtime.FROZEN.items()):
            names[node_id] = runtime._input_names(entry) == [item.id for item in runtime.schema_for(node_id).inputs]
    return {
        "rows": rows,
        "rows_ok": sum(1 for value in rows.values() if value["ok"]),
        "package_init_ran": init_ran,
        "modules_imported": sorted(key for key in sys.modules if key.startswith(pkg + ".")),
        "frozen_input_names_match_schema": sum(names.values()),
        "frozen_input_names_checked": len(names),
        "frozen_input_names_mismatched": sorted(key for key, value in names.items() if not value),
    }, refusals


# --------------------------------------------------------------------------------------------------------------- #
# B. the guest's own _import_pack + the lookup _execute_node does
# --------------------------------------------------------------------------------------------------------------- #
def execute_node_lookup(mod, node_class):
    """comfy_secure_nodes/guest/__init__.py _execute_node, after _import_pack (inline there)."""
    cls = getattr(mod, node_class, None)
    found_by = "getattr" if cls is not None else None
    if cls is None:
        for value in vars(mod).values():
            if isinstance(value, type) and value.__name__ == node_class:
                cls, found_by = value, "name scan"
                break
    if cls is None:
        raise AttributeError(f"{node_class} not found in {mod.__name__}")
    return cls, found_by


def layer_b():
    pkg = "prodload_b"
    rows = {}
    for node_id, row in sorted(ROWS.items()):
        result = {"module": row["module"], "class": row["class"]}
        try:
            mod = guest_runtime._import_pack(f"{pkg}.{row['module']}", str(V2 / f"{row['module']}.py"))
            cls, found_by = execute_node_lookup(mod, row["class"])
            result["found_by"] = found_by
            result["ok"] = found_by == "getattr" and cls.GET_SCHEMA().node_id == node_id
        except Exception:  # noqa: BLE001
            result.update(ok=False, error=traceback.format_exc()[-700:])
        rows[node_id] = result
    package = sys.modules.get(pkg)
    return {
        "rows": rows,
        "rows_ok": sum(1 for value in rows.values() if value["ok"]),
        "found_by_getattr": sum(1 for value in rows.values() if value.get("found_by") == "getattr"),
        "package_init_ran": hasattr(package, "NODE_CLASS_MAPPINGS") or hasattr(package, "__file__"),
    }


# --------------------------------------------------------------------------------------------------------------- #
# C. served: real loader proxies -> core-shaped plan -> a real guest process
# --------------------------------------------------------------------------------------------------------------- #
class SealedEntryGuestSession(GuestSession):
    """Start the guest the way production pack guests start: fixr1_compat applied before the guest main. The entry's
    guest import audit is on: pack code may import only the stdlib, the sealed guest lock or the declared profile."""

    def _guest_command(self, python):
        return [python, GUEST_ENTRY]

    def _adjust_guest_env(self, env):
        super()._adjust_guest_env(env)
        env["WLSH_GUARD_ROOT"] = str(self.guest_runtime_root)
        env["WLSH_GUARD_PROFILE"] = str(V2 / "pyproject.toml")
        env["WLSH_GUARD_LOG"] = str(GUARD_LOG)


async def serve(guest, proxy, prompt_id):
    permissions = tuple(proxy.SDK_PERMISSIONS)
    refs = _sdk.InProcessRefResolver()
    scope = _execution_metadata.ExecutionMetadataScope(prompt_id, DynamicPrompt({}), None, observe=True)
    scope.__enter__()
    try:
        plan = _sdk.ExecutionPlan(
            prompt_id=prompt_id, node_id="1", node_type=proxy.__name__, node_module=proxy.__module__,
            inputs={}, input_mode="refs" if proxy.SDK_REFS else "values", method="execute",
            permissions=permissions, prompt={}, extra_pnginfo=None, dynamic_prompt=DynamicPrompt({}),
            execution_metadata=scope)
        runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
        try:
            await asyncio.wait_for(guest.execute(plan, runtime, capabilities=permissions, tenant="prodload"),
                                   timeout=CALL_TIMEOUT_S)
            return {"outcome": "returned"}
        except wire.WireError as error:
            return {"outcome": "raised", "type": error.remote_type, "message": error.remote_message,
                    "phase": error.remote_phase}
    finally:
        scope.__exit__(None, None, None)


async def layer_c(refusals):
    mount = "custom_nodes.prodload_c"
    loaded = encode_manifest.load_snapshot((V2 / "secure-nodes.json").read_bytes(), mount)
    by_module = defaultdict(list)
    for node_id, proxy in sorted(loaded.node_mappings.items()):
        by_module[ROWS[node_id]["module"]].append((node_id, proxy))
    # The proxies' modules are the loader's host-side stubs; their __file__ is what crosses to the guest.
    shipped = {name: sys.modules[members[0][1].__module__].__file__ for name, members in by_module.items()}
    snapshot_v2 = Path(next(iter(shipped.values()))).parent
    rows, guests = {}, {}
    for module_name, members in sorted(by_module.items()):
        guest = await SealedEntryGuestSession(f"prodload:{module_name}", guest_runtime_root=snapshot_v2).start()
        pid = guest.pid
        t0 = time.perf_counter()
        try:
            for node_id, proxy in members:
                row = ROWS[node_id]
                result = {"module": row["module"], "class": row["class"],
                          "plan_node_type": proxy.__name__, "plan_node_module": proxy.__module__}
                try:
                    result.update(await serve(guest, proxy, f"prodload-{module_name}"))
                except Exception:  # noqa: BLE001
                    result.update(outcome="harness error", error=traceback.format_exc()[-700:])
                lookup_failed = (result.get("type") == "AttributeError" and "not found in" in result.get("message", ""))
                plan_ok = (proxy.__name__ == row["class"] and proxy.__module__ == f"{mount}.{row['module']}")
                if node_id in refusals:
                    reached = (result.get("type") == "NotImplementedError"
                               and result.get("message") == refusals[node_id])
                else:
                    reached = result.get("outcome") == "returned" or (
                        result.get("outcome") == "raised" and not lookup_failed and result.get("phase") != "import")
                result["ok"] = bool(plan_ok and reached and result.get("phase") != "import")
                rows[node_id] = result
        finally:
            guests[module_name] = {"rows": len(members), "guest_process": pid,
                                   "module_file_shipped": shipped[module_name],
                                   "seconds": round(time.perf_counter() - t0, 2)}
            await guest.kill()
    guard = [json.loads(line) for line in GUARD_LOG.read_text().splitlines()] if GUARD_LOG.exists() else []
    return {
        "rows": rows,
        "rows_ok": sum(1 for value in rows.values() if value["ok"]),
        "guest_import_audit": {"on": True, "refused_imports": sorted({g["module"] for g in guard}),
                               "refused_import_events": len(guard)},
        "refused_rows_raising_their_refusal": sum(1 for key, value in rows.items() if key in refusals and value["ok"]),
        "converted_rows_reaching_execute": sum(1 for key, value in rows.items()
                                               if key not in refusals and value["ok"]),
        "guests": guests,
        "proxies": len(loaded.node_mappings),
    }


def main():
    a, refusals = layer_a()
    b = layer_b()
    c = asyncio.run(layer_c(refusals))
    total = len(ROWS)
    doc = {
        "rows_total": total,
        "refused_rows": len(refusals),
        "A_bare_namespace_import_module_getattr": a,
        "B_guest_import_pack_and_lookup": b,
        "C_served_real_guest": c,
    }
    failures = {
        "A": sorted(key for key, value in a["rows"].items() if not value["ok"]),
        "B": sorted(key for key, value in b["rows"].items() if not value["ok"]),
        "C": sorted(key for key, value in c["rows"].items() if not value["ok"]),
    }
    doc["failures"] = failures
    doc["passed"] = (not any(failures.values()) and a["rows_ok"] == b["rows_ok"] == c["rows_ok"] == total
                     and not a["package_init_ran"] and not b["package_init_ran"]
                     and not a["frozen_input_names_mismatched"] and c["proxies"] == total)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "production-load.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    summary = {
        "rows_total": total, "refused_rows": len(refusals),
        "A_ok": a["rows_ok"], "A_package_init_ran": a["package_init_ran"], "A_modules": a["modules_imported"],
        "A_frozen_input_names": f"{a['frozen_input_names_match_schema']}/{a['frozen_input_names_checked']}",
        "B_ok": b["rows_ok"], "B_found_by_getattr": b["found_by_getattr"], "B_package_init_ran": b["package_init_ran"],
        "C_ok": c["rows_ok"], "C_refused_raising_refusal": c["refused_rows_raising_their_refusal"],
        "C_converted_reaching_execute": c["converted_rows_reaching_execute"], "C_guests": c["guests"],
        "C_guest_import_audit": c["guest_import_audit"],
        "passed": doc["passed"],
    }
    print(json.dumps(summary, indent=1, sort_keys=True))
    for layer, keys in failures.items():
        for node_id in keys[:5]:
            print("FAIL", layer, node_id, json.dumps(doc[{"A": "A_bare_namespace_import_module_getattr",
                                                          "B": "B_guest_import_pack_and_lookup",
                                                          "C": "C_served_real_guest"}[layer]]["rows"][node_id])[:600])
    return 0 if doc["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
