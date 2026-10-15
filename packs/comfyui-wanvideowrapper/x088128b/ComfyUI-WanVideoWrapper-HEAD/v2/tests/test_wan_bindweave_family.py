"""Pinned Bindweave CPU math and real public producer/consumer boundary.

Recording CLIP controls scheduling, not trained inference. Every147-ID
release remains pending; resource limits below are local workload narrowings.
"""
import ast
import asyncio
import copy
import hashlib
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
sys.path[:0] = [str(CORE), str(BACKEND)]
os.environ.setdefault('COMFY_CORE_ROOT', str(CORE))
from comfy.cli_args import args
args.cpu = True
from comfy.utils import common_upscale
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb
from comfy_secure_nodes.transport.host import GuestSession

ID = 'WanVideoAddBindweaveEmbeds'
QWEN = 'TextImageEncodeQwenVL'
STUB_SHA = '57246795795118e320926fbbb6be50f7c03c6971b2b5029ac709adef5169ab03'


def load_file(name, path, package=False):
    spec = importlib.util.spec_from_file_location(name, path,
        submodule_search_locations=[str(path.parent)] if package else None)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def current():
    package = load_file('_jack_bindweave_candidate', V2/'__init__.py', True)
    return sys.modules[package.__name__+'.secure_bindweave_nodes']


def original():
    cls = next(x for x in ast.parse((PACK/'nodes.py').read_text()).body
        if isinstance(x, ast.ClassDef) and x.name == ID)
    namespace = {'torch':torch, 'common_upscale':common_upscale,
        'log':logging.getLogger('jack-pinned-bindweave')}
    exec(compile(ast.Module(body=[cls],type_ignores=[]),str(PACK/'nodes.py'),'exec'),namespace)
    return namespace[ID]


def fixture(references=2, length=1, dtype=torch.float32, ref_mask=True, context=6):
    def tensor(shape, offset=0):
        return (torch.arange(__import__('math').prod(shape)).reshape(shape)/97+offset).to(dtype)
    marker = object()
    embeds = {'extra':{'name':'retained', 'model_handle':marker},
        'image_embeds':tensor((4,3,2,3),1), 'mask':tensor((4,2,2,3),2),
        'clip_context':None if context is None else tensor((1,context,2),3),
        'qwenvl_embeds_pos':'overwritten', 'qwenvl_embeds_neg':'overwritten'}
    latents = {'samples':tensor((references,4,length,2,3),4), 'ignored':{'plain':True}}
    masks = tensor((references+1,3,5),5) if ref_mask else None
    return {'embeds':embeds,'reference_latents':latents,'ref_masks':masks}


def equivalent(left, right):
    if isinstance(left,torch.Tensor):
        assert isinstance(right,torch.Tensor)
        assert left.shape == right.shape and left.dtype == right.dtype
        assert torch.equal(left,right)
    elif isinstance(left,dict):
        assert isinstance(right,dict) and list(left) == list(right)
        for key in left: equivalent(left[key],right[key])
    elif isinstance(left,(tuple,list)):
        assert type(left) is type(right) and len(left) == len(right)
        for a,b in zip(left,right): equivalent(a,b)
    else:
        assert left is right or left == right


def math_cases():
    for dtype in (torch.float16,torch.bfloat16,torch.float32,torch.float64):
        for references in range(5):
            for length in (1,2):
                for ref_mask in (False,True):
                    yield fixture(references,length,dtype,ref_mask,
                        (None,0,1027,1028,1029)[references])


