"""Public native-vision branch evidence, not trained inference/full node support.

Real core ops/canonical preprocessing + deterministic recording projection;
actual guest uses a test-only scratch entrypoint, not the release manifest.
"""
import ast
import asyncio
import copy
import importlib.util
import logging
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
for path in (CORE, BACKEND): sys.path.insert(0, str(path))
os.environ.setdefault('COMFY_CORE_ROOT', str(CORE))
from comfy_api.latest import _sdk
import comfy.clip_vision
import comfy.model_management as mm
from comfy_secure_nodes.transport.host import GuestSession


def candidate(root=V2):
    name = '_wan_native_vision_' + str(id(root))
    spec = importlib.util.spec_from_file_location(name, root/'__init__.py',
        submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return importlib.import_module(name+'.secure_vision_algorithms')


def original():
    funcs = {'split_tiles', 'merge_hiddenstates', 'clip_encode_image_tiled', 'encode_image_'}
    helpers = [item for item in ast.parse((PACK/'utils.py').read_text()).body
        if isinstance(item, ast.FunctionDef) and item.name in funcs]
    assert len(helpers) == 4
    cls = next(item for item in ast.parse((PACK/'nodes.py').read_text()).body
        if isinstance(item, ast.ClassDef) and item.name == 'WanVideoClipVisionEncode')
    ns = {'torch': torch, 'ClipVisionModel': comfy.clip_vision.ClipVisionModel,
        'device': torch.device('cpu'), 'offload_device': torch.device('cpu'),
        'mm': SimpleNamespace(soft_empty_cache=lambda: None), 'log': logging.getLogger('wan-native-oracle')}
    exec(compile(ast.Module(body=helpers+[cls], type_ignores=[]), str(PACK/'nodes.py'), 'exec'), ns)
    return ns[cls.name]()


class Projection:
    def __init__(self): self.calls = []; self.moves = []
    def to(self, device): self.moves.append(device); return self
    def __call__(self, pixel_values, intermediate_output):
        assert intermediate_output == -2
        self.calls.append(pixel_values.clone())
        tokens = pixel_values.flatten(2).transpose(1, 2)[:, :5]
        return tokens, tokens+100, pixel_values.mean((2, 3)), None


def encoder():
    value = comfy.clip_vision.ClipVisionModel.__new__(comfy.clip_vision.ClipVisionModel)
    value.image_size = 224
    value.image_mean = [.48145466, .4578275, .40821073]
    value.image_std = [.26862954, .26130258, .27577711]
    value.model_type = 'clip_vision_model'
    value.return_all_hidden_states = False
    value.load_device = torch.device('cpu')
    value.patcher = object()
    value.model = Projection()
    return value


def recording_encoder(dtype=torch.float32, token_count=5, width=3):
    value = encoder()
    def record(image, crop=True):
        assert crop is True
        value.model.calls.append(image.clone())
        mean = image.mean(dim=(1,2,3)).reshape(-1,1,1).to(dtype)
        pattern = torch.arange(token_count*width,dtype=dtype).reshape(1,token_count,width)/16
        last = mean+pattern
        return SimpleNamespace(last_hidden_state=last,penultimate_hidden_states=last+100,
            image_embeds=last.mean(dim=1))
    value.encode_image = record
    return value


@pytest.fixture
def canonical_policy(monkeypatch):
    # Pytest adds the snapshot beside nodes.py; trusted provider imports must
    # use canonical core, including the progress provider's server dependency.
    monkeypatch.syspath_prepend(str(CORE))
    loads = []; unloads = []
    monkeypatch.setattr(mm, 'load_model_gpu', loads.append)
    monkeypatch.setattr(mm, 'intermediate_device', lambda: torch.device('cpu'))
    monkeypatch.setattr(mm, 'unload_model_and_clones', lambda patcher, **kw: unloads.append((patcher, kw)))
    # Keep these small recording CPU fixtures cheap; restore global setting.
    previous = torch.get_num_threads(); torch.set_num_threads(1)
    try: yield loads, unloads
    finally: torch.set_num_threads(previous)


def images(batch, h=17, w=23, dtype=torch.float32):
    return torch.linspace(0, 1, batch*h*w*3, dtype=dtype).reshape(batch,h,w,3)


def cases():
    values = []
    for batch in (1, 2, 3):
        for tiles in (0, 1, 2, 4):
            for mode in ('average', 'sum', 'concat', 'batch', 'unrecognized'):
                for ratio in (0., .5, 1.):
                    values.append(dict(image_1=images(batch), strength_1=.25, strength_2=2.5,
                        force_offload=False, crop='disabled', combine_embeds=mode, tiles=tiles, ratio=ratio))
    for dtype in (torch.float32, torch.float64):
        for tiles in (0, 1, 2, 4, 8):
            for mode in ('average', 'sum', 'concat', 'batch'):
                values.append(dict(image_1=images(2,dtype=dtype), image_2=images(1,dtype=dtype),
                    negative_image=images(2,19,25,dtype), strength_1=0., strength_2=3.,
                    force_offload=True, crop='center', combine_embeds=mode, tiles=tiles, ratio=.25))
    return values


def equal(expected, actual):
    assert list(expected) == list(actual)
    for key, value in expected.items():
        if value is None: assert actual[key] is None
        else:
            assert actual[key].dtype == value.dtype and actual[key].shape == value.shape
            assert torch.equal(actual[key], value)


async def in_process(inputs, value, permissions=('raw',), ops=None):
    refs = _sdk.InProcessRefResolver()
    fields = {'clip_vision': value, **inputs}
    types = {'clip_vision':'CLIP_VISION', 'image_1':'IMAGE', 'image_2':'IMAGE', 'negative_image':'IMAGE'}
    wrapped = await _sdk.wrap_inputs(refs, fields, types)
    plan = _sdk.ExecutionPlan('wan-native', '1', 'JackWanNativeVisionProbe', permissions=permissions)
    rt = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=ops or _sdk.InProcessOps())
    with _sdk.bind_runtime(rt.refs, rt.ctx, rt.ops):
        return await candidate().encode_native_vision(wrapped.pop('clip_vision'), **wrapped)


