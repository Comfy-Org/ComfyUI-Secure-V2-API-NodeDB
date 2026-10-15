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

COMMIT = 'a3f17b0926fda30971e38d0f1c0188d9f7d8b3d7'
DTS_SHA = '4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3'
PYI_SHA = '50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78'
PAIR = PACK_DB / 'patches/comfyui-textnodes/xa3f17b0/comfyui-textnodes-xa3f17b0'
TIDY = [
    ('', ''), ('cat', 'cat'), (' ,, a , a,b ,, b, ', 'a, b'),
    ('Cat,cat,Cat', 'Cat, cat'), ('one BREAK two,BREAK,three', 'one BREAK two BREAK three'),
    ('BREAKfast,BREAK,BREAK', ' BREAK fast BREAK '), ('a\nb,c\t d', 'a\nb, c d'),
    (['cat', 'dog', 'cat', 42, None], 'cat, dog, 42, None'),
    (['', ' ', '\t', ''], ''), ([], ''), (None, ''), (False, ''), (12, ''),
    ({'cat': 1}, ''), (b'cat,dog', ''), ('雪, 猫,雪,🙂', '雪, 猫, 🙂'),
    ('<script>,alert(1),<script>', '<script>, alert(1)'), ('\t\r\n', ''),
    ('a\u00a0\u00a0b,c', 'a b, c'), ('null\x00, null\x00', 'null\x00'),
]
TEXTS = ['', 'a,b,c', ' ,,a, b, c, ', 'a,a,b,a', 'a,,b,,,c',
         'BREAK,a,BREAK,b,BREAK', 'BREAKfast,cat', 'a\nb, c\td',
         '雪,猫,🙂', '<script>, //a, /*b*/', ' \t\r\n', 'a\x00,b']
COUNTS = [0, 1, 2, 3, 100, -1, -3, -100, None, True]
INVALID_TRUNCATE = [(1, ['a']), (2, [1, None]), (1.5, 'a,b'), ('2', 'a,b'), ([], 'a,b'), ({}, 'a,b')]


def _load(name, root):
    spec = importlib.util.spec_from_file_location(name, root / '__init__.py', submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _secure():
    return _load('_textnodes_secure_test', V2)


def _old(tmp_path):
    root = tmp_path / 'source'
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns('v2'))
    return _load('_textnodes_upstream_test', root)


def _normalized(value):
    return ('',) if value == '' else value


def _manifest(module):
    return {'format': FORMAT, 'nodes': {node_id: {
        'class': cls.__name__, 'module': 'text_nodes', 'sdk_refs': False, 'permissions': [],
        'methods': {name: False for name in ('validate_inputs', 'fingerprint_inputs', 'check_lazy_status')},
        'schema': encode_schema(copy.deepcopy(cls.GET_SCHEMA()))}
        for node_id, cls in module.NODE_CLASS_MAPPINGS.items()}, 'runtime': manifest_declaration(V2)}


def _generated():
    rng = random.Random(811516)
    tokens = ['cat', 'dog', 'CAT', ',', ',,', ' ', '\t', '\n', '\r\n', 'BREAK', 'break', '雪', '🙂', '<svg>', '"', '\x00']
    return [''.join(rng.choices(tokens, k=rng.randint(0, 80))) for _ in range(256)]


def test_actual_loader_exact_census_schema_and_no_frontend_routes(tmp_path):
    old, new = _old(tmp_path), _secure()
    assert list(old.NODE_CLASS_MAPPINGS) == list(new.NODE_CLASS_MAPPINGS) == ['Tidy Tags', 'Prompt Truncate']
    assert not hasattr(old, 'NODE_DISPLAY_NAME_MAPPINGS') and not hasattr(new, 'NODE_DISPLAY_NAME_MAPPINGS')
    assert not hasattr(old, 'WEB_DIRECTORY') and not list(PACK.rglob('*.js'))
    for node_id, cls in new.NODE_CLASS_MAPPINGS.items():
        upstream = old.NODE_CLASS_MAPPINGS[node_id]
        schema = cls.GET_SCHEMA(); schema.validate()
        assert schema.node_id == schema.display_name == node_id
        assert schema.category == upstream.CATEGORY
        assert not schema.is_input_list and not schema.is_output_node
        assert [item.io_type for item in schema.outputs] == list(upstream.RETURN_TYPES)
        assert [item.display_name for item in schema.outputs] == list(upstream.RETURN_NAMES)
        required = upstream.INPUT_TYPES()['required']
        assert [item.id for item in schema.inputs] == list(required)
        for item in schema.inputs:
            assert item.io_type == required[item.id][0]
            for key, value in required[item.id][1].items():
                assert getattr(item, 'force_input' if key == 'forceInput' else key) == value
        assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS == ()
    loaded = packdb.load_pack(SNAPSHOT, mount_name='custom_nodes.textnodes_census')
    assert set(loaded.node_mappings) == {'Tidy Tags', 'Prompt Truncate'}
    assert not loaded.routes and not loaded.frontend_permissions


