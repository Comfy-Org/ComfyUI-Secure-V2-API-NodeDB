"""Dependency profile (gate only): which rows need the pack's dependency profile, and what a guest does with and
without it.

1. Static map. The profile modules come from v2/pyproject.toml ``dependencies``. For each manifest module, the map
   records which profile modules it reaches. It is an AST walk over the v2 tree:
   - relative imports are resolved, and importing a submodule also imports its package __init__ files;
   - imports in a function body count only when that function runs ("call time");
   - imports guarded by an ImportError-family handler are optional;
   - module-level unguarded imports, followed transitively, are what an import of the row's module needs
     ("import time").
2. Served, in real guests started through _res4_profile_guest_entry.py, where profile modules resolve only from
   /deps:
   - every manifest row runs: a packdb proxy and a core-shaped plan, a fresh guest per module, no inputs;
   - both scheduler providers run through the guest's provider call: beta57 on a synthetic sigma table, and
     bong_tangent.
   The outcome is checked against the static map:
     --expect profile     (DEPS = the unpacked profile wheels): every row reaches its own code, and both providers
                          return schedules.
     --expect no-profile  (no DEPS): exactly the rows whose module needs a profile module at import time fail at
                          import with ModuleNotFoundError for that module; every other row behaves as with the
                          profile; a provider fails exactly when its function needs a profile module.
Writes /results/profile-load.json; exits 1 when the observed outcome differs from the expectation.
Run: [DEPS=<unpacked profile wheels>] run_in_gate.sh <Pack-HEAD with v2> <v2/tests> <out> test_profile_load.py
     --expect profile|no-profile
"""
import argparse
import ast
import asyncio
import copy
import json
import os
import re
import sys
import time
import tomllib
import traceback
from collections import defaultdict
from pathlib import Path

CORE = Path(os.environ.get("COMFY_CORE_ROOT", "/core"))
sys.path[:0] = [str(CORE), "/overlay", str(Path(__file__).resolve().parent)]
from comfy.cli_args import args  # noqa: E402

args.cpu = True
from comfy_api.latest import _execution_metadata, _sdk  # noqa: E402
from comfy_execution.graph import DynamicPrompt  # noqa: E402
from comfy_secure_nodes.transport import wire  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402

import encode_manifest  # noqa: E402

PACK = Path(os.environ.get("PROFILE_PACK", "/pack"))
V2 = PACK / "v2"
RESULTS = Path(os.environ.get("PROFILE_RESULTS", "/results"))
GUEST_ENTRY = str(Path(__file__).resolve().parent / "_res4_profile_guest_entry.py")
MANIFEST = json.loads((V2 / "secure-nodes.json").read_text())
ROWS = MANIFEST["nodes"]
CALL_TIMEOUT_S = 120
GUARDS = {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}


# --------------------------------------------------------------------------------------------------------------- #
# 1. Static map
# --------------------------------------------------------------------------------------------------------------- #
def profile_modules():
    pins = tomllib.loads((V2 / "pyproject.toml").read_text())["project"].get("dependencies", [])
    return sorted({re.split(r"[=<>!~;\[ ]", pin, maxsplit=1)[0].lower().replace("-", "_") for pin in pins})


