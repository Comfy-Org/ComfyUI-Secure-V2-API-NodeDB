"""Pinned workflow/scalar helpers: exact algorithms, bounds, fresh guest and outer output."""
import ast
import asyncio
import copy
import importlib.util
import json
import os
import re
import typing
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import torch

sys.dont_write_bytecode=True;sys.argv=['ned-comfyroll-tensors','--cpu']
CORE=Path(os.environ['COMFY_CORE_ROOT']);sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
spec=importlib.util.spec_from_file_location('ned_comfyroll_tensors_pack',V2/'__init__.py',submodule_search_locations=[str(V2)])
NEW=importlib.util.module_from_spec(spec);sys.modules[spec.name]=NEW;spec.loader.exec_module(NEW)
LEDGER=json.loads((V2/'tensor-draft-ledger.json').read_text());OLD={}
icons=ast.literal_eval(ast.parse((PACK/'categories.py').read_text()).body[0].value)
TREES={name:ast.parse((PACK/'nodes'/name).read_text()) for name in {row['source_file'] for row in LEDGER.values()}}
for node_id,row in LEDGER.items():
    tree=TREES[row['source_file']]
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==row['class']);ns={'icons':icons,'any_type':'*','re':re,'torch':torch,'tg':typing}
    exec(compile(ast.Module(body=[copy.deepcopy(cls)],type_ignores=[]),'pinned-pipes','exec'),ns);OLD[node_id]=ns[row['class']]

def args_for(node_id,**changes):
    args={}
    for items in LEDGER[node_id]['source_inputs'].values():
        for key,spec in items.items():
            options=spec[1] if len(spec)>1 else {}
            args[key]=options['default'] if 'default' in options else spec[0][0] if isinstance(spec[0],list) else None
    args.update(changes);return args

def oracle(node_id,args):
    obj=OLD[node_id]();return getattr(obj,obj.FUNCTION)(**args)

def outcome(fn):
    try:
        result=fn();return ('value',result.result if hasattr(result,'result') else result)
    except Exception as exc:return ('error',type(exc),str(exc))

def exact(a,b):
    assert type(a) is type(b)
    if isinstance(b,(list,tuple)):
        assert len(a)==len(b)
        for x,y in zip(a,b):exact(x,y)
    elif isinstance(b,dict):
        assert set(a)==set(b)
        for key in b:exact(a[key],b[key])
    elif isinstance(b,torch.Tensor):
        assert a.dtype==b.dtype and a.shape==b.shape
        assert torch.equal(a.contiguous().reshape(-1).view(torch.uint8),b.contiguous().reshape(-1).view(torch.uint8))
    elif isinstance(b,SimpleNamespace):assert a is b
    else:assert a==b



def differential(node_id,args):
    expected=oracle(node_id,copy.deepcopy(args))
    actual=NEW.NODE_CLASS_MAPPINGS[node_id].execute(**copy.deepcopy(args)).result
    exact(actual,expected)

@pytest.mark.parametrize('dtype',[torch.float32,torch.float16,torch.bfloat16,torch.float64])
@pytest.mark.parametrize('batch',[-2,0,1,2,4])
def test_latent_batch_repeat_exact_drops_metadata_and_preserves_dtype(dtype,batch):
    samples=torch.arange(48,dtype=torch.float32).reshape(2,4,2,3).to(dtype).transpose(2,3)
    args=dict(latent={'samples':samples,'noise_mask':torch.ones(2,3,2),'metadata':'dropped'},batch_size=batch)
    differential('CR Latent Batch Size',args)
    assert set(NEW.NODE_CLASS_MAPPINGS['CR Latent Batch Size'].execute(**args).result[0])=={'samples'}