@pytest.mark.parametrize('text,expected', TIDY)
def test_exact_tidy_semantics_and_empty_output_normalization(tmp_path, text, expected):
    old = _old(tmp_path).NODE_CLASS_MAPPINGS['Tidy Tags']().tidy_tags(text)
    assert _normalized(old) == (expected,)
    assert _secure().NODE_CLASS_MAPPINGS['Tidy Tags'].execute(text).result == (expected,)


@pytest.mark.parametrize('text', TEXTS)
@pytest.mark.parametrize('count', COUNTS)
def test_truncate_exact_comma_slicing_whitespace_and_break(tmp_path, text, count):
    old = _old(tmp_path).NODE_CLASS_MAPPINGS['Prompt Truncate']().execute(count, text)
    assert _secure().NODE_CLASS_MAPPINGS['Prompt Truncate'].execute(count, text).result == old


@pytest.mark.parametrize('count,text', INVALID_TRUNCATE)
def test_truncate_preserves_direct_list_and_index_errors(tmp_path, count, text):
    with pytest.raises(Exception) as expected:
        _old(tmp_path).NODE_CLASS_MAPPINGS['Prompt Truncate']().execute(count, text)
    with pytest.raises(type(expected.value)) as actual:
        _secure().NODE_CLASS_MAPPINGS['Prompt Truncate'].execute(count, text)
    assert str(expected.value) == str(actual.value)


def test_generated_differential_no_global_state_and_independent_instances(tmp_path):
    old, new = _old(tmp_path).NODE_CLASS_MAPPINGS, _secure().NODE_CLASS_MAPPINGS
    before = random.getstate()
    for index, text in enumerate(_generated()):
        assert new['Tidy Tags'].execute(text).result == _normalized(old['Tidy Tags']().tidy_tags(text))
        count = COUNTS[index % len(COUNTS)]
        assert new['Prompt Truncate'].execute(count, text).result == old['Prompt Truncate']().execute(count, text)
    assert random.getstate() == before
    assert new['Tidy Tags'].execute('a,b,a').result == ('a, b',)
    assert new['Prompt Truncate'].execute(-1, 'a,b,c').result == ('a, b',)
    for value in [None, False, 0, [], {}, b'a,b']:
        assert new['Prompt Truncate'].execute(1, value).result == old['Prompt Truncate']().execute(1, value)


def test_text_list_output_bounds_and_unicode(tmp_path):
    new, old = _secure().NODE_CLASS_MAPPINGS, _old(tmp_path).NODE_CLASS_MAPPINGS
    for text in ['x'*65536, '🙂'*16384, 'a, '*18000, '\ud800']:
        for node_id in new:
            expected = old[node_id]().tidy_tags(text) if node_id == 'Tidy Tags' else old[node_id]().execute(100000, text)
            actual = new[node_id].execute(text) if node_id == 'Tidy Tags' else new[node_id].execute(100000, text)
            assert actual.result == _normalized(expected)
    assert new['Tidy Tags'].execute(['a']*4096).result == ('a',)
    assert new['Tidy Tags'].execute(['x'*65536]).result == ('x'*65536,)
    for node_id in new:
        for text, match in [('x'*65537, 'input limit'), ('🙂'*16385, 'input limit'), (['a']*4097, 'list limit')]:
            with pytest.raises(ValueError, match=match):
                new[node_id].execute(text) if node_id == 'Tidy Tags' else new[node_id].execute(1, text)
    with pytest.raises(ValueError, match='input limit'):
        new['Tidy Tags'].execute(['x'*65536, 'y'])
    module = sys.modules[new['Tidy Tags'].__module__]
    with pytest.raises(ValueError, match='output limit'):
        module._output('x'*131073)
    assert module._output('x'*131072).result == ('x'*131072,)


