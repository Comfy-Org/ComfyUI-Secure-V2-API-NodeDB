"""Original source filenames/encoder controls and deliberate managed cardinality policy."""
import ast,asyncio,copy,datetime,hashlib,json,os,re,types
from pathlib import Path
import numpy as np
import pytest,torch
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from test_ned_comfyroll_cycle_models import NEW,V2,PACK,_sdk,GuestSession,wire
import folder_paths
IDS=['CR Image Output','CR XY Save Grid Image','CR Output Flow Frames']
LEDGER=json.loads((V2/'output-writers-draft-ledger.json').read_text())
class Clock:
    @staticmethod
    def now():return datetime.datetime(2026,10,7,12,30)
def pixels(dtype=torch.float32,batch=3,channels=3):return torch.linspace(-.1,1.1,batch*7*11*channels).reshape(batch,7,11,channels).to(dtype)
@pytest.fixture
def roots(tmp_path,monkeypatch):
    paths={version:{folder:tmp_path/version/folder for folder in ('output','temp')} for version in ('source','v2')}
    for group in paths.values():
        for p in group.values():p.mkdir(parents=True);(p/'album').mkdir()
    for folder,p in paths['v2'].items():monkeypatch.setattr(folder_paths,'get_'+folder+'_directory',lambda p=p:str(p))
    monkeypatch.setattr(NEW.secure_output_writers,'datetime',types.SimpleNamespace(datetime=Clock))
    return paths
def args(id,**changes):
    if id==IDS[0]:a=dict(images=pixels(),file_format='png',prefix_presets='None',filename_prefix='CR',trigger=True,output_type='Save')
    elif id==IDS[1]:a=dict(mode='Save',output_folder='album',image=pixels(),file_format='png',filename_prefix='CR',trigger=True,output_path='')
    else:a=dict(output_folder='album',current_image=pixels(),current_frame=3,filename_prefix='CR',output_path='',interpolated_img=None)
    a.update(changes);return a
def native(id,a,roots):
    calls=[];server=types.SimpleNamespace(client_id='SOURCE-ONLY-AUDIENCE',send_sync=lambda kind,data,audience:calls.append((kind,data,audience)))
    folders=types.SimpleNamespace(output_directory=str(roots['source']['output']),temp_directory=str(roots['source']['temp']),get_output_directory=lambda:str(roots['source']['output']),get_temp_directory=lambda:str(roots['source']['temp']))
    path=PACK/'nodes'/LEDGER[id]['source_file'];tree=ast.parse(path.read_text());name=LEDGER[id]['class']
    body=[copy.deepcopy(n) for n in tree.body if isinstance(n,ast.ClassDef) and n.name==name or isinstance(n,ast.FunctionDef) and n.name=='find_highest_numeric_value']
    ns={'torch':torch,'np':np,'Image':Image,'PngInfo':PngInfo,'os':os,'re':re,'json':json,'datetime':types.SimpleNamespace(datetime=Clock),'PromptServer':types.SimpleNamespace(instance=server),'BinaryEventTypes':types.SimpleNamespace(UNENCODED_PREVIEW_IMAGE=42),'folder_paths':folders,'icons':{}}
    exec(compile(ast.Module(body=body,type_ignores=[]),'pinned-source-'+id,'exec'),ns)
    c=ns[name]();result=getattr(c,c.FUNCTION)(**a)
    return result,calls
async def migrated(id,a):
    refs=_sdk.InProcessRefResolver()
    context=_sdk.InProcessCtxProvider().build(_sdk.ExecutionPlan(prompt_id='output-controls',node_id='n',node_type=id,prompt=a.get('prompt'),extra_pnginfo=a.get('extra_pnginfo')))
    with _sdk.bind_runtime(refs,context,_sdk.InProcessOps()):result=await NEW.NODE_CLASS_MAPPINGS[id].execute(**a)
    return result
def outcome(call):
    try:return 'value',call()
    except Exception as error:return 'error',type(error),str(error)
def descriptors(result):return result.ui['images']
def source_file(row,roots):
    sub=row['subfolder'];root=roots['source'][row['type']]
    folder=Path(sub) if Path(sub).is_absolute() else root/sub
    return folder/row['filename']
def new_file(row,roots):
    assert row['type'] in ('output','temp') and not Path(row['subfolder']).is_absolute() and '..' not in Path(row['subfolder']).parts
    return roots['v2'][row['type']]/row['subfolder']/row['filename']
