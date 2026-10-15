"""Pinned stack/rounding policy and actual canonical tiny patch weights; no trained inference."""
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
sys.argv=['ned-comfyroll-merge','--cpu']
CORE=Path(os.environ['COMFY_CORE_ROOT'])
sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy_api.latest import _sdk
from comfy.model_patcher import ModelPatcher
from comfy.sd import CLIP
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.transport import wire
import comfy.sd
import folder_paths

V2=Path(__file__).resolve().parents[1];PACK=V2.parent
spec=importlib.util.spec_from_file_location('ned_comfyroll_merge_pack',V2/'__init__.py',submodule_search_locations=[str(V2)])
NEW=importlib.util.module_from_spec(spec);sys.modules[spec.name]=NEW;spec.loader.exec_module(NEW)
LEDGER=json.loads((V2/'merge-draft-ledger.json').read_text())
icons=ast.literal_eval(ast.parse((PACK/'categories.py').read_text()).body[0].value)
tree=ast.parse((PACK/'nodes/nodes_model_merge.py').read_text())

def patcher(value,dtype):
    model=torch.nn.Module();model.diffusion_model=torch.nn.Linear(3,2);model.encoder=torch.nn.Linear(3,2)
    model.encoder.register_buffer('position_ids',torch.arange(3));model.encoder.logit_scale=torch.nn.Parameter(torch.tensor(2.))
    model.to(dtype=dtype)
    for i,p in enumerate(model.parameters()):p.data.fill_(value+i/8)
    result=ModelPatcher(model,torch.device('cpu'),torch.device('cpu'))
    result.model_options['retained']=value
    result.add_patches({'diffusion_model.weight':(torch.full((2,3),.125,dtype=dtype),)})
    return result

def clip(value,dtype):
    result=CLIP(no_init=True);result.patcher=patcher(value,dtype);result.cond_stage_model=result.patcher.model
    result.tokenizer=object();result.layer_idx=-2;result.tokenizer_options={'retained':value}
    result.use_clip_schedule=True;result.apply_hooks_to_conds=False
    return result

class VaeDouble:
    def encode(self,*args):raise AssertionError('Not an inference test')
    def decode(self,*args):raise AssertionError('Not an inference test')

def weights(value):
    obj=value.patcher if isinstance(value,CLIP) else value
    return {k:obj.patch_weight_to_device(k,device_to=torch.device('cpu'),return_weight=True) for k in obj.model_state_dict()}

def exact_weights(actual,expected):
    a,b=weights(actual),weights(expected);assert a.keys()==b.keys()
    for key in a:assert a[key].dtype==b[key].dtype and torch.equal(a[key],b[key]),key

def oracle(load):
    ns={'icons':icons,'folder_paths':types.SimpleNamespace(get_filename_list=lambda k:[],get_full_path=lambda k,n:n,get_folder_paths=lambda k:[]),
        'comfy':types.SimpleNamespace(sd=types.SimpleNamespace(load_checkpoint_guess_config=load))}
    exec(compile(ast.Module(body=copy.deepcopy([n for n in tree.body if isinstance(n,ast.ClassDef)]),type_ignores=[]),str(PACK/'nodes/nodes_model_merge.py'),'exec'),ns)
    return ns

@pytest.fixture
def loaders(monkeypatch):
    state={'dtype':torch.float32,'calls':[],'loaded':[]}
    def load(name,**kwargs):
        value={'one':1.,'two':3.,'three':5.}[str(name)];state['calls'].append(str(name))
        result=(patcher(value,state['dtype']),clip(value,state['dtype']),VaeDouble(),None)
        state['loaded'].append(result);return result
    monkeypatch.setattr(folder_paths,'get_full_path_or_raise',lambda kind,name:name)
    monkeypatch.setattr(folder_paths,'get_folder_paths',lambda kind:[])
    monkeypatch.setattr(comfy.sd,'load_checkpoint_guess_config',load)
    state['load']=load;return state

