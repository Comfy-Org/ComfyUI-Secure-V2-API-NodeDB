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

COMMIT = '8869dbd17e8fb7afb7dd8990b26bb4baaae07027'
DTS_SHA = '4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3'
PYI_SHA = '50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78'
PAIR = PACK_DB / 'patches/sdupcaletiledsize/x8869dbd/sdupcaletiledsize-x8869dbd'
NODE_ID = 'SDupscaleTiledSize'
PRISTINE_SHA = {
    'pyproject.toml': '3acb0db6f1fa5bc6cdd4e34316933e0a25e55f66bebbd11ffa290d6714e33102',
    '__init__.py': '7efd5daa4ed5f9d06f2731db352403b6a7cd12accd5d510b1328d158b13ebcad',
    'README.md': '82185cc56167bdadfb5131f97995a578e3bbf103717151ffc410c521721d1e97',
    'nodes.py': '37a52a419df73a3cda4a4af1e4049420dce5f51ecdfe04c8ac4f989e645aebf1',
    '.github/workflows/publish.yml': '61e33002e11097be5f2b138eb9d0f1a2dac5a299f3635dccf81dae74960cd7af',
}


def _load(name, root):
    if name in sys.modules and Path(sys.modules[name].__file__) == root / '__init__.py':
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, root / '__init__.py', submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _old():
    return _load('_ned_tiled_size_pristine', PACK)


def _new():
    return _load('_ned_tiled_size_secure', V2)


def _manifest(module):
    node = module.NODE_CLASS_MAPPINGS[NODE_ID]
    return {'format': FORMAT, 'nodes': {NODE_ID: {
        'class': node.__name__, 'module': 'nodes', 'sdk_refs': True, 'permissions': [],
        'methods': {key: False for key in ('validate_inputs', 'fingerprint_inputs', 'check_lazy_status')},
        'schema': encode_schema(copy.deepcopy(node.GET_SCHEMA())),
    }}, 'runtime': manifest_declaration(V2)}


class MetadataOnlyOps(_sdk.InProcessOps):
    def __init__(self):
        super().__init__(); self.calls = []
    async def apply(self, name, ref, params):
        self.calls.append((name, params))
        assert name == 'image.spatial_shape', 'unexpected pixel access/inspection/allocation'
        return await super().apply(name, ref, params)


async def _local(image, tiled_block=1536, upscale_by=1.):
    refs = _sdk.InProcessRefResolver(); ops = MetadataOnlyOps()
    inputs = await _sdk.wrap_inputs(refs, dict(image=image, tiled_block=tiled_block, upscale_by=upscale_by))
    plan = _sdk.ExecutionPlan(prompt_id='tile-local', node_id='1', node_type=NODE_ID, inputs=inputs, permissions=())
    with _sdk.bind_runtime(refs, _sdk.InProcessCtxProvider().build(plan), ops):
        output = await _new().NODE_CLASS_MAPPINGS[NODE_ID].execute(**inputs)
        assert output.result[0] is inputs['image']
        assert await refs.resolve(output.result[0]) is image
        assert len(refs._table) == 1 and ops.calls == [('image.spatial_shape', {})]
        return output.result


def _old_helper(width, height, upscale_by, tiled_block):
    node = _old().NODE_CLASS_MAPPINGS[NODE_ID]
    return sys.modules[node.__module__].uov_tiled_size(width, height, upscale_by, tiled_block)


def test_actual_census_complete_schema_display_manifest_and_license_disposition():
    old, new = _old(), _new()
    loaded = packdb.load_pack(SNAPSHOT, mount_name='custom_nodes.ned_tiled_size_census')
    assert list(old.NODE_CLASS_MAPPINGS) == list(new.NODE_CLASS_MAPPINGS) == list(loaded.node_mappings) == [NODE_ID]
    assert old.NODE_DISPLAY_NAME_MAPPINGS == new.NODE_DISPLAY_NAME_MAPPINGS == {NODE_ID: NODE_ID}
    node = new.NODE_CLASS_MAPPINGS[NODE_ID]; legacy = old.NODE_CLASS_MAPPINGS[NODE_ID]
    schema = node.GET_SCHEMA(); schema.validate()
    assert schema.node_id == NODE_ID and schema.display_name == NODE_ID and schema.category == legacy.CATEGORY
    assert not schema.is_output_node and not schema.is_input_list
    assert [(x.io_type, x.display_name) for x in schema.outputs] == list(zip(legacy.RETURN_TYPES, legacy.RETURN_NAMES))
    expected = copy.deepcopy(legacy.INPUT_TYPES()); expected['required']['image'] = ('IMAGE', {})
    assert loaded.node_mappings[NODE_ID].INPUT_TYPES() == expected
    assert loaded.node_mappings[NODE_ID].RETURN_TYPES == list(legacy.RETURN_TYPES)
    assert node.SDK_REFS is True and node.SDK_PERMISSIONS == ()
    assert not loaded.routes and not loaded.frontend_permissions and loaded.web_directory is None
    assert not hasattr(old, 'WEB_DIRECTORY') and not list(PACK.rglob('*.js'))
    assert not (PACK / 'LICENSE').exists() and not (V2 / 'LICENSE').exists()
    assert 'absent LICENSE' in (V2 / 'SECURE_CONVERSION.md').read_text()


