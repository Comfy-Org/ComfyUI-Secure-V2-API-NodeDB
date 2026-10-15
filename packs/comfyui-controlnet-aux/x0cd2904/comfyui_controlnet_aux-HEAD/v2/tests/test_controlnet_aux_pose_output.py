"""Pinned pose JSON bytes/counters and actual managed output boundaries."""
import ast
import asyncio
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import pytest

CORE = Path('/Users/ben/comfy/ComfyUI-secure-nodes')
OVERLAY = Path('/Users/ben/comfy/ComfyUI_secure_nodes')
sys.path[:0] = [str(CORE), str(OVERLAY / 'backend')]
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb
from comfy_secure_nodes.transport.host import GuestSession
import execution
import folder_paths

V2 = Path(__file__).resolve().parents[1]
PRISTINE = V2.parent
NODE = 'SavePoseKpsAsJsonFile'


def load(name, root):
    spec = importlib.util.spec_from_file_location(name, root / '__init__.py', submodule_search_locations=[str(root)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return sys.modules[name + '.nodes']


converted = load('_many_pose_output_test', V2)
output = converted._pose_output
source = ast.parse((PRISTINE / 'node_wrappers/pose_keypoint_postprocess.py').read_text())
namespace = dict(json=json, os=os, folder_paths=folder_paths)
exec(compile(ast.Module(body=[node for node in source.body if isinstance(node, ast.ClassDef) and node.name == NODE], type_ignores=[]), 'pinned_pose_output', 'exec'), namespace)
original = namespace[NODE]


def pose():
    return [{'canvas_width': 96, 'canvas_height': 64, 'people': [
        {'pose_keypoints_2d': [0.125, 2.75, 1.0], 'label': '人 λ', 'missing': None}],
        'animals': [], 'version': 'ap10k'}]


async def direct(values):
    refs = _sdk.InProcessRefResolver()
    plan = _sdk.ExecutionPlan(prompt_id='pose-output', node_id='1', node_type=NODE)
    with _sdk.bind_runtime(refs, _sdk.InProcessCtxProvider().build(plan), _sdk.InProcessOps()):
        return await converted.NODE_CLASS_MAPPINGS[NODE].execute(**values)


@pytest.mark.parametrize('prefix', ['PoseKeypoint', 'poses/人-%width%x%height%', '', 'a/./b'])
def test_source_file_bytes_names_and_no_mutation(prefix, tmp_path, monkeypatch):
    oracle = tmp_path / 'oracle'
    actual = tmp_path / 'actual'
    oracle.mkdir(); actual.mkdir()
    monkeypatch.setattr(folder_paths, 'get_output_directory', lambda: str(oracle))
    values = dict(pose_kps=pose(), filename_prefix=prefix)
    untouched = copy.deepcopy(values)
    assert original().save_pose_kps(**values) == {}
    expected = {str(p.relative_to(oracle)): p.read_bytes() for p in oracle.rglob('*.json')}
    monkeypatch.setattr(folder_paths, 'get_output_directory', lambda: str(actual))
    assert asyncio.run(direct(values)).result is None
    assert {str(p.relative_to(actual)): p.read_bytes() for p in actual.rglob('*.json')} == expected
    assert values == untouched


@pytest.mark.parametrize('names', [[], ['P_00003.json'], ['P_00002_.png', 'P_00008.txt', 'other_00999.json'], ['P_bad.json', 'P_.png'], ['P_-0002.json']])
def test_counter_matches_canonical_file_enumeration(names, tmp_path):
    for name in names:
        (tmp_path / name).write_text('sentinel')
    expected = folder_paths.get_save_image_path('P', str(tmp_path))[2]
    assert output.counter(names, 'P') == expected


def test_time_and_unknown_template_variables_match_canonical(tmp_path, monkeypatch):
    import time
    now = time.struct_time((2026, 3, 8, 7, 6, 5, 6, 67, 0))
    monkeypatch.setattr(time, 'localtime', lambda: now)
    prefix = '%year%/%month%-%day%-%hour%-%minute%-%second%-%width%-%height%-%unknown%'
    _, folder, filename = output.prepare(pose(), prefix)
    expected = folder_paths.get_save_image_path(prefix, str(tmp_path), 96, 64)
    assert (folder, filename) == (expected[3], expected[1])


@pytest.mark.parametrize('payload', [[], [{}], [{'canvas_width': 96}], [{'canvas_width': 96, 'canvas_height': 64, 'bad': object()}]])
def test_native_invalid_data_classes_before_side_effects(payload, tmp_path, monkeypatch):
    monkeypatch.setattr(folder_paths, 'get_output_directory', lambda: str(tmp_path))
    try:
        original().save_pose_kps(payload, 'old')
    except Exception as error:
        expected = type(error)
    else:
        pytest.fail('pinned invalid control unexpectedly succeeded')
    with pytest.raises(expected):
        output.prepare(payload, 'new')
    assert not list(tmp_path.glob('new*'))


@pytest.mark.parametrize('prefix', ['/absolute', '../escape', 'a/../escape', 'C:/escape', 'a\\b', 'bad\0name', 'x' * 256])
def test_confined_prefix_refuses_before_catalogue_or_output(prefix):
    with pytest.raises(ValueError):
        output.prepare(pose(), prefix)


def test_json_structure_and_encoded_byte_limits(monkeypatch):
    cycle = []; cycle.append(cycle)
    with pytest.raises(ValueError, match='circular'):
        output._json_text(cycle)
    with pytest.raises(ValueError, match='finite'):
        output._json_text([float('nan')])
    monkeypatch.setattr(output, 'MAX_JSON_BYTES', 100)
    with pytest.raises(ValueError, match='encoded'):
        output._json_text(['人' * 20])
    monkeypatch.setattr(output, 'MAX_ENTRIES', 3)
    with pytest.raises(ValueError, match='structure'):
        output._json_text([1, 2, 3])


def test_new_only_collision_retry_keeps_source_naming_without_overwrite():
    writes = []
    class Outputs:
        async def write_text(self, text, filename, **options):
            writes.append((text, filename, options))
            if len(writes) == 1:
                raise FileExistsError(filename)
    class Assets:
        async def list(self, *args, **kwargs): return ['poses/P_00002.json']
    runtime = _sdk.Runtime(refs=_sdk.InProcessRefResolver(), ctx=SimpleNamespace(assets=Assets(), output=Outputs()), ops=_sdk.InProcessOps())
    async def run():
        with _sdk.bind_runtime(runtime.refs, runtime.ctx, runtime.ops):
            await output.execute(pose(), 'poses/P')
    asyncio.run(run())
    assert [row[1] for row in writes] == ['poses/P_00003.json', 'poses/P_00004.json']
    assert writes[1][0].encode() == json.dumps(pose()).encode()
    assert all(row[2] == {'folder': 'output', 'mode': 'new_only'} for row in writes)


def test_collision_and_catalogue_failures_are_bounded(monkeypatch):
    writes = []
    class Outputs:
        async def write_text(self, *args, **kwargs):
            writes.append(kwargs)
            raise FileExistsError('collision')
    class Assets:
        names = []
        async def list(self, *args, **kwargs): return self.names
    assets = Assets()
    runtime = _sdk.Runtime(refs=_sdk.InProcessRefResolver(), ctx=SimpleNamespace(assets=assets, output=Outputs()), ops=_sdk.InProcessOps())
    async def run():
        with _sdk.bind_runtime(runtime.refs, runtime.ctx, runtime.ops):
            with pytest.raises(RuntimeError, match='retry'):
                await output.execute(pose(), 'P')
            assert len(writes) == 32
            assets.names = ['wrong/P_00001.json']
            with pytest.raises(ValueError, match='immediate'):
                await output.execute(pose(), 'P')
            assert len(writes) == 32
            monkeypatch.setattr(output, 'MAX_NAMES', 1)
            assets.names = ['a.json', 'b.json']
            with pytest.raises(ValueError, match='catalogue'):
                await output.execute(pose(), 'P')
            assert len(writes) == 32
    asyncio.run(run())


def test_actual_two_fresh_output_guests_denials_and_outer_empty_contract(tmp_path, monkeypatch):
    monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE', 'required')
    destination = tmp_path / 'output'; destination.mkdir()
    (destination / 'Guest_00004.json').write_text('unchanged')
    monkeypatch.setattr(folder_paths, 'get_output_directory', lambda: str(destination))
    fresh = tmp_path / 'fresh'; shutil.copytree(V2, fresh)
    expected = json.dumps(pose()).encode()
    async def run():
        pids = []
        for index, root in enumerate((V2, fresh)):
            package = load('_many_pose_output_guest' + str(index), root)
            cls = package.NODE_CLASS_MAPPINGS[NODE]
            session = await GuestSession('many-pose-output', guest_runtime_root=root).start()
            try:
                assert session.sandbox_kind == 'seatbelt'
                refs = _sdk.InProcessRefResolver()
                values = dict(pose_kps=pose(), filename_prefix='Guest')
                plan = _sdk.ExecutionPlan(prompt_id='pose-output', node_id='1', node_type=cls.__name__, node_module=cls.__module__, inputs=await _sdk.wrap_inputs(refs, values), input_mode='values')
                runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
                result = await session.execute(plan, runtime, capabilities=('assets', 'output'))
                assert (await _sdk.unwrap_outputs(refs, result)).result is None
                assert (destination / f'Guest_{5 + index:05}.json').read_bytes() == expected
                for capabilities in ((), ('assets',), ('output',)):
                    with pytest.raises(Exception, match='not granted'):
                        await session.execute(plan, runtime, capabilities=capabilities)
                plan.inputs = await _sdk.wrap_inputs(refs, dict(values, filename_prefix='../escape'))
                with pytest.raises(Exception, match='managed output'):
                    await session.execute(plan, runtime, capabilities=('assets', 'output'))
                pids.append(session.last_guest_pid)
            finally:
                await session.kill()
        assert len(set(pids)) == 2 and os.getpid() not in pids
        loaded = packdb.load_pack(PRISTINE.parent, mount_name='custom_nodes.many_pose_output_outer')
        class Backend:
            session = None
            async def dispatch(self, plan, local_call, runtime):
                if self.session is None:
                    self.session = await GuestSession('many-pose-output-outer', guest_runtime_root=V2).start()
                    assert self.session.sandbox_kind == 'seatbelt'
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs, plan.input_types)
                return await self.session.execute(plan, runtime, capabilities=plan.permissions)
        backend = Backend(); previous = _sdk.providers.execution_backend
        _sdk.providers.execution_backend = backend
        try:
            cls = loaded.node_mappings[NODE]
            assert set(cls.SDK_PERMISSIONS) == {'assets', 'output'}
            result = await execution._async_map_node_over_list('pose-output-outer', '1', cls, {'pose_kps': [pose()], 'filename_prefix': ['Guest']}, cls.FUNCTION)
            assert len(result) == 1 and result[0].result is None
            assert (destination / 'Guest_00007.json').read_bytes() == expected
        finally:
            _sdk.providers.execution_backend = previous
            if backend.session: await backend.session.kill()
    asyncio.run(run())
    assert (destination / 'Guest_00004.json').read_text() == 'unchanged'
    assert sorted(path.name for path in destination.iterdir()) == ['Guest_00004.json', 'Guest_00005.json', 'Guest_00006.json', 'Guest_00007.json']
