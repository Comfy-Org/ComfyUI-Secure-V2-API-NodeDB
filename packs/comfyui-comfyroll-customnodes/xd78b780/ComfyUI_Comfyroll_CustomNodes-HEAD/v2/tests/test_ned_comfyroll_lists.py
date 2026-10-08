"""Pinned list algorithms, native errors, list axes and actual zero-capability guests."""
import ast
import asyncio
import copy
import importlib.util
from itertools import product
import json
import math
import os
from pathlib import Path
import sys

import numpy as np
import pytest

sys.dont_write_bytecode=True;sys.argv=['ned-comfyroll-lists','--cpu']
CORE=Path(os.environ['COMFY_CORE_ROOT']);sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
spec=importlib.util.spec_from_file_location('ned_comfyroll_lists_pack',V2/'__init__.py',submodule_search_locations=[str(V2)])
NEW=importlib.util.module_from_spec(spec);sys.modules[spec.name]=NEW;spec.loader.exec_module(NEW)
LEDGER=json.loads((V2/'list-draft-ledger.json').read_text());OLD={}
icons=ast.literal_eval(ast.parse((PACK/'categories.py').read_text()).body[0].value)
tree=ast.parse((PACK/'nodes/nodes_list.py').read_text())
for node_id,row in LEDGER.items():
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==row['class'])
    ns={'icons':icons,'any_type':'*','np':np,'math':math,'product':product}
    exec(compile(ast.Module(body=[copy.deepcopy(cls)],type_ignores=[]),'pinned-lists','exec'),ns);OLD[node_id]=ns[row['class']]

def args_for(node_id,**changes):
    args={}
    for items in LEDGER[node_id]['source_inputs'].values():
        for key,spec in items.items():
            opts=spec[1] if len(spec)>1 else {}
            args[key]=opts['default'] if 'default' in opts else spec[0][0] if isinstance(spec[0],list) else '' if spec[0]=='STRING' else None
    args.update(changes);return args

def oracle(node_id,args):
    obj=OLD[node_id]();return getattr(obj,obj.FUNCTION)(**args)

def outcome(fn):
    try:
        result=fn();return ('value',result.result if hasattr(result,'result') else result)
    except Exception as exc:return ('error',type(exc),str(exc))

def exact(a,b):
    assert type(a) is type(b)
    if isinstance(a,(list,tuple)):
        assert len(a)==len(b)
        for x,y in zip(a,b):exact(x,y)
    else:assert a==b

@pytest.mark.parametrize('node_id',list(LEDGER))
def test_default_and_approved_unused_loops_repair(node_id):
    args=args_for(node_id)
    if node_id=='CR Text List':
        with pytest.raises(TypeError,match='loops'):oracle(node_id,args)
        exact(NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args).result,oracle(node_id,dict(args,loops=1)))
    else:exact(outcome(lambda:NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args)),outcome(lambda:oracle(node_id,args)))

@pytest.mark.parametrize('text',['','\n','  a \n\n b  \n c','1\n2.5\n-3\n0','é\n🙂\n<&script>'])
@pytest.mark.parametrize('start,max_rows',[(-3,2),(0,1),(1,3),(9999,9999),(1,0),(2,-1)])
def test_text_prompt_slicing_blank_unicode(text,start,max_rows):
    for node_id in ('CR Text List','CR Prompt List'):
        args=args_for(node_id,multiline_text=text,start_index=start,max_rows=max_rows)
        if node_id=='CR Prompt List':args.update(prepend_text='[(',append_text=')]')
        expected=oracle(node_id,dict(args,loops=7) if node_id=='CR Text List' else args)
        exact(NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args).result,expected)

@pytest.mark.parametrize('operation',['none','sin','cos','tan'])
@pytest.mark.parametrize('start,end,step',[(0.,1.,.25),(1.,-1.,.3),(-1.,1.,.3),(0.,1.,-1.),(1.,1.,.2)])
@pytest.mark.parametrize('loops,ping,ignore',[(1,False,True),(3,True,True),(2,True,False),(0,False,False)])
def test_float_range_rounding_iteration_and_numpy_scalars(operation,start,end,step,loops,ping,ignore):
    node_id='CR Float Range List';args=args_for(node_id,operation=operation,start=start,end=end,step=step,loops=loops,ping_pong=ping,ignore_first_value=ignore,max_values_per_loop=4,decimal_places=3)
    exact(NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args).result,oracle(node_id,args))

