"""Exact pipe/scalar math; opaque/tensor identity through actual guest/outer executor."""
import ast
import asyncio
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import torch

sys.dont_write_bytecode=True;sys.argv=['ned-comfyroll-pipes','--cpu']
CORE=Path(os.environ['COMFY_CORE_ROOT']);sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
spec=importlib.util.spec_from_file_location('ned_comfyroll_pipes_pack',V2/'__init__.py',submodule_search_locations=[str(V2)])
NEW=importlib.util.module_from_spec(spec);sys.modules[spec.name]=NEW;spec.loader.exec_module(NEW)
LEDGER=json.loads((V2/'pipe-draft-ledger.json').read_text());OLD={}
icons=ast.literal_eval(ast.parse((PACK/'categories.py').read_text()).body[0].value)
for node_id,row in LEDGER.items():
    tree=ast.parse((PACK/'nodes'/row['source_file']).read_text())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==row['class']);ns={'icons':icons,'any_type':'*'}
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
    elif isinstance(b,torch.Tensor):assert a.dtype==b.dtype and a.shape==b.shape and torch.equal(a,b)
    elif isinstance(b,SimpleNamespace):assert a is b
    else:assert a==b

@pytest.mark.parametrize('node_id',list(LEDGER))
def test_defaults_native_errors_and_scalar_type_quirks(node_id):
    args=args_for(node_id)
    exact(outcome(lambda:NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args)),outcome(lambda:oracle(node_id,args)))

GRADIENTS=['CR Gradient Integer','CR Gradient Float','CR Increment Integer','CR Increment Float']
@pytest.mark.parametrize('node_id',GRADIENTS)
@pytest.mark.parametrize('frame',[-1,0,1,2,3,5,6,15])
@pytest.mark.parametrize('duration',[0,1,4])
def test_scalar_piecewise_frames_and_native_zero_duration(node_id,frame,duration):
    args=args_for(node_id,start_value=7 if 'Integer' in node_id else 7.25,start_frame=1,frame_duration=duration,current_frame=frame)
    if 'end_value' in args:args['end_value']=-3 if 'Integer' in node_id else -3.5
    if 'step' in args:args['step']=-2 if 'Integer' in node_id else -.25
    exact(outcome(lambda:NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args)),outcome(lambda:oracle(node_id,args)))

@pytest.mark.parametrize('size,in_id,out_id,keys',[(4,'CR Data Bus In','CR Data Bus Out',['any'+str(i) for i in range(1,5)]),(8,'CR 8 Channel In','CR 8 Channel Out',['ch'+str(i) for i in range(1,9)])])
@pytest.mark.parametrize('replacement',[None,0,False,'',('a','b')])
def test_bus_updates_falsy_vs_none_and_tuple_order(size,in_id,out_id,keys,replacement):
    args={'pipe':tuple(range(size)),keys[0]:replacement,keys[-1]:'last'}
    actual=NEW.NODE_CLASS_MAPPINGS[in_id].execute(**args).result;expected=oracle(in_id,args)
    exact(actual,expected)
    exact(NEW.NODE_CLASS_MAPPINGS[out_id].execute(pipe=actual[0]).result,oracle(out_id,{'pipe':expected[0]}))

@pytest.mark.parametrize('node_id',['CR Data Bus Out','CR 8 Channel Out','CR Module Input','CR Module Output','CR Image Pipe Edit','CR Image Pipe Out'])
@pytest.mark.parametrize('pipe',[(),(1,2),None,'ab'])
def test_malformed_pipeline_native_cardinality_errors(node_id,pipe):
    args={'pipe':pipe}
    exact(outcome(lambda:NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args)),outcome(lambda:oracle(node_id,args)))

