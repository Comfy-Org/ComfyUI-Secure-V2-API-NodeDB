"""Vendor pinned RES4LYF modules into the V2 tree (text processing only; nothing is imported or run).

  vendor_res4lyf.py <pristine RES4LYF-HEAD> <v2 dir>

FILES: the RK-loop modules, copied byte-for-byte into <v2>/res4lyf_core/ with ONLY their import statements rewritten:
  * `import comfy` / `import comfy.<mod>`        -> `from <rel> import _comfy as comfy`
  * `from comfy.<mod> import names`               -> `from <rel>_comfy.<mod> import names`
  * `from comfy import names`                     -> `from <rel>_comfy import names`
  * `import pywt`                                 -> optional import (wavelet noise types are refused in V2)
Every other line is unchanged.

SUBSETS: some upstream modules import packages the needed definitions never use (images.py imports kornia, cv2 and
torchvision; sigmas.py imports scipy at module level, which only one node's unreachable method uses). From those, only
the named top-level definitions are copied, byte-for-byte and in upstream order, under a fixed header that holds the
imports they use. For each subset this tool proves, from the source text alone (symtable/ast), that every global name
the copied definitions use resolves as it does upstream: to the same import statement, to another copied definition,
or to the same builtin, or that it is unbound in both (a NameError in both). `import comfy` maps to the stand-in as
above.

Writes <v2>/res4lyf_core/VENDOR.json (sha256s, each rewritten line, each copied definition's source lines and sha256,
and the global-name proof) and fails if a check fails or any absolute `comfy`, `server`, `folder_paths`, `nodes`,
`execution` or `node_helpers` import remains. tests/test_res4lyf_vendor.py reruns this tool in the gate against the
pristine upstream and compares every output byte-for-byte.
"""
import ast
import builtins
import hashlib
import json
import math
import re
import symtable
import sys
from pathlib import Path

