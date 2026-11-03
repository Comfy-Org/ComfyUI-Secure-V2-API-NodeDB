"""Independent re-implementation of the comfy-pack-patch/1 pair (generate / apply / compare).

Written from a reading of the deployed backend's packpatch.py (sdk-surfaces-r1,
not imported or executed). Semantics kept identical:
  * file walk: sorted rglob, skip v2/ on the pristine side, skip .git,
    __pycache__, .pytest_cache, node_modules dirs and .DS_Store files, refuse symlinks;
  * ops: copy (same sha256), convert (text, hunks against the pristine file),
    add (text, hunks from /dev/null), delete;
  * diff: difflib.unified_diff(n=3), labels a/<rel> or /dev/null -> b/v2/<rel>,
    every unterminated line followed by "\\n\\ No newline at end of file\\n";
  * manifest: json.dumps(indent=1) + "\\n", counts for copy/convert/add/delete;
  * apply: verify every base sha256 first, rebuild v2/ in a staging dir, check
    every v2_sha256 and set every mode, then rename into place.

Usage:
  packpair.py generate <snapshot_dir(<slug>/<key>)> <out_dir>
  packpair.py apply    <snapshot_dir> <pair_prefix(<dir>/<pack>-<key>)>
  packpair.py cmptree  <tree_a> <tree_b>        (files, bytes and modes)
"""
from __future__ import annotations

import difflib, hashlib, json, re, shutil, stat, sys, tempfile
from pathlib import Path

FORMAT = "comfy-pack-patch/1"
IGNORE_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules"}
IGNORE_FILES = {".DS_Store"}
EMPTY = hashlib.sha256(b"").hexdigest()
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?$")


class PairError(Exception):
    pass


def files(root: Path, include_v2: bool = False) -> dict[str, Path]:
    out = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if p.is_symlink():
            raise PairError(f"symlink: {p}")
        if not p.is_file():
            continue
        if rel.parts[0] == "v2" and root.name != "v2" and not include_v2:
            continue
        if any(part in IGNORE_DIRS for part in rel.parts) or rel.name in IGNORE_FILES:
            continue
        out[rel.as_posix()] = p
    return out


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def is_text(p: Path) -> bool:
    data = p.read_bytes()
    if b"\0" in data[:8192]:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def lines(p: Path) -> list[str]:
    return p.read_bytes().decode("utf-8").splitlines(keepends=True)


def mode(p: Path) -> int:
    return stat.S_IMODE(p.stat().st_mode) & 0o777


def unified(a, b, la, lb) -> str:
    out = []
    for line in difflib.unified_diff(a, b, fromfile=la, tofile=lb, n=3):
        out.append(line)
        if not line.endswith("\n"):
            out.append("\n\\ No newline at end of file\n")
    return "".join(out)


def pack_folder(snapshot: Path) -> Path:
    dirs = [d for d in sorted(snapshot.iterdir()) if d.is_dir() and not d.name.startswith(".")]
    if len(dirs) != 1:
        raise PairError(f"{snapshot}: expected one pack folder, found {[d.name for d in dirs]}")
    return dirs[0]


def generate(snapshot: Path):
    pack = pack_folder(snapshot)
    v2 = pack / "v2"
    orig, conv = files(pack), files(v2)
    entries, parts = [], []
    for rel in sorted(set(orig) | set(conv)):
        o, c = orig.get(rel), conv.get(rel)
        if c is None:
            entries.append({"path": rel, "op": "delete", "base_sha256": sha(o)})
            continue
        if o is None:
            if not is_text(c):
                raise PairError(f"binary add: {rel}")
            entries.append({"path": rel, "op": "add", "v2_sha256": sha(c), "mode": mode(c)})
            parts.append(unified([], lines(c), "/dev/null", f"b/v2/{rel}"))
            continue
        bs, vs = sha(o), sha(c)
        if bs == vs:
            entries.append({"path": rel, "op": "copy", "base_sha256": bs, "mode": mode(c)})
            continue
        if not (is_text(o) and is_text(c)):
            raise PairError(f"binary differs: {rel}")
        entries.append({"path": rel, "op": "convert", "base_sha256": bs, "v2_sha256": vs, "mode": mode(c)})
        parts.append(unified(lines(o), lines(c), f"a/{rel}", f"b/v2/{rel}"))
    m = re.fullmatch(r"(?:x[0-9a-f]{7,12}|r[0-9a-f]{64})", snapshot.resolve().name)
    if not m:
        raise PairError("snapshot folder is not a key")
    manifest = {"format": FORMAT, "pack": snapshot.resolve().parent.name, "key": snapshot.resolve().name,
                "files": entries,
                "counts": {op: sum(1 for e in entries if e["op"] == op) for op in ("copy", "convert", "add", "delete")}}
    return manifest, "".join(parts)