@pytest.mark.parametrize('node_id',list(LEDGER))
def test_exact_schema_outputnode_metadata_zero_authority(node_id):
    row=LEDGER[node_id];cls=NEW.NODE_CLASS_MAPPINGS[node_id];schema=cls.GET_SCHEMA()
    assert cls.SDK_REFS is True and cls.SDK_PERMISSIONS==()
    assert schema.node_id==node_id and schema.display_name==row['display_name'] and schema.category==row['category'] and schema.is_output_node==row['is_output_node']
    assert [o.io_type for o in schema.outputs]==row['return_types'] and [o.display_name for o in schema.outputs]==row['return_names']
    flat={key:(group,spec) for group,items in row['source_inputs'].items() for key,spec in items.items()}
    assert [i.id for i in schema.inputs]==list(flat)
    for inp in schema.inputs:
        group,source=flat[inp.id];assert inp.optional==(group=='optional')
        if isinstance(source[0],list):assert inp.options==source[0]
        else:assert inp.io_type==source[0]
        for key,value in (source[1] if len(source)>1 else {}).items():assert inp.as_dict()[key]==value

def test_workload_and_nonfinite_fail_before_routing():
    with pytest.raises(ValueError,match='item workload'):NEW.NODE_CLASS_MAPPINGS['CR Data Bus In'].execute(any1=['x']*17000)
    with pytest.raises(ValueError,match='finite'):NEW.NODE_CLASS_MAPPINGS['CR Gradient Float'].execute(**args_for('CR Gradient Float',start_value=float('inf')))
    with pytest.raises(ValueError,match='nesting'):NEW.NODE_CLASS_MAPPINGS['CR Data Bus In'].execute(any1=[[[[[[[[[[0]]]]]]]]]])

def test_all_fifteen_actual_guest_outer_pipes_model_tensor_identity_and_fresh_workflow():
    import execution
    def deny(*args,**kwargs):raise AssertionError('Pipe must not invoke model methods')
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for render in range(2):
                session=await GuestSession('ned-comfyroll-pipes-'+str(render),guest_runtime_root=V2).start()
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):return await session.execute(plan,runtime,capabilities=())
                _sdk.providers.register_execution_backend(Backend())
                model=SimpleNamespace(model_options={},load_device='cpu');clip=SimpleNamespace(tokenize=deny);vae=SimpleNamespace(encode=deny,decode=deny)
                image=torch.full((1,3,4,3),.25);latent={'samples':torch.full((1,4,2,3),.5)};positive=[[torch.ones(1,2,3),{}]];negative=[[torch.zeros(1,2,3),{}]]
                module=(model,positive,negative,latent,vae,clip,{'recording':'CONTROL_NET'},image,123)
                imagepipe=(image,4,3,1.5)
                valid={
                  'CR Data Bus In':dict(pipe=(model,clip,image,0),any4=False),
                  'CR Data Bus Out':dict(pipe=(model,clip,image,False)),
                  'CR 8 Channel In':dict(pipe=tuple(range(8)),ch1=image,ch8=clip),
                  'CR 8 Channel Out':dict(pipe=(image,clip,model,vae,None,0,'text',False)),
                  'CR Module Pipe Loader':dict(zip(('model','pos','neg','latent','vae','clip','controlnet','image','seed'),module)),
                  'CR Module Input':dict(pipe=module),
                  'CR Module Output':dict(pipe=module,seed=0,clip=clip),
                  'CR Image Pipe In':dict(image=image,width=4,height=3,upscale_factor=1.5),
                  'CR Image Pipe Edit':dict(pipe=imagepipe,width=0),
                  'CR Image Pipe Out':dict(pipe=imagepipe),
                  'CR Pipe Switch':dict(Input=2,pipe1=imagepipe,pipe2=module)}
                try:
                    for node_id in LEDGER:
                        args=valid[node_id] if node_id in valid else json.loads(json.dumps(args_for(node_id,current_frame=1)))
                        expected=oracle(node_id,args);cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA()
                        out=await execution._async_map_node_over_list(prompt_id='pipe-workflow-'+str(render),unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                        exact(out[0].result,expected)
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(previous)
        assert pids[0]!=pids[1]
    asyncio.run(run())
