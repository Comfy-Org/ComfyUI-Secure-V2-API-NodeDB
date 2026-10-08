"""Pinned workflow/scalar helpers: exact algorithms, bounds, fresh guest and outer output."""
import ast
import asyncio
import copy
import importlib.util
import json
import os
import re
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import torch

sys.dont_write_bytecode=True;sys.argv=['ned-comfyroll-utilities','--cpu']
CORE=Path(os.environ['COMFY_CORE_ROOT']);sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
spec=importlib.util.spec_from_file_location('ned_comfyroll_utilities_pack',V2/'__init__.py',submodule_search_locations=[str(V2)])
NEW=importlib.util.module_from_spec(spec);sys.modules[spec.name]=NEW;spec.loader.exec_module(NEW)
LEDGER=json.loads((V2/'utility-draft-ledger.json').read_text());OLD={}
icons=ast.literal_eval(ast.parse((PACK/'categories.py').read_text()).body[0].value)
TREES={name:ast.parse((PACK/'nodes'/name).read_text()) for name in {row['source_file'] for row in LEDGER.values()}}
for node_id,row in LEDGER.items():
    tree=TREES[row['source_file']]
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==row['class']);ns={'icons':icons,'any_type':'*','re':re}
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
def test_defaults_native_errors_and_schema_type_quirks(node_id):
    args=args_for(node_id)
    exact(outcome(lambda:NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args)),outcome(lambda:oracle(node_id,args)))

@pytest.mark.parametrize('node_id',['CR SDXL Prompt Mixer','CR SDXL Prompt Mix Presets'])
@pytest.mark.parametrize('text',['', 'hello, ', '<script>x</script>\nΩ "quote" \\ path', '🙂'*128])
def test_every_preset_exact_prompt_order_and_concatenation(node_id,text):
    presets=LEDGER[node_id]['source_inputs']['optional']['preset'][0]
    for preset in presets+['invalid']:
        args=args_for(node_id,prompt_positive=text,prompt_negative='neg '+text,style_positive='POSstyle',style_negative='NEGstyle',preset=preset)
        exact(outcome(lambda:NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args)),outcome(lambda:oracle(node_id,args)))

@pytest.mark.parametrize('ratio',LEDGER['CR Aspect Ratio SDXL']['source_inputs']['required']['aspect_ratio'][0])
@pytest.mark.parametrize('swap',['On','Off'])
def test_legacy_aspect_dimensions_no_allocation_or_multiplication(ratio,swap):
    args=args_for('CR Aspect Ratio SDXL',width=735,height=419,aspect_ratio=ratio,swap_dimensions=swap,upscale_factor1=1.7,upscale_factor2=2.3,batch_size=3)
    exact(NEW.NODE_CLASS_MAPPINGS['CR Aspect Ratio SDXL'].execute(**args).result,oracle('CR Aspect Ratio SDXL',args))

@pytest.mark.parametrize('seed',[{'seed':0},{'seed':2**64-1},{},{'seed':-3},None,1,'bad'])
def test_seed_get_missing_and_native_malformed_contract(seed):
    args={'seed':seed}
    exact(outcome(lambda:NEW.NODE_CLASS_MAPPINGS['CR Seed to Int'].execute(**args)),outcome(lambda:oracle('CR Seed to Int',args)))

@pytest.mark.parametrize('binary',['','01','0 1\n2 3','9','Ω','\t1','\r0'])
@pytest.mark.parametrize('loops',[-1,0,1,3])
@pytest.mark.parametrize('interval',[-2,0,5])
def test_bit_schedule_loops_spacing_nonbinary_native_errors(binary,loops,interval):
    args=dict(binary_string=binary,loops=loops,interval=interval)
    exact(outcome(lambda:NEW.NODE_CLASS_MAPPINGS['CR Bit Schedule'].execute(**args)),outcome(lambda:oracle('CR Bit Schedule',args)))

@pytest.mark.parametrize('first,second',[('x','y'),('a, b, "c,d"','one,two'),('',''),('a,"b,c','"d,e",f'),('"a""b",c','Ω,🙂')])
@pytest.mark.parametrize('index',[-1,0,1,2,3,6,7])
def test_xy_quoted_split_final_annotations_trigger_and_native_bounds(first,second,index):
    args=args_for('CR XY List',list1=first,list2=second,index=index,x_prepend='X(',x_append=')',y_prepend='Y(',y_append=')',x_annotation_prepend='α:',y_annotation_prepend='β:')
    exact(outcome(lambda:NEW.NODE_CLASS_MAPPINGS['CR XY List'].execute(**args)),outcome(lambda:oracle('CR XY List',args)))

