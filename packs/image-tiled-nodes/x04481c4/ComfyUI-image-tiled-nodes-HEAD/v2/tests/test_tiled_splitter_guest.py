"""image-tiled-nodes repair NED r1: TiledImageSplitter against the original, through a real guest (gate).

    run_in_gate.sh <snapshot dir x04481c4, or the pack folder> <.../v2/tests> <results> test_tiled_splitter_guest.py

1. Parity. The original (the pristine nodes.py, imported here) and the V2 node (the proxy packdb builds from
   secure-nodes.json, its body in a real guest started with the production patch fixr1_compat, see
   _sealed_guest_entry.py) run the same inputs: tile grids with and without overlap and feathering, a batch of two,
   a tile larger than the image, and two empty grids (the image no larger than the overlap), where the original's
   mask is zeros((H, W)). Tiles and masks must be equal in dtype, shape and bytes; tile_info must be equal.
2. Production load. Each manifest row loads the way the guest loads it (the module file under a namespace parent,
   without v2/__init__.py), with the guest SDK from each base in /bases and Core blocked; a static audit lists every
   import (function-local included) of the modules the rows reach.
3. Negative control: one changed mask element is caught.
Writes /results/tiled.json; exits 1 on any failed check.
"""

import ast
import asyncio
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path[:0] = ["/core", "/overlay"]

from comfy.cli_args import args  # noqa: E402

args.cpu = True

import comfy.samplers  # noqa: E402,F401
import execution  # noqa: E402
import torch  # noqa: E402
from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402

SLUG, KEY, FOLDER = "image-tiled-nodes", "x04481c4", "ComfyUI-image-tiled-nodes-HEAD"
NODE = "TiledImageSplitter"
checks = []


def record(name, ok, detail=None):
    checks.append({"check": name, "ok": bool(ok), "detail": None if ok else str(detail)[:1500]})
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": {str(detail)[:400]}"), flush=True)


def pack_head() -> Path:
    root = Path("/pack")
    return root if (root / "v2").is_dir() else root / FOLDER


def snapshot_dir() -> Path:
    root = Path("/pack")
    if not (root / "v2").is_dir():
        return root
    snap = Path("/tmp/tiled-snapshot") / SLUG / KEY
    if not (snap / FOLDER).is_dir():
        shutil.copytree(root, snap / FOLDER, ignore=shutil.ignore_patterns("__pycache__"))
    return snap


def same(a, b, path="value"):
    if isinstance(a, torch.Tensor) or isinstance(b, torch.Tensor):
        if not (isinstance(a, torch.Tensor) and isinstance(b, torch.Tensor)):
            return f"{path}: {type(a).__name__} vs {type(b).__name__}"
        if a.dtype != b.dtype or tuple(a.shape) != tuple(b.shape):
            return f"{path}: {a.dtype}{tuple(a.shape)} vs {b.dtype}{tuple(b.shape)}"
        ca, cb = a.detach().cpu().contiguous(), b.detach().cpu().contiguous()
        return None if ca.numpy().tobytes() == cb.numpy().tobytes() else f"{path}: values differ"
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return f"{path}: length {len(a)} vs {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            problem = same(x, y, f"{path}[{i}]")
            if problem:
                return problem
        return None
    return None if (type(a) is type(b) and a == b) else f"{path}: {a!r} vs {b!r}"


def g(seed):
    return torch.Generator().manual_seed(seed)


CASES = {
    "grid 300x260, tile 128, overlap 32, feather 0.1": (torch.rand(1, 300, 260, 3, generator=g(1)), 128, 128, 32, 0.1),
    "batch of 2, tile 96, overlap 16, feather 0.25": (torch.rand(2, 200, 180, 3, generator=g(2)), 96, 96, 16, 0.25),
    "no overlap, no feather": (torch.rand(1, 256, 256, 3, generator=g(3)), 128, 128, 0, 0.0),
    "tile larger than the image": (torch.rand(1, 100, 90, 3, generator=g(4)), 1024, 1024, 8, 0.1),
    "RGBA image": (torch.rand(1, 160, 140, 4, generator=g(5)), 64, 64, 8, 0.2),
    "empty grid: 64x48 at the defaults (overlap 128)": (torch.rand(1, 64, 48, 3, generator=g(6)), 1024, 1024, 128, 0.1),
    "empty grid: height 100 <= overlap 128": (torch.rand(1, 100, 300, 3, generator=g(7)), 1024, 1024, 128, 0.1),
}

