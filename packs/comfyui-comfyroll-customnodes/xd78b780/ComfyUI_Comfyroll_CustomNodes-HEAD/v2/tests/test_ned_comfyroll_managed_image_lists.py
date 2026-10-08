"""Pristine PIL pixel oracle vs confined managed bytes; no cloud/catalogue migration proof."""
import ast,asyncio,copy,os,re,types
from io import BytesIO
import numpy as np
import pytest,torch
from PIL import Image,ImageSequence
from test_ned_comfyroll_cycle_models import NEW,V2,PACK,_sdk,GuestSession,wire
import folder_paths
IDS=['CR Load Image List','CR Load Image List Plus','CR Load GIF As List']
tree=ast.parse((PACK/'nodes/nodes_list.py').read_text());icons=ast.literal_eval(ast.parse((PACK/'categories.py').read_text()).body[0].value)
source_nodes=[copy.deepcopy(n) for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in ('CR_LoadImageList','CR_LoadImageListPlus','CR_LoadGIFAsList','tensor2rgba','pil2tensor')]
def oracle(root):
    ns={'torch':torch,'np':np,'os':os,'re':re,'Image':Image,'ImageSequence':ImageSequence,'icons':icons,'folder_paths':types.SimpleNamespace(input_directory=str(root))}
    exec(compile(ast.Module(body=copy.deepcopy(source_nodes),type_ignores=[]),str(PACK/'nodes/nodes_list.py'),'exec'),ns);return ns
@pytest.fixture(params=['RGB','RGBA','L','P'])
def media(request,tmp_path,monkeypatch):
    root=tmp_path/'input';album=root/'album';album.mkdir(parents=True)
    for number in (10,2,1):
        values=(np.arange(9*6*3,dtype=np.uint8).reshape(6,9,3)+number*10)
        image=Image.fromarray(values)
        if request.param=='RGBA':
            image=image.convert('RGBA');image.putalpha(Image.fromarray(np.full((6,9),17*number,dtype=np.uint8)))
        elif request.param!='RGB':image=image.convert(request.param)
        exif=Image.Exif();exif[274]=6
        image.save(album/f'a{number}.png',exif=exif)
    frames=[Image.fromarray(np.full((6,9,3),[31+i*50,50+i*20,181-i*30],dtype=np.uint8)) for i in range(3)]
    frames[0].save(album/'z.gif',save_all=True,append_images=frames[1:],duration=[20,40,80],loop=0,disposal=2)
    monkeypatch.setattr(folder_paths,'get_input_directory',lambda:str(root))
    return root,oracle(root),request.param
def args(id,**changes):
    a=dict(input_folder='album',input_path=None)
    if id==IDS[2]:a.update(gif_filename='z.gif',start_frame=0,max_frames=3)
    else:a.update(start_index=0,max_images=3)
    a.update(changes);return a
def native(media,id,a):
    c=media[1][NEW.NODE_CLASS_MAPPINGS[id].__name__]();return getattr(c,c.FUNCTION)(**a)
async def migrated(id,a,assets=None):
    refs=_sdk.InProcessRefResolver()
    with _sdk.bind_runtime(refs,types.SimpleNamespace(assets=assets or _sdk._InProcessAssets()),_sdk.InProcessOps()):r=await NEW.NODE_CLASS_MAPPINGS[id].execute(**a)
    return r.result if hasattr(r,'result') else r
def same(a,b):
    if torch.is_tensor(b):assert torch.is_tensor(a) and a.dtype==b.dtype and a.shape==b.shape and torch.equal(a,b)
    elif isinstance(b,(list,tuple)):
        assert type(a)==type(b) and len(a)==len(b)
        for x,y in zip(a,b):same(x,y)
    else:assert a==b and type(a)==type(b)
def repaired(id,out):return out[:4]+out[5:] if id==IDS[1] and out else out
@pytest.mark.parametrize('id',IDS[:2])
@pytest.mark.parametrize('start',[-9,0,1,2,3,99])
@pytest.mark.parametrize('count',[-1,0,1,2,99])
def test_exact_natural_order_last_exclusion_exif_red_masks_and_native_empty(media,id,start,count):
    a=args(id,start_index=start,max_images=count);expected=native(media,id,a);actual=asyncio.run(migrated(id,a))
    if id==IDS[1] and expected:assert len(expected)==9 and expected[2]==expected[4]
    same(actual,repaired(id,expected))
    if actual:
        assert actual[0][0].shape[1:3]==(6,9) # EXIF6 was not rotated/transposed.
        if id==IDS[1]:assert actual[3][-1]!='z.gif' and len(actual)==8
