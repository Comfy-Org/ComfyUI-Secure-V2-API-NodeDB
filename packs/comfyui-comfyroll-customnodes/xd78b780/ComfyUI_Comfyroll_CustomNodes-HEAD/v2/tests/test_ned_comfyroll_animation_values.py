"""Pinned animation math and opaque image-ref routing; approved flat-list repair is explicit."""
import ast
import asyncio
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest
import torch

sys.dont_write_bytecode=True;sys.argv=['ned-comfyroll-animation-values','--cpu']
CORE=Path(os.environ['COMFY_CORE_ROOT']);sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
spec=importlib.util.spec_from_file_location('ned_comfyroll_animation_values_pack',V2/'__init__.py',submodule_search_locations=[str(V2)])
NEW=importlib.util.module_from_spec(spec);sys.modules[spec.name]=NEW;spec.loader.exec_module(NEW)
LEDGER=json.loads((V2/'animation-values-draft-ledger.json').read_text());OLD={}
icons=ast.literal_eval(ast.parse((PACK/'categories.py').read_text()).body[0].value)
for node_id,row in LEDGER.items():
    source=PACK/'nodes'/row['source_file'];tree=ast.parse(source.read_text());scope={'icons':icons}
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==row['class'])
    exec(compile(ast.Module(body=[copy.deepcopy(cls)],type_ignores=[]),str(source),'exec'),scope);OLD[node_id]=scope[row['class']]

def args_for(node_id,**changes):
    args={}
    for group,items in LEDGER[node_id]['source_inputs'].items():
        for key,spec in items.items():
            options=spec[1] if len(spec)>1 else {}
            args[key]=options['default'] if 'default' in options else spec[0][0] if isinstance(spec[0],list) else None
    if node_id=='CR Simple Prompt List Keyframes':args['simple_prompt_list']=['first','next','last']
    if node_id=='CR Prompt List Keyframes':args['prompt_list']=[('first','Default','Default','Default',7,3),('next','Default','Default','Default',13,99)]
    if node_id.startswith('CR Cycle'):
        args['current_frame']=0
        if 'Text' in node_id:
            if 'text_list' in args:args['text_list']=[('a','first'),('b','next'),('c','last')]
            else:args.update(text_1='first',text_2='next',text_3='',text_4='',text_5='last')
        else:
            images=[torch.full((1,3,5,3),i/3) for i in range(3)]
            if 'image_list' in args:args['image_list']=[('image-'+str(i),v) for i,v in enumerate(images)]
            else:args.update(image_1=images[0],image_2=images[1],image_list_simple=[images[2]])
    if node_id=='CR Image List':args.update(image_1=torch.full((1,3,5,3),.3),alias1='first',image_list=[('old',torch.full((1,3,5,3),.7))])
    args.update(changes);return args

def exact(a,b):
    assert type(a) is type(b)
    if isinstance(b,(list,tuple)):
        assert len(a)==len(b)
        for x,y in zip(a,b):exact(x,y)
    elif isinstance(b,dict):
        assert set(a)==set(b)
        for key in b:exact(a[key],b[key])
    elif isinstance(b,torch.Tensor):assert a.dtype==b.dtype and a.shape==b.shape and torch.equal(a,b)
    else:assert a==b

def oracle(node_id,args):
    obj=OLD[node_id]();return getattr(obj,obj.FUNCTION)(**args)

def outcome(fn):
    try:
        value=fn();return 'value',value.result if hasattr(value,'result') else value
    except Exception as exc:return 'error',type(exc),str(exc)

def parity(node_id,args):
    exact(outcome(lambda:NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args)),outcome(lambda:oracle(node_id,args)))

@pytest.mark.parametrize('text',['','first','\n','é💥<>&"','a\nb','None'])
@pytest.mark.parametrize('stack',[None,[],['old','',None],('old','second')])
def test_simple_prompt_stack_blank_falsy_literals_and_existing_order(text,stack):
    parity('CR Simple Prompt List',args_for('CR Simple Prompt List',prompt_1=text,prompt_2='',prompt_3='next',simple_prompt_list=stack))

@pytest.mark.parametrize('prompts',[[],['a'],['a','b'],['','é"<>\n'],[None],[123]])
@pytest.mark.parametrize('interval',[-2,0,1,13])
@pytest.mark.parametrize('loops',[-1,0,1,3])
def test_simple_keyframes_interval_loop_spaces_truncation_native_types(prompts,interval,loops):
    parity('CR Simple Prompt List Keyframes',args_for('CR Simple Prompt List Keyframes',simple_prompt_list=prompts,keyframe_interval=interval,loops=loops,keyframe_format='unknown'))

