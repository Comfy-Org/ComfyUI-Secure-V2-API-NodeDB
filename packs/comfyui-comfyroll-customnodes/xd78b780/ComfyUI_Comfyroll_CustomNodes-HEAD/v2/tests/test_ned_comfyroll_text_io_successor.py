"""Four authored-node managed IO successor; real local brokers, not cloud backing."""
import asyncio
import builtins
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

from multidict import MultiDict
import pytest

from test_ned_comfyroll_text_artifacts import (
    M, NEW, V2, PACK, LEDGER, LocalService, RecordingFS, native, oracle_call,
    _sdk, storage, GuestSession,
)
from comfy_secure_nodes import webassets
from comfy_secure_nodes.transport import wire

WRITERS = ['CR Save Text To File', 'CR Output Schedule To File']
READERS = ['CR Load Text List', 'CR Load Schedule From File']
LABEL = 'authored/curves'

def save_args(node_id=WRITERS[0], extension='txt', label=LABEL, name='notes', value='alpha\r\nbeta\rc\n'):
    args=dict(output_file_path=label,file_name=name,file_extension=extension)
    args.update(multiline_text=value) if node_id==WRITERS[0] else args.update(schedule=value)
    return args

def load_args(extension='txt', label=LABEL, name='notes'):
    return dict(input_file_path=label,file_name=name,file_extension=extension)

def result(value):
    return value.result if hasattr(value,'result') else value

class TracedStorage(LocalService):
    def __init__(self,path,events):super().__init__(path);self.events=events
    async def read(self,key):self.events.append(('kv-read',key));return await super().read(key)
    async def compare_and_set(self,key,rev,value):
        self.events.append(('kv-cas',key));r=await super().compare_and_set(key,rev,value)
        if r['updated']:self.events.append(('kv-committed',key))
        return r

class TracedAssets:
    def __init__(self,events):self.real=_sdk._InProcessAssets();self.events=events
    async def exists(self,folder,name):self.events.append(('exists',folder,name));return await self.real.exists(folder,name)
    async def resolve(self,folder,name):self.events.append(('resolve',folder,name));return await self.real.resolve(folder,name)
    async def size(self,ref):self.events.append(('size',));return await self.real.size(ref)
    async def read_range(self,ref,offset=0,length=8388608):
        self.events.append(('range',offset,length));return await self.real.read_range(ref,offset,length)

class TracedOutput:
    def __init__(self,events):self.real=_sdk._InProcessOutput(None,None);self.events=events
    async def write_text(self,text,filename,folder='output',mode='overwrite',insert_newline=False):
        self.events.append(('publish',filename,folder,mode,insert_newline))
        return await self.real.write_text(text,filename,folder,mode,insert_newline)

class Harness:
    def __init__(self,root):
        self.root=root;self.events=[];self.storage=TracedStorage(root/'backing',self.events)
        self.assets=TracedAssets(self.events);self.output=TracedOutput(self.events)
    def context(self):return SimpleNamespace(storage=self.storage,assets=self.assets,output=self.output)
    async def execute(self,node_id,args):
        with _sdk.bind_runtime(_sdk.InProcessRefResolver(),self.context(),_sdk.InProcessOps()):
            return await NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args)
    async def read(self,label=LABEL,name='notes',extension='txt'):
        with _sdk.bind_runtime(_sdk.InProcessRefResolver(),self.context(),_sdk.InProcessOps()):
            return await M._read(label,name,extension)
    def input(self,data,extension='txt',label=LABEL,name='notes'):
        target=self.root/'input'/label/(name+'.'+extension);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);return target
    def output_path(self,extension='txt',label=LABEL,name='notes'):
        return self.root/'output'/label/(name+'.'+extension)
    def record(self,label=LABEL,name='notes',extension='txt'):
        return self.storage.store.get('user','pack',M._key((label,name,extension)))

@pytest.fixture
def h(tmp_path,monkeypatch):
    import folder_paths
    for name in ('input','output','temp'):
        (tmp_path/name).mkdir()
        monkeypatch.setattr(folder_paths,'get_'+name+'_directory',lambda name=name:str(tmp_path/name))
    return Harness(tmp_path)