@pytest.mark.parametrize('width,height', [(1, 1), (511, 513), (768, 1024), (1535, 1536),
    (2048, 2049), (4096, 6144), (16384, 16384)])
@pytest.mark.parametrize('factor', [.5, 1., 1.9, 3.99999, 4., 8.])
def test_exact_int_ceil_16_rounding_and_upper_factor_clamp(width, height, factor):
    image = torch.empty((2, height, width, 3), device='meta')
    for block in (512, 768, 1024, 1280, 1536, 1792, 2048):
        result = asyncio.run(_local(image, block, factor))
        assert tuple(result[1:]) == _old_helper(width, height, factor, block)
        assert result[2] % 16 == result[3] % 16 == 0


def test_1000_seeded_math_differentials_with_block_threshold_neighbors():
    new = sys.modules[_new().NODE_CLASS_MAPPINGS[NODE_ID].__module__]
    rng = random.Random(3120)
    cases = [(w, h, f, b) for b in (1, 512, 1536, 2048)
             for w, h in ((b-1 if b > 1 else 1, b), (b, b+1), (2*b, 2*b+1))
             for f in (.5, 1., 4., 1e100, 0., -.5)]
    cases += [(rng.randint(1, 16384), rng.randint(1, 16384), rng.uniform(-5, 8), rng.randint(1, 2048)) for _ in range(1000)]
    for w, h, f, b in cases:
        assert new.uov_tiled_size(w, h, f, b) == _old_helper(w, h, f, b)


@pytest.mark.parametrize('shape,dtype', [((1, 7, 13, 1), torch.float16), ((3, 7, 13, 3), torch.float32),
    ((2, 7, 13, 4), torch.float64), ((0, 7, 13, 3), torch.float32),
    ((4096, 1, 1, 3), torch.uint8)])
def test_image_aliasing_batch_channels_dtype_stride_and_no_buffer_compute(shape, dtype):
    image = torch.ones(shape, dtype=dtype)[:, ::2, ::2]
    old = _old().NODE_CLASS_MAPPINGS[NODE_ID]().calculate_tiled_size(image, 1536, 2.5)
    before = image.clone()
    result = asyncio.run(_local(image, 1536, 2.5))
    assert old[0] is image and tuple(result[1:]) == old[1:]
    assert torch.equal(image, before)


@pytest.mark.parametrize('factor', [0., -.5, -1_000_000., 1e100])
def test_bounded_direct_call_quirks_zero_negative_and_high_clamp(factor):
    image = torch.zeros(1, 19, 23, 3)
    result = asyncio.run(_local(image, 1, factor))
    assert tuple(result[1:]) == _old().NODE_CLASS_MAPPINGS[NODE_ID]().calculate_tiled_size(image, 1, factor)[1:]


def test_sdk_admitted_hwc_uses_actual_dimensions_not_legacy_accidental_channel_indexing():
    image = torch.zeros(7, 13, 3)
    result = asyncio.run(_local(image, 512, 2.))
    assert tuple(result[1:]) == _old_helper(13, 7, 2., 512)
    legacy = _old().NODE_CLASS_MAPPINGS[NODE_ID]().calculate_tiled_size(image, 512, 2.)
    assert tuple(result[1:]) != legacy[1:]
    assert 'HWC' in (V2 / 'SECURE_CONVERSION.md').read_text()


@pytest.mark.parametrize('image', [torch.zeros(2, 2), torch.zeros(1, 2, 2, 2),
    torch.zeros(1, 0, 2, 3), torch.zeros(1, 2, 0, 3), torch.empty(1, 16385, 1, 3, device='meta')])
def test_image_malformed_shape_and_metadata_bounds_reject(image):
    with pytest.raises((TypeError, ValueError)):
        asyncio.run(_local(image))


@pytest.mark.parametrize('overrides', [{'tiled_block': 0}, {'tiled_block': -1}, {'tiled_block': 2049},
    {'tiled_block': True}, {'tiled_block': 512.}, {'tiled_block': '512'}, {'upscale_by': True},
    {'upscale_by': []}, {'upscale_by': float('nan')}, {'upscale_by': float('inf')}, {'upscale_by': -1_000_001.}])