def test_native_public_ref_differential_220_cases(canonical_policy):
    values = cases(); assert len(values) == 220
    async def run():
        for inputs in values:
            legacy = encoder(); current = encoder()
            expected = original().process(legacy, **copy.deepcopy(inputs))[0]
            actual = await in_process(copy.deepcopy(inputs), current)
            equal(expected, actual)
            assert len(legacy.model.calls) == len(current.model.calls)
            for a, b in zip(legacy.model.calls, current.model.calls): assert torch.equal(a, b)
    asyncio.run(run())
    _, unloads = canonical_policy
    assert len(unloads) == 40
    assert all(options == {'unload_additional_models':False, 'all_devices':True} for _, options in unloads)


def test_native_crop_ignored_and_final_vs_penultimate_are_distinct(canonical_policy):
    async def run():
        base = dict(image_1=images(2), force_offload=False, combine_embeds='batch')
        center = await in_process({**base, 'crop':'center'}, encoder())
        disabled = await in_process({**base, 'crop':'disabled'}, encoder())
        tiled1 = await in_process({**base, 'tiles':1}, encoder())
        equal(center, disabled)
        assert torch.allclose(center['clip_embeds']-tiled1['clip_embeds'], torch.full_like(center['clip_embeds'],100))
    asyncio.run(run())


def test_last_image_tile_overwrite_broadcast_and_single_unscaled_merge(canonical_policy):
    async def run():
        image = torch.arange(3.).reshape(3,1,1,1).expand(3,16,16,3).clone()
        result = await in_process(dict(image_1=image,tiles=2,ratio=0.,combine_embeds='batch',force_offload=False),encoder())
        assert torch.equal(result['clip_embeds'][0], result['clip_embeds'][1])
        assert torch.equal(result['clip_embeds'][1], result['clip_embeds'][2])
        single = await in_process(dict(image_1=image[2:],tiles=2,ratio=1.,combine_embeds='batch',force_offload=False),encoder())
        assert single['clip_embeds'].shape[0] == 2
        assert torch.count_nonzero(single['clip_embeds'][1]) > 0
    asyncio.run(run())


def test_oversize_and_malformed_tile_work_refused_before_encoder_or_allocation(canonical_policy, monkeypatch):
    algorithm = candidate()
    class Raw:
        def __init__(self, value): self.value = value
        async def raw(self): return self.value
    class NoVision:
        async def encode_image(self, *a, **kw): raise AssertionError('must preflight')
        async def offload(self): raise AssertionError('must preflight')
    monkeypatch.setattr(algorithm, 'split_tiles', lambda *a: (_ for _ in ()).throw(AssertionError('no split allocation')))
    async def run():
        with pytest.raises(ValueError, match='projected tile work'):
            await algorithm.encode_native_vision(NoVision(), Raw(torch.empty(1,1400,1400,3,device='meta')), tiles=2)
        with pytest.raises(ValueError, match='combined batch'):
            await algorithm.encode_native_vision(NoVision(), Raw(images(40)), image_2=Raw(images(25)))
        with pytest.raises(ValueError, match='nonempty'):
            await algorithm.encode_native_vision(NoVision(), Raw(images(1,1,1)), tiles=2)
    asyncio.run(run())