@pytest.mark.parametrize('batch',[0,1,2,4])
@pytest.mark.parametrize('dtype',[torch.float32,torch.float16,torch.uint8])
def test_debatch_order_single_batch_views_dtype_and_list_axis(batch,dtype):
    frames=torch.arange(batch*3*4*3,dtype=torch.float32).reshape(batch,3,4,3).to(dtype)
    differential('CR Debatch Frames',{'frames':frames})
    outputs=NEW.NODE_CLASS_MAPPINGS['CR Debatch Frames'].execute(frames=frames).result[0]
    assert len(outputs)==batch and all(t.shape==(1,3,4,3) for t in outputs)
    if batch:
        outputs[0][0,0,0,0]=12
        assert frames[0,0,0,0]==12  # pinned local view semantics, not cross-guest alias claim

@pytest.mark.parametrize('method',['Combine','Average','Concatenate'])
@pytest.mark.parametrize('lengths',[(2,3),(4,2),(2,2)])
@pytest.mark.parametrize('strength',[-1.,0.,.37,1.,2.])
@pytest.mark.parametrize('dtype',[torch.float32,torch.float16])
def test_conditioning_mixer_padding_truncation_order_pooled_metadata(method,lengths,strength,dtype):
    first=[[torch.arange(lengths[0]*4,dtype=torch.float32).reshape(1,lengths[0],4).to(dtype),{'pooled_output':torch.ones(1,4,dtype=dtype)*.4,'ignored_from':'first'}],
           [torch.full((1,1,4),99,dtype=dtype),{}]]
    second=[[torch.full((1,lengths[1],4),.7,dtype=dtype),{'pooled_output':torch.ones(1,4,dtype=dtype)*.8,'strength':.23,'area':(2,3,4,5)}],
            [torch.full((1,lengths[1],4),.3,dtype=dtype),{'target':'second','mask':torch.ones(1,2,3)}]]
    differential('CR Conditioning Mixer',dict(conditioning_1=first,conditioning_2=second,mix_method=method,average_strength=strength))

@pytest.mark.parametrize('first,second',[([],[]),([],[[torch.ones(1,2,3),{}]]),([[torch.ones(1,2,3),{}]],[]),([[torch.ones(1,2,3),{}]],[[torch.ones(1,2,4),{}]])])
@pytest.mark.parametrize('method',['Combine','Average','Concatenate','invalid'])
def test_conditioning_empty_and_malformed_native_outcomes(first,second,method):
    args=dict(conditioning_1=first,conditioning_2=second,mix_method=method,average_strength=.5)
    exact(outcome(lambda:NEW.NODE_CLASS_MAPPINGS['CR Conditioning Mixer'].execute(**copy.deepcopy(args))),outcome(lambda:oracle('CR Conditioning Mixer',copy.deepcopy(args))))

@pytest.mark.parametrize('dtype',[torch.float32,torch.float16,torch.bfloat16])
@pytest.mark.parametrize('method',['lerp','slerp','invalid'])
@pytest.mark.parametrize('weight',[0.,.37,1.])
def test_latent_interpolation_exact_native_formula_and_metadata(dtype,method,weight):
    first={'samples':torch.linspace(.01,.2,48).reshape(2,4,2,3).to(dtype),'noise_mask':torch.ones(2,2,3),'batch_index':[7,8]}
    second={'samples':torch.linspace(.03,.3,48).reshape(2,4,2,3).to(dtype),'unused':'second'}
    args=dict(latent1=first,latent2=second,weight=weight,method=method)
    differential('CR Interpolate Latents',args)
    if method=='lerp':
        original=first['samples'].clone()
        output=NEW.NODE_CLASS_MAPPINGS['CR Interpolate Latents'].execute(**args).result[0]
        assert output['samples'] is first['samples']
        assert torch.equal(first['samples'],torch.lerp(original,second['samples'],weight))

