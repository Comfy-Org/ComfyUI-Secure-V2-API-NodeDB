"""Actual service/public guest-surface negatives, not inferred backing absence."""
import asyncio
import importlib.util
import json
from pathlib import Path
import shutil
import sys

V2 = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True


def load(name, path, package=False):
    spec = importlib.util.spec_from_file_location(name, path, submodule_search_locations=[str(path.parent)] if package else None)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_actual_existing_model_broker_and_public_argument_boundaries(tmp_path, monkeypatch):
    from comfy.cli_args import args
    monkeypatch.setattr(args, 'cpu', True)
    from comfy_api.latest import _sdk
    from comfy_secure_nodes.transport.host import GuestSession
    import nodes
    # Explicit no-City96 fixture. Missing dependency is not a model test or
    # proof that calcuis loading works. No calcuis ID is aliased to City96.
    monkeypatch.delitem(nodes.NODE_CLASS_MAPPINGS, 'UnetLoaderGGUF', raising=False)
    current = tmp_path / 'synthetic-gguf-boundary'
    shutil.copytree(V2, current)
    shutil.copyfile(V2 / 'tests/wire_control.py', current / 'wire_control.py')
    load('moe_gguf_model_boundary', current / '__init__.py', True)
    control = load('moe_gguf_model_boundary.wire_control', current / 'wire_control.py').ExistingModelBoundaryControl

    async def run():
        session = await GuestSession('moe-gguf-model-boundary', guest_runtime_root=current).start()
        try:
            refs = _sdk.InProcessRefResolver()
            plan = _sdk.ExecutionPlan(prompt_id='synthetic-model-boundary', node_id='1', node_type=control.__name__, node_module=control.__module__, tier='secure', input_mode='values', permissions=('models',), inputs={}, method='execute')
            runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
            output = await session.execute(plan, runtime, capabilities=('models',))
            observed = json.loads(output.result[0])
            assert 'city96/ComfyUI-GGUF' in observed['gguf_service']['message']
            assert observed['gguf_device_argument']['exception'] == 'TypeError' and 'device' in observed['gguf_device_argument']['message']
            assert observed['audio_public_member']['exception'] == 'AttributeError' and 'load_audio_encoder' in observed['audio_public_member']['message']
            assert observed['binary_public_member']['exception'] == 'AttributeError' and 'save_binary' in observed['binary_public_member']['message']
            print('GGUF_BOUNDARY_OBSERVED ' + json.dumps({'observations': observed, 'city96_explicitly_absent_fixture': True, 'no_weight_parse_or_inference': True, 'missing_member_not_absent_host_service_claim': True}))
        finally:
            await session.kill()
    asyncio.run(run())