def compare(id,a,roots,*,require_value=False):
    b=outcome(lambda:native(id,a,roots));r=outcome(lambda:asyncio.run(migrated(id,a)))
    if require_value:assert b[0]==r[0]=='value', (b,r)
    assert b[0]==r[0], (b,r)
    if b[0]=='error':assert b[1] is r[1];return
    old,calls=b[1];new=r[1]
    if id==IDS[1] and a['trigger']==False:assert old==new==();return
    if id==IDS[0]:
        assert new.result==(a['trigger'],)
        if a['output_type']=='UI (no batch)':
            assert 'result' not in old and len(calls)==a['images'].shape[0]
            assert all(kind==42 and data[0]=='PNG' and audience=='SOURCE-ONLY-AUDIENCE' for kind,data,audience in calls)
            assert len(descriptors(new))==len(calls)
            for row,(_,data,_) in zip(descriptors(new),calls):
                assert row['type']=='temp' and 'source' not in row
                assert np.array_equal(np.array(Image.open(new_file(row,roots))),np.array(data[1]))
            return
        assert len(old['result'])==2 and old['result'][0]==new.result[0]
    else:assert 'result' not in old and new.result is None
    assert len(descriptors(new))==len(old['ui']['images'])
    for row,original in zip(descriptors(new),old['ui']['images']):
        assert row['filename']==original['filename'] and row['type']==original['type']
        assert new_file(row,roots).read_bytes()==source_file(original,roots).read_bytes()
@pytest.mark.parametrize('id',IDS[:2])
@pytest.mark.parametrize('mode',['Save','Preview'])
@pytest.mark.parametrize('format',['png','jpg','webp','tif'])
@pytest.mark.parametrize('dtype',[torch.float32,torch.float16,torch.float64,torch.bfloat16])
@pytest.mark.parametrize('channels',[1,3,4])
def test_exact_source_counter_names_first_or_batch_pixels_encoder_defaults_and_native_dtype_modes(id,mode,format,dtype,channels,roots):
    a=args(id,**({'images':pixels(dtype,channels=channels),'output_type':mode} if id==IDS[0] else {'image':pixels(dtype,channels=channels),'mode':mode}),file_format=format)
    compare(id,a,roots,require_value=dtype in (torch.float32,torch.float16,torch.float64) and channels==3)
@pytest.mark.parametrize('format',['png','jpg','webp','tif','unknown'])
@pytest.mark.parametrize('batch',[0,1,3])
def test_ui_no_batch_scoped_managed_png_pixels_and_single_trigger_not_source_zero_cardinality(format,batch,roots):
    compare(IDS[0],args(IDS[0],images=pixels(batch=batch),output_type='UI (no batch)',file_format=format),roots,require_value=True)
@pytest.mark.parametrize('prefix',['CR','_CR','folder/CR','folder/_CR'])
@pytest.mark.parametrize('preset',['None','yyyyMMdd','unrecognized-non-None'])
def test_source_date_prefix_one_leading_underscore_and_subfolder_counter_filter(prefix,preset,roots):
    date='_20261007' if preset!='None' else ''
    final=(prefix+date);final=final[1:] if final[0]=='_' else final
    sub=Path(final).parent;name=Path(final).name
    for group in roots.values():
        p=group['output']/sub;p.mkdir(exist_ok=True,parents=True)
        for filename in [name+'_00004_.png',name+'_9_ignored.jpg','other_90_.png',name+'_text_.png',name+'X_99_.png']:(p/filename).write_bytes(b'counter sentinel')
    compare(IDS[0],args(IDS[0],filename_prefix=prefix,prefix_presets=preset),roots,require_value=True)
    assert any(row.name.endswith('_00010_.png') for row in roots['v2']['output'].rglob('*.png'))
@pytest.mark.parametrize('format',['png','jpg','webp','tif'])
def test_nonempty_prompt_metadata_png_only_exact_source_bytes_and_no_nonpng_exif(format,roots):
    compare(IDS[0],args(IDS[0],file_format=format,prompt={'node':{'inputs':{'text':'literal Ω'}}},extra_pnginfo={'workflow':{'nodes':[1,2]},'safe_note':'literal'}),roots,require_value=True)
def test_empty_prompt_metadata_key_exact_source_png_without_hidden_prompt_recovery(roots):
    old,_=native(IDS[0],args(IDS[0],images=pixels(batch=1),prompt={}),roots)
    new=asyncio.run(migrated(IDS[0],args(IDS[0],images=pixels(batch=1),prompt={})))
    source_info=Image.open(source_file(old['ui']['images'][0],roots)).info
    new_info=Image.open(new_file(descriptors(new)[0],roots)).info
    assert source_info.get('prompt')==new_info.get('prompt')=='{}'
    assert source_file(old['ui']['images'][0],roots).read_bytes()==new_file(descriptors(new)[0],roots).read_bytes()
    assert new.result==(True,)
