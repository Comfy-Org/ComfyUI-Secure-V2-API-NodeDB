"""A pack's declared dependency profile, as a production guest sees it (gate). Configured by
dependency_profile.json beside this file: the pack, the pinned modules and versions, the rows that need them when
they load, and the guest cases.

    DEPS=<folder holding the profile's unpacked, pinned wheels> \
        run_in_gate.sh <snapshot dir, or the pack folder> <.../v2/tests> <results> test_dependency_profile.py

A production guest imports only its sealed lock, the pack's runtime base and its declared profile, not Core's
requirements. In both the guest and the load emulation below, a profile module can come only from /deps (the
pinned wheels), and the modules the guest bases lack (BASE_ABSENT: scipy, torchvision, tqdm, yaml, cv2) can come
only from /deps as well, so they are missing unless the profile provides them. The gate image's own copies are
refused.
1. Pins: v2/pyproject.toml declares exactly the configured pins, and /deps holds those versions.
2. Production load, per guest base (comfy_api from /bases, Core blocked): without /deps exactly the configured rows
   fail to load, each for lack of a profile module, and every other row loads. With /deps every row loads the way
   the guest loads it: module file under a namespace parent (no v2/__init__.py), class looked up by name and then
   by __name__. Its schema builds, its SDK_REFS, SDK_PERMISSIONS and overridden methods match its manifest row, and
   each profile module is the /deps copy.
3. Real guest (fixr1_compat applied; _profile_guest_entry.py): each configured case equals the pristine upstream
   node run in-process, where the gate's own copies serve. A configured token output is compared field by field
   with the upstream object. The same guest without /deps fails for lack of a profile module. Negative control: a
   changed output is caught.
Writes /results/dependency_profile.json; exits 1 on any failed check.
"""

import asyncio
import importlib
import json
import os
import shutil
import subprocess
import sys
import types
from pathlib import Path

sys.path[:0] = ["/core", "/overlay"]

from comfy.cli_args import args  # noqa: E402

args.cpu = True

import comfy.samplers  # noqa: E402,F401
import execution  # noqa: E402
import folder_paths  # noqa: E402
import torch  # noqa: E402
from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402

HERE = Path(__file__).resolve().parent
CONFIG = json.loads((HERE / "dependency_profile.json").read_text(encoding="utf-8"))
DEPS = Path("/deps")
MODULES = sorted(CONFIG["pins"])
BASE_ABSENT = ("scipy", "torchvision", "tqdm", "yaml", "_yaml", "cv2")
DEPS_ONLY = sorted(set(MODULES) | set(BASE_ABSENT))
checks = []


def record(name, ok, detail=None):
    checks.append({"check": name, "ok": bool(ok), "detail": None if ok else str(detail)[:1500]})
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": {str(detail)[:400]}"), flush=True)


def names_module(error: str, module: str) -> bool:
    """The error names the module (or one of its submodules) as the one that is missing."""
    return f"'{module}'" in error or f"'{module}." in error


def pack_head() -> Path:
    root = Path("/pack")
    return root if (root / "v2").is_dir() else root / CONFIG["folder"]


def snapshot_dir() -> Path:
    root = Path("/pack")
    if not (root / "v2").is_dir():
        return root
    snap = Path("/tmp/profile-snapshot") / CONFIG["pack"] / CONFIG["key"]
    if not (snap / CONFIG["folder"]).is_dir():
        shutil.copytree(root, snap / CONFIG["folder"], ignore=shutil.ignore_patterns("__pycache__"))
    return snap