STACKS=[ [('one',.2,.3),('two',.8,.7)], [('one',1.,2.),('two',2.,1.),('three',3.,4.)],
        [('one',1.,2.),('two',0.,2.)], [('one',-.5,-.25),('two',1.5,1.25)] ]
@pytest.mark.parametrize('dtype',[torch.float32,torch.float16,torch.bfloat16])
@pytest.mark.parametrize('stack',STACKS)
@pytest.mark.parametrize('method',['Recursive','Weighted'])
@pytest.mark.parametrize('normalise',['Yes','No'])
@pytest.mark.parametrize('factor',[0.,.37,1.])
def test_sequential_patch_weights_rounding_normalization_and_info_exact(loaders,dtype,stack,method,normalise,factor):
    loaders['dtype']=dtype;args=dict(model_stack=stack,merge_method=method,normalise_ratios=normalise,weight_factor=factor)
    expected=oracle(loaders['load'])['CR_ApplyModelMerge']().merge(**args)
    async def run():
        refs=_sdk.InProcessRefResolver()
        with _sdk.bind_runtime(refs,types.SimpleNamespace(models=_sdk._InProcessModels()),_sdk.InProcessOps()):
            actual=await NEW.secure_merge.CR_ApplyModelMerge.execute(**args)
        exact_weights(await refs.resolve(actual.result[0]),expected[0]);exact_weights(await refs.resolve(actual.result[1]),expected[1])
        assert actual.result[2:]==expected[2:]
    asyncio.run(run())
    assert loaders['calls']==[row[0] for row in stack]*2

@pytest.mark.parametrize('stack',[[('one',1.,0.),('two',1.,0.)],[('one',1.,1.),('two',-1.,1.)]])
def test_native_zero_division_is_not_silently_normalized(loaders,stack):
    args=dict(model_stack=stack,merge_method='Weighted',normalise_ratios='Yes',weight_factor=.5)
    with pytest.raises(ZeroDivisionError):oracle(loaders['load'])['CR_ApplyModelMerge']().merge(**args)
    async def run():
        with _sdk.bind_runtime(_sdk.InProcessRefResolver(),types.SimpleNamespace(models=_sdk._InProcessModels()),_sdk.InProcessOps()):
            with pytest.raises(ZeroDivisionError):await NEW.secure_merge.CR_ApplyModelMerge.execute(**args)
    asyncio.run(run())

def stack_args(**extra):
    args={'model_stack':[('None',1.,1.),('one',.1,.2)]}
    for i in range(1,4):args.update({f'switch_{i}':'On',f'ckpt_name{i}':['one','two','three'][i-1],f'model_ratio{i}':i/4,f'clip_ratio{i}':-i/4})
    args.update(extra);return args

@pytest.mark.parametrize('switches',[('On','On','On'),('Off','On','Off'),('Off','Off','Off')])
def test_model_stack_order_duplicates_and_none_exact(switches):
    args=stack_args()
    for i,switch in enumerate(switches,1):args[f'switch_{i}']=switch
    expected=oracle(None)['CR_ModelMergeStack']().list_checkpoints(**args)
    assert NEW.secure_merge.CR_ModelMergeStack.execute(**args).result==expected
    assert args['model_stack']==[('None',1.,1.),('one',.1,.2)]

@pytest.mark.parametrize('node_id',list(LEDGER))
def test_exact_schemas_and_permissions(node_id):
    cls=NEW.NODE_CLASS_MAPPINGS[node_id];row=LEDGER[node_id];schema=cls.GET_SCHEMA()
    assert schema.node_id==node_id and schema.display_name==row['display_name'] and schema.category==row['category']
    assert [o.io_type for o in schema.outputs]==row['return_types'] and [o.display_name for o in schema.outputs]==row['return_names']
    flat={k:(group,spec) for group,items in row['source_inputs'].items() for k,spec in items.items()}
    assert [i.id for i in schema.inputs]==list(flat)
    for inp in schema.inputs:
        group,source=flat[inp.id];assert inp.optional==(group=='optional')
        if isinstance(source[0],list):assert inp.options==source[0]
        else:assert inp.io_type==source[0]
        for k,v in (source[1] if len(source)>1 else {}).items():assert inp.as_dict()[k]==v
    assert tuple(cls.SDK_PERMISSIONS)==tuple(row['permissions'])