def test_exact_schema_and_literal_pinned_math_body():
    module = current()
    cls = module.NODE_CLASS_MAPPINGS[ID]
    source = original()
    schema = cls.GET_SCHEMA()
    assert schema.node_id == ID and schema.category == source.CATEGORY
    specs = source.INPUT_TYPES()
    assert [x.id for x in schema.inputs] == list(specs['required'])+list(specs['optional'])
    for inp in schema.inputs:
        upstream = (specs['required']|specs['optional'])[inp.id]
        assert inp.io_type == upstream[0]
        assert inp.optional == (inp.id in specs['optional'])
        assert inp.tooltip == (upstream[1].get('tooltip') if len(upstream)>1 else None)
    assert [(x.io_type,x.display_name) for x in schema.outputs] == list(zip(source.RETURN_TYPES,source.RETURN_NAMES))
    assert cls.SDK_REFS is True and cls.SDK_PERMISSIONS == ('raw','inspect')
    assert hashlib.sha256((V2/'comfy-api.pyi').read_bytes()).hexdigest() == STUB_SHA
    upstream = next(x for x in ast.parse((PACK/'nodes.py').read_text()).body if isinstance(x,ast.ClassDef) and x.name==ID)
    native = next(x for x in upstream.body if isinstance(x,ast.FunctionDef) and x.name=='add')
    port = next(x for x in ast.parse((V2/'secure_bindweave_nodes.py').read_text()).body if isinstance(x,ast.FunctionDef) and x.name=='bindweave_math')
    for name in ast.walk(port):
        if isinstance(name,ast.Name) and name.id=='_nearest_upscale':name.id='common_upscale'
    assert ast.dump(ast.Module(body=native.body,type_ignores=[])) == ast.dump(ast.Module(body=port.body[1:],type_ignores=[]))


def test_80_exact_cpu_math_shapes_dtypes_masks_context_and_shallow_state():
    module = current()
    count=0
    for inputs in math_cases():
        pos,neg = torch.arange(12).reshape(1,3,4),object()
        inputs.update(qwenvl_embeds_pos=pos,qwenvl_embeds_neg=neg)
        expected = original()().add(**inputs)
        result = module.bindweave_math(**inputs)
        equivalent(expected,result)
        assert result[0]['extra'] is inputs['embeds']['extra']
        assert result[0]['qwenvl_embeds_pos'] is pos and result[0]['qwenvl_embeds_neg'] is neg
        assert inputs['embeds']['qwenvl_embeds_pos']=='overwritten'
        assert result[0]['image_embeds'].untyped_storage().data_ptr()==result[1]['samples'].untyped_storage().data_ptr()
        count+=1
    assert count==80


def test_mixed_dtypes_and_nearest_disabled_branch_match_source():
    module=current()
    for image_dtype,latent_dtype,mask_dtype,ref_dtype in (
            (torch.float16,torch.bfloat16,torch.float64,torch.float16),
            (torch.float64,torch.float32,torch.bfloat16,torch.float32)):
        values=fixture()
        values['embeds']['image_embeds']=values['embeds']['image_embeds'].to(image_dtype)
        values['reference_latents']['samples']=values['reference_latents']['samples'].to(latent_dtype)
        values['embeds']['mask']=values['embeds']['mask'].to(mask_dtype)
        values['ref_masks']=values['ref_masks'].to(ref_dtype)
        equivalent(original()().add(**values),module.bindweave_math(**values))
    for shape in ((2,1,3,5),(2,1,4,3,5)):
        value=torch.arange(__import__('math').prod(shape)).reshape(shape).float()
        equivalent(common_upscale(value,7,2,'nearest','disabled'),module._nearest_upscale(value,7,2,'nearest','disabled'))


def malformed_cases():
    values=fixture(5);yield 'negative pad',values
    values=fixture();values['embeds']['mask']=None;yield 'mask None',values
    values=fixture();del values['embeds']['mask'];yield 'mask absent',values
    values=fixture();values['embeds']['clip_context']=torch.ones(1,2);yield 'context rank',values
    values=fixture();values['ref_masks']=torch.ones(2,1,3,5);yield 'ref masks rank',values
    values=fixture();values['reference_latents']['samples']=torch.ones(2,3,1,2,3);yield 'channel mismatch',values
    values=fixture();values['reference_latents']['samples']=torch.ones(2,4,2,3);yield 'latent rank',values
    values=fixture();values['embeds']['image_embeds']=torch.ones(4,3,2,3,1);yield 'image rank',values
    values=fixture();values['embeds']['mask']=torch.ones(4,2,2,3,1);yield 'mask rank',values
    values=fixture();del values['embeds']['image_embeds'];yield 'missing image',values
    values=fixture();del values['reference_latents']['samples'];yield 'missing samples',values
    values=fixture();values['embeds']=[('a',1)];yield 'list malformed',values


