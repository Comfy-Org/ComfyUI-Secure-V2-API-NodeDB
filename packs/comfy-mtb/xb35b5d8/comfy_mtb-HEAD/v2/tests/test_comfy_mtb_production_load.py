"""comfy_mtb: every secure-nodes.json row loads the way the guest loads it, with the guest's packages only.

    run_in_gate.sh <snapshot dir, or the pack folder> <.../v2/tests> <results> \
        test_comfy_mtb_production_load.py

1. Static audit: every import statement (module level and function-local) in every v2 module a row can reach is
   listed with its line; each must be the standard library, torch, numpy, Pillow, the SDK (comfy_api) or the pack's
   own modules.
2. Production load, once per guest base (/bases: 0cd9adec and 0b86765f): a fresh `python3 -I` process whose
   comfy_api is the guest base's SDK (never Core's), where Core (comfy, folder_paths, nodes, server, execution) and
   the libraries the original uses that the guest lacks (scipy, scikit-image, OpenCV, torchvision, requests,
   onnxruntime, tensorflow, qrcode, torchaudio, huggingface_hub) cannot be imported. For every row it loads the row's
   module the way the guest worker does (comfy_secure_nodes.guest: the module file, under a namespace parent package,
   without running v2/__init__.py), resolves the row's class, builds its schema, and checks the node id, methods,
   sdk_refs and permissions against the row. It records every top-level module that got imported.
Writes /results/production_load.json; exits 1 on any failed check.
"""

import ast
import json
import subprocess
import sys
from pathlib import Path

RESULTS = Path("/results")
ALLOWED_THIRD_PARTY = {"torch", "numpy", "PIL", "comfy_api"}
BLOCKED = ["comfy", "comfy_extras", "comfy_execution", "folder_paths", "nodes", "server", "execution", "scipy",
           "skimage", "cv2", "torchvision", "requests", "onnxruntime", "tensorflow", "qrcode", "torchaudio",
           "huggingface_hub", "rembg", "comfy_secure_nodes"]
REACHED = ["_frozen_schema.py", "_mtb_upstream.py", "_secure_unconverted.py", "_secure_used.py", "_vendored.py",
           "log.py"]
checks = []

CHILD = r'''
import importlib.abc, importlib.util, json, os, sys, types

base, v2, rows_path = sys.argv[1], sys.argv[2], sys.argv[3]
BLOCKED = set(json.loads(sys.argv[4]))


class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in BLOCKED:
            raise ModuleNotFoundError(f"blocked in the guest emulation: {name}", name=name)
        return None


sys.meta_path.insert(0, Block())
sys.path.insert(0, os.path.join(base, "common-site-packages"))
before = set(sys.modules)
import comfy_api  # noqa: E402
from comfy_api.latest import io  # noqa: E402,F401

sdk_root = list(comfy_api.__path__)[0]
with open(rows_path, encoding="utf-8") as handle:
    rows = json.load(handle)
mount = "custom_nodes.mtb_guest_emulation"


def load_module(module_name, module_file):
    # comfy_secure_nodes/guest/__init__.py load_module, for a plain module file.
    if module_name in sys.modules:
        return sys.modules[module_name]
    pkg_dir = os.path.dirname(module_file)
    parts = module_name.split(".")
    depth_dir = pkg_dir
    for i in range(len(parts) - 1, 0, -1):
        name = ".".join(parts[:i])
        if name not in sys.modules:
            parent = types.ModuleType(name)
            parent.__path__ = [depth_dir]
            parent.__package__ = name
            sys.modules[name] = parent
        depth_dir = os.path.dirname(depth_dir)
    spec = importlib.util.spec_from_file_location(module_name, module_file)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = ".".join(parts[:-1])
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


out = {"sdk_root": sdk_root, "rows": {}}
for node_id, row in rows.items():
    entry = {}
    try:
        module = load_module(f"{mount}.{row['module']}", os.path.join(v2, row["module"] + ".py"))
        cls = getattr(module, row["class"])
        schema = cls.GET_SCHEMA()
        entry = {
            "node_id": schema.node_id,
            "methods": {k: k in cls.__dict__ for k in ("validate_inputs", "fingerprint_inputs", "check_lazy_status")},
            "sdk_refs": bool(getattr(cls, "SDK_REFS", False)),
            "permissions": list(getattr(cls, "SDK_PERMISSIONS", ())),
            "inputs": [i.id for i in schema.inputs],
            "init_ran": f"{mount}.__init__" in sys.modules or hasattr(sys.modules.get(mount), "comfy_entrypoint"),
        }
    except BaseException as error:  # noqa: BLE001
        entry = {"error": f"{type(error).__name__}: {error}"}
    out["rows"][node_id] = entry
out["imported_top_level"] = sorted({m.split(".")[0] for m in set(sys.modules) - before})
print(json.dumps(out))
'''


