"""Verify actual returned artifact bytes/metadata without supplied imports."""
from pathlib import Path
import csv
import hashlib
import json
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
RECEIVED = HERE / "received"
SOURCE = ROOT / "coordination/sizefrompresets-generation-macos-r2-20261019"
ATTEMPT = RECEIVED / "sizefrompresets-generation-macos-r2-attempt1"
SNAPSHOT = Path("comfyui-sizefrompresets/x05d2d9c/ComfyUI-SizeFromPresets-HEAD")
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
load = lambda path: json.loads(path.read_bytes())
capture = load(HERE / "CAPTURE_RECEIPT.json")
archive_rows = {row["path"]: row for row in capture["files"]}
manifest = load(RECEIVED / "MANIFEST.json")
assert {row["path"] for row in manifest["files"]} == set(archive_rows) - {"MANIFEST.json"}
for row in manifest["files"]:
    path = RECEIVED / row["path"]
    assert path.stat().st_size == row["bytes"] and sha(path) == row["sha256"]
for path in SOURCE.rglob("*"):
    if path.is_file():
        assert path.read_bytes() == (RECEIVED / SOURCE.name / path.relative_to(SOURCE)).read_bytes()
result_path = ATTEMPT / "RESULT.json"
assert sha(result_path) == "5217d9bf8d818aabcfab27f91c88be56ea57e220d71b36386e9ea83d8d1b6afa"
result = load(result_path)
outer_path = RECEIVED / "size-generation-r2-attempt1-outer/OUTER_RECEIPT.json"
outer = load(outer_path)
assert outer["exact_argv"] == load(SOURCE.with_suffix(".INVOCATION.json"))["argv"]
assert outer["attempts"] == 1 and outer["automatic_retries"] == 0 and outer["exit_code"] == 0
assert not outer["outer_watchdog_fired"] and outer["wall_seconds"] < 60
assert outer["outer_group_absent"] and outer["all_command_cleanups_confirmed"]
assert all(outer["command_groups_independently_absent"].values())
assert result["status"] == "PASS_SIZE_MAC_NORMAL_GENERATION_AND_CANONICAL_REPLAY_ONLY"
assert result["generator_attempts"] == 1
assert [row["name"] for row in result["commands"]] == ["generator", "pair_generate", "pair_bundle", "replay_pair", "replay_zip"]
for row in result["commands"]:
    assert row["exit_code"] == 0 and row["argv"][0] == "/usr/bin/sandbox-exec"
    assert row["cleanup"]["confirmed"] and row["cleanup"]["leader_reaped"] and row["cleanup"]["group_absence_confirmed"]
    assert not row["cleanup"]["errors"] and outer["command_groups_independently_absent"][str(row["pid"])]
spec = load(SOURCE / "JOB_SPEC.json")
profile = load(SOURCE / "inputs/ACTUAL_MAC_PROFILE.json")
post_path = ATTEMPT / "POST_GENERATION_READBACK.json"
post = load(post_path)
assert sha(post_path) == result["post_generation_readback_sha256"]
assert post["sdk"] == profile["sdk_files"] and len(post["sdk"]) == 141
assert post["core"] == profile["core_files"] and len(post["core"]) == 1384
assert post["science"] == load(SOURCE / "inputs/SCIENCE_BINDING.json")["site_file_pins"] and len(post["science"]) == 4
backend = load(SOURCE / "inputs/mac-readback/OVERLAY-SOURCE-INVENTORY.json")
assert post["backend"] == {name.removeprefix("backend/"): row["sha256"] for name, row in backend["files"].items()} and len(post["backend"]) == 83
candidate = {str(p.relative_to(SOURCE / "candidate")): sha(p) for p in (SOURCE / "candidate").rglob("*") if p.is_file()}
assert post["candidate"] == candidate and len(candidate) == 14
with zipfile.ZipFile(SOURCE / "inputs/ORIGINAL.zip") as archive:
    pristine = {item.filename: archive.read(item) for item in archive.infolist()}
trees = [ATTEMPT / kind / SNAPSHOT for kind in ("packs", "replay-pair", "replay-zip")]
expected = dict(candidate)
expected["pyproject.toml"] = spec["staged_pyproject_sha256"]
expected["secure-nodes.json"] = sha(trees[0] / "v2/secure-nodes.json")
for tree in trees:
    originals = {str(p.relative_to(tree)): p.read_bytes() for p in tree.rglob("*")
                 if p.is_file() and not p.is_relative_to(tree / "v2")}
    assert originals == pristine and len(originals) == 13
    actual = {str(p.relative_to(tree / "v2")): sha(p) for p in (tree / "v2").rglob("*") if p.is_file()}
    assert actual == expected and len(actual) == 15
    for path in tree.rglob("*"):
        if path.is_file():
            assert archive_rows[str(path.relative_to(RECEIVED))]["archive_mode"] == "0o644"
