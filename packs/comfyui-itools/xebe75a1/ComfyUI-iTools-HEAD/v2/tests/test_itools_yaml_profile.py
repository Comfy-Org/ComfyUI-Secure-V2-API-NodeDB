"""iTools dependency profile (NED profile r1): pyyaml 6.0.3, as a production guest sees it (gate).

    DEPS=<folder holding the unpacked pyyaml-6.0.3 cp313 manylinux wheel> \
        run_in_gate.sh <snapshot dir xebe75a1, or the pack folder> <.../v2/tests> <results> test_itools_yaml_profile.py

A production guest imports only its sealed lock, the pack's runtime base and its declared dependency profile, not
Core's requirements, and base 0cd9adec has no pyyaml. v2/nodes.py imports yaml when it loads, so without a profile
no iTools row loads. v2/pyproject.toml now pins pyyaml==6.0.3 for the profile. Everywhere below, yaml can come only
from /deps, the pinned wheel; the gate image's own copy is refused.
1. Production load, per guest base (comfy_api from /bases, Core blocked): without /deps every row fails with
   ModuleNotFoundError for yaml; with /deps all rows load the way the guest loads them (no v2/__init__.py), match
   their manifest rows, and yaml is the copy under /deps.
2. Real guest (fixr1_compat applied, yaml only from /deps; _yaml_profile_guest_entry.py): the Prompt Styler cases of
   test_itools_prompt_styler.py equal the original's outputs; the same guest without /deps fails with
   ModuleNotFoundError for yaml.
Writes /results/yaml_profile.json; exits 1 on any failed check.
"""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path[:0] = ["/core", "/overlay", "/tests"]

import test_itools_prompt_styler as S  # noqa: E402  (its setup and helpers; its main() is not run)
from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402

DEPS = Path("/deps")
checks = []


def record(name, ok, detail=None):
    checks.append({"check": name, "ok": bool(ok), "detail": None if ok else str(detail)[:1500]})
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": {str(detail)[:400]}"), flush=True)


CHILD = r'''
import importlib.abc, importlib.machinery, importlib.util, json, os, sys, types
base, v2, rows_path, with_profile = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] == "1"
BLOCKED = {"comfy", "comfy_extras", "comfy_execution", "folder_paths", "nodes", "server", "execution",
           "comfy_secure_nodes"}
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        top = fullname.split(".")[0]
        if top in BLOCKED:
            raise ModuleNotFoundError(f"blocked in the guest emulation: {fullname}", name=fullname)
        if top in ("yaml", "_yaml"):
            spec = importlib.machinery.PathFinder.find_spec(fullname, path)
            locations = [spec.origin or ""] + list(spec.submodule_search_locations or []) if spec else []
            if spec is None or not all(str(l).startswith("/deps") for l in locations if l):
                raise ModuleNotFoundError(f"No module named {fullname!r}", name=fullname)
            return spec
        return None
sys.meta_path.insert(0, Guard())
sys.path.insert(0, os.path.join(base, "common-site-packages"))
if with_profile:
    sys.path.insert(0, "/deps")
import comfy_api
rows = json.load(open(rows_path))
mount = "custom_nodes.itools_profile_emulation"
def load_module(module_name, module_file):
    if module_name in sys.modules:
        return sys.modules[module_name]
    parts = module_name.split(".")
    depth_dir = os.path.dirname(module_file)
    for i in range(len(parts) - 1, 0, -1):
        name = ".".join(parts[:i])
        if name not in sys.modules:
            parent = types.ModuleType(name); parent.__path__ = [depth_dir]; parent.__package__ = name
            sys.modules[name] = parent
        depth_dir = os.path.dirname(depth_dir)
    spec = importlib.util.spec_from_file_location(module_name, module_file)
    mod = importlib.util.module_from_spec(spec); mod.__package__ = ".".join(parts[:-1])
    sys.modules[module_name] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop(module_name, None); raise
    return mod
out = {"rows": {}}
for node_id, row in rows.items():
    try:
        cls = getattr(load_module(f"{mount}.{row['module']}", os.path.join(v2, row["module"] + ".py")), row["class"])
        schema = cls.GET_SCHEMA()
        out["rows"][node_id] = {"node_id": schema.node_id, "sdk_refs": bool(getattr(cls, "SDK_REFS", False)),
                                "permissions": list(getattr(cls, "SDK_PERMISSIONS", ())),
                                "methods": {k: k in cls.__dict__ for k in ("validate_inputs", "fingerprint_inputs",
                                                                          "check_lazy_status")}}
    except BaseException as error:
        out["rows"][node_id] = {"error": f"{type(error).__name__}: {error}"}
yaml_module = sys.modules.get("yaml")
out["yaml_file"] = getattr(yaml_module, "__file__", None)
out["yaml_version"] = getattr(yaml_module, "__version__", None)
print(json.dumps(out))
'''