def v2_modules():
    """Dotted names (relative to v2) of every module in the v2 tree, tests excluded."""
    modules = {}
    for path in sorted(V2.rglob("*.py")):
        relative = path.relative_to(V2)
        if relative.parts[0] == "tests":
            continue
        parts = list(relative.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        modules[".".join(parts)] = path
    return modules


def package_of(name):
    """The package a module's relative imports resolve against: itself for a package, else its parent."""
    if not name:
        return ""
    return name if (V2.joinpath(*name.split(".")) / "__init__.py").is_file() else name.rpartition(".")[0]


def with_parents(name, modules):
    """Importing a.b.c runs a/__init__ and a/b/__init__ first (when they exist)."""
    parts = name.split(".")
    found = []
    for index in range(1, len(parts) + 1):
        candidate = ".".join(parts[:index])
        if candidate in modules:
            found.append(candidate)
    return found


class ImportCollector(ast.NodeVisitor):
    """Each import with: the enclosing scope (module/function) and whether an ImportError-family handler guards it."""

    def __init__(self):
        self.records = []
        self.function_depth = 0
        self.guard_depth = 0

    def _scope(self):
        return "call" if self.function_depth else "import"

    def visit_FunctionDef(self, node):
        self.function_depth += 1
        self.generic_visit(node)
        self.function_depth -= 1

    visit_AsyncFunctionDef = visit_FunctionDef
    visit_Lambda = visit_FunctionDef

    def visit_Try(self, node):
        guarded = any(
            handler.type is None
            or (isinstance(handler.type, ast.Name) and handler.type.id in GUARDS)
            or (isinstance(handler.type, ast.Tuple) and any(isinstance(e, ast.Name) and e.id in GUARDS
                                                          for e in handler.type.elts))
            for handler in node.handlers)
        if guarded:
            self.guard_depth += 1
        for statement in node.body:
            self.visit(statement)
        if guarded:
            self.guard_depth -= 1
        for part in (node.handlers, node.orelse, node.finalbody):
            for statement in part:
                self.visit(statement)

    visit_TryStar = visit_Try

    def visit_Import(self, node):
        for alias in node.names:
            self.records.append({"level": 0, "module": alias.name, "names": [], "scope": self._scope(),
                                 "guarded": bool(self.guard_depth), "line": node.lineno})

    def visit_ImportFrom(self, node):
        self.records.append({"level": node.level, "module": node.module or "", "names": [a.name for a in node.names],
                             "scope": self._scope(), "guarded": bool(self.guard_depth), "line": node.lineno})


def edges_of(name, path, modules):
    """(target, kind, scope, guarded, line) for one module; kind 'internal' (a v2 module) or 'external' (top level)."""
    collector = ImportCollector()
    collector.visit(ast.parse(path.read_text(), filename=str(path)))
    package = package_of(name)
    out = []
    for record in collector.records:
        if record["level"] == 0:
            top = record["module"].split(".")[0]
            out.append((top, "external", record["scope"], record["guarded"], record["line"]))
            continue
        base = package.split(".") if package else []
        if record["level"] > 1:
            base = base[:len(base) - (record["level"] - 1)]
        target = ".".join(base + ([record["module"]] if record["module"] else []))
        targets = with_parents(target, modules) if target else []
        for imported in record["names"]:
            child = f"{target}.{imported}" if target else imported
            if child in modules:
                targets.append(child)
        for internal in dict.fromkeys(targets):
            out.append((internal, "internal", record["scope"], record["guarded"], record["line"]))
    return out


def static_map(profile):
    modules = v2_modules()
    edges = {name: edges_of(name, path, modules) for name, path in modules.items()}

    def reach(start, call_time):
        """Profile modules reachable from start through unguarded imports: module-level ones only (import time), or
        also those in function bodies anywhere along the way (call time, an over-approximation)."""
        found, seen, stack = {}, set(), [start]
        while stack:
            name = stack.pop()
            if name in seen:
                continue
            seen.add(name)
            for target, kind, scope, guarded, line in edges.get(name, ()):
                if guarded or (scope != "import" and not call_time):
                    continue
                if kind == "external":
                    if target in profile:
                        found.setdefault(target, []).append(f"{name}:{line}")
                else:
                    stack.append(target)
        return found

    def externals(start):
        """Every non-stdlib top-level module an import of start reaches (module-level, unguarded), with sites."""
        found, seen, stack = {}, set(), [start]
        while stack:
            name = stack.pop()
            if name in seen:
                continue
            seen.add(name)
            for target, kind, scope, guarded, line in edges.get(name, ()):
                if guarded or scope != "import":
                    continue
                if kind == "internal":
                    stack.append(target)
                elif target not in sys.stdlib_module_names:
                    found.setdefault(target, []).append(f"{name}:{line}")
        return found

    per_module = {}
    for module in sorted({row["module"] for row in ROWS.values()}):
        per_module[module] = {"import_time": reach(module, False), "call_time": reach(module, True),
                              "externals_at_import": {k: v[:3] for k, v in sorted(externals(module).items())}}
    guarded = sorted({f"{name}:{line} {target}" for name, items in edges.items()
                      for target, kind, scope, is_guarded, line in items
                      if kind == "external" and is_guarded and target not in profile
                      and target not in sys.stdlib_module_names})
    return per_module, guarded, edges


def provider_needs(profile, edges):
    """Profile modules a provider function imports in its own body (the provider module is imported by name)."""
    out = {}
    for provider in MANIFEST.get("scheduler_providers", []):
        source = (V2 / f"{provider['module']}.py").read_text()
        tree = ast.parse(source)
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name == provider["function"])
        names = set()
        for node in ast.walk(function):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
        out[provider["name"]] = sorted(names & set(profile))
    return out


