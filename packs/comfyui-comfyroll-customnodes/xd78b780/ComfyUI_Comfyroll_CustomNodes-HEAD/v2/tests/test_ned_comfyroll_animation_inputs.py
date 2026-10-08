"""Exact bounded frame/index/pixels via managed bytes; no filesystem/cloud migration proof."""
import ast,asyncio,copy,glob,hashlib,json,os,re,types
import numpy as np
import pytest,torch
from PIL import Image
from test_ned_comfyroll_cycle_models import NEW,V2,PACK,_sdk,GuestSession,wire
import folder_paths
IDS=['CR Load Animation Frames','CR Load Flow Frames']
LEDGER=json.loads((V2/'animation-inputs-draft-ledger.json').read_text())
TREE=ast.parse((PACK/'nodes/nodes_animation_io.py').read_text())
ICONS=ast.literal_eval(ast.parse((PACK/'categories.py').read_text()).body[0].value)
def oracle(root):
    ns={'os':os,'re':re,'glob':glob,'np':np,'torch':torch,'Image':Image,'icons':ICONS,'folder_paths':types.SimpleNamespace(input_directory=str(root))}
    body=[copy.deepcopy(n) for n in TREE.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in ('resolve_pattern','get_files','CR_LoadAnimationFrames','CR_LoadFlowFrames')]
    exec(compile(ast.Module(body=body,type_ignores=[]),str(PACK/'nodes/nodes_animation_io.py'),'exec'),ns);return ns
@pytest.fixture(params=['RGB','RGBA'])
def frames(request,tmp_path,monkeypatch):
    root=tmp_path/'input';album=root/'frames';album.mkdir(parents=True)
    for number in (10,2,1):
        pixels=(np.arange(6*9*3,dtype=np.uint8).reshape(6,9,3)+number*20)
        im=Image.fromarray(pixels)
        if request.param=='RGBA':im=im.convert('RGBA');im.putalpha(31*number%256)
        exif=Image.Exif();exif[274]=6;im.save(album/f'frame{number}.png',exif=exif)
    Image.new('RGB',(9,6),'red').save(album/'.hidden.png')
    (album/'z-not-image.txt').write_text('literal non-image source error',encoding='utf8')
    monkeypatch.setattr(folder_paths,'get_input_directory',lambda:str(root))
    return root,oracle(root)
def args(id,**changes):
    if id==IDS[0]:a=dict(image_sequence_folder='frames',start_index=1,max_frames=3)
    else:a=dict(file_pattern='frame*.png',skip_start_frames=0,input_folder='frames',sort_by='Index',current_frame=0,input_path='')
    a.update(changes);return a
def native(frames,id,a):
    c=frames[1][LEDGER[id]['class']]();return getattr(c,c.FUNCTION)(**a)
async def migrated(id,a,assets=None):
    refs=_sdk.InProcessRefResolver()
    with _sdk.bind_runtime(refs,types.SimpleNamespace(assets=assets or _sdk._InProcessAssets()),_sdk.InProcessOps()):r=await NEW.NODE_CLASS_MAPPINGS[id].execute(**a)
    return r.result if hasattr(r,'result') else r
def same(a,b):
    if isinstance(b,torch.Tensor):assert isinstance(a,torch.Tensor) and a.dtype is b.dtype and a.shape==b.shape and torch.equal(a,b)
    elif isinstance(b,(tuple,list)):
        assert type(a) is type(b) and len(a)==len(b)
        for x,y in zip(a,b):same(x,y)
    else:assert a==b and type(a) is type(b)
def outcome(call):
    try:return 'value',call()
    except Exception as e:return 'error',type(e),str(e)
def compare(actual,expected):
    assert actual[0]==expected[0]
    if expected[0]=='error':
        assert actual[1] is expected[1] # Filename locations differ deliberately, no host-path disclosure.
    else:same(actual[1],expected[1])
@pytest.mark.parametrize('start',[-1,0,1,2,3,4,9])
@pytest.mark.parametrize('count',[-2,0,1,2,3,99])
def test_animation_one_based_negative_index_slicing_squeeze_and_native_stack_failures(frames,start,count):
    a=args(IDS[0],start_index=start,max_frames=count)
    compare(outcome(lambda:asyncio.run(migrated(IDS[0],a))),outcome(lambda:native(frames,IDS[0],a)))
@pytest.mark.parametrize('sort_by',['Index','Alphabetic'])
@pytest.mark.parametrize('pattern',['frame*.png','frame#.png','frame?.png','frame[12].png','no-match*','*',None])
@pytest.mark.parametrize('index',[-1,0,1,3,9])
@pytest.mark.parametrize('skip',[0,1])
def test_flow_exact_glob_hash_sort_index_skip_previous_and_native_zero_output(frames,sort_by,pattern,index,skip):
    a=args(IDS[1],sort_by=sort_by,file_pattern=pattern,current_frame=index,skip_start_frames=skip)
    expected=outcome(lambda:native(frames,IDS[1],a));actual=outcome(lambda:asyncio.run(migrated(IDS[1],a)));compare(actual,expected)
    if pattern=='no-match*':assert expected==('value',()) and actual==('value',()) # Malformed declared4-output source branch remains pending.