def test_scalar_malformed_bounds_fail_before_host_metadata_call(overrides):
    async def run():
        refs = _sdk.InProcessRefResolver(); ops = MetadataOnlyOps()
        values = dict(image=torch.zeros(1, 2, 2, 3), tiled_block=1536, upscale_by=1.) | overrides
        inputs = await _sdk.wrap_inputs(refs, values)
        plan = _sdk.ExecutionPlan(prompt_id='invalid', node_id='1', node_type=NODE_ID, inputs=inputs)
        with _sdk.bind_runtime(refs, _sdk.InProcessCtxProvider().build(plan), ops):
            with pytest.raises((TypeError, ValueError)):
                await _new().NODE_CLASS_MAPPINGS[NODE_ID].execute(**inputs)
        assert not ops.calls and len(refs._table) <= 2
    asyncio.run(run())


async def _guest_result(session, root, image, block, factor, tenant=None):
    name = '_ned_tiled_guest_' + hashlib.sha256(str(root).encode()).hexdigest()[:12]
    node = _load(name, root).NODE_CLASS_MAPPINGS[NODE_ID]
    assert Path(sys.modules[node.__module__].__file__).parent == root
    refs = _sdk.InProcessRefResolver(); ops = MetadataOnlyOps()
    plan = _sdk.ExecutionPlan(prompt_id='tile-guest', node_id='1', node_type=node.__name__, tier='sandbox',
        node_module=node.__module__, inputs=await _sdk.wrap_inputs(refs, dict(image=image, tiled_block=block, upscale_by=factor)),
        permissions=(), method='execute')
    runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=ops)
    output = await session.execute(plan, runtime, capabilities=(), tenant=tenant)
    assert output.result[0].kind == 'IMAGE' and output.result[0].id == plan.inputs['image'].id
    assert await refs.resolve(output.result[0]) is image
    assert len(refs._table) == 1 and ops.calls == [('image.spatial_shape', {})]
    return output.result


def test_real_zero_permission_guest_passthrough_and_scalar_results():
    async def run():
        session = await GuestSession('ned-tiled-size', guest_runtime_root=V2).start()
        try:
            for image, block, factor in [
                (torch.zeros(2, 13, 17, 3), 512, .5), (torch.ones(1, 17, 13, 4, dtype=torch.float64), 1536, 8.),
                (torch.empty(2, 16384, 16384, 3, device='meta'), 2048, 4.),
                (torch.zeros(13, 17, 3), 512, 2.), (torch.zeros(0, 13, 17, 3), 1536, 1.)]:
                result = await _guest_result(session, V2, image, block, factor)
                assert tuple(result[1:]) == _old_helper(image.shape[-2], image.shape[-3], factor, block)
            assert session.last_guest_pid not in (None, os.getpid()) and session.sandbox_kind != 'none'
        finally:
            await session.kill()
    asyncio.run(run())


def test_real_outer_executor_keeps_image_object_device_dtype_stride_and_exact_scalars():
    loaded = packdb.load_pack(SNAPSHOT, mount_name='custom_nodes.ned_tiled_size_outer')
    async def run():
        previous = _sdk.providers.execution_backend
        class Backend:
            session = None
            async def dispatch(self, plan, local_call, runtime):
                if self.session is None:
                    self.session = await GuestSession('ned-tiled-size-outer', guest_runtime_root=V2).start()
                return await self.session.execute(plan, runtime, capabilities=())
        backend = Backend(); _sdk.providers.register_execution_backend(backend)
        try:
            node = loaded.node_mappings[NODE_ID]
            for image in [torch.ones(2, 13, 17, 3)[:, ::2, ::2], torch.ones(1, 13, 17, 4, dtype=torch.float64),
                          torch.empty(1, 16384, 16384, 3, device='meta')]:
                inputs = dict(image=image, tiled_block=1536, upscale_by=3.5)
                results = await execution._async_map_node_over_list(prompt_id='ned-tile-outer', unique_id='1', obj=node,
                    input_data_all={key: [value] for key, value in inputs.items()}, func=node.FUNCTION, v3_data=None)
                assert len(results) == 1 and results[0].result[0] is image
                assert tuple(results[0].result[1:]) == _old().NODE_CLASS_MAPPINGS[NODE_ID]().calculate_tiled_size(**inputs)[1:]
        finally:
            _sdk.providers.register_execution_backend(previous)
            if backend.session is not None:
                await backend.session.kill()
    asyncio.run(run())


