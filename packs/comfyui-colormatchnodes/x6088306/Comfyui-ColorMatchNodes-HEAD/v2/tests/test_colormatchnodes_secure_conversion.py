from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.metadata
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
BACKEND = Path('/Users/ben/comfy/ComfyUI_secure_nodes/backend')
CORE = Path(os.environ.get('COMFY_CORE_ROOT', '/Users/ben/comfy/ComfyUI-secure-nodes'))
for root in (BACKEND, CORE):
    sys.path.insert(0, str(root))
os.environ.setdefault('COMFY_CORE_ROOT', str(CORE))
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb, packpatch
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes.transport.host import GuestSession

COMMIT = '6088306cda0383cbfc5252e83f25b7de82152ae1'
DTS_SHA = '4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3'
PYI_SHA = '50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78'
PAIR = PACK_DB / 'patches/comfyui-colormatchnodes/x6088306/comfyui-colormatchnodes-x6088306'
METHODS = ['mkl', 'hm', 'reinhard', 'mvgd', 'hm-mvgd-hm', 'hm-mkl-hm']
EASING = ['linear', 'ease_in', 'ease_out', 'ease_in_out', 'smoothstep']


def _load(name, root):
    for key in tuple(sys.modules):
        if key == name or key.startswith(name + '.'):
            sys.modules.pop(key)
    spec = importlib.util.spec_from_file_location(name, root / '__init__.py', submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _secure():
    return _load('_color_match_nodes_secure', V2)


def _old(tmp_path):
    root = tmp_path / 'source'
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns('v2'))
    return _load('_color_match_nodes_upstream', root)


def _manifest(module):
    return {'format': FORMAT, 'nodes': {node_id: {
        'class': cls.__name__, 'module': 'nodes', 'sdk_refs': False, 'permissions': ['raw'],
        'methods': {name: False for name in ('validate_inputs', 'fingerprint_inputs', 'check_lazy_status')},
        'schema': encode_schema(copy.deepcopy(cls.GET_SCHEMA()))}
        for node_id, cls in module.NODE_CLASS_MAPPINGS.items()}, 'runtime': manifest_declaration(V2)}


def _image(batch, height=10, width=12, offset=0.0, dtype=torch.float32):
    generator = torch.Generator().manual_seed(6600 + batch + int(offset*1000))
    return (torch.rand((batch, height, width, 3), generator=generator, dtype=dtype)*0.65 + offset).clamp(0, 1)


def _inputs(method='mkl', batch=3):
    return {'image_ref_a': _image(1, offset=0.21), 'image_ref_b': _image(1, offset=0.02),
            'image_target': _image(batch, offset=0.09), 'method': method}


def _call_old(module, node_id, inputs):
    cls = module.NODE_CLASS_MAPPINGS[node_id]
    return getattr(cls(), cls.FUNCTION)(**inputs)[0]


def _exact(actual, expected):
    assert actual.shape == expected.shape and actual.dtype == expected.dtype == torch.float32
    assert actual.device.type == expected.device.type == 'cpu'
    assert torch.equal(actual, expected)
    assert torch.isfinite(actual).all()
    assert actual.min() >= 0 and actual.max() <= 1


def test_actual_census_all_schema_attributes_and_missing_frontend(tmp_path):
    old, new = _old(tmp_path), _secure()
    assert list(old.NODE_CLASS_MAPPINGS) == list(new.NODE_CLASS_MAPPINGS) == ['ColorMatch2Refs', 'ColorMatchBlendAutoWeights']
    assert old.NODE_DISPLAY_NAME_MAPPINGS == new.NODE_DISPLAY_NAME_MAPPINGS
    assert old.WEB_DIRECTORY == './js' and not (PACK / 'js').exists()
    assert not list(PACK.rglob('*.js')) and not hasattr(new, 'WEB_DIRECTORY')
    for node_id, cls in new.NODE_CLASS_MAPPINGS.items():
        upstream = old.NODE_CLASS_MAPPINGS[node_id]
        schema = cls.GET_SCHEMA(); schema.validate()
        assert schema.node_id == node_id and schema.display_name == old.NODE_DISPLAY_NAME_MAPPINGS[node_id]
        assert schema.category == upstream.CATEGORY and schema.description == upstream.DESCRIPTION
        assert [x.io_type for x in schema.outputs] == list(upstream.RETURN_TYPES)
        assert [x.display_name for x in schema.outputs] == list(upstream.RETURN_NAMES)
        groups = upstream.INPUT_TYPES(); required, optional = groups['required'], groups.get('optional', {})
        all_inputs = dict(required, **optional)
        assert [x.id for x in schema.inputs] == list(all_inputs)
        for item in schema.inputs:
            spec = all_inputs[item.id]
            assert item.optional == (item.id in optional)
            assert item.io_type == ('COMBO' if isinstance(spec[0], list) else spec[0])
            if isinstance(spec[0], list):
                assert item.options == spec[0]
            if len(spec) > 1:
                for key, value in spec[1].items():
                    assert getattr(item, key) == value
        assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS == ('raw',)
    loaded = packdb.load_pack(SNAPSHOT, mount_name='custom_nodes.color_match_nodes_census')
    assert set(loaded.node_mappings) == set(old.NODE_CLASS_MAPPINGS)
    assert not loaded.routes and not loaded.frontend_permissions