def parse_diff(text: str) -> dict:
    ls = text.splitlines(keepends=True)
    blocks, i = {}, 0
    while i < len(ls):
        if not ls[i].startswith("--- "):
            raise PairError(f"expected header at {i + 1}: {ls[i]!r}")
        src = ls[i][4:].rstrip("\r\n")
        if i + 1 >= len(ls) or not ls[i + 1].startswith("+++ "):
            raise PairError("header without target")
        tgt = ls[i + 1][4:].rstrip("\r\n")
        if not tgt.startswith("b/v2/"):
            raise PairError(f"bad target {tgt}")
        rel = tgt[5:]
        if rel in blocks:
            raise PairError(f"duplicate target {rel}")
        block, i = [], i + 2
        while i < len(ls) and ls[i].startswith("@@"):
            mm = HUNK_RE.fullmatch(ls[i].rstrip("\r\n"))
            if not mm:
                raise PairError(f"bad hunk header {ls[i]!r}")
            ro = int(mm.group(2)) if mm.group(2) is not None else 1
            rn = int(mm.group(4)) if mm.group(4) is not None else 1
            block.append(ls[i]); i += 1
            while (ro > 0 or rn > 0) and i < len(ls):
                t = ls[i][0] if ls[i] else " "
                if t == " ":
                    ro -= 1; rn -= 1
                elif t == "-":
                    ro -= 1
                elif t == "+":
                    rn -= 1
                elif t != "\\":
                    raise PairError(f"bad body {ls[i]!r}")
                block.append(ls[i]); i += 1
            if ro or rn:
                raise PairError(f"{rel}: truncated hunk")
            if i < len(ls) and ls[i].startswith("\\"):
                block.append(ls[i]); i += 1
        if not block:
            raise PairError(f"{rel}: no hunks")
        blocks[rel] = (src, block)
    return blocks


def apply_hunks(base: list[str], hunks: list[str], rel: str) -> list[str]:
    res = []
    for h in hunks:
        if h.startswith("\\"):
            res[-1] = res[-1].rstrip("\n")
        else:
            res.append(h)
    out, pos, i = [], 0, 0
    while i < len(res):
        hdr = res[i].split("@@")[1].strip()
        old = hdr.split(" ")[0]
        start = int(old.lstrip("-").split(",")[0])
        olen = int(old.split(",")[1]) if "," in old else 1
        anchor = start - 1 if olen else start
        if anchor < pos:
            raise PairError(f"{rel}: overlapping hunks")
        out.extend(base[pos:anchor]); pos = anchor; i += 1
        while i < len(res) and not res[i].startswith("@@"):
            t, body = res[i][0], res[i][1:]
            if t in " -":
                if pos >= len(base) or base[pos] != body:
                    raise PairError(f"{rel}: {'context' if t == ' ' else 'removal'} mismatch at {pos + 1}")
                if t == " ":
                    out.append(body)
                pos += 1
            elif t == "+":
                out.append(body)
            else:
                raise PairError(f"{rel}: bad line")
            i += 1
    out.extend(base[pos:])
    return out


