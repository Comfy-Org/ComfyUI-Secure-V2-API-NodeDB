"""Managed output XY pixels against exact pinned source with approved font-path repair."""
import ast,asyncio,copy,hashlib,importlib.util,json,os,re,sys,types,typing
from pathlib import Path
import numpy as np
import pytest,torch
from PIL import Image,ImageFont
from test_ned_comfyroll_cycle_models import NEW,V2,PACK,_sdk,GuestSession,wire
import folder_paths
ID='CR XY From Folder'
LEDGER=json.loads((V2/'xy-input-draft-ledger.json').read_text())[ID]
TREE=ast.parse((PACK/'nodes/nodes_xygrid.py').read_text())
def source(root,repair=True):
    spec=importlib.util.spec_from_file_location('ned_pinned_xy_helpers',PACK/'nodes/functions_xygrid.py')
    mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
    ns={'__file__':str(PACK/'nodes/nodes_xygrid.py'),'os':os,'re':re,'np':np,'torch':torch,'Image':Image,'ImageFont':ImageFont,'t':typing,'folder_paths':types.SimpleNamespace(output_directory=str(root)), 'icons':ast.literal_eval(ast.parse((PACK/'categories.py').read_text()).body[0].value),'Annotation':mod.Annotation,'create_images_grid_by_columns':mod.create_images_grid_by_columns}
    nodes=[copy.deepcopy(n) for n in TREE.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in ('tensor_to_pillow','pillow_to_tensor','CR_XYFromFolder')]
    if repair:
        for node in nodes:
            for value in ast.walk(node):
                if isinstance(value,ast.Constant) and value.value=='fonts\\Roboto-Regular.ttf':value.value='fonts/Roboto-Regular.ttf'
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'pinned-xy-font-repair-only' if repair else 'pinned-native-xy','exec'),ns)
    return ns
@pytest.fixture(params=['RGB','RGBA'])
def album(request,tmp_path,monkeypatch):
    root=tmp_path/'output';p=root/'album';p.mkdir(parents=True)
    for number in (10,2,1,3):
        pixels=(np.arange(7*11*3,dtype=np.uint8).reshape(7,11,3)+number*19)
        image=Image.fromarray(pixels)
        if request.param=='RGBA':image=image.convert('RGBA');image.putalpha(39)
        exif=Image.Exif();exif[274]=6;image.save(p/f'image{number}.png',exif=exif)
    monkeypatch.setattr(folder_paths,'get_output_directory',lambda:str(root))
    return root,source(root)
def args(**changes):
    a=dict(image_folder='album',start_index=1,end_index=4,max_columns=2,x_annotation='one;two;three;four;',y_annotation=' top;middle;bottom;',font_size=12,gap=3,trigger=True);a.update(changes);return a
def native(album,a,repair=True):
    ns=album[1] if repair else source(album[0],False);return ns['CR_XYFromFolder']().load_images(**a)
async def migrated(a,assets=None):
    with _sdk.bind_runtime(_sdk.InProcessRefResolver(),types.SimpleNamespace(assets=assets or _sdk._InProcessAssets()),_sdk.InProcessOps()):
        result=await NEW.NODE_CLASS_MAPPINGS[ID].execute(**a)
    return result.result if hasattr(result,'result') else result
def same(a,b):
    assert type(a) is type(b) and len(a)==len(b)==3 and a[1:]==b[1:] and type(a[1]) is type(b[1])
    if isinstance(b[0],torch.Tensor):assert type(a[0]) is torch.Tensor and a[0].shape==b[0].shape and a[0].dtype is b[0].dtype and torch.equal(a[0],b[0])
    else:assert a[0]==b[0] and type(a[0]) is type(b[0])
def outcome(call):
    try:return 'value',call()
    except Exception as error:return 'error',type(error),str(error)
def compare(a,b):
    assert a[0]==b[0]
    if b[0]=='value':same(a[1],b[1])
    else:assert a[1] is b[1]
@pytest.mark.parametrize('start',[-1,0,1,2,3,4,5])
@pytest.mark.parametrize('end',[0,1,2,4,9])
@pytest.mark.parametrize('columns',[1,2,3])
def test_exact_source_natural_order_one_based_zero_last_end_clamp_annotations_and_grid_pixels(album,start,end,columns):
    a=args(start_index=start,end_index=end,max_columns=columns)
    compare(outcome(lambda:asyncio.run(migrated(a))),outcome(lambda:native(album,a)))
