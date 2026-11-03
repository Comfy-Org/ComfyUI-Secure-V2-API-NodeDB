"""Production-style bare load of every secure-nodes.json row (gate container only; run by the parity test).

The secure runtime mounts v2/ as a bare namespace package (its __init__.py is NOT executed), imports
<pkg>.<row module> and takes <row class> from it: getattr, then any module-level class whose __name__ matches. This
script does the same for every row, in a fresh interpreter, against the guest SDK base. Each class must exist, be an
io.ComfyNode, and declare the row's node id.

argv: OUT_JSON
"""
import importlib
import json
import os
from pathlib import Path
import shutil
import sys
import types

BASE = "/bases/0cd9adec273a703eb3d1c715d83ff1c7d2bb00746330c866c7e3ac644c80ebbb/common-site-packages"
OUT = Path(sys.argv[1])
dst = Path("/tmp/was-bare-load/v2")
if dst.exists():
    shutil.rmtree(dst)
shutil.copytree("/pack/v2", dst, ignore=shutil.ignore_patterns("__pycache__"))
sys.argv = [sys.argv[0], "--cpu"]
sys.path[:0] = [BASE, "/overlay", "/core"]
os.chdir("/tmp")
NAME = "was_bare_pack"
package = types.ModuleType(NAME)
package.__path__ = [str(dst)]
package.__package__ = NAME
sys.modules[NAME] = package
from comfy_api.latest import io  # noqa: E402

manifest = json.loads((dst / "secure-nodes.json").read_text())
rows = {}
for node_id, row in manifest["nodes"].items():
    try:
        module = importlib.import_module(f"{NAME}.{row['module']}")
        cls = getattr(module, row["class"], None)
        if cls is None:
            cls = next((value for value in vars(module).values()
                        if isinstance(value, type) and value.__name__ == row["class"]), None)
        if cls is None:
            raise AttributeError(f"{row['class']} not found in {row['module']}")
        if not issubclass(cls, io.ComfyNode):
            raise TypeError(f"{row['class']} is not an io.ComfyNode")
        declared = cls.GET_SCHEMA().node_id
        if declared != node_id:
            raise ValueError(f"{row['class']} declares node id {declared!r}")
        rows[node_id] = "OK"
    except Exception as error:  # noqa: BLE001
        rows[node_id] = f"{type(error).__name__}: {error}"[:300]
report = {"rows": len(rows), "ok": sum(1 for value in rows.values() if value == "OK"),
          "failures": {key: value for key, value in rows.items() if value != "OK"},
          "root_init_executed": hasattr(package, "comfy_entrypoint") or hasattr(package, "NODE_CLASS_MAPPINGS"),
          "modules": sorted({row["module"] for row in manifest["nodes"].values()})}
OUT.write_text(json.dumps(report, indent=1) + "\n")
print(json.dumps({k: report[k] for k in ("rows", "ok", "root_init_executed", "modules")}))
