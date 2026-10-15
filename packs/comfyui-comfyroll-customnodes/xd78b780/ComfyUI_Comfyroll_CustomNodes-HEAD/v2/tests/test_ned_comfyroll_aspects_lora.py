"""Native algorithms, public LoRA chain and actual guest/outer proofs; not trained inference."""
import ast
import asyncio
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import types

import pytest
import torch

sys.dont_write_bytecode=True
sys.argv=['ned-comfyroll-tests','--cpu']
CORE=Path(os.environ['COMFY_CORE_ROOT']);sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.transport import wire

spec=importlib.util.spec_from_file_location('ned_comfyroll_secure',V2/'__init__.py',submodule_search_locations=[str(V2)])
NEW=importlib.util.module_from_spec(spec);sys.modules[spec.name]=NEW;spec.loader.exec_module(NEW)
ASPECTS=json.loads((V2/'aspect-draft-ledger.json').read_text())
LORAS=json.loads((V2/'lora-draft-ledger.json').read_text())
icons=ast.literal_eval(ast.parse((PACK/'categories.py').read_text()).body[0].value)
tree=ast.parse((PACK/'nodes/nodes_aspect_ratio.py').read_text())
old_ns={'icons':icons,'torch':torch}
selected=[copy.deepcopy(n) for n in tree.body if isinstance(n,(ast.Assign,ast.ClassDef)) and (isinstance(n,ast.ClassDef) or any(isinstance(t,ast.Name) and t.id=='PRINT_SIZES' for t in n.targets))]
exec(compile(ast.Module(body=selected,type_ignores=[]),str(PACK/'nodes/nodes_aspect_ratio.py'),'exec'),old_ns)

def args_for(node_id,**overrides):
    args={}
    for name,spec in ASPECTS[node_id]['source_inputs']['required'].items():
        args[name]=spec[0][0] if isinstance(spec[0],list) else spec[1]['default']
    args.update(overrides)
    return args

def old_aspect(node_id,args):
    cls=old_ns[ASPECTS[node_id]['class']];return getattr(cls(),cls.FUNCTION)(**args)

def exact(actual,expected):
    assert len(actual)==len(expected)
    for a,b in zip(actual,expected):
        if isinstance(b,dict):
            assert set(a)==set(b)=={'samples'}
            assert a['samples'].dtype==b['samples'].dtype==torch.float32
            assert a['samples'].shape==b['samples'].shape and torch.equal(a['samples'],b['samples'])
        else:assert a==b and type(a) is type(b)

CASES=[(node_id,choice,swap) for node_id,row in ASPECTS.items() for choice in row['source_inputs']['required']['aspect_ratio'][0] for swap in ('Off','On')]
@pytest.mark.parametrize('node_id,choice,swap',CASES)
def test_every_ordered_choice_and_swap_exact(node_id,choice,swap):
    args=args_for(node_id,aspect_ratio=choice,swap_dimensions=swap,width=101,height=79,batch_size=1)
    exact(NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args).result,old_aspect(node_id,args))

@pytest.mark.parametrize('node_id',list(ASPECTS))
@pytest.mark.parametrize('dims,batch,scale',[((65,71),2,.1),((8,9),0,1.),((127,33),2,1.3)])
def test_floor_zero_grid_batch_and_noncompounding_dimensions(node_id,dims,batch,scale):
    args=args_for(node_id,width=dims[0],height=dims[1],batch_size=batch,aspect_ratio='custom')
    if 'prescale_factor' in args:args['prescale_factor']=scale
    exact(NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args).result,old_aspect(node_id,args))
    exact(NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args).result,old_aspect(node_id,args))

@pytest.mark.parametrize('node_id',list(ASPECTS))
def test_preallocation_budget_and_negative_native_error(node_id,monkeypatch):
    cls=NEW.NODE_CLASS_MAPPINGS[node_id]
    with pytest.raises(ValueError,match='whole-batch'):
        cls.execute(**args_for(node_id,width=8192,height=8192,batch_size=64,aspect_ratio='custom'))
    calls=[]
    monkeypatch.setattr(NEW.secure_aspects.torch,'zeros',lambda *a,**k:calls.append((a,k)))
    with pytest.raises(ValueError):cls.execute(**args_for(node_id,width=100000,height=8192,batch_size=64,aspect_ratio='custom'))
    with pytest.raises(RuntimeError,match='negative dimension'):cls.execute(**args_for(node_id,width=-16,height=64,aspect_ratio='custom'))
    with pytest.raises(RuntimeError,match='negative dimension'):cls.execute(**args_for(node_id,width=64,height=64,batch_size=-1,aspect_ratio='custom'))
    assert not calls