# --------------------------------------------------------------------------------------------------------------- #
# 2. Served
# --------------------------------------------------------------------------------------------------------------- #
class ProfileEntryGuestSession(GuestSession):
    def _guest_command(self, python):
        return [python, GUEST_ENTRY]


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
            await asyncio.wait_for(guest.execute(plan, runtime, capabilities=permissions, tenant="profile"),
                                   timeout=CALL_TIMEOUT_S)
            return {"outcome": "returned"}
        except wire.WireError as error:
            return {"outcome": "raised", "type": error.remote_type, "message": error.remote_message[:300],
                    "phase": error.remote_phase}
    finally:
        scope.__exit__(None, None, None)


def sigma_table():
    """A synthetic, strictly increasing 1000-entry SD-style sigma table (float64 values as the projection gives)."""
    import torch
    betas = torch.linspace(0.00085 ** 0.5, 0.012 ** 0.5, 1000, dtype=torch.float64) ** 2
    alphas = torch.cumprod(1.0 - betas, dim=0)
    return (((1 - alphas) / alphas) ** 0.5).tolist()


async def served(snapshot_name):
    loaded = encode_manifest.load_snapshot((V2 / "secure-nodes.json").read_bytes(), snapshot_name)
    by_module = defaultdict(list)
    for node_id, proxy in sorted(loaded.node_mappings.items()):
        by_module[ROWS[node_id]["module"]].append((node_id, proxy))
    shipped = {name: sys.modules[members[0][1].__module__].__file__ for name, members in by_module.items()}
    snapshot_v2 = Path(next(iter(shipped.values()))).parent
    rows, guests = {}, {}
    for module_name, members in sorted(by_module.items()):
        guest = await ProfileEntryGuestSession(f"profile:{module_name}", guest_runtime_root=snapshot_v2).start()
        t0 = time.perf_counter()
        try:
            for node_id, proxy in members:
                try:
                    rows[node_id] = {"module": module_name, **await serve(guest, proxy, f"profile-{module_name}")}
                except Exception:  # noqa: BLE001
                    rows[node_id] = {"module": module_name, "outcome": "harness error",
                                     "error": traceback.format_exc()[-600:]}
        finally:
            guests[module_name] = {"rows": len(members), "seconds": round(time.perf_counter() - t0, 2),
                                   "stderr_profile_lines": sorted({line for line in (guest.last_stderr or "")
                                                                   .splitlines() if "res4lyf profile:" in line})}
            await guest.kill()
    providers = {}
    for provider in loaded.scheduler_providers:
        guest = await ProfileEntryGuestSession(f"profile:provider:{provider.name}",
                                               guest_runtime_root=snapshot_v2).start()
        projection = sigma_table() if provider.projection == "model_sigmas" else None
        try:
            result = await asyncio.wait_for(guest.invoke_scheduler_provider(
                module_name=provider.module_name, module_file=str(provider.module_file),
                function_name=provider.function, projection=projection, steps=8,
                config=copy.deepcopy(provider.config)), timeout=CALL_TIMEOUT_S)
            values = result.get("sigmas", result) if isinstance(result, dict) else result
            providers[provider.name] = {"outcome": "returned", "length": len(values) if values is not None else None}
        except wire.WireError as error:
            providers[provider.name] = {"outcome": "raised", "type": error.remote_type,
                                        "message": error.remote_message[:300], "phase": error.remote_phase}
        except Exception as error:  # noqa: BLE001
            providers[provider.name] = {"outcome": "harness error", "error": f"{type(error).__name__}: {error}"[:300]}
        finally:
            providers[provider.name]["stderr_profile_lines"] = sorted(
                {line for line in (guest.last_stderr or "").splitlines() if "res4lyf profile:" in line})
            await guest.kill()
    return rows, guests, providers


