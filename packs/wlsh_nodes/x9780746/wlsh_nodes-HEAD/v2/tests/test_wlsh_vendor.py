"""v2/_core_utils.py is exactly what vendor_core.py derives from the gate's Core (gate only).

Runs vendor_core.py (a copy ships in this folder; text processing only, it imports nothing it reads) on /core into a
fresh directory. _core_utils.py and _core_utils.json must equal /pack/v2's byte-for-byte; the tool itself fails unless
every global name in the copied definitions resolves as it does in Core (see its docstring).
Writes /results/vendor.json; exit 1 on any difference.
Run: run_in_gate.sh <wlsh_nodes-HEAD with v2> <v2/tests> <out> test_wlsh_vendor.py
"""
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vendor_core  # noqa: E402

PACK = Path(os.environ.get("WLSH_PACK", "/pack"))
CORE = Path(os.environ.get("COMFY_CORE_ROOT", "/core"))
RESULTS = Path(os.environ.get("WLSH_RESULTS", "/results"))


def main():
    out = Path(tempfile.mkdtemp(prefix="wlsh-vendor-"))
    rc = vendor_core.main(str(CORE), str(out))
    files = {}
    for name in ("_core_utils.py", "_core_utils.json"):
        derived = (out / name).read_bytes()
        shipped = (PACK / "v2" / name).read_bytes() if (PACK / "v2" / name).is_file() else None
        files[name] = {"equal": derived == shipped, "sha256": hashlib.sha256(derived).hexdigest()}
    record = json.loads((out / "_core_utils.json").read_text())
    passed = rc == 0 and all(f["equal"] for f in files.values())
    doc = {"passed": passed, "tool_exit": rc, "files": files, "core_utils_sha256": record["source_sha256"],
           "definitions": record["definitions"], "global_names": record["global_names"]}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "vendor.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: doc[k] for k in ("passed", "tool_exit", "files")}, indent=1))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
