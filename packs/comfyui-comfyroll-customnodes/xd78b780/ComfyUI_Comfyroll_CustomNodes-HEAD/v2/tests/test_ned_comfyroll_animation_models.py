"""Exact animation tuple values and managed LoRA selection; recording application, not inference."""
import ast,asyncio,copy,importlib.util,json,os,sys,types
from pathlib import Path
import pytest,torch
sys.dont_write_bytecode=True;sys.argv=['ned-animation-models','--cpu']
CORE=Path(os.environ['COMFY_CORE_ROOT']);sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.transport import wire
import comfy.sd,comfy.utils,folder_paths
from safetensors.torch import save_file
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
spec=importlib.util.spec_from_file_location('ned_cr_animation_models',V2/'__init__.py',submodule_search_locations=[str(V2)])
NEW=importlib.util.module_from_spec(spec);sys.modules[spec.name]=NEW;spec.loader.exec_module(NEW)
LEDGER=json.loads((V2/'animation-models-draft-ledger.json').read_text())
icons=ast.literal_eval(ast.parse((PACK/'categories.py').read_text()).body[0].value)
LISTS=['CR Model List','CR LoRA List']
class ModelTrace:
    def __init__(self,trace=()):self.model_options={};self.load_device='cpu';self.trace=trace
class ClipTrace:
    def __init__(self,trace=()):self.trace=trace
    def tokenize(self,*args):raise AssertionError('Recording application is not trained inference')

def oracle(node_id,dependencies=None):
    row=LEDGER[node_id];path=PACK/'nodes'/row['source_file']
    source=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.ClassDef) and n.name==row['class'])
    ns={'icons':icons,'folder_paths':types.SimpleNamespace(get_filename_list=lambda folder:[])}
    ns.update(dependencies or {})
    exec(compile(ast.Module(body=[copy.deepcopy(source)],type_ignores=[]),str(path),'exec'),ns)
    return ns[row['class']]

def list_args(node_id,**changes):
    args={}
    for key,info in LEDGER[node_id]['source_inputs']['required'].items():
        args[key]=info[0][0] if isinstance(info[0],list) else info[1]['default']
    args.update(changes);return args

@pytest.mark.parametrize('node_id',LISTS)
@pytest.mark.parametrize('mask',range(32))
@pytest.mark.parametrize('rows',[None,[],[('keep','2.safetensors',.1,-.2),(None,'ignored',0.,0.),('None','1.safetensors',0.,0.)]])
def test_exact_alias_filter_order_sentinel_duplicate_and_text(node_id,mask,rows):
    args=list_args(node_id)
    count=5 if node_id=='CR Model List' else 3
    for i in range(1,count+1):
        args[('ckpt_name' if count==5 else 'lora_name')+str(i)]='1.safetensors' if mask&(1<<(i-1)) else 'None'
        args['alias'+str(i)]='' if i%2 else 'alias\n"literal"'
        if count==3:args['model_strength_'+str(i)]=i*.3;args['clip_strength_'+str(i)]=-i*.7
    if rows is not None:
        args['model_list' if count==5 else 'lora_list']=[tuple(row[:2]) if count==5 else row for row in rows]
    old=oracle(node_id)();expected=getattr(old,old.FUNCTION)(**args)
    actual=NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args).result
    assert actual==expected and type(actual[0]) is list and type(actual[1]) is str
    assert all(type(row) is tuple for row in actual[0])
    if rows:assert len(args['model_list' if count==5 else 'lora_list'])==3

@pytest.mark.parametrize('node_id',LISTS)
@pytest.mark.parametrize('rows',[[()],[[None]],['a'],[None],[[1,2]],[]])
def test_connected_native_malformed_and_list_row_type(node_id,rows):
    args=list_args(node_id,**{'model_list' if node_id==LISTS[0] else 'lora_list':rows})
    old=oracle(node_id)()
    try:expected=('value',getattr(old,old.FUNCTION)(**args))
    except Exception as e:expected=('error',type(e),str(e))
    try:actual=('value',NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args).result)
    except Exception as e:actual=('error',type(e),str(e))
    assert actual==expected

