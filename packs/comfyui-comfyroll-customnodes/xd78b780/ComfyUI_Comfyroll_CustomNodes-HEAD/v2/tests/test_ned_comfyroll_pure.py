"""Per-ID pure-family evidence, not complete199/model/cloud certification."""
import ast
import asyncio
import copy
import csv
import hashlib
import importlib.util
import io as stdlib_io
import json
import math
import os
from pathlib import Path
import sys
import types

import pytest

sys.dont_write_bytecode = True
sys.argv = ['ned-comfyroll-tests', '--cpu']
CORE = Path(os.environ['COMFY_CORE_ROOT'])
sys.path[:0] = [str(CORE), '/Users/ben/comfy/ComfyUI_secure_nodes/backend']
V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession

spec = importlib.util.spec_from_file_location('ned_comfyroll_secure',V2/'__init__.py',submodule_search_locations=[str(V2)])
NEW = importlib.util.module_from_spec(spec);sys.modules[spec.name]=NEW;spec.loader.exec_module(NEW)
LEDGER = json.loads((V2/'pure-draft-ledger.json').read_text())
ICONS = ast.literal_eval(ast.parse((PACK/'categories.py').read_text()).body[0].value)
ORACLE = {'icons':ICONS,'any':'*','any_type':'*','csv':csv,'io':stdlib_io,'math':math}
for source in sorted({r['source_path'] for r in LEDGER.values()}):
    file=PACK/'nodes'/Path(source).name
    assert hashlib.sha256(file.read_bytes()).hexdigest() == next(r['source_sha256'] for r in LEDGER.values() if r['source_path']==source)
    names={r['class'] for r in LEDGER.values() if r['source_path']==source}
    tree=ast.parse(file.read_text())
    body=[copy.deepcopy(n) for n in tree.body if isinstance(n,ast.ClassDef) and n.name in names]
    exec(compile(ast.Module(body=body,type_ignores=[]),str(file),'exec'),ORACLE)

def old(node_id,args):
    cls=ORACLE[LEDGER[node_id]['class']]
    return getattr(cls(),cls.FUNCTION)(**args)

def approved_expected(node_id,args):
    value=old(node_id,args)
    if node_id=='CR Index Increment':return (value[0],args['interval'],value[1])
    if node_id=='CR Text Concatenate':return (value[0],'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-save-text-to-file')
    return value

def new(node_id,args):
    result=NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args)
    return result.result if hasattr(result,'result') else result

def defaults(node_id):
    args={}
    for items in LEDGER[node_id]['source_inputs'].values():
        for name,spec in items.items():
            kind=spec[0];options=spec[1] if len(spec)>1 else {}
            if isinstance(kind,list): args[name]=kind[0]
            elif 'default' in options:args[name]=options['default']
            elif kind=='STRING':args[name]='some text'
            elif kind=='BOOLEAN':args[name]=True
            else:args[name]=object()
    if node_id=='CR String To Number':args['text']='2.5'
    if node_id=='CR String To Boolean':args['text']='true'
    return args

@pytest.mark.parametrize('node_id',list(LEDGER))
def test_pinned_behavior_default(node_id):
    args=defaults(node_id)
    assert new(node_id,args)==approved_expected(node_id,args)

@pytest.mark.parametrize('node_id',list(LEDGER))
def test_exact_static_schema(node_id):
    cls=NEW.NODE_CLASS_MAPPINGS[node_id];schema=cls.GET_SCHEMA();row=LEDGER[node_id]
    assert schema.node_id==node_id and schema.display_name==row['display_name'] and schema.category==row['category']
    assert schema.is_output_node==row['is_output_node']
    assert [o.io_type for o in schema.outputs]==row['return_types']
    assert [o.display_name for o in schema.outputs]==list(row['return_names'])
    assert cls.SDK_REFS is True and cls.SDK_PERMISSIONS==()
    flat={name:(group,spec) for group,items in row['source_inputs'].items() for name,spec in items.items()}
    assert [i.id for i in schema.inputs]==list(flat)
    for inp in schema.inputs:
        group,source=flat[inp.id]
        assert inp.optional==(group=='optional')
        if isinstance(source[0],list):assert inp.options==source[0]
        else:assert inp.io_type==source[0]
        for key,value in (source[1] if len(source)>1 else {}).items():assert inp.as_dict()[key]==value