@pytest.mark.parametrize('start,end,step',[(0,6,2),(6,0,-2),(6,0,2),(0,6,-2),(0,0,1),(-5,4,3)])
@pytest.mark.parametrize('loops,ping',[(0,False),(1,False),(3,True),(-2,True)])
def test_integer_range_end_exclusion_and_pingpong(start,end,step,loops,ping):
    node_id='CR Integer Range List';args=args_for(node_id,start=start,end=end,step=step,loops=loops,ping_pong=ping)
    exact(NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args).result,oracle(node_id,args))

@pytest.mark.parametrize('node_id',['CR Float Range List','CR Integer Range List'])
def test_zero_step_native_error(node_id):
    args=args_for(node_id,start=0,end=1,step=0)
    exact(outcome(lambda:NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args)),outcome(lambda:oracle(node_id,args)))

@pytest.mark.parametrize('repeats,loops',[(0,1),(1,0),(2,3),(-2,1),(1,-2)])
@pytest.mark.parametrize('text',['0\n1.5\n-2\nnot-number',' 001 \n .5 \n2.9','','1\n\n2','...','3\n4'])
def test_cycles_loop_order_filter_and_native_errors(repeats,loops,text):
    for node_id,key in (('CR Text Cycler','text'),('CR Value Cycler','values')):
        args=args_for(node_id,**{key:text},repeats=repeats,loops=loops)
        exact(outcome(lambda:NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args)),outcome(lambda:oracle(node_id,args)))

@pytest.mark.parametrize('node_id,args',[
 ('CR Intertwine Lists',dict(list1='a\nb',list2='1')),
 ('CR Intertwine Lists',dict(list1=['a','b'],list2=['1'])),
 ('CR Binary To Bit List',dict(bit_string='01a🙂\n')),
 ('CR Text List To String',dict(text_list=['a','','🙂'])),
 ('CR Text List To String',dict(text_list='abc')),
 ('CR Simple List',dict(list_values='  a \n\n b\n  ')),
 ('CR XY Product',dict(text_x='x1\nx2',text_y='y1\ny2\ny3')),
 ('CR XY Product',dict(text_x='',text_y='')),
 ('CR Repeater',dict(input_data=['a','b'],repeats=3)),
 ('CR Repeater',dict(input_data=('a','b'),repeats=2)),
 ('CR Repeater',dict(input_data='a',repeats=-1))])
def test_list_utils_cartesian_and_copy_order(node_id,args):
    exact(NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args).result,oracle(node_id,args))

@pytest.mark.parametrize('node_id',list(LEDGER))
def test_exact_schema_list_axes_zero_authority(node_id):
    cls=NEW.NODE_CLASS_MAPPINGS[node_id];schema=cls.GET_SCHEMA();row=LEDGER[node_id]
    assert cls.SDK_REFS is True and cls.SDK_PERMISSIONS==()
    assert schema.node_id==node_id and schema.display_name==row['display_name'] and schema.category==row['category']
    assert schema.is_input_list==row['is_input_list']
    assert [o.io_type for o in schema.outputs]==row['return_types']
    assert [o.is_output_list for o in schema.outputs]==row['output_is_list']
    if row['return_names'] is not None:assert [o.display_name for o in schema.outputs]==row['return_names']
    flat={key:(group,spec) for group,items in row['source_inputs'].items() for key,spec in items.items()}
    assert [i.id for i in schema.inputs]==list(flat)
    for inp in schema.inputs:
        group,source=flat[inp.id];assert inp.optional==(group=='optional')
        if isinstance(source[0],list):assert inp.options==source[0]
        else:assert inp.io_type==source[0]
        for key,value in (source[1] if len(source)>1 else {}).items():assert inp.as_dict()[key]==value

@pytest.mark.parametrize('node_id,changes',[
 ('CR Integer Range List',dict(start=0,end=100000,step=1)),
 ('CR Float Range List',dict(start=0.,end=1000.,step=.0001)),
 ('CR XY Product',dict(text_x='x\n'*200,text_y='y\n'*200)),
 ('CR Repeater',dict(input_data=['a']*300,repeats=300)),
 ('CR Text Cycler',dict(text='x\n'*300,repeats=100,loops=2)),
 ('CR Prompt List',dict(multiline_text='x\n'*300,prepend_text='x'*2000)),
 ('CR Binary To Bit List',dict(bit_string='1'*20000))])
