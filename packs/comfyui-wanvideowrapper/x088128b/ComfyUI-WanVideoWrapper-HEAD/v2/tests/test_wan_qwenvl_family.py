"""Exact scheduled source projection through actual inspect-only guests.

Host RecordingClip is a deterministic control, with actual HookGroup metadata;
no tokenizer weights, trained Qwen/CLIP inference, physical profile or sampler.
"""
import ast
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import pytest
import torch

sys.dont_write_bytecode = True
V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent
CORE = Path('/Users/ben/comfy/ComfyUI-secure-nodes')
BACKEND = Path('/Users/ben/comfy/ComfyUI_secure_nodes/backend')
sys.path[:0] = [str(CORE), str(BACKEND)]
os.environ.setdefault('COMFY_CORE_ROOT', str(CORE))
from comfy.cli_args import args
args.cpu = True
from comfy.hooks import HookGroup
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb
from comfy_secure_nodes.transport.host import GuestSession

ID = 'TextImageEncodeQwenVL'
PRIMITIVE = Path('/Users/ben/popbot/raw-chats/outputs/many-oct7-cond-embedding')
STUB_SHA = '57246795795118e320926fbbb6be50f7c03c6971b2b5029ac709adef5169ab03'


def candidate(root=V2):
    name = '_jack_qwenvl_' + str(id(root))
    spec = importlib.util.spec_from_file_location(name, root/'__init__.py',
        submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module.NODE_CLASS_MAPPINGS[ID]


def original():
    cls = next(x for x in ast.parse((PACK/'nodes.py').read_text()).body
        if isinstance(x, ast.ClassDef) and x.name == ID)
    ns = {}
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(PACK/'nodes.py'), 'exec'), ns)
    return ns[ID]


class RecordingClip:
    """Pure scheduled projection; template omission is interpreted as None."""
    def __init__(self, dtype=torch.float32, rows=None):
        self.dtype = dtype
        self.calls = []
        self.scheduled = []
        self.row_override = rows

    def tokenize(self, prompt, **kwargs):
        images = kwargs.get('images', [])
        self.calls.append((prompt, dict(kwargs)))
        # Stay source-controlled: this is NOT Qwen's trained tokenizer math.
        offset = len(prompt) + sum(float(x.sum()) for x in images)
        tensor = (torch.arange(48).reshape(2, 6, 4)[:, ::2] + offset).to(self.dtype)
        return {'first': tensor, 'later': tensor + 100}

    def encode_from_tokens_scheduled(self, tokens):
        self.scheduled.append(tokens)
        if self.row_override is not None:
            self.rows = self.row_override
        else:
            metadata = {'hooks': HookGroup(), 'model': object(), 'opaque': object()}
            self.rows = [[tokens['first'], metadata], [tokens['later'], metadata]]
        return self.rows


def cases():
    for dtype in (torch.float16, torch.bfloat16, torch.float32, torch.float64):
        for channels in (None, 3, 4):
            for prompt in ('', 'literal {braces}\nhello', '日本語🎥<|im_start|>'):
                image = None if channels is None else torch.arange(2*3*5*channels).reshape(2, 3, 5, channels).double()/97
                yield dtype, prompt, image


def same_calls(source, current, image):
    assert len(source.calls) == len(current.calls) == 1
    assert len(source.scheduled) == len(current.scheduled) == 1
    assert source.calls[0][0] == current.calls[0][0]
    left, right = source.calls[0][1], current.calls[0][1]
    assert len(left['images']) == len(right['images']) == (0 if image is None else 1)
    if image is None:
        assert left['llama_template'] is None and 'llama_template' not in right
    else:
        assert left['llama_template'] == right['llama_template']
        assert torch.equal(left['images'][0], right['images'][0])
        assert right['images'][0].shape[-1] == 3


async def in_process(clip, prompt, image=None):
    refs = _sdk.InProcessRefResolver()
    wrapped = await _sdk.wrap_inputs(refs, dict(clip=clip, prompt=prompt, image=image),
        {'clip':'CLIP', 'prompt':'STRING', 'image':'IMAGE'})
    with _sdk.bind_runtime(refs, SimpleNamespace(), _sdk.InProcessOps()):
        result = await candidate().execute(**wrapped)
    return await refs.resolve(result.result[0])


