from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import torch

sys.dont_write_bytecode = True
V2 = Path(__file__).resolve().parents[1]
PACK, SNAPSHOT = V2.parent, V2.parent.parent
PACK_DB = SNAPSHOT.parents[2]
CORE = Path(os.environ.get('COMFY_CORE_ROOT', '/Users/ben/comfy/ComfyUI-secure-nodes'))
BACKEND = Path('/Users/ben/comfy/ComfyUI_secure_nodes/backend')
for root in (BACKEND, CORE):
    sys.path.insert(0, str(root))
os.environ.setdefault('COMFY_CORE_ROOT', str(CORE))
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb, packpatch
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes.transport.host import GuestSession

COMMIT = '1c2fa94b5053aa4b0bd99cebc1747a71a8e1f028'
DTS_SHA = '4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3'
PYI_SHA = '50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78'
PAIR = PACK_DB / 'patches/comfyui-aspect-ratio-presets/x1c2fa94/comfyui-aspect-ratio-presets-x1c2fa94'


def _load(name, root):
    spec = importlib.util.spec_from_file_location(name, root / '__init__.py', submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _secure():
    return _load('_aspect_secure_test', V2)


def _old():
    module = _load('_aspect_old_test', PACK)
    sys.modules[module.EmptyLatentAspectPreset.__module__]._LATENT_DEVICE = 'cpu'
    return module


def _manifest(package):
    return {'format': FORMAT, 'frontend_permissions': [], 'web_directory': 'web',
        'runtime': manifest_declaration(V2), 'nodes': {
        key: {'module': 'nodes', 'class': cls.__name__, 'sdk_refs': True, 'permissions': [],
              'schema': encode_schema(copy.deepcopy(cls.GET_SCHEMA())), 'methods': {
                  name: False for name in ('validate_inputs', 'fingerprint_inputs', 'check_lazy_status')}}
        for key, cls in sorted(package.NODE_CLASS_MAPPINGS.items())}}


def _runtime(refs, plan):
    return _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())


async def _execute(cls, args, refs):
    plan = _sdk.ExecutionPlan(prompt_id='aspect-direct', node_id='1', node_type=cls.__name__,
        tier='sandbox', node_module=cls.__module__, inputs=args, permissions=(), method='execute')
    with _sdk.bind_runtime(refs, _sdk.InProcessCtxProvider().build(plan), _sdk.InProcessOps()):
        result = await cls.execute(**args)
    value = await refs.resolve(result.result[0])
    await refs.release(result.result[0])
    return (value, *result.result[1:])


def _compare(actual, expected, stride):
    assert actual[1:] == expected[1:]
    assert set(actual[0]) == {'samples', 'downscale_ratio_spacial'}
    assert actual[0]['downscale_ratio_spacial'] == stride
    assert actual[0]['samples'].dtype == expected[0]['samples'].dtype == torch.float32
    assert torch.equal(actual[0]['samples'], expected[0]['samples'])


def test_actual_loader_census_and_schemas():
    old, new = _old(), _secure()
    assert list(old.NODE_CLASS_MAPPINGS) == list(new.NODE_CLASS_MAPPINGS) == [
        'CAS Empty Latent Aspect Ratio Preset', 'CAS Empty Latent Aspect Ratio Axis']
    assert not hasattr(old, 'NODE_DISPLAY_NAME_MAPPINGS')
    assert (PACK / 'web/aspect_ratio_filter.js').read_text().count('app.registerExtension({') == 1
    for key, cls in new.NODE_CLASS_MAPPINGS.items():
        legacy = old.NODE_CLASS_MAPPINGS[key]
        schema = cls.GET_SCHEMA(); schema.validate()
        assert schema.node_id == key and schema.category == legacy.CATEGORY
        assert [item.io_type for item in schema.outputs] == list(legacy.RETURN_TYPES)
        assert [item.display_name for item in schema.outputs] == list(legacy.RETURN_NAMES)
        inputs = legacy.INPUT_TYPES()['required']
        assert [item.id for item in schema.inputs] == list(inputs)
        for item in schema.inputs:
            kind, *options = inputs[item.id]
            if isinstance(kind, list):
                assert item.io_type == 'COMBO' and item.options == kind
            else:
                assert item.io_type == kind
            for name, value in (options[0] if options else {}).items():
                assert getattr(item, name) == value
        assert cls.SDK_REFS is True and cls.SDK_PERMISSIONS == ()
    loaded = packdb.load_pack(SNAPSHOT, mount_name='custom_nodes.aspect_presets_test')
    assert set(loaded.node_mappings) == set(new.NODE_CLASS_MAPPINGS)
    assert not loaded.routes and not loaded.frontend_permissions
    assert loaded.web_directory == V2 / 'web'