@pytest.mark.parametrize('rows',[[],[('a','x','y','z',0,3),('b','x','y','z',7,99)],[('a','x','y','z',13,0),('quoted "\n','x','y','z',-2,-1)],[('bad',)],[(None,'x','y','z',7,1)]])
@pytest.mark.parametrize('format',['Deforum','CR','unknown'])
def test_tuple_keyframes_forced_format_ignored_loops_native_cardinality(rows,format):
    parity('CR Prompt List Keyframes',args_for('CR Prompt List Keyframes',prompt_list=rows,keyframe_format=format))

@pytest.mark.parametrize('text',['','not-json','"0": "hello"','<>&"\n💥'])
@pytest.mark.parametrize('format',['Deforum','CR','unknown'])
def test_keyframe_list_is_literal_passthrough_not_json_parser(text,format):
    parity('CR Keyframe List',args_for('CR Keyframe List',keyframe_list=text,keyframe_format=format))

CYCLERS=['CR Cycle Text','CR Cycle Text Simple','CR Cycle Images','CR Cycle Images Simple']
@pytest.mark.parametrize('node_id',CYCLERS)
@pytest.mark.parametrize('frame',[-1,0,1,29,30,31,99,0.0,1.5])
@pytest.mark.parametrize('interval',[0,1,30])
@pytest.mark.parametrize('loops',[-1,0,1,3])
def test_all_four_cyclers_frame_boundaries_floor_modulo_and_native_empty_float_index(node_id,frame,interval,loops):
    parity(node_id,args_for(node_id,current_frame=frame,frame_interval=interval,loops=loops))

@pytest.mark.parametrize('node_id',CYCLERS)
@pytest.mark.parametrize('mode',['Sequential','Off','unknown'])
def test_mode_branch_none_is_not_synthesized_output(node_id,mode):
    parity(node_id,args_for(node_id,mode=mode))

@pytest.mark.parametrize('node_id',CYCLERS)
def test_declared_float_INT_defaults_preserve_native_failure_not_usable_default(node_id):
    args=args_for(node_id);args['current_frame']=LEDGER[node_id]['source_inputs']['required']['current_frame'][1]['default']
    assert type(args['current_frame']) is float
    parity(node_id,args);assert outcome(lambda:oracle(node_id,args))[0]=='error'

@pytest.mark.parametrize('alias',[None,'','same','<>&"💥'])
@pytest.mark.parametrize('present',[(False,False),(True,False),(False,True),(True,True)])
def test_image_list_alias_tuple_order_none_and_identity(alias,present):
    first=torch.full((1,3,5,3),.25);second=torch.full((1,3,5,3),.75)
    args=args_for('CR Image List',image_1=first if present[0] else None,image_2=second if present[1] else None,alias1=alias,alias2=alias)
    parity('CR Image List',args)
    result=NEW.NODE_CLASS_MAPPINGS['CR Image List'].execute(**args).result
    if present[0]:assert result[0][1][1] is first
    if present[1]:assert result[0][-1][1] is second

@pytest.mark.parametrize('node_id',list(LEDGER))
def test_exact_schema_metadata_types_defaults_options_and_zero_authority(node_id):
    row=LEDGER[node_id];cls=NEW.NODE_CLASS_MAPPINGS[node_id];schema=cls.GET_SCHEMA()
    assert cls.SDK_REFS is True and cls.SDK_PERMISSIONS==()
    assert schema.node_id==node_id and schema.display_name==row['display_name'] and schema.category==row['category']
    assert [o.io_type for o in schema.outputs]==row['return_types'] and [o.display_name for o in schema.outputs]==row['return_names']
    flat={k:(group,value) for group,items in row['source_inputs'].items() for k,value in items.items()}
    assert [i.id for i in schema.inputs]==list(flat)
    assert json.loads(json.dumps(OLD[node_id].INPUT_TYPES()))==row['source_inputs']
    for inp in schema.inputs:
        group,source=flat[inp.id];assert inp.optional==(group=='optional')
        if isinstance(source[0],list):assert inp.options==source[0]
        else:assert inp.io_type==source[0]
        for k,value in (source[1] if len(source)>1 else {}).items():assert inp.as_dict()[k]==value
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