@pytest.mark.parametrize('id',IDS)
def test_positive_default_is_exercised_not_merely_matching_failures_and_exif_is_not_rotated(frames,id):
    a=args(id)
    # Unpatterned source includes hidden files; remove nonimage only to obtain a genuine admitted album.
    (frames[0]/'frames'/'z-not-image.txt').unlink()
    expected=native(frames,id,a);actual=asyncio.run(migrated(id,a));same(actual,expected)
    assert isinstance(actual[0],torch.Tensor) and actual[0].shape[-3:-1]==(6,9) and actual[0].dtype is torch.float32
@pytest.mark.parametrize('sort_by',['Index','Alphabetic'])
def test_source_relative_vs_full_glob_name_sort_is_discriminating(frames,sort_by):
    a=args(IDS[1],sort_by=sort_by,current_frame=0)
    first=native(frames,IDS[1],a)[0];same(asyncio.run(migrated(IDS[1],a))[0],first)
    if sort_by=='Index':expected=frames[0]/'frames'/'frame1.png'
    else:expected=frames[0]/'frames'/'frame1.png'
    tensor=torch.from_numpy(np.array(Image.open(expected).convert('RGB')).astype(np.float32)/255.)[None,]
    assert torch.equal(first,tensor)
    index_order=frames[1]['get_files'](str(frames[0]/'frames'),'Index','frame*.png')
    alpha_order=frames[1]['get_files'](str(frames[0]/'frames'),'Alphabetic','frame*.png')
    assert [os.path.basename(p) for p in index_order]==['frame1.png','frame2.png','frame10.png']
    assert [os.path.basename(p) for p in alpha_order]==['frame1.png','frame10.png','frame2.png']
def test_flow_logical_override_matches_source_pinned_managed_album(frames):
    source=args(IDS[1],input_folder='ignored',input_path=str(frames[0]/'frames'),current_frame=2)
    logical=args(IDS[1],input_folder='ignored',input_path='frames',current_frame=2)
    same(asyncio.run(migrated(IDS[1],logical)),native(frames,IDS[1],source))
@pytest.mark.parametrize('pattern',['*.png','frame#.png','.hidden.png','[.]hidden.png'])
def test_hidden_glob_semantics_not_plain_fnmatch_everything(frames,pattern):
    old=frames[1]['get_files'](str(frames[0]/'frames'),'Index',pattern)
    async def run():
        refs=_sdk.InProcessRefResolver()
        with _sdk.bind_runtime(refs,types.SimpleNamespace(assets=_sdk._InProcessAssets()),_sdk.InProcessOps()):
            names=await NEW.secure_animation_inputs._files('frames')
        return NEW.secure_animation_inputs._sort(names,'Index',pattern)
    assert asyncio.run(run())==[os.path.basename(p) for p in old]
@pytest.mark.parametrize('pattern',['../*.png','nested/*.png','/host','C:*.png','a\\*.png','x'*513,'a\x00b'])
def test_pattern_is_bounded_immediate_name_before_any_broker(pattern):
    class Deny:
        def __getattr__(self,key):raise AssertionError('No broker calls')
    with pytest.raises(ValueError,match='pattern'):asyncio.run(migrated(IDS[1],args(IDS[1],file_pattern=pattern),Deny()))
@pytest.mark.parametrize('id',IDS)
@pytest.mark.parametrize('prefix',['../host','/host','a/../b','a\\b','C:host','a//b','x'*2049])
def test_directory_is_logical_prefix_not_host_authority(id,prefix):
    class Deny:
        def __getattr__(self,key):raise AssertionError('No broker calls')
    a=args(id,**({'image_sequence_folder':prefix} if id==IDS[0] else {'input_path':prefix}))
    with pytest.raises(ValueError,match='logical'):asyncio.run(migrated(id,a,Deny()))
@pytest.mark.parametrize('case',['one-height','mixed-shape','corrupt','float-start'])
def test_animation_native_decoder_rank_and_type_controls(frames,case):
    album=frames[0]/'probe';album.mkdir()
    if case=='one-height':Image.new('RGB',(9,1),'red').save(album/'a1.png')
    elif case=='corrupt':(album/'a1.png').write_bytes(b'not a PNG')
    else:
        Image.new('RGB',(9,6),'red').save(album/'a1.png');Image.new('RGB',(8 if case=='mixed-shape' else 9,6),'blue').save(album/'a2.png')
    a=args(IDS[0],image_sequence_folder='probe',max_frames=2,start_index=.5 if case=='float-start' else 1)
    compare(outcome(lambda:asyncio.run(migrated(IDS[0],a))),outcome(lambda:native(frames,IDS[0],a)))
    # Source squeeze of height1 is retained as malformed IMAGE shape, not valid BHWC claim.
