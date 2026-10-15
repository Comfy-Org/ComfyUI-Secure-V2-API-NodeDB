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

COMMIT = 'aa109023d632974e45455190225ab46e74b29ecc'
DTS_SHA = '4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3'
PYI_SHA = '50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78'
PAIR = PACK_DB / 'patches/comfyui-text-node-with-comments/xaa10902/comfyui-text-node-with-comments-xaa10902'
CASES = [
    ('', ''), ('plain text', 'plain text'), ('a/**/b', 'ab'),
    ('a//comment\nb', 'a\nb'), ('a/*one\ntwo*/b', 'ab'),
    ('//whole line\n', '\n'), ('//one\r\n//two\r\n', '\n\n'),
    ('"//quoted" /*gone*/', '"//quoted" '), ("'/*quoted*/' //gone", "'/*quoted*/' "),
    ('a/*unterminated', 'a/*unterminated'), ('a*/b', 'a*/b'),
    ('/*outer /*inner*/ tail*/', ' tail*/'),
    ('/*x*//*y*/z', 'z'), ('a\n\n\tb', 'a\n\n\tb'),
    ('https://example.test/a', 'https:'),
    ('"https://example.test/a"', '"https://example.test/a"'),
    ('雪/*注釈*/猫 //文\n🙂', '雪猫 \n🙂'),
    ('<script>//not executed\n</script>', '<script>\n</script>'),
    ('a\x00/*gone*/b', 'a\x00b'),
    ('"escaped \\" //quoted"/*gone*/', '"escaped \\" //quoted"'),
    ("'escaped \\' /*quoted*/'//gone", "'escaped \\' /*quoted*/'"),
    ('"a\nb/*quoted*/" //gone', '"a\nb/*quoted*/" '),
    ('"unterminated //gone', '"unterminated '),
    ("'unterminated /*gone*/", "'unterminated "),
]
MALFORMED = [None, 0, 2.5, True, [], {}, b'//bytes']


def _load(name, root):
    spec = importlib.util.spec_from_file_location(name, root / '__init__.py', submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _secure():
    return _load('_comments_secure_test', V2)


def _old(tmp_path):
    root = tmp_path / 'source'
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns('v2'))
    return _load('_comments_upstream_test', root)


def _class(module):
    return module.NODE_CLASS_MAPPINGS['text-node-with-comments']


def _manifest(module):
    cls = _class(module)
    return {'format': FORMAT, 'nodes': {'text-node-with-comments': {
        'class': cls.__name__, 'module': 'nodes', 'sdk_refs': False, 'permissions': [],
        'methods': {name: False for name in ('validate_inputs', 'fingerprint_inputs', 'check_lazy_status')},
        'schema': encode_schema(copy.deepcopy(cls.GET_SCHEMA()))}}, 'runtime': manifest_declaration(V2)}


def _generated():
    rng = random.Random(530103)
    tokens = ['a', '雪', '🙂', '\n', '\r\n', '\t', '//', '/*', '*/', '"', "'", '\\', '\\"', "\\'", '<img>', '\x00']
    return [''.join(rng.choices(tokens, k=rng.randint(0, 150))) for _ in range(256)]


def test_exact_schema_actual_loader_census_and_no_frontend_routes(tmp_path):
    old, new = _old(tmp_path), _secure()
    assert list(old.NODE_CLASS_MAPPINGS) == list(new.NODE_CLASS_MAPPINGS) == ['text-node-with-comments']
    assert old.NODE_DISPLAY_NAME_MAPPINGS == new.NODE_DISPLAY_NAME_MAPPINGS
    cls, upstream = _class(new), _class(old)
    schema = cls.GET_SCHEMA(); schema.validate()
    assert schema.node_id == 'text-node-with-comments'
    assert schema.display_name == old.NODE_DISPLAY_NAME_MAPPINGS[schema.node_id]
    assert schema.category == upstream.CATEGORY
    assert [item.io_type for item in schema.outputs] == list(upstream.RETURN_TYPES)
    assert not schema.is_input_list and not schema.is_output_node
    assert [item.id for item in schema.inputs] == ['string']
    item = schema.inputs[0]
    assert item.io_type == 'STRING' and item.default == '' and item.multiline is True
    assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS == ()
    assert not hasattr(old, 'WEB_DIRECTORY') and not list(PACK.rglob('*.js'))
    loaded = packdb.load_pack(SNAPSHOT, mount_name='custom_nodes.comments_census')
    assert list(loaded.node_mappings) == ['text-node-with-comments']
    assert not loaded.routes and not loaded.frontend_permissions