def test_projected_bounds_before_numpy_or_list_work(node_id,changes,monkeypatch):
    calls=[];monkeypatch.setattr(NEW.secure_lists.np,'arange',lambda *a,**k:calls.append(a))
    with pytest.raises(ValueError,match='bound'):NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args_for(node_id,**changes))
    assert not calls

VALID={
 'CR Text List':dict(multiline_text='a\n\nb',start_index=1,max_rows=2),
 'CR Prompt List':dict(multiline_text='a\n\nb',prepend_text='[',append_text=']'),
 'CR Float Range List':dict(start=0.,end=1.,step=.25,ignore_first_value=False),
 'CR Integer Range List':dict(start=0,end=6,step=2,loops=2,ping_pong=True),
 'CR Intertwine Lists':dict(list1='a\nb',list2='1\n2'),
 'CR Binary To Bit List':dict(bit_string='01a🙂'),
 'CR Text List To String':dict(text_list=['a','','b']),
 'CR Simple List':dict(list_values=' a \n\nb '),
 'CR XY Product':dict(text_x='a\nb',text_y='1\n2'),
 'CR Repeater':dict(input_data=['a','b'],repeats=2),
 'CR Text Cycler':dict(text='a\nb',repeats=2,loops=2),
 'CR Value Cycler':dict(values='1\n2.5\n-3\nword',repeats=2,loops=2)}
def test_all_twelve_actual_guests_outer_list_axes_and_workflow_reconstruction():
    import execution
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for render in range(2):
                session=await GuestSession('ned-comfyroll-lists-'+str(render),guest_runtime_root=V2).start()
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):return await session.execute(plan,runtime,capabilities=())
                _sdk.providers.register_execution_backend(Backend())
                try:
                    for node_id,row in LEDGER.items():
                        args=json.loads(json.dumps(args_for(node_id,**VALID[node_id])))
                        expected=oracle(node_id,dict(args,loops=1) if node_id=='CR Text List' else args)
                        cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA()
                        data=args if row['is_input_list'] else {k:[v] for k,v in args.items()}
                        outputs=await execution._async_map_node_over_list(prompt_id='lists-'+str(render),unique_id=node_id,obj=cls,input_data_all=data,func=cls.FUNCTION,v3_data=None)
                        exact(outputs[0].result,expected)
                        merged=execution.get_output_from_returns(outputs,cls)
                        assert merged[1]=={} and not merged[2]
                        for i,value in enumerate(expected):exact(merged[0][i],value if row['output_is_list'][i] else [value])
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(previous)
        assert pids[0]!=pids[1]
    asyncio.run(run())

def test_repeater_actual_guest_opaque_model_clip_vae_identity_without_model_calls():
    import execution
    from types import SimpleNamespace
    def deny(*args,**kwargs):raise AssertionError('Repeater must not invoke model methods')
    async def run():
        session=await GuestSession('ned-comfyroll-repeater-handles',guest_runtime_root=V2).start()
        previous=_sdk.providers.execution_backend
        class Backend:
            async def dispatch(self,plan,local_call,runtime):return await session.execute(plan,runtime,capabilities=())
        _sdk.providers.register_execution_backend(Backend())
        try:
            objects=[SimpleNamespace(model_options={},load_device='cpu'),SimpleNamespace(tokenize=deny),SimpleNamespace(encode=deny,decode=deny)]
            assert [_sdk._ref_type_for(obj)[1] for obj in objects]==['MODEL','CLIP','VAE']
            cls=NEW.NODE_CLASS_MAPPINGS['CR Repeater'];cls.GET_SCHEMA()
            for value in objects+[objects]:
                result=await execution._async_map_node_over_list(prompt_id='opaque-copy',unique_id='node',obj=cls,input_data_all={'input_data':[value],'repeats':[2]},func=cls.FUNCTION,v3_data=None)
                expected=[obj for obj in value for _ in range(2)] if isinstance(value,list) else [value,value]
                assert len(result[0].result[0])==len(expected)
                assert all(a is b for a,b in zip(result[0].result[0],expected))
        finally:await session.kill();_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