@pytest.mark.parametrize('node_id',list(ASPECTS)+list(LORAS))
def test_exact_metadata_and_declarations(node_id):
    row=(ASPECTS|LORAS)[node_id];cls=NEW.NODE_CLASS_MAPPINGS[node_id];schema=cls.GET_SCHEMA()
    assert schema.node_id==node_id and schema.display_name==row['display_name'] and schema.category==row['category']
    assert [o.io_type for o in schema.outputs]==row['return_types']
    assert [o.display_name for o in schema.outputs]==row['return_names']
    assert tuple(cls.SDK_PERMISSIONS)==tuple(row['permissions'])
    flat={k:(group,spec) for group,items in row['source_inputs'].items() for k,spec in items.items()}
    assert [i.id for i in schema.inputs]==list(flat)
    for inp in schema.inputs:
        group,source=flat[inp.id];assert inp.optional==(group=='optional')
        if isinstance(source[0],list):
            assert inp.options==source[0]
            if inp.id.startswith('lora_name'):assert inp.remote.route=='/secure-nodes/models/loras'
        else:assert inp.io_type==source[0]
        for k,v in (source[1] if len(source)>1 else {}).items():assert inp.as_dict()[k]==v

def test_real_guest_outer_all_aspects_raw_and_deny():
    import execution
    async def run():
        previous=_sdk.providers.execution_backend;session=await GuestSession('ned-comfyroll-aspects',guest_runtime_root=V2).start()
        class Backend:
            caps=('raw',)
            async def dispatch(self,plan,local_call,runtime):
                assert plan.input_mode=='values'
                return await session.execute(plan,runtime,capabilities=self.caps)
        backend=Backend();_sdk.providers.register_execution_backend(backend)
        try:
            for node_id in ASPECTS:
                cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA()
                for width,height in ((101,79),(6,7)):
                    args=args_for(node_id,width=width,height=height,batch_size=2,aspect_ratio='custom')
                    result=await execution._async_map_node_over_list(prompt_id='ned-aspects',unique_id='1',obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                    exact(result[0].result,old_aspect(node_id,args))
            backend.caps=()
            with pytest.raises(wire.WireError,match='raw'):
                await execution._async_map_node_over_list(prompt_id='ned-aspect-denial',unique_id='1',obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
            assert session.last_guest_pid not in (None,os.getpid())
        finally:await session.kill();_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())

def lora_args(**overrides):
    args={}
    for i in range(1,4):args.update({f'lora_name_{i}':f'folder/{i}.safetensors',f'switch_{i}':'On',f'model_weight_{i}':i*.1,f'clip_weight_{i}':-i*.1})
    args.update(overrides);return args

@pytest.mark.parametrize('switches',[('On','On','On'),('On','Off','On'),('Off','Off','Off')])
@pytest.mark.parametrize('names',[('a','b','c'),('None','a','a')])
def test_stack_selection_order_filter_and_caller_identity(switches,names):
    path=PACK/'nodes/nodes_lora.py';tree=ast.parse(path.read_text())
    cls_ast=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='CR_LoRAStack')
    ns={'icons':icons};exec(compile(ast.Module(body=[copy.deepcopy(cls_ast)],type_ignores=[]),str(path),'exec'),ns)
    args=lora_args(lora_stack=[('None',1.,1.),('keep',2.,-2.)])
    for i in range(1,4):args[f'switch_{i}']=switches[i-1];args[f'lora_name_{i}']=names[i-1]
    expected=ns['CR_LoRAStack']().lora_stacker(**args)
    assert NEW.secure_lora.CR_LoRAStack.execute(**args).result==expected
    assert len(args['lora_stack'])==2

@pytest.mark.parametrize('name',['../secret','/tmp/file','a//b','a\\b','a/./b','a\x00b','C:x',''])
def test_logical_lora_name_boundaries(name):
    with pytest.raises(ValueError):NEW.secure_lora.CR_LoRAStack.execute(**lora_args(lora_name_1=name))

def test_real_guest_lora_stack_plain_data_zero_authority():
    import execution
    async def run():
        previous=_sdk.providers.execution_backend;session=await GuestSession('ned-comfyroll-lora-stack',guest_runtime_root=V2).start()
        class Backend:
            async def dispatch(self,plan,local_call,runtime):return await session.execute(plan,runtime,capabilities=())
        _sdk.providers.register_execution_backend(Backend())
        try:
            cls=NEW.secure_lora.CR_LoRAStack;cls.GET_SCHEMA();args=lora_args(lora_stack=[('keep',2.,-2.)])
            result=await execution._async_map_node_over_list(prompt_id='ned-lora-stack',unique_id='1',obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
            assert result[0].result==cls.execute(**args).result
            assert session.last_guest_pid not in (None,os.getpid())
        finally:await session.kill();_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())

