"""Seed-exact outputs and scoped RNG lifetime, not process-global continuation parity."""
import ast
import asyncio
import copy
import importlib.util
import json
import os
from pathlib import Path
import random
import string
import sys

import matplotlib.colors as mcolors
import pytest

sys.dont_write_bytecode=True;sys.argv=['ned-comfyroll-seeded-random','--cpu']
CORE=Path(os.environ['COMFY_CORE_ROOT']);sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
spec=importlib.util.spec_from_file_location('ned_comfyroll_seeded_random_pack',V2/'__init__.py',submodule_search_locations=[str(V2)])
NEW=importlib.util.module_from_spec(spec);sys.modules[spec.name]=NEW;spec.loader.exec_module(NEW)
LEDGER=json.loads((V2/'seeded-random-draft-ledger.json').read_text())
icons=ast.literal_eval(ast.parse((PACK/'categories.py').read_text()).body[0].value)
ns={'random':random,'string':string,'mcolors':mcolors,'icons':icons,'any_type':'*'}
helpers=[copy.deepcopy(n) for n in ast.parse((PACK/'nodes/functions_graphics.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name in ('random_rgb','random_hex_color')]
exec(compile(ast.Module(body=helpers,type_ignores=[]),'pinned-random-helpers','exec'),ns)
tree=ast.parse((PACK/'nodes/nodes_utils_random.py').read_text());OLD={}
for node_id,row in LEDGER.items():
    scope=dict(ns);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==row['class'])
    exec(compile(ast.Module(body=[copy.deepcopy(cls)],type_ignores=[]),str(PACK/'nodes/nodes_utils_random.py'),'exec'),scope)
    OLD[node_id]=scope[row['class']]

def args_for(node_id,**changes):
    args={}
    for group,items in LEDGER[node_id]['source_inputs'].items():
        for name,spec in items.items():
            opts=spec[1] if len(spec)>1 else {}
            args[name]=opts.get('default',spec[0][0] if isinstance(spec[0],list) else None)
    args.update(changes);return args

def oracle(node_id,args):
    before=random.getstate()
    try:
        obj=OLD[node_id]();return getattr(obj,obj.FUNCTION)(**args)
    finally:random.setstate(before)

def outcome(fn):
    try:
        value=fn();return 'value',value.result if hasattr(value,'result') else value
    except Exception as exc:return 'error',type(exc),str(exc)

def exact(actual,expected):
    assert type(actual) is tuple and type(expected) is tuple
    assert len(actual)==len(expected)
    for a,b in zip(actual,expected):assert type(a) is type(b) and a==b

def parity(node_id,args):
    before=random.getstate()
    actual=outcome(lambda:NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args));assert random.getstate()==before
    expected=outcome(lambda:oracle(node_id,args));assert random.getstate()==before
    assert actual[0]==expected[0],(actual if actual[0]=='error' else actual[0],expected if expected[0]=='error' else expected[0])
    if actual[0]=='error':assert actual[1:]==expected[1:]
    else:exact(actual[1],expected[1])

@pytest.mark.parametrize('node_id',list(LEDGER))
@pytest.mark.parametrize('seed',[0,1,17,-1,2**64-1,2**65,2**100,True])
def test_all_six_seed_sign_width_and_repeat_exact_without_global_mutation(node_id,seed):
    args=args_for(node_id,seed=seed);parity(node_id,args);parity(node_id,args)

@pytest.mark.parametrize('mode',['binary','decimal','natural','hexadecimal','alphabetic','alphanumeric','custom','unknown'])
@pytest.mark.parametrize('geometry',[(0,0),(-1,3),(1,-1),(4,9),(1,0),(3,1)])
@pytest.mark.parametrize('custom',['','A1','é💥中文'])
def test_multiline_all_alphabets_prefix_unicode_and_native_empty_unknown(mode,geometry,custom):
    parity('CR Random Multiline Values',args_for('CR Random Multiline Values',value_type=mode,rows=geometry[0],string_length=geometry[1],custom_values=custom,prepend_text='<>&"',seed=137))

@pytest.mark.parametrize('mode',['rgb','hex color','matplotlib xkcd','unknown'])
@pytest.mark.parametrize('seed',[0,1,77,2**64-1])
@pytest.mark.parametrize('rows',[-1,0,1,9,99])
def test_multiline_colors_exact_xkcd_order_and_native_unknown(mode,seed,rows):
    parity('CR Random Multiline Colors',args_for('CR Random Multiline Colors',value_type=mode,seed=seed,rows=rows))

@pytest.mark.parametrize('alphabet',['','123','XYZ','é💥','1','  '])
@pytest.mark.parametrize('geometry',[(0,0),(-1,3),(1,-1),(4,9),(1,0),(3,1)])
def test_panel_codes_preserve_unused_initial_draw_and_native_empty_alphabet(alphabet,geometry):
    parity('CR Random Panel Codes',args_for('CR Random Panel Codes',values=alphabet,rows=geometry[0],string_length=geometry[1],seed=91))

@pytest.mark.parametrize('rows',[-1,0,1,3,10,99,100,101])
@pytest.mark.parametrize('seed',[0,1,2,77,2**64-1])
def test_gradient_exact_dropped_rows_trailing_newline_and_source_draw_sequence(rows,seed):
    parity('CR Random RGB Gradient',args_for('CR Random RGB Gradient',rows=rows,seed=seed))

def test_legacy_global_reset_continuation_diagnostic_is_deliberately_not_reproduced():
    node_id='CR Random Hex Color';args=args_for(node_id,seed=41);before=random.getstate()
    try:
        source=OLD[node_id]();expected=getattr(source,source.FUNCTION)(**args)
        after=random.getstate();assert after!=before
        random.setstate(before)
        actual=NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args).result
        assert random.getstate()==before;exact(actual,expected)
    finally:random.setstate(before)