def production_load(head: Path) -> dict:
    v2 = head / "v2"
    rows = json.loads((v2 / "secure-nodes.json").read_text())["nodes"]
    rows_path = Path("/tmp/itools-profile-rows.json")
    rows_path.write_text(json.dumps(rows))
    out = {}
    for base in sorted(p for p in Path("/bases").iterdir() if (p / "common-site-packages" / "comfy_api").is_dir()):
        tag = base.name[:8]
        for with_profile in (False, True):
            proc = subprocess.run([sys.executable, "-I", "-c", CHILD, str(base), str(v2), str(rows_path),
                                   "1" if with_profile else "0"], capture_output=True, text=True, timeout=300,
                                  cwd="/tmp")
            label = f"[{tag}] {'with' if with_profile else 'without'} the profile"
            if proc.returncode != 0:
                record(f"{label}: production load ran", False, proc.stderr[-800:])
                continue
            result = json.loads(proc.stdout.strip().splitlines()[-1])
            out[label] = result
            errors = {k: v["error"] for k, v in result["rows"].items() if "error" in v}
            if not with_profile:
                record(f"{label}: every row fails for lack of yaml ({len(rows)} rows)",
                       len(errors) == len(rows) and all("yaml" in e for e in errors.values()), errors)
                continue
            mismatched = {}
            for node_id, row in rows.items():
                got = result["rows"][node_id]
                want = {"node_id": node_id, "sdk_refs": row["sdk_refs"], "permissions": row["permissions"],
                        "methods": row["methods"]}
                if "error" in got or {k: got.get(k) for k in want} != want:
                    mismatched[node_id] = {"got": got, "want": want}
            record(f"{label}: all {len(rows)} rows load as the guest loads them and match their rows", not mismatched,
                   mismatched)
            record(f"{label}: yaml is the profile's copy under /deps (pyyaml 6.0.3)",
                   str(result.get("yaml_file", "")).startswith("/deps/") and result.get("yaml_version") == "6.0.3",
                   [result.get("yaml_file"), result.get("yaml_version")])
    return out


def session_class(with_profile: bool):
    class ProfileGuestSession(GuestSession):
        def _guest_command(self, python):
            return [python, "/tests/_yaml_profile_guest_entry.py"]

        def _adjust_guest_env(self, env):
            super()._adjust_guest_env(env)
            if with_profile:
                env["PYTHONPATH"] = os.pathsep.join(p for p in (str(DEPS), env.get("PYTHONPATH", "")) if p)

        def _extra_ro_paths(self):
            return list(super()._extra_ro_paths()) + ([str(DEPS)] if with_profile else [])
    return ProfileGuestSession


async def guest_runs(head: Path) -> dict:
    for name, setter in (("temp", S.folder_paths.set_temp_directory), ("output", S.folder_paths.set_output_directory)):
        Path(f"/tmp/it-{name}").mkdir(parents=True, exist_ok=True)
        setter(f"/tmp/it-{name}")
    V1 = S.original_class(head)
    loaded = packdb.load_pack(S.snapshot_dir(), mount_name="custom_nodes.it_profile_proxy",
                              pack_id="comfyui-itools/xebe75a1")
    for folder, directory in loaded.asset_directories.items():
        S.folder_paths.add_model_folder_path(folder, str(directory))
    proxy = loaded.node_mappings[S.NODE]
    facts = {}
    for with_profile in (True, False):
        session = await session_class(with_profile)(f"it-profile-{int(with_profile)}").start()

        class Backend:
            async def dispatch(self, plan, local_call, runtime=None):
                if not str(getattr(plan, "node_module", "") or "").startswith("custom_nodes."):
                    return await local_call()
                caps = set(plan.permissions or ())
                if getattr(plan, "input_mode", "refs") == "values":
                    caps.add("raw")
                    plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
                return await session.execute(plan, runtime, capabilities=frozenset(caps), tenant="it-profile")

        previous = _sdk.providers.execution_backend
        _sdk.providers.register_execution_backend(Backend())
        try:
            if with_profile:
                for name, inputs in S.CASES.items():
                    want, got = S.run_v1(V1, inputs), await S.run_v2(proxy, inputs)
                    same = (want[0] == got[0] == "ok" and len(got[1]) == 3
                            and all(type(a) is type(b) and a == b for a, b in zip(want[1], got[1])))
                    record(f"guest with the profile, {name}: outputs == the original's", same, [want, got])
            else:
                got = await S.run_v2(proxy, S.CASES["none with text"])
                record("guest without the profile: the node fails with ModuleNotFoundError for yaml",
                       got[0] == "error" and "yaml" in got[1], got)
        finally:
            _sdk.providers.register_execution_backend(previous)
            facts[f"guest_pid_{int(with_profile)}"] = session.last_guest_pid
            await session.kill()
    record("guest: out-of-process", facts.get("guest_pid_1") not in (None, os.getpid()), facts)
    return facts


def main() -> int:
    head = S.pack_head()
    record("DEPS: the pinned wheel is mounted at /deps",
           (DEPS / "yaml" / "__init__.py").is_file() and (DEPS / "pyyaml-6.0.3.dist-info").is_dir(),
           sorted(p.name for p in DEPS.iterdir()) if DEPS.is_dir() else "no /deps")
    pyproject = (head / "v2" / "pyproject.toml").read_text(encoding="utf-8")
    record("v2/pyproject.toml pins pyyaml==6.0.3", 'dependencies = ["pyyaml==6.0.3"]' in pyproject, pyproject)
    loads = production_load(head)
    facts = asyncio.run(guest_runs(head))
    out = {"loads": loads, "facts": facts, "checks": checks, "failed": [c["check"] for c in checks if not c["ok"]]}
    Path("/results").mkdir(parents=True, exist_ok=True)
    Path("/results/yaml_profile.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(json.dumps({"failed": out["failed"]}, indent=1))
    return 1 if out["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