@pytest.mark.parametrize('text,expected', CASES)
def test_exact_comment_quotes_escapes_unicode_and_edge_semantics(tmp_path, text, expected):
    old = _class(_old(tmp_path))().get_sanitized_string(text)
    assert old == (expected,)
    assert _class(_secure()).execute(text).result == old


def test_generated_differential_and_no_mutable_random_state(tmp_path):
    upstream, new = _class(_old(tmp_path))(), _class(_secure())
    before = random.getstate()
    for text in _generated():
        assert new.execute(text).result == upstream.get_sanitized_string(text)
    assert random.getstate() == before


@pytest.mark.parametrize('value', MALFORMED)
def test_exact_malformed_input_type_and_message(tmp_path, value):
    with pytest.raises(Exception) as expected:
        _class(_old(tmp_path))().get_sanitized_string(value)
    with pytest.raises(type(expected.value)) as actual:
        _class(_secure()).execute(value)
    assert str(expected.value) == str(actual.value)


def test_bounded_text_output_utf8_and_adversarial_regex(tmp_path):
    upstream, new = _class(_old(tmp_path))(), _class(_secure())
    for text in ('x' * 65536, '🙂' * 16384, '/*' * 32768, '"' + '\\a' * 32767, '//'+ 'a' * 65534, '\ud800'):
        assert new.execute(text).result == upstream.get_sanitized_string(text)
    for text in ('x' * 65537, '🙂' * 16385, '/*' + 'x' * 65535 + '*/'):
        with pytest.raises(ValueError, match='64 KiB text limit'):
            new.execute(text)


def test_real_zero_capability_guest_and_fresh_render_continuity(tmp_path):
    old = _class(_old(tmp_path))()
    fresh = tmp_path / 'fresh-render-pack'
    shutil.copytree(V2, fresh)
    async def run():
        refs = _sdk.InProcessRefResolver()
        for index, root in enumerate((V2, fresh)):
            # Separate module namespaces prevent Python's import cache from
            # reusing the original files in the recreated render sandbox.
            new = _class(_load(f'_comments_render_test_{index}', root))
            session = await GuestSession('text-comments', guest_runtime_root=root).start()
            try:
                async def execute(value):
                    plan = _sdk.ExecutionPlan(prompt_id='comments-guest', node_id='1', node_type=new.__name__,
                        tier='sandbox', node_module=new.__module__, inputs={'string': value},
                        input_mode='values', permissions=(), method='execute')
                    runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
                    return await session.execute(plan, runtime, capabilities=())
                for text in [text for text, _ in CASES] + _generated():
                    assert (await execute(text)).result == old.get_sanitized_string(text)
                assert (await execute('🙂'*16384)).result == ('🙂'*16384,)
                for value in MALFORMED:
                    with pytest.raises(Exception):
                        await execute(value)
                with pytest.raises(Exception, match='64 KiB text limit'):
                    await execute('x'*65537)
                assert session.last_guest_pid not in (None, os.getpid())
                assert not refs._table
            finally:
                await session.kill()
    asyncio.run(run())


def test_manifest_contract_license_and_absence_of_host_authority():
    assert json.loads((V2 / 'secure-nodes.json').read_text()) == _manifest(_secure())
    assert hashlib.sha256((V2 / 'comfy-api.d.ts').read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / 'comfy-api.pyi').read_bytes()).hexdigest() == PYI_SHA
    assert (V2 / 'LICENSE').read_bytes() == (PACK / 'LICENSE').read_bytes()
    report = (V2 / 'SECURE_CONVERSION.md').read_text()
    assert COMMIT in report and 'no durable pack state' in report
    for file in ('nodes.py', 'remove_comments.py', '__init__.py'):
        source = (V2 / file).read_text()
        for forbidden in ('import os', 'folder_paths', 'open(', 'requests', 'subprocess', '_from_raw', 'eval(', 'exec(', 'pickle'):
            assert forbidden not in source


def test_byte_exact_pristine_patch_roundtrip(tmp_path):
    manifest, diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix('.json').read_text()) == manifest
    assert PAIR.with_suffix('.diff').read_text() == diff
    root = tmp_path / 'comfyui-text-node-with-comments/xaa10902'; root.mkdir(parents=True)
    shutil.copytree(PACK, root / PACK.name, ignore=shutil.ignore_patterns('v2'))
    packpatch.apply(root, manifest, diff)
    packpatch.validate_tree(root / PACK.name / 'v2', V2)
    assert not list(PACK.rglob('*.pyc')) and not list(PACK.rglob('__pycache__'))