@pytest.mark.parametrize('text',['','abc','α\nβ','line\x00<script>x</script>','  AbC\n'])
@pytest.mark.parametrize('node_id',['CR Text','CR Prompt Text','CR Text Length','CR String To Combo'])
def test_text_unicode_blank_adversarial(node_id,text):
    key='prompt' if node_id=='CR Prompt Text' else 'text'
    assert new(node_id,{key:text})==old(node_id,{key:text})

@pytest.mark.parametrize('operation',['uppercase','lowercase','capitalize','invert_case','reverse','trim','remove_spaces','invalid'])
@pytest.mark.parametrize('text',['',' ÄbC α\n🙂 ','<script>x</script>'])
def test_text_operation_native_invalid_outcome(operation,text):
    args=dict(operation=operation,text=text)
    assert new('CR Text Operation',args)==old('CR Text Operation',args)

@pytest.mark.parametrize('text',['','aaa','αβ','one\ntwo'])
@pytest.mark.parametrize('find,replace',[('a','b'),('','_'),('β','🙂'),('none','')])
def test_replacements_exact_order(text,find,replace):
    args=dict(text=text,find1=find,replace1=replace,find2=replace,replace2='X',find3='X',replace3='Z')
    assert new('CR Text Replace',args)==old('CR Text Replace',args)

@pytest.mark.parametrize('split,csv_mode,remove',[(False,False,False),(False,False,True),(True,False,False),(False,True,False),(True,True,True)])
@pytest.mark.parametrize('text',['','a\n# comment\n\nb,',"'a', 'b'",'"a", "b"','α,β'])
def test_multiline_comment_csv_and_combined_modes(split,csv_mode,remove,text):
    args=dict(text=text,chars_to_remove="'",split_string=split,remove_chars=remove,convert_from_csv=csv_mode,csv_quote_char="'")
    assert new('CR Multiline Text',args)==old('CR Multiline Text',args)

@pytest.mark.parametrize('text',['2','-2','2.5','-2.5','0','1e3','bad','.','-',' 2',''])
@pytest.mark.parametrize('round_integer',['round','round down','round up'])
def test_number_parse_native_rules_and_errors(text,round_integer):
    args=dict(text=text,round_integer=round_integer)
    try:expected=old('CR String To Number',args)
    except (ValueError,OverflowError) as error:
        with pytest.raises(type(error)):new('CR String To Number',args)
    else:assert new('CR String To Number',args)==expected

@pytest.mark.parametrize('text',['true','True','false','False','','yes'])
def test_boolean_native_uninitialized_error(text):
    args=dict(text=text)
    try:expected=old('CR String To Boolean',args)
    except UnboundLocalError:
        with pytest.raises(UnboundLocalError):new('CR String To Boolean',args)
    else:assert new('CR String To Boolean',args)==expected

@pytest.mark.parametrize('operation',['sin','cos','tan','sqrt','exp','log','neg','abs','invalid'])
@pytest.mark.parametrize('value',[-2.,0.,1.,2.5])
def test_math_native_tan_cos_bug_and_domain_errors(operation,value):
    args=dict(a=value,operation=operation,decimal_places=3)
    try:expected=old('CR Math Operation',args)
    except (ValueError,OverflowError) as error:
        with pytest.raises(type(error)):new('CR Math Operation',args)
    else:assert new('CR Math Operation',args)==expected

def test_upstream_cardinality_controls_and_explicit_approved_repairs():
    for node_id,args,declared,returned in [('CR Index Increment',dict(index=3,interval=2),3,2),('CR Text Concatenate',dict(text1='a',text2='b',separator='/'),2,1)]:
        assert len(NEW.NODE_CLASS_MAPPINGS[node_id].GET_SCHEMA().outputs)==declared
        assert len(old(node_id,args))==returned
        assert len(new(node_id,args))==declared and new(node_id,args)==approved_expected(node_id,args)

