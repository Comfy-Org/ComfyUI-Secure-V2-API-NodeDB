"""Workflow-owned schedule parsing/state, native defects, exact schemas and fresh guests."""
import ast
import asyncio
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest

sys.dont_write_bytecode=True;sys.argv=['ned-comfyroll-schedules','--cpu']
CORE=Path(os.environ['COMFY_CORE_ROOT']);sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
spec=importlib.util.spec_from_file_location('ned_comfyroll_schedules_pack',V2/'__init__.py',submodule_search_locations=[str(V2)])
NEW=importlib.util.module_from_spec(spec);sys.modules[spec.name]=NEW;spec.loader.exec_module(NEW)
LEDGER=json.loads((V2/'schedule-draft-ledger.json').read_text())
icons=ast.literal_eval(ast.parse((PACK/'categories.py').read_text()).body[0].value)
ns={'icons':icons}
helpers=[copy.deepcopy(n) for n in ast.parse((PACK/'nodes/functions_animation.py').read_text()).body if isinstance(n,ast.FunctionDef)]
exec(compile(ast.Module(body=helpers,type_ignores=[]),'pinned-animation-helpers','exec'),ns)
OLD={}
for node_id,row in LEDGER.items():
    path=PACK/'nodes'/row['source_file'];cls=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.ClassDef) and n.name==row['class'])
    scope=dict(ns);exec(compile(ast.Module(body=[copy.deepcopy(cls)],type_ignores=[]),str(path),'exec'),scope);OLD[node_id]=scope[row['class']]

def defaults(node_id,**overrides):
    args={}
    for group,items in LEDGER[node_id]['source_inputs'].items():
        for name,spec in items.items():
            opts=spec[1] if len(spec)>1 else {}
            if 'default' in opts:args[name]=opts['default']
            elif isinstance(spec[0],list):args[name]=spec[0][0]
            elif spec[0]=='STRING':args[name]=''
            else:args[name]=None
    args.update(overrides);return args

def oracle(node_id,args):
    obj=OLD[node_id]();return getattr(obj,obj.FUNCTION)(**args)

def outcome(call):
    try:
        value=call();return ('value',value.result if hasattr(value,'result') else value)
    except Exception as exc:return ('error',type(exc),str(exc))

@pytest.mark.parametrize('node_id',list(LEDGER))
def test_default_native_outcome_and_workflow_repeat_exact(node_id):
    args=defaults(node_id)
    expected=outcome(lambda:oracle(node_id,args))
    for _ in range(2):assert outcome(lambda:NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args))==expected

@pytest.mark.parametrize('frame',[-1,0,1,5,7,10,11,30])
@pytest.mark.parametrize('node_id',['CR Value Scheduler','CR Text Scheduler','CR Simple Value Scheduler','CR Simple Text Scheduler','CR Prompt Scheduler','CR Simple Prompt Scheduler'])
def test_piecewise_and_prompt_interpolation_exact(node_id,frame):
    if 'Prompt' in node_id:text='0, first\n5, second\n10, third'
    elif 'Value' in node_id:text='0, -1.25\n5, 2.5\n10, 4.0'
    else:text='0, first\n5, second\n10, third'
    overrides={'current_frame':frame}
    fields=LEDGER[node_id]['source_inputs']
    flat={k for entries in fields.values() for k in entries}
    if 'mode' in flat:overrides['mode']='Schedule'
    if 'schedule_alias' in flat:overrides['schedule_alias']='a'
    overrides['schedule']=[('ignored','0, not chosen')]+[('a',line) for line in text.split('\n')] if 'mode' in flat else text
    if 'keyframe_list' in flat:overrides['keyframe_list']=text
    args=defaults(node_id,**overrides)
    if 'keyframe_list' in flat and 'mode' not in flat:args.pop('schedule',None)
    expected=outcome(lambda:oracle(node_id,args))
    assert outcome(lambda:NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args))==expected

@pytest.mark.parametrize('text',['','\n','0, first\n\n5, next','no comma','frame, text','5, later','0, "quoted", comma\n5, "other"','0: "first",\n5: "next",'])
@pytest.mark.parametrize('node_id',['CR Simple Prompt Scheduler','CR Simple Value Scheduler','CR Simple Text Scheduler'])
def test_malformed_and_deforum_native_outcomes_retained(node_id,text):
    key='keyframe_list' if 'Prompt' in node_id else 'schedule';args=defaults(node_id,**{key:text},current_frame=3)
    if 'keyframe_format' in args:args['keyframe_format']='Deforum'
    assert outcome(lambda:NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args))==outcome(lambda:oracle(node_id,args))