def test_exact_schema_and_source_registration():
    schema = candidate().GET_SCHEMA()
    source = original()
    assert source.RETURN_TYPES == ('QWENVL_EMBEDS',)
    assert source.RETURN_NAMES == ('qwenvl_embeds',)
    assert schema.node_id == ID and schema.category == source.CATEGORY
    assert [x.id for x in schema.inputs] == ['clip','prompt','image']
    assert [x.io_type for x in schema.inputs] == ['CLIP','STRING','IMAGE']
    assert schema.inputs[1].default == '' and schema.inputs[1].multiline is True
    assert schema.inputs[2].optional is True
    assert [(x.io_type,x.display_name) for x in schema.outputs] == [('QWENVL_EMBEDS','qwenvl_embeds')]
    assert candidate().SDK_REFS is True and candidate().SDK_PERMISSIONS == ('inspect',)
    assert hashlib.sha256((V2/'comfy-api.pyi').read_bytes()).hexdigest() == STUB_SHA
    assert 'async def embedding(self, index: int = 0)' in (V2/'comfy-api.pyi').read_text()


def test_36_source_exact_first_scheduled_tensor_dtype_views_and_console_shape(capsys):
    async def run():
        count = 0
        for dtype, prompt, image in cases():
            source, current = RecordingClip(dtype), RecordingClip(dtype)
            expected = original()().add(source, prompt, image)[0]
            result = await in_process(current, prompt, image)
            assert result is current.rows[0][0]
            assert result.dtype == expected.dtype and result.shape == expected.shape
            assert torch.equal(result, expected) and not torch.equal(result, current.rows[1][0])
            same_calls(source, current, image)
            count += 1
        assert count == 36
    asyncio.run(run())
    assert capsys.readouterr().out.count('Qwen-VL embeds shape: torch.Size([2, 3, 4])') == 72


def test_c1_c2_and_explicit_none_keyword_fit_are_documented_narrowings():
    async def run():
        for channels in (1, 2):
            image = torch.ones(1, 2, 3, channels)
            source = RecordingClip()
            assert original()().add(source, '', image)[0].shape == (2,3,4)
            current = RecordingClip()
            with pytest.raises(ValueError, match='at least three channels'):
                await in_process(current, '', image)
            assert not current.calls
    asyncio.run(run())
    # Canonical tokenizer signature makes omitted keyword equal to None.
    tree = ast.parse((CORE/'comfy/text_encoders/qwen_image.py').read_text())
    cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == 'QwenImageTokenizer')
    fn = next(x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == 'tokenize_with_weights')
    defaults = dict(zip([x.arg for x in fn.args.args][-len(fn.args.defaults):], fn.args.defaults))
    assert isinstance(defaults['llama_template'], ast.Constant) and defaults['llama_template'].value is None


def test_empty_rows_and_projection_bounds_without_export_or_allocation():
    async def run():
        for rows, error in (([], IndexError),
                ([[torch.empty(134217729, device='meta'), {}]], ValueError),
                ([[torch.empty((1,)*33, device='meta'), {}]], ValueError)):
            clip = RecordingClip(rows=rows)
            with pytest.raises(error):
                await in_process(clip, '')
    asyncio.run(run())


def test_encode_input_bounds_before_tokenizer():
    async def run():
        for prompt in ('x'*32769, '🎥'*32769, 123):
            clip = RecordingClip()
            with pytest.raises((ValueError, TypeError)):
                await in_process(clip, prompt)
            assert not clip.calls
        for image in (torch.empty(65,1,1,3), torch.empty(1,8193,1,3,device='meta')):
            clip = RecordingClip()
            with pytest.raises(ValueError):
                await in_process(clip, '', image)
            assert not clip.calls
    asyncio.run(run())


def test_source_consumers_remain_explicitly_pending():
    manifest = json.loads((V2/'secure-nodes.json').read_text())
    assert ID in manifest['nodes'] and 'WanVideoAddBindweaveEmbeds' in manifest['nodes']
    assert 'WanVideoSampler' not in manifest['nodes']
    assert manifest['conversion_progress']['complete'] is False
    node = next(x for x in ast.parse((PACK/'nodes.py').read_text()).body
        if isinstance(x, ast.ClassDef) and x.name == 'WanVideoAddBindweaveEmbeds')
    fn = next(x for x in node.body if isinstance(x, ast.FunctionDef) and x.name == 'add')
    for key in ('qwenvl_embeds_pos','qwenvl_embeds_neg'):
        assert any(isinstance(x, ast.Assign) and ast.unparse(x) == f"updated['{key}'] = {key}"
            for x in fn.body)
    sampler = (PACK/'nodes_sampler.py').read_text()
    assert 'qwenvl_embeds_pos.to(device)' in sampler and 'qwenvl_embeds_neg.to(device)' in sampler


