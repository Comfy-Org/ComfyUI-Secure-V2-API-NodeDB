"""Guest import audit for published V2 packs (MERVYN, 2026-11-03). Run with python3 -I. Reads files only; imports nothing.

  import_audit.py <v2_dir> [<v2_dir> ...]      -> JSON report on stdout

For each v2 dir: start from the modules that secure-nodes.json rows name (what the production guest imports), follow
the pack's own imports transitively (relative and absolute-within-v2), and list every import of a module that is NOT
the stdlib, torch, numpy, PIL or comfy_api. Each finding says where it is and how it is reached:
  level   module-level (fails the whole module at import) | local (fails when that function runs)
  guarded inside a try block whose handlers catch ImportError/ModuleNotFoundError/Exception (a designed fallback)
It also prints what the pack declares: v2/pyproject.toml [project].dependencies and the manifest's runtime block.
The gate image has scipy, cv2, einops etc., so gate parity alone cannot show that a guest lacks one of these.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

BASE_OK = {"torch", "numpy", "PIL", "comfy_api", "typing_extensions", "__future__"}
STDLIB = set(getattr(sys, "stdlib_module_names", ()))
CATCHES_IMPORT = {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}


def module_file(v2: Path, dotted: str) -> Path | None:
    p = v2.joinpath(*dotted.split("."))
    if p.with_suffix(".py").is_file():
        return p.with_suffix(".py")
    if (p / "__init__.py").is_file():
        return p / "__init__.py"
    return None


def resolve_relative(cur: str, is_pkg: bool, level: int, mod: str | None) -> str:
    parts = cur.split(".")
    base = parts if is_pkg else parts[:-1]
    if level > 1:
        base = base[: len(base) - (level - 1)]
    return ".".join([*base, *(mod.split(".") if mod else [])]).strip(".")


class Visitor(ast.NodeVisitor):
    def __init__(self):
        self.depth_fn = 0
        self.try_stack: list[bool] = []
        self.found: list[dict] = []  # {"name", "level", "relative", "module", "lineno", "guarded", "names"}

    def _guarded(self) -> bool:
        return any(self.try_stack)

    def visit_FunctionDef(self, node):
        self.depth_fn += 1
        self.generic_visit(node)
        self.depth_fn -= 1

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Try(self, node):
        catches = False
        for h in node.handlers:
            if h.type is None:
                catches = True
            else:
                names = [h.type] if not isinstance(h.type, ast.Tuple) else list(h.type.elts)
                for n in names:
                    if isinstance(n, ast.Name) and n.id in CATCHES_IMPORT:
                        catches = True
        self.try_stack.append(catches)
        for stmt in node.body:
            self.visit(stmt)
        self.try_stack.pop()
        for part in (node.handlers, node.orelse, node.finalbody):
            for stmt in part:
                self.visit(stmt)

    visit_TryStar = visit_Try

    def visit_Import(self, node):
        for a in node.names:
            self.found.append({"name": a.name, "level": 0, "lineno": node.lineno, "local": self.depth_fn > 0,
                               "guarded": self._guarded(), "names": []})

    def visit_ImportFrom(self, node):
        self.found.append({"name": node.module or "", "level": node.level, "lineno": node.lineno,
                           "local": self.depth_fn > 0, "guarded": self._guarded(),
                           "names": [a.name for a in node.names]})


def audit(v2: Path) -> dict:
    manifest = json.loads((v2 / "secure-nodes.json").read_text())
    rows = manifest.get("nodes") or manifest.get("rows") or []
    if isinstance(rows, dict):
        rows = list(rows.values())
    starts = sorted({r.get("module") for r in rows if isinstance(r, dict) and r.get("module")})
    seen: dict[str, Path] = {}
    queue = [s for s in starts]
    findings = []
    missing_internal = []
    while queue:
        mod = queue.pop()
        if mod in seen:
            continue
        f = module_file(v2, mod)
        if f is None:
            missing_internal.append(mod)
            continue
        seen[mod] = f
        try:
            tree = ast.parse(f.read_bytes())
        except SyntaxError as e:  # noqa: PERF203
            findings.append({"module": mod, "error": f"SyntaxError {e}"})
            continue
        v = Visitor()
        v.visit(tree)
        is_pkg = f.name == "__init__.py"
        for imp in v.found:
            if imp["level"]:
                target = resolve_relative(mod, is_pkg, imp["level"], imp["name"] or None)
                cands = [target] + [f"{target}.{n}" for n in imp["names"]]
                for c in cands:
                    if module_file(v2, c):
                        queue.append(c)
                continue
            top = imp["name"].split(".")[0]
            if module_file(v2, imp["name"]) or module_file(v2, top):
                queue.append(imp["name"] if module_file(v2, imp["name"]) else top)
                continue
            if top in STDLIB or top in BASE_OK:
                continue
            findings.append({"module": mod, "file": str(f.relative_to(v2)), "line": imp["lineno"],
                             "import": imp["name"], "top": top,
                             "level": "local" if imp["local"] else "module-level",
                             "guarded": imp["guarded"]})
    deps = []
    pp = v2 / "pyproject.toml"
    if pp.is_file():
        try:
            import tomllib
            deps = tomllib.loads(pp.read_text()).get("project", {}).get("dependencies", [])
        except Exception as e:  # noqa: BLE001
            deps = [f"<unreadable: {e}>"]
    runtime = manifest.get("runtime")
    unguarded = sorted({x["top"] for x in findings if "top" in x and not x["guarded"]})
    return {"v2": str(v2), "row_modules": starts, "reachable_modules": len(seen),
            "missing_internal": sorted(set(missing_internal)), "declared_dependencies": deps, "runtime": runtime,
            "unguarded_third_party": unguarded,
            "module_level_unguarded": sorted({x["top"] for x in findings
                                              if "top" in x and not x["guarded"] and x["level"] == "module-level"}),
            "findings": findings}


def main(argv):
    out = [audit(Path(a)) for a in argv]
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