@pytest.mark.parametrize('node_id', ['ColorMatch2Refs', 'ColorMatchBlendAutoWeights'])
@pytest.mark.parametrize('method', METHODS)
@pytest.mark.parametrize('multithread', [False, True])
def test_six_methods_both_nodes_parallel_and_serial_are_pixel_exact(tmp_path, node_id, method, multithread):
    old, new = _old(tmp_path), _secure()
    inputs = _inputs(method); inputs['multithread'] = multithread
    inputs.update({'weight_a': 0.37, 'strength': 1.8} if node_id == 'ColorMatch2Refs' else
                  {'strength': 1.8, 'mid_strength': 0.2, 'strength_mode': 'u_shape'})
    originals = {key: value.clone() for key, value in inputs.items() if isinstance(value, torch.Tensor)}
    expected = _call_old(old, node_id, inputs)
    actual = new.NODE_CLASS_MAPPINGS[node_id].execute(**inputs).result[0]
    _exact(actual, expected)
    for key, value in originals.items():
        assert torch.equal(inputs[key], value)


@pytest.mark.parametrize('easing', EASING)
@pytest.mark.parametrize('strength_easing', EASING)
def test_all_auto_weight_and_u_strength_curves_exact(tmp_path, easing, strength_easing):
    old, new = _old(tmp_path), _secure()
    inputs = _inputs('reinhard', batch=5)
    inputs.update(easing=easing, strength_easing=strength_easing, ease_power=3.3,
                  start_weight_a=0.15, end_weight_a=0.9, strength_mode='u_shape',
                  strength=1.7, mid_strength=0.12, multithread=False)
    _exact(new.ColorMatchBlendAutoWeights.execute(**inputs).result[0], _call_old(old, 'ColorMatchBlendAutoWeights', inputs))
    for power in (1.0, 2.0, 5.0):
        for t in (0.0, 0.1, 0.49, 0.5, 0.51, 0.9, 1.0):
            assert new.ColorMatchBlendAutoWeights._ease(t, easing, power) == old.ColorMatchBlendAutoWeights._ease(t, easing, power)


@pytest.mark.parametrize('ref_a_mode', ['first frame', 'last frame'])
@pytest.mark.parametrize('ref_b_mode', ['first frame', 'last frame'])
def test_first_last_auto_reference_selection_and_order(tmp_path, ref_a_mode, ref_b_mode):
    old, new = _old(tmp_path), _secure()
    inputs = _inputs('hm', batch=4)
    inputs.update(image_ref_a=_image(3, offset=0.2), image_ref_b=_image(2, offset=0.0),
                  ref_a_batch_mode=ref_a_mode, ref_b_batch_mode=ref_b_mode, multithread=True)
    _exact(new.ColorMatchBlendAutoWeights.execute(**inputs).result[0], _call_old(old, 'ColorMatchBlendAutoWeights', inputs))
    select = dict(inputs)
    select['image_ref_a'] = inputs['image_ref_a'][0 if ref_a_mode == 'first frame' else -1].unsqueeze(0)
    select['image_ref_b'] = inputs['image_ref_b'][0 if ref_b_mode == 'first frame' else -1].unsqueeze(0)
    _exact(new.ColorMatchBlendAutoWeights.execute(**select).result[0], new.ColorMatchBlendAutoWeights.execute(**inputs).result[0])


@pytest.mark.parametrize('batch', [1, 2, 4])
@pytest.mark.parametrize('dtype', [torch.float16, torch.float32, torch.float64])
def test_manual_reference_batches_dtypes_strength_zero_and_singleton_auto(tmp_path, batch, dtype):
    old, new = _old(tmp_path), _secure()
    inputs = {name: _image(batch, offset=offset, dtype=dtype) for name, offset in
              [('image_ref_a', 0.2), ('image_ref_b', 0.02), ('image_target', 0.09)]}
    inputs.update(method='hm', weight_a=0.75, multithread=False)
    for strength in (0.0, 0.4, 10.0):
        args = dict(inputs, strength=strength)
        _exact(new.ColorMatch2Refs.execute(**args).result[0], _call_old(old, 'ColorMatch2Refs', args))
    inputs.pop('weight_a')
    for start, end in [(-0.5, 1.8), (1.8, -0.5)]:
        args = dict(inputs, start_weight_a=start, end_weight_a=end)
        _exact(new.ColorMatchBlendAutoWeights.execute(**args).result[0], _call_old(old, 'ColorMatchBlendAutoWeights', args))


