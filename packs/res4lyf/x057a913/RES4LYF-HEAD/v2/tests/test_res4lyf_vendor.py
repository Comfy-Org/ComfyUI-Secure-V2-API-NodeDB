"""The vendored upstream code in v2/res4lyf_core is what vendor_res4lyf.py derives from the pristine pack (gate only).

* Runs vendor_res4lyf.py (a copy ships in this folder; text processing only, it imports nothing it reads) on /pack,
  the pristine RES4LYF-HEAD, into a fresh directory. Every file it writes, VENDOR.json included, must equal
  /pack/v2/res4lyf_core byte-for-byte. The tool itself fails unless every global name in each copied subset resolves
  as it does upstream (see its docstring).
* Each subset definition's sha256 in VENDOR.json must equal the sha256 of that definition's lines in the pristine
  upstream file.
* res4lyf_core/_comfy/utils.py's lanczos must be Core's comfy/utils.py lanczos, byte-for-byte (the source lines of
  the function definition).
Writes /results/vendor.json; exit 1 on any difference.
Run: run_in_gate.sh <RES4LYF-HEAD with v2> <v2/tests> <out> test_res4lyf_vendor.py
"""
import ast
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
import vendor_res4lyf  # noqa: E402

PACK = Path(os.environ.get("RES4_PACK", "/pack"))
CORE = Path(os.environ.get("COMFY_CORE_ROOT", "/core"))
RESULTS = Path(os.environ.get("RES4_RESULTS", "/results"))
SHIPPED = PACK / "v2" / "res4lyf_core"


def definition_source(path, name):
    text = path.read_bytes().decode("utf-8")  # no newline translation
    lines = text.splitlines(keepends=True)
    for node in ast.parse(text).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == name:
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            return "".join(lines[start - 1:node.end_lineno])
    return None


def main():
    out = Path(tempfile.mkdtemp(prefix="res4-vendor-")) / "v2"
    rc = vendor_res4lyf.main(str(PACK), str(out))
    derived_root = out / "res4lyf_core"
    report = json.loads((derived_root / "VENDOR.json").read_text())
    files = {}
    for rel in sorted(report["files"]) + ["VENDOR.json"]:
        derived = (derived_root / rel).read_bytes()
        shipped = (SHIPPED / rel).read_bytes() if (SHIPPED / rel).is_file() else None
        files[rel] = {"equal": derived == shipped, "sha256": hashlib.sha256(derived).hexdigest()}
    definitions = {}
    for rel, entry in sorted(report["files"].items()):
        if entry.get("mode") != "subset":
            continue
        source = (PACK / entry["source"]).read_bytes().decode("utf-8").splitlines(keepends=True)  # no newline translation
        for name, info in entry["definitions"].items():
            first, last = info["source_lines"]
            segment = "".join(source[first - 1:last]).encode("utf-8")
            definitions[f"{rel}:{name}"] = {"upstream_lines": f"{entry['source']}:{first}-{last}",
                                            "equal": hashlib.sha256(segment).hexdigest() == info["sha256"]}
    core_lanczos = definition_source(CORE / "comfy" / "utils.py", "lanczos")
    v2_lanczos = definition_source(SHIPPED / "_comfy" / "utils.py", "lanczos")
    lanczos = {"equal": core_lanczos is not None and core_lanczos == v2_lanczos,
               "sha256": hashlib.sha256((v2_lanczos or "").encode("utf-8")).hexdigest()}
    passed = rc == 0 and all(f["equal"] for f in files.values()) and all(d["equal"] for d in definitions.values()) \
        and lanczos["equal"]
    doc = {"passed": passed, "tool_exit": rc, "files_compared": len(files),
           "files_equal": sum(1 for f in files.values() if f["equal"]), "files": files,
           "subset_definitions": definitions, "lanczos_equals_core": lanczos,
           "global_name_proofs": {rel: entry["global_names"] for rel, entry in report["files"].items()
                                  if entry.get("mode") == "subset"}}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "vendor.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: doc[k] for k in ("passed", "tool_exit", "files_compared", "files_equal",
                                          "lanczos_equals_core")}, indent=1))
    for rel, f in files.items():
        if not f["equal"]:
            print("DIFFERS", rel)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
