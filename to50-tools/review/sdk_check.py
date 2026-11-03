"""Static SDK-compatibility and hard-rule check for a V2 pack (MERVYN, to-50% publication review, 2026-11-02).

AST only: never imports or runs pack code. Run with `python3 -I`.

  python3 -I sdk_check.py <v2_dir> <label>=<base common-site-packages dir> [<label>=<dir> ...]  > sdk-check.json

What it checks (non-test files under v2/, i.e. not under v2/tests/):
  * Every attribute chain rooted at a name imported from `comfy_api` (e.g. `io.Combo.Input`, `sdk.MaskRef.from_value`) is
    resolved against each base by class/member lookup (nested classes and base classes followed by name). A chain that
    does not resolve on a base is MISSING there.
  * Keyword arguments of calls to resolved SDK classes/functions are checked against the callee's parameters
    (`__init__`, dataclass fields, or function signature; **kwargs accepts all). E.g. RemoteOptions(static_options=...).
  * Heuristic (WARN only): calls `<expr>.<method>(kw=...)` where <method> is defined only on SDK *Domain/*Ref/*Context
    classes and not in the pack: keywords absent from every SDK definition (e.g. a writer keyword like jpeg_subsampling).
  * Hard rules: private SDK members (_from_raw, _wrap, _raw, _resolve_host), weights_only=False, torch.jit.load,
    pickle/dill/joblib loads, numpy allow_pickle=True -> FAIL. Network/process/host-only imports, private comfy_api modules,
    exec/eval, bare torch.load without weights_only -> WARN (file:line for manual review).
Output JSON: {"bases", "fail": [...], "warn": [...], "chains": [...], "min_base": label|null, "verdict"}.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

MODULE_NAMES = {"io", "ui", "sdk", "_io", "_ui", "_sdk", "_io_public", "_ui_public", "_sdk_public", "input", "input_impl",
                "util", "torch_helpers", "latest", "v0_0_1", "v0_0_2", "v0_0_3", "internal", "_input", "_input_impl", "_util",
                "resources", "types"}
PRIVATE_ATTRS = {"_from_raw", "_wrap", "_raw", "_resolve_host"}
# Ben 2026-11-03: no pack-specific code in the engine. These SDK verbs exist for one pack family each; new conversions
# must build such architectures in the guest instead (WARN, so existing conversions are listed, not blocked).
PACK_SPECIFIC_VERBS = {"load_sam", "load_object_detector", "load_ipadapter", "load_brushnet", "load_powerpaint",
                       "load_clipseg", "load_inpaint_model", "load_background_removal_model", "load_advanced_controlnet",
                       "load_controlnet_plusplus", "load_language_model", "generate_text"}
# Ben 2026-11-03 00:31Z: GGUF loading (load_gguf_model / load_gguf_text_encoders) is a sanctioned generic facility (a file
# format, like safetensors). Text generation (generate_text / load_language_model) is undecided, so it stays listed.
NET_MODULES = {"requests", "urllib", "urllib3", "http", "httpx", "aiohttp", "socket", "websocket", "websockets", "ftplib",
               "smtplib", "huggingface_hub", "gdown", "wget"}
PROC_MODULES = {"subprocess", "multiprocessing", "ctypes", "importlib", "pty"}
HOST_MODULES = {"folder_paths", "comfy", "nodes", "server", "comfy_execution", "execution", "comfy_extras", "latent_preview",
                "node_helpers", "comfy_api_nodes", "app", "main"}


class ClassInfo:
    __slots__ = ("module", "qualname", "members", "nested", "bases", "methods", "fields", "dataclass", "lineno")

    def __init__(self, module: str, qualname: str, node: ast.ClassDef):
        self.module, self.qualname, self.lineno = module, qualname, node.lineno
        self.members: set[str] = set()
        self.nested: dict[str, ClassInfo] = {}
        self.bases = [base_name(b) for b in node.bases]
        self.methods: dict[str, tuple[list[str], bool]] = {}
        self.fields: list[str] = []
        self.dataclass = any(base_name(d) in ("dataclass",) for d in node.decorator_list)


def base_name(expr) -> str | None:
    if isinstance(expr, ast.Call):
        expr = expr.func
    if isinstance(expr, ast.Subscript):
        expr = expr.value
    if isinstance(expr, ast.Attribute):
        return expr.attr
    if isinstance(expr, ast.Name):
        return expr.id
    return None


def params_of(fn) -> tuple[list[str], bool]:
    a = fn.args
    names = [p.arg for p in a.posonlyargs + a.args + a.kwonlyargs]
    if names and names[0] in ("self", "cls"):
        names = names[1:]
    return names, a.kwarg is not None


class Base:
    def __init__(self, label: str, root: Path):
        self.label, self.root = label, root
        self.classes: dict[str, list[ClassInfo]] = {}
        self.top: dict[str, tuple[str, int]] = {}        # top-level name -> (module, line)
        self.functions: dict[str, list[tuple[list[str], bool]]] = {}
        self.dynamic: set[str] = set()                      # X.attr = ... / setattr(X, "attr", ...)
        self.domain_methods: dict[str, list[tuple[list[str], bool]]] = {}
        api = root / "comfy_api"
        if not api.is_dir():
            raise SystemExit(f"{root}: no comfy_api package")
        for f in sorted(api.rglob("*.py")):
            mod = ".".join(f.relative_to(root).with_suffix("").parts)
            try:
                tree = ast.parse(f.read_bytes())
            except SyntaxError:
                continue
            self._index_module(mod, tree)

    def _index_module(self, mod: str, tree: ast.Module):
        for node in tree.body:
            self._top(mod, node)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Attribute):
                        self.dynamic.add(t.attr)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "setattr" \
                    and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                self.dynamic.add(node.args[1].value)

    def _top(self, mod: str, node):
        if isinstance(node, ast.ClassDef):
            self.top.setdefault(node.name, (mod, node.lineno))
            self._class(mod, node.name, node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self.top.setdefault(node.name, (mod, node.lineno))
            self.functions.setdefault(node.name, []).append(params_of(node))
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                for n in ast.walk(t):
                    if isinstance(n, ast.Name):
                        self.top.setdefault(n.id, (mod, node.lineno))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            self.top.setdefault(node.target.id, (mod, node.lineno))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                if a.name != "*":
                    self.top.setdefault((a.asname or a.name).split(".")[0], (mod, node.lineno))
        elif isinstance(node, (ast.If, ast.Try)):
            for sub in ast.iter_child_nodes(node):
                if isinstance(sub, ast.stmt):
                    self._top(mod, sub)
                elif isinstance(sub, ast.ExceptHandler):
                    for s in sub.body:
                        self._top(mod, s)

    def _class(self, mod: str, qual: str, node: ast.ClassDef) -> ClassInfo:
        ci = ClassInfo(mod, qual, node)
        self.classes.setdefault(node.name, []).append(ci)
        # Domain/Context objects only: *Ref method names (decode, resize, op, ...) collide with torch/PIL and are too noisy.
        is_domain = node.name.endswith(("Domain", "Context"))
        for item in node.body:
            if isinstance(item, ast.ClassDef):
                ci.members.add(item.name)
                ci.nested[item.name] = self._class(mod, f"{qual}.{item.name}", item)
            elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                ci.members.add(item.name)
                ci.methods[item.name] = params_of(item)
                if is_domain and not item.name.startswith("_"):
                    self.domain_methods.setdefault(item.name, []).append(params_of(item))
            elif isinstance(item, ast.Assign):
                for t in item.targets:
                    for n in ast.walk(t):
                        if isinstance(n, ast.Name):
                            ci.members.add(n.id)
            elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                ci.members.add(item.target.id)
                ci.fields.append(item.target.id)
        return ci

    # ---- lookups -------------------------------------------------------------------------------------------------
    def mro(self, cands: list[ClassInfo]):
        seen, queue = set(), list(cands)
        while queue:
            c = queue.pop(0)
            if id(c) in seen:
                continue
            seen.add(id(c))
            yield c
            for b in c.bases:
                if b and b in self.classes:
                    queue.extend(x for x in self.classes[b] if id(x) not in seen)

    def member(self, cands: list[ClassInfo], name: str):
        """-> (found, nested ClassInfos if the member is a class, method signatures if it is a method)."""
        found, nested, sigs = False, [], []
        for c in self.mro(cands):
            if name in c.members:
                found = True
                if name in c.nested:
                    nested.append(c.nested[name])
                if name in c.methods:
                    sigs.append(c.methods[name])
        if not found and name in self.dynamic:
            found = True
        return found, nested, sigs

    def ctor_params(self, cands: list[ClassInfo]):
        """-> (set of accepted keyword names, accepts_any)."""
        accepted, any_kw, have_init = set(), False, False
        for c in self.mro(cands):
            if "__init__" in c.methods and not have_init:
                names, varkw = c.methods["__init__"]
                accepted |= set(names)
                any_kw |= varkw
                have_init = True
            if c.dataclass:
                accepted |= set(c.fields)
            if "__new__" in c.methods:
                names, varkw = c.methods["__new__"]
                accepted |= set(names)
                any_kw |= varkw
            # NamedTuple / TypedDict style bases: annotated fields are keywords
            if any(b in ("NamedTuple", "TypedDict", "BaseModel") for b in c.bases):
                accepted |= set(c.fields)
                if "BaseModel" in c.bases:
                    any_kw = True
        if not have_init and not accepted:
            any_kw = True  # unknown constructor (e.g. Enum or builtin base) -> don't judge
        return accepted, any_kw


def pack_py_files(v2: Path):
    for f in sorted(v2.rglob("*.py")):
        rel = f.relative_to(v2)
        if any(p in ("__pycache__", ".git", "node_modules") for p in rel.parts):
            continue
        yield f, rel, (rel.parts[0] in ("tests", "test") or rel.name.startswith("test_") or rel.name == "conftest.py")


def sdk_bindings(tree: ast.Module) -> dict[str, tuple[str, str]]:
    """local name -> ("module", dotted) or ("symbol", name)."""
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "comfy_api" and node.level == 0:
            for a in node.names:
                if a.name == "*":
                    continue
                kind = "module" if a.name in MODULE_NAMES else "symbol"
                out[a.asname or a.name] = (kind, f"{node.module}.{a.name}" if kind == "module" else a.name)
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] == "comfy_api":
                    if a.asname:
                        out[a.asname] = ("module", a.name)
                    else:
                        out["comfy_api"] = ("module", "comfy_api")
    return out


def chain_of(node: ast.Attribute):
    parts, cur = [], node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        return cur.id, list(reversed(parts))
    return None, None


def resolve(base: Base, binding: tuple[str, str], attrs: list[str]):
    """-> (ok, failing_index, kind, payload). kind: 'class' (payload ClassInfos), 'func' (payload sigs), 'other'."""
    kind, target = binding
    i = 0
    if kind == "module":
        # walk through submodule names (e.g. comfy_api.latest -> .io)
        while i < len(attrs) and attrs[i] in MODULE_NAMES:
            i += 1
        if i == len(attrs):
            return True, None, "module", None
        name = attrs[i]
        i += 1
    else:
        name = target
    if name in base.classes:
        cur_kind, cur = "class", list(base.classes[name])
    elif name in base.functions:
        cur_kind, cur = "func", base.functions[name]
    elif name in base.top:
        cur_kind, cur = "other", None
    else:
        return False, (i - 1 if kind == "module" else -1), None, None
    while i < len(attrs):
        a = attrs[i]
        if cur_kind != "class":
            return True, None, "other", None  # cannot follow further statically
        found, nested, sigs = base.member(cur, a)
        if not found:
            return False, i, None, None
        if nested:
            cur_kind, cur = "class", nested
        elif sigs:
            cur_kind, cur = "func", sigs
        else:
            cur_kind, cur = "other", None
        i += 1
    return True, None, cur_kind, cur


def reachable_files(v2: Path):
    """Relative paths (posix) of v2 .py files the guest can import, starting from secure-nodes.json's modules.

    Conservative static closure: every Import/ImportFrom anywhere in a file (lazy imports included), relative imports
    resolved against the pack, parent packages' __init__.py included. Returns None without a manifest."""
    manifest = v2 / "secure-nodes.json"
    if not manifest.is_file():
        return None
    try:
        roots = {row["module"] for row in json.loads(manifest.read_text())["nodes"].values()}
    except Exception:  # noqa: BLE001
        return None
    files = {}
    for f, rel, is_test in pack_py_files(v2):
        parts = list(rel.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        files[".".join(parts)] = rel.as_posix()

    def module_and_parents(mod: str):
        out, parts = [], mod.split(".")
        for i in range(1, len(parts) + 1):
            name = ".".join(parts[:i])
            if name in files:
                out.append(name)
        return out

    seen, queue = set(), []
    for r in roots:
        queue.extend(module_and_parents(r))
    while queue:
        mod = queue.pop()
        if mod in seen:
            continue
        seen.add(mod)
        rel = files[mod]
        try:
            tree = ast.parse((v2 / rel).read_bytes())
        except SyntaxError:
            continue
        is_pkg = rel.endswith("__init__.py")
        pkg = mod.split(".") if is_pkg else mod.split(".")[:-1]
        for n in ast.walk(tree):
            targets = []
            if isinstance(n, ast.ImportFrom):
                if n.level:
                    base = pkg[: len(pkg) - (n.level - 1)] if n.level > 1 else pkg
                    stem = base + (n.module.split(".") if n.module else [])
                    targets.append(".".join(stem))
                    targets += [".".join(stem + [a.name]) for a in n.names]
                elif n.module:
                    # absolute import of a pack-internal module (packs that add their own dir to sys.path)
                    targets.append(n.module)
                    targets += [f"{n.module}.{a.name}" for a in n.names]
            elif isinstance(n, ast.Import):
                targets += [a.name for a in n.names]
            for t in targets:
                t = t.strip(".")
                if t:
                    queue.extend(m for m in module_and_parents(t) if m not in seen)
    return {files[m] for m in seen}


def main(argv: list[str]) -> int:
    v2 = Path(argv[0])
    bases = []
    for spec in argv[1:]:
        label, _, path = spec.partition("=")
        bases.append(Base(label, Path(path)))
    fails, warns, chains = [], [], {}
    pack_defs: set[str] = set()
    trees = []
    for f, rel, is_test in pack_py_files(v2):
        try:
            tree = ast.parse(f.read_bytes())
        except SyntaxError as e:
            fails.append({"rule": "syntax", "where": f"{rel}:{e.lineno}", "detail": str(e)})
            continue
        trees.append((rel, tree, is_test))
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                pack_defs.add(n.name)
    for rel, tree, is_test in trees:
        binds = sdk_bindings(tree)
        inner = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Attribute):
                inner.add(id(n.value))
        calls = {}
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                calls[id(n.func)] = n
        for n in ast.walk(tree):
            where = f"{rel}:{getattr(n, 'lineno', 0)}"
            # ---- hard rules (non-test code only, except private SDK members which are checked everywhere but tests) ---
            if not is_test:
                if isinstance(n, ast.Attribute) and n.attr in PRIVATE_ATTRS:
                    fails.append({"rule": "private-sdk-member", "where": where, "detail": n.attr})
                if isinstance(n, ast.keyword) and n.arg == "weights_only" and isinstance(n.value, ast.Constant) \
                        and n.value.value is False:
                    fails.append({"rule": "weights_only=False", "where": f"{rel}:{n.value.lineno}", "detail": "pickle execution"})
                if isinstance(n, ast.keyword) and n.arg == "allow_pickle" and isinstance(n.value, ast.Constant) \
                        and n.value.value is True:
                    fails.append({"rule": "allow_pickle=True", "where": f"{rel}:{n.value.lineno}", "detail": "pickle execution"})
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in PACK_SPECIFIC_VERBS:
                    warns.append({"rule": "pack-specific-engine-verb", "where": where,
                                  "detail": f".{n.func.attr}(): pack-specific engine helper; build it in the guest"})
                if isinstance(n, ast.Call):
                    fn = n.func
                    dotted = None
                    if isinstance(fn, ast.Attribute):
                        root, parts = chain_of(fn)
                        dotted = ".".join([root] + parts) if root else None
                    elif isinstance(fn, ast.Name):
                        dotted = fn.id
                    if dotted:
                        if dotted.endswith("jit.load"):
                            fails.append({"rule": "torch.jit.load", "where": where, "detail": dotted})
                        if dotted in ("pickle.load", "pickle.loads", "cPickle.load", "dill.load", "dill.loads",
                                      "joblib.load", "pickle.Unpickler", "_pickle.load", "pd.read_pickle", "pandas.read_pickle"):
                            fails.append({"rule": "pickle-load", "where": where, "detail": dotted})
                        if dotted.endswith("torch.load"):
                            if not any(k.arg == "weights_only" for k in n.keywords):
                                warns.append({"rule": "torch.load-without-weights_only", "where": where,
                                              "detail": "torch 2.8 defaults to weights_only=True; make it explicit"})
                        if dotted in ("exec", "eval", "compile", "__import__", "os.system", "os.popen"):
                            warns.append({"rule": "dynamic-exec", "where": where, "detail": dotted})
                if isinstance(n, (ast.Import, ast.ImportFrom)):
                    mods = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""]
                    if isinstance(n, ast.ImportFrom) and n.level:
                        mods = []
                    for m in mods:
                        top = m.split(".")[0]
                        if top in NET_MODULES:
                            warns.append({"rule": "network-import", "where": where, "detail": m})
                        if top in PROC_MODULES:
                            warns.append({"rule": "process/dynamic-import", "where": where, "detail": m})
                        if top in HOST_MODULES:
                            warns.append({"rule": "host-only-import", "where": where, "detail": m})
                        if top == "comfy_api" and any(p.startswith("_") for p in m.split(".")[1:]):
                            warns.append({"rule": "private-comfy_api-module", "where": where, "detail": m})
                    if isinstance(n, ast.ImportFrom) and (n.module or "").split(".")[0] == "comfy_api":
                        for a in n.names:
                            if a.name.startswith("_") and a.name not in ("__future__",):
                                warns.append({"rule": "private-comfy_api-module", "where": where, "detail": f"{n.module}.{a.name}"})
            # ---- SDK chains ----------------------------------------------------------------------------------------
            if isinstance(n, ast.Attribute) and id(n) not in inner:
                root, attrs = chain_of(n)
                if root in binds and attrs:
                    key = ".".join([root] + attrs)
                    rec = chains.setdefault(key, {"chain": key, "binding": list(binds[root]), "where": [], "present": {},
                                                  "detail": {}, "test_only": True})
                    rec["where"].append(where)
                    rec["test_only"] = rec["test_only"] and is_test
                    call = calls.get(id(n))
                    for b in bases:
                        ok, idx, kind, payload = resolve(b, binds[root], attrs)
                        prev = rec["present"].get(b.label, True)
                        rec["present"][b.label] = prev and ok
                        if not ok:
                            missing = attrs[idx] if idx is not None and 0 <= idx < len(attrs) else binds[root][1]
                            rec["detail"][b.label] = f"missing '{missing}'"
                        elif call is not None and call.keywords:
                            bad = []
                            if kind == "class":
                                accepted, any_kw = b.ctor_params(payload)
                            elif kind == "func":
                                accepted = set().union(*[set(s[0]) for s in payload]) if payload else set()
                                any_kw = any(s[1] for s in payload) if payload else True
                            else:
                                accepted, any_kw = set(), True
                            if not any_kw:
                                bad = [k.arg for k in call.keywords if k.arg and k.arg not in accepted]
                            if bad:
                                kwkey = f"{key}({', '.join(k + '=' for k in bad)})"
                                krec = chains.setdefault(kwkey, {"chain": kwkey, "binding": list(binds[root]), "where": [],
                                                                 "present": {}, "detail": {}, "test_only": True})
                                if where not in krec["where"]:
                                    krec["where"].append(where)
                                krec["test_only"] = krec["test_only"] and is_test
                                krec["present"][b.label] = False
                                krec["detail"][b.label] = f"keyword(s) not accepted: {bad}"
            # ---- heuristic: keywords on SDK domain methods called through runtime objects (WARN) ------------------
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.keywords and not is_test:
                meth = n.func.attr
                root, _attrs = chain_of(n.func)
                if root in binds:
                    continue
                if meth in pack_defs:
                    continue
                for b in bases[:1]:
                    sigs = b.domain_methods.get(meth)
                    if not sigs or any(s[1] for s in sigs):
                        continue
                    accepted = set().union(*[set(s[0]) for s in sigs])
                    bad = [k.arg for k in n.keywords if k.arg and k.arg not in accepted]
                    if bad:
                        warns.append({"rule": "sdk-domain-method-keyword", "where": where,
                                      "detail": f".{meth}({', '.join(bad)}=...) not accepted by any SDK definition on {b.label}"})
    # ---- reachability: static import closure from the manifest's modules (what the guest can actually import) ----
    reach = reachable_files(v2)
    if reach is not None:
        def where_file(w):
            return w.rsplit(":", 1)[0]
        kept = []
        for f in fails:
            if f["where"] != "-" and where_file(f["where"]) not in reach:
                warns.append({**f, "rule": f["rule"] + " (unreachable from manifest modules)"})
            else:
                kept.append(f)
        fails = kept
        for r in chains.values():
            if all(where_file(w) not in reach for w in r["where"]):
                r["test_only"] = True  # never imported by the guest: report, don't fail
    chain_list = sorted(chains.values(), key=lambda r: r["chain"])
    labels = [b.label for b in bases]
    for r in chain_list:
        for lab in labels:
            r["present"].setdefault(lab, True)
        if not r["present"][labels[0]] and not r["test_only"]:
            fails.append({"rule": "sdk-symbol-missing-on-target", "where": r["where"][0], "detail": f"{r['chain']}: {r['detail'].get(labels[0])}"})
    min_base = None
    if len(labels) > 1:
        only_first = [r["chain"] for r in chain_list if not r["test_only"] and r["present"][labels[0]]
                      and not all(r["present"][l] for l in labels[1:])]
        if only_first:
            min_base = labels[0]
            warns.append({"rule": "minimum-base", "where": "-", "detail": f"needs {labels[0]}: {only_first}"})
    out = {"tool": "to50 review sdk_check.py", "v2": str(v2), "bases": {b.label: str(b.root) for b in bases},
           "fail": fails, "warn": warns, "min_base": min_base, "chains": chain_list,
           "verdict": "FAIL" if fails else "PASS"}
    json.dump(out, sys.stdout, indent=1)
    sys.stdout.write("\n")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