def test_transfer_failure_fallback_and_direct_empty_indexing_errors(tmp_path, capsys, monkeypatch):
    old, new = _old(tmp_path), _secure()
    from color_matcher import ColorMatcher
    transfer = ColorMatcher.transfer
    def fail_a(self, src, ref, method):
        if float(ref.mean()) > 0.5:
            raise ValueError('forced ref A transfer failure')
        return transfer(self, src=src, ref=ref, method=method)
    monkeypatch.setattr(ColorMatcher, 'transfer', fail_a)
    for node_id in new.NODE_CLASS_MAPPINGS:
        inputs = _inputs('mkl')
        if node_id == 'ColorMatch2Refs':
            inputs['weight_a'] = 0.4
        _exact(new.NODE_CLASS_MAPPINGS[node_id].execute(**inputs).result[0], _call_old(old, node_id, inputs))
        assert 'failed' in capsys.readouterr().out
        inputs['image_target'] = inputs['image_target'][:0]
        with pytest.raises(Exception) as expected:
            _call_old(old, node_id, inputs)
        with pytest.raises(type(expected.value)) as actual:
            new.NODE_CLASS_MAPPINGS[node_id].execute(**inputs)
        assert str(actual.value) == str(expected.value)
    monkeypatch.setattr(ColorMatcher, 'transfer', transfer)
    # Normalize the vendor's fatal BaseException for values outside the
    # declared six-method enum into an ordinary fail-closed guest error.
    for node_id in new.NODE_CLASS_MAPPINGS:
        inputs = _inputs('invalid-method')
        if node_id == 'ColorMatch2Refs':
            inputs['weight_a'] = 0.5
        with pytest.raises(BaseException) as expected:
            _call_old(old, node_id, inputs)
        with pytest.raises(ValueError) as actual:
            new.NODE_CLASS_MAPPINGS[node_id].execute(**inputs)
        assert str(actual.value) == str(expected.value)
    inputs = _inputs(); inputs.update(image_ref_a=_image(2), weight_a=0.5, multithread=False)
    with pytest.raises(IndexError) as expected:
        _call_old(old, 'ColorMatch2Refs', inputs)
    with pytest.raises(IndexError) as actual:
        new.ColorMatch2Refs.execute(**inputs)
    assert str(actual.value) == str(expected.value)
    inputs = _inputs(); inputs.update(weight_a=0.5)
    inputs['image_target'].requires_grad_(True)
    with pytest.raises(RuntimeError) as expected:
        _call_old(old, 'ColorMatch2Refs', inputs)
    with pytest.raises(RuntimeError) as actual:
        new.ColorMatch2Refs.execute(**inputs)
    assert str(actual.value) == str(expected.value)


def test_singleton_spatial_squeeze_quirk_matches_upstream(tmp_path):
    old, new = _old(tmp_path), _secure()
    inputs = {name: _image(1, height=1, width=12, offset=offset) for name, offset in
              [('image_ref_a', 0.2), ('image_ref_b', 0.0), ('image_target', 0.1)]}
    inputs.update(method='mkl', weight_a=0.5)
    with pytest.raises(ValueError) as expected:
        _call_old(old, 'ColorMatch2Refs', inputs)
    with pytest.raises(ValueError) as actual:
        new.ColorMatch2Refs.execute(**inputs)
    assert str(actual.value) == str(expected.value)


def test_bounded_thread_fanout_rng_and_resource_limits(monkeypatch):
    new = _secure()
    module = sys.modules[new.ColorMatch2Refs.__module__]
    from concurrent.futures import ThreadPoolExecutor
    seen = []
    class BoundedPool(ThreadPoolExecutor):
        def __init__(self, max_workers):
            seen.append(max_workers)
            super().__init__(max_workers=max_workers)
    monkeypatch.setattr(module, 'ThreadPoolExecutor', BoundedPool)
    py_state, torch_state = random.getstate(), torch.random.get_rng_state().clone()
    inputs = _inputs('hm', batch=5)
    new.ColorMatch2Refs.execute(**inputs, weight_a=0.5)
    new.ColorMatchBlendAutoWeights.execute(**inputs)
    assert seen == [2, 2]
    assert py_state == random.getstate() and torch.equal(torch_state, torch.random.get_rng_state())
    for node_id, cls in new.NODE_CLASS_MAPPINGS.items():
        base = _inputs(); base.update({'weight_a': 0.5} if node_id == 'ColorMatch2Refs' else {})
        for value in [torch.empty((65, 1, 1, 3), device='meta'),
                      torch.empty((1, 4097, 1, 3), device='meta'),
                      torch.empty((1, 1, 1, 5), device='meta'),
                      torch.empty((2, 4096, 4096, 3), device='meta')]:
            with pytest.raises(ValueError, match='bounded'):
                cls.execute(**dict(base, image_target=value))
        with pytest.raises(TypeError, match='BHWC'):
            cls.execute(**dict(base, image_target=base['image_target'][0]))
    massive = torch.empty((1, 4096, 4096, 1), device='meta')
    with pytest.raises(ValueError, match='total-work'):
        module._bounded_images(massive, massive, massive)