def record(name, ok, detail=None):
    checks.append({"check": name, "ok": bool(ok), "detail": None if ok else str(detail)[:2000]})
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": {str(detail)[:600]}"), flush=True)


def pack_head() -> Path:
    root = Path("/pack")
    if (root / "v2").is_dir():
        return root
    return next(d for d in sorted(root.iterdir()) if (d / "v2").is_dir())


def static_audit(v2: Path, modules: list) -> dict:
    stdlib = set(sys.stdlib_module_names)
    report, queue, seen = {}, list(modules), set()
    while queue:
        name = queue.pop()
        if name in seen:
            continue
        seen.add(name)
        path = v2 / f"{name}.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        function_lines = {n.lineno for f in ast.walk(tree) if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))
                          for n in ast.walk(f) if isinstance(n, (ast.Import, ast.ImportFrom))}
        entries = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                targets = [(a.name, 0) for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level and not node.module:
                targets = [(a.name, node.level) for a in node.names]  # from . import module
            elif isinstance(node, ast.ImportFrom):
                targets = [(node.module or "", node.level)]
            else:
                continue
            for target, level in targets:
                if level:
                    kind = "pack"
                    queue.append(target.split(".")[0] if target else "__init__")
                elif target.split(".")[0] in stdlib:
                    kind = "stdlib"
                elif target.split(".")[0] in ALLOWED_THIRD_PARTY:
                    kind = target.split(".")[0]
                else:
                    kind = "NOT ALLOWED"
                entries.append({"line": node.lineno, "import": "." * level + target, "kind": kind,
                                "function_local": node.lineno in function_lines})
        report[f"{name}.py"] = sorted(entries, key=lambda e: e["line"])
    return report


def main() -> int:
    head = pack_head()
    v2 = head / "v2"
    manifest = json.loads((v2 / "secure-nodes.json").read_text())
    rows = manifest["nodes"]
    modules = sorted({row["module"] for row in rows.values()})
    audit = static_audit(v2, modules)
    bad = [(f, e) for f, entries in audit.items() for e in entries if e["kind"] == "NOT ALLOWED"]
    record("static audit: every import (function-local included) is stdlib, torch, numpy, Pillow, the SDK or the pack",
           not bad, bad)
    record(f"static audit: the rows reach only {', '.join(REACHED)}", sorted(audit) == REACHED, sorted(audit))

    loads = {}
    bases = sorted(p for p in Path("/bases").iterdir() if (p / "common-site-packages" / "comfy_api").is_dir())
    record("guest bases present", len(bases) == 2, [p.name for p in bases])
    for base in bases:
        rows_path = Path("/tmp/mtb-production-load-rows.json")
        rows_path.write_text(json.dumps(rows), encoding="utf-8")
        proc = subprocess.run([sys.executable, "-I", "-c", CHILD, str(base), str(v2), str(rows_path),
                               json.dumps(BLOCKED)], capture_output=True, text=True, timeout=300, cwd="/tmp")
        tag = base.name[:8]
        if proc.returncode != 0:
            record(f"[{tag}] production load ran", False, proc.stderr[-1500:])
            continue
        result = json.loads(proc.stdout.strip().splitlines()[-1])
        loads[tag] = result
        record(f"[{tag}] comfy_api is the guest base's SDK", result["sdk_root"].startswith(str(base)),
               result["sdk_root"])
        for node_id, row in rows.items():
            got = result["rows"][node_id]
            want = {"node_id": node_id, "methods": row["methods"], "sdk_refs": row["sdk_refs"],
                    "permissions": row["permissions"]}
            same = "error" not in got and {k: got[k] for k in want} == want and not got["init_ran"]
            record(f"[{tag}] row {node_id} resolves as the guest loads it (no __init__) and matches the row",
                   same, {"got": got, "want": want})
        # For the record: what torch / numpy / Pillow / the SDK themselves imported besides the stdlib.
        loads[tag]["imported_other_than_stdlib_and_allowed"] = [
            m for m in result["imported_top_level"]
            if m not in set(sys.stdlib_module_names) | ALLOWED_THIRD_PARTY | {"custom_nodes"}]

    report = {"static_audit": audit, "loads": loads, "blocked": BLOCKED, "checks": checks,
              "failed": [c["check"] for c in checks if not c["ok"]]}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "production_load.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({"failed": report["failed"]}, indent=1))
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