CHILD = r'''
import importlib.abc, importlib.machinery, importlib.util, json, os, sys, types
base, v2, rows_path, with_profile = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] == "1"
PROFILE, DEPS_ONLY = sys.argv[5].split(","), set(sys.argv[6].split(","))
BLOCKED = {"comfy", "comfy_extras", "comfy_execution", "folder_paths", "nodes", "server", "execution",
           "comfy_secure_nodes"}
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in BLOCKED:
            raise ModuleNotFoundError(f"blocked in the guest emulation: {fullname}", name=fullname)
        return None
class DepsOnlyFileFinder(importlib.machinery.FileFinder):
    # Outside /deps the DEPS_ONLY modules are absent, to imports and to importlib.util.find_spec alike.
    def find_spec(self, fullname, target=None):
        if fullname.split(".")[0] in DEPS_ONLY and not (self.path == "/deps" or self.path.startswith("/deps/")):
            return None
        return super().find_spec(fullname, target)
LOADERS = [(importlib.machinery.ExtensionFileLoader, importlib.machinery.EXTENSION_SUFFIXES),
           (importlib.machinery.SourceFileLoader, importlib.machinery.SOURCE_SUFFIXES),
           (importlib.machinery.SourcelessFileLoader, importlib.machinery.BYTECODE_SUFFIXES)]
sys.path_hooks.insert(0, DepsOnlyFileFinder.path_hook(*LOADERS))
sys.path_importer_cache.clear()
sys.meta_path.insert(0, Guard())
sys.path.insert(0, os.path.join(base, "common-site-packages"))
if with_profile:
    sys.path.insert(0, "/deps")
import comfy_api
rows = json.load(open(rows_path))
mount = "custom_nodes.profile_emulation"
def module_file(module):
    base_path = os.path.join(v2, *module.split("."))
    return base_path + ".py" if os.path.isfile(base_path + ".py") else os.path.join(base_path, "__init__.py")
def load_module(module_name, path):
    if module_name in sys.modules:
        return sys.modules[module_name]
    parts = module_name.split(".")
    depth_dir = os.path.dirname(path) if not path.endswith("__init__.py") else os.path.dirname(os.path.dirname(path))
    for i in range(len(parts) - 1, 0, -1):
        name = ".".join(parts[:i])
        if name not in sys.modules:
            parent = types.ModuleType(name); parent.__path__ = [depth_dir]; parent.__package__ = name
            sys.modules[name] = parent
        depth_dir = os.path.dirname(depth_dir)
    if path.endswith("__init__.py"):
        spec = importlib.util.spec_from_file_location(module_name, path, submodule_search_locations=[os.path.dirname(path)])
    else:
        spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    if not path.endswith("__init__.py"):
        mod.__package__ = ".".join(parts[:-1])
    sys.modules[module_name] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop(module_name, None); raise
    return mod
def find_class(mod, name):
    # The guest's own lookup: the module attribute, else a class whose __name__ is the manifest's class name.
    cls = getattr(mod, name, None)
    if cls is None:
        cls = next((v for v in vars(mod).values() if isinstance(v, type) and v.__name__ == name), None)
    if cls is None:
        raise AttributeError(f"{name} not found in {mod.__name__}")
    return cls
def overridden(cls, name):
    owner = next((k for k in cls.__mro__ if name in vars(k)), None)
    return owner is not None and not str(getattr(owner, "__module__", "")).startswith("comfy_api")
out = {"rows": {}}
for node_id, row in rows.items():
    try:
        cls = find_class(load_module(f"{mount}.{row['module']}", module_file(row["module"])), row["class"])
        schema = cls.GET_SCHEMA()
        permissions = list(getattr(cls, "SDK_PERMISSIONS", ()))
        if getattr(cls, "SDK_REQUIRED_WEIGHTS", ()) and "models.download" not in permissions:
            permissions.append("models.download")  # as the encoder and the host's proxy add it
        out["rows"][node_id] = {"schema_node_id": schema.node_id,
                                "sdk_refs": bool(getattr(cls, "SDK_REFS", False)),
                                "permissions": permissions,
                                "methods": {k: overridden(cls, k) for k in ("check_lazy_status", "fingerprint_inputs",
                                                                            "validate_inputs")}}
    except BaseException as error:
        out["rows"][node_id] = {"error": f"{type(error).__name__}: {error}"}
out["module_files"] = {m: getattr(sys.modules.get(m), "__file__", None) for m in sorted(PROFILE)}
print(json.dumps(out))
'''


def production_load(head: Path):
    v2 = head / "v2"
    rows = json.loads((v2 / "secure-nodes.json").read_text())["nodes"]
    rows_path = Path("/tmp/profile-rows.json")
    rows_path.write_text(json.dumps(rows))
    expected_failures = set(CONFIG["load_fail_rows"])
    out = {}
    for base in sorted(p for p in Path("/bases").iterdir() if (p / "common-site-packages" / "comfy_api").is_dir()):
        tag = base.name[:8]
        for with_profile in (False, True):
            proc = subprocess.run([sys.executable, "-I", "-c", CHILD, str(base), str(v2), str(rows_path),
                                   "1" if with_profile else "0", ",".join(MODULES), ",".join(DEPS_ONLY)],
                                  capture_output=True, text=True, timeout=600, cwd="/tmp")
            label = f"[{tag}] {'with' if with_profile else 'without'} the profile"
            if proc.returncode != 0:
                record(f"{label}: production load ran", False, proc.stderr[-800:])
                continue
            result = json.loads(proc.stdout.strip().splitlines()[-1])
            out[label] = {"errors": {k: v["error"] for k, v in result["rows"].items() if "error" in v},
                          "module_files": result["module_files"]}
            errors = out[label]["errors"]
            if not with_profile:
                missing = {k: e for k, e in errors.items() if any(names_module(e, m) for m in MODULES)}
                out[label]["missing_by_module"] = {m: sorted(k for k, e in missing.items() if names_module(e, m))
                                                   for m in MODULES}
                record(f"{label}: exactly the {len(expected_failures)} configured rows fail, for lack of a profile "
                       "module, and the other rows load",
                       set(errors) == expected_failures and set(missing) == expected_failures,
                       {"unexpected": sorted(set(errors) - expected_failures),
                        "not_failing": sorted(expected_failures - set(errors)),
                        "other_errors": {k: e for k, e in errors.items() if k not in missing}})
                continue
            mismatched = {}
            for node_id, row in rows.items():
                got = result["rows"][node_id]
                want = {"sdk_refs": row["sdk_refs"], "permissions": row["permissions"], "methods": row["methods"]}
                if "error" in got or {k: got.get(k) for k in want} != want:
                    mismatched[node_id] = {"got": got, "want": want}
            record(f"{label}: all {len(rows)} rows load as the guest loads them, build their schema and match their "
                   "rows (SDK_REFS, SDK_PERMISSIONS, overridden methods)", not mismatched,
                   dict(list(mismatched.items())[:5]))
            loaded_from = {m: f for m, f in result["module_files"].items() if f is not None}
            record(f"{label}: every profile module that loaded is the /deps copy",
                   all(str(f).startswith("/deps/") for f in loaded_from.values()), loaded_from)
    return out


