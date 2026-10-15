"""Actual immutable bundled-data parity, not MultiTalk model inference."""
import ast
import asyncio
import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import sys
import pytest
import torch
from safetensors.torch import load_file

sys.dont_write_bytecode = True
V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent
CORE = Path('/Users/ben/comfy/ComfyUI-secure-nodes')
BACKEND = Path('/Users/ben/comfy/ComfyUI_secure_nodes/backend')
sys.path[:0] = [str(CORE), str(BACKEND)]
os.environ.setdefault('COMFY_CORE_ROOT', str(CORE))
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession

ID = 'MultiTalkSilentEmbeds'
RESOURCE = Path('multitalk/encoded_silence.safetensors')


def candidate(root=V2):
    name = '_wan_silence_' + str(id(root))
    # Relative helper import requires the safe package, not the legacy loader.
    pkg = importlib.util.spec_from_file_location(name, root/'__init__.py', submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(pkg); sys.modules[name] = module; pkg.loader.exec_module(module)
    spec = importlib.util.spec_from_file_location(name+'.secure_silence_nodes', root/'secure_silence_nodes.py')
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
    return module.MultiTalkSilentEmbeds


def original():
    tree = ast.parse((PACK/'multitalk/nodes.py').read_text())
    cls = next(item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == ID)
    ns = {'os': os, 'script_directory': str(PACK/'multitalk'), 'load_torch_file': load_file}
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(PACK/'multitalk/nodes.py'), 'exec'), ns)
    return ns[ID]


def equal(expected, actual):
    assert set(actual) == set(expected) == {'audio_features', 'audio_scale', 'audio_cfg_scale', 'ref_target_masks'}
    assert torch.equal(actual['audio_features'], expected['audio_features'])
    assert actual['audio_features'].shape == expected['audio_features'].shape
    assert actual['audio_features'].dtype == expected['audio_features'].dtype == torch.float16
    assert actual['audio_features'].device == expected['audio_features'].device == torch.device('cpu')
    for key in ('audio_scale', 'audio_cfg_scale', 'ref_target_masks'):
        assert actual[key] == expected[key]


def test_silence_pristine_resource_and_exact_schema():
    path = PACK/RESOURCE
    assert path.stat().st_size == 1658968
    assert hashlib.sha256(path.read_bytes()).hexdigest() == 'cd68739d78b9566cf3d575e4140f7e02f0d36e4ae9bcb33457d92711c3c6584d'
    assert (V2/RESOURCE).read_bytes() == path.read_bytes()
    schema = candidate().GET_SCHEMA(); old = original()
    assert schema.node_id == ID and schema.category == old.CATEGORY
    assert schema.inputs[0].io_type == 'INT' and schema.inputs[0].id == 'num_frames'
    for key, value in old.INPUT_TYPES()['required']['num_frames'][1].items():
        assert getattr(schema.inputs[0], key) == value
    assert len(schema.outputs) == 1
    assert schema.outputs[0].io_type == old.RETURN_TYPES[0]
    assert schema.outputs[0].display_name == old.RETURN_NAMES[0]
    assert candidate().SDK_PERMISSIONS == ('raw',) and candidate().SDK_REFS is False


def test_silence_exact_repeated_asset_slice_and_independent_outputs_rng():
    cls = candidate(); old = original()()
    before = torch.random.get_rng_state().clone()
    for frames in (-89, -1, 0, 1, 2, 81, 89, 90, 91, 179, 180, 181, 1000):
        equal(old.process(frames)[0], cls.execute(frames).result[0])
    first = cls.execute(81).result[0]
    first['audio_features'].zero_()
    equal(old.process(81)[0], cls.execute(81).result[0])
    assert torch.equal(torch.random.get_rng_state(), before)