def test_all_declared_tile_choices_450_recording_cases_exact_no_preprocess_inference(canonical_policy):
    async def run():
        count = 0
        for batch in (1,2,3):
            for tiles in (0,1,2,4,6,8,10,12,14,16):
                for mode in ('average','sum','concat','batch','unknown'):
                    for ratio in (0.,.5,1.):
                        fields = dict(image_1=images(batch),tiles=tiles,ratio=ratio,
                            combine_embeds=mode,strength_1=.25,strength_2=2.5,force_offload=False,crop='disabled')
                        legacy = recording_encoder(); current = recording_encoder()
                        expected = original().process(legacy,**copy.deepcopy(fields))[0]
                        result = await in_process(copy.deepcopy(fields),current)
                        equal(expected,result)
                        expected_batches = [batch]+([tiles*tiles]*batch if tiles > 1 else [])
                        assert [item.shape[0] for item in current.model.calls] == expected_batches
                        for a,b in zip(legacy.model.calls,current.model.calls): assert torch.equal(a,b)
                        count += 1
        assert count == 450
    asyncio.run(run())


def test_token_windows_are_ordered_transport_only_b256_bf16_exact(canonical_policy):
    class RecordingOps(_sdk.InProcessOps):
        def __init__(self): super().__init__(); self.requests = []
        async def apply(self,name,ref,params):
            self.requests.append((name,copy.deepcopy(params)))
            return await super().apply(name,ref,params)
    async def run():
        for dtype in (torch.float32,torch.float64,torch.bfloat16):
            fields = dict(image_1=images(2),tiles=16,ratio=.5,combine_embeds='batch',force_offload=False,
                strength_1=.25,strength_2=2.5,crop='center')
            legacy = recording_encoder(dtype); current = recording_encoder(dtype); ops = RecordingOps()
            result = await in_process(copy.deepcopy(fields),current,ops=ops)
            equal(original().process(legacy,**copy.deepcopy(fields))[0],result)
            assert [item.shape[0] for item in current.model.calls] == [2,256,256]
            windows = [params for name,params in ops.requests if name=='clip_vision_output.last_hidden_state']
            assert [(row['batch_start'],row['batch_count']) for row in windows] == [
                (0,2),(0,64),(64,64),(128,64),(192,64),(0,64),(64,64),(128,64),(192,64)]
    asyncio.run(run())


def test_token_work_preflight_rejects_after_first_window_before_remaining_or_cat(canonical_policy, monkeypatch):
    algorithm = candidate(); calls = []
    class Raw:
        # First32.125MiB/8.4M-element window is admitted; full256-row
        # projection then exceeds unchanged64MiB work reserve before cat.
        async def raw(self): return torch.empty(64,257,512,device='meta')
    class Output:
        async def last_hidden_state(self,**kw): calls.append(kw); return Raw()
    class Vision:
        async def encode_image(self,*a,**kw): return Output()
    monkeypatch.setattr(algorithm.torch,'cat',lambda *a,**kw: (_ for _ in ()).throw(AssertionError('no concat')))
    async def run():
        refs = _sdk.InProcessRefResolver()
        plan = _sdk.ExecutionPlan('token-quota','1','probe',permissions=('raw',))
        rt = _sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
        with _sdk.bind_runtime(rt.refs,rt.ctx,rt.ops):
            with pytest.raises(ValueError,match='64 MiB'):
                await algorithm._encode_tokens(Vision(),images(256,1,1),last=True)
        assert calls == [{'batch_start':0,'batch_count':64}]
    asyncio.run(run())


def test_no_host_encoder_recovery_source_boundary():
    # InProcessRefResolver is trusted and does not enforce raw permissions.
    # The actual guest test below, not this source check, proves denial.
    tree = ast.parse((V2/'secure_vision_algorithms.py').read_text())
    assert not any(isinstance(item,ast.Attribute) and item.attr in ('model','visual','_from_raw','resolve') for item in ast.walk(tree))