def test_workload_bounds_are_before_byte_read_and_constant_size_range_selection(frames):
    m=NEW.secure_animation_inputs
    for i in range(70):Image.new('RGB',(2,2),'red').save(frames[0]/'frames'/f'a{i}.png')
    with pytest.raises(m.WorkloadError,match='count'):asyncio.run(migrated(IDS[0],args(IDS[0],max_frames=65)))
    Image.new('RGB',(4097,1)).save(frames[0]/'frames'/'huge.png')
    with pytest.raises(m.WorkloadError,match='shape'):asyncio.run(migrated(IDS[1],args(IDS[1],file_pattern='huge.png')))
    # Equivalent range slicing avoids materializing source's huge unsliced list.
    with pytest.raises(IndexError):asyncio.run(migrated(IDS[0],args(IDS[0],start_index=-(10**30),max_frames=1)))
    class Large:
        async def list(self,*a,**k):return ['frames/frame1.png']
        async def resolve(self,*a):return object()
        async def size(self,*a):return 8*1024*1024+1
        async def read_bytes(self,*a):raise AssertionError('Oversized read forbidden')
    with pytest.raises(m.WorkloadError,match='Encoded'):asyncio.run(migrated(IDS[1],args(IDS[1]),Large()))
@pytest.mark.parametrize('id',IDS)
def test_exact_schema_options_defaults_force_input_axes_and_source_hash(frames,id):
    row=LEDGER[id];cls=NEW.NODE_CLASS_MAPPINGS[id];s=cls.GET_SCHEMA();old=frames[1][row['class']]
    assert s.node_id==id and s.display_name==row['display_name'] and s.category==old.CATEGORY
    assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS==('assets','raw')
    flat={key:(g,info) for g,values in old.INPUT_TYPES().items() for key,info in values.items()}
    assert [i.id for i in s.inputs]==list(flat) and [o.io_type for o in s.outputs]==list(old.RETURN_TYPES) and [o.display_name for o in s.outputs]==list(old.RETURN_NAMES)
    for i in s.inputs:
        group,info=flat[i.id];assert i.optional==(group=='optional')
        if i.id in ('input_folder','image_sequence_folder'):assert i.remote.route=='/secure-nodes/assets/input?kind=directory' and i.options==[]
        elif isinstance(info[0],list):assert i.options==info[0]
        else:
            for k,v in (info[1] if len(info)>1 else {}).items():assert i.as_dict()[k]==v
    assert hashlib.sha256((PACK/'nodes'/row['source_file']).read_bytes()).hexdigest()==row['source_sha256']
def test_missing_logical_prefix_dispositions_not_legacy_os_existence_parity(frames):
    a=args(IDS[1],input_path=str(frames[0]/'missing'))
    assert native(frames,IDS[1],a)==('',)
    assert asyncio.run(migrated(IDS[1],args(IDS[1],input_path='missing')))==()
    with pytest.raises(FileNotFoundError):native(frames,IDS[0],args(IDS[0],image_sequence_folder='missing'))
    with pytest.raises(RuntimeError):asyncio.run(migrated(IDS[0],args(IDS[0],image_sequence_folder='missing')))
def test_two_fresh_actual_guests_outer_image_scalar_types_denials_and_production(frames,monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    (frames[0]/'frames'/'z-not-image.txt').unlink()
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        async def execute(id,a):
            cls=NEW.NODE_CLASS_MAPPINGS[id];cls.GET_SCHEMA()
            r=await execution._async_map_node_over_list(prompt_id='animation-input',unique_id='n',obj=cls,input_data_all={k:[v] for k,v in a.items()},func=cls.FUNCTION,v3_data=None)
            r=await execution.resolve_map_node_over_list_results(r);return r[0].result
        try:
            for generation in range(2):
                session=await GuestSession('ned-animation-input-'+str(generation),guest_runtime_root=V2).start();caps={'value':('assets','raw')}
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=caps['value'])
                _sdk.providers.register_execution_backend(Backend())
                try:
                    for id,a in [(IDS[0],args(IDS[0])),(IDS[1],args(IDS[1],current_frame=2)),(IDS[1],args(IDS[1],sort_by='Alphabetic',current_frame=1))]:
                        actual=await execute(id,a);same(actual,native(frames,id,a))
                        assert type(actual[0]) is torch.Tensor and actual[0].dtype is torch.float32
                        if id==IDS[1]:assert type(actual[2]) is int and type(actual[3]) is str
                    for granted in [('assets',),('raw',)]:
                        caps['value']=granted
                        for id in IDS:
                            with pytest.raises(wire.WireError,match='assets|raw|capability'):await execute(id,args(id))
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
            assert pids[0]!=pids[1]
            session=await GuestSession('ned-animation-input-production',guest_runtime_root=V2).start();backend=CloudExecutionBackend()
            monkeypatch.setattr(backend,'_is_sandbox',lambda p:True)
            async def session_for(*a,**k):return session
            monkeypatch.setattr(backend.guests,'session_for',session_for);_sdk.providers.register_execution_backend(backend)
            try:
                for id in IDS:same(await execute(id,args(id)),native(frames,id,args(id)))
            finally:await session.kill();await backend.shutdown()
        finally:_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