@pytest.mark.parametrize('node_id',list(LEDGER))
def test_exact_schema_and_zero_authority(node_id):
    cls=NEW.NODE_CLASS_MAPPINGS[node_id];row=LEDGER[node_id];schema=cls.GET_SCHEMA()
    assert schema.node_id==node_id and schema.display_name==row['display_name'] and schema.category==row['category']
    assert schema.is_output_node==row['is_output_node'] and schema.is_input_list==row['is_input_list']
    assert [o.io_type for o in schema.outputs]==row['return_types'] and [o.display_name for o in schema.outputs]==row['return_names']
    assert [o.is_output_list for o in schema.outputs]==row['output_is_list']
    flat={k:(group,spec) for group,items in row['source_inputs'].items() for k,spec in items.items()}
    assert [i.id for i in schema.inputs]==list(flat)
    for inp in schema.inputs:
        group,source=flat[inp.id];assert inp.optional==(group=='optional')
        if isinstance(source[0],list):assert inp.options==source[0]
        else:assert inp.io_type==source[0]
        for k,v in (source[1] if len(source)>1 else {}).items():
            if k!='forceInput':assert inp.as_dict()[k]==v
    assert cls.SDK_REFS is True and cls.SDK_PERMISSIONS==()

VALID={
 'CR Simple Schedule':dict(schedule='0, first\n\n5, second',schedule_alias='a'),
 'CR Combine Schedules':dict(schedule_1=[('a','0, first')],schedule_2=[('a','5, second')]),
 'CR Central Schedule':dict(schedule_1='0, first\n\n5, second',schedule_alias1='a'),
 'CR Schedule Input Switch':dict(Input=2,schedule1=[('a','0, first')],schedule2=[('b','0, second')]),
 'CR Value Scheduler':dict(mode='Schedule',schedule_alias='a',schedule=[('a','0, 1.25'),('a','5, 4.5')],current_frame=3),
 'CR Text Scheduler':dict(mode='Schedule',schedule_alias='a',schedule=[('a','0, first'),('a','5, second')],current_frame=3),
 'CR Prompt Scheduler':dict(mode='Keyframe List',keyframe_list='0, first\n5, second',schedule_alias='a',current_frame=3,interpolate_prompt='Yes'),
 'CR Simple Prompt Scheduler':dict(keyframe_list='0, first\n5, second',current_frame=3),
 'CR Simple Value Scheduler':dict(schedule='0, 1.25\n5, 4.5',current_frame=3),
 'CR Simple Text Scheduler':dict(schedule='0, first\n5, second',current_frame=3),
 'CR Text List Simple':dict(text_1='a',text_2='',text_3='b',text_list_simple=['prior']),
}
def test_all_eleven_fresh_guest_outer_workflow_reconstruction_and_node_isolation():
    import execution
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for render in range(2):
                session=await GuestSession('ned-comfyroll-schedule-'+str(render),guest_runtime_root=V2).start()
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):return await session.execute(plan,runtime,capabilities=())
                _sdk.providers.register_execution_backend(Backend())
                try:
                    for node_id in LEDGER:
                        cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA();args=defaults(node_id,**VALID[node_id])
                        # JSON workflow inputs are reconstructed, not process-global state.
                        reconstructed=json.loads(json.dumps(args))
                        expected=oracle(node_id,reconstructed)
                        result=await execution._async_map_node_over_list(prompt_id='ned-schedule-'+str(render),unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in reconstructed.items()},func=cls.FUNCTION,v3_data=None)
                        assert result[0].result==expected
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(previous)
        assert len(set(pids))==2 and os.getpid() not in pids
    asyncio.run(run())

def test_bounds_and_known_native_defects_explicit():
    with pytest.raises(ValueError,match='text'):NEW.secure_schedules.CR_SimpleSchedule.execute(**defaults('CR Simple Schedule',schedule='x'*262145))
    with pytest.raises(ValueError,match='workload'):NEW.secure_schedules.CR_SimpleSchedule.execute(**defaults('CR Simple Schedule',schedule='x\n'*4097))
    with pytest.raises(ValueError,match='item'):NEW.secure_schedules.CR_CombineSchedules.execute(schedule_1=['a']*16385)
    # Original missing default_value in TextScheduler and mixed tuple join in CentralSchedule.
    args=defaults('CR Text Scheduler',mode='Schedule',schedule_alias='a',schedule=[])
    assert outcome(lambda:oracle('CR Text Scheduler',args))[1] is NameError
    assert outcome(lambda:NEW.secure_schedules.CR_TextScheduler.execute(**args))[1] is NameError
    args=defaults('CR Central Schedule',schedule=[('a','0, first')])
    assert outcome(lambda:oracle('CR Central Schedule',args))[1] is TypeError
    assert outcome(lambda:NEW.secure_schedules.CR_CentralSchedule.execute(**args))[1] is TypeError
    declared=json.loads((V2/'intended-node-census.json').read_text())
    assert set(NEW.NODE_CLASS_MAPPINGS)=={node_id for node_id,row in declared.items() if row['registered_in_v2']}
    assert len(LEDGER)==11
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))
