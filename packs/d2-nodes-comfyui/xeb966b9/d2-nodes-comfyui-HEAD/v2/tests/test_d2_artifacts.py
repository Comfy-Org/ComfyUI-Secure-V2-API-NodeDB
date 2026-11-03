"""Encoder/census/schema/loader/replay checks and POSIX stage sealing, gate only."""
from __future__ import annotations

import ast
import asyncio
import copy
import hashlib
import json
import os
import shutil
import signal
import sys
import tarfile
import tempfile
import traceback
import types
from pathlib import Path

sys.path[:0] = ["/core", "/overlay", "/tests"]
import test_d2_parity as parity
import packpair_tool
from comfy_api.latest import io
from comfy_secure_nodes import packdb, packmanifest, packpatch
import comfy.samplers
import folder_paths
import nodes as core_nodes
import yaml

RESULTS = Path("/results")
PACK = Path("/pack")
V2 = PACK / "v2"
REPORT = {"environment": "gate, B13 sources 38f28c98; core 6257422b; selected guest base 0cd9adec"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def data_value(node, env):
    """Literal source constants only; no upstream imports or arbitrary calls."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return env[node.id]
    if isinstance(node, (ast.List, ast.Tuple)):
        values = [data_value(x, env) for x in node.elts]
        return tuple(values) if isinstance(node, ast.Tuple) else values
    if isinstance(node, ast.Dict):
        return {data_value(k, env): data_value(v, env) for k, v in zip(node.keys, node.values)}
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -data_value(node.operand, env)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return data_value(node.left, env) + data_value(node.right, env)
    if isinstance(node, ast.Subscript):
        return data_value(node.value, env)[data_value(node.slice, env)]
    raise ValueError(ast.dump(node))


def source_schemas():
    constants = {}
    for name in ["util", "marker_util", "mask_rect_util", "random_util", "text_util",
                 "nai_prompt_util", "moss_util"]:
        env = {}
        if name == "random_util":
            env.update(vars(constants["marker_util"]))
        for node in parity.source_ast("nodes/modules/" + name + ".py").body:
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                try:
                    env[node.targets[0].id] = data_value(node.value, env)
                except (ValueError, KeyError, TypeError, IndexError):
                    pass
        constants[name] = types.SimpleNamespace(**env)
    size_dict = yaml.safe_load((PACK / "config/sizeselector_config.sample.yaml").read_text())["size_dict"]
    constants["size_util"] = types.SimpleNamespace(SIZE_LIST=["custom"] + list(size_dict))
    for name in ["input", "output", "temp"]:
        path = Path("/tmp/d2-schema-" + name)
        path.mkdir(exist_ok=True)
        getattr(folder_paths, "set_" + name + "_directory")(str(path))
    result = {}
    for module in sorted((PACK / "nodes").glob("d2_*.py")):
        source = ast.parse(module.read_text())
        mappings = next(n for n in source.body if isinstance(n, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == "NODE_CLASS_MAPPINGS"
                                for t in n.targets))
        classes = {v.id for v in mappings.value.values}
        selected = []
        for cls in source.body:
            if not isinstance(cls, ast.ClassDef) or cls.name not in classes:
                continue
            body = [n for n in cls.body if isinstance(n, ast.FunctionDef)
                    and n.name in {"define_schema", "_xy_inputs"}]
            body += [n for n in cls.body if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == "XY_INPUT_TYPES" for t in n.targets)]
            selected.append(ast.ClassDef(name=cls.name, bases=copy.deepcopy(cls.bases),
                                         keywords=[], body=body, decorator_list=[]))
        namespace = {"io": io, "os": os, "folder_paths": folder_paths, "comfy": comfy,
                     "VAELoader": core_nodes.VAELoader, "CLIPLoader": core_nodes.CLIPLoader,
                     **constants}
        exec(compile(ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])),
                     str(module), "exec"), namespace)
        for key, value in zip(mappings.value.keys, mappings.value.values):
            node_id = ast.literal_eval(key)
            schema = namespace[value.id].define_schema()
            schema.finalize()
            schema.validate()
            assert schema.node_id == node_id
            result[node_id] = packmanifest.encode_schema(copy.deepcopy(schema))
    assert len(result) == 70
    return result


def verify_schemas(manifest):
    expected = source_schemas()
    assert set(manifest["nodes"]) == set(expected)
    differences = {}
    remote_rows = []
    for node_id, schema in expected.items():
        actual = copy.deepcopy(manifest["nodes"][node_id]["schema"])
        # Remote catalogue metadata replaces only the host-enumerated source.
        # In this empty synthetic catalogue, source options including sentinels
        # must still match exactly; no static option is discarded.
        for field in actual["inputs"]:
            remote = field.get("attrs", {}).get("remote")
            if remote:
                remote_rows.append({"node_id": node_id, "input": field["attrs"]["id"],
                                    "route": remote["attrs"]["route"]})
                field["attrs"]["remote"] = None
        if schema != actual:
            differences[node_id] = {"source": schema, "converted": actual}
    (RESULTS / "schema-differences.json").write_text(
        json.dumps(differences, indent=2, sort_keys=True) + "\n")
    assert not differences, f"{len(differences)} source schema differences"
    REPORT["schema_count"] = len(expected)
    REPORT["remote_catalogue_declarations"] = remote_rows


MEDIA = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".mp4", ".mov", ".webm",
         ".wav", ".mp3", ".flac", ".ogg", ".safetensors", ".ckpt", ".pth", ".pt",
         ".onnx", ".bin"}


def omit(rel, converted):
    if rel == "static/Roboto-Regular.ttf":
        return "unused bundled font: no font-specific licence evidence at pin"
    if rel.split("/", 1)[0] in {"workflow", "workflows", "examples", "example"}:
        return "upstream demo/example workflow omission policy"
    if Path(rel).suffix.lower() in MEDIA and not rel.startswith("web/"):
        return "upstream media/bundled-model omission policy"
    if converted and rel.startswith("test/"):
        return "unreachable upstream host-only tests; replaced by gate tests"
    return None


def stage_copy(source, target, converted=False):
    omitted = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(source).as_posix()
        if not converted and rel.startswith("v2/"):
            continue
        if any(part in {"__pycache__", ".pytest_cache", ".git"} for part in Path(rel).parts):
            continue
        reason = omit(rel, converted)
        if reason:
            omitted.append({"sibling": "v2" if converted else "pristine",
                            "path": rel, "sha256": sha(path), "reason": reason})
            continue
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(path.read_bytes())
        dest.chmod(0o644)
    return omitted


def seal_stage():
    work = Path(tempfile.mkdtemp(prefix="d2-seal-"))
    stage = work / "stage-r2"
    snapshot = stage / "packs/d2-nodes-comfyui/xeb966b9"
    folder = snapshot / "d2-nodes-comfyui-HEAD"
    folder.mkdir(parents=True)
    omissions = stage_copy(PACK, folder)
    omissions += stage_copy(V2, folder / "v2", converted=True)
    pristine_omissions = [row for row in omissions if row["sibling"] == "pristine"]
    pristine_digest = hashlib.sha256("".join(
        f"{row['path']}\t{row['sha256']}\n" for row in sorted(
            pristine_omissions, key=lambda row: row["path"])).encode()).hexdigest()
    pristine_bytes = sum((PACK / row["path"]).stat().st_size for row in pristine_omissions)
    assert len(pristine_omissions) == 118 and pristine_bytes == 28507353
    assert pristine_digest == "cf7c377e6f393c43cb9e89e4fe2f5883d4b5fe5e4864bd922dd0ed73b8a75ed1"
    REPORT["canonical_pristine_omissions"] = {
        "count": 118, "bytes": pristine_bytes, "digest": pristine_digest,
        "matches_independent_canonical_plan": True}
    omission_bytes = (json.dumps({"files": omissions}, indent=2, sort_keys=True) + "\n").encode()
    (stage / "OMISSIONS.json").write_bytes(omission_bytes)
    (RESULTS / "OMISSIONS.json").write_bytes(omission_bytes)
    meta, diff = packpair_tool.generate(snapshot)
    real_meta, real_diff = packpatch.generate(snapshot)
    assert meta == real_meta and diff == real_diff, "lane pair differs from real overlay generator"
    patches = stage / "patches/d2-nodes-comfyui/xeb966b9"
    patches.mkdir(parents=True)
    prefix = patches / "d2-nodes-comfyui-xeb966b9"
    prefix.with_suffix(".json").write_text(json.dumps(meta, indent=1) + "\n")
    prefix.with_suffix(".diff").write_text(diff)
    for row in meta["files"]:
        if row["op"] != "delete":
            assert row["mode"] == 0o644
    fresh = work / "replay/packs/d2-nodes-comfyui/xeb966b9"
    fresh.mkdir(parents=True)
    shutil.copytree(folder, fresh / folder.name, ignore=shutil.ignore_patterns("v2"))
    packpair_tool.apply(fresh, meta, diff)
    compared = packpair_tool.cmptree(fresh / folder.name / "v2", folder / "v2")
    assert not any(compared[k] for k in ["missing_in_a", "missing_in_b", "bytes_differ", "modes_differ"])
    packpatch.validate_tree(fresh / folder.name / "v2", folder / "v2")
    loaded = packdb.load_pack(snapshot, mount_name="custom_nodes.d2_recovery_stage")
    assert set(loaded.node_mappings) == set(json.loads((V2 / "secure-nodes.json").read_bytes())["nodes"])
    assert len(loaded.node_mappings) == 70 and loaded.web_directory is None and not loaded.routes
    entry = {
        "commit": "eb966b9f38e816d84b584b05de45ef678fe7c0fc", "key": "xeb966b9",
        "pack": "d2-nodes-comfyui-HEAD", "upstream": "https://github.com/da2el-ai/d2-nodes-comfyui",
    }
    (stage / "packs-json-entry.json").write_text(json.dumps(entry, indent=2, sort_keys=True) + "\n")
    for path in stage.rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o644)
    sums = "".join(f"{sha(p)}  {p.relative_to(stage).as_posix()}\n"
                   for p in sorted(stage.rglob("*")) if p.is_file())
    (stage / "SHA256SUMS").write_text(sums)
    (stage / "SHA256SUMS").chmod(0o644)
    archive = RESULTS / "stage-r2.tar.gz"
    with tarfile.open(archive, "w:gz") as output:
        output.add(stage, arcname="stage-r2")
    REPORT["stage_archive"] = {"path": str(archive), "sha256": sha(archive),
                               "size_bytes": archive.stat().st_size}
    REPORT["pair"] = {"counts": meta["counts"], "manifest_sha256": sha(prefix.with_suffix(".json")),
                       "diff_sha256": sha(prefix.with_suffix(".diff")),
                       "real_generator_matches": True}
    REPORT["replay"] = compared
    REPORT["loader_registered"] = len(loaded.node_mappings)
    REPORT["web_directory"] = None
    REPORT["omission_count"] = len(omissions)


def main():
    RESULTS.mkdir(exist_ok=True)
    new = parity.load_v2()
    encoded = parity.encode(new)
    assert encoded == (V2 / "secure-nodes.json").read_bytes()
    manifest = json.loads(encoded)
    REPORT["manifest_sha256"] = hashlib.sha256(encoded).hexdigest()
    REPORT["manifest_size_bytes"] = len(encoded)
    REPORT["encoder"] = {"file": packmanifest.__file__, "sha256": sha(Path(packmanifest.__file__))}
    verify_schemas(manifest)
    status = json.loads((V2 / "CONVERSION-STATUS.json").read_text())
    counts = {tag: sum(row["status"] == tag for row in status["nodes"])
              for tag in ["CONVERTED-BACKEND", "PARTIAL", "REFUSED-AS-DESIGNED"]}
    assert counts == {"CONVERTED-BACKEND": 21, "PARTIAL": 3, "REFUSED-AS-DESIGNED": 46}
    assert set(row["node_id"] for row in status["nodes"]) == set(manifest["nodes"])
    REPORT["counts"] = counts
    assert (V2 / "nodes/modules/text_util.py").read_bytes() == (PACK / "nodes/modules/text_util.py").read_bytes()
    assert (V2 / "nodes/modules/nai_prompt_util.py").read_bytes() == (PACK / "nodes/modules/nai_prompt_util.py").read_bytes()
    seal_stage()
    (RESULTS / "artifacts.json").write_text(json.dumps(REPORT, indent=2, sort_keys=True) + "\n")
    print(json.dumps(REPORT, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    def timed_out(signum, frame):
        raise TimeoutError("finite artifact-sealing budget exceeded: 240 seconds")
    signal.signal(signal.SIGALRM, timed_out)
    signal.alarm(240)
    try:
        main()
    except BaseException as error:
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / "artifact-failure.json").write_text(json.dumps({
            "error_type": type(error).__name__, "message": str(error),
            "traceback": traceback.format_exc(), "partial_report": REPORT,
        }, indent=2, sort_keys=True) + "\n")
        raise
    finally:
        signal.alarm(0)
