"""Tree helpers for the to-50% publication review (MERVYN 2026-11-02). Run with python3 -I.

  treecmp.py bytes <tree_a> <tree_b> [--skip-v2]
      Same file walk as packpair.py (skips .git, __pycache__, .pytest_cache, node_modules, .DS_Store; refuses symlinks).
      Compares file sets and bytes ONLY (modes are meaningless on /mnt/c). rc 1 on any difference.
  treecmp.py modes <pair.json> <pristine_pack_folder>
      Pair-mode policy: every mode is 0644 (420) or 0755 (493); added files are 0644; copied/converted files keep the
      pristine file's mode (as checked out on ext4). rc 1 on violations of the first two, WARN-only for the third.
"""
from __future__ import annotations

import hashlib
import json
import stat
import sys
from pathlib import Path

IGNORE_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules"}
IGNORE_FILES = {".DS_Store"}


def walk(root: Path, skip_v2: bool) -> dict[str, Path]:
    out = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if p.is_symlink():
            raise SystemExit(f"symlink: {p}")
        if not p.is_file():
            continue
        if skip_v2 and rel.parts[0] == "v2":
            continue
        if any(part in IGNORE_DIRS for part in rel.parts) or rel.name in IGNORE_FILES:
            continue
        out[rel.as_posix()] = p
    return out


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def cmd_bytes(a: Path, b: Path, skip_v2: bool) -> int:
    fa, fb = walk(a, skip_v2), walk(b, skip_v2)
    shared = sorted(set(fa) & set(fb))
    r = {"a": str(a), "b": str(b), "only_in_a": sorted(set(fa) - set(fb)), "only_in_b": sorted(set(fb) - set(fa)),
         "bytes_differ": [p for p in shared if sha(fa[p]) != sha(fb[p])], "files_compared": len(shared)}
    bad = r["only_in_a"] or r["only_in_b"] or r["bytes_differ"]
    r["verdict"] = "DIFFER" if bad else "IDENTICAL"
    print(json.dumps(r, indent=1))
    return 1 if bad else 0


def cmd_modes(pair_json: Path, pristine: Path) -> int:
    m = json.loads(pair_json.read_text())
    fails, warns = [], []
    for e in m["files"]:
        if e["op"] == "delete":
            continue
        mode = e.get("mode")
        if mode not in (0o644, 0o755):
            fails.append(f"{e['path']}: mode {oct(mode) if isinstance(mode, int) else mode}")
            continue
        if e["op"] == "add" and mode != 0o644:
            fails.append(f"{e['path']}: added file mode {oct(mode)} (must be 0644)")
        if e["op"] in ("copy", "convert"):
            p = pristine / e["path"]
            if p.is_file():
                pm = stat.S_IMODE(p.stat().st_mode) & 0o777
                if pm != mode:
                    warns.append(f"{e['path']}: pair mode {oct(mode)} != pristine {oct(pm)}")
    r = {"pair": str(pair_json), "fail": fails, "warn": warns, "counts": m.get("counts"),
         "verdict": "FAIL" if fails else "PASS"}
    print(json.dumps(r, indent=1))
    return 1 if fails else 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "bytes":
        sys.exit(cmd_bytes(Path(a[1]), Path(a[2]), "--skip-v2" in a))
    if a and a[0] == "modes":
        sys.exit(cmd_modes(Path(a[1]), Path(a[2])))
    print(__doc__)
    sys.exit(2)