@pytest.mark.parametrize('model', ['Krea', 'Flux.2', 'Qwen-Image', 'Flux.1', 'SDXL', 'SD15'])
def test_every_native_preset_is_sample_exact(model):
    old, new = _old(), _secure()
    async def run():
        refs = _sdk.InProcessRefResolver()
        for preset in new.EmptyLatentAspectPreset.PRESET_MAP:
            if preset.endswith(' - ' + model):
                args = dict(model=model, preset=preset, batch_size=1)
                expected = old.EmptyLatentAspectPreset().generate(**args)
                actual = await _execute(new.EmptyLatentAspectPreset, args, refs)
                _compare(actual, expected, 16 if model == 'Flux.2' else 8)
        assert not refs._table
    asyncio.run(run())


@pytest.mark.parametrize('model', ['Krea', 'Flux.2', 'Qwen-Image', 'Flux.1', 'SDXL', 'SD15', 'unknown'])
def test_all_axis_ratios_rounding_reference_fallback_and_failures(model):
    old, new = _old(), _secure()
    async def run():
        refs = _sdk.InProcessRefResolver()
        for ratio, _ in old.EmptyLatentAspectByAxis.ASPECT_CHOICES:
            for primary in (8, 16, 96, 512):
                for reference in ('Width', 'Height', 'unknown'):
                    args = dict(primary_dim=primary, reference=reference, aspect_ratio=ratio, batch_size=1, model=model)
                    try:
                        expected = old.EmptyLatentAspectByAxis().generate(**args)
                    except ValueError as error:
                        with pytest.raises(ValueError, match=str(error)):
                            await _execute(new.EmptyLatentAspectByAxis, args, refs)
                    else:
                        actual = await _execute(new.EmptyLatentAspectByAxis, args, refs)
                        _compare(actual, expected, 16 if model == 'Flux.2' else 8)
        assert not refs._table
    asyncio.run(run())


@pytest.mark.parametrize('batch', [0, 65, -1, True, 1.5, '2'])
def test_invalid_batch_fails_before_allocation(batch):
    new = _secure()
    args = dict(model='Krea', preset=next(iter(new.EmptyLatentAspectPreset.PRESET_MAP)), batch_size=batch)
    async def run():
        refs = _sdk.InProcessRefResolver()
        with pytest.raises((ValueError, TypeError)):
            await _execute(new.EmptyLatentAspectPreset, args, refs)
        assert not refs._table
    asyncio.run(run())


@pytest.mark.parametrize('dimension', [0, -8, 513, True, 512., '512', 16400, 16384])
def test_primary_dimension_type_alignment_and_size_bounds(dimension):
    new = _secure()
    async def run():
        refs = _sdk.InProcessRefResolver()
        with pytest.raises((ValueError, TypeError)):
            await _execute(new.EmptyLatentAspectByAxis,
                dict(primary_dim=dimension, reference='Width', aspect_ratio='1:1 Square', batch_size=2, model='Flux.2'), refs)
        assert not refs._table
    asyncio.run(run())


def test_unknown_presets_ratios_and_cross_model_direct_input():
    old, new = _old(), _secure()
    async def run():
        refs = _sdk.InProcessRefResolver()
        for cls, args in ((new.EmptyLatentAspectPreset, dict(model='Krea', preset='missing', batch_size=1)),
            (new.EmptyLatentAspectByAxis, dict(model='Krea', primary_dim=512, reference='Width', aspect_ratio='missing', batch_size=1))):
            with pytest.raises(ValueError, match='Unknown'):
                await _execute(cls, args, refs)
        for model in ('unknown', 'Flux.2', 'SD15'):
            args = dict(model=model, preset=next(iter(new.EmptyLatentAspectPreset.PRESET_MAP)), batch_size=2)
            _compare(await _execute(new.EmptyLatentAspectPreset, args, refs),
                     old.EmptyLatentAspectPreset().generate(**args), 16 if model == 'Flux.2' else 8)
    asyncio.run(run())


def test_maximum_batch_at_bounded_resolution():
    old, new = _old(), _secure()
    async def run():
        refs = _sdk.InProcessRefResolver()
        args = dict(model='Krea', preset=next(iter(new.EmptyLatentAspectPreset.PRESET_MAP)), batch_size=64)
        _compare(await _execute(new.EmptyLatentAspectPreset, args, refs),
                 old.EmptyLatentAspectPreset().generate(**args), 8)
    asyncio.run(run())