@pytest.mark.parametrize('index,interval',[(-10000,10000),(0,0),(1,-1),(12,3),(10000,-10000)])
def test_repaired_increment_exact_index_interval_and_source_help(index,interval):
    args=dict(index=index,interval=interval);native=old('CR Index Increment',args)
    assert native[0]==index+interval and len(native)==2
    assert new('CR Index Increment',args)==(native[0],interval,native[1])

@pytest.mark.parametrize('text1,text2,separator',[('','',''),('a','b','/'),('α','🙂','\n'),('<script>','</script>',''),('a\x00','b','_')])
def test_repaired_concat_exact_text_and_existing_help(text1,text2,separator):
    args=dict(text1=text1,text2=text2,separator=separator);native=old('CR Text Concatenate',args)
    actual=new('CR Text Concatenate',args)
    assert len(native)==1 and actual[0]==native[0] and len(actual)==2
    assert actual[1]=='https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-save-text-to-file'

def test_preallocation_workload_limits():
    for node,args in [('CR Text',dict(text='x'*262145)),('CR Text Replace',dict(text='x'*1000,find1='',replace1='z'*1000)),('CR Seed',dict(seed=1<<5000)),('CR Text Blacklist',dict(text='x'*10000,blacklist_words='a\n'*4097))]:
        with pytest.raises(ValueError,match='Comfyroll'):new(node,args)

@pytest.mark.parametrize('node_id',[k for k,v in LEDGER.items() if Path(v['source_path']).name=='nodes_utils_logic.py'])
@pytest.mark.parametrize('choice',[0,1,2,3,4,'invalid'])
def test_all_routing_branches_and_direct_fallback(node_id,choice):
    args=defaults(node_id);args['Input']=choice
    expected=old(node_id,args);actual=new(node_id,args)
    assert actual==expected
    for a,b in zip(actual,expected):
        if type(b) is object:assert a is b

@pytest.mark.parametrize('text,delimiter',[('',';'),('a,b,c,d,e',','),('α||β','||'),(' a ; b ',';'),('abc','')])
def test_split_four_outputs_and_empty_delimiter_error(text,delimiter):
    args=dict(text=text,delimiter=delimiter)
    try:expected=old('CR Split String',args)
    except ValueError:
        with pytest.raises(ValueError):new('CR Split String',args)
    else:assert new('CR Split String',args)==expected

@pytest.mark.parametrize('prompt,search',[('prefix !x=2 rest','!x'),('!x=true','!x'),('!x="two words"','!x'),('!x','!x'),('!x=','!x'),('abc',''),('!x=2.5','!x'),('none','!missing')])
def test_prompt_parameter_native_indexing_and_parse(prompt,search):
    args=dict(prompt=prompt,search_string=search)
    try:expected=old('CR Get Parameter From Prompt',args)
    except IndexError:
        with pytest.raises(IndexError):new('CR Get Parameter From Prompt',args)
    else:assert new('CR Get Parameter From Prompt',args)==expected

@pytest.mark.parametrize('text,words,replacement',[('a b a','a\n b ','x'),('αβ','β','🙂'),('a','\n\n','x'),('ab','a\nb','b'),('a','#a\na','')])
def test_blacklist_order_and_blank_lines(text,words,replacement):
    args=dict(text=text,blacklist_words=words,replacement_text=replacement)
    assert new('CR Text Blacklist',args)==old('CR Text Blacklist',args)

