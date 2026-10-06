from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
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
sys.path.append('/Users/ben/comfy/ComfyUI')
os.environ.setdefault('COMFY_CORE_ROOT', str(CORE))

from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb, packpatch
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes.transport.host import GuestSession

COMMIT = '93266a0efcf093cbf197f89ff51a2892a0f4cc1b'
DTS_SHA = '4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3'
PYI_SHA = '50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78'
PAIR = PACK_DB / 'patches/film-grain-ltxv/x93266a0/film-grain-ltxv-x93266a0'


def _load(name, root):
    spec = importlib.util.spec_from_file_location(
        name, root / '__init__.py', submodule_search_locations=[str(root)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return package


def _secure():
    return _load('_film_grain_secure_test', V2)


def _pristine(tmp_path, monkeypatch):
    root = tmp_path / 'pristine'
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns('v2'))
    import comfy.model_management as mm
    monkeypatch.setattr(mm, 'get_torch_device', lambda: torch.device('cpu'))
    monkeypatch.setattr(mm, 'intermediate_device', lambda: torch.device('cpu'))
    return _load('_film_grain_pristine_test', root)


def _manifest(package):
    cls = package.NODE_CLASS_MAPPINGS['FilmGrainLTXV']
    return {'format': FORMAT, 'nodes': {'FilmGrainLTXV': {
        'module': 'nodes', 'class': 'FilmGrainLTXV', 'sdk_refs': False,
        'permissions': ['raw'], 'methods': {name: False for name in (
            'validate_inputs', 'fingerprint_inputs', 'check_lazy_status')},
        'schema': encode_schema(copy.deepcopy(cls.GET_SCHEMA())),
    }}, 'runtime': manifest_declaration(V2)}


def test_actual_registration_census_and_exact_schema(tmp_path, monkeypatch):
    old, new = _pristine(tmp_path, monkeypatch), _secure()
    assert set(old.NODE_CLASS_MAPPINGS) == set(new.NODE_CLASS_MAPPINGS) == {'FilmGrainLTXV'}
    assert old.NODE_DISPLAY_NAME_MAPPINGS == new.NODE_DISPLAY_NAME_MAPPINGS
    legacy = old.NODE_CLASS_MAPPINGS['FilmGrainLTXV']
    schema = new.FilmGrainLTXV.GET_SCHEMA()
    schema.validate()
    assert schema.node_id == 'FilmGrainLTXV'
    assert schema.display_name == 'Film Grain LTXV'
    assert schema.category == legacy.CATEGORY
    assert schema.description == legacy.DESCRIPTION
    assert [x.io_type for x in schema.outputs] == list(legacy.RETURN_TYPES)
    inputs = legacy.INPUT_TYPES()['required']
    assert [x.id for x in schema.inputs] == list(inputs)
    for item in schema.inputs:
        assert item.io_type == inputs[item.id][0]
        for key, value in (inputs[item.id][1] if len(inputs[item.id]) > 1 else {}).items():
            assert getattr(item, key) == value
    assert not hasattr(old, 'WEB_DIRECTORY')
    assert not list(PACK.glob('*.js'))
    loaded = packdb.load_pack(SNAPSHOT, mount_name='custom_nodes.film_grain_census')
    assert set(loaded.node_mappings) == {'FilmGrainLTXV'}
    assert not loaded.routes and not loaded.frontend_permissions
    assert COMMIT in (V2 / 'SECURE_CONVERSION.md').read_text()


@pytest.mark.parametrize('dtype', [torch.float16, torch.float32, torch.float64])
@pytest.mark.parametrize('batch,intensity,saturation', [
    (1, 0., 0.), (3, .17, 0.), (2, .3, .5), (3, 1., 1.)])
def test_pixel_and_rng_exact_upstream_differential(tmp_path, monkeypatch, dtype,
                                                  batch, intensity, saturation):
    old = _pristine(tmp_path, monkeypatch).NODE_CLASS_MAPPINGS['FilmGrainLTXV']()
    new = _secure().FilmGrainLTXV
    image = torch.linspace(-.2, 1.2, batch * 7 * 11 * 3, dtype=dtype).reshape(batch, 7, 11, 3)
    image = image.transpose(1, 2)  # Noncontiguous layouts must remain correct.
    saved = image.clone()
    with torch.random.fork_rng():
        torch.manual_seed(817)
        expected = old.add_film_grain(image.clone(), intensity, saturation)[0]
        expected_rng = torch.random.get_rng_state().clone()
        torch.manual_seed(817)
        actual = new.execute(image, intensity, saturation).result[0]
        assert torch.equal(torch.random.get_rng_state(), expected_rng)
    assert torch.equal(actual, expected)
    assert actual.dtype == image.dtype and actual.shape == image.shape
    assert torch.equal(image, saved)
    assert actual.data_ptr() != image.data_ptr()


@pytest.mark.parametrize('saturation', [0., .5, 1.])
def test_fixed_noise_channel_weights_and_one_draw_per_frame(monkeypatch, saturation):
    calls = []
    def noise(shape, *, device, out):
        calls.append(shape)
        out[..., 0] = .2 * len(calls)
        out[..., 1] = -.1 * len(calls)
        out[..., 2] = .3 * len(calls)
        return out
    monkeypatch.setattr(torch, 'randn', noise)
    image = torch.full((2, 4, 5, 3), .5)
    actual = _secure().FilmGrainLTXV.execute(image, .1, saturation).result[0]
    assert len(calls) == 2
    for index in range(2):
        grain = torch.tensor([.4, -.1, .9]) * (index + 1)
        grain = grain * saturation + grain[1] * (1 - saturation)
        expected = (.5 + .1 * grain).clamp(0, 1)
        torch.testing.assert_close(actual[index], expected.expand(4, 5, 3), rtol=0, atol=1e-7)


@pytest.mark.parametrize('key,value', [(key, value) for key in ('grain_intensity', 'saturation')
    for value in (True, None, '0.1', float('nan'), float('inf'), -.1, 1.1)])
def test_invalid_controls_fail_closed(key, value):
    args = {'grain_intensity': .1, 'saturation': .5, key: value}
    with pytest.raises((ValueError, TypeError)):
        _secure().FilmGrainLTXV.execute(torch.zeros(1, 2, 2, 3), **args)


@pytest.mark.parametrize('image', [None, torch.zeros(1, 2, 2, 3, dtype=torch.int32),
    torch.zeros(1, 2, 2), torch.zeros(1, 2, 2, 4), torch.zeros(0, 2, 2, 3),
    torch.zeros(65, 1, 1, 3), torch.full((1, 1, 1, 3), float('nan')),
    torch.full((1, 1, 1, 3), float('inf'))])
def test_invalid_images_fail_closed(image):
    with pytest.raises((TypeError, ValueError)):
        _secure().FilmGrainLTXV.execute(image, .1, .5)


def test_element_limit_is_checked_before_rng_or_clone(monkeypatch):
    new = _secure()
    monkeypatch.setattr(sys.modules[new.FilmGrainLTXV.__module__], 'MAX_ELEMENTS', 10)
    with pytest.raises(ValueError, match='bounded'):
        new.FilmGrainLTXV.execute(torch.zeros(1, 2, 2, 3), .1, .5)


def test_real_guest_deterministic_and_stochastic_behavior_and_raw_denial():
    node = _secure().FilmGrainLTXV
    async def run():
        refs = _sdk.InProcessRefResolver()
        session = await GuestSession('film-grain-ltxv', guest_runtime_root=V2).start()
        try:
            for index, (intensity, saturation) in enumerate(((0., 1.), (.03, 0.), (.03, 1.))):
                image = (torch.linspace(-.2, 1.2, 2 * 12 * 17 * 3).reshape(2, 12, 17, 3)
                         if intensity == 0 else torch.full((2, 32, 40, 3), .5))
                saved = image.clone()
                ref = _sdk.ImageRef._wrap(await refs.create('IMAGE', image))
                plan = _sdk.ExecutionPlan(prompt_id=f'grain-{index}', node_id=str(index),
                    node_type='FilmGrainLTXV', tier='sandbox', node_module=node.__module__,
                    inputs={'images': ref, 'grain_intensity': intensity, 'saturation': saturation},
                    input_mode='values', permissions=('raw',), method='execute')
                runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan),
                                       ops=_sdk.InProcessOps())
                result = await session.execute(plan, runtime, capabilities=('raw',))
                actual = await refs.resolve(result.result[0])
                assert actual.shape == image.shape and actual.dtype == image.dtype
                assert torch.equal(image, saved)
                assert torch.isfinite(actual).all() and actual.min() >= 0 and actual.max() <= 1
                if intensity == 0:
                    assert torch.equal(actual, image.clamp(0, 1))
                    with pytest.raises(Exception, match='raw'):
                        await session.execute(plan, runtime, capabilities=())
                else:
                    delta = actual - .5
                    assert not torch.equal(actual[0], actual[1])
                    if saturation == 0:
                        assert torch.equal(delta[..., 0], delta[..., 1])
                        assert torch.equal(delta[..., 1], delta[..., 2])
                    else:
                        variance = delta.flatten(0, 2).var(dim=0)
                        assert 3 < variance[0] / variance[1] < 5
                        assert 7 < variance[2] / variance[1] < 11
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()
    asyncio.run(run())


