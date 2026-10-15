from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import random
import shutil
import sys

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

COMMIT = 'aada583b1f15f572c9737c88e61d528a15021fed'
DTS_SHA = '4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3'
PYI_SHA = '50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78'
PAIR = PACK_DB / 'patches/comfyui-reimgsize/xaada583/comfyui-reimgsize-xaada583'
IDS = ('Reimgsize', 'Cropimg', 'Resizebyratio')
METHODS = ('nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos')
PRISTINE_SHA = {
    'LICENSE': '5271251291f42ba4611715ab05c6f2f70d60a14139859b7efc5d2ebd506a3a9c',
    'pyproject.toml': 'b787d6529cf3ad1d9be419ff1a6c0b59729a9ca0e95a50ecf8b037215117e699',
    '__init__.py': '4c0f96b0f0006df5a559d09d44b8d521a32d7992383223310b5ba2a3f88e3e42',
    'README.md': 'c560a9d71b08b83db38dab95819995291515d3aa25e0d706c4051a4ba15318c6',
    'README_CN.md': 'ed641cfb96b06c788805d5f8e3159a2224be7bd4c4fd6a15e171efbfe74709cc',
    '.gitignore': '0cd064765b740a9d791f15266ee55d644b4b0cf40294754c21d5901ed9c781c3',
    'nodes.py': '17fcce904350838dbc3182ef075eecd455531ea060f68036dceace79afc4e358',
    'example_workflows/comfyui_reimgsize.jpg': '1d85786b5b3816141a279a1f3594e08f693a58abbdf1cca1e8bb753e0216506f',
    'example_workflows/comfyui_reimgsize.json': '0cbb0e7084e8317e3206821edbd72ad12fa34bd94a475850ef79e7f23e78c3f2',
    '.github/workflows/publish.yml': '4ac9bbcd2dc1164e4fe89df487f07b18918f20d7fbe23eda0045e4e52c8884cc',
}


def _load(name, root):
    spec = importlib.util.spec_from_file_location(name, root / '__init__.py', submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _new():
    return _load('_ned_reimgsize_secure', V2)


def _old():
    return _load('_ned_reimgsize_pristine', PACK)


def _manifest(module):
    return {'format': FORMAT, 'nodes': {node_id: {
        'class': cls.__name__, 'module': 'nodes', 'sdk_refs': True, 'permissions': list(cls.SDK_PERMISSIONS),
        'methods': {key: False for key in ('validate_inputs', 'fingerprint_inputs', 'check_lazy_status')},
        'schema': encode_schema(copy.deepcopy(cls.GET_SCHEMA())),
    } for node_id, cls in module.NODE_CLASS_MAPPINGS.items()}, 'runtime': manifest_declaration(V2)}


def _inputs(node_id, image=None, method='bicubic', crop='disabled', **overrides):
    if node_id == 'Reimgsize':
        values = dict(image=image, img_size=24, upscale_method=method, crop_methods=crop, GCD=2)
    elif node_id == 'Cropimg':
        values = dict(image=image, upscale_method=method, crop_methods=crop, width_ratio=3., height_ratio=2.)
    else:
        values = dict(size=1024, width_ratio=3., height_ratio=2., GCD=64)
    return values | overrides


def _legacy(node_id, inputs):
    node = _old().NODE_CLASS_MAPPINGS[node_id]()
    return getattr(node, node.FUNCTION)(**inputs)


def _assert_output(actual, expected):
    assert len(actual) == len(expected)
    if isinstance(expected[0], torch.Tensor):
        assert isinstance(actual[0], torch.Tensor)
        assert actual[0].shape == expected[0].shape and actual[0].dtype == expected[0].dtype
        assert actual[0].device == expected[0].device and torch.equal(actual[0], expected[0])
        actual, expected = actual[1:], expected[1:]
    assert tuple(actual) == tuple(expected) and all(type(x) is int for x in actual)


async def _execute(node_id, inputs, ops=None):
    refs = _sdk.InProcessRefResolver()
    wrapped = await _sdk.wrap_inputs(refs, inputs)
    plan = _sdk.ExecutionPlan(prompt_id='local', node_id=node_id, node_type=node_id, inputs=wrapped, permissions=())
    runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=ops or _sdk.InProcessOps())
    with _sdk.bind_runtime(runtime.refs, runtime.ctx, runtime.ops):
        output = _new().NODE_CLASS_MAPPINGS[node_id].execute(**wrapped)
        if inspect.isawaitable(output):
            output = await output
        result = list(output.result)
        if result and isinstance(result[0], _sdk.Ref):
            result[0] = await refs.resolve(result[0])
        return result