CHILD = r'''
import importlib.abc, importlib.util, json, os, sys, types
base, v2, rows_path = sys.argv[1], sys.argv[2], sys.argv[3]
BLOCKED = {"comfy", "comfy_extras", "comfy_execution", "folder_paths", "nodes", "server", "execution",
           "comfy_secure_nodes", "scipy", "cv2", "torchvision"}
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in BLOCKED:
            raise ModuleNotFoundError(f"blocked in the guest emulation: {name}", name=name)
        return None
sys.meta_path.insert(0, Block())
sys.path.insert(0, os.path.join(base, "common-site-packages"))
import comfy_api
rows = json.load(open(rows_path))
mount = "custom_nodes.tiled_guest_emulation"
def load_module(module_name, module_file):
    if module_name in sys.modules:
        return sys.modules[module_name]
    parts = module_name.split(".")
    depth_dir = os.path.dirname(module_file)
    for i in range(len(parts) - 1, 0, -1):
        name = ".".join(parts[:i])
        if name not in sys.modules:
            parent = types.ModuleType(name); parent.__path__ = [depth_dir]; parent.__package__ = name
            sys.modules[name] = parent
        depth_dir = os.path.dirname(depth_dir)
    spec = importlib.util.spec_from_file_location(module_name, module_file)
    mod = importlib.util.module_from_spec(spec); mod.__package__ = ".".join(parts[:-1])
    sys.modules[module_name] = mod; spec.loader.exec_module(mod); return mod
out = {"sdk_root": list(comfy_api.__path__)[0], "rows": {}}
for node_id, row in rows.items():
    try:
        cls = getattr(load_module(f"{mount}.{row['module']}", os.path.join(v2, row["module"] + ".py")), row["class"])
        schema = cls.GET_SCHEMA()
        out["rows"][node_id] = {"node_id": schema.node_id, "sdk_refs": bool(getattr(cls, "SDK_REFS", False)),
                                "permissions": list(getattr(cls, "SDK_PERMISSIONS", ())),
                                "methods": {k: k in cls.__dict__ for k in ("validate_inputs", "fingerprint_inputs",
                                                                          "check_lazy_status")}}
    except BaseException as error:
        out["rows"][node_id] = {"error": f"{type(error).__name__}: {error}"}
print(json.dumps(out))
'''


