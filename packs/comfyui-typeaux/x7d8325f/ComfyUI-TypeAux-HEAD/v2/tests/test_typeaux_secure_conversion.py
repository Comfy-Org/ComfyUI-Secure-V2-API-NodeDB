from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import re
import shutil
import signal
import subprocess
import sys
import time

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
from comfy_secure_nodes.transport import host

COMMIT = '7d8325f0c2e83ea4b6e85b2a3f8e6d8cbe83680c'
DTS_SHA = '4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3'
PYI_SHA = '50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78'
PAIR = PACK_DB / 'patches/comfyui-typeaux/x7d8325f/comfyui-typeaux-x7d8325f'
PRISTINE_SHA = {
    'README.md': 'bead71c0bd48f4cbb45c34bec068ddd2e8c5c81adfc985193f625d1cec9495a6',
    '__init__.py': '64b6078376400c2612c4dc33104c1c4a2ff75c9ae4e0edb23087c94682ae273a',
    'nodes/PromptTextNode.py': 'f2e0555fd1840fd5407ede12d383b53df369a02ace20450fa9beede7253bf832',
    'nodes/StringReplace.py': '1af6e8350bd1b54d2cd337c0bc822e78701303861fa6e76ebd5773bd3bfd28c2',
    'pyproject.toml': '0624b0e524f1200718c9ffd8368e2ede62256319ab668c532cb4b5b3fbac2e0d',
}
PROMPTS = ['', 'hello', 'é漢🙂e\u0301', 'a\n\t b', '<script>x</script>\x00', 'undefined']
REPLACEMENTS = [
    ('<think>a\nb</think>\n\nanswer', r'\<think\>.*\<\/think\>\n+', '', 'regex'),
    ('<think>a</think>\nx<think>b</think>\nanswer', r'\<think\>.*\<\/think\>\n+', '', 'regex'),
    ('ab ab', '(a)(b)', r'\2-\1-\g<0>', 'regex'),
    ('one 12 two 34', r'(?P<digits>\d+)', r'<\g<digits>>', 'regex'),
    ('abc', '(a)|(b)', r'\1:\2', 'regex'),
    ('A\na', '(?i:a)', 'z', 'regex'),
    ('abc abc', r'(?<=a)b(?=c)', 'B', 'regex'),
    ('aab aa', r'(a)\1', 'X', 'regex'),
    ('abxd', 'x*', '-', 'regex'),
    ('ab', '.*?', '-', 'regex'),
    ('', '', 'x', 'regex'),
    ('🙂漢', '', '_', 'regex'),
    ('a\nb', '.', 'x', 'regex'),
    ('a', '(a)', r'\\\1\n\t', 'regex'),
    ('[x]+ [x]+', '[x]+', r'\1', 'text'),
    ('a\nb\na', 'a', '🙂', 'text'),
    ('abc', '', '-', 'text'),
    ('', '', '🙂', 'text'),
    ('a', 'absent', '', 'text'),
    ('漢🙂漢', '漢', 'é', 'text'),
]


