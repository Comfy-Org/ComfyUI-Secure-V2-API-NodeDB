from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import shutil
import sys

import numpy as np
import cv2
import pytest
import torch

sys.dont_write_bytecode = True
V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = SNAPSHOT.parents[2]
CORE = Path(os.environ.get('COMFY_CORE_ROOT', '/Users/ben/comfy/ComfyUI-secure-nodes'))
BACKEND = Path('/Users/ben/comfy/ComfyUI_secure_nodes/backend')
for root in (BACKEND, CORE):
    sys.path.insert(0, str(root))
os.environ.setdefault('COMFY_CORE_ROOT', str(CORE))
from comfy.cli_args import args
args.cpu = True
import execution
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb, packpatch
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes.transport.host import GuestSession

COMMIT = 'c7b02434e908d6133c0acb94e031640689165abf'
DTS_SHA = '4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3'
PYI_SHA = '50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78'
PAIR = PACK_DB / 'patches/comfyui-colorimagedetection/xc7b0243/comfyui-colorimagedetection-xc7b0243'
PRISTINE_SHA = {
    '.github/workflows/publish_action.yml': 'a7b5cf97862bd1a84c0a7ac95a1817d3e53bbdab5fd976d519fd98fd47629831',
    '.gitignore': '56122d8c7c68f7804aab7d175352049cd31cd387c40bdc853d49c2aa68fe3035',
    'LICENSE': 'fbd1632ad8cc93d3c795f3d3d929d52ed83a244e4b346defffa5f09db6d4c091',
    'README.md': 'c9cbb945a083ef99156facb3f32ac371f6a16cde6f782563e9609f9a7cddfdc1',
    '__init__.py': 'b18de9dc0005d53c6f3d873b501fc60dee4a6810b74a3722dd0f9420633a04e8',
    'nodes.py': 'b608f6068b853ee5197efe3609bd0274b2a81aa10bd90bfc0009150fc722c668',
    'pyproject.toml': '1192db89301ffdeabf3af85362f7e23044d0ce9a8ccd0d3ba5d355ebf277c9a4',
    'requirements.txt': '254c887b4724fd2f4f99620d750bbddc08fa78f0cc2fc6b5fb04fde9afea2b95',
}
IDS = ('RGBColorDetection', 'LABColorDetection')