@pytest.mark.parametrize('start',[-1,0,1,2,3,99])
@pytest.mark.parametrize('count',[-1,0,1,2,99,None])
def test_gif_exact_palette_first_frame_red_masks_frame_order_and_error_fallback(media,start,count):
    id=IDS[2];a=args(id,start_frame=start,max_frames=count);same(asyncio.run(migrated(id,a)),native(media,id,a))
@pytest.mark.parametrize('id',IDS)
def test_logical_prefix_override_matches_pinned_file_selection(media,id):
    original=args(id,input_folder='ignored',input_path=str(media[0]/'album'))
    logical=args(id,input_folder='ignored',input_path='album')
    same(asyncio.run(migrated(id,logical)),repaired(id,native(media,id,original)))
@pytest.mark.parametrize('id',IDS)
def test_schema_list_axes_and_exact_defaults(media,id):
    old=media[1][NEW.NODE_CLASS_MAPPINGS[id].__name__];source=old.INPUT_TYPES();c=NEW.NODE_CLASS_MAPPINGS[id];s=c.GET_SCHEMA()
    assert s.node_id==id and s.display_name=='⌨️ '+id and s.category==old.CATEGORY
    assert c.SDK_REFS is False and c.SDK_PERMISSIONS==('assets','raw')
    flat={k:(group,info) for group,values in source.items() for k,info in values.items()}
    assert [i.id for i in s.inputs]==list(flat)
    for i in s.inputs:
        group,info=flat[i.id];assert i.optional==(group=='optional')
        if i.id=='input_folder':assert i.remote.route=='/secure-nodes/assets/input?kind=directory' and i.options==[]
        else:
            assert i.io_type==info[0]
            for k,v in (info[1] if len(info)>1 else {}).items():assert i.as_dict()[k]==v
    assert [o.io_type for o in s.outputs]==list(old.RETURN_TYPES)
    assert [o.display_name for o in s.outputs]==list(old.RETURN_NAMES)
    assert [o.is_output_list for o in s.outputs]==list(old.OUTPUT_IS_LIST)
def test_catalogue_choices_are_nested_but_execution_is_strictly_immediate(media):
    root,_,_=media;(root/'album'/'nested').mkdir();Image.new('RGB',(9,6),'red').save(root/'album'/'nested'/'hidden.png')
    async def run():
        refs=_sdk.InProcessRefResolver()
        with _sdk.bind_runtime(refs,types.SimpleNamespace(assets=_sdk._InProcessAssets()),_sdk.InProcessOps()):names=await NEW.secure_managed_image_lists._files('album')
        assert names==['a1.png','a2.png','a10.png','z.gif']
    asyncio.run(run())
    # Native directory names participate in os.listdir and may fail Image.open;
    # managed file catalogue intentionally excludes directories, no recursion.
    assert 'nested' in os.listdir(root/'album')
@pytest.mark.parametrize('id',IDS)
@pytest.mark.parametrize('path',['/host','../host','album/../host','C:\\host','album\\nested','a//b','a/','a\x00b'])
def test_paths_rejected_before_any_broker_operation(id,path):
    class Deny:
        def __getattr__(self,key):raise AssertionError('No broker call before logical-name rejection')
    with pytest.raises(ValueError,match='logical'):
        asyncio.run(migrated(id,args(id,input_path=path),Deny()))
def test_bounds_size_shape_selected_rows_and_decoder_failure(media):
    root,_,_=media;module=NEW.secure_managed_image_lists
    Image.new('RGB',(4097,1),'red').save(root/'album'/'huge.png')
    with pytest.raises(module.WorkloadError,match='shape'):asyncio.run(migrated(IDS[0],args(IDS[0],start_index=3,max_images=1)))
    with pytest.raises(module.WorkloadError,match='shape'):asyncio.run(migrated(IDS[2],args(IDS[2],gif_filename='huge.png')))
    for i in range(70):Image.new('RGB',(2,2)).save(root/'album'/f'b{i}.png')
    with pytest.raises(module.WorkloadError,match='count'):asyncio.run(migrated(IDS[0],args(IDS[0],max_images=70)))
    (root/'album'/'bad.png').write_bytes(b'not an image')
    same(asyncio.run(migrated(IDS[2],args(IDS[2],gif_filename='bad.png'))),native(media,IDS[2],args(IDS[2],gif_filename='bad.png')))
    class Large:
        async def resolve(self,*a):return object()
        async def size(self,*a):return 8*1024*1024+1
        async def read_bytes(self,*a):raise AssertionError('No oversized read')
        async def exists(self,*a):return True
    with pytest.raises(module.WorkloadError,match='Encoded'):asyncio.run(migrated(IDS[2],args(IDS[2]),Large()))
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))
def test_missing_prefix_explicit_managed_disposition_not_os_exists_parity(media):
    native_result=native(media,IDS[0],args(IDS[0],input_path=str(media[0]/'not-present')))
    assert native_result==('',) and asyncio.run(migrated(IDS[0],args(IDS[0],input_path='not-present'))) is None
    # Logical prefixes do not expose OS directory existence; no source parity claim.
