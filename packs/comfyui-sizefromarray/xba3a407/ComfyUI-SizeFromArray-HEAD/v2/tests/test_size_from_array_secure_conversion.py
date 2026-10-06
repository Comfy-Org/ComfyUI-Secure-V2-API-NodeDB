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
import types

import numpy as np
import pytest

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

COMMIT = 'ba3a407af84a9446ebf0f9eb8cb38379953ad5a1'
DTS_SHA = '4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3'
PYI_SHA = '50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78'
PAIR = PACK_DB / 'patches/comfyui-sizefromarray/xba3a407/comfyui-sizefromarray-xba3a407'
TEXTS = [
    '512,512\n512,768\n768,512\n',
    '16,32', ' 16 , 32 \r\n\n 48,64\r\n',
    '16,32\n16,32\n48,64', '48,64\n16,32\n16,32',
    '-8,0\n+16,32\n64,-1', '16,32,99\n48,64,123',
    '１６,３２\n４８,６４',
]
SEEDS = [0, 1, 2, 7, 42, 1024, 2**32 + 1, 2**64 - 1]
INVALID = [('', 0), ('\n\n', 0), (' ', 0), ('# comment', 0), ('16', 0),
           ('16,', 0), ('16,32\n48', 0), ('1.5,2', 0), ('1;2', 0),
           (None, 0), ('16,32', -1), ('16,32', 1.5), ('16,32', '1')]


