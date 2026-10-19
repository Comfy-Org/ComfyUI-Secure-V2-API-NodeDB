"""Prepared one-attempt real original/SDK plus canonical generation job."""
import argparse
import json
from pathlib import Path
import resource
import signal
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent))
import support as s


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--input-manifest-sha256", required=True)
    parser.add_argument("--scratch", required=True, type=Path)
    parser.add_argument("--authorization-message", required=True)
    args = parser.parse_args()
    if not args.execute:
        print("SOURCE_ONLY_UNRUN; explicit Root Mac sequencing and --execute required")
        return 2
    s.require(args.authorization_message not in {"ROOT_SEQUENCE_MAIL_PENDING", "m_0da4e82b2d", "m_2c8098c04f", "m_2c6904a2d3", "m_68445dee27", "m_53c64c8643"}, "Preparation/Size/PC-hold message is not a Resolution Ratio run grant")
    report = {"status": "PRECHECK_FAILED", "commands": [], "actual_sdk_attempts": 0,
        "normal_generation_attempts": 0, "root_execution_mail": args.authorization_message,
        "hard_memory_cap_bytes": None, "cpu_quota": None, "managed_runtime_claim": False,
        "frontend_or_service_or_registry_acceptance": False,
        "network_control": "Unsandboxed controller; every child uses actual sandbox-exec deny network*."}
    scratch = None
    code = 1
    signal.signal(signal.SIGTERM, s.stop)
    signal.signal(signal.SIGALRM, s.stop)
    signal.setitimer(signal.ITIMER_REAL, max(.001, s.DEADLINE - time.monotonic()))
    try:
        s.packet(args.input_manifest_sha256)
        spec = json.loads((s.ROOT / "JOB_SPEC.json").read_bytes())
        actual = json.loads((s.ROOT / "inputs/ACTUAL_MAC_PROFILE.json").read_bytes())
        science = json.loads((s.ROOT / "inputs/SCIENCE_BINDING.json").read_bytes())
        python, site, core = s.verify_runtime(actual, science)
        backend_args = argparse.Namespace(backend_root=Path(spec["actual_mac_binding"]["backend_source_root"]),
                                          backend_commit=spec["actual_mac_binding"]["overlay_commit"])
        backend, tools = s.verify_backend(backend_args, spec)
        source = json.loads((s.ROOT / "inputs/SOURCE_BINDING.json").read_bytes())
        candidate = s.inventory(s.ROOT / "candidate")
        s.require({name: row["sha256"] for name, row in candidate.items()} == source["candidate_files"], "Frozen12-file candidate differs")
        s.require(args.scratch.is_absolute() and not args.scratch.exists() and not args.scratch.is_symlink(), "Fresh absolute scratch required")
        scratch = args.scratch.parent.resolve(strict=True) / args.scratch.name
        s.require(not scratch.is_relative_to(s.ROOT) and not s.ROOT.is_relative_to(scratch), "Scratch overlaps sealed packet")
        scratch.mkdir(mode=0o700)
        (scratch / "temporary").mkdir(mode=0o700)
        relative = Path(spec["slug"]) / ("x" + spec["commit"][:7])
        snapshot = scratch / "packs" / relative
        pack = snapshot / spec["folder"]
        s.original(pack)
        pristine = s.inventory(pack)
        s.require({name: row["sha256"] for name, row in pristine.items()} == source["original_files"], "Pristine7 Git source differs")
        v2 = pack / "v2"
        v2.mkdir(mode=0o700)
        for name in candidate:
            target = v2 / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(s.file_at(s.ROOT / "candidate", name).read_bytes())
            target.chmod(0o644)
        cmd = ["/usr/bin/sandbox-exec", "-f", s.ROOT / "inputs/deny-network.sb", python, "-I", "-S", "-B"]
        sdk_result_path = scratch / "ACTUAL_SDK_RESULT.json"
        report["actual_sdk_attempts"] = 1
        s.run(cmd + [s.ROOT / "actual_sdk_driver.py", "--backend", backend, "--site", site, "--core", core,
                     "--original", pack, "--candidate", v2, "--output", sdk_result_path], scratch, "sdk_parity", report)
        s.require(sdk_result_path.is_file() and sdk_result_path.stat().st_size <= 256 * 1024, "Actual SDK result absent/oversized")
        sdk_result = json.loads(sdk_result_path.read_bytes())
        s.require(sdk_result["status"] == "PASS_REAL_ORIGINAL_AND_SELECTED_SDK_BACKEND_ONLY"
                  and sdk_result["execution_comparisons"] == 1033 and sdk_result["validator_comparisons"] == 1033,
                  "Real original/SDK coverage incomplete")
        s.require(len(sdk_result["guard_denials"]) == 33 and len(sdk_result["negative_controls"]) == 3
                  and all(row["detected"] for row in sdk_result["negative_controls"]), "Guard/control coverage incomplete")
        s.require(s.inventory(v2) == candidate, "Actual SDK test changed frozen source")
        report["normal_generation_attempts"] = 1
        s.run(cmd + [s.ROOT / "invoke_manifest.py", "--backend", backend, "--site", site, "--core", core,
                     "--v2", v2, "--generator", s.ROOT / "generate_popular_pack_manifest.py"], scratch, "normal_generate", report)
        (v2 / "secure-nodes.json").chmod(0o644)
        normal = json.loads((v2 / "secure-nodes.json").read_bytes())
        s.require(set(normal["nodes"]) == {"ResolutionAndRatio"} and normal["web_directory"] == "web", "Generated node/frontend declaration differs")
        node = normal["nodes"]["ResolutionAndRatio"]
        s.require(node["validation_inputs"] == sdk_result["validator_signature_encoded_by_actual_encoder"], "Generated validator signature differs from real SDK check")
        s.require(normal["runtime"]["python"]["resolved"] == "3.13", "Runtime declaration differs")
        expected = s.inventory(v2)
        s.require(set(expected) == set(candidate), "Generated source file set differs")
        for name, row in candidate.items():
            if name != "secure-nodes.json":
                s.require(expected[name] == {"sha256": row["sha256"], "git_mode": "100644"}, "Generator changed existing code/source: " + name)
        s.require({n: r for n, r in s.inventory(pack).items() if not n.startswith("v2/")} == pristine, "Pristine changed")
        patches = scratch / "patches" / relative
        pair = patches / (spec["slug"] + "-x" + spec["commit"][:7])
        tool = backend / "comfy_secure_nodes/packpatch.py"
        s.run(cmd + [tool, "generate", snapshot, patches], scratch, "pair_generate", report)
        s.run(cmd + [tool, "bundle", pair, pair.with_suffix(".zip")], scratch, "pair_bundle", report)
        for kind, action, artifact in (("pair", "apply", pair), ("zip", "apply-zip", pair.with_suffix(".zip"))):
            replay = scratch / ("replay-" + kind) / relative
            replay_pack = replay / spec["folder"]
            s.original(replay_pack)
            s.run(cmd + [tool, action, replay, artifact], scratch, "replay_" + kind, report)
            s.require(s.inventory(replay_pack / "v2") == expected, "Replay byte/Git-mode mismatch: " + kind)
            s.require({n: r for n, r in s.inventory(replay_pack).items() if not n.startswith("v2/")} == pristine, "Replay pristine changed")
        post = {}
        for key, root, pins in (("sdk", site, actual["sdk_files"]), ("core", core, actual["core_files"]),
                                ("science", site, science["site_file_pins"]), ("candidate", s.ROOT / "candidate", source["candidate_files"]),
                                ("backend", backend, {n: r["sha256"] for n, r in tools.items()})):
            observed = {name: s.sha(s.file_at(root, name)) for name in pins}
            s.require(observed == pins, "Post-attempt selected inputs differ: " + key)
            post[key] = observed
        post_path = scratch / "POST_GENERATION_READBACK.json"
        post_path.write_text(json.dumps(post, indent=2) + "\n")
        report.update(status="PASS_REAL_RESOLUTION_BACKEND_SDK_NORMAL_ENCODER_AND_CANONICAL_REPLAYS_ONLY",
            actual_sdk_result_sha256=s.sha(sdk_result_path), normal_manifest_sha256=s.sha(v2 / "secure-nodes.json"),
            v2_files=expected, artifact_files=s.inventory(patches), post_generation_readback_sha256=s.sha(post_path),
            frontend_acceptance="NOT_RUN; existing actual frontend acceptance remains separate")
        code = 0
    except BaseException as error:
        report.update(status="FAILED_ACTUAL_ATTEMPT" if report["actual_sdk_attempts"] else "PRECHECK_FAILED",
                      error_type=type(error).__name__, error=str(error)[:1024])
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if any(not row.get("cleanup", {}).get("confirmed", False) for row in report["commands"]):
            report["status"] = "FAILED_OWNED_GROUP_CLEANUP"
            code = 1
        report["elapsed_seconds"] = round(time.monotonic() - s.STARTED, 6)
        if sys.platform == "darwin":
            report["observed_children_maxrss_bytes_darwin"] = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        if scratch is not None:
            (scratch / "RESULT.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"status": report["status"], "scratch": str(scratch) if scratch else None, "error": report.get("error")}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