def _normalize_inputs(inputs):
    result = copy.deepcopy(inputs)
    for group in result.values():
        for name, value in group.items():
            kind, options = value if len(value) == 2 else (value[0], {})
            if kind == 'COMBO':
                kind = options.pop('options'); options.pop('multiselect', None)
            options.pop('optional', None)
            group[name] = (kind, options)
    return result


def test_exact_actual_loader_census_schema_and_manifest():
    old, new = _old(), _new()
    loaded = packdb.load_pack(SNAPSHOT, mount_name='custom_nodes.ned_reimgsize_census')
    assert tuple(old.NODE_CLASS_MAPPINGS) == tuple(new.NODE_CLASS_MAPPINGS) == tuple(loaded.node_mappings) == IDS
    assert old.NODE_DISPLAY_NAME_MAPPINGS == new.NODE_DISPLAY_NAME_MAPPINGS
    assert not loaded.routes and not loaded.frontend_permissions and loaded.web_directory is None
    assert not hasattr(old, 'WEB_DIRECTORY') and not list(PACK.rglob('*.js'))
    for node_id, node in new.NODE_CLASS_MAPPINGS.items():
        legacy = old.NODE_CLASS_MAPPINGS[node_id]
        schema = node.GET_SCHEMA(); schema.validate()
        assert schema.node_id == node_id and schema.category == legacy.CATEGORY
        assert schema.display_name == old.NODE_DISPLAY_NAME_MAPPINGS[node_id]
        assert not schema.is_output_node and not schema.is_input_list
        assert [(x.io_type, x.display_name) for x in schema.outputs] == list(zip(legacy.RETURN_TYPES, legacy.RETURN_NAMES))
        assert _normalize_inputs(loaded.node_mappings[node_id].INPUT_TYPES()) == _normalize_inputs(legacy.INPUT_TYPES())
        assert node.SDK_REFS is True
        assert node.SDK_PERMISSIONS == (() if node_id == IDS[2] else ('inspect',))
        assert loaded.node_mappings[node_id].RETURN_TYPES == list(legacy.RETURN_TYPES)


@pytest.mark.parametrize('node_id', IDS[:2])
@pytest.mark.parametrize('method', METHODS)
@pytest.mark.parametrize('crop', ['disabled', 'center'])
@pytest.mark.parametrize('shape', [(1, 13, 19, 3), (2, 21, 9, 3)])
def test_every_interpolation_crop_batch_orientation_pixel_exact(node_id, method, crop, shape):
    image = torch.rand(shape, generator=torch.Generator().manual_seed(12))
    before = image.clone()
    inputs = _inputs(node_id, image, method, crop)
    _assert_output(asyncio.run(_execute(node_id, inputs)), _legacy(node_id, inputs))
    assert torch.equal(image, before)


@pytest.mark.parametrize('override', [{}, {'width': 17}, {'height': 17}, {'width': 17, 'height': 23},
    {'width': 5, 'height': 7, 'GCD': 2}, {'width': 7, 'height': 9, 'GCD': 2}, {'img_size': 33, 'GCD': 8}])
def test_optional_dimensions_rounding_ties_and_order(override):
    image = torch.rand((3, 9, 13, 3), generator=torch.Generator().manual_seed(10))
    inputs = _inputs('Reimgsize', image, **override)
    _assert_output(asyncio.run(_execute('Reimgsize', inputs)), _legacy('Reimgsize', inputs))


@pytest.mark.parametrize('channels', [1, 3, 4])
@pytest.mark.parametrize('dtype', [torch.float16, torch.float32, torch.float64])
def test_channels_dtypes_noncontiguous_and_identity(channels, dtype):
    image = torch.rand((2, 12, 16, channels), generator=torch.Generator().manual_seed(5)).to(dtype)[:, ::2, ::2]
    inputs = _inputs('Reimgsize', image, method='nearest-exact', width=8, height=6, GCD=1)
    _assert_output(asyncio.run(_execute('Reimgsize', inputs)), _legacy('Reimgsize', inputs))


def test_scalar_ratio_extremes_zero_dimensions_and_1000_seeded_cases():
    node = _new().NODE_CLASS_MAPPINGS['Resizebyratio']
    rng = random.Random(1212)
    cases = [(32, .001, 64., 512), (8192, 64., .001, 1), (33, 1., 1., 2)]
    cases += [(rng.randint(32, 8192), rng.uniform(.001, 64), rng.uniform(.001, 64), rng.randint(1, 512)) for _ in range(1000)]
    for size, w, h, gcd in cases:
        inputs = _inputs('Resizebyratio', size=size, width_ratio=w, height_ratio=h, GCD=gcd)
        _assert_output(node.execute(**inputs).result, _legacy('Resizebyratio', inputs))


