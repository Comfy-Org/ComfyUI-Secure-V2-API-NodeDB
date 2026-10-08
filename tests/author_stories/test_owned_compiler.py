"""No host compiler RPC or filesystem-policy change is used by this gate."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path[:0] = [os.environ["COMFY_CORE_ROOT"], str(Path(os.environ["MANY_OVERLAY_ROOT"]) / "backend")]
from comfy.cli_args import args
args.cpu = True
import execution
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession


def test_installed_declared_compiler_builds_and_executes_only_in_owned_scratch(tmp_path):
    async def run():
        for index in range(2):
            root = tmp_path / f"compiler-pack-{index}"
            shutil.copytree(HERE / "compiler_pack", root)
            profile_path = root / "profile.json"
            profile = json.loads(profile_path.read_text())
            if "artifact_root" in profile:
                source_root = profile["artifact_root"]
                actual_root = str(root / "toolchain")
                profile["compiler"] = profile["compiler"].replace(source_root, actual_root)
                profile["flags"] = [flag.replace(source_root, actual_root) for flag in profile["flags"]]
                profile["artifact_root"] = actual_root
                profile_path.write_text(json.dumps(profile, indent=2) + "\n")
            spec = importlib.util.spec_from_file_location(f"many_compiler_{index}", root / "__init__.py",
                                                         submodule_search_locations=[str(root)])
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            cls = module.NODE_CLASS_MAPPINGS["ManyOwnedScratchCompiler"]
            cls.GET_SCHEMA()
            session = await GuestSession(f"compiler-{index}", guest_runtime_root=root).start()
            prior = _sdk.providers.execution_backend

            class Backend:
                async def dispatch(self, plan, local_call, runtime):
                    assert plan.permissions == ()
                    return await session.execute(plan, runtime, capabilities=(), tenant="compiler-fixture")

            _sdk.providers.register_execution_backend(Backend())
            try:
                assert session.sandbox_kind == os.environ["AUTHOR_SANDBOX_KIND"]
                mapped = await execution._async_map_node_over_list("compiler-story", "1", cls, {}, cls.FUNCTION)
                value = (await execution.resolve_map_node_over_list_results(mapped))[0]
                report = json.loads(value.result[0])
                assert report["compiled"] and report["executed"] and report["cleanup"]
                assert report["capabilities"] == []
                print("OWNED_COMPILER_REPORT", json.dumps(report, sort_keys=True))
            finally:
                _sdk.providers.register_execution_backend(prior)
                await session.kill()
    asyncio.run(run())