def test_native_unchanged_inputs_rng_and_unregistered_release(canonical_policy):
    inputs = dict(image_1=images(2), image_2=images(1), negative_image=images(1), tiles=2)
    saved = copy.deepcopy(inputs); rng = torch.random.get_rng_state().clone()
    asyncio.run(in_process(inputs, encoder()))
    assert torch.equal(rng, torch.random.get_rng_state())
    for key in ('image_1','image_2','negative_image'): assert torch.equal(inputs[key], saved[key])
    root = candidate().__package__
    mapping = sys.modules[root].NODE_CLASS_MAPPINGS
    assert len(mapping) == 49 and 'WanVideoClipVisionEncode' not in mapping


def scratch_probe(tmp_path):
    root = tmp_path/'native-probe'; root.mkdir()
    for name in ('secure_vision_algorithms.py','secure_tensor_nodes.py','secure_scalar_nodes.py'):
        shutil.copyfile(V2/name, root/name)
    shutil.copyfile(V2/'tests/vision_guest_probe.py', root/'__init__.py')
    name = '_jack_native_probe_'+str(id(root))
    spec = importlib.util.spec_from_file_location(name, root/'__init__.py', submodule_search_locations=[str(root)])
    mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod; spec.loader.exec_module(mod)
    return root, mod.NODE_CLASS_MAPPINGS['JackWanNativeVisionProbe']


def guest_cases():
    all_values = cases()
    return [all_values[i] for i in (0,14,32,61,102,173,180,199,219)]


def window_guest_cases():
    return [dict(image_1=images(2),image_2=images(1),negative_image=images(1),
        tiles=tiles,ratio=.25,combine_embeds=mode,strength_1=.5,strength_2=2.,force_offload=True,crop='center')
        for tiles,mode in ((10,'average'),(12,'sum'),(14,'concat'),(16,'batch'))]


def test_real_guest_recording_projection_original_and_fresh_raw_denial(tmp_path, canonical_policy):
    root, cls = scratch_probe(tmp_path)
    fresh = tmp_path/'fresh'; shutil.copytree(root,fresh)
    async def run():
        for runtime_root in (root, fresh):
            cls = sys.modules[candidate(runtime_root).__package__].NODE_CLASS_MAPPINGS['JackWanNativeVisionProbe']
            session = await GuestSession('wan-native-probe',guest_runtime_root=runtime_root).start()
            try:
                for index, inputs in enumerate(guest_cases()):
                    value = encoder(); expected = original().process(encoder(), **copy.deepcopy(inputs))[0]
                    fields = {key:item for key,item in inputs.items() if key in ('image_1','image_2','negative_image')}
                    fields.update(clip_vision=value, options={key:item for key,item in inputs.items() if key not in fields})
                    refs = _sdk.InProcessRefResolver()
                    plan = _sdk.ExecutionPlan('native-guest',str(index),'JackWanNativeVisionProbe',node_module=cls.__module__,
                        input_mode='refs',input_types={'clip_vision':'CLIP_VISION','image_1':'IMAGE','image_2':'IMAGE','negative_image':'IMAGE'},
                        permissions=('raw',), inputs=await _sdk.wrap_inputs(refs,fields,{'clip_vision':'CLIP_VISION','image_1':'IMAGE','image_2':'IMAGE','negative_image':'IMAGE'}),tier='sandbox')
                    rt = _sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                    if index == 0:
                        with pytest.raises(Exception,match='raw|capabilit|permission'):
                            await session.execute(plan,rt,capabilities=())
                        assert not value.model.calls
                    actual = await session.execute(plan,rt,capabilities=('raw',))
                    decoded = await _sdk.unwrap_outputs(refs,actual)
                    equal(expected,decoded.result[0])
                assert session.last_guest_pid not in (None,os.getpid())
            finally: await session.kill()
    asyncio.run(run())


def test_image_b256_admission_actual_guest_no_inference(tmp_path,canonical_policy):
    root, native_cls = scratch_probe(tmp_path)
    cls = sys.modules[native_cls.__module__].NODE_CLASS_MAPPINGS['JackWanImageAdmissionProbe']
    async def run():
        value = encoder(); seen = []
        image = images(256,2,3)
        # Only admission/dispatch is measured here: deterministic host recorder,
        # not canonical preprocessing, projection, model allocation or inference.
        def record(pixels, crop=True):
            seen.append((pixels.clone(),crop))
            return SimpleNamespace(last_hidden_state=None,penultimate_hidden_states=None)
        value.encode_image = record
        refs = _sdk.InProcessRefResolver()
        plan = _sdk.ExecutionPlan('image-admission','1','JackWanImageAdmissionProbe',node_module=cls.__module__,
            input_mode='refs',input_types={'clip_vision':'CLIP_VISION','image':'IMAGE'},permissions=(),tier='sandbox',
            inputs=await _sdk.wrap_inputs(refs,{'clip_vision':value,'image':image}, {'clip_vision':'CLIP_VISION','image':'IMAGE'}))
        rt = _sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
        session = await GuestSession('wan-image-admission',guest_runtime_root=root).start()
        try:
            result = await session.execute(plan,rt,capabilities=())
            assert result.result == (256,)
            assert len(seen) == 1 and torch.equal(seen[0][0],image) and seen[0][1] is True
            assert session.last_guest_pid not in (None,os.getpid())
        finally: await session.kill()
    asyncio.run(run())