def test_real_guest_outer_all_draft_ids_zero_capabilities():
    import execution
    import torch
    async def run():
        previous=_sdk.providers.execution_backend
        session=await GuestSession('ned-comfyroll-pure',guest_runtime_root=V2).start()
        class Backend:
            async def dispatch(self,plan,local_call,runtime):return await session.execute(plan,runtime,capabilities=())
        _sdk.providers.register_execution_backend(Backend())
        try:
            for node_id in LEDGER:
                cls=NEW.NODE_CLASS_MAPPINGS[node_id];schema=cls.GET_SCHEMA();args=defaults(node_id)
                for key,value in list(args.items()):
                    if type(value) is object:
                        kind=next(i.io_type for i in schema.inputs if i.id==key)
                        if kind=='IMAGE':args[key]=torch.full((1,3,4,3),.1 if key.endswith('1') else .2)
                        elif kind=='LATENT':args[key]={'samples':torch.ones(1,4,2,2)}
                        elif kind=='CONDITIONING':args[key]=[[torch.ones(1,2,3),{}]]
                        else:args[key]={'recording_model':kind,'name':key}
                expected=approved_expected(node_id,args)
                result=await execution._async_map_node_over_list(prompt_id='ned-comfyroll',unique_id='1',obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                actual=result[0].result
                assert len(actual)==len(expected),node_id
                for a,b in zip(actual,expected):
                    if isinstance(b,torch.Tensor):assert torch.equal(a,b) and a.dtype==b.dtype
                    elif type(b) is dict and 'samples' in b:assert torch.equal(a['samples'],b['samples'])
                    elif type(b) is list and b and isinstance(b[0],list):assert torch.equal(a[0][0],b[0][0])
                    else:assert a==b,(node_id,a,b)
            assert session.last_guest_pid not in (None,os.getpid())
        finally:
            await session.kill();_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())

@pytest.mark.parametrize('node_id,kind,names',[('CR Model Input Switch','MODEL',('model1','model2')),('CR Clip Input Switch','CLIP',('clip1','clip2')),('CR VAE Input Switch','VAE',('VAE1','VAE2'))])
def test_real_outer_model_handles_routing_identity(node_id,kind,names):
    import execution
    def deny(*args,**kwargs):raise AssertionError('No model methods during routing')
    def make():
        if kind=='MODEL':return types.SimpleNamespace(model_options={},load_device='cpu')
        if kind=='CLIP':return types.SimpleNamespace(tokenize=deny)
        return types.SimpleNamespace(encode=deny,decode=deny)
    async def run():
        previous=_sdk.providers.execution_backend;session=await GuestSession('ned-comfyroll-model-routing',guest_runtime_root=V2).start()
        class Backend:
            async def dispatch(self,plan,local_call,runtime):
                assert all(isinstance(plan.inputs[key],_sdk.Ref) for key in names)
                return await session.execute(plan,runtime,capabilities=())
        _sdk.providers.register_execution_backend(Backend())
        try:
            cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA();first,second=make(),make()
            assert _sdk._ref_type_for(first)[1]==kind
            for choice in (1,2):
                args={names[0]:first,names[1]:second,'Input':choice}
                result=await execution._async_map_node_over_list(prompt_id='ned-routing',unique_id='1',obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                assert result[0].result[0] is (first if choice==1 else second)
        finally:await session.kill();_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())

def test_actual_guest_assets_capability_denial():
    import ned_comfyroll_secure.tests.comfyroll_authority_probe as probe
    from comfy_secure_nodes.transport import wire
    async def run():
        refs=_sdk.InProcessRefResolver();plan=_sdk.ExecutionPlan(prompt_id='ned-denial',node_id='1',node_type='AssetsProbe',node_module=probe.__name__,inputs={},permissions=())
        runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
        session=await GuestSession('ned-comfyroll-denial',guest_runtime_root=V2).start()
        try:
            with pytest.raises(wire.WireError,match='assets'):await session.execute(plan,runtime,capabilities=())
            assert session.pid not in (None,os.getpid()) and session.alive()
        finally:await session.kill()
    asyncio.run(run())

def test_full_census_remains199_and_resources_pristine():
    tree=ast.parse((PACK/'node_mappings.py').read_text())
    mapping=next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='NODE_CLASS_MAPPINGS' for t in n.targets))
    assert len(mapping.keys)==199 and set(LEDGER).issubset(NEW.NODE_CLASS_MAPPINGS)
    assert all(r['status']=='pending' for r in LEDGER.values())
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))