@pytest.mark.parametrize('pair',[False,True])
@pytest.mark.parametrize('frame',[-1,0,3,100001])
def test_flow_exact_frame_names_first_batch_distinct_pair_pixels_and_atomic_same_name_replacement(pair,frame,roots):
    a=args(IDS[2],current_frame=frame,interpolated_img=torch.flip(pixels(),[2]) if pair else None)
    compare(IDS[2],a,roots,require_value=True)
    old={p.name:p.read_bytes() for p in (roots['v2']['output']/'album').iterdir()}
    a['current_image']=torch.zeros_like(a['current_image'])
    if pair:a['interpolated_img']=torch.ones_like(a['interpolated_img'])
    compare(IDS[2],a,roots,require_value=True)
    assert len(list((roots['v2']['output']/'album').iterdir()))==(2 if pair else 1)
    assert any(p.read_bytes()!=old[p.name] for p in (roots['v2']['output']/'album').iterdir())
@pytest.mark.parametrize('id',IDS)
def test_workflow_reload_and_native_declared_output_cardinality_controls(id,roots):
    a=args(id);image=a.pop('images' if id==IDS[0] else 'image' if id==IDS[1] else 'current_image');a=json.loads(json.dumps(a));a['images' if id==IDS[0] else 'image' if id==IDS[1] else 'current_image']=image
    compare(id,a,roots,require_value=True)
    cls=NEW.NODE_CLASS_MAPPINGS[id];s=cls.GET_SCHEMA();assert s.is_output_node and len(s.outputs)==len(LEDGER[id]['return_types'])
    assert cls.SDK_REFS is False and list(cls.SDK_PERMISSIONS)==LEDGER[id]['permissions']
    flat={k:(g,v) for g,d in LEDGER[id]['source_inputs'].items() if g!='hidden' for k,v in d.items()}
    assert [i.id for i in s.inputs]==list(flat)
    for i in s.inputs:
        g,v=flat[i.id];assert i.optional==(g=='optional')
        if i.id=='output_folder':assert i.remote.route=='/secure-nodes/assets/output?kind=directory' and i.options==[]
        elif isinstance(v[0],list):assert i.options==v[0]
        else:
            for k,value in (v[1] if len(v)>1 else {}).items():assert i.as_dict()[k]==value
    if id==IDS[0]:assert set(s.hidden)=={NEW.secure_output_writers.io.Hidden.prompt,NEW.secure_output_writers.io.Hidden.extra_pnginfo}
    assert hashlib.sha256((PACK/'nodes'/LEDGER[id]['source_file']).read_bytes()).hexdigest()==LEDGER[id]['source_sha256']
def test_xy_false_source_zero_no_side_effects_and_regex_counter_native_defect(roots):
    compare(IDS[1],args(IDS[1],trigger=False,output_path='/forbidden',image=None),roots,require_value=True)
    for group in roots.values():(group['output']/'album'/'CR_bad.png').write_bytes(b'keep')
    b=outcome(lambda:native(IDS[1],args(IDS[1]),roots));r=outcome(lambda:asyncio.run(migrated(IDS[1],args(IDS[1]))))
    assert b[0]==r[0]=='error' and b[1] is r[1] is AttributeError
@pytest.mark.parametrize('id',IDS)
@pytest.mark.parametrize('value',['../escape','/escape','C:escape','a\\b','a/../b','a//b','x'*2049])
def test_path_reinterpretation_is_fail_closed_without_any_write(id,value,roots):
    a=args(id,**({'filename_prefix':value} if id==IDS[0] else {'output_path':value}))
    with pytest.raises(ValueError):asyncio.run(migrated(id,a))
    assert not any(p.is_file() for group in roots.values() for root in group.values() for p in root.rglob('*'))
def test_output_bounds_before_numpy_or_broker_and_empty_source_failures_retained(roots):
    for id in IDS:
        key='images' if id==IDS[0] else 'image' if id==IDS[1] else 'current_image'
        a=args(id,**{key:torch.empty(16,4096,4096,3,device='meta')})
        with pytest.raises(ValueError,match='workload'):asyncio.run(migrated(id,a))
    compare(IDS[0],args(IDS[0],images=pixels(batch=0)),roots,require_value=True)
    for id in IDS[1:]:
        key='image' if id==IDS[1] else 'current_image'
        compare(id,args(id,**{key:pixels(batch=0)}),roots)