class CountingOps(_sdk.InProcessOps):
    def __init__(self):
        super().__init__(); self.resize_calls = []
    async def apply(self, name, ref, params):
        if name == 'image.resize':
            self.resize_calls.append(params)
        return await super().apply(name, ref, params)


def test_legacy_zero_rounding_and_degenerate_crop_fail_without_broker_allocation():
    image = torch.zeros(1, 9, 13, 3)
    for node_id, inputs in [
        ('Reimgsize', _inputs('Reimgsize', image, img_size=1, GCD=64)),
        ('Cropimg', _inputs('Cropimg', image, width_ratio=.001, height_ratio=64.))]:
        with pytest.raises(Exception):
            _legacy(node_id, inputs)
        ops = CountingOps()
        with pytest.raises((ValueError, ZeroDivisionError)):
            asyncio.run(_execute(node_id, inputs, ops))
        assert not ops.resize_calls


@pytest.mark.parametrize('override', [{'width': 8192, 'height': 8192}, {'width': 8193}, {'GCD': 0},
    {'GCD': True}, {'img_size': -1}, {'width': '2'}, {'upscale_method': 'unknown'}, {'crop_methods': 'unknown'}])
def test_bounds_reject_before_resize_dispatch(override):
    ops = CountingOps()
    with pytest.raises((TypeError, ValueError)):
        asyncio.run(_execute('Reimgsize', _inputs('Reimgsize', torch.zeros(1, 8, 8, 3), **override), ops))
    assert not ops.resize_calls


@pytest.mark.parametrize('image', [torch.zeros(1, 2, 2), torch.zeros(1, 2, 2, 2), torch.zeros(0, 2, 2, 3),
    torch.zeros(33, 1, 1, 3), torch.empty(1, 8193, 1, 3, device='meta'), torch.empty(1, 2049, 2049, 3, device='meta')])
def test_input_shapes_and_resource_budget_reject_without_allocation(image):
    ops = CountingOps()
    with pytest.raises(ValueError):
        asyncio.run(_execute('Reimgsize', _inputs('Reimgsize', image), ops))
    assert not ops.resize_calls


@pytest.mark.parametrize('value', [True, None, '1', float('nan'), float('inf'), 0., 64.001])
def test_ratio_inputs_are_finite_bounded_scalars(value):
    for node_id in IDS[1:]:
        with pytest.raises((TypeError, ValueError)):
            asyncio.run(_execute(node_id, _inputs(node_id, torch.zeros(1, 8, 8, 3), width_ratio=value)))


def test_trusted_resize_broker_itself_fails_closed_before_common_upscale(monkeypatch):
    import comfy.utils
    def never(*args, **kwargs):
        raise AssertionError('broker allocated before rejecting malformed input')
    monkeypatch.setattr(comfy.utils, 'common_upscale', never)
    async def run():
        refs = _sdk.InProcessRefResolver()
        wrapped = await _sdk.wrap_inputs(refs, {'image': torch.zeros(1, 2, 2, 3)})
        plan = _sdk.ExecutionPlan(prompt_id='broker', node_id='1', node_type='broker', inputs=wrapped)
        with _sdk.bind_runtime(refs, _sdk.InProcessCtxProvider().build(plan), _sdk.InProcessOps()):
            for params in ({'width': 0, 'height': 1}, {'width': 16385, 'height': 1},
                           {'width': 2, 'height': 2, 'method': 'unknown'}, {'width': 2, 'height': 2, 'crop': 'bad'}):
                with pytest.raises(ValueError):
                    await wrapped['image'].resize(**params)
        assert len(refs._table) == 1
    asyncio.run(run())


def test_actual_guest_without_inspect_fails_before_resize_allocation():
    async def run():
        session = await GuestSession('ned-reimg-inspect-denial', guest_runtime_root=V2).start()
        refs = _sdk.InProcessRefResolver(); ops = CountingOps()
        try:
            for node_id in IDS[:2]:
                node = _new().NODE_CLASS_MAPPINGS[node_id]
                plan = _sdk.ExecutionPlan(prompt_id='denial', node_id=node_id, node_type=node.__name__, tier='sandbox',
                    node_module=node.__module__, inputs=await _sdk.wrap_inputs(refs, _inputs(node_id, torch.zeros(1, 8, 8, 3))),
                    permissions=(), method='execute')
                runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=ops)
                with pytest.raises(Exception, match='inspect'):
                    await session.execute(plan, runtime, capabilities=())
            assert not ops.resize_calls and len(refs._table) == 2
        finally:
            await session.kill()
    asyncio.run(run())