def test_source_xkcd_catalogue_949_names_order_and_four_hex_vs_rgb_draws():
    assert len(mcolors.XKCD_COLORS)==949
    assert list(NEW.secure_seeded_random.mcolors.XKCD_COLORS.items())==list(mcolors.XKCD_COLORS.items())
    for seed in range(24):
        rgb=NEW.NODE_CLASS_MAPPINGS['CR Random RGB'].execute(seed=seed).result
        hexa=NEW.NODE_CLASS_MAPPINGS['CR Random Hex Color'].execute(seed=seed).result
        for r,h in zip(rgb[:4],hexa[:4]):assert h=='#{:02x}{:02x}{:02x}'.format(*map(int,r.split(',')))

@pytest.mark.parametrize('node_id',list(LEDGER))
def test_exact_schema_defaults_names_options_and_workflow_reconstruction(node_id):
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
    args=args_for(node_id);exact(NEW.NODE_CLASS_MAPPINGS[node_id].execute(**json.loads(json.dumps(args))).result,oracle(node_id,args))
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

def test_workload_bounds_before_rng_construction_and_output_generation(monkeypatch):
    def deny(*args,**kwargs):raise AssertionError('RNG before preflight')
    monkeypatch.setattr(NEW.secure_seeded_random.random,'Random',deny)
    cases=[('CR Random Hex Color',{'seed':2**4096}),('CR Random RGB',{'seed':b'x'*262145}),('CR Random Multiline Values',{'rows':2049}),('CR Random Multiline Values',{'rows':2048,'string_length':1024}),('CR Random Multiline Values',{'rows':100,'string_length':1024,'custom_values':'💥'}),('CR Random Multiline Values',{'rows':8,'prepend_text':'x'*32768}),('CR Random Panel Codes',{'rows':2048,'string_length':1024}),('CR Random Multiline Colors',{'rows':2049}),('CR Random RGB Gradient',{'rows':2049})]
    for node_id,changes in cases:
        with pytest.raises(ValueError,match='bound'):NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args_for(node_id,**changes))

def test_all_six_registered_zero_capabilities_two_fresh_pids_outer_strings_and_sequences():
    import execution
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for render in range(2):
                session=await GuestSession('ned-comfyroll-seeded-random-'+str(render),guest_runtime_root=V2).start()
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=())
                _sdk.providers.register_execution_backend(Backend())
                try:
                    for node_id in LEDGER:
                        cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA()
                        for seed in (0,17,2**64-1):
                            args=args_for(node_id,seed=seed)
                            result=await execution._async_map_node_over_list(prompt_id='seeded-random',unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                            exact(result[0].result,oracle(node_id,args))
                    args=args_for('CR Random Multiline Colors',value_type='matplotlib xkcd',seed=77,rows=11)
                    cls=NEW.NODE_CLASS_MAPPINGS['CR Random Multiline Colors']
                    result=await execution._async_map_node_over_list(prompt_id='seeded-random-xkcd',unique_id='xkcd',obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                    exact(result[0].result,oracle('CR Random Multiline Colors',args));pids.append(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(previous)
        assert pids[0]!=pids[1]
    asyncio.run(run())

def test_production_dispatch_all_six_zero_capability_random_entrypoints(monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        previous=_sdk.providers.execution_backend;session=await GuestSession('ned-comfyroll-production-seeded-random',guest_runtime_root=V2).start();backend=CloudExecutionBackend()
        monkeypatch.setattr(backend,'_is_sandbox',lambda plan:True)
        async def session_for(*args,**kwargs):return session
        monkeypatch.setattr(backend.guests,'session_for',session_for);_sdk.providers.register_execution_backend(backend)
        try:
            for node_id in LEDGER:
                args=args_for(node_id,seed=77);cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA()
                result=await execution._async_map_node_over_list(prompt_id='production-seeded-random',unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                result=await execution.resolve_map_node_over_list_results(result);exact(result[0].result,oracle(node_id,args))
            assert session.last_guest_pid not in (None,os.getpid())
        finally:await session.kill();await backend.shutdown();_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())