@pytest.mark.parametrize('node_id',list(LEDGER))
def test_exact_schema_raw_value_mode_and_output_list_flags(node_id):
    row=LEDGER[node_id];cls=NEW.NODE_CLASS_MAPPINGS[node_id];schema=cls.GET_SCHEMA()
    assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS==('raw',)
    assert schema.node_id==node_id and schema.display_name==row['display_name'] and schema.category==row['category']
    assert [o.io_type for o in schema.outputs]==row['return_types']
    assert [o.display_name for o in schema.outputs]==row['return_names']
    assert [o.is_output_list for o in schema.outputs]==row['output_is_list']
    flat={key:(group,spec) for group,items in row['source_inputs'].items() for key,spec in items.items()}
    assert [i.id for i in schema.inputs]==list(flat)
    for inp in schema.inputs:
        group,source=flat[inp.id];assert inp.optional==(group=='optional')
        if isinstance(source[0],list):assert inp.options==source[0]
        else:assert inp.io_type==source[0]
        for key,value in (source[1] if len(source)>1 else {}).items():assert inp.as_dict()[key]==value

def test_preallocation_container_batch_output_bounds(monkeypatch):
    u=NEW.secure_tensors
    def deny(*args,**kwargs):raise AssertionError('tensor operation ran before preflight')
    monkeypatch.setattr(u.torch,'cat',deny)
    with pytest.raises(ValueError,match='multiplier'):
        u.CR_LatentBatchSize.execute(latent={'samples':torch.ones(1,4,2,3)},batch_size=65)
    with pytest.raises(ValueError,match='projected'):
        u.CR_LatentBatchSize.execute(latent={'samples':torch.empty((1,4,256,256),device='meta')},batch_size=64)
    with pytest.raises(ValueError,match='inputs'):
        u.CR_DebatchFrames.execute(frames=torch.empty((1,4096,4096,3),device='meta'))
    with pytest.raises(ValueError,match='Frame batch'):
        u.CR_DebatchFrames.execute(frames=torch.empty((65,1,1,3)))
    with pytest.raises(ValueError,match='container'):
        u.CR_ConditioningMixer.execute(conditioning_1=[None]*4097,conditioning_2=[],mix_method='Combine',average_strength=.5)
    with pytest.raises(ValueError,match='finite'):
        u.CR_InterpolateLatents.execute(latent1={},latent2={},method='lerp',weight=float('nan'))
    with pytest.raises(ValueError,match='projected'):
        u.CR_ConditioningMixer.execute(conditioning_1=[[torch.ones(1,1,1),{'pooled_output':torch.empty((1,2048,2048),device='meta')}]],conditioning_2=[[torch.ones(1,1,1),{}] for _ in range(8)],mix_method='Average',average_strength=.5)
    with pytest.raises(ValueError,match='metadata text'):
        u.CR_LatentBatchSize.execute(latent={'samples':torch.ones(1,4,1,1),'x':'x'*150000,'y':'y'*150000},batch_size=1)

def test_source_slerp_singularities_and_lerp_malformed_shape_dtype_outcomes():
    for first,second,method in [(torch.zeros(1,4,2,3),torch.zeros(1,4,2,3),'slerp'),(torch.ones(1,4,2,3),torch.ones(1,4,2,3),'slerp'),(torch.ones(1,4,2,3),torch.ones(1,4,3,2),'lerp'),(torch.ones(1,4,2,3),torch.ones(1,4,2,3,dtype=torch.float16),'lerp')]:
        args=dict(latent1={'samples':first},latent2={'samples':second},weight=.3,method=method)
        exact(outcome(lambda:NEW.NODE_CLASS_MAPPINGS['CR Interpolate Latents'].execute(**copy.deepcopy(args))),outcome(lambda:oracle('CR Interpolate Latents',copy.deepcopy(args))))