@pytest.mark.parametrize('columns,rows',[(0,2),(1,1),(3,2),(3.0,2.0),(-3,2)])
@pytest.mark.parametrize('index',[0,1,2,6])
def test_xy_numeric_rounding_last_cell_annotation_and_native_float_int_ambiguity(columns,rows,index):
    for node_id in ['CR XY Interpolate','CR XY Index']:
        args=args_for(node_id,x_columns=columns,y_rows=rows,index=index)
        if node_id=='CR XY Interpolate':
            args.update(x_start_value=1.23456,x_step=-.3,y_start_value=-3.14159,y_step=.12345,x_annotation_prepend='x=',y_annotation_prepend='y=')
        exact(outcome(lambda:NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args)),outcome(lambda:oracle(node_id,args)))

@pytest.mark.parametrize('node_id',list(LEDGER))
def test_exact_schema_zero_authority_and_source_metadata(node_id):
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

def test_print_exact_yes_only_and_no_native_side_effect(capsys):
    cls=NEW.NODE_CLASS_MAPPINGS['CR Current Frame']
    assert cls.execute(index=-3,print_to_console='Yes').result==(-3,)
    assert capsys.readouterr().out=='[Info] CR Current Frame:-3\n'
    cls.execute(index=5,print_to_console='No')
    assert capsys.readouterr().out==''

def test_projected_workload_denied_before_regex_or_generation(monkeypatch):
    from ned_comfyroll_utilities_pack import secure_utilities as u
    def deny(*args,**kwargs):raise AssertionError('regex ran before workload preflight')
    monkeypatch.setattr(u.re,'split',deny)
    for changes in [dict(list1='x'*8193),dict(list1=','*2048),dict(list1=','*300,x_annotation_prepend='x'*1000)]:
        with pytest.raises(ValueError,match='workload'):
            NEW.NODE_CLASS_MAPPINGS['CR XY List'].execute(**args_for('CR XY List',**changes))
    with pytest.raises(ValueError,match='projected item'):
        NEW.NODE_CLASS_MAPPINGS['CR Bit Schedule'].execute(binary_string='01',interval=1,loops=10000)
    with pytest.raises(ValueError,match='projected text'):
        NEW.NODE_CLASS_MAPPINGS['CR Bit Schedule'].execute(binary_string='01',interval=10**100,loops=2000)
    with pytest.raises(ValueError,match='annotation'):
        NEW.NODE_CLASS_MAPPINGS['CR XY Interpolate'].execute(**args_for('CR XY Interpolate',x_columns=1025))
    with pytest.raises(ValueError,match='annotation'):
        NEW.NODE_CLASS_MAPPINGS['CR XY Interpolate'].execute(**args_for('CR XY Interpolate',x_columns=500,x_annotation_prepend='Ω'*300))
    with pytest.raises(ValueError,match='integer'):
        NEW.NODE_CLASS_MAPPINGS['CR Seed to Int'].execute(seed={'seed':1<<4097})

def test_all_eleven_actual_guest_outer_zero_authority_and_workflow_reconstruction():
    import execution
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for render in range(2):
                session=await GuestSession('ned-comfyroll-utilities-'+str(render),guest_runtime_root=V2).start()
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):return await session.execute(plan,runtime,capabilities=())
                _sdk.providers.register_execution_backend(Backend())
                try:
                    for node_id in LEDGER:
                        args=args_for(node_id)
                        if node_id=='CR Seed to Int':args['seed']={'seed':2**64-1}
                        if node_id=='CR XY List':args.update(index=6,list1='a,"b,c",d',list2='first,last')
                        if node_id=='CR XY Interpolate':args.update(x_columns=3,y_rows=2,index=6)
                        if node_id=='CR XY Index':args.update(x_columns=3,y_rows=2,index=6)
                        if node_id=='CR Bit Schedule':args.update(binary_string='0 1\n2',loops=2,interval=3)
                        args=json.loads(json.dumps(args))
                        expected=oracle(node_id,args);cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA()
                        out=await execution._async_map_node_over_list(prompt_id='workflow-'+str(render),unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                        exact(out[0].result,expected)
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(previous)
        assert pids[0]!=pids[1]
    asyncio.run(run())