def static_audit(v2: Path, modules):
    stdlib, allowed = set(sys.stdlib_module_names), {"torch", "numpy", "PIL", "comfy_api"}
    report, queue, seen = {}, list(modules), set()
    while queue:
        name = queue.pop()
        if name in seen:
            continue
        seen.add(name)
        tree = ast.parse((v2 / f"{name}.py").read_text(encoding="utf-8"))
        entries = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                targets = [(a.name, 0) for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level and not node.module:
                targets = [(a.name, node.level) for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                targets = [(node.module or "", node.level)]
            else:
                continue
            for target, level in targets:
                top = target.split(".")[0]
                if level:
                    kind = "pack"
                    queue.append(top)
                else:
                    kind = "stdlib" if top in stdlib else (top if top in allowed else "NOT ALLOWED")
                entries.append({"line": node.lineno, "import": "." * level + target, "kind": kind})
        report[f"{name}.py"] = entries
    return report


async def main_async() -> int:
    head = pack_head()
    spec = importlib.util.spec_from_file_location("_tiled_original", head / "nodes.py")
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    loaded = packdb.load_pack(snapshot_dir(), mount_name="custom_nodes.tiled_guest", pack_id=f"{SLUG}/{KEY}")
    proxy = loaded.node_mappings[NODE]

    class PatchedEntryGuestSession(GuestSession):
        def _guest_command(self, python):
            return [python, "/tests/_sealed_guest_entry.py"]

    session = await PatchedEntryGuestSession("tiled").start()

    class Backend:
        async def dispatch(self, plan, local_call, runtime=None):
            if not str(getattr(plan, "node_module", "") or "").startswith("custom_nodes."):
                return await local_call()
            caps = set(plan.permissions or ())
            if getattr(plan, "input_mode", "refs") == "values":
                caps.add("raw")
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
            return await session.execute(plan, runtime, capabilities=frozenset(caps), tenant="tiled")

    previous = _sdk.providers.execution_backend
    _sdk.providers.register_execution_backend(Backend())
    report, sample = {}, None
    try:
        for index, (name, (image, tw, th, overlap, feather)) in enumerate(CASES.items()):
            want = original.TiledImageSplitter().split(image.clone(), tw, th, overlap, feather)
            try:
                output, _ui, _sub, _pending = await execution.get_output_data(
                    f"tiled-{index}", str(index + 1), proxy,
                    {"image": [image.clone()], "tile_width": [tw], "tile_height": [th], "overlap": [overlap],
                     "feather_ratio": [feather]})
                got = tuple(slot[0] for slot in output)
                problem = same(tuple(want), got)
            except Exception as error:  # noqa: BLE001
                got, problem = None, f"{getattr(error, 'remote_type', None) or type(error).__name__}: {error}"
            report[name] = {"verdict": "EXACT" if problem is None else "MISMATCH", "detail": problem,
                            "mask_shape": list(want[1].shape)}
            record(f"{NODE} / {name}: EXACT (mask {list(want[1].shape)})", problem is None, problem)
            if problem is None and sample is None:
                sample = (tuple(want), got)
        guest_pid = session.last_guest_pid
    finally:
        _sdk.providers.register_execution_backend(previous)
        await session.kill()
    record("guest: the node body ran in a separate guest process", bool(guest_pid) and guest_pid != os.getpid(),
           guest_pid)
    if sample is not None:
        tampered = sample[1][1].clone()
        tampered.view(-1)[0] += 0.5
        caught = same(sample[0], (sample[1][0], tampered, sample[1][2])) is not None
    else:
        caught = False
    record("negative control: a changed mask element is caught", caught)

    v2 = head / "v2"
    rows = json.loads((v2 / "secure-nodes.json").read_text())["nodes"]
    audit = static_audit(v2, sorted({r["module"] for r in rows.values()}))
    bad = [(f, e) for f, entries in audit.items() for e in entries if e["kind"] == "NOT ALLOWED"]
    record("static audit: every import (function-local included) is stdlib, torch, numpy, Pillow, SDK or pack",
           not bad, bad)
    rows_path = Path("/tmp/tiled-rows.json")
    rows_path.write_text(json.dumps(rows))
    loads = {}
    for base in sorted(p for p in Path("/bases").iterdir() if (p / "common-site-packages" / "comfy_api").is_dir()):
        proc = subprocess.run([sys.executable, "-I", "-c", CHILD, str(base), str(v2), str(rows_path)],
                              capture_output=True, text=True, timeout=300, cwd="/tmp")
        tag = base.name[:8]
        if proc.returncode != 0:
            record(f"[{tag}] production load ran", False, proc.stderr[-800:])
            continue
        result = json.loads(proc.stdout.strip().splitlines()[-1])
        loads[tag] = result
        for node_id, row in rows.items():
            got = result["rows"][node_id]
            want = {"node_id": node_id, "sdk_refs": row["sdk_refs"], "permissions": row["permissions"],
                    "methods": row["methods"]}
            record(f"[{tag}] row {node_id} loads as the guest loads it (no __init__) and matches its row",
                   "error" not in got and {k: got.get(k) for k in want} == want, {"got": got, "want": want})
    out = {"pack": SLUG, "node": NODE, "cases": report, "static_audit": audit, "loads": loads, "checks": checks,
           "failed": [c["check"] for c in checks if not c["ok"]]}
    Path("/results").mkdir(parents=True, exist_ok=True)
    Path("/results/tiled.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(json.dumps({"failed": out["failed"]}, indent=1))
    return 1 if out["failed"] else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main_async()))