@pytest.mark.parametrize('x,y',[('',''),(' left ; right\nline;',' top ;middle; bottom ;'),('<img src=x onerror=alert(1)>;','{{unsafe}};'),('a;',''),('','b;')])
@pytest.mark.parametrize('gap',[0,2,-1])
@pytest.mark.parametrize('size',[1,12,50])
def test_source_annotation_slices_strip_multiline_safe_literals_gap_and_font_pixels(album,x,y,gap,size):
    a=args(x_annotation=x,y_annotation=y,gap=gap,font_size=size)
    compare(outcome(lambda:asyncio.run(migrated(a))),outcome(lambda:native(album,a)))
def test_positive_default_annotated_result_and_source_order_are_discriminating(album):
    a=args();expected=native(album,a);same(asyncio.run(migrated(a)),expected)
    assert expected[0].ndim==4 and expected[0].shape[-1]==3 and expected[0].dtype is torch.float32
    async def names():
        with _sdk.bind_runtime(_sdk.InProcessRefResolver(),types.SimpleNamespace(assets=_sdk._InProcessAssets()),_sdk.InProcessOps()):return await NEW.secure_xy_input._files('album')
    assert asyncio.run(names())==['image1.png','image2.png','image3.png','image10.png']
    # Exact oracle omits EXIF transpose; annotations do not interpret markup.
def test_trigger_false_retains_empty_image_native_contract_without_reading_or_font_work(album):
    class Deny:
        def __getattr__(self,key):raise AssertionError('No broker calls')
    a=args(trigger=False,image_folder='../forbidden',max_columns=999999)
    same(asyncio.run(migrated(a,Deny())),native(album,a));assert native(album,a)[0]==()
def test_windows_font_separator_original_error_and_byte_exact_approved_repair_control(album):
    with pytest.raises(OSError):native(album,args(),repair=False)
    same(asyncio.run(migrated(args())),native(album,args(),repair=True))
    assert (V2/'fonts/Roboto-Regular.ttf').read_bytes()==(PACK/'fonts/Roboto-Regular.ttf').read_bytes()
@pytest.mark.parametrize('changes',[{'max_columns':0},{'font_size':0},{'font_size':-1},{'gap':-20},{'start_index':.5},{'end_index':.5}])
def test_bounded_native_arithmetic_font_range_errors_not_silently_repaired(album,changes):
    a=args(**changes);compare(outcome(lambda:asyncio.run(migrated(a))),outcome(lambda:native(album,a)))
@pytest.mark.parametrize('case',['one-height','one-width','mixed-size','corrupt','empty'])
def test_source_squeeze_decode_and_stack_errors_or_pixels_remain_visible(album,case):
    p=album[0]/'probe';p.mkdir()
    if case!='empty':
        if case=='corrupt':(p/'a1.png').write_bytes(b'not a png')
        else:
            Image.new('RGB',(1 if case=='one-width' else 11,1 if case=='one-height' else 7),'red').save(p/'a1.png')
            if case=='mixed-size':Image.new('RGB',(9,7),'blue').save(p/'a2.png')
    a=args(image_folder='probe',end_index=2)
    compare(outcome(lambda:asyncio.run(migrated(a))),outcome(lambda:native(album,a)))
@pytest.mark.parametrize('value',['../host','/host','C:host','a\\b','a/../b','a//b','x'*2049])
def test_logical_selection_rejects_host_path_before_broker(album,value):
    class Deny:
        def __getattr__(self,key):raise AssertionError('No broker calls')
    with pytest.raises(ValueError,match='logical'):asyncio.run(migrated(args(image_folder=value),Deny()))