def test_missing_kv_reads_existing_managed_input(h):
    h.input(b' a\r\nb\rc\n')
    assert asyncio.run(h.read())==' a\nb\nc\n'
    assert h.storage.writes==0 and [e[0] for e in h.events]==['kv-read','resolve','size','range','size']

def test_explicit_input_observes_edit_without_kv_cache(h):
    h.storage.store.set('user','pack',M._key((LABEL,'notes','txt')),M._encode((LABEL,'notes','txt'),'authored'))
    p=h.input(b'original\r\n')
    assert asyncio.run(h.read())=='authored'
    before=h.storage.reads
    assert asyncio.run(h.read('input:'+LABEL))=='original\n'
    p.write_bytes(b'edited\r')
    assert asyncio.run(h.read('input:'+LABEL))=='edited\n'
    assert h.storage.reads==before and h.storage.writes==0
    assert json.loads(h.record())['payload']=='authored'

def test_save_commits_kv_then_publishes_exact_new_only(h):
    out=asyncio.run(h.execute(WRITERS[0],save_args()))
    assert result(out)==('https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-save-text-to-file',)
    assert h.output_path().read_bytes()==b'alpha\r\nbeta\rc\n'
    assert json.loads(h.record())['payload']=='alpha\r\nbeta\rc\n'
    steps=[e[0] for e in h.events]
    assert steps.index('kv-committed')<steps.index('publish')
    assert h.events[-1]==('publish',LABEL+'/notes.txt','output','new_only',False)

@pytest.mark.parametrize('label,name',[
    ('/host/absolute','notes'),('C:/host','notes'),('a\\b','notes'),('../escape','notes'),
    ('a/../b','notes'),('a/./b','notes'),('a//b','notes'),('input:authored','notes'),
    ('control\x1flabel','notes'),('a','../notes'),('a','n/otes'),('a','n\\otes'),('a','n:otes'),
])
def test_portable_export_names_refuse_before_any_broker(h,label,name):
    with pytest.raises(ValueError,match='logical|portable'):
        asyncio.run(h.execute(WRITERS[0],save_args(label=label,name=name)))
    assert h.events==[] and h.storage.store.list('user','pack')==[]

@pytest.mark.parametrize('node_id',WRITERS)
@pytest.mark.parametrize('extension',['txt','csv'])
@pytest.mark.parametrize('value',['','  first  \nlast \n','a,b\n"q"\n🙂','a\r\nb\rc\n','N\x85not-newline\n','\ufeffBOM\n'])
def test_exact_source_payload_and_published_newlines(h,node_id,extension,value):
    payload=value if node_id==WRITERS[0] else [('a',value),('b','1,"q"\r\n')]
    args=save_args(node_id,extension,value=payload)
    fs=RecordingFS();old=native(fs);expected=oracle_call(old,node_id,args)
    actual=result(asyncio.run(h.execute(node_id,args)))
    assert actual==expected
    source=fs.files[LABEL+'\\notes.'+extension]
    assert h.output_path(extension).read_bytes()==source.encode('utf-8')
    assert json.loads(h.record(extension=extension))['payload']==source
    for reader in READERS:
        loaded=result(asyncio.run(h.execute(reader,load_args(extension))))
        assert loaded==oracle_call(old,reader,load_args(extension))

@pytest.mark.parametrize('reader',READERS)
@pytest.mark.parametrize('extension',['txt','csv'])
@pytest.mark.parametrize('payload',[
    '', 'first\r\nsecond\rthird\n', 'a,"unclosed\ninside', 'a,b,extra\n\n',
    'a,"b"oops\r\n', '🙂\n<script>\n', 'first\x85still-one-line\n', '\ufeffa,b\n',
])
def test_imported_bytes_match_exact_source_reader(h,reader,extension,payload):
    h.input(payload.encode('utf-8'),extension)
    fs=RecordingFS();fs.files[LABEL+'\\notes.'+extension]=payload;old=native(fs)
    expected=oracle_call(old,reader,load_args(extension))
    assert result(asyncio.run(h.execute(reader,load_args(extension))))==expected
    assert h.storage.writes==0
    assert ('range',0,len(payload.encode('utf-8'))+1) in h.events