def test_real_guest_tile10_to16_bf16_recording_tokens_fresh_raw_denial(tmp_path,canonical_policy):
    root, _ = scratch_probe(tmp_path)
    fresh = tmp_path/'fresh-window'; shutil.copytree(root,fresh)
    async def run():
        for runtime_root in (root,fresh):
            cls = sys.modules[candidate(runtime_root).__package__].NODE_CLASS_MAPPINGS['JackWanNativeVisionProbe']
            session = await GuestSession('wan-window-probe',guest_runtime_root=runtime_root).start()
            try:
                for index,inputs in enumerate(window_guest_cases()):
                    value = recording_encoder(torch.bfloat16)
                    expected = original().process(recording_encoder(torch.bfloat16),**copy.deepcopy(inputs))[0]
                    fields = {key:item for key,item in inputs.items() if key in ('image_1','image_2','negative_image')}
                    fields.update(clip_vision=value,options={key:item for key,item in inputs.items() if key not in fields})
                    refs = _sdk.InProcessRefResolver()
                    types = {'clip_vision':'CLIP_VISION','image_1':'IMAGE','image_2':'IMAGE','negative_image':'IMAGE'}
                    plan = _sdk.ExecutionPlan('window-guest',str(index),'JackWanNativeVisionProbe',node_module=cls.__module__,
                        input_mode='refs',input_types=types,permissions=('raw',),
                        inputs=await _sdk.wrap_inputs(refs,fields,types),tier='sandbox')
                    rt = _sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                    if index==0:
                        with pytest.raises(Exception,match='raw|capabilit|permission'):
                            await session.execute(plan,rt,capabilities=())
                        assert not value.model.calls
                    result = await session.execute(plan,rt,capabilities=('raw',))
                    decoded = await _sdk.unwrap_outputs(refs,result)
                    equal(expected,decoded.result[0])
                    assert [item.shape[0] for item in value.model.calls] == [3]+[inputs['tiles']**2]*3+[1,inputs['tiles']**2]
                assert session.last_guest_pid not in (None,os.getpid())
            finally: await session.kill()
    asyncio.run(run())


def test_public_outer_probe_tokens_reconstruction_not_release_node(tmp_path, canonical_policy, monkeypatch):
    monkeypatch.syspath_prepend(str(CORE))
    import execution
    root, cls = scratch_probe(tmp_path)
    async def run():
        previous = _sdk.providers.execution_backend
        class Backend:
            sessions = []
            async def dispatch(self,plan,local_call,runtime):
                plan.inputs = await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                session = await GuestSession('wan-vision-outer-probe',guest_runtime_root=root).start()
                self.sessions.append(session)
                return await session.execute(plan,runtime,capabilities=('raw',))
        backend = Backend(); _sdk.providers.register_execution_backend(backend)
        try:
            for inputs in guest_cases()[::4]:
                fields = {key:item for key,item in inputs.items() if key in ('image_1','image_2','negative_image')}
                fields.update(clip_vision=encoder(), options={key:item for key,item in inputs.items() if key not in fields})
                expected = original().process(encoder(),**copy.deepcopy(inputs))[0]
                cls.GET_SCHEMA()
                finalized,missing,data = execution.get_input_data(fields,cls,'1',None)
                assert not missing
                result = await execution._async_map_node_over_list(prompt_id='vision-outer',unique_id='1',obj=cls,
                    input_data_all=finalized,func='execute',v3_data=data)
                assert tuple(cls.RETURN_TYPES) == ('WANVIDIMAGE_CLIPEMBEDS',)
                equal(expected,result[0].result[0])
        finally:
            _sdk.providers.register_execution_backend(previous)
            for session in backend.sessions: await session.kill()
    asyncio.run(run())