def test_projected_loop_and_keyframe_text_bounds_before_native_materialization():
    with pytest.raises(ValueError,match='bound'):
        NEW.NODE_CLASS_MAPPINGS['CR Cycle Text'].execute(**args_for('CR Cycle Text',text_list=[('a','text')]*256,loops=1000))
    with pytest.raises(ValueError,match='bound'):
        NEW.NODE_CLASS_MAPPINGS['CR Simple Prompt List Keyframes'].execute(**args_for('CR Simple Prompt List Keyframes',simple_prompt_list=['x'*4096]*3,loops=100))
    with pytest.raises(ValueError,match='bound'):
        NEW.NODE_CLASS_MAPPINGS['CR Simple Prompt List Keyframes'].execute(**args_for('CR Simple Prompt List Keyframes',simple_prompt_list=['text']*256,loops=1000))
    with pytest.raises(ValueError,match='nesting'):
        NEW.NODE_CLASS_MAPPINGS['CR Image List'].execute(**args_for('CR Image List',image_list=[[[[[[[[[[0]]]]]]]]]]))

def test_all_ten_two_fresh_zero_capability_guests_and_exact_outer_values():
    import execution
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for render in range(2):
                session=await GuestSession('ned-comfyroll-animation-values-'+str(render),guest_runtime_root=V2).start()
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=())
                _sdk.providers.register_execution_backend(Backend())
                try:
                    for node_id in LEDGER:
                        cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA();args=args_for(node_id)
                        result=await execution._async_map_node_over_list(prompt_id='animation-values',unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                        exact(result[0].result,oracle(node_id,args))
                        if node_id=='CR Image List':assert result[0].result[0][1][1] is args['image_1']
                        if node_id=='CR Cycle Images':assert result[0].result[0] is args['image_list'][0][1]
                        if node_id=='CR Cycle Images Simple':assert result[0].result[0] is args['image_list_simple'][0]
                    images=[torch.full((1,3,5,3),i/4) for i in range(3)]
                    cls=NEW.NODE_CLASS_MAPPINGS['CR Image List Simple']
                    args=args_for('CR Image List Simple',image_list_simple=images[:2],image_1=images[2])
                    result=await execution._async_map_node_over_list(prompt_id='animation-flat-list',unique_id='image-list-simple',obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                    assert len(result[0].result[0])==3
                    for a,b in zip(result[0].result[0],images):assert a is b
                    produced=result[0].result[0]
                    cls=NEW.NODE_CLASS_MAPPINGS['CR Cycle Images Simple']
                    args=args_for('CR Cycle Images Simple',image_list_simple=produced,image_1=None,image_2=None,image_3=None,image_4=None,image_5=None,current_frame=1,frame_interval=1)
                    result=await execution._async_map_node_over_list(prompt_id='animation-flat-consumer',unique_id='cycler',obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                    assert result[0].result[0] is images[1]
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(previous)
        assert pids[0]!=pids[1]
    asyncio.run(run())

def test_production_dispatch_all_ten_animation_values(monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        previous=_sdk.providers.execution_backend;session=await GuestSession('ned-comfyroll-production-animation-values',guest_runtime_root=V2).start();backend=CloudExecutionBackend()
        monkeypatch.setattr(backend,'_is_sandbox',lambda plan:True)
        async def session_for(*args,**kwargs):return session
        monkeypatch.setattr(backend.guests,'session_for',session_for);_sdk.providers.register_execution_backend(backend)
        try:
            for node_id in LEDGER:
                args=args_for(node_id);cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA()
                result=await execution._async_map_node_over_list(prompt_id='production-animation-values',unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                result=await execution.resolve_map_node_over_list_results(result);exact(result[0].result,oracle(node_id,args))
            assert session.last_guest_pid not in (None,os.getpid())
        finally:await session.kill();await backend.shutdown();_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())

@pytest.mark.parametrize('count',[0,1,3])
@pytest.mark.parametrize('extra',[False,True])
def test_simple_image_list_source_nested_generator_defect_and_approved_flat_order(count,extra):
    images=[torch.full((1,3,5,3),i/4) for i in range(count)]
    extra_image=torch.full((1,3,5,3),.9) if extra else None
    args=args_for('CR Image List Simple',image_list_simple=images,image_1=extra_image)
    old=oracle('CR Image List Simple',args)
    assert type(old[0][0]).__name__=='generator'
    exact(list(old[0][0]),images)
    assert len(old[0])==1+int(extra)
    expected=images+([extra_image] if extra else [])
    actual=NEW.NODE_CLASS_MAPPINGS['CR Image List Simple'].execute(**args).result
    exact(actual,(expected,old[1]))
    for a,b in zip(actual[0],expected):assert a is b