@pytest.mark.parametrize('writer,suffixes',[(WRITERS[0],['notes','notes_1','notes_2']), (WRITERS[1],['notes','notes2','notes3'])])
def test_kv_and_existing_output_collisions_follow_source_names(h,writer,suffixes):
    args=save_args(writer,value='first' if writer==WRITERS[0] else [('a','first')])
    target=h.output_path();target.parent.mkdir(parents=True);target.write_bytes(b'outside-existing')
    asyncio.run(h.execute(writer,args));asyncio.run(h.execute(writer,args))
    assert target.read_bytes()==b'outside-existing'
    assert h.record() is None
    assert {p.stem for p in target.parent.iterdir()}==set(suffixes)
    assert all(h.record(name=name) is not None for name in suffixes[1:])

@pytest.mark.parametrize('writer',WRITERS)
def test_publication_race_raises_and_preserves_committed_kv(h,monkeypatch,writer):
    original=h.output.write_text
    async def race(text,filename,**kwargs):
        p=h.root/'output'/filename;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'race-winner')
        return await original(text,filename,**kwargs)
    monkeypatch.setattr(h.output,'write_text',race)
    args=save_args(writer,value='body' if writer==WRITERS[0] else [('a','body')])
    with pytest.raises(RuntimeError,match='KV committed.*authored/curves.*notes.txt') as raised:
        asyncio.run(h.execute(writer,args))
    assert isinstance(raised.value.__cause__,FileExistsError)
    assert json.loads(h.record())['payload'] in ('body','a,"body"\n')
    assert h.output_path().read_bytes()==b'race-winner' and h.storage.writes==1
    assert asyncio.run(h.read()) in ('body','a,"body"\n')

def test_partial_io_failure_is_not_transactional_or_reset(h,monkeypatch):
    async def partial(text,filename,**kwargs):
        h.events.append(('partial-publish',filename))
        p=h.root/'output'/filename;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'par')
        raise OSError('injected disk failure')
    monkeypatch.setattr(h.output,'write_text',partial)
    with pytest.raises(RuntimeError,match='KV committed'):
        asyncio.run(h.execute(WRITERS[0],save_args(value='complete')))
    assert json.loads(h.record())['payload']=='complete' and h.output_path().read_bytes()==b'par'
    assert h.storage.writes==1 and asyncio.run(h.read())=='complete'
    monkeypatch.setattr(h.output,'write_text',TracedOutput(h.events).write_text)
    asyncio.run(h.execute(WRITERS[0],save_args(value='deliberate new save')))
    assert h.output_path().read_bytes()==b'par'
    assert h.output_path(name='notes_1').read_bytes()==b'deliberate new save'

def test_actual_new_only_stream_io_failure_leaves_partial_target_and_kv(h,monkeypatch):
    original=builtins.open
    class InterruptedWriter:
        def __init__(self,stream):self.stream=stream
        def __enter__(self):self.stream.__enter__();return self
        def __exit__(self,*args):return self.stream.__exit__(*args)
        def write(self,text):self.stream.write(text[:3]);raise OSError('injected stream write failure')
    def open_with_interrupt(path,mode='r',*args,**kwargs):
        stream=original(path,mode,*args,**kwargs)
        if Path(path)==h.output_path() and mode=='x':return InterruptedWriter(stream)
        return stream
    monkeypatch.setattr(builtins,'open',open_with_interrupt)
    with pytest.raises(RuntimeError,match='KV committed.*output publication failed') as raised:
        asyncio.run(h.execute(WRITERS[0],save_args(value='complete')))
    assert isinstance(raised.value.__cause__,OSError)
    assert h.output_path().read_bytes()==b'com' and json.loads(h.record())['payload']=='complete'
    assert h.storage.writes==1 and asyncio.run(h.read())=='complete'

@pytest.mark.parametrize('schedule',[[('only-one',)],[()],[('a','body'),()]])
def test_exact_native_malformed_txt_error_and_deliberate_preflight_side_effect_difference(h,schedule):
    args=save_args(WRITERS[1],value=schedule)
    fs=RecordingFS();old=native(fs)
    with pytest.raises(IndexError) as source:oracle_call(old,WRITERS[1],args)
    with pytest.raises(type(source.value),match=str(source.value)):
        asyncio.run(h.execute(WRITERS[1],args))
    # Native open/write can leave an empty/partial source file. The bounded
    # pack encoder intentionally fails BEFORE either CAS or publication.
    assert fs.files[LABEL+'\\notes.txt']==('a,"body"\n' if len(schedule)==2 else '')
    assert h.events==[] and h.record() is None and not h.output_path().exists()

