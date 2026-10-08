"""Source preview pixels/order versus managed scoped PNG transport, not browser/deployment."""
import ast,asyncio,copy,importlib.util,json,os,sys,types
from pathlib import Path
import numpy as np,pytest,torch
from PIL import Image,ImageOps
sys.dont_write_bytecode=True;sys.argv=['ned-template-previews','--cpu']
CORE=Path(os.environ['COMFY_CORE_ROOT']);sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.transport import wire
import folder_paths
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
spec=importlib.util.spec_from_file_location('ned_cr_template_previews',V2/'__init__.py',submodule_search_locations=[str(V2)])
NEW=importlib.util.module_from_spec(spec);sys.modules[spec.name]=NEW;spec.loader.exec_module(NEW)
LEDGER=json.loads((V2/'template-previews-draft-ledger.json').read_text())
def pixels(dtype=torch.float32,batch=3,height=13,width=17,channels=3):
    x=torch.linspace(-.1,1.1,max(1,batch*height*width*channels))
    return x[:batch*height*width*channels].reshape(batch,height,width,channels).to(dtype)
def args_for(node_id,**changes):
    args={k:(v[0][0] if isinstance(v[0],list) else v[1]['default']) for k,v in LEDGER[node_id]['source_inputs']['required'].items() if k!='image'}
    args['image']=pixels(batch=3 if node_id=='CR Thumbnail Preview' else 1);args.update(changes);return args