def materialize(value):
    if isinstance(value, dict) and value.get("__tensor__"):
        return torch.rand(*value["shape"], generator=torch.Generator().manual_seed(value.get("seed", 0)))
    if isinstance(value, dict) and value.get("__mask__"):
        return (torch.rand(*value["shape"], generator=torch.Generator().manual_seed(value.get("seed", 0))) > 0.5).float()
    return value


def same(a, b):
    if isinstance(a, torch.Tensor) or isinstance(b, torch.Tensor):
        return (isinstance(a, torch.Tensor) and isinstance(b, torch.Tensor) and a.dtype == b.dtype
                and tuple(a.shape) == tuple(b.shape) and torch.equal(a.cpu(), b.cpu()))
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return list(a) == list(b) and all(same(a[k], b[k]) for k in a)
    return type(a) is type(b) and a == b


def as_token(value):
    """The upstream object's fields, which the converted node carries as a plain token dict."""
    return dict(vars(value)) if hasattr(value, "__dict__") and not isinstance(value, (type, torch.Tensor)) else value


def tampered(value):
    if isinstance(value, torch.Tensor):
        changed = value.clone()
        changed.view(-1)[0] += 0.5
        return changed
    if isinstance(value, bool):
        return not value
    if isinstance(value, (int, float)):
        return value + 1
    if isinstance(value, dict) and value:
        key = next(iter(value))
        return {**value, key: tampered(value[key])}
    if isinstance(value, (list, tuple)) and value:
        return type(value)([tampered(value[0]), *value[1:]])
    return ["tampered", value]


def original_class(spec: dict):
    """The pristine upstream class, imported from the pack folder in-process (its __init__.py is not run).

    With "reference_deps" in the config, /deps is appended to the in-process path first, for profile modules the
    gate image itself lacks (the gate's own copies still come first where it has them)."""
    root = "profile_original"
    if CONFIG.get("reference_deps") and str(DEPS) not in sys.path:
        sys.path.append(str(DEPS))
    if root not in sys.modules:
        package = types.ModuleType(root)
        package.__path__ = [str(pack_head())]
        package.__package__ = root
        sys.modules[root] = package
    return getattr(importlib.import_module(f"{root}.{spec['module']}"), spec["class"])


def run_original(cls, inputs):
    try:
        if callable(getattr(cls, "define_schema", None)):
            result = cls.execute(**inputs)
            return "ok", tuple(result.result if hasattr(result, "result") else result)
        return "ok", tuple(getattr(cls(), cls.FUNCTION)(**inputs))
    except Exception as error:  # noqa: BLE001
        return "error", f"{type(error).__name__}: {error}"


REMOTE_ERRORS = {}


async def run(proxy, inputs, prompt_id):
    try:
        output, _ui, _sub, _pending = await execution.get_output_data(
            prompt_id, "1", proxy, {k: [v] for k, v in inputs.items()})
        return "ok", tuple(slot[0] for slot in output)
    except Exception as error:  # noqa: BLE001
        # A guest error keeps its phase, frames and stderr; they go to the results file.
        REMOTE_ERRORS[prompt_id] = {"phase": getattr(error, "remote_phase", ""),
                                    "frames": list(getattr(error, "remote_frames", ()))[-12:],
                                    "stderr": str(getattr(error, "remote_stderr", ""))[-3000:]}
        return "error", f"{getattr(error, 'remote_type', None) or type(error).__name__}: {error}"