FILES = [
    "beta/rk_sampler_beta.py", "beta/rk_method_beta.py", "beta/rk_coefficients_beta.py", "beta/phi_functions.py",
    "beta/deis_coefficients.py", "beta/rk_noise_sampler_beta.py", "beta/noise_classes.py",
    "beta/rk_guide_func_beta.py", "beta/constants.py", "helper.py", "latents.py",
]
SUBSETS = [
    {
        "source": "images.py",
        "dest": "images.py",
        "header": (
            '"""V2 subset of upstream images.py (057a913e). The definitions below are copied verbatim, in upstream\n'
            "order; VENDOR.json records each one's source lines and sha256. Upstream also imports math, torchvision,\n"
            "kornia and cv2, which these definitions never use, so only their own imports are kept (vendor_res4lyf.py\n"
            "proves that every global name resolves as upstream). MAX_RESOLUTION is not defined upstream either\n"
            "(images.py never imports it): image_resize's keep-proportion and pad branches with a zero size raise\n"
            'NameError here exactly as they do there."""\n'
            "import torch\n"
            "import torch.nn.functional as F\n"
            "\n"
            "import numpy as np\n"
            "\n"
            "from PIL import Image, ImageFilter, ImageEnhance\n"
            "\n"
            "from . import _comfy as comfy  # V2: guest-side stand-in (res4lyf_core/_comfy; lanczos is Core's, verbatim)\n"
        ),
        "definitions": ["tensor2pil", "pil2tensor", "hard_light_blend", "image_resize", "Film_Grain",
                        "Image_Grain_Add", "Frames_Slice"],
    },
    {
        "source": "sigmas.py",
        "dest": "sigmas_values.py",
        "header": (
            '"""V2 subset of upstream sigmas.py (057a913e): four sigma value nodes, copied verbatim in upstream order;\n'
            "VENDOR.json records each one's source lines and sha256. They use only torch and math, so the upstream\n"
            "module's other imports (scipy, ComfyUI core) are not needed (vendor_res4lyf.py proves that every global\n"
            'name resolves as upstream)."""\n'
            "import torch\n"
            "import math\n"
        ),
        "definitions": ["sigmas_from_text", "sigmas_rescale", "sigmas_easing", "sigmas_split_value"],
    },
    {
        "source": "sigmas.py",
        "dest": "sigmas_resample.py",
        "header": (
            '"""V2 subset of upstream sigmas.py (057a913e): "Sigmas Resample" (sigmas_interpolate) and the small\n'
            "network its \"model\" mode trains, copied verbatim in upstream order; VENDOR.json records each one's source\n"
            "lines and sha256. The imports below are upstream's own statements for the names these definitions use\n"
            "(vendor_res4lyf.py proves that every global name resolves as upstream). scipy is imported at module level\n"
            "upstream; only the unreachable interpolate_sigma_schedule_constrained method uses it.\"\"\"\n"
            "import torch\n"
            "import numpy as np\n"
            "from scipy.interpolate import CubicSpline\n"
            "import torch.nn.functional as F\n"
            "import torch.optim as optim\n"
            "\n"
            "from torch import Tensor, nn\n"
        ),
        "definitions": ["SimpleInterpolator", "train_interpolator", "interpolate_sigma_schedule_model",
                        "sigmas_interpolate"],
    },
]
# upstream import -> its stand-in in a subset header (same rule as the FILES rewrite)
EQUIVALENT_BINDINGS = {("import", "comfy", None): ("from", 1, "", "_comfy", "comfy")}
STAR_MODULES = {"math": math}  # star imports upstream uses; stdlib only
BLOCKED = ("comfy", "server", "folder_paths", "nodes", "execution", "node_helpers")
IMPORT_COMFY = re.compile(r"^(\s*)import comfy(?:\.[\w.]+)?\s*(#.*)?$")
FROM_COMFY = re.compile(r"^(\s*)from comfy\.([\w.]+) import (.+)$")
FROM_COMFY_TOP = re.compile(r"^(\s*)from comfy import (.+)$")
IMPORT_PYWT = re.compile(r"^(\s*)import pywt\s*$")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def rewrite(rel_path, text):
    rel = ".." if rel_path.startswith("beta/") else "."
    out, changes = [], []
    for number, line in enumerate(text.splitlines(keepends=True), 1):
        body = line.rstrip("\r\n")
        newline = line[len(body):]
        m = IMPORT_COMFY.match(body)
        if m:
            new = f"{m.group(1)}from {rel} import _comfy as comfy  # V2: guest-side stand-in (res4lyf_core/_comfy)"
            out.append(new + newline)
            changes.append({"line": number, "from": body, "to": new})
            continue
        m = FROM_COMFY.match(body)
        if m:
            new = f"{m.group(1)}from {rel}_comfy.{m.group(2)} import {m.group(3)}"
            out.append(new + newline)
            changes.append({"line": number, "from": body, "to": new})
            continue
        m = FROM_COMFY_TOP.match(body)
        if m:
            new = f"{m.group(1)}from {rel}_comfy import {m.group(2)}"
            out.append(new + newline)
            changes.append({"line": number, "from": body, "to": new})
            continue
        m = IMPORT_PYWT.match(body)
        if m:
            ind = m.group(1)
            new = (f"{ind}try:  # V2: optional; wavelet noise types are refused by name\n"
                   f"{ind}    import pywt\n{ind}except ImportError:\n{ind}    pywt = None")
            out.append(new + newline)
            changes.append({"line": number, "from": body, "to": new})
            continue
        out.append(line)
    return "".join(out), changes


def check_imports(path, text):
    tree = ast.parse(text, filename=str(path))
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in BLOCKED:
                    bad.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module.split(".")[0] in BLOCKED:
                bad.append((node.lineno, node.module))
    return bad