@pytest.mark.parametrize('id',IDS[:2])
@pytest.mark.parametrize('case',['corrupt','mixed-shape','float-index','one-file'])
def test_native_decoder_concat_index_and_single_lastfile_dispositions(media,id,case):
    root=media[0];folder=root/'probe';folder.mkdir();a=args(id,input_folder='probe')
    if case=='corrupt':
        (folder/'a1.png').write_bytes(b'not PNG');Image.new('RGB',(9,6)).save(folder/'z.png')
    elif case=='mixed-shape':
        Image.new('RGB',(9,6)).save(folder/'a1.png');Image.new('RGB',(8,6)).save(folder/'a2.png');Image.new('RGB',(9,6)).save(folder/'z.png')
    else:
        Image.new('RGB',(9,6)).save(folder/'a1.png')
        if case=='float-index':
            Image.new('RGB',(9,6)).save(folder/'a2.png');Image.new('RGB',(9,6)).save(folder/'z.png');a['start_index']=.5
    try:expected=('value',native(media,id,a))
    except Exception as exc:expected=('error',type(exc))
    try:actual=('value',asyncio.run(migrated(id,a)))
    except Exception as exc:actual=('error',type(exc))
    assert actual[0]==expected[0]
    if expected[0]=='error':assert actual[1] is expected[1]
    else:same(actual[1],repaired(id,expected[1]))
def test_selected_gif_allocation_and_scan_workload_limits_are_not_swallowed(media):
    root=media[0];frames=[Image.new('RGB',(2,2),(i,255-i,i//2)) for i in range(67)]
    frames[0].save(root/'album'/'long.gif',save_all=True,append_images=frames[1:],duration=10)
    a=args(IDS[2],gif_filename='long.gif',max_frames=65)
    assert len(native(media,IDS[2],a)[0])==65
    with pytest.raises(NEW.secure_managed_image_lists.WorkloadError,match='count'):
        asyncio.run(migrated(IDS[2],a))
def test_forged_catalogue_and_changed_byte_count_fail_closed():
    module=NEW.secure_managed_image_lists
    class Forged:
        async def list(self,*a,**k):return ['album/nested/unexpected.png']
    class Changed:
        async def exists(self,*a):return True
        async def resolve(self,*a):return object()
        async def size(self,*a):return 1
        async def read_bytes(self,*a):return b'two'
    with pytest.raises(ValueError,match='non-immediate'):asyncio.run(migrated(IDS[0],args(IDS[0]),Forged()))
    with pytest.raises(ValueError,match='changed'):asyncio.run(migrated(IDS[2],args(IDS[2]),Changed()))
def test_two_fresh_raw_guests_outer_list_axes_asset_raw_denial_and_production(media,monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        async def execute(id,a):
            cls=NEW.NODE_CLASS_MAPPINGS[id];cls.GET_SCHEMA()
            r=await execution._async_map_node_over_list(prompt_id='managed-list',unique_id='images',obj=cls,input_data_all={k:[v] for k,v in a.items()},func=cls.FUNCTION,v3_data=None)
            r=await execution.resolve_map_node_over_list_results(r);return r[0].result
        try:
            for render in range(2):
                session=await GuestSession('ned-managed-lists-'+str(render),guest_runtime_root=V2).start();caps={'value':('assets','raw')}
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=caps['value'])
                _sdk.providers.register_execution_backend(Backend())
                try:
                    for id in IDS:
                        a=args(id);same(await execute(id,a),repaired(id,native(media,id,a)))
                    # Each authority separately denied on genuine nonempty paths.
                    for granted in [('raw',),('assets',)]:
                        caps['value']=granted
                        for id in IDS:
                            with pytest.raises(wire.WireError,match='assets|raw|capability|permission'):await execute(id,args(id))
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
            assert len(set(pids))==2 and os.getpid() not in pids
            session=await GuestSession('ned-managed-lists-production',guest_runtime_root=V2).start();backend=CloudExecutionBackend()
            monkeypatch.setattr(backend,'_is_sandbox',lambda plan:True)
            async def session_for(*a,**k):return session
            monkeypatch.setattr(backend.guests,'session_for',session_for);_sdk.providers.register_execution_backend(backend)
            try:
                for id in IDS:same(await execute(id,args(id)),repaired(id,native(media,id,args(id))))
            finally:await session.kill();await backend.shutdown()
        finally:_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