def _load(name, root):
    spec = importlib.util.spec_from_file_location(name, root / '__init__.py', submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _secure():
    return _load('_ned_color_image_detection_secure', V2)


def _old():
    return _load('_ned_color_image_detection_pristine', PACK)


def _manifest(module):
    return {'format': FORMAT, 'nodes': {node_id: {
        'class': cls.__name__, 'module': 'nodes', 'sdk_refs': False, 'permissions': ['raw'],
        'methods': {key: False for key in ('validate_inputs', 'fingerprint_inputs', 'check_lazy_status')},
        'schema': encode_schema(copy.deepcopy(cls.GET_SCHEMA())),
    } for node_id, cls in module.NODE_CLASS_MAPPINGS.items()}, 'runtime': manifest_declaration(V2)}


def _images():
    rng = torch.Generator().manual_seed(90013)
    gray = torch.linspace(0, 1, 80).reshape(1, 8, 10, 1).expand(-1, -1, -1, 3).clone()
    red = torch.zeros_like(gray); red[..., 0] = 1
    blue = torch.zeros_like(gray); blue[..., 2] = .75
    return [gray, red, blue, torch.cat((red, gray)), torch.cat((gray, red)),
            torch.cat((blue, red, gray)), torch.rand((3, 11, 13, 3), generator=rng),
            torch.rand((1, 1, 1, 3), generator=rng), gray[:, ::2, ::2],
            red.to(torch.float16), blue.to(torch.float64),
            torch.cat((red, torch.full_like(red[..., :1], .2)), dim=-1),
            torch.cat((gray, torch.full_like(gray[..., :1], .9)), dim=-1)]


def _inputs(node_id, image, threshold=None, percent=.1):
    data = {'image': image, 'threshold': threshold if threshold is not None else (.15 if node_id == IDS[0] else 2.5)}
    if node_id == IDS[0]:
        data['det_pixel_percent'] = percent
    return data


def _assert_scalars(actual, expected):
    assert len(actual) == 2 and type(actual[0]) is bool and type(actual[1]) is float
    assert actual[0] is bool(expected[0]) and actual[1] == float(expected[1])


def test_actual_census_exact_schema_legacy_mapping_and_manifest():
    old, new = _old(), _secure()
    assert tuple(old.NODE_CLASS_MAPPINGS) == tuple(new.NODE_CLASS_MAPPINGS) == IDS
    assert old.NODE_DISPLAY_NAME_MAPPINGS == new.NODE_DISPLAY_NAME_MAPPINGS == {
        'ColorDetection': 'RGB Color Detection', 'LABColorDetection': 'LAB Color Detection'}
    for node_id, cls in new.NODE_CLASS_MAPPINGS.items():
        legacy = old.NODE_CLASS_MAPPINGS[node_id]
        schema = cls.GET_SCHEMA(); schema.validate()
        assert schema.node_id == node_id and schema.category == legacy.CATEGORY
        assert schema.display_name == old.NODE_DISPLAY_NAME_MAPPINGS.get(node_id)
        assert not schema.is_output_node and not schema.is_input_list
        assert [(item.io_type, item.display_name) for item in schema.outputs] == list(zip(legacy.RETURN_TYPES, legacy.RETURN_NAMES))
        inputs = legacy.INPUT_TYPES()['required']
        assert [item.id for item in schema.inputs] == list(inputs)
        for item in schema.inputs:
            assert item.io_type == inputs[item.id][0] and not item.optional
            for key, value in (inputs[item.id][1] if len(inputs[item.id]) > 1 else {}).items():
                assert item.as_dict()[key] == value
        assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS == ('raw',)
    loaded = packdb.load_pack(SNAPSHOT, mount_name='custom_nodes.ned_color_detection_census')
    assert tuple(loaded.node_mappings) == IDS
    assert not loaded.routes and not loaded.frontend_permissions and loaded.web_directory is None
    assert not hasattr(old, 'WEB_DIRECTORY') and not list(PACK.rglob('*.js'))
    for node_id, cls in loaded.node_mappings.items():
        expected = copy.deepcopy(old.NODE_CLASS_MAPPINGS[node_id].INPUT_TYPES())
        expected['required'] = {key: value if len(value) == 2 else (value[0], {})
                                for key, value in expected['required'].items()}
        assert cls.INPUT_TYPES() == expected
        assert cls.RETURN_TYPES == list(old.NODE_CLASS_MAPPINGS[node_id].RETURN_TYPES)


@pytest.mark.parametrize('node_id', IDS)
@pytest.mark.parametrize('image_index', range(13))
def test_image_dtype_shape_stride_batch_order_and_exact_score_differential(node_id, image_index):
    image = _images()[image_index]
    before = image.clone()
    old = _old().NODE_CLASS_MAPPINGS[node_id]()
    new = _secure().NODE_CLASS_MAPPINGS[node_id]
    for threshold in (-1., 0., .15, 2.5, 100.):
        inputs = _inputs(node_id, image, threshold)
        _assert_scalars(new.execute(**inputs).result, old.process(**inputs))
    assert torch.equal(before, image)


@pytest.mark.parametrize('percent', [0., .001, .1, 1., 33.3, 100., 150., -.01, -1.])
def test_rgb_percentage_zero_selected_slice_and_extended_finite_semantics(percent):
    image = _images()[6]
    inputs = _inputs(IDS[0], image, percent=percent)
    _assert_scalars(_secure().NODE_CLASS_MAPPINGS[IDS[0]].execute(**inputs).result,
                    _old().NODE_CLASS_MAPPINGS[IDS[0]]().process(**inputs))


def test_last_batch_not_first_or_average_and_zero_selection_quirks():
    old, new = _old(), _secure()
    for node_id in IDS:
        gray_last, red_last = _images()[3:5]
        a = new.NODE_CLASS_MAPPINGS[node_id].execute(**_inputs(node_id, gray_last)).result
        b = new.NODE_CLASS_MAPPINGS[node_id].execute(**_inputs(node_id, red_last)).result
        assert a[1] != b[1]
        _assert_scalars(a, old.NODE_CLASS_MAPPINGS[node_id]().process(**_inputs(node_id, gray_last[-1:])))
    tiny = _images()[7]
    new_rgb = new.NODE_CLASS_MAPPINGS[IDS[0]]
    full = new_rgb.execute(**_inputs(IDS[0], tiny, percent=100)).result
    for percent in (0., .1, .001):
        assert new_rgb.execute(**_inputs(IDS[0], tiny, percent=percent)).result == full


def test_exact_threshold_equality_is_false_and_native_bfloat16_failure_is_preserved():
    old, new = _old(), _secure()
    for node_id in IDS:
        image = _images()[1]
        score = old.NODE_CLASS_MAPPINGS[node_id]().process(**_inputs(node_id, image))[1]
        exact = _inputs(node_id, image, threshold=float(score))
        result = new.NODE_CLASS_MAPPINGS[node_id].execute(**exact).result
        _assert_scalars(result, old.NODE_CLASS_MAPPINGS[node_id]().process(**exact))
        assert result[0] is False
        bfloat = _inputs(node_id, image.to(torch.bfloat16))
        with pytest.raises(TypeError) as expected:
            old.NODE_CLASS_MAPPINGS[node_id]().process(**bfloat)
        with pytest.raises(TypeError) as actual:
            new.NODE_CLASS_MAPPINGS[node_id].execute(**bfloat)
        assert str(actual.value) == str(expected.value)


def test_single_channel_rgb_support_and_native_lab_rejection_are_preserved():
    old, new = _old(), _secure()
    image = _images()[0][..., :1]
    inputs = _inputs(IDS[0], image)
    _assert_scalars(new.NODE_CLASS_MAPPINGS[IDS[0]].execute(**inputs).result,
                    old.NODE_CLASS_MAPPINGS[IDS[0]]().process(**inputs))
    inputs = _inputs(IDS[1], image)
    with pytest.raises(cv2.error) as expected:
        old.NODE_CLASS_MAPPINGS[IDS[1]]().process(**inputs)
    with pytest.raises(cv2.error) as actual:
        new.NODE_CLASS_MAPPINGS[IDS[1]].execute(**inputs)
    assert str(actual.value) == str(expected.value)


@pytest.mark.parametrize('image', [None, [], torch.zeros(1, 2, 2), torch.zeros(1, 2, 2, 2),
    torch.zeros(0, 2, 2, 3), torch.zeros(1, 0, 2, 3), torch.zeros(33, 1, 1, 3),
    torch.empty(1, 8193, 1, 3, device='meta'), torch.empty(1, 2049, 2049, 3, device='meta'),
    torch.zeros(1, 2, 2, 3, dtype=torch.int32), torch.full((1, 1, 1, 3), float('nan')),
    torch.full((1, 1, 1, 3), float('inf'))])
def test_malformed_image_and_resource_limits_fail_closed(image):
    for cls in _secure().NODE_CLASS_MAPPINGS.values():
        with pytest.raises(ValueError):
            cls.execute(**_inputs(cls.GET_SCHEMA().node_id, image))


@pytest.mark.parametrize('value', [None, True, '1', [], float('nan'), float('inf'), 1_000_001.])
def test_malformed_scalar_parameters_fail_closed(value):
    new = _secure()
    for node_id in IDS:
        with pytest.raises((TypeError, ValueError)):
            new.NODE_CLASS_MAPPINGS[node_id].execute(**_inputs(node_id, _images()[0], threshold=value) | {'threshold': value})
    with pytest.raises((TypeError, ValueError)):
        new.NODE_CLASS_MAPPINGS[IDS[0]].execute(**_inputs(IDS[0], _images()[0], percent=value))


def test_nonfinite_analysis_is_rejected_instead_of_serializing_nan():
    with pytest.warns(RuntimeWarning), pytest.raises(ValueError, match='nonfinite score'):
        _secure().NODE_CLASS_MAPPINGS[IDS[0]].execute(**_inputs(IDS[0], _images()[0], percent=-100.))


def test_repeat_execution_rng_isolation_and_no_durable_state():
    py_state = random.getstate(); np_state = np.random.get_state(); torch_state = torch.random.get_rng_state()
    for node_id in IDS:
        node = _secure().NODE_CLASS_MAPPINGS[node_id]
        inputs = _inputs(node_id, _images()[6])
        first = node.execute(**inputs).result
        for _ in range(10):
            assert node.execute(**inputs).result == first
    assert random.getstate() == py_state and torch.equal(torch.random.get_rng_state(), torch_state)
    after = np.random.get_state()
    assert after[0] == np_state[0] and np.array_equal(after[1], np_state[1]) and after[2:] == np_state[2:]


def test_real_guest_raw_denial_and_exact_scalars_for_both_nodes():
    old, new = _old(), _secure()
    async def run():
        session = await GuestSession('ned-color-detection', guest_runtime_root=V2).start()
        refs = _sdk.InProcessRefResolver()
        try:
            for node_id in IDS:
                node = new.NODE_CLASS_MAPPINGS[node_id]
                for image in _images() + ([_images()[0][..., :1]] if node_id == IDS[0] else []):
                    inputs = _inputs(node_id, image)
                    plan = _sdk.ExecutionPlan(prompt_id='color', node_id=node_id, node_type=node.__name__,
                        tier='sandbox', node_module=node.__module__, input_mode='values', permissions=('raw',),
                        inputs=await _sdk.wrap_inputs(refs, inputs), method='execute')
                    runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
                    result = await session.execute(plan, runtime, capabilities=('raw',))
                    _assert_scalars(tuple(result.result), old.NODE_CLASS_MAPPINGS[node_id]().process(**inputs))
                    with pytest.raises(Exception, match='raw'):
                        await session.execute(plan, runtime, capabilities=())
                    await refs.release(plan.inputs['image'])
            assert session.last_guest_pid not in (None, os.getpid()) and session.sandbox_kind != 'none'
            assert not refs._table
        finally:
            await session.kill()
    asyncio.run(run())


def test_real_outer_executor_preserves_custom_bool_and_float_scalars():
    loaded = packdb.load_pack(SNAPSHOT, mount_name='custom_nodes.ned_color_detection_outer')
    old = _old()
    async def run():
        previous = _sdk.providers.execution_backend
        class OuterGuestBackend:
            session = None
            async def dispatch(self, plan, local_call, runtime):
                if self.session is None:
                    self.session = await GuestSession('ned-color-outer', guest_runtime_root=V2).start()
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
                return await self.session.execute(plan, runtime, capabilities=('raw',))
        backend = OuterGuestBackend(); _sdk.providers.register_execution_backend(backend)
        try:
            for node_id, node in loaded.node_mappings.items():
                assert node.RETURN_TYPES == ['BOOL', 'FLOAT']
                for image in _images()[:8] + _images()[11:] + ([_images()[0][..., :1]] if node_id == IDS[0] else []):
                    inputs = _inputs(node_id, image)
                    results = await execution._async_map_node_over_list(prompt_id='ned-color-outer', unique_id=node_id,
                        obj=node, input_data_all={key: [value] for key, value in inputs.items()}, func=node.FUNCTION, v3_data=None)
                    assert len(results) == 1
                    _assert_scalars(results[0].result, old.NODE_CLASS_MAPPINGS[node_id]().process(**inputs))
            assert backend.session.last_guest_pid not in (None, os.getpid())
        finally:
            _sdk.providers.register_execution_backend(previous)
            if backend.session is not None:
                await backend.session.kill()
    asyncio.run(run())


def test_fresh_filesystem_and_guests_across_tenants_are_stateless(tmp_path):
    expected = _old().NODE_CLASS_MAPPINGS[IDS[0]]().process(**_inputs(IDS[0], _images()[6]))
    async def run():
        pids = []
        for index, tenant in enumerate(('user-a', 'user-b', 'user-a')):
            fresh = tmp_path / str(index); shutil.copytree(V2, fresh)
            node = _load(f'_ned_color_fresh_{index}', fresh).NODE_CLASS_MAPPINGS[IDS[0]]
            session = await GuestSession(f'ned-color-fresh-{index}', guest_runtime_root=fresh).start()
            refs = _sdk.InProcessRefResolver()
            try:
                plan = _sdk.ExecutionPlan(prompt_id='fresh', node_id='1', node_type=node.__name__, tier='sandbox',
                    node_module=node.__module__, inputs=await _sdk.wrap_inputs(refs, _inputs(IDS[0], _images()[6])),
                    input_mode='values', permissions=('raw',), method='execute')
                runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
                _assert_scalars(tuple((await session.execute(plan, runtime, capabilities=('raw',), tenant=tenant)).result), expected)
                pids.append(session.last_guest_pid)
            finally:
                await refs.release(plan.inputs['image']); await session.kill()
        assert len(set(pids)) == 3
    asyncio.run(run())


def test_current_stubs_manifest_pristine_identity_and_no_ambient_authority():
    assert json.loads((V2 / 'secure-nodes.json').read_text()) == _manifest(_secure())
    assert hashlib.sha256((V2 / 'comfy-api.d.ts').read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / 'comfy-api.pyi').read_bytes()).hexdigest() == PYI_SHA
    paths = {path.relative_to(PACK).as_posix() for path in PACK.rglob('*') if path.is_file() and not path.is_relative_to(V2)}
    assert paths == set(PRISTINE_SHA)
    for path, sha in PRISTINE_SHA.items():
        assert hashlib.sha256((PACK / path).read_bytes()).hexdigest() == sha
    source = (V2 / 'nodes.py').read_text()
    for forbidden in ('import comfy.', 'folder_paths', 'PromptServer', 'requests', 'open(', '_from_raw',
                      'subprocess', 'pip install', 'eval(', 'exec(', 'global '):
        assert forbidden not in source
    assert COMMIT in (V2 / 'SECURE_CONVERSION.md').read_text()


def test_byte_exact_pristine_to_v2_patch_roundtrip_and_cache_hygiene(tmp_path):
    manifest, diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix('.json').read_text()) == manifest
    assert PAIR.with_suffix('.diff').read_text() == diff
    fresh = tmp_path / 'comfyui-colorimagedetection/xc7b0243'; fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns('v2'))
    packpatch.apply(fresh, manifest, diff)
    packpatch.validate_tree(fresh / PACK.name / 'v2', V2)
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))
