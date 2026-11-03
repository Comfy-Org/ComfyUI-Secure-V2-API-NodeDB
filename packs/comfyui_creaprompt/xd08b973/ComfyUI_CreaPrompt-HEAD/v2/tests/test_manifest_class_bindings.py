"""Every manifest row's class is a module attribute under the name the manifest records (gate test).

    run_in_gate.sh <pack root (pristine + v2/)> <.../v2/tests> <results dir> test_manifest_class_bindings.py

The production guest imports a row's module from v2/ as a bare namespace package (v2/__init__.py does not run) and
looks the class up by the manifest's "class" name. The provisioning prewarm probe asserts exactly that:
    assert all(hasattr(m, c) for e, m in zip(entries, modules) for c in e['classes'])
This test reproduces it for every row, checks the attribute's __name__, and adds a negative control (an unbound
name must be reported). Writes /results/class_bindings.json; exits 1 on any failure.
"""
import importlib
import json
import sys
import types
from pathlib import Path

sys.path[:0] = ["/core", "/overlay"]
from comfy.cli_args import args as _cli_args  # noqa: E402

_cli_args.cpu = True


def pack_root(root=Path("/pack")):
    if (root / "v2").is_dir():
        return root
    heads = [d for d in sorted(root.iterdir()) if d.is_dir() and not d.name.startswith(".")]
    if len(heads) != 1:
        raise SystemExit(f"/pack must hold exactly one pack folder: {heads}")
    return heads[0]


PACK = pack_root()
V2 = PACK / "v2"
RESULTS = Path("/results")
PKG = "fi_v2_bare"


def bare_package():
    # The guest's view: a namespace package over v2/, so v2/__init__.py does not run.
    module = types.ModuleType(PKG)
    module.__path__ = [str(V2)]
    sys.modules[PKG] = module
    return module


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((V2 / "secure-nodes.json").read_text())
    bare_package()
    rows, failed = [], []
    for node_id, row in sorted(manifest["nodes"].items()):
        module = importlib.import_module(f"{PKG}.{row['module']}")
        cls = getattr(module, row["class"], None)
        ok = cls is not None and getattr(cls, "__name__", None) == row["class"]
        rows.append({"node_id": node_id, "module": row["module"], "class": row["class"], "ok": ok})
        if not ok:
            failed.append(node_id)
    # Negative control: a class name the module does not bind must be caught.
    first = next(iter(manifest["nodes"].values()))
    control_module = importlib.import_module(f"{PKG}.{first['module']}")
    control_caught = not hasattr(control_module, first["class"] + "_DoesNotExist")
    report = {"rows": len(rows), "failed": failed, "negative_control_caught": control_caught,
              "passed": not failed and control_caught, "details": rows}
    (RESULTS / "class_bindings.json").write_text(json.dumps(report, indent=1))
    print(json.dumps({k: report[k] for k in ("rows", "failed", "negative_control_caught", "passed")}, indent=1))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