@pytest.mark.parametrize('operation,error', [('raw', 'raw'), ('describe', 'inspect')])
def test_zero_permissions_deny_buffer_access_and_inspection(tmp_path, operation, error):
    (tmp_path / 'probe.py').write_text(
        'from comfy_api.latest import io\n'
        'class Probe(io.ComfyNode):\n'
        ' @classmethod\n'
        ' def define_schema(cls): return io.Schema(node_id="Probe", inputs=[io.Image.Input("image")], outputs=[])\n'
        ' @classmethod\n'
        ' async def execute(cls,image):\n'
        '  await image.spatial_shape()\n'
        f'  await image.{operation}()\n'
        '  return io.NodeOutput()\n')
    spec = importlib.util.spec_from_file_location('_ned_tiled_security_probe', tmp_path / 'probe.py')
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
    async def run():
        session = await GuestSession('ned-tiled-security-probe', guest_runtime_root=tmp_path).start()
        refs = _sdk.InProcessRefResolver()
        try:
            plan = _sdk.ExecutionPlan(prompt_id='deny', node_id='1', node_type='Probe', node_module=spec.name,
                inputs=await _sdk.wrap_inputs(refs, {'image': torch.zeros(1, 2, 2, 3)}), permissions=(), method='execute')
            runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
            with pytest.raises(Exception, match=error):
                await session.execute(plan, runtime, capabilities=())
            assert len(refs._table) == 1
        finally:
            await session.kill()
    asyncio.run(run())


def test_actual_guest_malformed_limits_fail_without_new_refs_and_recovers():
    async def run():
        node = _new().NODE_CLASS_MAPPINGS[NODE_ID]
        session = await GuestSession('ned-tiled-limits', guest_runtime_root=V2).start()
        try:
            for image, overrides in [(torch.zeros(1, 2, 2, 3), {'tiled_block': 0}),
                (torch.zeros(1, 2, 2, 3), {'upscale_by': float('nan')}),
                (torch.zeros(1, 2, 2, 2), {}), (torch.empty(1, 16385, 2, 3, device='meta'), {})]:
                refs = _sdk.InProcessRefResolver(); ops = _sdk.InProcessOps()
                values = dict(image=image, tiled_block=1536, upscale_by=1.) | overrides
                plan = _sdk.ExecutionPlan(prompt_id='invalid', node_id='1', node_type=node.__name__, node_module=node.__module__,
                    inputs=await _sdk.wrap_inputs(refs, values), permissions=(), method='execute')
                runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=ops)
                with pytest.raises(Exception):
                    await session.execute(plan, runtime, capabilities=())
                assert len(refs._table) == 1
            result = await _guest_result(session, V2, torch.ones(1, 2, 2, 3), 1536, 1.)
            assert tuple(result[1:]) == (1., 16, 16)
        finally:
            await session.kill()
    asyncio.run(run())


def test_fresh_filesystems_and_guests_per_user_are_stateless(tmp_path):
    async def run():
        pids = []
        for index, user in enumerate(('user-a', 'user-b', 'user-a')):
            fresh = tmp_path / str(index); shutil.copytree(V2, fresh)
            session = await GuestSession(f'ned-tiled-fresh-{index}', guest_runtime_root=fresh).start()
            try:
                result = await _guest_result(session, fresh, torch.ones(1, 513, 511, 3), 512, 1.5, tenant=user)
                assert tuple(result[1:]) == _old_helper(511, 513, 1.5, 512)
                pids.append(session.last_guest_pid)
            finally:
                await session.kill()
        assert len(set(pids)) == 3
    asyncio.run(run())


def test_exact_manifest_current_stubs_pristine_identity_and_no_ambient_authority():
    assert json.loads((V2 / 'secure-nodes.json').read_text()) == _manifest(_new())
    assert hashlib.sha256((V2 / 'comfy-api.d.ts').read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / 'comfy-api.pyi').read_bytes()).hexdigest() == PYI_SHA
    paths = {p.relative_to(PACK).as_posix() for p in PACK.rglob('*') if p.is_file() and not p.is_relative_to(V2)}
    assert paths == set(PRISTINE_SHA)
    for path, sha in PRISTINE_SHA.items():
        assert hashlib.sha256((PACK / path).read_bytes()).hexdigest() == sha
    source = (V2 / 'nodes.py').read_text()
    for forbidden in ('torch', 'PIL', 'import comfy.', 'folder_paths', 'PromptServer', '.raw(', '.describe(', '_from_raw',
                      'open(', 'subprocess', 'requests', 'eval(', 'exec('):
        assert forbidden not in source
    assert COMMIT in (V2 / 'SECURE_CONVERSION.md').read_text()


def test_byte_exact_patch_roundtrip_and_pristine_v2_cache_hygiene(tmp_path):
    manifest, diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix('.json').read_text()) == manifest
    assert PAIR.with_suffix('.diff').read_bytes().decode('utf-8') == diff
    fresh = tmp_path / 'sdupcaletiledsize/x8869dbd'; fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns('v2'))
    packpatch.apply(fresh, manifest, diff)
    packpatch.validate_tree(fresh / PACK.name / 'v2', V2)
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))