def _load(name, root):
    spec = importlib.util.spec_from_file_location(name, root / '__init__.py', submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _secure():
    return _load('_size_array_secure_test', V2)


def _old(tmp_path, monkeypatch):
    target = tmp_path / 'source'
    shutil.copytree(PACK, target, ignore=shutil.ignore_patterns('v2'))
    folder = types.ModuleType('folder_paths')
    folder.get_folder_paths = lambda _: [str(tmp_path)]
    monkeypatch.setitem(sys.modules, 'folder_paths', folder)
    comfy = types.ModuleType('comfy'); comfy.__path__ = []
    monkeypatch.setitem(sys.modules, 'comfy', comfy)
    monkeypatch.setitem(sys.modules, 'comfy.model_management', types.ModuleType('comfy.model_management'))
    # These imports are unused by the upstream algorithm.
    return _load('_size_array_upstream_test', target)


def _manifest(pack):
    cls = pack.SizeFromArray
    return {'format': FORMAT, 'nodes': {'SizeFromArray': {
        'class': 'SizeFromArray', 'module': 'nodes.random', 'sdk_refs': False,
        'permissions': [], 'methods': {name: False for name in (
            'validate_inputs', 'fingerprint_inputs', 'check_lazy_status')},
        'schema': encode_schema(copy.deepcopy(cls.GET_SCHEMA()))}}, 'runtime': manifest_declaration(V2)}


def test_exact_actual_census_schema_and_no_frontend_or_routes(tmp_path, monkeypatch):
    old, new = _old(tmp_path, monkeypatch), _secure()
    assert list(old.NODE_CLASS_MAPPINGS) == list(new.NODE_CLASS_MAPPINGS) == ['SizeFromArray']
    assert old.NODE_DISPLAY_NAME_MAPPINGS == new.NODE_DISPLAY_NAME_MAPPINGS
    assert not hasattr(old, 'WEB_DIRECTORY') and not list(PACK.rglob('*.js'))
    cls = new.SizeFromArray
    schema = cls.GET_SCHEMA(); schema.validate()
    assert schema.node_id == 'SizeFromArray'
    assert schema.display_name == old.NODE_DISPLAY_NAME_MAPPINGS['SizeFromArray']
    assert schema.category == old.SizeFromArray.CATEGORY
    assert schema.description == old.SizeFromArray.DESCRIPTION
    assert [x.io_type for x in schema.outputs] == list(old.SizeFromArray.RETURN_TYPES)
    assert [x.display_name for x in schema.outputs] == list(old.SizeFromArray.RETURN_NAMES)
    inputs = old.SizeFromArray.INPUT_TYPES()['required']
    assert [x.id for x in schema.inputs] == list(inputs)
    for item in schema.inputs:
        assert item.io_type == inputs[item.id][0]
        for key, value in inputs[item.id][1].items():
            assert getattr(item, key) == value
    assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS == ()
    loaded = packdb.load_pack(SNAPSHOT, mount_name='custom_nodes.size_array_census')
    assert set(loaded.node_mappings) == {'SizeFromArray'}
    assert not loaded.routes and not loaded.frontend_permissions


@pytest.mark.parametrize('sizes', TEXTS)
@pytest.mark.parametrize('seed', SEEDS)
def test_seeded_selection_exact_upstream(tmp_path, monkeypatch, sizes, seed):
    expected = _old(tmp_path, monkeypatch).SizeFromArray().get_size(sizes, seed)
    actual = _secure().SizeFromArray.execute(sizes, seed).result
    assert actual == expected
    assert all(type(x) is int for x in actual)


@pytest.mark.parametrize('sizes,seed', INVALID)
def test_malformed_input_error_type_and_message_are_exact(tmp_path, monkeypatch, sizes, seed):
    old, new = _old(tmp_path, monkeypatch), _secure()
    with pytest.raises(Exception) as expected:
        old.SizeFromArray().get_size(sizes, seed)
    with pytest.raises(type(expected.value)) as actual:
        new.SizeFromArray.execute(sizes, seed)
    assert str(actual.value) == str(expected.value)


def test_independent_calls_and_no_global_numpy_or_python_rng_mutation():
    node = _secure().SizeFromArray
    python_state = random.getstate()
    numpy_state = copy.deepcopy(np.random.get_state())
    expected = node.execute(TEXTS[0], 812).result
    for seed in range(128):
        node.execute(TEXTS[0], seed)
    assert node.execute(TEXTS[0], 812).result == expected
    assert python_state == random.getstate()
    current = np.random.get_state()
    assert numpy_state[0] == current[0]
    assert np.array_equal(numpy_state[1], current[1])
    assert numpy_state[2:] == current[2:]


def test_text_and_rows_resource_bounds_and_exact_max_rows():
    node = _secure().SizeFromArray
    with pytest.raises(ValueError, match='text limit'):
        node.execute('1,2\n' * 300000, 0)
    with pytest.raises(ValueError, match='row limit'):
        node.execute('1,2\n' * 4097, 0)
    assert node.execute('16,32\n' * 4096, 0).result == (16, 32)


def test_real_zero_capability_guest_seeded_values_errors_and_bounds(tmp_path, monkeypatch):
    old, new = _old(tmp_path, monkeypatch), _secure()
    async def run():
        refs = _sdk.InProcessRefResolver()
        session = await GuestSession('size-from-array', guest_runtime_root=V2).start()
        try:
            async def execute(sizes, seed):
                plan = _sdk.ExecutionPlan(prompt_id='size-array-guest', node_id='1',
                    node_type='SizeFromArray', tier='sandbox', node_module=new.SizeFromArray.__module__,
                    inputs={'sizes': sizes, 'seed': seed}, input_mode='values', permissions=(), method='execute')
                runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
                return await session.execute(plan, runtime, capabilities=())
            for sizes in TEXTS:
                for seed in SEEDS:
                    result = await execute(sizes, seed)
                    expected = old.SizeFromArray().get_size(sizes, seed)
                    assert result.result == tuple(int(x) for x in expected)
            for sizes, seed in INVALID:
                with pytest.raises(Exception):
                    await execute(sizes, seed)
            # Oversize strings are denied by the wire before node execution.
            for sizes, match in (('16,32\n' * 4097, 'row limit'), ('1,2\n' * 300000, 'MAX_FRAME')):
                with pytest.raises(Exception, match=match):
                    await execute(sizes, 0)
            assert session.last_guest_pid not in (None, os.getpid())
            assert not refs._table
        finally:
            await session.kill()
    asyncio.run(run())


def test_manifest_canonical_contract_license_and_authority():
    assert json.loads((V2 / 'secure-nodes.json').read_text()) == _manifest(_secure())
    assert hashlib.sha256((V2 / 'comfy-api.d.ts').read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / 'comfy-api.pyi').read_bytes()).hexdigest() == PYI_SHA
    assert (V2 / 'LICENSE').read_bytes() == (PACK / 'LICENSE').read_bytes()
    assert COMMIT in (V2 / 'SECURE_CONVERSION.md').read_text()
    source = (V2 / 'nodes/random.py').read_text()
    for forbidden in ('import os', 'import torch', 'import comfy\n', 'folder_paths', 'model_management',
                      'open(', 'requests', 'subprocess', '_from_raw', 'random.seed(', 'np.random.seed('):
        assert forbidden not in source


def test_byte_exact_pristine_patch_roundtrip(tmp_path):
    manifest, diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix('.json').read_text()) == manifest
    assert PAIR.with_suffix('.diff').read_text() == diff
    fresh = tmp_path / 'comfyui-sizefromarray/xba3a407'; fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns('v2'))
    packpatch.apply(fresh, manifest, diff)
    packpatch.validate_tree(fresh / PACK.name / 'v2', V2)
    assert not list(PACK.rglob('*.pyc')) and not list(PACK.rglob('__pycache__'))