def test_inert_inspection_does_not_grant_pixel_buffers(tmp_path):
    # A separate confined probe exercises real raw denial using only inspect.
    (tmp_path / 'probe.py').write_text(
        'from comfy_api.latest import io\n'
        'class Probe(io.ComfyNode):\n'
        ' @classmethod\n'
        ' def define_schema(cls): return io.Schema(node_id="Probe", inputs=[io.Image.Input("image")], outputs=[])\n'
        ' @classmethod\n'
        ' async def execute(cls,image):\n'
        '  await image.describe()\n'
        '  await image.raw()\n'
        '  return io.NodeOutput()\n')
    spec = importlib.util.spec_from_file_location('_ned_reimg_probe', tmp_path / 'probe.py')
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
    async def run():
        session = await GuestSession('ned-reimg-raw-denial', guest_runtime_root=tmp_path).start()
        refs = _sdk.InProcessRefResolver()
        try:
            plan = _sdk.ExecutionPlan(prompt_id='raw-denial', node_id='1', node_type='Probe', node_module=spec.name,
                inputs=await _sdk.wrap_inputs(refs, {'image': torch.zeros(1, 2, 2, 3)}), permissions=('inspect',), method='execute')
            runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
            with pytest.raises(Exception, match='raw'):
                await session.execute(plan, runtime, capabilities=('inspect',))
            assert len(refs._table) == 1
        finally:
            await session.kill()
    asyncio.run(run())


def test_actual_guest_computed_bounds_fail_before_host_resize_and_guest_remains_usable():
    async def run():
        session = await GuestSession('ned-reimg-allocation-denial', guest_runtime_root=V2).start()
        refs = _sdk.InProcessRefResolver(); ops = CountingOps()
        try:
            cases = [('Reimgsize', {'width': 8192, 'height': 8192}),
                     ('Reimgsize', {'width': 2048, 'height': 2048}),
                     ('Reimgsize', {'img_size': 1, 'GCD': 64}),
                     ('Cropimg', {'width_ratio': .001, 'height_ratio': 64.})]
            for node_id, overrides in cases:
                node = _new().NODE_CLASS_MAPPINGS[node_id]
                inputs = _inputs(node_id, torch.zeros(2, 8, 8, 3), **overrides)
                plan = _sdk.ExecutionPlan(prompt_id='bounds', node_id=node_id, node_type=node.__name__, tier='sandbox',
                    node_module=node.__module__, inputs=await _sdk.wrap_inputs(refs, inputs),
                    permissions=node.SDK_PERMISSIONS, method='execute')
                runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=ops)
                size_before = len(refs._table)
                with pytest.raises(Exception, match='bounded|ZeroDivisionError'):
                    await session.execute(plan, runtime, capabilities=node.SDK_PERMISSIONS)
                assert not ops.resize_calls and len(refs._table) == size_before
            inputs = _inputs('Reimgsize', torch.zeros(1, 8, 8, 3))
            node = _new().NODE_CLASS_MAPPINGS['Reimgsize']
            plan = _sdk.ExecutionPlan(prompt_id='bounds-ok', node_id='ok', node_type=node.__name__, tier='sandbox',
                node_module=node.__module__, inputs=await _sdk.wrap_inputs(refs, inputs), permissions=node.SDK_PERMISSIONS, method='execute')
            runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=ops)
            result = list((await session.execute(plan, runtime, capabilities=node.SDK_PERMISSIONS)).result)
            result[0] = await refs.resolve(result[0]); _assert_output(result, _legacy('Reimgsize', inputs))
            assert len(ops.resize_calls) == 1
        finally:
            await session.kill()
    asyncio.run(run())


def test_real_minimal_capability_guest_all_methods_crop_and_scalar():
    async def run():
        session = await GuestSession('ned-reimgsize', guest_runtime_root=V2).start()
        refs = _sdk.InProcessRefResolver()
        try:
            for node_id in IDS:
                for method in (METHODS if node_id != IDS[2] else ('bicubic',)):
                    for crop in (('disabled', 'center') if node_id != IDS[2] else ('disabled',)):
                        image = torch.rand((2, 13, 19, 3), generator=torch.Generator().manual_seed(19))
                        inputs = _inputs(node_id, image, method, crop)
                        node = _new().NODE_CLASS_MAPPINGS[node_id]
                        plan = _sdk.ExecutionPlan(prompt_id='reimg', node_id=node_id, node_type=node.__name__, tier='sandbox',
                            node_module=node.__module__, inputs=await _sdk.wrap_inputs(refs, inputs), permissions=node.SDK_PERMISSIONS, method='execute')
                        runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
                        result = list((await session.execute(plan, runtime, capabilities=node.SDK_PERMISSIONS)).result)
                        if isinstance(result[0], _sdk.Ref):
                            result[0] = await refs.resolve(result[0])
                        _assert_output(result, _legacy(node_id, inputs))
            assert session.last_guest_pid not in (None, os.getpid()) and session.sandbox_kind != 'none'
        finally:
            await session.kill()
    asyncio.run(run())