@pytest.mark.parametrize('mode',['corrupt','quota','conflict','oversize','malformed'])
def test_failures_before_cas_success_never_publish(h,monkeypatch,mode):
    args=save_args()
    if mode=='corrupt':h.storage.store.set('user','pack',M._key((LABEL,'notes','txt')),'not JSON')
    elif mode=='quota':monkeypatch.setattr(storage,'MAX_TOTAL_BYTES',1)
    elif mode=='conflict':h.storage.conflicts=32
    elif mode=='oversize':args['multiline_text']='x'*65536
    else:args=save_args(WRITERS[1],value=[('only-one',)])
    writer=WRITERS[1] if mode=='malformed' else WRITERS[0]
    with pytest.raises((ValueError,RuntimeError,IndexError)):
        asyncio.run(h.execute(writer,args))
    assert not any(e[0]=='publish' for e in h.events) and not list((h.root/'output').rglob('*'))

@pytest.mark.parametrize('writer',WRITERS)
@pytest.mark.parametrize('label,name',[('','notes'),(LABEL,''),('','')])
def test_native_blank_returns_without_services(h,writer,label,name):
    args=save_args(writer,label=label,name=name,value='body' if writer==WRITERS[0] else [('a','body')])
    fs=RecordingFS();old=native(fs)
    assert result(asyncio.run(h.execute(writer,args)))==oracle_call(old,writer,args)==()
    assert h.events==[]

@pytest.mark.parametrize('label',['/opaque/user/label','C:\\opaque\\label','../old-opaque'])
def test_prior_opaque_kv_read_remains_data_only(h,label):
    identity=(label,'notes','txt');h.storage.store.set('user','pack',M._key(identity),M._encode(identity,'old\r\nrecord'))
    assert asyncio.run(h.read(label))=='old\nrecord' and [e[0] for e in h.events]==['kv-read']
    with pytest.raises(ValueError,match='logical|portable'):
        asyncio.run(h.execute(WRITERS[0],save_args(label=label)))
    assert json.loads(h.record(label=label))['payload']=='old\r\nrecord'

@pytest.mark.parametrize('payload',[b'\xff',b'\xc0\xaf',b'x'*65537])
def test_import_invalid_utf8_and_size_refused_without_authored_reset(h,payload):
    h.input(payload)
    with pytest.raises((UnicodeDecodeError,ValueError)):
        asyncio.run(h.read())
    assert h.storage.writes==0
    if len(payload)>65536:assert not any(e[0]=='range' for e in h.events)

@pytest.mark.parametrize('label',['../escape','input:/absolute','input:a\\b','input:C:/a','input:a/../b'])
def test_import_names_never_reach_asset_broker(h,label):
    with pytest.raises(ValueError,match='logical|portable'):
        asyncio.run(h.read(label))
    assert not any(e[0] in ('resolve','range') for e in h.events)

def test_unknown_import_does_not_mutate_authored_state(h):
    with pytest.raises(FileNotFoundError):asyncio.run(h.read())
    assert h.storage.writes==0

def test_corrupt_kv_does_not_fall_back_to_valid_input(h):
    h.input(b'valid-input')
    h.storage.store.set('user','pack',M._key((LABEL,'notes','txt')),'corrupt')
    with pytest.raises(ValueError,match='Corrupt'):asyncio.run(h.read())
    assert [e[0] for e in h.events]==['kv-read'] and h.record()=='corrupt'

@pytest.mark.parametrize('reader',READERS)
@pytest.mark.parametrize('corrupt',['{}','{"v":1,"v":1}', 'x'*65537, M._encode(('forged','notes','txt'),'wrong identity')])
def test_corrupt_envelope_never_imports_resets_or_overwrites(h,reader,corrupt):
    h.input(b'valid-input')
    h.storage.store.set('user','pack',M._key((LABEL,'notes','txt')),corrupt)
    with pytest.raises(ValueError,match='Corrupt'):
        asyncio.run(h.execute(reader,load_args()))
    assert h.record()==corrupt and h.storage.writes==0 and [e[0] for e in h.events]==['kv-read']