@pytest.mark.parametrize('node_id',list(LEDGER))
def test_exact_schema_case_catalogue_default_and_permissions(node_id):
    row=LEDGER[node_id];cls=NEW.NODE_CLASS_MAPPINGS[node_id];schema=cls.GET_SCHEMA()
    assert schema.node_id==node_id and schema.display_name==row['display_name'] and schema.category==row['category']
    assert tuple(cls.SDK_PERMISSIONS)==tuple(row['permissions']) and cls.SDK_REFS is True
    assert [o.io_type for o in schema.outputs]==row['return_types'] and [o.display_name for o in schema.outputs]==row['return_names']
    flat={k:(group,info) for group,values in row['source_inputs'].items() for k,info in values.items()}
    assert [i.id for i in schema.inputs]==list(flat)
    for inp in schema.inputs:
        group,info=flat[inp.id];assert inp.optional==(group=='optional')
        if isinstance(info[0],list):
            assert inp.options==info[0]
            if inp.id.startswith(('ckpt_name','lora_name')):assert inp.remote.route==('/secure-nodes/models/checkpoints' if inp.id.startswith('ckpt_name') else '/secure-nodes/models/loras')
        elif node_id=='CR LoRA List' and inp.id=='lora_list':
            # Approved ONE-socket source defect repair; immutable source ledger stays literal.
            assert info[0]=='lora_LIST' and inp.io_type=='LORA_LIST'
        else:assert inp.io_type==info[0]
        for k,v in (info[1] if len(info)>1 else {}).items():assert inp.as_dict()[k]==v
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

def test_real_core_source_case_incompatibility_and_approved_one_socket_repair():
    from comfy_execution.validation import validate_node_input
    row=LEDGER['CR LoRA List']
    assert row['source_inputs']['optional']['lora_list'][0]=='lora_LIST'
    assert row['return_types'][0]=='LORA_LIST'
    assert not validate_node_input('LORA_LIST','lora_LIST')
    inp=next(i for i in NEW.NODE_CLASS_MAPPINGS['CR LoRA List'].GET_SCHEMA().inputs if i.id=='lora_list')
    assert inp.optional and inp.io_type=='LORA_LIST'
    assert validate_node_input('LORA_LIST',inp.io_type)
    assert validate_node_input('LORA_LIST',LEDGER['CR Cycle LoRAs']['source_inputs']['required']['lora_list'][0])
    assert validate_node_input('MODEL_LIST',NEW.secure_cycle_models.CR_CycleModels.GET_SCHEMA().inputs[3].io_type)

@pytest.fixture
def managed(monkeypatch,tmp_path):
    root=tmp_path/'loras';root.mkdir()
    for i in (1,2,3):save_file({'marker':torch.tensor([float(i)])},str(root/(str(i)+'.safetensors')))
    paths=folder_paths.get_folder_paths;full=folder_paths.get_full_path
    monkeypatch.setattr(folder_paths,'get_folder_paths',lambda folder:[str(root)] if folder=='loras' else paths(folder))
    monkeypatch.setattr(folder_paths,'get_full_path',lambda folder,name:str(root/name) if folder=='loras' and (root/name).is_file() else full(folder,name))
    applications=[]
    def apply(model,clip,state,sm,sc,**kwargs):
        marker=float(state['marker'][0]);applications.append((marker,sm,sc))
        return ModelTrace(model.trace+((marker,sm),)),ClipTrace(clip.trace+((marker,sc),))
    monkeypatch.setattr(comfy.sd,'load_lora_for_models',apply)
    old=oracle('CR Cycle LoRAs',{'folder_paths':folder_paths,'comfy':types.SimpleNamespace(sd=comfy.sd,utils=comfy.utils)})
    return old,applications

def cycle_args(**changes):
    args=dict(mode='Sequential',model=ModelTrace(),clip=ClipTrace(),lora_list=[('A','1.safetensors',.1,-.2),('B','2.safetensors',-.3,.4),('C','3.safetensors',0.,0.)],frame_interval=30,loops=1,current_frame=31)
    args.update(changes);return args

def trace_result(result):
    return (result[0].trace,result[1].trace,result[2])

async def migrated(args):
    refs=_sdk.InProcessRefResolver();wrapped=await _sdk.wrap_inputs(refs,args)
    with _sdk.bind_runtime(refs,types.SimpleNamespace(assets=_sdk._InProcessAssets()),_sdk.InProcessOps()):
        result=await NEW.secure_animation_models.CR_CycleLoRAs.execute(**wrapped)
    out=[]
    for value in result.result:
        out.append(await refs.resolve(value) if isinstance(value,(_sdk.ModelRef,_sdk.ClipRef)) else value)
    return tuple(out)