def test_12_native_errors_are_not_repaired_or_dropped():
    module=current()
    for name,inputs in malformed_cases():
        with pytest.raises(Exception) as expected: original()().add(**inputs)
        with pytest.raises(type(expected.value)) as actual: module.bindweave_math(**inputs)
        assert str(actual.value)==str(expected.value),name


def test_projected_allocations_refused_before_any_tensor_construction(monkeypatch):
    module=current()
    values=[]
    x=fixture();x['embeds']['clip_context']=torch.empty(1,0,32768,device='meta');values.append(x)
    x=fixture();x['embeds']['mask']=torch.empty(4,2,512,512,device='meta');values.append(x)
    x=fixture(0,ref_mask=False);x['embeds']['image_embeds']=torch.empty(4,1,512,512,device='meta');values.append(x)
    x=fixture();x['embeds']['image_embeds']=torch.empty(4,1,2048,2048,0,device='meta');values.append(x)
    x=fixture();x['embeds']['mask']=torch.empty(4,1,2048,2048,0,device='meta');values.append(x)
    def forbidden(*args,**kwargs):raise AssertionError('allocation reached before projected refusal')
    for name in ('zeros','ones','cat'):monkeypatch.setattr(module.torch,name,forbidden)
    monkeypatch.setattr(module.F,'interpolate',forbidden)
    for inputs in values:
        with pytest.raises(ValueError,match='projected'):module.bindweave_math(**inputs)
    x=fixture();x['embeds']['extra']='x'*65537
    with pytest.raises(ValueError,match='64 KiB'):module.bindweave_math(**x)


def test_in_process_public_refs_preserve_opaque_metadata_and_aliases():
    async def run():
        cls=current().NODE_CLASS_MAPPINGS[ID]
        inputs=fixture()
        expected=original()().add(**inputs)
        refs=_sdk.InProcessRefResolver()
        wrapped=await _sdk.wrap_inputs(refs,inputs,dict(embeds='WANVIDIMAGE_EMBEDS',reference_latents='LATENT',ref_masks='MASK'))
        with _sdk.bind_runtime(refs,SimpleNamespace(),_sdk.InProcessOps()):
            output=await cls.execute(**wrapped)
        result=(await _sdk.unwrap_outputs(refs,output)).result
        equivalent(expected,result)
        assert result[0]['extra']['model_handle'] is inputs['embeds']['extra']['model_handle']
        assert result[0]['image_embeds'].untyped_storage().data_ptr()==result[1]['samples'].untyped_storage().data_ptr()
    asyncio.run(run())


def test_samples_geometry_existing_limit_before_raw_import(monkeypatch):
    async def run():
        cls=current().NODE_CLASS_MAPPINGS[ID]
        inputs=fixture()
        inputs['reference_latents']['samples']=torch.empty(4,4,1,1025,1025,device='meta')
        refs=_sdk.InProcessRefResolver()
        wrapped=await _sdk.wrap_inputs(refs,{'reference_latents':inputs['reference_latents']},{'reference_latents':'LATENT'})
        inputs['reference_latents']=wrapped['reference_latents']
        async def forbidden(self):raise AssertionError('raw import reached before existing shape bound')
        monkeypatch.setattr(_sdk.TensorRef,'raw',forbidden)
        with _sdk.bind_runtime(refs,SimpleNamespace(),_sdk.InProcessOps()):
            with pytest.raises(ValueError,match='16777216 elements'):await cls.execute(**inputs)
    asyncio.run(run())


def test_direct_math_also_ignores_unused_cyclic_metadata():
    inputs=fixture()
    cycle={};cycle['self']=cycle
    inputs['reference_latents']['unused_cycle']=cycle
    inputs['reference_latents']['unused_oversize_text']='x'*65537
    inputs['reference_latents']['unused_model']=object()
    equivalent(original()().add(**inputs),current().bindweave_math(**inputs))


