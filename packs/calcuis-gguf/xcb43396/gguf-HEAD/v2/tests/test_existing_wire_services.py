"""Real broker/wire with synthetic weights; no trained/provider/deployment claim."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

import pytest
import torch
from safetensors.torch import load_file
from safetensors import safe_open

sys.dont_write_bytecode = True
V2 = Path(__file__).resolve().parents[1]


def load(name, path, package=False):
    spec = importlib.util.spec_from_file_location(name, path, submodule_search_locations=[str(path.parent)] if package else None)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("node_name,permissions", [("StateDictWireControl", ("raw", "output")), ("RangeWireControl", ("assets",))])
def test_actual_guest_existing_public_services(node_name, permissions, tmp_path, monkeypatch):
    from comfy.cli_args import args
    monkeypatch.setattr(args, "cpu", True)
    from comfy_api.latest import _sdk
    from comfy_secure_nodes.transport.host import GuestSession
    from comfy_secure_nodes.transport.wire import WireError
    import folder_paths

    output_dir = tmp_path / "managed-output"
    output_dir.mkdir()
    monkeypatch.setattr(folder_paths, "output_directory", str(output_dir))
    catalogue = tmp_path / "synthetic-operator-catalogue"
    catalogue.mkdir()
    (catalogue / "fixture.gguf").write_bytes(b"0123456789abcdef")
    monkeypatch.setitem(folder_paths.folder_names_and_paths, "checkpoints", ([str(catalogue)], {".gguf"}))

    async def run():
        pids = []
        results = []
        for render in range(2):
            current = tmp_path / (node_name + str(render))
            shutil.copytree(V2, current)
            shutil.copyfile(V2 / "tests/wire_control.py", current / "wire_control.py")
            prefix = "moe_gguf_wire_" + node_name + str(render)
            load(prefix, current / "__init__.py", True)
            control = load(prefix + ".wire_control", current / "wire_control.py")
            node = getattr(control, node_name)
            session = await GuestSession(prefix, guest_runtime_root=current).start()
            try:
                refs = _sdk.InProcessRefResolver()
                plan = _sdk.ExecutionPlan(prompt_id="synthetic-gguf-wire", node_id="1", node_type=node_name, node_module=node.__module__, tier="raw" if "raw" in permissions else "secure", input_mode="values", permissions=permissions, inputs={}, method="execute")
                runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
                output = await session.execute(plan, runtime, capabilities=permissions)
                result = json.loads(output.result[0])
                if node_name == "StateDictWireControl":
                    artifact = output_dir / result["artifact"]
                    assert artifact.is_file() and artifact.suffix == ".safetensors"
                    state = load_file(str(artifact))
                    assert torch.equal(state["vector"], torch.arange(6, dtype=torch.float32).reshape(2, 3))
                    assert torch.equal(state["scalar"], torch.tensor(7, dtype=torch.int64))
                    with safe_open(str(artifact), framework="pt") as reader:
                        assert reader.metadata() == {"probe": "synthetic-only"}
                    assert result["ref_kind"] == "VALUE"
                else:
                    assert result == {"size": 16, "bytes": list(b"34567"), "return_type": "bytes"}
                for permission in permissions:
                    with pytest.raises(WireError):
                        await session.execute(plan, runtime, capabilities=tuple(p for p in permissions if p != permission))
                pids.append(session.last_guest_pid)
                results.append(result)
            finally:
                await session.kill()
        assert len(set(pids)) == 2 and all(pid not in (None, os.getpid()) for pid in pids)
        if node_name == "StateDictWireControl":
            assert results[0]["artifact"] != results[1]["artifact"]
        print("GGUF_REAL_WIRE_OBSERVED " + json.dumps({"node": node_name, "results": results, "fresh_pids": pids, "synthetic_only": True, "denied_each_permission": list(permissions)}))
    asyncio.run(run())