@pytest.mark.parametrize('conflicts',[1,31,32])
def test_bounded_cas_retries_publish_only_after_success(h,conflicts):
    h.storage.conflicts=conflicts
    if conflicts==32:
        with pytest.raises(RuntimeError,match='32 CAS'):
            asyncio.run(h.execute(WRITERS[0],save_args()))
        assert h.record() is None and not h.output_path().exists()
    else:
        asyncio.run(h.execute(WRITERS[0],save_args()))
        assert h.output_path().read_bytes()==b'alpha\r\nbeta\rc\n'
    assert h.storage.writes==min(conflicts+1,32)

def test_two_concurrent_saves_have_distinct_kv_and_publications(h):
    async def run():
        with _sdk.bind_runtime(_sdk.InProcessRefResolver(),h.context(),_sdk.InProcessOps()):
            names=await asyncio.gather(*(M._save(LABEL,'notes','txt',value,'text') for value in ('first','second')))
        assert set(names)=={'notes','notes_1'}
    asyncio.run(run())
    assert {h.output_path(name=name).read_text() for name in ('notes','notes_1')}=={'first','second'}
    for name in ('notes','notes_1'):
        assert json.loads(h.record(name=name))['payload']==h.output_path(name=name).read_text()

def test_collision_limit_never_resets_existing_authored_records(h):
    for index in range(256):
        name='notes' if index==0 else 'notes_'+str(index)
        identity=(LABEL,name,'txt')
        h.storage.store.set('user','pack',M._key(identity),M._encode(identity,'prior'))
    before={key:h.storage.store.read('user','pack',key) for key in h.storage.store.list('user','pack')}
    with pytest.raises(RuntimeError,match='256 collision'):
        asyncio.run(h.execute(WRITERS[0],save_args()))
    assert before=={key:h.storage.store.read('user','pack',key) for key in before}
    assert h.storage.reads==256 and h.storage.writes==0 and not any(e[0] in ('exists','publish') for e in h.events)

@pytest.mark.parametrize('declared_size',[True,-1,1.0,65537])
def test_asset_size_type_and_bound_checked_before_read(h,monkeypatch,declared_size):
    h.input(b'body')
    async def size(ref):return declared_size
    monkeypatch.setattr(h.assets,'size',size)
    with pytest.raises(ValueError,match='size'):
        asyncio.run(h.read())
    assert not any(e[0]=='range' for e in h.events) and h.storage.writes==0

def test_import_bound_is_whole_record_not_payload_only(h):
    h.input(b'x'*65536)
    with pytest.raises(ValueError,match='whole record'):
        asyncio.run(h.read())
    assert h.storage.writes==0

@pytest.mark.parametrize('change',['grow','shrink','edit-after-read'])
def test_complete_read_size_changes_refuse(h,monkeypatch,change):
    p=h.input(b'body');original=h.assets.read_range
    async def changed(ref,offset=0,length=8388608):
        if change!='edit-after-read':p.write_bytes(b'body-extra' if change=='grow' else b'b')
        data=await original(ref,offset,length)
        if change=='edit-after-read':p.write_bytes(b'body-extra')
        return data
    monkeypatch.setattr(h.assets,'read_range',changed)
    with pytest.raises(ValueError,match='changed|complete'):asyncio.run(h.read())
    assert h.storage.writes==0

def test_symlink_outside_input_refuses(h,tmp_path):
    outside=tmp_path/'outside.txt';outside.write_text('outside')
    p=h.root/'input'/LABEL;p.mkdir(parents=True);(p/'notes.txt').symlink_to(outside)
    with pytest.raises(ValueError,match='escape'):asyncio.run(h.read())
    assert h.storage.writes==0