def test_count_encoded_decode_text_and_grid_projection_limits_are_fail_closed(album,monkeypatch):
    m=NEW.secure_xy_input
    class Many:
        async def list(self,*a,**k):return ['album/a'+str(i)+'.png' for i in range(65)]
        async def resolve(self,*a,**k):raise AssertionError('Count bound before reads')
    with pytest.raises(m.WorkloadError,match='count'):asyncio.run(migrated(args(end_index=65),Many()))
    class Large:
        async def list(self,*a,**k):return ['album/a1.png']
        async def resolve(self,*a,**k):return object()
        async def size(self,*a,**k):return 8*1024*1024+1
        async def read_bytes(self,*a,**k):raise AssertionError('No oversized read')
    with pytest.raises(m.WorkloadError,match='encoded'):asyncio.run(migrated(args(),Large()))
    with pytest.raises(m.WorkloadError,match='annotation'):asyncio.run(migrated(args(x_annotation='a'*4097)))
    huge=album[0]/'huge';huge.mkdir();Image.new('RGB',(4097,1),'red').save(huge/'a1.png')
    with pytest.raises(m.WorkloadError,match='shape'):asyncio.run(migrated(args(image_folder='huge')))
    wide=album[0]/'wide';wide.mkdir();Image.new('RGB',(1000,2),'red').save(wide/'a1.png')
    # Reject projected250000 width BEFORE helper Image.new (source could allocate immense grid).
    with pytest.raises(m.WorkloadError,match='axes'):asyncio.run(migrated(args(image_folder='wide',max_columns=250)))
def test_exact_schema_and_source_helper_font_hashes_and_remote_catalogue(album):
    cls=NEW.NODE_CLASS_MAPPINGS[ID];schema=cls.GET_SCHEMA();old=album[1]['CR_XYFromFolder']
    assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS==('assets','raw') and schema.node_id==ID and schema.category==old.CATEGORY and schema.display_name==LEDGER['display_name']
    flat={k:(g,v) for g,group in old.INPUT_TYPES().items() for k,v in group.items()}
    assert [i.id for i in schema.inputs]==list(flat) and [o.io_type for o in schema.outputs]==list(old.RETURN_TYPES) and [o.display_name for o in schema.outputs]==list(old.RETURN_NAMES)
    for input in schema.inputs:
        g,v=flat[input.id];assert input.optional==(g=='optional')
        if input.id=='image_folder':assert input.options==[] and input.remote.route=='/secure-nodes/assets/output?kind=directory'
        else:
            for k,val in (v[1] if len(v)>1 else {}).items():assert input.as_dict()[k]==val
    assert hashlib.sha256((PACK/'nodes'/LEDGER['source_file']).read_bytes()).hexdigest()==LEDGER['source_sha256']
    assert (V2/'nodes/functions_xygrid.py').read_bytes()==(PACK/'nodes/functions_xygrid.py').read_bytes()
def test_two_actual_guest_reconstructions_output_catalogue_outer_types_denials_and_production(album,monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        async def execute(a):
            cls=NEW.NODE_CLASS_MAPPINGS[ID];cls.GET_SCHEMA()
            r=await execution._async_map_node_over_list(prompt_id='xy-input',unique_id='n',obj=cls,input_data_all={k:[v] for k,v in a.items()},func=cls.FUNCTION,v3_data=None)
            r=await execution.resolve_map_node_over_list_results(r);return r[0].result
        try:
            for generation in range(2):
                session=await GuestSession('ned-xy-input-'+str(generation),guest_runtime_root=V2).start();caps={'value':('assets','raw')}
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=caps['value'])
                _sdk.providers.register_execution_backend(Backend())
                try:
                    for a in [args(),args(start_index=0,end_index=2),args(max_columns=1,x_annotation='A;B;C;',y_annotation='D;E;F;')]:
                        actual=await execute(a);same(actual,native(album,a));assert type(actual[0]) is torch.Tensor and type(actual[1]) is bool and type(actual[2]) is str
                    for granted in [('assets',),('raw',)]:
                        caps['value']=granted
                        with pytest.raises(wire.WireError,match='assets|raw|capability'):await execute(args())
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
            assert pids[0]!=pids[1]
            session=await GuestSession('ned-xy-input-production',guest_runtime_root=V2).start();backend=CloudExecutionBackend();monkeypatch.setattr(backend,'_is_sandbox',lambda p:True)
            async def session_for(*a,**k):return session
            monkeypatch.setattr(backend.guests,'session_for',session_for);_sdk.providers.register_execution_backend(backend)
            try:same(await execute(args()),native(album,args()))
            finally:await session.kill();await backend.shutdown()
        finally:_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())