def test_all_four_actual_guest_outer_raw_denial_output_types_and_fresh_reconstruction():
    import execution
    from comfy_secure_nodes.transport import wire
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for render in range(2):
                session=await GuestSession('ned-comfyroll-tensors-'+str(render),guest_runtime_root=V2).start()
                class Backend:
                    caps=('raw',)
                    async def dispatch(self,plan,local_call,runtime):
                        assert plan.input_mode=='values'
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=self.caps)
                backend=Backend();_sdk.providers.register_execution_backend(backend)
                valid={
                  'CR Latent Batch Size':dict(latent={'samples':torch.linspace(0,1,48).reshape(2,4,2,3),'noise_mask':torch.ones(2,2,3)},batch_size=3),
                  'CR Debatch Frames':dict(frames=torch.linspace(0,1,72).reshape(2,3,4,3)),
                  'CR Conditioning Mixer':dict(conditioning_1=[[torch.ones(1,2,4),{'pooled_output':torch.ones(1,4)}]],conditioning_2=[[torch.ones(1,3,4)*.3,{'area':(2,3,4,5),'pooled_output':torch.ones(1,4)*.7}]],mix_method='Average',average_strength=.37),
                  'CR Interpolate Latents':dict(latent1={'samples':torch.ones(1,4,2,3)*.02,'noise_mask':torch.ones(1,2,3)},latent2={'samples':torch.ones(1,4,2,3)*.08},weight=.3,method='lerp')}
                try:
                    for node_id,args in valid.items():
                        expected=oracle(node_id,copy.deepcopy(args));cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA()
                        out=await execution._async_map_node_over_list(prompt_id='tensor-workflow-'+str(render),unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                        exact(out[0].result,expected)
                        backend.caps=()
                        with pytest.raises(wire.WireError,match='raw'):
                            await execution._async_map_node_over_list(prompt_id='tensor-denial-'+str(render),unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                        backend.caps=('raw',)
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(previous)
        assert pids[0]!=pids[1]
    asyncio.run(run())

def test_production_dispatch_tensor_algorithms_outer_list_merge_and_isolated_input_mutation(monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        previous=_sdk.providers.execution_backend
        session=await GuestSession('ned-comfyroll-production-tensors',guest_runtime_root=V2).start()
        backend=CloudExecutionBackend()
        monkeypatch.setattr(backend,'_is_sandbox',lambda plan:True)
        async def session_for(*args,**kwargs):return session
        monkeypatch.setattr(backend.guests,'session_for',session_for)
        _sdk.providers.register_execution_backend(backend)
        try:
            frames=torch.linspace(0,1,72).reshape(2,3,4,3)
            first={'samples':torch.ones(1,4,2,3)*.02,'noise_mask':torch.ones(1,2,3)}
            original=first['samples'].clone()
            cases={
                'CR Debatch Frames':{'frames':frames},
                'CR Latent Batch Size':{'latent':first,'batch_size':2},
                'CR Interpolate Latents':{'latent1':first,'latent2':{'samples':torch.ones(1,4,2,3)*.08},'weight':.3,'method':'lerp'},
                'CR Conditioning Mixer':{'conditioning_1':[[torch.ones(1,2,4),{'pooled_output':torch.ones(1,4)}]],'conditioning_2':[[torch.ones(1,3,4)*.3,{'area':(2,3,4,5)}]],'average_strength':.37,'mix_method':'Average'}}
            for node_id,args in cases.items():
                expected=oracle(node_id,copy.deepcopy(args));cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA()
                result=await execution._async_map_node_over_list(prompt_id='production-tensors',unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                result=await execution.resolve_map_node_over_list_results(result)
                exact(result[0].result,expected)
                if node_id=='CR Debatch Frames':
                    # Public execution output axis, not merely io.NodeOutput inspection.
                    values,ui,has_subgraph=execution.get_output_from_returns(result,cls)
                    assert not has_subgraph
                    assert len(values[0])==2
                    for index,item in enumerate(values[0]):assert torch.equal(item,frames[index:index+1])
                if node_id=='CR Interpolate Latents':
                    assert torch.equal(first['samples'],original)
                    assert not torch.equal(result[0].result[0]['samples'],original)
                    assert result[0].result[0]['samples'] is not first['samples']
            assert session.last_guest_pid not in (None,os.getpid())
        finally:await session.kill();await backend.shutdown();_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