def test_real_outer_executor_output_types_pixels_and_metadata():
    loaded = packdb.load_pack(SNAPSHOT, mount_name='custom_nodes.ned_reimgsize_outer')
    async def run():
        previous = _sdk.providers.execution_backend
        class Backend:
            session = None
            async def dispatch(self, plan, local_call, runtime):
                if self.session is None:
                    self.session = await GuestSession('ned-reimg-outer', guest_runtime_root=V2).start()
                return await self.session.execute(plan, runtime, capabilities=plan.permissions)
        backend = Backend(); _sdk.providers.register_execution_backend(backend)
        try:
            for node_id, node in loaded.node_mappings.items():
                for method in (METHODS if node_id != IDS[2] else ('bicubic',)):
                    inputs = _inputs(node_id, torch.rand((2, 11, 17, 3), generator=torch.Generator().manual_seed(25)), method, 'center')
                    results = await execution._async_map_node_over_list(prompt_id='ned-reimg-outer', unique_id=node_id,
                        obj=node, input_data_all={key: [value] for key, value in inputs.items()}, func=node.FUNCTION, v3_data=None)
                    assert len(results) == 1
                    _assert_output(results[0].result, _legacy(node_id, inputs))
        finally:
            _sdk.providers.register_execution_backend(previous)
            if backend.session is not None:
                await backend.session.kill()
    asyncio.run(run())


def test_fresh_guest_filesystem_tenant_statelessness(tmp_path):
    async def run():
        pids = []
        for index, tenant in enumerate(('a', 'b', 'a')):
            fresh = tmp_path / str(index); shutil.copytree(V2, fresh)
            node = _load(f'_ned_reimg_fresh_{index}', fresh).NODE_CLASS_MAPPINGS['Reimgsize']
            session = await GuestSession(f'ned-reimg-fresh-{index}', guest_runtime_root=fresh).start()
            refs = _sdk.InProcessRefResolver()
            inputs = _inputs('Reimgsize', torch.ones(1, 7, 11, 3))
            try:
                plan = _sdk.ExecutionPlan(prompt_id='fresh', node_id='1', node_type=node.__name__, tier='sandbox',
                    node_module=node.__module__, inputs=await _sdk.wrap_inputs(refs, inputs), permissions=node.SDK_PERMISSIONS, method='execute')
                runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
                result = list((await session.execute(plan, runtime, capabilities=node.SDK_PERMISSIONS, tenant=tenant)).result)
                result[0] = await refs.resolve(result[0]); _assert_output(result, _legacy('Reimgsize', inputs))
                pids.append(session.last_guest_pid)
            finally:
                await session.kill()
        assert len(set(pids)) == 3
    asyncio.run(run())


def test_manifest_stubs_identity_and_no_ambient_authority():
    assert json.loads((V2 / 'secure-nodes.json').read_text()) == _manifest(_new())
    assert hashlib.sha256((V2 / 'comfy-api.d.ts').read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / 'comfy-api.pyi').read_bytes()).hexdigest() == PYI_SHA
    paths = {p.relative_to(PACK).as_posix() for p in PACK.rglob('*') if p.is_file() and not p.is_relative_to(V2)}
    assert paths == set(PRISTINE_SHA)
    for path, sha in PRISTINE_SHA.items():
        assert hashlib.sha256((PACK / path).read_bytes()).hexdigest() == sha
    source = (V2 / 'nodes.py').read_text()
    for forbidden in ('import comfy.', 'folder_paths', 'PromptServer', '.raw(', '_from_raw', 'open(', 'subprocess', 'requests', 'eval(', 'exec('):
        assert forbidden not in source
    assert COMMIT in (V2 / 'SECURE_CONVERSION.md').read_text()


def test_exact_patch_roundtrip_and_cache_hygiene(tmp_path):
    manifest, diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix('.json').read_text()) == manifest
    assert PAIR.with_suffix('.diff').read_text() == diff
    fresh = tmp_path / 'comfyui-reimgsize/xaada583'; fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns('v2'))
    packpatch.apply(fresh, manifest, diff)
    packpatch.validate_tree(fresh / PACK.name / 'v2', V2)
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))