def test_fresh_guest_outer_real_patch_weights_and_models_denial(loaders):
    import execution
    async def run():
        previous=_sdk.providers.execution_backend;session=await GuestSession('ned-comfyroll-model-merge',guest_runtime_root=V2).start()
        class Backend:
            caps=('models',)
            async def dispatch(self,plan,local_call,runtime):return await session.execute(plan,runtime,capabilities=self.caps)
        backend=Backend();_sdk.providers.register_execution_backend(backend)
        async def execute(cls,args):
            cls.GET_SCHEMA()
            result=await execution._async_map_node_over_list(prompt_id='ned-merge',unique_id='1',obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
            return result[0].result
        try:
            for dtype in (torch.float32,torch.float16,torch.bfloat16):
                loaders['dtype']=dtype
                for method in ('Recursive','Weighted'):
                    args=dict(model_stack=STACKS[1],merge_method=method,normalise_ratios='Yes',weight_factor=.37)
                    expected=oracle(loaders['load'])['CR_ApplyModelMerge']().merge(**args)
                    actual=await execute(NEW.secure_merge.CR_ApplyModelMerge,args)
                    exact_weights(actual[0],expected[0]);exact_weights(actual[1],expected[1]);assert actual[2:]==expected[2:]
            backend.caps=()
            with pytest.raises(wire.WireError,match='models'):await execute(NEW.secure_merge.CR_ApplyModelMerge,args)
            before=len(loaders['calls'])
            with pytest.raises(wire.WireError,match='No active checkpoints'):
                await execute(NEW.secure_merge.CR_ApplyModelMerge,dict(model_stack=[],merge_method='Recursive',normalise_ratios='Yes',weight_factor=1.))
            assert len(loaders['calls'])==before
            backend.caps=('models',)
            one=await execute(NEW.secure_merge.CR_ApplyModelMerge,dict(model_stack=[('one',1.,1.)],merge_method='Recursive',normalise_ratios='Yes',weight_factor=1.))
            assert len(one)==4 and isinstance(one[0],ModelPatcher) and isinstance(one[1],CLIP)
            assert type(one[2]) is str and type(one[3]) is str
            backend.caps=()
            args=stack_args();actual=await execute(NEW.secure_merge.CR_ModelMergeStack,args)
            assert actual==NEW.secure_merge.CR_ModelMergeStack.execute(**args).result
            assert session.last_guest_pid not in (None,os.getpid())
        finally:await session.kill();_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())

def test_native_empty_and_single_defects_and_authorized_pack_repairs(loaders):
    old=oracle(loaders['load'])['CR_ApplyModelMerge']()
    assert old.merge([], 'Recursive','Yes',1.)==()
    pinned_one=old.merge([('one',1.,1.)],'Recursive','Yes',1.)
    assert len(pinned_one)==4 and isinstance(pinned_one[2],VaeDouble) and pinned_one[3] is None
    async def run():
        refs=_sdk.InProcessRefResolver()
        with _sdk.bind_runtime(refs,types.SimpleNamespace(models=_sdk._InProcessModels()),_sdk.InProcessOps()):
            before=len(loaders['calls'])
            with pytest.raises(ValueError,match='No active checkpoints'):
                await NEW.secure_merge.CR_ApplyModelMerge.execute([], 'Recursive','Yes',1.)
            assert len(loaders['calls'])==before
            one=await NEW.secure_merge.CR_ApplyModelMerge.execute([('one',1.,1.)],'Recursive','Yes',1.)
        assert len(one.result)==4 and isinstance(await refs.resolve(one.result[0]),ModelPatcher) and isinstance(await refs.resolve(one.result[1]),CLIP)
        assert type(one.result[2]) is str and type(one.result[3]) is str
        assert 'no merge applied' in one.result[2]
        assert all(row['status']=='pending' for row in LEDGER.values())
    asyncio.run(run())