def test_actual_qwen_bindweave_chain_outer_types_native_errors_and_cap_recovery(tmp_path,monkeypatch):
    monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE','required')
    monkeypatch.syspath_prepend(str(CORE))
    import execution
    qwen=load_file('_jack_bindweave_qwen_control',V2/'tests/test_wan_qwenvl_family.py')
    async def run():
        previous=_sdk.providers.execution_backend
        pids=set()
        try:
            for number in range(2):
                snapshot=PACK.parent;root=V2
                if number:
                    snapshot=tmp_path/'fresh-snapshot';root=snapshot/PACK.name/'v2'
                    shutil.copytree(V2,root)
                loaded=packdb.load_pack(snapshot,mount_name=f'custom_nodes.jack_bindweave_{number}')
                cls=loaded.node_mappings[ID];producer=loaded.node_mappings[QWEN]
                assert tuple(cls.RETURN_TYPES)==('WANVIDIMAGE_EMBEDS','LATENT','MASK')
                session=await GuestSession('jack-wan-bindweave',guest_runtime_root=root).start()
                assert session.sandbox_kind=='seatbelt'
                class Backend:
                    grants=('raw','inspect')
                    async def dispatch(self,plan,local_call,runtime):
                        assert plan.input_mode=='refs'
                        if plan.node_type==ID:
                            assert plan.permissions==('raw','inspect')
                            # Production input_types carries built-in ref kinds,
                            # not custom socket labels. Assert the actual proxy
                            # schema instead; don't fabricate typing in plan.
                            specs={x.id:x.io_type for x in cls.GET_SCHEMA().inputs}
                            assert specs['qwenvl_embeds_pos']==specs['qwenvl_embeds_neg']=='QWENVL_EMBEDS'
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        grants=plan.permissions if plan.node_type==QWEN else self.grants
                        return await session.execute(plan,runtime,capabilities=grants,tenant=f'bindweave-owner-{number}')
                backend=Backend();_sdk.providers.register_execution_backend(backend)
                async def outer(node,inputs):
                    finalized,missing,data=execution.get_input_data(inputs,node,'owner',None)
                    assert not missing
                    result=await execution._async_map_node_over_list('bindweave-outer','owner',node,finalized,'execute',v3_data=data)
                    return result[0].result
                async def recover():
                    inputs=fixture()
                    equivalent(original()().add(**inputs),await outer(cls,inputs))
                try:
                    positive=0
                    for dtype in (torch.float16,torch.bfloat16,torch.float32,torch.float64):
                        clip=qwen.RecordingClip(dtype)
                        pos=(await outer(producer,dict(clip=clip,prompt='Bindweave positive',image=torch.ones(1,2,3,4))))[0]
                        neg=(await outer(producer,dict(clip=qwen.RecordingClip(dtype),prompt='negative')))[0]
                        assert pos is clip.rows[0][0]
                        for references in (0,2,4):
                            inputs=fixture(references,dtype=dtype,ref_mask=references!=4,context=1028 if references==4 else 6)
                            inputs.update(qwenvl_embeds_pos=pos,qwenvl_embeds_neg=neg)
                            expected=original()().add(**inputs)
                            actual=await outer(cls,inputs)
                            equivalent(expected,actual)
                            assert actual[0]['extra']['model_handle'] is inputs['embeds']['extra']['model_handle']
                            assert actual[0]['qwenvl_embeds_pos'] is pos and actual[0]['qwenvl_embeds_neg'] is neg
                            if references==4:
                                assert actual[0]['clip_context'] is inputs['embeds']['clip_context']
                            assert isinstance(actual[1]['samples'],torch.Tensor) and actual[2].dtype==torch.float32
                            assert actual[2].shape==expected[2].shape
                            if positive==0:
                                print('JACK_BINDWEAVE_COMPUTED_OUTPUT_STORAGE',number,
                                    'source_alias=True', 'guest_host_alias='+str(actual[0]['image_embeds'].untyped_storage().data_ptr()==actual[1]['samples'].untyped_storage().data_ptr()),
                                    'value/shape/dtype equality proved; no alias equivalence inferred')
                            positive+=1
                    # Source-native invalid workloads remain failures in the
                    # same real guest, followed by successful recovery.
                    for name,inputs in (('negative pad',fixture(5)),('mask None',fixture())):
                        if name=='mask None':inputs['embeds']['mask']=None
                        with pytest.raises(Exception) as source_error:original()().add(**inputs)
                        with pytest.raises(Exception) as actual_error:await outer(cls,inputs)
                        assert str(source_error.value) in str(actual_error.value)
                        await recover()
                    backend.grants=('inspect',)
                    with pytest.raises(Exception,match='raw.*not granted'):await outer(cls,fixture())
                    backend.grants=('raw','inspect')
                    await recover()
                    large=fixture()
                    large['reference_latents']['samples']=torch.empty(4,4,1,1025,1025,device='meta')
                    with pytest.raises(Exception,match='16777216 elements'):await outer(cls,large)
                    await recover()
                    backend.grants=('raw',)
                    with pytest.raises(Exception,match='inspect.*not granted'):await outer(cls,fixture())
                    backend.grants=('raw','inspect')
                    await recover()
                    # Public samples projection now preserves source success
                    # without touching unrelated opaque/cyclic LATENT metadata.
                    extra_latent=fixture();extra_latent['reference_latents']['unused_model']=object()
                    cycle={};cycle['self']=cycle
                    extra_latent['reference_latents']['unused_cycle']=cycle
                    expected=original()().add(**extra_latent)
                    equivalent(expected,await outer(cls,extra_latent))
                    print('JACK_BINDWEAVE_LATENT_PROJECTION_CLOSED',number,
                        'source/candidate ignore unused_model+cyclic metadata; samples-only public projection succeeds')
                    # Unregistered controls prove zero-cap projection, separate
                    # raw denial and unchanged whole opaque-export refusal.
                    refs=_sdk.InProcessRefResolver()
                    wrapped=await _sdk.wrap_inputs(refs,{'latent':extra_latent['reference_latents']},{'latent':'LATENT'})
                    runtime=_sdk.Runtime(refs=refs,ctx=SimpleNamespace(),ops=_sdk.InProcessOps())
                    probe_name=cls.__module__.rsplit('.',1)[0]+'.tests.bindweave_latent_boundary_probe'
                    load_file(probe_name,root/'tests/bindweave_latent_boundary_probe.py')
                    plan=_sdk.ExecutionPlan('bindweave-boundary','owner','JackBindweaveLatentProbe',node_module=probe_name,
                        inputs={'latent':wrapped['latent'],'mode':'project'},permissions=())
                    projected=await session.execute(plan,runtime,capabilities=(),tenant=f'bindweave-owner-{number}')
                    assert projected.result[0].kind=='TENSOR'
                    assert await refs.resolve(projected.result[0]) is extra_latent['reference_latents']['samples']
                    plan.inputs['mode']='raw'
                    with pytest.raises(Exception,match='raw.*not granted'):await session.execute(plan,runtime,capabilities=(),tenant=f'bindweave-owner-{number}')
                    plan.inputs['mode']='whole'
                    # Use only the opaque extra here: preserve the old exact
                    # object refusal, without asking the exporter to recurse a cycle.
                    ordinary=fixture();ordinary['reference_latents']['unused_model']=object()
                    plan.inputs['latent']=(await _sdk.wrap_inputs(refs,{'latent':ordinary['reference_latents']},{'latent':'LATENT'}))['latent']
                    with pytest.raises(Exception,match='object') as refused:
                        await session.execute(plan,runtime,capabilities=('raw',),tenant=f'bindweave-owner-{number}')
                    print('JACK_BINDWEAVE_WHOLE_OPAQUE_REFUSAL',number,type(refused.value).__name__,str(refused.value))
                    plan.inputs['mode']='project'
                    projected=await session.execute(plan,runtime,capabilities=(),tenant=f'bindweave-owner-{number}')
                    assert await refs.resolve(projected.result[0]) is ordinary['reference_latents']['samples']
                    pids.add(session.pid)
                    print('JACK_BINDWEAVE_REQUIRED_GUEST',number,session.pid,
                        f'{positive} chained math positives; 8 Qwen projections; opaque+cyclic LATENT positive; raw+inspect denial; pre-read geometry refusal; 2 native failures; 5 consumer recoveries; zero-cap samples+raw denial+whole refusal+projection recovery')
                finally:await session.kill()
            assert len(pids)==2 and os.getpid() not in pids
        finally:_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