def _load(name, root):
    spec = importlib.util.spec_from_file_location(name, root / '__init__.py',
                                                submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _secure():
    return _load('_ned_typeaux_secure_test', V2)


def _old():
    return _load('_ned_typeaux_pristine_test', PACK)


def _manifest(module):
    return {'format': FORMAT, 'nodes': {node_id: {
        'class': cls.__name__, 'module': cls.__module__.removeprefix(module.__name__ + '.'),
        'sdk_refs': False, 'permissions': [],
        'methods': {key: False for key in ('validate_inputs', 'fingerprint_inputs', 'check_lazy_status')},
        'schema': encode_schema(copy.deepcopy(cls.GET_SCHEMA())),
    } for node_id, cls in module.NODE_CLASS_MAPPINGS.items()}, 'runtime': manifest_declaration(V2)}


def _plan(node, inputs, prompt='typeaux', node_id='1'):
    return _sdk.ExecutionPlan(prompt_id=prompt, node_id=node_id, node_type=node.__name__,
        tier='sandbox', node_module=node.__module__, inputs=inputs, input_mode='values',
        permissions=(), method='execute')


async def _execute(session, node, inputs, refs=None, tenant='ned-test'):
    refs = refs or _sdk.InProcessRefResolver()
    plan = _plan(node, inputs)
    runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
    return await session.execute(plan, runtime, capabilities=(), tenant=tenant)


def test_actual_entrypoint_exact_schema_census_and_manifest_loader():
    old, new = _old(), _secure()
    assert set(old.NODE_CLASS_MAPPINGS) == set(new.NODE_CLASS_MAPPINGS) == {
        'PromptTextNodeFunction', 'StringReplaceFunction'}
    for node_id, cls in new.NODE_CLASS_MAPPINGS.items():
        legacy = old.NODE_CLASS_MAPPINGS[node_id]
        schema = cls.GET_SCHEMA(); schema.validate()
        assert schema.node_id == node_id and schema.display_name is None
        assert schema.category == legacy.CATEGORY and not schema.is_output_node
        assert [item.io_type for item in schema.outputs] == list(legacy.RETURN_TYPES)
        expected = legacy.INPUT_TYPES()['required']
        assert [item.id for item in schema.inputs] == list(expected)
        for item in schema.inputs:
            kind, options = expected[item.id]
            assert not item.optional
            if isinstance(kind, list):
                assert item.options == kind and item.io_type == 'COMBO'
            else:
                assert item.io_type == kind
            actual = item.as_dict()
            for key, value in options.items():
                assert actual[key] == value
        assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS == ()
    assert not hasattr(old, 'NODE_DISPLAY_NAME_MAPPINGS') and not hasattr(new, 'NODE_DISPLAY_NAME_MAPPINGS')
    assert not hasattr(old, 'WEB_DIRECTORY') and not list(PACK.rglob('*.js'))
    loaded = packdb.load_pack(SNAPSHOT, mount_name='custom_nodes.ned_typeaux_census')
    assert set(loaded.node_mappings) == set(old.NODE_CLASS_MAPPINGS)
    assert not loaded.routes and not loaded.frontend_permissions and loaded.web_directory is None
    for node_id, proxy in loaded.node_mappings.items():
        assert proxy.INPUT_TYPES() == new.NODE_CLASS_MAPPINGS[node_id].INPUT_TYPES()
        normalized = copy.deepcopy(proxy.INPUT_TYPES())
        for input_id, (kind, options) in normalized['required'].items():
            if kind == 'COMBO':
                assert options.pop('multiselect') is False
                normalized['required'][input_id] = (options.pop('options'), options)
        assert normalized == old.NODE_CLASS_MAPPINGS[node_id].INPUT_TYPES()
        assert proxy.RETURN_TYPES == list(old.NODE_CLASS_MAPPINGS[node_id].RETURN_TYPES)


@pytest.mark.parametrize('text', PROMPTS)
def test_prompt_text_passthrough_differential(text):
    expected = _old().NODE_CLASS_MAPPINGS['PromptTextNodeFunction']().encode(text)
    result = _secure().NODE_CLASS_MAPPINGS['PromptTextNodeFunction'].execute(text)
    assert result.result == expected


@pytest.mark.parametrize('args', REPLACEMENTS)
def test_native_replacement_semantics_differential(args):
    expected = _old().NODE_CLASS_MAPPINGS['StringReplaceFunction']().encode(*args)
    result = _secure().NODE_CLASS_MAPPINGS['StringReplaceFunction'].execute(*args)
    assert result.result == expected


def test_randomized_literal_regex_zero_width_and_backreference_differentials():
    rng = random.Random(733165)
    old = _old().NODE_CLASS_MAPPINGS['StringReplaceFunction']()
    new = _secure().NODE_CLASS_MAPPINGS['StringReplaceFunction']
    patterns = [('', '_'), (r'(a)?b', r'\1X'), (r'(?P<x>🙂|漢)', r'[\g<x>]'),
                (r'.*?', 'z'), (r'\s+', ''), (r'(?=a)', '_'), (r'(a)(b)', r'\2\1')]
    for _ in range(1000):
        text = ''.join(rng.choice('ab漢🙂 \n\t') for _ in range(rng.randrange(80)))
        match, value = rng.choice(patterns)
        assert new.execute(text, match, value, 'regex').result == old.encode(text, match, value, 'regex')
        match = rng.choice(['', 'a', '漢', '🙂', 'ab', '[x]'])
        value = rng.choice(['', 'z', '🙂', r'\1'])
        assert new.execute(text, match, value, 'text').result == old.encode(text, match, value, 'text')


@pytest.mark.parametrize('text,match,value', [
    ('a', '[', ''), ('a', '(?P<x>a)(?P<x>b)', ''), ('a', 'a{2,1}', ''),
    ('nomatch', '(a)', r'\2'), ('nomatch', '(a)', r'\g<absent>'),
    ('nomatch', '(a)', r'\q'), ('a', '(a)', '\\'), ('', '(a)', r'\g<-1>'),
])
def test_invalid_regex_and_replacement_errors_are_not_swallowed(text, match, value):
    old = _old().NODE_CLASS_MAPPINGS['StringReplaceFunction']()
    new = _secure().NODE_CLASS_MAPPINGS['StringReplaceFunction']
    with pytest.raises((re.error, IndexError)) as expected:
        old.encode(text, match, value, 'regex')
    with pytest.raises(type(expected.value)) as actual:
        new.execute(text, match, value, 'regex')
    assert str(actual.value) == str(expected.value)


@pytest.mark.parametrize('field', ['text', 'match', 'value'])
@pytest.mark.parametrize('value', [None, 1, True, [], {}])
def test_malformed_scalar_inputs_are_rejected(field, value):
    inputs = {'text': 'a', 'match': 'a', 'value': '', 'match_type': 'text'}
    inputs[field] = value
    with pytest.raises(TypeError):
        _secure().NODE_CLASS_MAPPINGS['StringReplaceFunction'].execute(**inputs)


def test_closed_match_type_and_utf8_resource_bounds():
    new = _secure().NODE_CLASS_MAPPINGS['StringReplaceFunction']
    for kind in ('other', '', None, True, 1):
        with pytest.raises(ValueError):
            new.execute('a', 'a', 'b', kind)
    for field, bound in [('text', 65_536), ('match', 8_192), ('value', 1_024)]:
        inputs = {'text': '', 'match': '', 'value': '', 'match_type': 'text'}
        inputs[field] = '🙂' * (bound // 4)
        expected = _old().NODE_CLASS_MAPPINGS['StringReplaceFunction']().encode(**inputs)
        assert new.execute(**inputs).result == expected
        inputs[field] += 'a'
        with pytest.raises(ValueError, match='UTF-8 limit'):
            new.execute(**inputs)
    prompt = _secure().NODE_CLASS_MAPPINGS['PromptTextNodeFunction']
    text = '🙂' * (131_072 // 4)
    assert prompt.execute(text).result == (text,)
    with pytest.raises(ValueError, match='128 KiB'):
        prompt.execute(text + 'a')
    with pytest.raises(TypeError):
        prompt.execute(None)
    with pytest.raises(UnicodeEncodeError):
        new.execute('\ud800', '', '', 'text')


@pytest.mark.parametrize('kind', ['text', 'regex'])
def test_output_expansion_is_bounded_and_exact_at_limit(kind):
    new = _secure().NODE_CLASS_MAPPINGS['StringReplaceFunction']
    text = 'a' * 128
    assert new.execute(text, 'a', 'b' * 1024, kind).result == ('b' * 131_072,)
    for text, match, value in [('a' * 129, 'a', 'b' * 1024),
                               ('a' * 128 + 'x', 'a', 'b' * 1024),
                               ('a' * 65_536, '', 'b' * 1024)]:
        with pytest.raises(ValueError, match='output exceeds'):
            new.execute(text, match, value, kind)
    if kind == 'regex':
        # A single backreference expansion can exceed the budget, too.
        with pytest.raises(ValueError, match='output exceeds'):
            new.execute('a' * 65_536, '(.*)', r'\1' * 32, kind)


def test_real_guest_both_nodes_native_syntax_and_zero_capability_denial():
    module = _secure()
    async def run():
        session = await host.GuestSession('ned-typeaux-behavior', guest_runtime_root=V2).start()
        refs = _sdk.InProcessRefResolver()
        try:
            assert session.sandbox_kind != 'none'
            for text in PROMPTS:
                result = await _execute(session, module.NODE_CLASS_MAPPINGS['PromptTextNodeFunction'], {'text': text})
                assert tuple(result.result) == (text,)
            node = module.NODE_CLASS_MAPPINGS['StringReplaceFunction']
            old = _old().NODE_CLASS_MAPPINGS['StringReplaceFunction']()
            for args in REPLACEMENTS:
                inputs = dict(zip(('text', 'match', 'value', 'match_type'), args, strict=True))
                result = await _execute(session, node, inputs)
                assert tuple(result.result) == old.encode(*args)
            # Worst-case JSON escaping (six wire bytes per NUL) must still fit
            # the real default 1 MiB frame, in both directions at the limit.
            controls = '\x00' * 131_072
            result = await _execute(session, module.NODE_CLASS_MAPPINGS['PromptTextNodeFunction'], {'text': controls})
            assert tuple(result.result) == (controls,)
            for kind in ('text', 'regex'):
                result = await _execute(session, node, {'text': 'a' * 128, 'match': 'a',
                    'value': '\x00' * 1024, 'match_type': kind})
                assert tuple(result.result) == (controls,)
                with pytest.raises(Exception, match='output exceeds'):
                    await _execute(session, node, {'text': 'a' * 129, 'match': 'a',
                        'value': '\x00' * 1024, 'match_type': kind})
            import torch
            image = _sdk.ImageRef._wrap(await refs.create('IMAGE', torch.zeros(1, 1, 1, 3)))
            with pytest.raises(Exception, match='raw'):
                await _execute(session, node, {'text': image, 'match': 'a', 'value': '', 'match_type': 'text'}, refs)
            await refs.release(image)
            assert session.last_guest_pid not in (None, os.getpid()) and not refs._table
        finally:
            await session.kill()
    asyncio.run(run())


def test_pathological_regex_deadline_kills_process_reclaims_resources_and_restarts(monkeypatch):
    node = _secure().NODE_CLASS_MAPPINGS['StringReplaceFunction']
    async def run():
        session = await host.GuestSession('ned-typeaux-deadline', guest_runtime_root=V2).start()
        try:
            benign = {'text': 'aba', 'match': 'b', 'value': '', 'match_type': 'regex'}
            assert tuple((await _execute(session, node, benign)).result) == ('aa',)
            pid, process = session.last_guest_pid, session._proc
            socket_dir, temp_dir = Path(session._sockdir), Path(session._guest_tmp)
            assert pid == process.pid and session.sandbox_kind != 'none'
            reclaimed = []
            session._held.add_ref(pid, 'ned-owned-deadline-marker', lambda value: reclaimed.append(value) or True)
            with monkeypatch.context() as patch:
                patch.setattr(host, 'EXEC_TIMEOUT_S', 1.0)
                started = time.monotonic()
                with pytest.raises(host.GuestDied, match='timed out mid-execute'):
                    await _execute(session, node, {'text': 'a' * 40 + '!', 'match': '(a+)+$',
                                                  'value': '', 'match_type': 'regex'})
                elapsed = time.monotonic() - started
            assert 0.9 <= elapsed < 5.0
            assert process.returncode == -signal.SIGKILL
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)
            assert not session.alive() and not socket_dir.exists() and not temp_dir.exists()
            assert session._sockdir is None and session._guest_tmp is None
            assert session._runtime is None and not session._caps and not session._closure_entries
            assert session._held.held_by(pid) == 0
            assert reclaimed == ['ned-owned-deadline-marker'] and session.leaked_segments_reclaimed >= 1
            await session.start()
            assert tuple((await _execute(session, node, benign)).result) == ('aa',)
            assert session.last_guest_pid != pid
        finally:
            await session.kill()
    asyncio.run(run())


def test_fresh_guests_and_tenants_have_no_cross_render_mutable_state(tmp_path):
    async def run():
        pids = []
        for index, tenant in enumerate(('user-a', 'user-b', 'user-a')):
            fresh = tmp_path / str(index)
            shutil.copytree(V2, fresh)
            module = _load(f'_ned_typeaux_fresh_{index}', fresh)
            session = await host.GuestSession(f'ned-typeaux-fresh-{index}', guest_runtime_root=fresh).start()
            try:
                node = module.NODE_CLASS_MAPPINGS['StringReplaceFunction']
                inputs = {'text': '<think>private\ntext</think>\nanswer',
                          'match': r'\<think\>.*\<\/think\>\n+', 'value': '', 'match_type': 'regex'}
                assert tuple((await _execute(session, node, inputs, tenant=tenant)).result) == ('answer',)
                pids.append(session.last_guest_pid)
            finally:
                await session.kill()
        assert len(set(pids)) == 3
    asyncio.run(run())


def test_manifest_current_contracts_pristine_identity_and_authority_boundary():
    assert json.loads((V2 / 'secure-nodes.json').read_text()) == _manifest(_secure())
    assert hashlib.sha256((V2 / 'comfy-api.d.ts').read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / 'comfy-api.pyi').read_bytes()).hexdigest() == PYI_SHA
    assert COMMIT in (V2 / 'SECURE_CONVERSION.md').read_text()
    actual_paths = {path.relative_to(PACK).as_posix() for path in PACK.rglob('*')
                    if path.is_file() and not path.is_relative_to(V2)}
    assert actual_paths == set(PRISTINE_SHA)
    for path, expected_sha in PRISTINE_SHA.items():
        assert hashlib.sha256((PACK / path).read_bytes()).hexdigest() == expected_sha
    # Original upstream tracked files are byte-identical to our captured source.
    upstream = Path('/tmp/ned-pack-screen.fYlox7/typeaux')
    if upstream.is_dir():
        assert subprocess.check_output(['git', '-C', str(upstream), 'rev-parse', 'HEAD'], text=True).strip() == COMMIT
        tracked = subprocess.check_output(['git', '-C', str(upstream), 'ls-files', '-z']).split(b'\0')
        for path in filter(None, tracked):
            assert (PACK / os.fsdecode(path)).read_bytes() == (upstream / os.fsdecode(path)).read_bytes()
    for source in (V2 / 'nodes').glob('*.py'):
        text = source.read_text()
        for forbidden in ('import os', 'import sys', 'folder_paths', 'PromptServer', 'requests',
                          'subprocess', 'open(', '_from_raw', 'eval(', 'exec(', 'threading'):
            assert forbidden not in text
    assert not (PACK / 'LICENSE').exists()  # Preserve the upstream declared-license caveat.


def test_pristine_to_v2_byte_exact_patch_and_cache_hygiene(tmp_path):
    manifest, diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix('.json').read_text()) == manifest
    assert PAIR.with_suffix('.diff').read_text() == diff
    fresh = tmp_path / 'comfyui-typeaux/x7d8325f'; fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns('v2'))
    packpatch.apply(fresh, manifest, diff)
    packpatch.validate_tree(fresh / PACK.name / 'v2', V2)
    assert not list(PACK.rglob('*.pyc')) and not list(PACK.rglob('__pycache__'))