def test_direct_registered_catalogue_discovers_exact_exported_names(h):
    asyncio.run(h.execute(WRITERS[0],save_args()))
    asyncio.run(h.execute(WRITERS[1],save_args(WRITERS[1],'csv',name='curve',value=[('a','0, value')])))
    class Routes:
        def __init__(self):self.handlers={}
        def get(self,path):
            def decorate(fn):self.handlers[path]=fn;return fn
            return decorate
        post=put=delete=get
    server=SimpleNamespace(routes=Routes());webassets.register_routes(server)
    handler=server.routes.handlers['/secure-nodes/text-files/{folder}']
    async def run():
        for suffix,name in [('.txt','notes.txt'),('.csv','curve.csv')]:
            response=await handler(SimpleNamespace(match_info={'folder':'output'},query=MultiDict(prefix=LABEL+'/',suffix=suffix)))
            assert json.loads(response.body)==[LABEL+'/'+name]
            assert response.headers['Cache-Control']=='no-store'
    asyncio.run(run())

@pytest.mark.parametrize('node_id',WRITERS+READERS)
def test_exact_source_schema_and_only_scoped_permissions_added(node_id):
    cls=NEW.NODE_CLASS_MAPPINGS[node_id];schema=cls.GET_SCHEMA();row=LEDGER[node_id]
    assert cls.SDK_PERMISSIONS==(('storage','assets','output') if node_id in WRITERS else ('storage','assets'))
    assert schema.node_id==node_id and schema.display_name==row['display_name'] and schema.category==row['category']
    assert schema.is_output_node==row['is_output_node'] and [o.io_type for o in schema.outputs]==row['return_types']
    assert [o.display_name for o in schema.outputs]==row['return_names'] and [o.is_output_list for o in schema.outputs]==row['output_is_list']
    flat={k:s for section in row['source_inputs'].values() for k,s in section.items()}
    assert [i.id for i in schema.inputs]==list(flat)
    for i in schema.inputs:
        src=flat[i.id]
        assert (i.options==src[0]) if isinstance(src[0],list) else (i.io_type==src[0])
        for k,v in (src[1] if len(src)>1 else {}).items():assert i.as_dict()[k]==v