def test_real_zero_capability_guests_and_fresh_filesystem_render(tmp_path):
    old = _old(tmp_path).NODE_CLASS_MAPPINGS
    fresh = tmp_path / 'fresh-render-pack'; shutil.copytree(V2, fresh)
    async def run():
        refs = _sdk.InProcessRefResolver()
        for index, root in enumerate((V2, fresh)):
            new = _load(f'_textnodes_guest_{index}', root).NODE_CLASS_MAPPINGS
            session = await GuestSession('textnodes', guest_runtime_root=root).start()
            try:
                async def execute(node_id, inputs):
                    cls = new[node_id]
                    plan = _sdk.ExecutionPlan(prompt_id='textnodes-guest', node_id='1', node_type=cls.__name__,
                        tier='sandbox', node_module=cls.__module__, inputs=inputs, input_mode='values',
                        permissions=(), method='execute')
                    runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
                    return await session.execute(plan, runtime, capabilities=())
                for text, expected in TIDY:
                    if isinstance(text, bytes):
                        # Bytes are outside the public STRING/JSON wire contract.
                        with pytest.raises(TypeError, match='cannot cross the guest wire'):
                            await execute('Tidy Tags', {'string': text})
                        continue
                    assert (await execute('Tidy Tags', {'string': text})).result == (expected,)
                for number, text in enumerate(_generated()):
                    assert (await execute('Tidy Tags', {'string': text})).result == _normalized(old['Tidy Tags']().tidy_tags(text))
                    count = COUNTS[number % len(COUNTS)]
                    assert (await execute('Prompt Truncate', {'number_of_tokens': count, 'string': text})).result == old['Prompt Truncate']().execute(count, text)
                for count, text in INVALID_TRUNCATE:
                    with pytest.raises(Exception):
                        await execute('Prompt Truncate', {'number_of_tokens': count, 'string': text})
                for node_id in new:
                    args = {} if node_id == 'Tidy Tags' else {'number_of_tokens': 1}
                    assert (await execute(node_id, dict(args, string='🙂'*16384))).result == ('🙂'*16384,)
                    for text, match in [('x'*65537, 'input limit'), (['a']*4097, 'list limit')]:
                        with pytest.raises(Exception, match=match):
                            await execute(node_id, dict(args, string=text))
                assert session.last_guest_pid not in (None, os.getpid()) and not refs._table
            finally:
                await session.kill()
    asyncio.run(run())


def test_manifest_canonical_contract_mit_and_no_host_authority():
    assert json.loads((V2 / 'secure-nodes.json').read_text()) == _manifest(_secure())
    assert hashlib.sha256((V2 / 'comfy-api.d.ts').read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / 'comfy-api.pyi').read_bytes()).hexdigest() == PYI_SHA
    assert (V2 / 'LICENSE').read_bytes() == (PACK / 'LICENSE').read_bytes()
    assert COMMIT in (V2 / 'SECURE_CONVERSION.md').read_text()
    assert 'no durable pack state' in (V2 / 'SECURE_CONVERSION.md').read_text()
    for filename in ('__init__.py', 'text_nodes.py'):
        source = (V2 / filename).read_text()
        for forbidden in ('import os', 'folder_paths', 'open(', 'requests', 'subprocess', '_from_raw', 'eval(', 'exec(', 'pickle'):
            assert forbidden not in source


def test_byte_exact_pristine_to_v2_patch_roundtrip(tmp_path):
    manifest, diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix('.json').read_text()) == manifest
    assert PAIR.with_suffix('.diff').read_text() == diff
    root = tmp_path / 'comfyui-textnodes/xa3f17b0'; root.mkdir(parents=True)
    shutil.copytree(PACK, root / PACK.name, ignore=shutil.ignore_patterns('v2'))
    packpatch.apply(root, manifest, diff)
    packpatch.validate_tree(root / PACK.name / 'v2', V2)
    assert not list(PACK.rglob('*.pyc')) and not list(PACK.rglob('__pycache__'))