def module_bindings(tree):
    """name -> list of (line, binding) for every module-level binding, in source order. A binding is
    ("import", module, asname) | ("from", level, module, name, asname) | ("star", module) | ("def", line) |
    ("assign", line) | ("conditional", line) (anything bound inside a module-level compound statement)."""
    out = {}

    def add(name, line, binding):
        out.setdefault(name, []).append((line, binding))

    def walk(statements, conditional):
        for node in statements:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                add(node.name, node.lineno, ("conditional", node.lineno) if conditional else ("def", node.lineno))
            elif isinstance(node, ast.Import):
                for a in node.names:
                    name = a.asname or a.name.split(".")[0]
                    binding = ("import", a.name if a.asname else a.name.split(".")[0], a.asname)
                    add(name, node.lineno, ("conditional", node.lineno) if conditional else binding)
            elif isinstance(node, ast.ImportFrom):
                for a in node.names:
                    if a.name == "*":
                        binding = ("star", node.module)
                        for name in public_names(node.module):
                            add(name, node.lineno, ("conditional", node.lineno) if conditional else binding)
                    else:
                        binding = ("from", node.level, node.module or "", a.name, a.asname)
                        add(a.asname or a.name, node.lineno, ("conditional", node.lineno) if conditional else binding)
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    for leaf in ast.walk(target):
                        if isinstance(leaf, ast.Name) and isinstance(leaf.ctx, ast.Store):
                            add(leaf.id, node.lineno, ("conditional", node.lineno) if conditional else
                                ("assign", node.lineno))
            elif isinstance(node, (ast.If, ast.Try, ast.TryStar, ast.With, ast.AsyncWith, ast.For, ast.AsyncFor,
                                   ast.While, ast.Match)):
                targets = [node.target] if isinstance(node, (ast.For, ast.AsyncFor)) else []
                targets += [item.optional_vars for item in getattr(node, "items", []) if item.optional_vars]
                for target in targets:
                    for leaf in ast.walk(target):
                        if isinstance(leaf, ast.Name):
                            add(leaf.id, node.lineno, ("conditional", node.lineno))
                for handler in getattr(node, "handlers", []) or []:
                    if handler.name:
                        add(handler.name, handler.lineno, ("conditional", handler.lineno))
                    walk(handler.body, True)
                for case in getattr(node, "cases", []) or []:
                    walk(case.body, True)
                for field in ("body", "orelse", "finalbody"):
                    walk(getattr(node, field, []) or [], True)
            elif not isinstance(node, ast.Pass):
                for leaf in ast.walk(node):  # e.g. del, walrus, type aliases: review by hand
                    if isinstance(leaf, ast.Name) and isinstance(leaf.ctx, (ast.Store, ast.Del)):
                        add(leaf.id, node.lineno, ("conditional", node.lineno))
    walk(tree.body, False)
    return out


def public_names(module):
    if module not in STAR_MODULES:
        raise SystemExit(f"star import from {module!r} upstream: add it to STAR_MODULES to check it")
    mod = STAR_MODULES[module]
    return list(getattr(mod, "__all__", None) or [n for n in dir(mod) if not n.startswith("_")])


def runtime_globals_declared(tree):
    """Names some upstream function declares `global` (and so may rebind at run time)."""
    return {name for node in ast.walk(tree) if isinstance(node, ast.Global) for name in node.names}


def used_globals(text, filename):
    """Every name the module's code looks up in module globals/builtins (module-level loads plus implicit or
    explicit globals of every nested scope)."""
    names = set()

    def visit(table):
        for sym in table.get_symbols():
            if table.get_type() == "module":
                if sym.is_referenced():
                    names.add(sym.get_name())
            elif sym.is_global():
                names.add(sym.get_name())
        for child in table.get_children():
            visit(child)
    visit(symtable.symtable(text, filename, "exec"))
    return names