def test_actual_required_fresh_guest_outer_all_four_import_export_and_denial(h,monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    monkeypatch.setattr(storage,'_STORAGE',storage.PackStorage(h.root/'guest-backing'))
    h.input(b'a,"imported"\r\nb,"line2"\n','csv')
    previous=_sdk.providers.execution_backend
    node_classes={'value':NEW.NODE_CLASS_MAPPINGS}
    async def outer(node_id,args):
        cls=node_classes['value'][node_id];cls.GET_SCHEMA()
        values=await execution._async_map_node_over_list(prompt_id='text-io-successor',unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
        values=await execution.resolve_map_node_over_list_results(values)
        return result(values[0])
    async def run():
        pids=[]
        try:
            for generation in range(2):
                restored=h.root/('recreated-pack-'+str(generation))
                shutil.copytree(V2,restored)
                name='ned_comfyroll_text_io_recreated_'+str(generation)
                spec=importlib.util.spec_from_file_location(name,restored/'__init__.py',submodule_search_locations=[str(restored)])
                recreated=importlib.util.module_from_spec(spec);sys.modules[name]=recreated;spec.loader.exec_module(recreated)
                node_classes['value']=recreated.NODE_CLASS_MAPPINGS
                # Recreate both pack filesystem and local storage owner, retaining
                # only host-managed backing/input/output between the fresh workers.
                monkeypatch.setattr(storage,'_STORAGE',storage.PackStorage(h.root/'guest-backing'))
                word='imported' if generation==0 else 'edited'
                h.input(('a,"'+word+'"\r\nb,"line2"\n').encode(),'csv')
                expected_rows=[['a',word],['b','line2']]
                session=await GuestSession('ned-text-io-successor',tenant='user-a',guest_runtime_root=restored).start()
                assert session.sandbox_kind=='seatbelt'
                caps={'value':('storage','assets','output')}
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        return await session.execute(plan,runtime,capabilities=caps['value'],tenant='user-a')
                _sdk.providers.register_execution_backend(Backend())
                try:
                    imported=await outer(READERS[1],load_args('csv','input:'+LABEL))
                    assert imported==(expected_rows,str(expected_rows))
                    assert (await outer(READERS[0],load_args('csv','input:'+LABEL)))[0]==['a,"'+word+'"\n','b,"line2"\n']
                    if generation:
                        assert (await outer(READERS[0],load_args(name='guest0')))[0]==['🙂\n','raw']
                        assert (await outer(READERS[1],load_args(name='curve0')))[0]==[['a','0, first']]
                    name='guest'+str(generation)
                    assert await outer(WRITERS[0],save_args(name=name,value='🙂\r\nraw'))==('https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-save-text-to-file',)
                    assert h.output_path(name=name).read_bytes()=='🙂\r\nraw'.encode()
                    assert (await outer(READERS[0],load_args(name=name)))[0]==['🙂\n','raw']
                    await outer(WRITERS[1],save_args(WRITERS[1],'txt',name='curve'+str(generation),value=[('a','0, first')]))
                    assert (await outer(READERS[1],load_args('txt',name='curve'+str(generation))))[0]==[['a','0, first']]
                    for node_id,args,missing in [
                        (READERS[0],load_args(name=name),'storage'),
                        (READERS[1],load_args('csv','input:'+LABEL),'assets'),
                        (WRITERS[0],save_args(name='deny'+str(generation)+'a'),'assets'),
                        (WRITERS[1],save_args(WRITERS[1],name='deny'+str(generation)+'o',value=[('a','b')]),'output'),
                    ]:
                        caps['value']=tuple(c for c in ('storage','assets','output') if c!=missing)
                        with pytest.raises(wire.WireError,match=missing):await outer(node_id,args)
                    caps['value']=('storage','assets','output')
                    # Missing output capability failed after an authoritative CAS;
                    # explicitly observe persisted data and absent publication.
                    assert (await outer(READERS[1],load_args(name='deny'+str(generation)+'o')))[0]==[['a','b']]
                    assert not h.output_path(name='deny'+str(generation)+'o').exists()
                    assert (await outer(READERS[0],load_args(name=name)))[0]==['🙂\n','raw']
                    with pytest.raises(wire.WireError,match='UTF|codec|decode'):
                        bad=h.input(b'\xff',name='bad'+str(generation));await outer(READERS[0],load_args(name=bad.stem))
                    with pytest.raises(wire.WireError,match='size|bound'):
                        large=h.input(b'x'*65537,name='large'+str(generation));await outer(READERS[0],load_args(name=large.stem))
                    with pytest.raises(wire.WireError,match='logical|portable'):
                        await outer(READERS[0],load_args(label='input:../escape'))
                    assert (await outer(READERS[1],load_args('csv','input:'+LABEL)))[0]==expected_rows
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
            assert pids[0]!=pids[1]
            node_classes['value']=NEW.NODE_CLASS_MAPPINGS
            # Authoritative KV, unlike local managed-media roots, is tested scoped.
            for tenant,pack in [('user-b','ned-text-io-successor'),('user-a','other-pack')]:
                isolated=await GuestSession(pack,tenant=tenant,guest_runtime_root=V2).start()
                assert isolated.sandbox_kind=='seatbelt'
                class IsolatedBackend:
                    async def dispatch(self,plan,local_call,runtime):
                        return await isolated.execute(plan,runtime,capabilities=('storage','assets'),tenant=tenant)
                _sdk.providers.register_execution_backend(IsolatedBackend())
                try:
                    with pytest.raises(wire.WireError,match='no input asset'):
                        await outer(READERS[0],load_args(name='guest0'))
                finally:await isolated.kill()
            # A third reconstructed guest uses the actual production backend's dispatch path.
            session=await GuestSession('ned-text-io-successor-production',guest_runtime_root=V2).start()
            assert session.sandbox_kind=='seatbelt'
            backend=CloudExecutionBackend();monkeypatch.setattr(backend,'_is_sandbox',lambda plan:True)
            async def session_for(*a,**k):return session
            monkeypatch.setattr(backend.guests,'session_for',session_for)
            _sdk.providers.register_execution_backend(backend)
            try:
                assert (await outer(READERS[1],load_args('csv','input:'+LABEL)))[0]==[['a','edited'],['b','line2']]
                await outer(WRITERS[0],save_args(name='production',value='canonical'))
                assert h.output_path(name='production').read_bytes()==b'canonical'
                assert (await outer(READERS[0],load_args(name='production')))[0]==['canonical']
                await outer(WRITERS[1],save_args(WRITERS[1],name='production-curve',value=[('a','source')]))
                assert (await outer(READERS[1],load_args(name='production-curve')))[0]==[['a','source']]
            finally:await session.kill();await backend.shutdown()
        finally:_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
