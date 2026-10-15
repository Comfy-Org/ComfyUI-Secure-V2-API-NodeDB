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
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb, packpatch
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes.transport.host import GuestSession

COMMIT = '1b1fce10cdfb1be355104d4d072f9194deb3ce6f'
DTS_SHA = '4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3'
PYI_SHA = '50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78'
PAIR = PACK_DB / 'patches/comfyui-substring/x1b1fce1/comfyui-substring-x1b1fce1'
TEXTS = ['', 'abcdef', 'undefined', 'Undefined', ' undefined ',
         'é漢字🙂e\u0301👨\u200d👩\u200d👧', 'line1\nline2\t end ', '<script>alert("x")</script>\x00']
LENGTHS = [-10**18, -100, -6, -2, -1, 0, 1, 2, 6, 75, 10**18]


def _load(name, root):
    spec = importlib.util.spec_from_file_location(name, root / '__init__.py', submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _secure():
    return _load('_ned_substring_secure_test', V2)


def _old():
    return _load('_ned_substring_pristine_test', PACK)


def _manifest(module):
    cls = module.NODE_CLASS_MAPPINGS['SubstringTheory']
    return {'format': FORMAT, 'nodes': {'SubstringTheory': {
        'class': 'SubstringFunction', 'module': 'nodes', 'sdk_refs': False,
        'permissions': [], 'methods': {key: False for key in (
            'validate_inputs', 'fingerprint_inputs', 'check_lazy_status')},
        'schema': encode_schema(copy.deepcopy(cls.GET_SCHEMA())),
    }}, 'runtime': manifest_declaration(V2)}


def test_actual_entrypoint_census_and_exact_schema():
    old, new = _old(), _secure()
    assert set(old.NODE_CLASS_MAPPINGS) == set(new.NODE_CLASS_MAPPINGS) == {'SubstringTheory'}
    assert old.NODE_DISPLAY_NAME_MAPPINGS == new.NODE_DISPLAY_NAME_MAPPINGS == {'SubstringTheory': 'Substring'}
    cls = new.NODE_CLASS_MAPPINGS['SubstringTheory']
    legacy = old.NODE_CLASS_MAPPINGS['SubstringTheory']
    schema = cls.GET_SCHEMA(); schema.validate()
    assert schema.node_id == 'SubstringTheory' and schema.display_name == 'Substring'
    assert schema.category == legacy.CATEGORY and schema.is_output_node is legacy.OUTPUT_NODE
    assert [item.io_type for item in schema.outputs] == list(legacy.RETURN_TYPES)
    inputs = legacy.INPUT_TYPES()['required']
    assert [item.id for item in schema.inputs] == list(inputs)
    for item in schema.inputs:
        kind, options = inputs[item.id]
        assert item.io_type == kind and not item.optional
        for key, value in options.items():
            assert getattr(item, key) == value
    assert schema.inputs[1].min is None and schema.inputs[1].max is None
    assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS == ()
    assert not hasattr(old, 'WEB_DIRECTORY')
    assert not list(PACK.rglob('*.js')) and not list(PACK.rglob('*.mjs'))
    loaded = packdb.load_pack(SNAPSHOT, mount_name='custom_nodes.ned_substring_census')
    assert set(loaded.node_mappings) == {'SubstringTheory'}
    assert not loaded.routes and not loaded.frontend_permissions and loaded.web_directory is None


@pytest.mark.parametrize('text', TEXTS)
@pytest.mark.parametrize('length', LENGTHS)
def test_prefix_suffix_sentinel_unicode_and_ui_are_exact(text, length):
    expected = _old().NODE_CLASS_MAPPINGS['SubstringTheory']().exec(text, length)
    actual = _secure().NODE_CLASS_MAPPINGS['SubstringTheory'].execute(text, length)
    assert actual.result == expected['result']
    assert actual.ui == expected['ui']


def test_repeat_calls_randomized_inputs_are_stateless_and_differential():
    rng = random.Random(88122)
    old = _old().NODE_CLASS_MAPPINGS['SubstringTheory']()
    new = _secure().NODE_CLASS_MAPPINGS['SubstringTheory']
    for _ in range(1000):
        text = ''.join(rng.choice(' aβ漢🙂\n\t') for _ in range(rng.randrange(100)))
        length = rng.randrange(-120, 120)
        expected = old.exec(text, length)
        actual = new.execute(text, length)
        assert actual.result == expected['result'] and actual.ui == expected['ui']


@pytest.mark.parametrize('text,length', [(None, 2), (3, 2), ([], 2), ('x', None),
    ('x', True), ('x', 1.2), ('x', '2')])
def test_direct_malformed_input_fails_closed(text, length):
    with pytest.raises(TypeError):
        _secure().NODE_CLASS_MAPPINGS['SubstringTheory'].execute(text, length)


def test_text_bound_is_utf8_bytes_and_maximum_valid_input_is_preserved():
    new = _secure().NODE_CLASS_MAPPINGS['SubstringTheory']
    for text in ('a' * 1_048_576, '🙂' * (1_048_576 // 4)):
        result = new.execute(text, 10**18)
        assert result.result == (text,) and result.ui == {'text': (text,)}
        with pytest.raises(ValueError, match='1 MiB'):
            new.execute(text + 'a', 1)
    with pytest.raises(UnicodeEncodeError):
        new.execute('\ud800', 1)


def test_real_isolated_guest_preserves_results_ui_and_denies_extra_authority():
    old = _old().NODE_CLASS_MAPPINGS['SubstringTheory']()
    node = _secure().NODE_CLASS_MAPPINGS['SubstringTheory']
    async def run():
        refs = _sdk.InProcessRefResolver()
        session = await GuestSession('ned-substring', guest_runtime_root=V2).start()
        try:
            for index, (text, length) in enumerate(
                [(text, length) for text in TEXTS for length in (-100, -2, 0, 2, 100)]):
                plan = _sdk.ExecutionPlan(prompt_id=f'substring-{index}', node_id=str(index),
                    node_type=node.__name__, tier='sandbox', node_module=node.__module__,
                    inputs={'text': text, 'length': length}, input_mode='values', permissions=(), method='execute')
                runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
                result = await session.execute(plan, runtime, capabilities=())
                expected = old.exec(text, length)
                assert tuple(result.result) == expected['result']
                assert tuple(result.ui['text']) == expected['ui']['text']
            import torch
            # Attempt to substitute a host tensor into this scalar-only node.
            # Zero capabilities must not materialize it into guest raw value mode.
            image_ref = _sdk.ImageRef._wrap(await refs.create('IMAGE', torch.zeros(1, 1, 1, 3)))
            denied = _sdk.ExecutionPlan(prompt_id='denied', node_id='denied', node_type=node.__name__,
                tier='sandbox', node_module=node.__module__, inputs={'text': image_ref, 'length': 1},
                input_mode='values', permissions=(), method='execute')
            runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(denied), ops=_sdk.InProcessOps())
            with pytest.raises(Exception, match='raw'):
                await session.execute(denied, runtime, capabilities=())
            await refs.release(image_ref)
            assert session.last_guest_pid not in (None, os.getpid())
            assert not refs._table
        finally:
            await session.kill()
    asyncio.run(run())


def test_manifest_current_contracts_and_authority_boundary():
    assert json.loads((V2 / 'secure-nodes.json').read_text()) == _manifest(_secure())
    assert hashlib.sha256((V2 / 'comfy-api.d.ts').read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / 'comfy-api.pyi').read_bytes()).hexdigest() == PYI_SHA
    assert COMMIT in (V2 / 'SECURE_CONVERSION.md').read_text()
    source = (V2 / 'nodes.py').read_text()
    for forbidden in ('import os', 'import sys', 'import comfy\n', 'folder_paths',
        'PromptServer', 'requests', 'subprocess', 'open(', '_from_raw', 'eval(', 'exec('):
        assert forbidden not in source
    assert not (PACK / 'LICENSE').exists()  # Upstream metadata caveat, not a fabricated license.


def test_pristine_to_v2_byte_exact_patch_and_cache_hygiene(tmp_path):
    manifest, diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix('.json').read_text()) == manifest
    assert PAIR.with_suffix('.diff').read_text() == diff
    fresh = tmp_path / 'comfyui-substring/x1b1fce1'; fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns('v2'))
    packpatch.apply(fresh, manifest, diff)
    packpatch.validate_tree(fresh / PACK.name / 'v2', V2)
    assert not list(PACK.rglob('*.pyc')) and not list(PACK.rglob('__pycache__'))