def test_real_zero_capability_guest_both_nodes_every_native_model():
    old, new = _old(), _secure()
    async def run():
        refs = _sdk.InProcessRefResolver()
        session = await GuestSession('aspect-ratio-presets', guest_runtime_root=V2).start()
        try:
            for model in new.EmptyLatentAspectPreset.MODELS:
                for cls, args, legacy in (
                    (new.EmptyLatentAspectPreset,
                     dict(model=model, preset=next(p for p in cls_presets(new) if p.endswith(' - ' + model)), batch_size=2),
                     old.EmptyLatentAspectPreset()),
                    (new.EmptyLatentAspectByAxis,
                     dict(primary_dim=96, reference='Width', aspect_ratio='3:2 Landscape', batch_size=2, model=model),
                     old.EmptyLatentAspectByAxis())):
                    plan = _sdk.ExecutionPlan(prompt_id='aspect-guest', node_id=model, node_type=cls.__name__,
                        tier='sandbox', node_module=cls.__module__, inputs=args, permissions=(), method='execute')
                    result = await session.execute(plan, _runtime(refs, plan), capabilities=())
                    value = await refs.resolve(result.result[0])
                    _compare((value, *result.result[1:]), legacy.generate(**args), 16 if model == 'Flux.2' else 8)
                    await refs.release(result.result[0])
            assert session.last_guest_pid not in (None, os.getpid())
            assert not refs._table
            for batch in (65, 0, True):
                plan = _sdk.ExecutionPlan(prompt_id='aspect-guest-denial', node_id='bad',
                    node_type=new.EmptyLatentAspectPreset.__name__, tier='sandbox',
                    node_module=new.EmptyLatentAspectPreset.__module__, permissions=(), method='execute',
                    inputs=dict(model='Krea', preset=next(iter(cls_presets(new))), batch_size=batch))
                with pytest.raises(Exception):
                    await session.execute(plan, _runtime(refs, plan), capabilities=())
                assert not refs._table
        finally:
            await session.kill()
    asyncio.run(run())


def cls_presets(new):
    return new.EmptyLatentAspectPreset.PRESET_MAP


def test_frontend_opaque_realm_filter_and_lifecycle():
    result = subprocess.run(['node', '--experimental-vm-modules', str(V2 / 'tests/aspect_filter_harness.mjs')],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Frontend passed:' in result.stdout


def test_frontend_against_authoritative_types(tmp_path):
    tsc = Path('/Users/ben/comfy/ComfyUI_frontend/node_modules/.bin/tsc')
    assert tsc.exists()
    stub = tmp_path / 'api.d.ts'
    canonical = (V2 / 'comfy-api.d.ts').as_posix()
    stub.write_text(f'export * from "{canonical}";\nexport declare const comfy: import("{canonical}").Comfy;\n')
    config = tmp_path / 'tsconfig.json'
    config.write_text(json.dumps({'compilerOptions': {
        'allowJs': True, 'checkJs': True, 'noEmit': True, 'target': 'ES2022',
        'module': 'ESNext', 'moduleResolution': 'Bundler', 'skipLibCheck': True,
        'paths': {'/comfy/api/v2.js': [str(stub)]}},
        'files': [str(V2 / 'web/aspect_ratio_filter.js')]}))
    result = subprocess.run([str(tsc), '-p', str(config)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_contract_manifest_license_and_authority():
    assert json.loads((V2 / 'secure-nodes.json').read_text()) == _manifest(_secure())
    assert hashlib.sha256((V2 / 'comfy-api.d.ts').read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / 'comfy-api.pyi').read_bytes()).hexdigest() == PYI_SHA
    assert (V2 / 'LICENSE').read_bytes() == (PACK / 'LICENSE').read_bytes()
    assert COMMIT in (V2 / 'SECURE_CONVERSION.md').read_text()
    source = (V2 / 'nodes.py').read_text()
    for word in ('import torch', 'import comfy\n', 'model_management', 'folder_paths', 'PromptServer',
                 'requests', 'subprocess', '_from_raw', 'open('):
        assert word not in source


def test_patch_roundtrip_byte_exact(tmp_path):
    manifest, diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix('.json').read_text()) == manifest
    assert PAIR.with_suffix('.diff').read_text() == diff
    fresh = tmp_path / 'comfyui-aspect-ratio-presets/x1c2fa94'; fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns('v2'))
    packpatch.apply(fresh, manifest, diff)
    packpatch.validate_tree(fresh / PACK.name / 'v2', V2)
    assert not list(PACK.rglob('*.pyc')) and not list(PACK.rglob('__pycache__'))