def test_manifest_canonical_stubs_license_and_authority_boundary():
    assert json.loads((V2 / 'secure-nodes.json').read_text()) == _manifest(_secure())
    assert hashlib.sha256((V2 / 'comfy-api.d.ts').read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / 'comfy-api.pyi').read_bytes()).hexdigest() == PYI_SHA
    assert (V2 / 'LICENSE').read_bytes() == (PACK / 'LICENSE').read_bytes()
    source = (V2 / 'nodes.py').read_text()
    for forbidden in ('import comfy\n', 'model_management', 'folder_paths', 'PromptServer',
                      'requests', 'subprocess', 'open(', '_from_raw', 'manual_seed',
                      'set_rng_state', 'os.', 'sys.', 'urllib', 'socket'):
        assert forbidden not in source


def test_byte_exact_pristine_patch_roundtrip(tmp_path):
    manifest, diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix('.json').read_text()) == manifest
    assert PAIR.with_suffix('.diff').read_text() == diff
    fresh = tmp_path / 'film-grain-ltxv/x93266a0'
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns('v2'))
    packpatch.apply(fresh, manifest, diff)
    packpatch.validate_tree(fresh / PACK.name / 'v2', V2)
    assert not list(PACK.rglob('*.pyc'))
    assert not list(PACK.rglob('__pycache__'))