def test_full_census_partial_draft_only():
    assert set(ASPECTS|LORAS).issubset(NEW.NODE_CLASS_MAPPINGS)
    assert all(row['status']=='pending' for row in (ASPECTS|LORAS).values())
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

def test_real_managed_lora_loader_guest_outer_order_bypass_and_denial(tmp_path,monkeypatch):
    import execution
    import folder_paths
    import comfy.sd
    import comfy.utils
    from safetensors.torch import save_file
    root=tmp_path/'loras';root.mkdir()
    for i in (1,2):save_file({'marker':torch.tensor([float(i)])},str(root/f'{i}.safetensors'))
    old_paths=folder_paths.get_folder_paths
    monkeypatch.setattr(folder_paths,'get_folder_paths',lambda kind:[str(root)] if kind=='loras' else old_paths(kind))
    old_full=folder_paths.get_full_path
    monkeypatch.setattr(folder_paths,'get_full_path',lambda kind,name:str(root/name) if kind=='loras' and (root/name).is_file() else old_full(kind,name))
    class ModelTrace:
        def __init__(self,trace=()):self.model_options={};self.load_device='cpu';self.trace=trace
    class ClipTrace:
        def __init__(self,trace=()):self.trace=trace
        def tokenize(self,*args):raise AssertionError('No inference/tokenization in this recording control')
    applications=[]
    def apply(model,clip,state,sm,sc,**kwargs):
        marker=float(state['marker'][0]);applications.append((marker,sm,sc))
        return ModelTrace(model.trace+((marker,sm),)),ClipTrace(clip.trace+((marker,sc),))
    monkeypatch.setattr(comfy.sd,'load_lora_for_models',apply)
    source=ast.parse((PACK/'nodes/nodes_lora.py').read_text())
    names={'CR_LoraLoader','CR_ApplyLoRAStack'}
    oracle={'icons':icons,'folder_paths':folder_paths,'comfy':types.SimpleNamespace(sd=comfy.sd,utils=comfy.utils)}
    exec(compile(ast.Module(body=[copy.deepcopy(n) for n in source.body if isinstance(n,ast.ClassDef) and n.name in names],type_ignores=[]),str(PACK/'nodes/nodes_lora.py'),'exec'),oracle)
    async def run():
        previous=_sdk.providers.execution_backend;session=await GuestSession('ned-comfyroll-managed-loras',guest_runtime_root=V2).start()
        class Backend:
            caps=('assets',)
            async def dispatch(self,plan,local_call,runtime):
                assert isinstance(plan.inputs['model'],_sdk.ModelRef) and isinstance(plan.inputs['clip'],_sdk.ClipRef)
                return await session.execute(plan,runtime,capabilities=self.caps)
        backend=Backend();_sdk.providers.register_execution_backend(backend)
        async def execute(cls,args):
            cls.GET_SCHEMA()
            output=await execution._async_map_node_over_list(prompt_id='ned-managed-loras',unique_id='1',obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
            return output[0].result
        try:
            for stack in ([],[('1.safetensors',.2,-.3)],[('2.safetensors',-.7,.8),('1.safetensors',.2,-.3)]):
                first,clip=ModelTrace(),ClipTrace();args=dict(model=first,clip=clip,lora_stack=stack)
                expected=oracle['CR_ApplyLoRAStack']().apply_lora_stack(**args)
                actual=await execute(NEW.secure_lora.CR_ApplyLoRAStack,args)
                assert actual[0].trace==expected[0].trace and actual[1].trace==expected[1].trace and actual[2]==expected[2]
                if not stack:assert actual[0] is first and actual[1] is clip
                assert first.trace==() and clip.trace==()
            for switch,name,sm,sc in [('On','1.safetensors',.25,-.5),('Off','1.safetensors',1.,1.),('On','None',1.,1.),('On','1.safetensors',0.,0.)]:
                first,clip=ModelTrace(),ClipTrace();args=dict(model=first,clip=clip,switch=switch,lora_name=name,strength_model=sm,strength_clip=sc)
                expected=oracle['CR_LoraLoader']().load_lora(**args)
                actual=await execute(NEW.secure_lora.CR_LoraLoader,args)
                assert actual[0].trace==expected[0].trace and actual[1].trace==expected[1].trace and actual[2]==expected[2]
                if switch=='Off' or name=='None' or sm==sc==0:assert actual[0] is first and actual[1] is clip
            backend.caps=()
            with pytest.raises(wire.WireError,match='assets'):
                await execute(NEW.secure_lora.CR_LoraLoader,dict(model=ModelTrace(),clip=ClipTrace(),switch='On',lora_name='1.safetensors',strength_model=1.,strength_clip=1.))
            assert session.last_guest_pid not in (None,os.getpid())
        finally:await session.kill();_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
    assert applications
