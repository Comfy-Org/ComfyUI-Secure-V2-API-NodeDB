"""Approved HalftoneFilter unpack repair; unchanged helper pixels, actual raw guest and bounds."""
import ast,asyncio,copy,importlib.util,json,os,sys
from pathlib import Path
import numpy as np,pytest,torch
from PIL import Image,ImageDraw,ImageStat
sys.dont_write_bytecode=True;sys.argv=['ned-halftone','--cpu']
CORE=Path(os.environ['COMFY_CORE_ROOT']);sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.transport import wire
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
spec=importlib.util.spec_from_file_location('ned_cr_halftone',V2/'__init__.py',submodule_search_locations=[str(V2)])
NEW=importlib.util.module_from_spec(spec);sys.modules[spec.name]=NEW;spec.loader.exec_module(NEW)
LEDGER=json.loads((V2/'halftone-draft-ledger.json').read_text())['CR Halftone Filter']
path=PACK/'nodes/nodes_graphics_filter.py'
node=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.ClassDef) and n.name=='CR_HalftoneFilter')
def source(corrected):
    cls=copy.deepcopy(node)
    if corrected:
        fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='halftone_effect')
        matches=0
        for n in ast.walk(fn):
            if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='halftone_images' for t in n.targets):
                n.targets=[ast.Tuple(elts=[ast.Name(id='halftone_images',ctx=ast.Store()),ast.Name(id='show_help',ctx=ast.Store())],ctx=ast.Store())];matches+=1
        assert matches==1
    ns={'torch':torch,'np':np,'Image':Image,'ImageDraw':ImageDraw,'ImageStat':ImageStat,'icons':{}}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[])),str(path),'exec'),ns)
    return ns['CR_HalftoneFilter']()

def image(dtype=torch.float32,channels=3,batch=1,height=9,width=11):
    x=torch.linspace(-.2,1.2,max(1,batch*height*width*channels))
    return x[:batch*height*width*channels].reshape(batch,height,width,channels).to(dtype)

def args_for(**changes):
    args={k:(v[0][0] if isinstance(v[0],list) else v[1]['default']) for k,v in LEDGER['source_inputs']['required'].items() if k!='image'}
    args['image']=image();args.update(changes);return args
def exact(actual,expected):
    assert len(actual)==len(expected)==2 and actual[1]==expected[1] and type(actual[1]) is str
    assert actual[0].dtype==expected[0].dtype==torch.float32
    assert actual[0].shape==expected[0].shape and torch.equal(actual[0],expected[0])
def old(args):return source(True).halftone_effect(**args)
def compare_native(args):
    try:expected=('value',old(args))
    except Exception as e:expected=('error',type(e),str(e))
    try:actual=('value',NEW.secure_halftone.CR_HalftoneFilter.execute(**args).result)
    except Exception as e:actual=('error',type(e),str(e))
    assert expected[0]==actual[0]
    if expected[0]=='value':exact(actual[1],expected[1])
    else:assert actual[1:]==expected[1:]

@pytest.mark.parametrize('gray',[True,False])
def test_original_tuple_helper_native_defects_retained(gray):
    args=args_for(greyscale=gray)
    with pytest.raises(AttributeError if gray else ValueError,match='convert|bands'):source(False).halftone_effect(**args)
    pil=Image.new('L',(9,11));result=source(False)._halftone_pil(pil,[pil],3,1,[0],True,False,2,'ellipse')
    assert type(result) is tuple and type(result[0]) is list and type(result[1]) is str
    exact(NEW.secure_halftone.CR_HalftoneFilter.execute(**args).result,old(args))

@pytest.mark.parametrize('gray',[True,False])
@pytest.mark.parametrize('shape',['ellipse','rectangle'])
@pytest.mark.parametrize('resolution',['normal','hi-res (2x output size)','unknown'])
@pytest.mark.parametrize('aa,scale',[(False,4),(True,1),(True,2),(True,3),(True,4)])
@pytest.mark.parametrize('border',[False,True])
def test_exact_corrected_composition_all_pinned_modes_rotations_border_and_lanczos(gray,shape,resolution,aa,scale,border):
    args=args_for(greyscale=gray,dot_shape=shape,resolution=resolution,antialias=aa,antialias_scale=scale,border_blending=border,angle_k=31,dot_size=3)
    exact(NEW.secure_halftone.CR_HalftoneFilter.execute(**args).result,old(args))

@pytest.mark.parametrize('dtype',[torch.float32,torch.float16,torch.bfloat16,torch.float64,torch.uint8])
@pytest.mark.parametrize('channels',[1,2,3,4])
def test_native_dtype_byte_conversion_and_channels_not_normalized(dtype,channels):
    compare_native(args_for(image=image(dtype,channels)))