def apply(snapshot: Path, manifest: dict, diff_text: str) -> None:
    pack = pack_folder(snapshot)
    if manifest.get("format") != FORMAT or manifest.get("pack") != snapshot.resolve().parent.name \
            or manifest.get("key") != snapshot.resolve().name:
        raise PairError("manifest identity mismatch")
    entries = manifest["files"]
    declared = {e["path"] for e in entries if e["op"] in ("copy", "convert", "delete")}
    base_files = files(pack)
    if declared != set(base_files):
        raise PairError(f"base set differs: missing={sorted(set(base_files) - declared)} extra={sorted(declared - set(base_files))}")
    counts = {op: sum(e["op"] == op for e in entries) for op in sorted(("copy", "convert", "add", "delete"))}
    if manifest.get("counts") != counts:
        raise PairError("counts mismatch")
    hunks = parse_diff(diff_text)
    want = {e["path"] for e in entries if e["op"] == "convert" or (e["op"] == "add" and e["v2_sha256"] != EMPTY)}
    if set(hunks) != want:
        raise PairError(f"diff targets differ: {sorted(set(hunks) ^ want)}")
    for e in entries:
        exp_src = "/dev/null" if e["op"] == "add" else f"a/{e['path']}"
        if e["path"] in hunks and hunks[e["path"]][0] != exp_src:
            raise PairError(f"bad source for {e['path']}")
        if e["op"] in ("copy", "convert", "delete") and sha(base_files[e["path"]]) != e["base_sha256"]:
            raise PairError(f"base sha mismatch: {e['path']}")
    v2 = pack / "v2"
    if v2.exists():
        raise PairError(f"refusing to replace {v2}")
    staging = Path(tempfile.mkdtemp(prefix=".v2-build-", dir=snapshot))
    try:
        for e in entries:
            rel, op = e["path"], e["op"]
            if op == "delete":
                continue
            t = staging / rel
            t.parent.mkdir(parents=True, exist_ok=True)
            if op == "copy":
                shutil.copy2(base_files[rel], t)
            elif op == "add":
                t.write_bytes("".join(apply_hunks([], hunks.get(rel, ("", []))[1], rel)).encode("utf-8"))
            else:
                t.write_bytes("".join(apply_hunks(lines(base_files[rel]), hunks[rel][1], rel)).encode("utf-8"))
            t.chmod(e["mode"])
            if "v2_sha256" in e and sha(t) != e["v2_sha256"]:
                raise PairError(f"result sha mismatch: {rel}")
        staging.replace(v2)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def cmptree(a: Path, b: Path) -> dict:
    fa, fb = files(a, include_v2=True), files(b, include_v2=True)
    shared = sorted(set(fa) & set(fb))
    return {"missing_in_a": sorted(set(fb) - set(fa)), "missing_in_b": sorted(set(fa) - set(fb)),
            "bytes_differ": [p for p in shared if sha(fa[p]) != sha(fb[p])],
            "modes_differ": [p for p in shared if mode(fa[p]) != mode(fb[p])],
            "files_compared": len(shared)}


def main(argv):
    cmd = argv[0]
    if cmd == "generate":
        snap, out = Path(argv[1]), Path(argv[2])
        manifest, diff = generate(snap)
        out.mkdir(parents=True, exist_ok=True)
        stem = out / f"{manifest['pack']}-{manifest['key']}"
        Path(str(stem) + ".json").write_bytes((json.dumps(manifest, indent=1) + "\n").encode("utf-8"))
        Path(str(stem) + ".diff").write_bytes(diff.encode("utf-8"))
        print(json.dumps(manifest["counts"]))
    elif cmd == "apply":
        snap, prefix = Path(argv[1]), argv[2]
        manifest = json.loads(Path(prefix + ".json").read_bytes().decode("utf-8"))
        apply(snap, manifest, Path(prefix + ".diff").read_bytes().decode("utf-8"))
        print("applied")
    elif cmd == "cmptree":
        r = cmptree(Path(argv[1]), Path(argv[2]))
        print(json.dumps(r))
        return 0 if not (r["missing_in_a"] or r["missing_in_b"] or r["bytes_differ"] or r["modes_differ"]) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