def test_actual_outer_custom_tensor_two_fresh_required_guests(tmp_path, monkeypatch):
    monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE', 'required')
    monkeypatch.syspath_prepend(str(CORE))
    import execution
    async def run():
        previous = _sdk.providers.execution_backend
        pids = set()
        try:
            for number in range(2):
                snapshot = PACK.parent
                root = V2
                if number:
                    snapshot = tmp_path/'fresh-snapshot'
                    root = snapshot/PACK.name/'v2'
                    shutil.copytree(V2, root)
                cls = packdb.load_pack(snapshot, mount_name=f'custom_nodes.jack_qwenvl_{number}').node_mappings[ID]
                session = await GuestSession('jack-wan-qwenvl', guest_runtime_root=root).start()
                assert session.sandbox_kind == 'seatbelt'
                class Backend:
                    grants = ('inspect',)
                    async def dispatch(self, plan, local_call, runtime):
                        assert plan.input_mode == 'refs' and plan.permissions == ('inspect',)
                        plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs, plan.input_types)
                        return await session.execute(plan, runtime, capabilities=self.grants, tenant=f'qwen-owner-{number}')
                backend = Backend()
                _sdk.providers.register_execution_backend(backend)
                try:
                    for dtype, prompt, image in cases():
                        source, current = RecordingClip(dtype), RecordingClip(dtype)
                        expected = original()().add(source, prompt, image)[0]
                        inputs = dict(clip=current, prompt=prompt)
                        if image is not None: inputs['image'] = image
                        finalized, missing, data = execution.get_input_data(inputs, cls, 'owner', None)
                        assert not missing
                        result = await execution._async_map_node_over_list('qwenvl-outer', 'owner',
                            cls, finalized, 'execute', v3_data=data)
                        assert tuple(cls.RETURN_TYPES) == ('QWENVL_EMBEDS',)
                        actual = result[0].result[0]
                        assert isinstance(actual, torch.Tensor) and actual is current.rows[0][0]
                        assert actual.dtype == expected.dtype and actual.shape == expected.shape
                        assert torch.equal(actual, expected)
                        same_calls(source, current, image)
                    # Declare != grant: same production consumer fails when
                    # inspect is withheld, then recovers when it is supplied.
                    backend.grants = ()
                    refused_clip = RecordingClip()
                    inputs = dict(clip=refused_clip, prompt='inspect refusal')
                    finalized, missing, data = execution.get_input_data(inputs, cls, 'owner', None)
                    assert not missing
                    with pytest.raises(Exception, match='inspect.*not granted'):
                        await execution._async_map_node_over_list('qwenvl-outer', 'owner',
                            cls, finalized, 'execute', v3_data=data)
                    backend.grants = ('inspect',)
                    result = await execution._async_map_node_over_list('qwenvl-outer', 'owner',
                        cls, finalized, 'execute', v3_data=data)
                    assert torch.equal(result[0].result[0], refused_clip.rows[0][0])
                    pids.add(session.pid)
                    # Same guest: selected tensor is allowed but raw/whole value
                    # access is not. These controls are NOT release mappings.
                    refs = _sdk.InProcessRefResolver()
                    rows = [[torch.arange(12).reshape(1,3,4), {'hooks':HookGroup()}]]
                    cond = _sdk.CondRef._wrap(await refs.create('CONDITIONING',rows))
                    runtime = _sdk.Runtime(refs=refs,ctx=SimpleNamespace(),ops=_sdk.InProcessOps())
                    probe_name = cls.__module__.rsplit('.',1)[0]+'.tests.qwenvl_boundary_probe'
                    probe_spec = importlib.util.spec_from_file_location(probe_name,
                        root/'tests/qwenvl_boundary_probe.py')
                    probe_module = importlib.util.module_from_spec(probe_spec)
                    sys.modules[probe_name] = probe_module
                    probe_spec.loader.exec_module(probe_module)
                    plan = _sdk.ExecutionPlan('qwen-boundary','owner','JackQwenBoundaryProbe',
                        node_module=probe_name,
                        inputs={'conditioning':cond,'mode':'raw'}, permissions=())
                    with pytest.raises(Exception, match='raw.*not granted'):
                        await session.execute(plan,runtime,capabilities=(),tenant=f'qwen-owner-{number}')
                    plan.inputs['mode'] = 'whole'
                    with pytest.raises(Exception, match='HookGroup'):
                        await session.execute(plan,runtime,capabilities=('raw',),tenant=f'qwen-owner-{number}')
                    plan.inputs['mode'] = 'project'
                    result = await session.execute(plan,runtime,capabilities=(),tenant=f'qwen-owner-{number}')
                    assert result.result[0].kind == 'TENSOR'
                    assert await refs.resolve(result.result[0]) is rows[0][0]
                    print('JACK_QWENVL_REQUIRED_GUEST', number, session.pid,
                        '36 outer positives; inspect refusal/recovery; raw refusal; whole HookGroup refusal; zero-cap projection recovery')
                finally:
                    await session.kill()
            assert len(pids) == 2 and os.getpid() not in pids
        finally:
            _sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
