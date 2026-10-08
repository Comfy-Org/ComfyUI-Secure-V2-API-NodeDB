"""Approved output normalization; canonical tiny objects/recording loader, not inference."""
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

sys.dont_write_bytecode=True;sys.argv=['ned-comfyroll-cycle-models','--cpu']
CORE=Path(os.environ['COMFY_CORE_ROOT']);sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy_api.latest import _sdk
from comfy.model_patcher import ModelPatcher
from comfy.sd import CLIP
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.transport import wire
import comfy.sd
import folder_paths
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
spec=importlib.util.spec_from_file_location('ned_comfyroll_cycle_models_pack',V2/'__init__.py',submodule_search_locations=[str(V2)])
NEW=importlib.util.module_from_spec(spec);sys.modules[spec.name]=NEW;spec.loader.exec_module(NEW)
LEDGER=json.loads((V2/'cycle-models-draft-ledger.json').read_text())
icons=ast.literal_eval(ast.parse((PACK/'categories.py').read_text()).body[0].value)
tree=ast.parse((PACK/'nodes/nodes_animation_cyclers.py').read_text());source=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='CR_CycleModels')

def patcher(value):
    model=torch.nn.Module();model.diffusion_model=torch.nn.Linear(3,2)
    for p in model.parameters():p.data.fill_(value)
    result=ModelPatcher(model,torch.device('cpu'),torch.device('cpu'));result.model_options['retained']=value
    return result

def clip(value):
    result=CLIP(no_init=True);result.patcher=patcher(value);result.cond_stage_model=result.patcher.model
    result.tokenizer=object();result.layer_idx=-2;result.tokenizer_options={'retained':value}
    result.use_clip_schedule=True;result.apply_hooks_to_conds=False
    return result

class VaeDouble:
    def encode(self,*args):raise AssertionError('Not an inference test')
    def decode(self,*args):raise AssertionError('Not an inference test')

@pytest.fixture
def loaders(monkeypatch):
    state={'calls':[],'loaded':[]}
    def load(name,**kwargs):
        value={'one':1.,'two':2.,'three':3.}[str(name)];state['calls'].append(str(name))
        result=(patcher(value),clip(value),VaeDouble(),None);state['loaded'].append(result);return result
    monkeypatch.setattr(folder_paths,'get_full_path_or_raise',lambda kind,name:name)
    monkeypatch.setattr(folder_paths,'get_folder_paths',lambda kind:[])
    monkeypatch.setattr(comfy.sd,'load_checkpoint_guess_config',load);state['load']=load
    ns={'icons':icons,'folder_paths':types.SimpleNamespace(get_full_path=lambda k,n:n,get_folder_paths=lambda k:[]),'comfy':types.SimpleNamespace(sd=types.SimpleNamespace(load_checkpoint_guess_config=load))}
    exec(compile(ast.Module(body=[copy.deepcopy(source)],type_ignores=[]),str(PACK/'nodes/nodes_animation_cyclers.py'),'exec'),ns)
    state['old']=ns['CR_CycleModels'];return state

def args_for(**changes):
    args=dict(mode='Sequential',model=patcher(11),clip=clip(17),model_list=[('A','one'),('B','two'),('C','three')],frame_interval=30,loops=1,current_frame=31)
    args.update(changes);return args

def source_outcome(loaders,args):
    try:return 'value',loaders['old']().cycle_models(**args)
    except Exception as exc:return 'error',type(exc),str(exc)

async def migrated(args):
    refs=_sdk.InProcessRefResolver()
    wrapped=await _sdk.wrap_inputs(refs,args)
    with _sdk.bind_runtime(refs,types.SimpleNamespace(models=_sdk._InProcessModels()),_sdk.InProcessOps()):
        result=await NEW.secure_cycle_models.CR_CycleModels.execute(**wrapped)
    if result is None:return None
    values=[]
    for value in result.result:
        values.append(await refs.resolve(value) if isinstance(value,(_sdk.ModelRef,_sdk.ClipRef,_sdk.VaeRef)) else value)
    return tuple(values)