def test_silence_native_malformed_and_projected_repeat_bounds():
    for frames in (-90, -91, -1000, 1.5, 'x', None):
        results = []
        for fn in (original()().process, candidate().execute):
            try:
                fn(frames)
                results.append(None)
            except Exception as error:
                results.append((type(error).__name__, str(error)))
        assert results[0] is not None and results[0] == results[1]
    for frames in (10000, 10**12):
        with pytest.raises(ValueError, match='projected'):
            candidate().execute(frames)


def test_silence_corrupt_oversized_symlink_resource_fails_before_parser(tmp_path, monkeypatch):
    fresh = tmp_path/'corrupt-render'; shutil.copytree(V2, fresh)
    cls = candidate(fresh); module = sys.modules[cls.__module__]
    monkeypatch.setattr(module, 'load', lambda data: pytest.fail('parser must not see malformed bytes'))
    path = fresh/RESOURCE
    for invalid in (b'invalid', b'x'*1658969):
        path.write_bytes(invalid)  # test-only disposable resource corruption
        with pytest.raises(ValueError, match='size/hash'):
            cls.execute(81)
    path.unlink()
    path.symlink_to(PACK/RESOURCE)
    with pytest.raises(ValueError, match='immutable in-pack'):
        cls.execute(81)


def test_silence_actual_guest_fresh_resource_raw_denial_and_copy_isolation(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(CORE))
    monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE', 'required')
    fresh = tmp_path/'fresh-render'; shutil.copytree(V2, fresh)
    async def run():
        pids = []
        for root in (V2, fresh):
            cls = candidate(root)
            session = await GuestSession('wan-silence', guest_runtime_root=root).start()
            assert session.sandbox_kind == 'seatbelt'
            try:
                for frames in (0, 81, 91, -1):
                    plan = _sdk.ExecutionPlan(prompt_id='wan-silence', node_id='1', node_type=cls.__name__,
                        node_module=cls.__module__, inputs={'num_frames': frames}, input_mode='values',
                        permissions=('raw',), tier='sandbox')
                    refs = _sdk.InProcessRefResolver()
                    runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
                    actual = await session.execute(plan, runtime, capabilities=('raw',), tenant='silence-owner')
                    data = dict(await refs.resolve(actual.result[0]))
                    if isinstance(data['audio_features'], _sdk.Ref):
                        data['audio_features'] = await refs.resolve(data['audio_features'])
                    equal(original()().process(frames)[0], data)
                with pytest.raises(Exception, match='raw'):
                    await session.execute(plan, runtime, capabilities=(), tenant='silence-owner')
                pids.append(session.last_guest_pid)
            finally:
                await session.kill()
        assert len(set(pids)) == 2 and os.getpid() not in pids
    asyncio.run(run())


def test_silence_real_outer_executor_typed_custom_output(monkeypatch):
    monkeypatch.syspath_prepend(str(CORE))
    monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE', 'required')
    import execution
    from comfy_secure_nodes import packdb
    classes = packdb.load_pack(PACK.parent, mount_name='custom_nodes.wan_silence_outer').node_mappings
    async def run():
        previous = _sdk.providers.execution_backend
        class Backend:
            sessions = []
            async def dispatch(self, plan, local_call, runtime):
                session = await GuestSession('wan-silence-outer', guest_runtime_root=V2).start()
                assert session.sandbox_kind == 'seatbelt'
                self.sessions.append(session)
                return await session.execute(plan, runtime, capabilities=('raw',), tenant='silence-owner')
        backend = Backend(); _sdk.providers.register_execution_backend(backend)
        try:
            cls = classes[ID]; cls.GET_SCHEMA()
            finalized, missing, data = execution.get_input_data({'num_frames': 81}, cls, '1', None)
            assert not missing
            results = await execution._async_map_node_over_list(prompt_id='silence-outer', unique_id='1',
                obj=cls, input_data_all=finalized, func='execute', v3_data=data)
            equal(original()().process(81)[0], results[0].result[0])
        finally:
            _sdk.providers.register_execution_backend(previous)
            for session in backend.sessions:
                await session.kill()
    asyncio.run(run())