def import_failure(result, profile):
    """The profile module named by an import-phase ModuleNotFoundError, else None."""
    if result.get("outcome") != "raised" or result.get("type") != "ModuleNotFoundError":
        return None
    match = re.search(r"No module named '([A-Za-z0-9_]+)", result.get("message", ""))
    return match.group(1) if match and match.group(1) in profile else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expect", choices=("profile", "no-profile"), required=True)
    expect = parser.parse_args().expect
    profile = profile_modules()
    deps_mounted = Path("/deps").is_dir()
    per_module, guarded_optional, edges = static_map(set(profile))
    needs = provider_needs(set(profile), edges)
    rows, guests, providers = asyncio.run(served(f"custom_nodes.profile_{expect.replace('-', '_')}"))
    verdicts = {}
    for node_id, result in sorted(rows.items()):
        module = ROWS[node_id]["module"]
        needed = sorted(per_module[module]["import_time"])
        failed_on = import_failure(result, profile)
        loaded = result.get("phase") != "import" and result.get("outcome") in ("returned", "raised")
        if expect == "profile" or not needed:
            ok = loaded
            expected = "loads and reaches its own code"
        else:
            ok = failed_on in needed and result.get("phase") == "import"
            expected = f"fails at import: ModuleNotFoundError for one of {needed}"
        verdicts[node_id] = {"ok": ok, "expected": expected, "import_time_needs": needed, **result}
    provider_verdicts = {}
    for name, result in providers.items():
        needed = needs.get(name, [])
        if expect == "profile" or not needed:
            ok = result.get("outcome") == "returned"
            expected = "returns a schedule"
        else:
            ok = (result.get("outcome") == "raised" and result.get("type") == "ModuleNotFoundError"
                  and any(f"'{n}'" in result.get("message", "") for n in needed))
            expected = f"fails: ModuleNotFoundError for one of {needed}"
        provider_verdicts[name] = {"ok": ok, "expected": expected, "needs_at_call": needed, **result}
    rows_needing = sorted(n for n in ROWS if per_module[ROWS[n]["module"]]["import_time"])
    doc = {
        "expect": expect,
        "deps_mounted": deps_mounted,
        "profile_modules": profile,
        "static_map": per_module,
        "optional_guarded_imports_outside_profile": guarded_optional,
        "provider_needs_at_call": needs,
        "rows_total": len(ROWS),
        "rows_needing_profile_at_import": rows_needing,
        "rows_loading_without_profile": len(ROWS) - len(rows_needing),
        "rows": verdicts,
        "providers": provider_verdicts,
        "guests": guests,
        "rows_ok": sum(1 for v in verdicts.values() if v["ok"]),
        "providers_ok": sum(1 for v in provider_verdicts.values() if v["ok"]),
    }
    doc["passed"] = (doc["rows_ok"] == len(ROWS) and doc["providers_ok"] == len(provider_verdicts)
                     and deps_mounted == (expect == "profile"))
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "profile-load.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    summary = {key: doc[key] for key in ("expect", "deps_mounted", "profile_modules", "rows_total",
                                         "rows_needing_profile_at_import", "rows_loading_without_profile",
                                         "rows_ok", "providers_ok", "provider_needs_at_call", "passed")}
    summary["static_map"] = {m: {k: sorted(v) for k, v in d.items()} for m, d in per_module.items()}
    summary["failed_rows"] = {n: {k: v.get(k) for k in ("type", "message", "phase", "expected")}
                              for n, v in verdicts.items() if not v["ok"] or v.get("phase") == "import"}
    summary["providers"] = {n: {k: v.get(k) for k in ("ok", "outcome", "type", "message", "length")}
                            for n, v in provider_verdicts.items()}
    summary["profile_lines"] = sorted({line for g in guests.values() for line in g["stderr_profile_lines"]}
                                      | {line for p in provider_verdicts.values()
                                         for line in p.get("stderr_profile_lines", [])})
    print(json.dumps(summary, indent=1, sort_keys=True))
    return 0 if doc["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