@pytest.mark.parametrize('mode',['Off','Sequential','unknown'])
@pytest.mark.parametrize('frame',[-31,-1,0,1,29,30,31,99,0.0,1.5])
@pytest.mark.parametrize('interval',[0,1,30])
@pytest.mark.parametrize('loops',[-1,0,1,3])
def test_cycle_exact_frame_zero_floor_native_errors_and_application(managed,mode,frame,interval,loops):
    old,applications=managed;args=cycle_args(mode=mode,current_frame=frame,frame_interval=interval,loops=loops)
    try:expected=('value',trace_result(old().cycle(**args)))
    except Exception as e:expected=('error',type(e),str(e))
    expected_calls=list(applications);applications.clear()
    try:actual=('value',trace_result(asyncio.run(migrated(args))))
    except Exception as e:actual=('error',type(e),str(e))
    assert actual==expected
    assert applications==expected_calls
    assert args['model'].trace==() and args['clip'].trace==()

@pytest.mark.parametrize('mode',['Off','Sequential','unknown'])
@pytest.mark.parametrize('rows',[None,[]])
def test_cycle_empty_bypass_without_broker_and_native_rows(managed,mode,rows):
    old,applications=managed;args=cycle_args(mode=mode,lora_list=rows)
    expected=old().cycle(**args);actual=asyncio.run(migrated(args))
    assert actual[0] is args['model'] and actual[1] is args['clip'] and actual[2]==expected[2]
    assert not applications

@pytest.mark.parametrize('changes',[{'lora_list':[('x','1.safetensors',1.,1.)]*257},{'loops':1001},{'lora_list':[('x','1.safetensors',1.,1.)]*256,'loops':1000},{'lora_list':[('x','../host',1.,1.)],'frame_interval':1,'current_frame':1},{'lora_list':[('x','1.safetensors',float('nan'),1.)]}])
def test_cycle_bounds_no_load_or_application(managed,changes):
    with pytest.raises(ValueError):asyncio.run(migrated(cycle_args(**changes)))
    assert not managed[1]

def test_two_fresh_registered_guests_outer_tuples_list_to_cycle_and_asset_denial(managed):
    import execution
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for render in range(2):
                session=await GuestSession('ned-animation-models-'+str(render),guest_runtime_root=V2).start()
                class Backend:
                    caps=()
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=self.caps)
                backend=Backend();_sdk.providers.register_execution_backend(backend)
                async def execute(node_id,args):
                    cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA()
                    result=await execution._async_map_node_over_list(prompt_id='animation-models',unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                    return result[0].result
                try:
                    for node_id in LISTS:
                        args=list_args(node_id)
                        if node_id==LISTS[0]:args.update(ckpt_name1='one',alias1='One',ckpt_name5='two',alias5='Two')
                        else:args.update(lora_name1='1.safetensors',alias1='One',lora_name3='2.safetensors',alias3='Two',model_strength_1=.2,clip_strength_1=-.3)
                        output=await execute(node_id,args)
                        assert output==NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args).result
                        assert all(type(row) is tuple for row in output[0])
                        if node_id==LISTS[1]:loras=output[0]
                    backend.caps=('assets',)
                    for frame in (0,1,30,31,60,99):
                        args=cycle_args(current_frame=frame,lora_list=loras);expected=managed[0]().cycle(**args)
                        actual=await execute('CR Cycle LoRAs',args)
                        assert trace_result(actual)==trace_result(expected) and type(actual[2]) is str
                        assert args['model'].trace==() and args['clip'].trace==()
                    backend.caps=()
                    for mode,rows in [('Off',loras),('Sequential',[])]:
                        args=cycle_args(mode=mode,lora_list=rows);actual=await execute('CR Cycle LoRAs',args)
                        assert actual[0] is args['model'] and actual[1] is args['clip']
                    with pytest.raises(wire.WireError,match='assets'):await execute('CR Cycle LoRAs',cycle_args())
                    backend.caps=('assets',);before=len(managed[1])
                    with pytest.raises(wire.WireError,match='logical'):await execute('CR Cycle LoRAs',cycle_args(lora_list=[('bad','../host',1.,1.)]))
                    assert len(managed[1])==before;pids.append(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(previous)
        assert pids[0]!=pids[1]
    asyncio.run(run())