@pytest.mark.parametrize('id',IDS)
def test_two_real_confined_guests_outer_declared_cardinality_encoding_roots_overwrite_and_denials(id,roots,monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        async def execute(a):
            cls=NEW.NODE_CLASS_MAPPINGS[id];cls.GET_SCHEMA()
            inputs=dict(a);hidden={}
            for name,key in [('prompt',NEW.secure_output_writers.io.Hidden.prompt),('extra_pnginfo',NEW.secure_output_writers.io.Hidden.extra_pnginfo)]:
                if name in inputs:hidden[key]=inputs.pop(name)
            r=await execution._async_map_node_over_list(prompt_id='managed-output',unique_id='n',obj=cls,input_data_all={k:[v] for k,v in inputs.items()},func=cls.FUNCTION,v3_data={'hidden_inputs':hidden} if hidden else None)
            r=await execution.resolve_map_node_over_list_results(r);return r[0]
        try:
            for generation in range(2):
                session=await GuestSession('ned-output-'+str(generation)+id,guest_runtime_root=V2).start();caps={'value':tuple(LEDGER[id]['permissions'])}
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=caps['value'])
                _sdk.providers.register_execution_backend(Backend())
                try:
                    cases=[args(id,filename_prefix='Guest'+str(generation))]
                    if id!=IDS[2]:cases.extend(args(id,filename_prefix='Guest'+str(generation)+f, file_format=f,**({'output_type':'Preview'} if id==IDS[0] else {'mode':'Preview'})) for f in ['jpg','webp','tif'])
                    if id==IDS[2]:cases.append(args(id,filename_prefix='Guest'+str(generation)+'Pair',interpolated_img=torch.flip(pixels(),[2])))
                    if id==IDS[0]:cases.append(args(id,filename_prefix='Guest'+str(generation)+'EmptyPrompt',prompt={}))
                    for a in cases:
                        original,_=native(id,a,roots)
                        result=await execute(a)
                        assert result.result==(True,) if id==IDS[0] else result.result is None
                        assert result.ui['images'] and all(new_file(row,roots).is_file() for row in result.ui['images'])
                        for row,old in zip(result.ui['images'],original['ui']['images']):
                            assert row['filename']==old['filename'] and row['type']==old['type'] and new_file(row,roots).read_bytes()==source_file(old,roots).read_bytes()
                        if id==IDS[2] and a['interpolated_img'] is not None:
                            row=result.ui['images'][0];old=original['ui']['images'][0]
                            assert new_file(row,roots).with_name(row['filename'].replace('_0.png','_1.png')).read_bytes()==source_file(old,roots).with_name(old['filename'].replace('_0.png','_1.png')).read_bytes()
                    if id==IDS[2]:
                        before=new_file(result.ui['images'][0],roots).read_bytes();a={**cases[-1],'current_image':torch.zeros_like(pixels())};again=await execute(a)
                        assert again.ui['images'][0]['filename']==result.ui['images'][0]['filename']
                        assert new_file(again.ui['images'][0],roots).read_bytes()!=before
                    if id==IDS[0]:
                        a=args(id,output_type='UI (no batch)');original,calls=native(id,a,roots);result=await execute(a)
                        assert 'result' not in original and result.result==(True,) and len(result.ui['images'])==len(calls)==3
                        for row,(_,data,_) in zip(result.ui['images'],calls):assert row['type']=='temp' and np.array_equal(np.array(Image.open(new_file(row,roots))),np.array(data[1]))
                    before_files={str(p):p.read_bytes() for root in roots['v2'].values() for p in root.rglob('*') if p.is_file()}
                    for missing in LEDGER[id]['permissions']:
                        caps['value']=tuple(x for x in LEDGER[id]['permissions'] if x!=missing)
                        a=args(id,filename_prefix='Denied'+missing,**({'output_type':'UI (no batch)'} if id==IDS[0] and missing=='ui' else {}))
                        with pytest.raises(wire.WireError,match='raw|assets|output|ui|capability'):await execute(a)
                        assert before_files=={str(p):p.read_bytes() for root in roots['v2'].values() for p in root.rglob('*') if p.is_file()}
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
            assert pids[0]!=pids[1]
            session=await GuestSession('ned-output-production-'+id,guest_runtime_root=V2).start();backend=CloudExecutionBackend();monkeypatch.setattr(backend,'_is_sandbox',lambda p:True)
            async def session_for(*a,**k):return session
            monkeypatch.setattr(backend.guests,'session_for',session_for);_sdk.providers.register_execution_backend(backend)
            try:
                result=await execute(args(id,filename_prefix='Production'))
                assert result.result==(True,) if id==IDS[0] else result.result is None
                assert all(new_file(row,roots).is_file() for row in result.ui['images'])
            finally:await session.kill();await backend.shutdown()
        finally:_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
