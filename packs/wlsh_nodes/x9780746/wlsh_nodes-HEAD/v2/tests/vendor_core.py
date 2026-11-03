"""Copy Core's image helpers that wlsh_nodes calls into the V2 tree (text processing only; nothing is imported or run).

  vendor_core.py <Core root> <v2 dir>

The named top-level definitions of Core's comfy/utils.py are copied byte-for-byte, in Core's order, under a fixed
header holding the imports they use, into <v2>/_core_utils.py. The tool proves from the source text alone (symtable
and ast) that every global name the copies use resolves as it does in Core: to the same import statement, to another
copied definition, or to the same builtin. It writes <v2>/_core_utils.json (Core file sha256, each definition's lines
and sha256, the global-name proof) and fails if any check fails. tests/test_wlsh_vendor.py reruns it in the gate
against /core and compares the output byte-for-byte.
"""
import ast
import builtins
import hashlib
import json
import symtable
import sys
from pathlib import Path

SOURCE = "comfy/utils.py"
DEFINITIONS = ["bislerp", "lanczos", "common_upscale", "tiled_scale_multidim", "tiled_scale"]
HEADER = (
    '"""V2: Core\'s image helpers that wlsh_nodes calls (comfy.utils.common_upscale and comfy.utils.tiled_scale, with\n'
    "what they call), copied verbatim from ComfyUI's comfy/utils.py in Core's order. _core_utils.json records Core's\n"
    "file sha256 and each definition's lines and sha256, and proves every global name resolves as it does in Core.\n"
    'tests/test_wlsh_vendor.py re-derives this file from the gate\'s Core."""\n'
    "import torch\n"
    "import math\n"
    "import itertools\n"
    "from PIL import Image\n"
    "import numpy as np\n"
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def bindings(tree):
    """name -> list of (line, binding) for every unconditional module-level import/def/assign, plus 'conditional'."""
    out = {}

    def add(name, line, binding):
        out.setdefault(name, []).append((line, binding))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            add(node.name, node.lineno, ("def", node.lineno))
        elif isinstance(node, ast.Import):
            for a in node.names:
                add(a.asname or a.name.split(".")[0], node.lineno,
                    ("import", a.name if a.asname else a.name.split(".")[0], a.asname))
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                add(a.asname or a.name, node.lineno, ("from", node.level, node.module or "", a.name, a.asname))
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for leaf in ast.walk(target):
                    if isinstance(leaf, ast.Name) and isinstance(leaf.ctx, ast.Store):
                        add(leaf.id, node.lineno, ("assign", node.lineno))
        elif not isinstance(node, (ast.Expr, ast.Pass)):
            for leaf in ast.walk(node):
                if isinstance(leaf, ast.Name) and isinstance(leaf.ctx, (ast.Store, ast.Del)):
                    add(leaf.id, node.lineno, ("conditional", node.lineno))
    return out


def used_globals(text, filename):
    names = set()

    def visit(table):
        for symbol in table.get_symbols():
            if table.get_type() == "module":
                if symbol.is_referenced():
                    names.add(symbol.get_name())
            elif symbol.is_global():
                names.add(symbol.get_name())
        for child in table.get_children():
            visit(child)
    visit(symtable.symtable(text, filename, "exec"))
    return names


def main(core, v2):
    raw = (Path(core) / SOURCE).read_bytes()
    text = raw.decode("utf-8")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)
    found = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in DEFINITIONS:
            if node.name in found:
                raise SystemExit(f"{node.name} defined twice in Core")
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            segment = "".join(lines[start - 1:node.end_lineno])
            found[node.name] = {"source_lines": [start, node.end_lineno], "def_line": node.lineno,
                                "sha256": sha(segment.encode("utf-8")), "text": segment}
    missing = [n for n in DEFINITIONS if n not in found]
    if missing:
        raise SystemExit(f"not found in Core: {missing}")
    ordered = sorted(found.items(), key=lambda item: item[1]["source_lines"][0])
    new_text = HEADER + "\n\n" + "\n\n".join(item["text"].rstrip("\n") + "\n" for _n, item in ordered)
    upstream, header = bindings(tree), bindings(ast.parse(HEADER))
    proof, failures = {}, []
    copied = {name: item["def_line"] for name, item in ordered}
    for name in sorted(used_globals(new_text, "_core_utils.py")):
        up = upstream.get(name, [])
        effective = up[-1][1] if up else None
        if effective is not None and effective[0] == "conditional":
            failures.append(f"{name}: bound conditionally in Core")
        elif name in copied:
            if effective != ("def", copied[name]):
                failures.append(f"{name}: the copied definition is not Core's effective binding")
            else:
                proof[name] = f"copied definition (Core line {copied[name]})"
        elif name in header:
            if header[name][-1][1] != effective:
                failures.append(f"{name}: header binds {header[name][-1][1]}, Core {effective}")
            else:
                proof[name] = f"header import, same as Core line {up[-1][0]}: {effective}"
        elif effective is not None:
            failures.append(f"{name}: Core binds it ({effective}) but the copy does not")
        else:
            proof[name] = "builtin in both" if hasattr(builtins, name) else "unbound in both (NameError in both)"
    data = new_text.encode("utf-8")
    (Path(v2) / "_core_utils.py").write_bytes(data)
    record = {"source": f"ComfyUI {SOURCE} (the conversion core)", "source_sha256": sha(raw),
              "header_sha256": sha(HEADER.encode("utf-8")), "dest_sha256": sha(data),
              "definitions": {name: {k: v for k, v in item.items() if k not in ("text", "def_line")}
                              for name, item in ordered},
              "global_names": proof}
    (Path(v2) / "_core_utils.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"definitions": [n for n, _ in ordered], "global_names": len(proof)}, indent=1))
    if failures:
        print("VENDOR CHECK FAILED:", json.dumps(failures, indent=1))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