def test_real_isolated_raw_guests_all_methods_and_fresh_render(tmp_path):
    old = _old(tmp_path)
    fresh = tmp_path / 'fresh-render-pack'; shutil.copytree(V2, fresh)
    async def run():
        refs = _sdk.InProcessRefResolver()
        for index, root in enumerate((V2, fresh)):
            new = _load(f'_colormatchnodes_guest_{index}', root)
            session = await GuestSession('color-match-nodes', guest_runtime_root=root).start()
            try:
                async def execute(node_id, inputs, capabilities=('raw',)):
                    handles = []
                    wire_inputs = dict(inputs)
                    for name, value in inputs.items():
                        if isinstance(value, torch.Tensor):
                            handle = _sdk.ImageRef._wrap(await refs.create('IMAGE', value))
                            handles.append(handle); wire_inputs[name] = handle
                    cls = new.NODE_CLASS_MAPPINGS[node_id]
                    plan = _sdk.ExecutionPlan(prompt_id='color-match-nodes', node_id='1', node_type=cls.__name__,
                        tier='sandbox', node_module=cls.__module__, inputs=wire_inputs,
                        input_mode='values', permissions=('raw',), method='execute')
                    runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
                    try:
                        result = await session.execute(plan, runtime, capabilities=capabilities)
                        output = await refs.resolve(result.result[0])
                        await refs.release(result.result[0])
                        return output
                    finally:
                        for handle in handles:
                            await refs.release(handle)
                for node_id in new.NODE_CLASS_MAPPINGS:
                    for method in METHODS:
                        inputs = _inputs(method)
                        inputs.update({'weight_a': 0.42} if node_id == 'ColorMatch2Refs' else
                                      {'easing': 'smoothstep', 'strength_mode': 'u_shape', 'strength_easing': 'ease_in_out'})
                        _exact(await execute(node_id, inputs), _call_old(old, node_id, inputs))
                    with pytest.raises(Exception, match='raw'):
                        await execute(node_id, inputs, capabilities=())
                    with pytest.raises(Exception, match='not recognized'):
                        await execute(node_id, dict(inputs, method='invalid-method'))
                    # A malformed method must not poison this live worker.
                    _exact(await execute(node_id, inputs), _call_old(old, node_id, inputs))
                    invalid = dict(inputs, image_target=torch.empty((65, 1, 1, 3)))
                    with pytest.raises(Exception, match='bounded'):
                        await execute(node_id, invalid)
                assert session.last_guest_pid not in (None, os.getpid()) and not refs._table
            finally:
                await session.kill()
    asyncio.run(run())


def test_manifest_canonical_contract_license_and_authority():
    assert json.loads((V2 / 'secure-nodes.json').read_text()) == _manifest(_secure())
    assert hashlib.sha256((V2 / 'comfy-api.d.ts').read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / 'comfy-api.pyi').read_bytes()).hexdigest() == PYI_SHA
    assert (V2 / 'LICENSE').read_bytes() == (PACK / 'LICENSE').read_bytes()
    report = (V2 / 'SECURE_CONVERSION.md').read_text()
    assert COMMIT in report and 'no durable pack state' in report
    assert importlib.metadata.version('color-matcher') == '0.6.0'
    source = (V2 / 'nodes.py').read_text()
    for forbidden in ('import os', 'os.', 'folder_paths', 'open(', 'requests', 'subprocess', '_from_raw', 'eval(', 'exec(', 'pickle', 'import comfy\n'):
        assert forbidden not in source


def test_byte_exact_pristine_patch_roundtrip(tmp_path):
    manifest, diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix('.json').read_text()) == manifest
    assert PAIR.with_suffix('.diff').read_bytes().decode('utf-8') == diff
    root = tmp_path / 'comfyui-colormatchnodes/x6088306'; root.mkdir(parents=True)
    shutil.copytree(PACK, root / PACK.name, ignore=shutil.ignore_patterns('v2'))
    packpatch.apply(root, manifest, diff)
    packpatch.validate_tree(root / PACK.name / 'v2', V2)
    assert not list(PACK.rglob('*.pyc')) and not list(PACK.rglob('__pycache__'))