def session_class(with_profile: bool):
    class ProfileGuestSession(GuestSession):
        def _guest_command(self, python):
            return [python, "/tests/_profile_guest_entry.py"]

        def _adjust_guest_env(self, env):
            super()._adjust_guest_env(env)
            env["NED_PROFILE_MODULES"] = ",".join(DEPS_ONLY)
            if with_profile:
                env["PYTHONPATH"] = os.pathsep.join(p for p in (str(DEPS), env.get("PYTHONPATH", "")) if p)

        def _extra_ro_paths(self):
            return list(super()._extra_ro_paths()) + ([str(DEPS)] if with_profile else [])
    return ProfileGuestSession


async def guest_runs():
    for name, setter in (("temp", folder_paths.set_temp_directory), ("output", folder_paths.set_output_directory),
                         ("input", folder_paths.set_input_directory)):
        Path(f"/tmp/profile-{name}").mkdir(parents=True, exist_ok=True)
        setter(f"/tmp/profile-{name}")
    loaded = packdb.load_pack(snapshot_dir(), mount_name="custom_nodes.profile_proxy",
                              pack_id=f"{CONFIG['pack']}/{CONFIG['key']}")
    for folder, directory in (loaded.asset_directories or {}).items():
        folder_paths.add_model_folder_path(folder, str(directory))
    references = {}
    for index, case in enumerate(CONFIG["guest_cases"]):
        inputs = {k: materialize(v) for k, v in case["inputs"].items()}
        status, value = run_original(original_class(case["original"]), {k: v for k, v in inputs.items()})
        if status == "ok" and case.get("token_output"):
            value = tuple(as_token(v) for v in value)
        references[index] = (inputs, (status, value))
        record(f"in-process upstream {case['original']['module']}.{case['original']['class']} "
               f"({case['node']}): ran", status == "ok", value)
    facts = {"torch": torch.__version__}
    controls = []
    for with_profile in (True, False):
        session = await session_class(with_profile)(f"profile-{int(with_profile)}").start()

        class Backend:
            async def dispatch(self, plan, local_call, runtime=None):
                if not str(getattr(plan, "node_module", "") or "").startswith("custom_nodes."):
                    return await local_call()
                caps = set(plan.permissions or ())
                if getattr(plan, "input_mode", "refs") == "values":
                    caps.add("raw")
                    plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
                return await session.execute(plan, runtime, capabilities=frozenset(caps), tenant="profile")

        previous = _sdk.providers.execution_backend
        _sdk.providers.register_execution_backend(Backend())
        try:
            for index, case in enumerate(CONFIG["guest_cases"]):
                inputs, reference = references[index]
                got = await run(loaded.node_mappings[case["node"]], inputs, f"profile-{int(with_profile)}-{index}")
                if with_profile:
                    record(f"guest with the profile, {case['node']} ({case['label']}): equals the upstream node "
                           "in-process", got[0] == reference[0] == "ok" and same(reference[1], got[1]),
                           [reference, got])
                    if got[0] == reference[0] == "ok":
                        controls.append(same(reference[1], tampered(got[1])))
                else:
                    record(f"guest without the profile, {case['node']} ({case['label']}): fails for lack of a "
                           "profile module", got[0] == "error" and any(names_module(got[1], m) for m in MODULES), got)
        finally:
            _sdk.providers.register_execution_backend(previous)
            facts[f"guest_pid_{int(with_profile)}"] = session.last_guest_pid
            await session.kill()
    record("guest: out-of-process", facts.get("guest_pid_1") not in (None, os.getpid()), facts)
    record("negative control: a changed output is caught in every case", controls and not any(controls), controls)
    return facts


def main() -> int:
    head = pack_head()
    pins = {name: version for name, version in CONFIG["pins"].items()}
    have = {}
    for name in pins:
        dist = [p.name for p in DEPS.glob(f"{CONFIG['dists'][name]}-*.dist-info")] if DEPS.is_dir() else []
        have[name] = dist
    record("DEPS: /deps holds exactly the pinned versions",
           all(have[n] == [f"{CONFIG['dists'][n]}-{v}.dist-info"] for n, v in pins.items()), have)
    pyproject = (head / "v2" / "pyproject.toml").read_text(encoding="utf-8")
    record("v2/pyproject.toml declares exactly the pins", CONFIG["pyproject_line"] in pyproject, pyproject)
    loads = production_load(head)
    facts = asyncio.run(guest_runs())
    out = {"config": CONFIG, "deps_only": DEPS_ONLY, "loads": loads, "facts": facts, "guest_errors": REMOTE_ERRORS,
           "checks": checks, "failed": [c["check"] for c in checks if not c["ok"]]}
    Path("/results").mkdir(parents=True, exist_ok=True)
    Path("/results/dependency_profile.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(json.dumps({"failed": out["failed"]}, indent=1))
    return 1 if out["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