def source(node_id,args):
    path=PACK/'nodes/nodes_graphics_template.py'
    selected=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.ClassDef) and n.name==LEDGER[node_id]['class'])
    helper_path=PACK/'nodes/functions_graphics.py'
    helper_names={'tensor2pil','pil2tensor','make_grid_panel'}
    helpers=[copy.deepcopy(n) for n in ast.parse(helper_path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in helper_names]
    up=next(n for n in ast.parse((PACK/'nodes/functions_upscale.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='apply_resize_image')
    calls=[]
    server=types.SimpleNamespace(client_id='controlled-source-client')
    server.send_sync=lambda kind,data,audience:calls.append((kind,data,audience))
    ns={'torch':torch,'np':np,'Image':Image,'ImageOps':ImageOps,'PromptServer':types.SimpleNamespace(instance=server),'BinaryEventTypes':types.SimpleNamespace(UNENCODED_PREVIEW_IMAGE=42),'icons':{}}
    exec(compile(ast.Module(body=helpers+[copy.deepcopy(up),copy.deepcopy(selected)],type_ignores=[]),str(path),'exec'),ns)
    old=ns[LEDGER[node_id]['class']]();result=getattr(old,old.FUNCTION)(**args)
    assert all(kind==42 and data[0]=='PNG' and data[2] is None and audience=='controlled-source-client' for kind,data,audience in calls)
    return result,[np.array(data[1]).copy() for kind,data,audience in calls]

async def migrated(node_id,args):
    refs=_sdk.InProcessRefResolver();captured=[]
    class UI:
        async def preview_images(self,images,animated=False):
            assert isinstance(images,_sdk.ImageRef) and images.kind=='IMAGE'
            value=await refs.resolve(images)
            captured.extend(np.clip(255*x.cpu().numpy(),0,255).astype(np.uint8) for x in value)
            return {'images':[{'filename':'controlled.png','subfolder':'','type':'temp'} for _ in value],'animated':(False,)}
    with _sdk.bind_runtime(refs,types.SimpleNamespace(ui=UI()),_sdk.InProcessOps()):
        result=await NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args)
    return result,captured

def compare(node_id,args):
    try:expected=('value',source(node_id,args))
    except Exception as e:expected=('error',type(e),str(e))
    try:actual=('value',asyncio.run(migrated(node_id,args)))
    except Exception as e:actual=('error',type(e),str(e))
    assert actual[0]==expected[0]
    if expected[0]=='error':assert actual[1:]==expected[1:]
    else:
        old,images=expected[1];result,captured=actual[1]
        assert result.result==old['result'] and len(captured)==len(images)==1
        assert type(result.result[0]) is str
        assert all(np.array_equal(a,b) and a.shape==b.shape for a,b in zip(captured,images))
        assert result.ui['images'][0]['type']=='temp' and 'source' not in result.ui['images'][0]

@pytest.mark.parametrize('batch',[1,2,3,5,8])
@pytest.mark.parametrize('columns',[1,2,3,5,8])
@pytest.mark.parametrize('factor',[.1,.25,1.,1.3])
def test_thumbnail_exact_grid_batch_order_partial_rows_border_and_lanczos(batch,columns,factor):
    compare('CR Thumbnail Preview',args_for('CR Thumbnail Preview',image=pixels(batch=batch,height=23,width=31),max_columns=columns,rescale_factor=factor))

@pytest.mark.parametrize('option',['2x2','3x3','4x4','5x5','6x6'])
@pytest.mark.parametrize('factor',[.1,.25,1.,1.3])
def test_seamless_exact_repeat_order_geometry_and_lanczos(option,factor):
    compare('CR Seamless Checker',args_for('CR Seamless Checker',grid_options=option,rescale_factor=factor,image=pixels(batch=1,height=23,width=31)))

@pytest.mark.parametrize('node_id',list(LEDGER))
@pytest.mark.parametrize('dtype',[torch.float32,torch.float16,torch.bfloat16,torch.float64,torch.uint8])
@pytest.mark.parametrize('channels',[1,3,4])
def test_dtype_channels_source_squeeze_and_native_bf16_error(node_id,dtype,channels):
    compare(node_id,args_for(node_id,image=pixels(dtype,batch=1,channels=channels)))

@pytest.mark.parametrize('node_id',list(LEDGER))
@pytest.mark.parametrize('changes',[{'image':pixels(batch=0)},{'image':pixels(height=1,batch=1)},{'image':pixels(width=1,batch=1)},{'rescale_factor':0.},{'rescale_factor':-1.}])
def test_native_small_empty_zero_negative_and_singleton_errors(node_id,changes):
    compare(node_id,args_for(node_id,**changes))

@pytest.mark.parametrize('columns',[0,-1,-3])
def test_native_thumbnail_bad_columns(columns):
    compare('CR Thumbnail Preview',args_for('CR Thumbnail Preview',max_columns=columns))

@pytest.mark.parametrize('option',['','no','0x0','1x1','9x9'])
def test_seamless_native_direct_options(option):
    compare('CR Seamless Checker',args_for('CR Seamless Checker',grid_options=option))

@pytest.mark.parametrize('node_id',list(LEDGER))
def test_schema_output_flag_permissions_and_json_workflow_state(node_id):
    row=LEDGER[node_id];cls=NEW.NODE_CLASS_MAPPINGS[node_id];schema=cls.GET_SCHEMA()
    assert schema.node_id==node_id and schema.display_name==row['display_name'] and schema.category==row['category'] and schema.is_output_node
    assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS==('raw','ui')
    assert [o.io_type for o in schema.outputs]==row['return_types'] and [o.display_name for o in schema.outputs]==row['return_names']
    flat=row['source_inputs']['required'];assert [i.id for i in schema.inputs]==list(flat)
    for inp in schema.inputs:
        info=flat[inp.id]
        if isinstance(info[0],list):assert inp.options==info[0]
        else:assert inp.io_type==info[0]
        for k,v in (info[1] if len(info)>1 else {}).items():assert inp.as_dict()[k]==v
    args=args_for(node_id);img=args.pop('image');restored=json.loads(json.dumps(args));restored['image']=img
    compare(node_id,restored)
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

@pytest.mark.parametrize('node_id',list(LEDGER))
@pytest.mark.parametrize('changes',[{'image':torch.empty(1,4096,4096,3,device='meta')},{'rescale_factor':5.},{'rescale_factor':float('inf')},{'image':torch.empty(16,1024,1024,3,device='meta')}])
def test_bounds_before_resize_or_ui(node_id,changes,monkeypatch):
    calls=[];monkeypatch.setattr(NEW.secure_template_previews,'tensor2pil',lambda *a,**k:calls.append((a,k)))
    with pytest.raises(ValueError,match='bound|finite'):asyncio.run(migrated(node_id,args_for(node_id,**changes)))
    assert not calls

def test_two_actual_fresh_guests_managed_png_outer_help_and_both_capability_denials(tmp_path,monkeypatch):
    import execution
    temp=tmp_path/'previews';temp.mkdir();monkeypatch.setattr(folder_paths,'get_temp_directory',lambda:str(temp))
    def read_ui(result,expected):
        assert result.result==expected[0]['result'] and type(result.result[0]) is str
        entries=result.ui['images'];assert len(entries)==len(expected[1])==1
        for row,pixels in zip(entries,expected[1]):
            assert row['type']=='temp' and not row['subfolder'] and '/' not in row['filename'] and '\\' not in row['filename']
            path=(temp/row['filename']).resolve();assert path.is_relative_to(temp.resolve())
            assert np.array_equal(np.array(Image.open(path)),pixels)
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for render in range(2):
                session=await GuestSession('ned-template-preview-'+str(render),guest_runtime_root=V2).start()
                class Backend:
                    caps=('raw','ui')
                    async def dispatch(self,plan,local_call,runtime):
                        assert plan.input_mode=='values'
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=self.caps)
                backend=Backend();_sdk.providers.register_execution_backend(backend)
                async def execute(node_id,args):
                    cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA()
                    r=await execution._async_map_node_over_list(prompt_id='template-preview',unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                    return r[0]
                try:
                    for node_id in LEDGER:
                        for factor in (.25,1.):
                            args=args_for(node_id,rescale_factor=factor);read_ui(await execute(node_id,args),source(node_id,args))
                        args=args_for(node_id)
                        for caps,denied in [(('raw',),'ui'),(('ui',),'raw'),((),'raw')]:
                            before={p.name for p in temp.iterdir()};backend.caps=caps
                            with pytest.raises(wire.WireError,match=denied):await execute(node_id,args)
                            assert {p.name for p in temp.iterdir()}==before
                        backend.caps=('raw','ui')
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(previous)
        assert pids[0]!=pids[1]
    asyncio.run(run())

def test_real_production_dispatch_both_previews(tmp_path,monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    temp=tmp_path/'production';temp.mkdir();monkeypatch.setattr(folder_paths,'get_temp_directory',lambda:str(temp))
    async def run():
        previous=_sdk.providers.execution_backend;session=await GuestSession('ned-template-preview-production',guest_runtime_root=V2).start();backend=CloudExecutionBackend()
        monkeypatch.setattr(backend,'_is_sandbox',lambda plan:True)
        async def session_for(*a,**k):return session
        monkeypatch.setattr(backend.guests,'session_for',session_for);_sdk.providers.register_execution_backend(backend)
        try:
            for node_id in LEDGER:
                cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA();args=args_for(node_id)
                r=await execution._async_map_node_over_list(prompt_id='preview-production',unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                r=await execution.resolve_map_node_over_list_results(r);assert r[0].result==source(node_id,args)[0]['result']
                row=r[0].ui['images'][0];assert row['type']=='temp' and (temp/row['filename']).is_file()
                assert np.array_equal(np.array(Image.open(temp/row['filename'])),source(node_id,args)[1][0])
            assert session.last_guest_pid not in (None,os.getpid())
        finally:await session.kill();await backend.shutdown();_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())