def prove_globals(source_rel, upstream_tree, new_text, dest_rel, header, vendored):
    """The global-name proof for one subset; returns (proof, failures)."""
    upstream = module_bindings(upstream_tree)
    header_tree = ast.parse(header)
    header_bindings = module_bindings(header_tree)
    rebound = runtime_globals_declared(upstream_tree)
    proof, failures = {}, []
    for name in sorted(used_globals(new_text, dest_rel)):
        if name.startswith("__") and name.endswith("__"):
            failures.append(f"{name}: a module dunder differs between the two modules")
            continue
        if name in rebound:
            failures.append(f"{name}: upstream declares it global inside a function")
            continue
        up = upstream.get(name, [])
        effective = up[-1][1] if up else None
        if effective is not None and effective[0] == "conditional":
            failures.append(f"{name}: bound conditionally upstream (line {effective[1]})")
            continue
        if name in vendored:
            if effective != ("def", vendored[name]):
                failures.append(f"{name}: copied definition (line {vendored[name]}) is not upstream's effective binding "
                                f"{effective}")
            else:
                proof[name] = f"copied definition (upstream line {vendored[name]})"
            continue
        mine = header_bindings.get(name, [])
        if mine:
            here = mine[-1][1]
            if effective is None:
                failures.append(f"{name}: bound by the header but not upstream")
            elif here != effective and EQUIVALENT_BINDINGS.get(effective) != here:
                failures.append(f"{name}: header binds {here}, upstream {effective} (line {up[-1][0]})")
            else:
                proof[name] = f"header import, same as upstream line {up[-1][0]}: {effective}"
            continue
        if effective is not None:
            failures.append(f"{name}: upstream binds it ({effective}, line {up[-1][0]}) but this subset does not")
            continue
        proof[name] = "builtin in both" if hasattr(builtins, name) else "unbound in both (NameError in both)"
    return proof, failures


def subset(spec, raw):
    """The named top-level definitions of an upstream module, verbatim, under the spec's header."""
    rel_path = spec["source"]
    text = raw.decode("utf-8")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text, filename=rel_path)
    found = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in spec["definitions"]:
            if node.name in found:
                raise SystemExit(f"{rel_path}: {node.name} is defined twice upstream")
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            segment = "".join(lines[start - 1:node.end_lineno])
            found[node.name] = {"source_lines": [start, node.end_lineno], "def_line": node.lineno,
                                "sha256": sha(segment.encode("utf-8")), "text": segment}
    missing = [name for name in spec["definitions"] if name not in found]
    if missing:
        raise SystemExit(f"{rel_path}: definitions not found upstream: {missing}")
    ordered = sorted(found.items(), key=lambda item: item[1]["source_lines"][0])  # upstream order
    body = "\n\n".join(item["text"].rstrip("\n") + "\n" for _name, item in ordered)
    new_text = spec["header"] + "\n\n" + body
    proof, failures = prove_globals(rel_path, tree, new_text, spec["dest"], spec["header"],
                                    {name: item["def_line"] for name, item in ordered})
    record = {"mode": "subset", "source": rel_path, "source_sha256": sha(raw),
              "header_sha256": sha(spec["header"].encode("utf-8")),
              "definitions": {name: {k: v for k, v in item.items() if k not in ("text", "def_line")}
                              for name, item in ordered},
              "global_names": proof}
    return new_text, record, failures


def main(src, v2):
    src, dest_root = Path(src), Path(v2) / "res4lyf_core"
    report = {"source": "upstream RES4LYF 057a913e (the pristine pack folder)", "files": {}}
    failures = []
    for spec in SUBSETS:
        raw = (src / spec["source"]).read_bytes()
        new_text, record, proof_failures = subset(spec, raw)
        failures += [(spec["dest"], f) for f in proof_failures]
        bad = check_imports(spec["dest"], new_text)
        if bad:
            failures.append((spec["dest"], bad))
        data = new_text.encode("utf-8")
        dest = dest_root / spec["dest"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        record["dest_sha256"] = sha(data)
        report["files"][spec["dest"]] = record
    for rel_path in FILES:
        raw = (src / rel_path).read_bytes()
        text = raw.decode("utf-8")
        new_text, changes = rewrite(rel_path, text)
        bad = check_imports(rel_path, new_text)
        if bad:
            failures.append((rel_path, bad))
        dest = dest_root / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = new_text.encode("utf-8")
        dest.write_bytes(data)
        report["files"][rel_path] = {"source_sha256": sha(raw), "dest_sha256": sha(data),
                                      "rewritten_lines": changes}
    (dest_root / "VENDOR.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: (len(v["rewritten_lines"]) if "rewritten_lines" in v else sorted(v["definitions"]))
                      for k, v in report["files"].items()}, indent=1))
    if failures:
        print("VENDOR CHECK FAILED:", json.dumps(failures, indent=1, default=str))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
