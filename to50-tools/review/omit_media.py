"""Omit upstream media, example/demo workflows and shipped model files from a mirrored pack (Comfy policy, JERRY
m_8641ee2dc2, 2026-11-02 23:53Z, applying Ben's rule). Run with python3 -I. Never commit the per-file list.

  omit_media.py plan  <pack_root> <out_list.json>     list omitted upstream files (pristine side; v2/ excluded)
  omit_media.py apply <pack_root> <list.json>         delete them from pack_root and the identical copies from pack_root/v2
  omit_media.py note  <list.json> <OMITTED.md>        write the generic git-safe note: count, total size, one digest

Omitted:
  * media: images, video, audio, by extension, EXCEPT images referenced by the pack's own frontend code (web/js assets
    whose file name appears in a .js/.mjs/.css/.html file of the pack). Those are functional UI assets and are kept.
  * example/demo workflows: any .json file whose content is a ComfyUI graph (UI format: "nodes"+"links"/"last_node_id";
    API format: objects with "class_type"), wherever it lives.
  * shipped model files: weights from outside sources (.caffemodel .pt .pth .ckpt .safetensors .onnx .bin .pb .tflite
    .gguf .h5 .pkl .npz .npy).
The digest is sha256 over the sorted lines "<path>\t<sha256>\n" of the omitted set.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

MEDIA = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".ico", ".svg", ".avif", ".heic",
         ".mp4", ".mov", ".webm", ".avi", ".mkv", ".m4v", ".mpg", ".mpeg",
         ".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus", ".wma"}
MODELS = {".caffemodel", ".pt", ".pth", ".ckpt", ".safetensors", ".onnx", ".bin", ".pb", ".tflite", ".gguf", ".h5",
          ".pkl", ".npz", ".npy"}
FRONTEND_TEXT = {".js", ".mjs", ".cjs", ".css", ".html", ".htm", ".ts", ".vue"}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".pytest_cache"}


def walk(root: Path, skip_v2: bool):
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if skip_v2 and rel.parts and rel.parts[0] == "v2":
            continue
        if p.is_file() and not p.is_symlink():
            yield rel.as_posix(), p


def is_workflow_json(p: Path) -> bool:
    if p.suffix.lower() != ".json" or p.stat().st_size > 64 * 1024 * 1024:
        return False
    try:
        data = json.loads(p.read_bytes())
    except Exception:  # noqa: BLE001
        return False
    if isinstance(data, dict):
        if isinstance(data.get("nodes"), list) and ("links" in data or "last_node_id" in data):
            return True
        vals = [v for v in data.values() if isinstance(v, dict)]
        if vals and sum(1 for v in vals if "class_type" in v) >= max(1, len(vals) // 2):
            return True
    return False


def frontend_names(root: Path) -> str:
    chunks = []
    for rel, p in walk(root, skip_v2=True):
        if p.suffix.lower() in FRONTEND_TEXT and p.stat().st_size < 8 * 1024 * 1024:
            try:
                chunks.append(p.read_text(errors="ignore"))
            except OSError:
                pass
    return "\n".join(chunks)


def plan(root: Path):
    refs = frontend_names(root)
    out = []
    for rel, p in walk(root, skip_v2=True):
        ext = p.suffix.lower()
        reason = None
        if ext in MEDIA:
            if p.name in refs:
                continue  # functional frontend asset referenced by the pack's own code
            reason = "media"
        elif ext in MODELS:
            reason = "model"
        elif ext == ".json" and is_workflow_json(p):
            reason = "workflow"
        if reason:
            data = p.read_bytes()
            out.append({"path": rel, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data), "reason": reason})
    return out


def digest(entries) -> str:
    lines = "".join(f"{e['path']}\t{e['sha256']}\n" for e in sorted(entries, key=lambda e: e["path"]))
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


def apply(root: Path, entries):
    removed, kept_v2 = 0, []
    for e in entries:
        p = root / e["path"]
        if p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest() == e["sha256"]:
            p.unlink(); removed += 1
        q = root / "v2" / e["path"]
        if q.is_file():
            if hashlib.sha256(q.read_bytes()).hexdigest() == e["sha256"]:
                q.unlink(); removed += 1
            else:
                kept_v2.append(e["path"])  # the conversion changed it: it is pack-authored, keep it
    # prune empty directories left behind
    for d in sorted((x for x in root.rglob("*") if x.is_dir()), key=lambda x: len(x.parts), reverse=True):
        try:
            d.rmdir()
        except OSError:
            pass
    return removed, kept_v2


def main(a):
    if a[0] == "plan":
        entries = plan(Path(a[1]))
        Path(a[2]).write_text(json.dumps({"entries": entries, "digest": digest(entries)}, indent=1))
        print(json.dumps({"omitted": len(entries), "bytes": sum(e["size"] for e in entries), "digest": digest(entries),
                          "by_reason": {r: sum(1 for e in entries if e["reason"] == r) for r in ("media", "model", "workflow")}}))
    elif a[0] == "apply":
        d = json.loads(Path(a[2]).read_text())
        removed, kept = apply(Path(a[1]), d["entries"])
        print(json.dumps({"removed_files": removed, "kept_in_v2_changed": kept}))
    elif a[0] == "note":
        d = json.loads(Path(a[1]).read_text())
        n, total = len(d["entries"]), sum(e["size"] for e in d["entries"])
        Path(a[2]).write_text(
            "# Omitted upstream files\n\n"
            f"{n} upstream media, example/demo workflow and bundled model files are omitted from this snapshot "
            f"(pristine and v2), {total / 1e6:.1f} MB in total, per Comfy policy.\n\n"
            f"Digest of the omitted set: `{d['digest']}` (sha256 over sorted `path<TAB>sha256` lines; the list is kept "
            "outside git).\n")
        print(f"wrote {a[2]}")
    else:
        print(__doc__); return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