@pytest.mark.parametrize('changes',[{'dot_size':0},{'dot_size':-1},{'antialias_scale':0},{'antialias_scale':-1},{'dot_shape':'unknown'},{'dot_shape':'polygon'},{'image':image(batch=0)},{'image':image(batch=2)},{'image':image(height=0)},{'image':image(width=0)},{'image':image(height=1)},{'image':image(width=1)}])
def test_native_small_malformed_zero_negative_and_empty_boundaries(changes):
    compare_native(args_for(**changes))

def test_schema_defaults_order_and_raw_only():
    cls=NEW.secure_halftone.CR_HalftoneFilter;schema=cls.GET_SCHEMA()
    assert schema.node_id=='CR Halftone Filter' and schema.display_name==LEDGER['display_name'] and schema.category==LEDGER['category']
    assert [o.io_type for o in schema.outputs]==LEDGER['return_types'] and [o.display_name for o in schema.outputs]==LEDGER['return_names']
    assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS==('raw',)
    flat=LEDGER['source_inputs']['required'];assert [i.id for i in schema.inputs]==list(flat)
    for inp in schema.inputs:
        info=flat[inp.id]
        if isinstance(info[0],list):assert inp.options==info[0]
        else:assert inp.io_type==info[0]
        for k,v in (info[1] if len(info)>1 else {}).items():assert inp.as_dict()[k]==v
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

@pytest.mark.parametrize('changes',[{'image':torch.empty(1,4096,4096,3,device='meta')},{'image':torch.empty(1,1500,1500,3,device='meta'),'dot_size':1,'greyscale':False,'antialias':False},{'image':torch.empty(1,512,512,3,device='meta'),'antialias_scale':4,'resolution':'hi-res (2x output size)'},{'dot_size':129},{'antialias_scale':5},{'angle_c':float('nan')},{'angle_k':36001},{'dot_shape':'x'*129}])
def test_bounds_before_any_pil_or_cpu_tensor_materialization(changes,monkeypatch):
    calls=[]
    monkeypatch.setattr(NEW.secure_halftone.CR_HalftoneFilter,'tensor_to_pil',lambda *a,**k:calls.append((a,k)))
    with pytest.raises(ValueError,match='bound|finite'):NEW.secure_halftone.CR_HalftoneFilter.execute(**args_for(**changes))
    assert not calls

def test_two_fresh_actual_raw_guests_default_output_outer_and_denial():
    import execution
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for render in range(2):
                session=await GuestSession('ned-halftone-'+str(render),guest_runtime_root=V2).start()
                class Backend:
                    caps=('raw',)
                    async def dispatch(self,plan,local_call,runtime):
                        assert plan.input_mode=='values'
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=self.caps)
                backend=Backend();_sdk.providers.register_execution_backend(backend)
                async def execute(args):
                    cls=NEW.secure_halftone.CR_HalftoneFilter;cls.GET_SCHEMA()
                    r=await execution._async_map_node_over_list(prompt_id='halftone',unique_id='halftone',obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                    return r[0].result
                try:
                    for args in (args_for(),args_for(greyscale=False,resolution='hi-res (2x output size)',border_blending=True),args_for(image=image(torch.bfloat16)),args_for(image=image(height=512,width=512))):
                        result=await execute(args);exact(result,old(args))
                    backend.caps=()
                    with pytest.raises(wire.WireError,match='raw'):await execute(args_for())
                    backend.caps=('raw',)
                    with pytest.raises(wire.WireError,match='bound'):await execute(args_for(image=torch.zeros(1,512,512,3),antialias_scale=4,resolution='hi-res (2x output size)'))
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(previous)
        assert pids[0]!=pids[1]
    asyncio.run(run())

def test_actual_production_dispatch_corrected_halftone(monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        previous=_sdk.providers.execution_backend;session=await GuestSession('ned-halftone-production',guest_runtime_root=V2).start();backend=CloudExecutionBackend()
        monkeypatch.setattr(backend,'_is_sandbox',lambda plan:True)
        async def session_for(*a,**k):return session
        monkeypatch.setattr(backend.guests,'session_for',session_for);_sdk.providers.register_execution_backend(backend)
        try:
            cls=NEW.secure_halftone.CR_HalftoneFilter;cls.GET_SCHEMA();args=args_for(greyscale=False,border_blending=True)
            result=await execution._async_map_node_over_list(prompt_id='production-halftone',unique_id='filter',obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
            result=await execution.resolve_map_node_over_list_results(result);exact(result[0].result,old(args))
            assert session.last_guest_pid not in (None,os.getpid())
        finally:await session.kill();await backend.shutdown();_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())