@pytest.mark.parametrize('mode',['Off','Sequential'])
@pytest.mark.parametrize('frame',[-1,0,1,29,30,31,99,0.0,1.5])
@pytest.mark.parametrize('interval',[0,1,30])
@pytest.mark.parametrize('loops',[-1,0,1,3])
def test_pinned_selection_floor_loop_native_errors_and_explicit_normalized_outputs(loaders,mode,frame,interval,loops):
    args=args_for(mode=mode,current_frame=frame,frame_interval=interval,loops=loops)
    source_result=source_outcome(loaders,args);source_calls=list(loaders['calls']);loaders['calls'].clear()
    try:actual=('value',asyncio.run(migrated(args)))
    except Exception as exc:actual=('error',type(exc),str(exc))
    assert actual[0]==source_result[0]
    if actual[0]=='error':assert actual[1:]==source_result[1:]
    elif mode=='Off' or frame==0:
        assert len(source_result[1])==3 and len(actual[1])==4
        assert actual[1][0] is args['model'] and actual[1][1] is args['clip'] and actual[1][2] is None
        assert actual[1][3]==source_result[1][2]
    else:
        assert len(source_result[1])==2 and len(actual[1])==4
        assert isinstance(actual[1][0],ModelPatcher) and isinstance(actual[1][1],CLIP) and isinstance(actual[1][2],VaeDouble)
        assert actual[1][3]==source_result[1][1]
        assert actual[1][0].model_options==source_result[1][0][0].model_options
        assert actual[1][1].tokenizer_options==source_result[1][0][1].tokenizer_options
    assert loaders['calls']==source_calls

def test_exact_schema_defaults_and_model_only_permission():
    row=LEDGER['CR Cycle Models'];cls=NEW.secure_cycle_models.CR_CycleModels;schema=cls.GET_SCHEMA()
    assert schema.node_id=='CR Cycle Models' and schema.display_name==row['display_name'] and schema.category==row['category']
    assert cls.SDK_REFS is True and cls.SDK_PERMISSIONS==('models',)
    assert [o.io_type for o in schema.outputs]==row['return_types'] and [o.display_name for o in schema.outputs]==row['return_names']
    flat={k:value for items in row['source_inputs'].values() for k,value in items.items()}
    assert [i.id for i in schema.inputs]==list(flat)
    for inp in schema.inputs:
        source_input=flat[inp.id]
        if isinstance(source_input[0],list):assert inp.options==source_input[0]
        else:assert inp.io_type==source_input[0]
        for k,value in (source_input[1] if len(source_input)>1 else {}).items():assert inp.as_dict()[k]==value
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

@pytest.mark.parametrize('changes',[{'model_list':[('a','one')]*257},{'loops':1001},{'model_list':[('a','one')]*256,'loops':1000},{'model_list':[('a','../host')],'current_frame':1,'frame_interval':1},{'model_list':[('a','/host/path')],'current_frame':1,'frame_interval':1}])
def test_bounds_and_logical_name_denial_before_loader(loaders,changes):
    args=args_for(**changes)
    with pytest.raises(ValueError,match='bound|logical'):
        asyncio.run(migrated(args))
    assert not loaders['calls']

def test_registered_two_actual_guests_outer_model_clip_vae_identity_and_models_denial(loaders):
    import execution
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for render in range(2):
                session=await GuestSession('ned-comfyroll-cycle-models-'+str(render),guest_runtime_root=V2).start()
                class Backend:
                    caps=('models',)
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=self.caps)
                backend=Backend();_sdk.providers.register_execution_backend(backend)
                async def execute(args):
                    cls=NEW.secure_cycle_models.CR_CycleModels;cls.GET_SCHEMA()
                    result=await execution._async_map_node_over_list(prompt_id='cycle-models',unique_id='cycler',obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                    return result[0].result
                try:
                    for mode,frame in [('Off',31),('Sequential',0),('Sequential',31),('Sequential',99)]:
                        args=args_for(mode=mode,current_frame=frame);before=len(loaders['calls']);actual=await execute(args)
                        assert len(actual)==4 and isinstance(actual[0],ModelPatcher) and isinstance(actual[1],CLIP) and type(actual[3]) is str
                        if mode=='Off' or frame==0:
                            assert actual[0] is args['model'] and actual[1] is args['clip'] and actual[2] is None
                            assert len(loaders['calls'])==before
                        else:
                            assert isinstance(actual[2],VaeDouble)
                            assert all(actual[i] is loaders['loaded'][-1][i] for i in range(3))
                    backend.caps=()
                    with pytest.raises(wire.WireError,match='models'):await execute(args_for())
                    backend.caps=('models',)
                    before=len(loaders['calls'])
                    with pytest.raises(wire.WireError,match='logical'):await execute(args_for(model_list=[('a','../host')],current_frame=1,frame_interval=1))
                    assert len(loaders['calls'])==before;pids.append(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(previous)
        assert pids[0]!=pids[1]
    asyncio.run(run())
