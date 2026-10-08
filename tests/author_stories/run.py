"""Run actual pinned pack consumers without changing provider or corpus sources."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import stat
import subprocess
import sys
import time
import urllib.request

HERE = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    require(path.is_file() and not path.is_symlink(), f"Missing regular file: {path}")
    return {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size, "mode": stat.S_IMODE(path.stat().st_mode)}


def tree(root):
    result = {}
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink(), f"Source symlink refused: {path}")
        require(path.name != "__pycache__" and path.suffix != ".pyc",
                f"Bytecode in source tree: {path}")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = digest(path)
    return result


def command_output(command, cwd=None):
    return subprocess.check_output(command, cwd=cwd, text=True).strip()


def identity(root):
    return {"root": str(root), "head": command_output(["git", "rev-parse", "HEAD"], root),
            "dirty": command_output(["git", "status", "--porcelain"], root)}


def corpus_sources(corpus, pins):
    index = json.loads((corpus / "packs/packs.json").read_text())
    roots = {}
    for slug, record in pins["packs"].items():
        require(index.get(slug) == record["source"], f"Catalogue pin mismatch: {slug}")
        root = corpus / record["root"]
        expected = {r["path"]: {k: r[k] for k in ("sha256", "bytes", "mode")}
                    for r in record["files"]}
        require(tree(root) == expected, f"Complete pinned tree mismatch: {slug}")
        for row in record["artifacts"]:
            require(digest(corpus / row["path"]) == {k: row[k] for k in ("sha256", "bytes", "mode")},
                    f"Pair/manifest mismatch: {row['path']}")
        roots[slug] = root
    return roots


def provider_sources(core, overlay, frontend):
    groups = {
        "core": (core, ["comfy_api/latest/_sdk.py", "comfy_api/latest/_io.py",
                         "comfy_api/latest/_sdk_public.pyi", "comfy_api/latest/api-spec.json", "execution.py"]),
        "overlay": (overlay, ["backend/comfy_secure_nodes/" + name for name in
                              ["transport/host.py", "transport/wire.py", "guest/__init__.py",
                               "transport/sandbox.py", "execution.py", "packruntime.py", "storage.py",
                               "storage_values.py", "packstorage_routes.py", "packroutes.py"]] +
                             ["frontend/src/" + name for name in ["host-entry.mjs", "guest.mjs", "ui-renderer.mjs"]]),
    }
    if frontend:
        groups["frontend"] = (frontend, ["src/" + name for name in
            ["platform/nodeApi/asyncWidgetSerialization.ts", "platform/nodeApi/widgetHandle.ts",
             "platform/nodeApi/graphHandle.ts", "platform/nodeApi/nodeHandle.ts",
             "platform/nodeApi/defsRegistry.ts", "platform/nodeApi/closedProxy.ts",
             "utils/executionUtil.ts", "lib/litegraph/src/LGraph.ts", "lib/litegraph/src/LGraphNode.ts",
             "lib/litegraph/src/extensionPersistence.ts"]])
        if (frontend / "src/platform/nodeApi/nativeOwnedElement.ts").exists():
            groups["frontend"][1].extend(["src/platform/nodeApi/nativeOwnedElement.ts", "src/platform/nodeApi/ownedElementHandle.ts",
                "src/platform/nodeApi/comfyApi.ts", "src/platform/nodeApi/nativeOwnedElement.test.ts",
                "docs/node-api/comfy-api.d.ts", "src/platform/nodeApi/apiSurface.ts"])
    return {f"{label}/{name}": digest(root / name)
            for label, (root, names) in groups.items() for name in names}


def stage_sources(destination, roots):
    destination.mkdir()
    for name in ["test_consumer_stories.py", "test_queued_metadata.py", "test_owned_compiler.py", "worker_storage_gate.mjs", "browser_gate.mjs", "owned_metadata_gate.mjs"]:
        shutil.copy2(HERE / name, destination / name)
    shutil.copytree(HERE / "consumer_pack", destination / "consumer_pack")
    shutil.copytree(HERE / "compiler_pack", destination / "compiler_pack")
    mask = roots["comfyui-my-mask"]
    shutil.copytree(mask / "v2", destination / "consumer_pack/converted")
    shutil.copytree(mask, destination / "mask")
    (destination / "source_original").mkdir()
    for path in mask.iterdir():
        if path.is_file():
            shutil.copy2(path, destination / "source_original" / path.name)
    shutil.copytree(roots["comfyui-comfyroll-customnodes"] / "v2", destination / "templates/comfyroll")
    shutil.copytree(roots["comfyui-inversednoise"], destination / "templates/inverse")
    shutil.copytree(roots["comfyui-simple_readable_metadata-sg"] / "v2", destination / "metadata-v2")
    changes = []
    for relative in ["mask/v2/tests/test_my_mask.py", "templates/inverse/v2/tests/test_amy_inverse_conversion.py"]:
        path = destination / relative
        before = digest(path)
        text = path.read_bytes().decode()
        needle = "session.sandbox_kind=='seatbelt'"
        require(needle in text, f"Expected test-only platform assertion absent: {relative}")
        text = text.replace(needle, "session.sandbox_kind==os.environ['AUTHOR_SANDBOX_KIND']")
        path.write_bytes(text.encode())
        changes.append({"path": relative, "before": before, "after": digest(path),
                        "adaptation": "Test-only expected sandbox kind; algorithms and admission unchanged"})
    return changes


def scoped_metadata(stage):
    path = stage / "metadata-v2/web/Simple_Readable_Metadata_Text_Viewer_SG.js"
    before = digest(path)
    text = path.read_bytes().decode()
    require(text.count("comfy.element(state.elementName)") == 3, "Metadata scoped-call preimage mismatch")
    marker = "state.elementName = `srm-viewer-${node.id}`;"
    require(text.count(marker) == 1, "Metadata scope owner preimage mismatch")
    text = text.replace(marker, marker + " state.elementScope = {nodeId:node.id,widget:'textDisplay'};")
    text = text.replace("comfy.element(state.elementName)", "comfy.element(state.elementName,state.elementScope)")
    path.write_bytes(text.encode())
    return {"path": str(path.relative_to(stage)), "before": before, "after": digest(path),
            "adaptation": "NEW consumer scope bound to its exact node/widget; frozen original remains unchanged"}


def shared_alias_metadata(stage):
    root = stage / "metadata-v2-shared"
    shutil.copytree(stage / "metadata-v2", root)
    path = root / "web/Simple_Readable_Metadata_Text_Viewer_SG.js"
    before = digest(path)
    text = path.read_bytes().decode()
    needle = "state.elementName = `srm-viewer-${node.id}`;"
    require(text.count(needle) == 1, "Shared-alias fixture preimage mismatch")
    path.write_bytes(text.replace(needle, "state.elementName = 'srm-shared-viewer';").encode())
    return {"path": str(path.relative_to(stage)), "before": before, "after": digest(path),
            "adaptation": "Test-only identical element alias across actual Metadata callbacks/mounts; production names remain distinct"}


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def execute_stage(name, command, cwd, environment, output, count=None):
    log = output / (name + ".log")
    started = time.monotonic()
    try:
        with log.open("wb") as stream:
            result = subprocess.run(command, cwd=cwd, env=environment, stdout=stream,
                                    stderr=subprocess.STDOUT, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as error:
        (output / (name + "-failure.json")).write_text(json.dumps({"stage": name, "command": command,
            "exception": type(error).__name__, "message": str(error), "log": {"path": str(log), **digest(log)},
            "acceptance": "failed; no skip/fallback"}, indent=2) + "\n")
        raise
    text = log.read_text()
    if result.returncode:
        (output / (name + "-failure.json")).write_text(json.dumps({"stage": name, "command": command,
            "exit_code": result.returncode, "log": {"path": str(log), **digest(log)},
            "acceptance": "failed; no skip/fallback"}, indent=2) + "\n")
    require(result.returncode == 0, f"{name} failed; see {log}")
    require(" skipped" not in text.lower(), f"Acceptance skip refused: {log}")
    if count is not None:
        import re
        matches = re.findall(r"(?:^|\s)(\d+) passed", text)
        require(matches and int(matches[-1]) == count, f"Unexpected accepted test count: {log}")
    return {"stage": name, "command": command, "cwd": str(cwd), "seconds": time.monotonic() - started,
            "exit_code": result.returncode, "log": {"path": str(log), **digest(log)}}


def run(args):
    stories = set(range(1, 7)) if args.stories == "all" else {int(x) for x in args.stories.split(",")}
    require(stories and stories <= set(range(1, 7)), "Choose stories 1–6")
    require(args.repeat >= 2, "Acceptance requires two unchanged-source runs")
    if 5 in stories:
        require(args.frontend is not None and (args.frontend / "src/platform/nodeApi/nativeOwnedElement.ts").is_file(),
                "Story 5 requires the published native owned-element provider")
    compiler_profile = None
    if 6 in stories and args.compiler_mode != "wheel-only":
        require(args.compiler_profile is not None,
                "Story 6 requires an installed, declared compiler profile; wheel-only mode is explicitly partial")
        compiler_profile = json.loads(args.compiler_profile.read_text())
        require(type(compiler_profile["compiler"]) is str and Path(compiler_profile["compiler"]).is_absolute(), "Compiler must be an explicit absolute profile path")
        require(type(compiler_profile["flags"]) is list and all(type(x) is str for x in compiler_profile["flags"]), "Invalid declared compiler flags")
        require(compiler_profile["identities"] and compiler_profile["headers"], "Compiler and header identities required")
        for row in compiler_profile["identities"] + compiler_profile["headers"]:
            require(digest(Path(row["path"])) == {k: row[k] for k in ("sha256", "bytes", "mode")}, "Installed toolchain identity mismatch")
        require(compiler_profile["compiler"] in [r["path"] for r in compiler_profile["identities"]], "Compiler identity not bound")
        if "artifact_root" in compiler_profile:
            require(compiler_profile["architecture"] == platform.machine(), "Toolchain architecture mismatch")
            require(tree(Path(compiler_profile["artifact_root"])) == compiler_profile["artifact_files"], "Immutable toolchain closure mismatch")
    output = args.output.resolve()
    require(not output.exists(), "Use a new output directory; historical receipts are immutable")
    pins = json.loads((HERE / "pins.json").read_text())
    roots = corpus_sources(args.corpus, pins)
    profile = json.loads(args.profile.read_text())
    require(profile["network_denial_errno"] == [1, 13],
            "This narrow socket control admits only permission refusal; disconnected-loopback errno requires a separately reviewed provider test")
    version = json.loads(command_output([args.python, "-c", "import json,sys;print(json.dumps(list(sys.version_info[:2])))"]))
    require(version == profile["python_major_minor"], "Python/profile mismatch")
    output.mkdir(parents=True)
    frontend = None
    if stories & {2, 5}:
        require(args.frontend and args.frontend_deps, "UI stories require frontend source and installed dependency roots")
        frontend = output / "frontend-fixture"
        head = identity(args.frontend)["head"]
        command_output(["git", "worktree", "add", "--detach", str(frontend), head], args.frontend)
        require((args.frontend_deps / "node_modules").is_dir(), "Frontend node_modules unavailable")
        (frontend / "node_modules").symlink_to(args.frontend_deps / "node_modules", target_is_directory=True)
        fixture = frontend / "temp/author-stories"
        shutil.copytree(HERE / "frontend_fixture", fixture)
        shutil.copy2(fixture / "manyAuthorSerialization.test.ts", frontend / "src/platform/nodeApi/manyAuthorSerialization.test.ts")
        shutil.copytree(args.overlay / "frontend/src", fixture / "provider")
        shutil.copy2(roots["comfyui-simple_readable_metadata-sg"] / "v2/web/Simple_Readable_Metadata_Save_Text_SG.js", fixture / "SaveText_SG.js")
    original_sources = provider_sources(args.core, args.overlay, frontend)
    original_pipeline = tree(HERE)
    receipts = []
    for number in range(1, args.repeat + 1):
        run_root = output / f"run-{number}"
        run_root.mkdir()
        stage = run_root / "fixtures"
        adaptations = stage_sources(stage, roots)
        if 5 in stories:
            adaptations.append(scoped_metadata(stage))
            adaptations.append(shared_alias_metadata(stage))
        if compiler_profile:
            staged_profile = dict(compiler_profile)
            if "artifact_root" in compiler_profile:
                source_toolchain = Path(compiler_profile["artifact_root"])
                toolchain = stage / "compiler_pack/toolchain"
                shutil.copytree(source_toolchain, toolchain)
                require(tree(toolchain) == compiler_profile["artifact_files"], "Staged toolchain closure mismatch")
                staged_profile["compiler"] = str(toolchain / Path(compiler_profile["compiler"]).relative_to(source_toolchain))
                staged_profile["flags"] = [flag.replace(str(source_toolchain), str(toolchain)) for flag in compiler_profile["flags"]]
                staged_profile["artifact_root"] = str(toolchain)
                adaptations.append({"adaptation": "Exact immutable host-provisioned toolchain copied inside existing admitted fixture root; fixed paths relocated, no policy change",
                                    "source": str(source_toolchain), "staged": str(toolchain), "files": compiler_profile["artifact_files"]})
            (stage / "compiler_pack/profile.json").write_text(json.dumps(staged_profile, indent=2) + "\n")
        before = tree(stage)
        environment = {**os.environ, "PATH": str(Path(args.node).parent) + os.pathsep + os.environ.get("PATH", ""),
                       "COMFY_CORE_ROOT": str(args.core), "MANY_OVERLAY_ROOT": str(args.overlay),
                       "PYTHONPATH": f"{args.core}:{args.overlay}/backend", "PYTHONDONTWRITEBYTECODE": "1",
                       "COMFY_SECURE_SANDBOX_MODE": "required", "AUTHOR_RUNTIME_PROFILE": str(args.profile),
                       "AUTHOR_SANDBOX_KIND": profile["sandbox_kind"], "AUTHOR_BROWSER_DEPS": str(args.browser_deps),
                       "AUTHOR_NODE": args.node}
        stages = []
        pytest = [args.python, "-B", "-m", "pytest", "-p", "no:cacheprovider", "-q", "-s", "--tb=short"]
        selection = {1: "test_frontend_http_authored_text_read_by_actual_comfyroll_node_in_recreated_render",
                     3: "test_actual_mask_algorithm_named_data_hit_miss_expiry_fresh_render_account_pack_isolation",
                     6: "test_declared_wheels_actually_execute_without_acquiring_default_network"}
        tests = [str(stage / "test_consumer_stories.py") + "::" + name for story, name in selection.items()
                 if story in stories and not (story == 6 and args.compiler_mode == "compiler-only")]
        if tests:
            stages.append(execute_stage("documents-cache-authority", pytest + tests, stage, environment, run_root, len(tests)))
        if compiler_profile:
            stages.append(execute_stage("owned-scratch-compiler", pytest + [str(stage / "test_owned_compiler.py")], stage, environment, run_root, 1))
        if 5 in stories:
            stages.append(execute_stage("owned-elements-native", [args.pnpm, "--config.verify-deps-before-run=false", "test:unit",
                "src/platform/nodeApi/nativeOwnedElement.test.ts"], frontend, environment, run_root, 10))
            stages.append(execute_stage("owned-metadata-worker", [args.node, str(stage / "owned_metadata_gate.mjs")], stage, environment, run_root))
            stages.append(execute_stage("owned-metadata-shared-alias-worker", [args.node, str(stage / "owned_metadata_gate.mjs")],
                stage, {**environment, "AUTHOR_SHARED_ALIAS": "1"}, run_root))
        if 4 in stories:
            stages.append(execute_stage("mask", pytest + [str(stage / "mask/v2/tests/test_my_mask.py"), "-k", "two_fresh_required or every_source_dtype"], stage, environment, run_root, 145))
            stages.append(execute_stage("untrained-model", pytest + [str(stage / "templates/inverse/v2/tests/test_amy_inverse_conversion.py"), "-k", "two_fresh_required or real_guest_ctx"], stage, environment, run_root, 2))
        if 2 in stories:
            environment["AUTHOR_FRONTEND_COMMIT"] = identity(frontend)["head"]
            environment["AUTHOR_FRONTEND_FIXTURE"] = str(frontend / "temp/author-stories")
            port = free_port()
            environment["AUTHOR_BROWSER_PORT"] = str(port)
            environment["AUTHOR_BROWSER_BASE"] = f"http://127.0.0.1:{port}"
            environment["MANY_BROWSER_RESULT"] = str(run_root / "serialization-browser.log")
            stages.append(execute_stage("serialization-native", [args.pnpm, "--config.verify-deps-before-run=false", "test:unit",
                "src/platform/nodeApi/manyAuthorSerialization.test.ts", "src/platform/nodeApi/asyncWidgetSerialization.test.ts"], frontend, environment, run_root, 31))
            with (run_root / "vite.log").open("wb") as stream:
                server = subprocess.Popen([args.node, str(frontend / "node_modules/vite/bin/vite.js"), "--config", "temp/author-stories/vite.config.ts"],
                                          cwd=frontend, env=environment, stdout=stream, stderr=subprocess.STDOUT)
                try:
                    deadline = time.monotonic() + 20
                    while True:
                        require(server.poll() is None, "Frontend fixture server exited; see vite.log")
                        try:
                            urllib.request.urlopen(environment["AUTHOR_BROWSER_BASE"], timeout=1).close()
                            break
                        except OSError:
                            require(time.monotonic() < deadline, "Frontend fixture server readiness failed")
                            time.sleep(.1)
                    stages.append(execute_stage("serialization-browser", [args.node, str(stage / "browser_gate.mjs")], frontend, environment, run_root))
                finally:
                    server.terminate()
                    try:
                        server.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait()
            stages.append(execute_stage("serialization-python", pytest + [str(stage / "test_queued_metadata.py")], stage, environment, run_root, 1))
        require(before == tree(stage), "Fixture source changed during acceptance")
        require(original_sources == provider_sources(args.core, args.overlay, frontend), "Participating provider source changed")
        require(original_pipeline == tree(HERE), "Pipeline source changed")
        if compiler_profile:
            for row in compiler_profile["identities"] + compiler_profile["headers"]:
                require(digest(Path(row["path"])) == {k: row[k] for k in ("sha256", "bytes", "mode")}, "Toolchain changed during acceptance")
            if "artifact_root" in compiler_profile:
                require(tree(Path(compiler_profile["artifact_root"])) == compiler_profile["artifact_files"], "Toolchain closure changed")
        corpus_sources(args.corpus, pins)
        receipt = {"stories": sorted(stories), "stages": stages, "profile": profile, "profile_identity": digest(args.profile),
                   "compiler_mode": args.compiler_mode, "compiler_profile": compiler_profile,
                   "providers": original_sources, "provider_identities": {"core": identity(args.core), "overlay": identity(args.overlay),
                   "frontend": identity(frontend) if frontend else None}, "fixture_sources": before, "adaptations": adaptations,
                   "corpus_pin_manifest": digest(HERE / "pins.json"), "pipeline_sources": original_pipeline,
                   "before_after_unchanged": True,
                   "limits": ["Local required-confinement CPU; no Cloud durability, trained weights, GPU or positive service-grant acceptance",
                              "Compiler coverage is fixed small freestanding C only" if compiler_profile else "No actual compiler acceptance",
                              "Frontend class/definition and authentication registration are explicit fixtures",
                              "Borrowed frontend dependencies are test tooling, not a sealed runtime",
                              "DATA cache opt-in wrapper changes no-contour reference identity on cache hit",
                              "Actual scoped two-instance Metadata fixture" if 5 in stories else "Story 5 unexercised; selected stories never imply all-story acceptance"]}
        path = run_root / "receipt.json"
        path.write_text(json.dumps(receipt, indent=2) + "\n")
        receipts.append({"path": str(path), **digest(path)})
        print(f"Run {number}: selected stories {sorted(stories)} passed with unchanged sources", flush=True)
    accepted = stories - {6} if args.compiler_mode != "required" else stories
    (output / "receipt.json").write_text(json.dumps({"accepted_stories": sorted(accepted), "runs": receipts,
        "conversion_count_change": 0, "story_5": "passed" if 5 in stories else "unexercised", "story_6": args.compiler_mode}, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("core", "overlay", "corpus", "profile", "browser-deps", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("frontend", "frontend-deps", "compiler-profile"):
        parser.add_argument("--" + name, type=Path)
    for name in ("python", "node", "pnpm"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--stories", default="all")
    parser.add_argument("--compiler-mode", choices=["required", "wheel-only", "compiler-only"], default="required")
    parser.add_argument("--repeat", type=int, default=2)
    args = parser.parse_args()
    for name in ("core", "overlay", "corpus", "profile", "browser_deps", "frontend", "frontend_deps", "compiler_profile"):
        value = getattr(args, name)
        if value:
            setattr(args, name, value.resolve())
    run(args)


if __name__ == "__main__":
    main()
