import asyncio
import ast
import copy
import hashlib
import importlib.util
import itertools
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import types

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

IDS = ['jupo.JoinPrompt.JoinStrings', 'jupo.JoinPrompt.JoinPrompt']
COMMIT = '0832089ec5f5f1808c6b649777b125a2b1db516c'
DTS_SHA = '4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3'
PYI_SHA = '50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78'
PAIR = PACK_DB / 'patches/comfy-join-prompt/x0832089/comfy-join-prompt-x0832089'


def load(name, root):
    spec = importlib.util.spec_from_file_location(name, root / '__init__.py', submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def secure():
    return load('_join_secure_test', V2)


def old(tmp_path):
    root = tmp_path / 'pristine'
    if not root.exists():
        shutil.copytree(PACK, root, ignore=shutil.ignore_patterns('v2'))
    # The pinned unused Endpoint class reads PromptServer.instance at import.
    # This records registrations without starting a server, not an SDK shim.
    registered = []
    server = types.ModuleType('server')
    class Routes:
        def get(self, path):
            registered.append(('GET', path)); return lambda fn: fn
        def post(self, path):
            registered.append(('POST', path)); return lambda fn: fn
    server.PromptServer = types.SimpleNamespace(instance=types.SimpleNamespace(routes=Routes()))
    previous = sys.modules.get('server')
    sys.modules['server'] = server
    try:
        module = load('_join_upstream_test', root)
        classes = asyncio.run((asyncio.run(module.comfy_entrypoint())).get_node_list())
        assert not registered
        return {cls.GET_SCHEMA().node_id: cls for cls in classes}
    finally:
        if previous is None:
            sys.modules.pop('server', None)
        else:
            sys.modules['server'] = previous


def manifest():
    return {'format': FORMAT, 'nodes': {node_id: {
        'class': cls.__name__, 'module': 'nodes', 'sdk_refs': False, 'permissions': [],
        'methods': {name: False for name in ('validate_inputs', 'fingerprint_inputs', 'check_lazy_status')},
        'schema': encode_schema(copy.deepcopy(cls.GET_SCHEMA())),
    } for node_id, cls in secure().NODE_CLASS_MAPPINGS.items()},
        'runtime': manifest_declaration(V2), 'frontend_permissions': [], 'web_directory': 'web'}


def outcome(fn, **inputs):
    try:
        return ('value', fn(**inputs).result)
    except Exception as exc:
        return ('error', type(exc).__name__, str(exc))


def test_actual_upstream_entrypoint_and_exact_schema_census(tmp_path):
    upstream, new = old(tmp_path), secure()
    assert list(upstream) == list(new.NODE_CLASS_MAPPINGS) == IDS
    assert [cls.GET_SCHEMA().node_id for cls in asyncio.run((asyncio.run(new.comfy_entrypoint())).get_node_list())] == IDS
    for node_id, cls in new.NODE_CLASS_MAPPINGS.items():
        cls.GET_SCHEMA().validate()
        assert encode_schema(cls.GET_SCHEMA()) == encode_schema(upstream[node_id].GET_SCHEMA())
        assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS == ()
    template = new.NODE_CLASS_MAPPINGS[IDS[0]].GET_SCHEMA().inputs[0].template
    assert template.min == 1 and template.max == 50 and template.prefix == 'text_'
    legacy_js = (PACK / 'web/extension/join-prompt.js').read_text()
    assert legacy_js.count('app.registerExtension(') == 1
    assert not any('registerNodeType(' in p.read_text() for p in (PACK / 'web').rglob('*.js'))


DELIMITERS = ['', ', ', r'\n', r'\r\n', r'\t', r'\\n', '雪🙂', ' \n ']
TEXTS = ['', 'plain', ' a ,b,, c ', ' a, b\n c,d ', '\r\n', '雪, 🙂', '<script>,<img>', 'a\x00,b']


@pytest.mark.parametrize('delimiter,cleanup', list(itertools.product(DELIMITERS, [False, True, 1, 'yes'])))
def test_join_strings_order_delimiter_comma_cleanup_exact(tmp_path, delimiter, cleanup):
    upstream, new = old(tmp_path)[IDS[0]], secure().NODE_CLASS_MAPPINGS[IDS[0]]
    for texts in [[], [''], TEXTS, list(reversed(TEXTS)), ['a'] * 50]:
        inputs = dict(texts={f'text_{i}': text for i, text in enumerate(texts)}, delimiter=delimiter, cleanup=cleanup)
        assert outcome(new.execute, **inputs) == outcome(upstream.execute, **inputs)


@pytest.mark.parametrize('options', ['', '{broken', 'null', '[]', '5', 'true', '"string"', None, {}, 5,
    '{"delimiter":null}', '{"delimiter":7}', '{"cleanup":"truthy","delimiter":"\\\\n"}',
    '{"delimiter":", ","cleanup":true}', '{"ignored":"value"}'])
def test_join_prompt_options_native_error_and_falsey_path_parity(tmp_path, options):
    upstream, new = old(tmp_path)[IDS[1]], secure().NODE_CLASS_MAPPINGS[IDS[1]]
    for text, prev in itertools.product(['', 'a, b ', None, 0, '雪\n🙂'], ['', ' p ,q ', None, 0]):
        inputs = dict(text=text, prev=prev, options=options)
        assert outcome(new.execute, **inputs) == outcome(upstream.execute, **inputs)


def test_generated_differential_and_malformed_groups(tmp_path):
    upstream, new = old(tmp_path), secure().NODE_CLASS_MAPPINGS
    rng = random.Random(61206)
    before = random.getstate()
    for _ in range(200):
        texts = [''.join(rng.choices(TEXTS, k=rng.randrange(6))) for _ in range(rng.randrange(8))]
        inputs = dict(texts={f'text_{i}': text for i, text in enumerate(texts)}, delimiter=rng.choice(DELIMITERS), cleanup=rng.choice([False, True]))
        assert outcome(new[IDS[0]].execute, **inputs) == outcome(upstream[IDS[0]].execute, **inputs)
    for inputs in [dict(texts=None), dict(texts=[]), dict(texts={'text_0': None}), dict(texts={'text_0': 5}),
                   dict(texts={'text_0': 5}, cleanup=True), dict(texts={}, delimiter=None), dict(texts={}, delimiter=5)]:
        assert outcome(new[IDS[0]].execute, **inputs) == outcome(upstream[IDS[0]].execute, **inputs)
    assert random.getstate() == before


def test_projected_output_text_row_and_utf8_resource_bounds(tmp_path):
    upstream, new = old(tmp_path), secure().NODE_CLASS_MAPPINGS
    cls = new[IDS[0]]
    for text in ['x' * 65536, '🙂' * 16384, '\ud800', ',' * 32768]:
        inputs = dict(texts={'text_0': text}, cleanup=True)
        assert outcome(cls.execute, **inputs) == outcome(upstream[IDS[0]].execute, **inputs)
    for inputs in [dict(texts={'text_0': 'x' * 65537}), dict(texts={'text_0': '🙂' * 16385}),
                   dict(texts={}, delimiter='x' * 65537)]:
        with pytest.raises(ValueError, match='64 KiB'):
            cls.execute(**inputs)
    with pytest.raises(ValueError, match='50 text'):
        cls.execute({f'text_{i}': 'a' for i in range(51)})
    assert len(cls.execute({f'text_{i}': 'x' * 65536 for i in range(16)}).result[0]) == 1048576
    with pytest.raises(ValueError, match='projected output'):
        cls.execute({f'text_{i}': 'x' * 65536 for i in range(17)})
    with pytest.raises(ValueError, match='projected output'):
        cls.execute({f'text_{i}': ',' * 65536 for i in range(9)}, cleanup=True)
    with pytest.raises(ValueError, match='64 KiB'):
        new[IDS[1]].execute('a', options=' ' * 65537)


def test_frontend_specific_operations_and_lifecycle_recording_harness():
    result = subprocess.run(['node', str(V2 / 'tests/frontend_harness.mjs')], capture_output=True, text=True, check=True)
    assert 'assertions passed' in result.stdout


def test_frontend_current_contract_typecheck():
    compiler = os.environ.get('TSC_BIN', '/Users/ben/popbot-ai/popbot-ai/node_modules/.bin/tsc')
    subprocess.run([compiler, '-p', str(V2 / 'tests/tsconfig.json')], check=True, capture_output=True, text=True)


def test_complete_pinned_snapshot_hash_inventory():
    expected = json.loads((V2 / 'tests/pristine-hashes.json').read_text())
    files = {str(p.relative_to(PACK)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in PACK.rglob('*') if p.is_file() and V2 not in p.parents}
    assert files == expected['files']
    assert expected['commit'] == COMMIT
    assert expected['archive_sha256'] == '0b1ba349ef353269c42c0226db4788c178ff77ec855300f6ad7e1c0035dd788f'


def test_real_zero_capability_guests_and_recreated_pack_filesystem(tmp_path):
    upstream = old(tmp_path)
    fresh = tmp_path / 'fresh-render'; shutil.copytree(V2, fresh)
    cases = [(IDS[0], dict(texts={'text_1': ' a,b ', 'text_0': '雪\n c ,d'}, delimiter=r'\n', cleanup=True)),
             (IDS[0], dict(texts={f'text_{i}': str(i) for i in range(50)}, delimiter='|')),
             (IDS[0], dict(texts={})),
             (IDS[1], dict(text='new', prev='previous', options='{"delimiter":"\\\\n","cleanup":true}')),
             (IDS[1], dict(text='', prev='p')), (IDS[1], dict(text='a', options='{broken'))]
    async def run():
        for index, root in enumerate((V2, fresh)):
            classes = load(f'_join_render_{index}', root).NODE_CLASS_MAPPINGS
            refs = _sdk.InProcessRefResolver()
            session = await GuestSession('join-prompt', guest_runtime_root=root).start()
            try:
                async def call(node_id, inputs):
                    cls = classes[node_id]
                    plan = _sdk.ExecutionPlan(prompt_id='join-guest', node_id='1', node_type=cls.__name__,
                        tier='sandbox', node_module=cls.__module__, inputs=inputs, input_mode='values', permissions=(), method='execute')
                    runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
                    return await session.execute(plan, runtime, capabilities=())
                for node_id, inputs in cases:
                    actual = (await call(node_id, inputs)).result
                    assert actual == upstream[node_id].execute(**inputs).result and isinstance(actual[0], str)
                with pytest.raises(Exception, match='64 KiB'):
                    await call(IDS[0], dict(texts={'text_0': 'x' * 65537}))
                with pytest.raises(Exception, match='get'):
                    await call(IDS[1], dict(text='a', options='[]'))
                with pytest.raises(Exception, match='values'):
                    await call(IDS[0], dict(texts=None))
                assert session.last_guest_pid not in (None, os.getpid())
                assert not refs._table
            finally:
                await session.kill()
    asyncio.run(run())


def test_public_outer_executor_autogrow_and_string_output_types():
    import execution
    loaded = packdb.load_pack(SNAPSHOT, mount_name='custom_nodes.join_prompt_outer')
    assert list(loaded.node_mappings) == IDS and not loaded.routes
    async def run():
        previous = _sdk.providers.execution_backend
        class Backend:
            sessions = []
            async def dispatch(self, plan, local_call, runtime):
                session = await GuestSession('join-outer', guest_runtime_root=V2).start()
                self.sessions.append(session)
                return await session.execute(plan, runtime, capabilities=())
        backend = Backend(); _sdk.providers.register_execution_backend(backend)
        try:
            for node_id, inputs, expected in [
                (IDS[0], {'texts.text_0': ['first'], 'texts.text_1': ['second'], 'delimiter': ['|'], 'cleanup': [False]}, 'first|second'),
                (IDS[1], {'text': ['new'], 'prev': ['old'], 'options': ['{"delimiter":", "}']}, 'old, new'),
            ]:
                cls = loaded.node_mappings[node_id]
                assert tuple(cls.RETURN_TYPES) == ('STRING',)
                raw_inputs = {name: values[0] for name, values in inputs.items()}
                finalized, missing, v3_data = execution.get_input_data(raw_inputs, cls, '1', None)
                assert not missing
                values = await execution._async_map_node_over_list(prompt_id='join-outer', unique_id='1', obj=cls,
                    input_data_all=finalized, func=cls.FUNCTION, v3_data=v3_data)
                assert values[0].result == (expected,) and isinstance(values[0].result[0], str)
        finally:
            _sdk.providers.register_execution_backend(previous)
            for session in backend.sessions:
                await session.kill()
    asyncio.run(run())


def test_manifest_canonical_stubs_assets_and_no_ambient_authority():
    assert json.loads((V2 / 'secure-nodes.json').read_text()) == manifest()
    assert hashlib.sha256((V2 / 'comfy-api.d.ts').read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / 'comfy-api.pyi').read_bytes()).hexdigest() == PYI_SHA
    assert (V2 / 'LICENSE').read_bytes() == (PACK / 'LICENSE').read_bytes()
    assert not list(V2.rglob('*_routes.py'))
    for file in [V2 / 'nodes.py', V2 / '__init__.py']:
        tree = ast.parse(file.read_text())
        for item in ast.walk(tree):
            if isinstance(item, ast.Import): assert all(x.name == 'json' for x in item.names)
            if isinstance(item, ast.ImportFrom): assert item.module in ('comfy_api.latest', 'nodes')
            if isinstance(item, ast.Call) and isinstance(item.func, ast.Name): assert item.func.id not in ('open', 'eval', 'exec', '__import__')
    assert COMMIT in (V2 / 'SECURE_CONVERSION.md').read_text()


def test_exact_pristine_to_v2_patch_roundtrip(tmp_path):
    generated, diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix('.json').read_text()) == generated
    assert PAIR.with_suffix('.diff').read_text() == diff
    root = tmp_path / 'comfy-join-prompt/x0832089'; root.mkdir(parents=True)
    shutil.copytree(PACK, root / PACK.name, ignore=shutil.ignore_patterns('v2'))
    packpatch.apply(root, generated, diff)
    packpatch.validate_tree(root / PACK.name / 'v2', V2)
    assert not list(PACK.rglob('*.pyc')) and not list(PACK.rglob('__pycache__'))