normal = load(trees[0] / "v2/secure-nodes.json")
assert set(normal) == {"format", "nodes", "runtime"} and normal["format"] == "comfy-secure-nodes-v1"
authority = load(ROOT / "coordination/sizefrompresets-manifest-source-r1-20261019/SOURCE_REVIEW.json")["node_authority"]
assert set(normal["nodes"]) == set(authority)
assert normal["runtime"] == {"python": {"requires": ">=3.13,<3.14", "resolved": "3.13"}}
for node_id, (refs, permissions) in authority.items():
    node = normal["nodes"][node_id]
    assert node["class"] == node_id and node["module"] == "api_nodes"
    assert node["sdk_refs"] is refs and node["permissions"] == permissions and not any(node["methods"].values())
    schema = node["schema"]
    assert schema["attrs"]["node_id"] == node_id and schema["attrs"]["category"] == "SizeFromPresets" and schema["hidden"] == []
    inputs = {row["attrs"]["id"]: row for row in schema["inputs"]}
    if "preset" in inputs:
        family = "sdxl" if "SDXL" in node_id else "sd15"
        with (SOURCE / "candidate/presets" / (family + ".csv")).open() as stream:
            rows = list(csv.reader(stream))[1:]
        digit = 4 if family == "sdxl" else 3
        options = [f"{int(w.strip()): >{digit}} x {int(h.strip()): >{digit}}" for w, h in rows]
        assert inputs["preset"]["attrs"]["options"] == options
    if "batch_size" in inputs:
        attrs = inputs["batch_size"]["attrs"]
        assert (attrs["default"], attrs["min"], attrs["max"]) == (1, 1, 4096)
    if "seed" in inputs:
        attrs = inputs["seed"]["attrs"]
        assert (attrs["default"], attrs["min"], attrs["max"]) == (0, 0, 2**64 - 1)
    if "is_sdxl" in inputs:
        assert inputs["is_sdxl"]["attrs"]["default"] is True
    latent = "EmptyLatent" in node_id
    assert [row["io_type"] for row in schema["outputs"]] == (["LATENT", "INT", "INT"] if latent else ["INT", "INT"])
    assert [row["attrs"]["id"] for row in schema["outputs"]] == (["latent", "w", "h"] if latent else ["w", "h"])
patches = ATTEMPT / "patches/comfyui-sizefrompresets/x05d2d9c"
pair = patches / "comfyui-sizefrompresets-x05d2d9c.json"
diff = pair.with_suffix(".diff")
bundle = pair.with_suffix(".zip")
pair_data = load(pair)
assert pair_data["format"] == "comfy-pack-patch/1" and pair_data["pack"] == "comfyui-sizefrompresets" and pair_data["key"] == "x05d2d9c"
assert {row["path"] for row in pair_data["files"]} == set(expected)
assert all(row["mode"] == 0o644 for row in pair_data["files"])
with zipfile.ZipFile(bundle) as archive:
    assert archive.testzip() is None and set(archive.namelist()) == {pair.name, diff.name}
    assert archive.read(pair.name) == pair.read_bytes() and archive.read(diff.name) == diff.read_bytes()
receipt = {"status": "VERIFIED_ACTUAL_NORMAL_GENERATION_AND_TWO_CANONICAL_REPLAYS_ONLY",
    "archive_sha256": capture["archive_sha256"], "archive_regular_files": 140,
    "returned_manifest_entries_verified": len(manifest["files"]), "result_sha256": sha(result_path),
    "normal_manifest_sha256": expected["secure-nodes.json"], "pair_sha256": sha(pair),
    "diff_sha256": sha(diff), "bundle_sha256": sha(bundle), "outer_receipt_sha256": sha(outer_path),
    "post_generation_sha256": sha(post_path), "original_count_per_tree": 13, "v2_count_per_tree": 15,
    "three_trees_bytes_and_git_modes_equal": True, "node_count": 10,
    "normal_node_authority_options_defaults_ranges_checked": True,
    "all_five_command_and_outer_groups_absent_in_actual_records": True,
    "postmaps": {"sdk": 141, "core": 1384, "science": 4, "backend": 83, "candidate": 14},
    "elapsed_seconds": outer["wall_seconds"], "observed_rss_bytes": outer["observed_children_maxrss_bytes_darwin"],
    "dependency_caveat": "MIKE reports prior accelerate96 additions under separate repair receipt; no dependency install in this generation job. Existing SDK/Core/science/tool pins match. Not blanket dependency certification.",
    "prior_dependency_receipt_sha256": outer["dependency_repair_receipt_sha256"],
    "supplied_code_executed_during_intake": False, "local_generator_or_replay_runs": 0,
    "service_guest_target_engine_or_whole_pack_acceptance": False,
    "production_v2": str(trees[0] / "v2"), "next": "Assemble actual-encoder TEST helper metadata, coordinate service slot, one positive10-output and one wrong-width control under m_53c64c8643."}
(HERE / "VERIFIED_RESULT_RECEIPT.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
print(json.dumps(receipt, indent=2))
