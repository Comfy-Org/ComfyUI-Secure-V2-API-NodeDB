"""Pinned txt/csv algorithms under recording IO; actual scoped broker/guest continuity."""
import ast
import asyncio
import copy
import csv
from io import StringIO
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.dont_write_bytecode=True;sys.argv=['ned-comfyroll-artifacts','--cpu']
CORE=Path(os.environ['COMFY_CORE_ROOT']);sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy_api.latest import _sdk
from comfy_secure_nodes import storage
from comfy_secure_nodes.transport.host import GuestSession
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
spec=importlib.util.spec_from_file_location('ned_comfyroll_artifacts_pack',V2/'__init__.py',submodule_search_locations=[str(V2)])
NEW=importlib.util.module_from_spec(spec);sys.modules[spec.name]=NEW;spec.loader.exec_module(NEW)
M=NEW.secure_text_artifacts;LEDGER=json.loads((V2/'text-artifact-draft-ledger.json').read_text())
SOURCE_TREES={name:ast.parse((PACK/'nodes'/name).read_text()) for name in {row['source_file'] for row in LEDGER.values()}}

class RecordingFS:
    """Oracle IO recording, not authority proof or actual OS-path compatibility."""
    def __init__(self):self.files={}
    def open(self,path,mode,newline=None):
        owner=self
        if mode=='r':return StringIO(self.files[path].replace('\r\n','\n').replace('\r','\n'))
        class Writer(StringIO):
            def __exit__(self,*args):owner.files[path]=self.getvalue();return super().__exit__(*args)
        return Writer(newline=newline)
    def exists(self,path):return path in self.files

def native(fs):
    old={};icons=ast.literal_eval(ast.parse((PACK/'categories.py').read_text()).body[0].value)
    for node_id,row in LEDGER.items():
        tree=SOURCE_TREES[row['source_file']];cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==row['class'])
        scope={'icons':icons,'csv':csv,'os':SimpleNamespace(path=SimpleNamespace(exists=fs.exists)),'open':fs.open}
        exec(compile(ast.Module(body=[copy.deepcopy(cls)],type_ignores=[]),'pinned-text-artifact','exec'),scope);old[node_id]=scope[row['class']]
    return old

class LocalService:
    def __init__(self,path):self.store=storage.PackStorage(path);self.conflicts=0;self.writes=0;self.reads=0
    async def read(self,key):self.reads+=1;await asyncio.sleep(0);return self.store.read('user','pack',key)
    async def compare_and_set(self,key,rev,value):
        self.writes+=1;await asyncio.sleep(0)
        if self.conflicts:self.conflicts-=1;return dict(self.store.read('user','pack',key),updated=False)
        return self.store.compare_and_set('user','pack',key,rev,value)

async def call(service,node_id,args):
    with _sdk.bind_runtime(_sdk.InProcessRefResolver(),SimpleNamespace(storage=service),_sdk.InProcessOps()):
        return await NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args)

def identity(name='notes',extension='txt',label='user-authored'):
    return (label,name,extension)

def oracle_call(old,node_id,args):
    obj=old[node_id]();return getattr(obj,obj.FUNCTION)(**args)

@pytest.mark.parametrize('extension',['txt','csv'])
@pytest.mark.parametrize('text',['','  leading \ntrailing  \n','a,b\n"quote"\nend','a\r\nb\rc\n','🙂\n<script>\n','first\x85still-line\nnext'])
def test_saved_text_exact_bytes_and_raw_line_loader(extension,text,tmp_path):
    fs=RecordingFS();old=native(fs);service=LocalService(tmp_path)
    args=dict(multiline_text=text,output_file_path='user-authored',file_name='notes',file_extension=extension)
    expected=oracle_call(old,'CR Save Text To File',args)
    async def run():
        result=await call(service,'CR Save Text To File',args);assert result.result==expected
        payload=json.loads(service.store.get('user','pack',M._key(identity(extension=extension))))['payload']
        assert payload==fs.files['user-authored\\notes.'+extension]
        load=dict(input_file_path='user-authored',file_name='notes',file_extension=extension)
        before=service.writes
        assert (await call(service,'CR Load Text List',load)).result==oracle_call(old,'CR Load Text List',load)
        assert service.writes==before
    asyncio.run(run())

@pytest.mark.parametrize('extension',['txt','csv'])
@pytest.mark.parametrize('schedule',[
 [],[('a','0, first'),('b','1, second')],
 [('a','embedded\nnewline'),('"quoted"','comma, quote" and \r\n')],
 [('0','0'),('1','')], [('only-one',)], [['a','b','extra']], ['abc'], [('',None)],
])
def test_schedule_encoding_parsing_and_native_malformed_outcomes(extension,schedule,tmp_path):
    fs=RecordingFS();old=native(fs);service=LocalService(tmp_path)
    args=dict(output_file_path='user-authored',file_name='notes',file_extension=extension,schedule=schedule)
    try:expected=oracle_call(old,'CR Output Schedule To File',args)
    except Exception as exc:
        with pytest.raises(type(exc),match=str(exc)):asyncio.run(call(service,'CR Output Schedule To File',args))
        assert service.writes==0;return
    async def run():
        assert await call(service,'CR Output Schedule To File',args)==expected==()
        payload=json.loads(service.store.get('user','pack',M._key(identity(extension=extension))))['payload']
        assert payload==fs.files['user-authored\\notes.'+extension]
        load=dict(input_file_path='user-authored',file_name='notes',file_extension=extension)
        assert (await call(service,'CR Load Schedule From File',load)).result==oracle_call(old,'CR Load Schedule From File',load)
    asyncio.run(run())

@pytest.mark.parametrize('payload',['"unclosed\ninside','a,b,extra\n\n','a,"b"oops\r\n','a,\"b\"\r c,d'])
def test_csv_native_non_strict_parsing_kept(tmp_path,payload):
    fs=RecordingFS();fs.files['user-authored\\notes.csv']=payload;old=native(fs);service=LocalService(tmp_path)
    service.store.set('user','pack',M._key(identity(extension='csv')),M._encode(identity(extension='csv'),payload))
    args=dict(input_file_path='user-authored',file_name='notes',file_extension='csv')
    assert asyncio.run(call(service,'CR Load Schedule From File',args)).result==oracle_call(old,'CR Load Schedule From File',args)

@pytest.mark.parametrize('node_id',['CR Save Text To File','CR Output Schedule To File'])
@pytest.mark.parametrize('path,name',[('','notes'),('user-authored',''),('','')])
def test_native_blank_cardinality_no_broker(node_id,path,name,tmp_path):
    service=LocalService(tmp_path);fs=RecordingFS();old=native(fs)
    args=dict(output_file_path=path,file_name=name,file_extension='txt')
    args.update(multiline_text='text') if node_id=='CR Save Text To File' else args.update(schedule=[('a','b')])
    assert asyncio.run(call(service,node_id,args))==oracle_call(old,node_id,args)==()
    assert service.reads==service.writes==0

@pytest.mark.parametrize('node_id,suffix',[('CR Save Text To File','_1'),('CR Output Schedule To File','2')])
def test_source_specific_collision_naming_without_overwrite(node_id,suffix,tmp_path):
    service=LocalService(tmp_path);fs=RecordingFS();old=native(fs)
    args=dict(output_file_path='user-authored',file_name='notes',file_extension='txt')
    args.update(multiline_text='text') if node_id=='CR Save Text To File' else args.update(schedule=[('a','b')])
    async def run():
        for _ in range(3):
            expected=oracle_call(old,node_id,args);actual=await call(service,node_id,args)
            assert (actual.result if hasattr(actual,'result') else actual)==expected
        names=[json.loads(service.store.get('user','pack',key))['name'] for key in service.store.list('user','pack')]
        assert 'notes' in names and 'notes'+suffix in names
        for path,payload in fs.files.items():
            name=path.removeprefix('user-authored\\').removesuffix('.txt')
            assert json.loads(service.store.get('user','pack',M._key(identity(name))))['payload']==payload
    asyncio.run(run())

def test_two_concurrent_saves_create_distinct_records(tmp_path):
    service=LocalService(tmp_path)
    async def run():
        names=await asyncio.gather(*(M._save('user-authored','notes','txt',text,'text') for text in ('first','second')))
        assert set(names)=={'notes','notes_1'}
    with _sdk.bind_runtime(_sdk.InProcessRefResolver(),SimpleNamespace(storage=service),_sdk.InProcessOps()):asyncio.run(run())
    assert {json.loads(service.store.get('user','pack',key))['payload'] for key in service.store.list('user','pack')}=={'first','second'}

@pytest.mark.parametrize('conflicts',[1,31,32])
def test_cas_retry_bound(tmp_path,conflicts):
    service=LocalService(tmp_path);service.conflicts=conflicts
    async def run():
        if conflicts==32:
            with pytest.raises(RuntimeError,match='32 CAS'):await M._save('user-authored','notes','txt','text','text')
            assert service.store.list('user','pack')==[]
        else:assert await M._save('user-authored','notes','txt','text','text')=='notes'
    with _sdk.bind_runtime(_sdk.InProcessRefResolver(),SimpleNamespace(storage=service),_sdk.InProcessOps()):asyncio.run(run())
    assert service.writes==min(conflicts+1,32)

@pytest.mark.parametrize('payload',['not json','{}','{"v":1,"v":1}',M._encode(identity(name='forged'),'bad'),'x'*65537])
@pytest.mark.parametrize('node_id',['CR Save Text To File','CR Load Text List','CR Load Schedule From File'])
def test_corrupt_identity_not_overwritten_or_skipped(tmp_path,payload,node_id):
    service=LocalService(tmp_path);key=M._key(identity());service.store.set('user','pack',key,payload)
    args=dict(file_name='notes',file_extension='txt')
    args.update(output_file_path='user-authored',multiline_text='new') if node_id=='CR Save Text To File' else args.update(input_file_path='user-authored')
    before=service.store.read('user','pack',key)
    with pytest.raises(ValueError,match='Corrupt'):asyncio.run(call(service,node_id,args))
    assert service.store.read('user','pack',key)==before and service.writes==0

def test_quota_workload_and_missing_not_reset(tmp_path,monkeypatch):
    service=LocalService(tmp_path);args=dict(multiline_text='x'*65536,output_file_path='user-authored',file_name='notes',file_extension='txt')
    with pytest.raises(ValueError,match='64KiB'):asyncio.run(call(service,'CR Save Text To File',args))
    assert service.writes==0
    monkeypatch.setattr(storage,'MAX_TOTAL_BYTES',1);args['multiline_text']='valid'
    with pytest.raises(ValueError,match='quota'):asyncio.run(call(service,'CR Save Text To File',args))
    assert service.store.list('user','pack')==[]
    with pytest.raises(FileNotFoundError,match='legacy host paths'):asyncio.run(call(service,'CR Load Text List',dict(input_file_path='user-authored',file_name='notes',file_extension='txt')))

def test_collision_bound_preserves_all_existing_artifacts(tmp_path):
    service=LocalService(tmp_path)
    for index in range(256):
        item=identity('notes' if index==0 else 'notes_'+str(index))
        service.store.set('user','pack',M._key(item),M._encode(item,'preserve-'+str(index)))
    before={key:service.store.get('user','pack',key) for key in service.store.list('user','pack')}
    async def run():
        with pytest.raises(RuntimeError,match='256 collision'):await M._save('user-authored','notes','txt','new','text')
    with _sdk.bind_runtime(_sdk.InProcessRefResolver(),SimpleNamespace(storage=service),_sdk.InProcessOps()):asyncio.run(run())
    assert service.reads==256 and service.writes==0
    assert {key:service.store.get('user','pack',key) for key in service.store.list('user','pack')}==before

def test_oversized_label_name_and_opaque_path_do_not_grant_os_access(tmp_path,monkeypatch):
    service=LocalService(tmp_path)
    with pytest.raises(ValueError,match='label/name'):M._identity('x'*1025,'notes','txt')
    with pytest.raises(ValueError,match='label/name'):M._identity('label','x'*513,'txt')
    # The coordinator-approved absolute-looking user label is only hashed data, no open/exists.
    import builtins
    original=builtins.open
    def deny_absolute_pack_path(path,*args,**kwargs):
        if isinstance(path,str) and path.startswith('/not-a-real-host-directory'):raise AssertionError('No OS lookup authority')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(builtins,'open',deny_absolute_pack_path)
    args=dict(multiline_text='body',output_file_path='/not-a-real-host-directory',file_name='notes',file_extension='txt')
    asyncio.run(call(service,'CR Save Text To File',args))
    record=service.store.get('user','pack',M._key(identity(label='/not-a-real-host-directory')))
    assert json.loads(record)['payload']=='body'

@pytest.mark.parametrize('node_id',list(LEDGER))
def test_exact_schema_list_flags_and_storage_only(node_id):
    row=LEDGER[node_id];cls=NEW.NODE_CLASS_MAPPINGS[node_id];schema=cls.GET_SCHEMA()
    assert cls.SDK_REFS is True and cls.SDK_PERMISSIONS==('storage',)
    assert schema.node_id==node_id and schema.display_name==row['display_name'] and schema.category==row['category'] and schema.is_output_node==row['is_output_node']
    assert [o.io_type for o in schema.outputs]==row['return_types'] and [o.display_name for o in schema.outputs]==row['return_names'] and [o.is_output_list for o in schema.outputs]==row['output_is_list']
    flat={key:spec for items in row['source_inputs'].values() for key,spec in items.items()}
    assert [i.id for i in schema.inputs]==list(flat)
    for inp in schema.inputs:
        src=flat[inp.id]
        if isinstance(src[0],list):assert inp.options==src[0]
        else:assert inp.io_type==src[0]
        for key,value in (src[1] if len(src)>1 else {}).items():assert inp.as_dict()[key]==value

def test_four_registered_nodes_actual_guest_outer_fresh_local_continuity_isolation_and_denial(tmp_path,monkeypatch):
    import execution
    backing=tmp_path/'backing';monkeypatch.setattr(storage,'_STORAGE',storage.PackStorage(backing))
    async def dispatch(node_id,args,tenant='user-a',pack='ned-text-artifacts',caps=('storage',)):
        session=await GuestSession(pack,tenant=tenant,guest_runtime_root=V2).start();previous=_sdk.providers.execution_backend
        class Backend:
            async def dispatch(self,plan,local_call,runtime):return await session.execute(plan,runtime,capabilities=caps,tenant=tenant)
        _sdk.providers.register_execution_backend(Backend())
        try:
            cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA()
            outputs=await execution._async_map_node_over_list(prompt_id='new-render',unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
            return outputs[0].result if hasattr(outputs[0],'result') else outputs[0],session.last_guest_pid
        finally:await session.kill();_sdk.providers.register_execution_backend(previous)
    async def run():
        text='  a,b  \n"quote"\n🙂';save=dict(multiline_text=text,output_file_path='/opaque/user/label',file_name='notes',file_extension='csv')
        fs=RecordingFS();old=native(fs);expected=oracle_call(old,'CR Save Text To File',save)
        saved,p1=await dispatch('CR Save Text To File',save);assert saved==expected
        monkeypatch.setattr(storage,'_STORAGE',storage.PackStorage(backing))
        load=dict(input_file_path='/opaque/user/label',file_name='notes',file_extension='csv')
        read,p2=await dispatch('CR Load Text List',load);assert read==oracle_call(old,'CR Load Text List',load) and p1!=p2
        for changes in ({'tenant':'user-b'},{'pack':'other-pack'}):
            with pytest.raises(Exception,match='not found'):await dispatch('CR Load Text List',load,**changes)
        schedule=[('a','0, first'),('b','1, second')];out=dict(output_file_path='schedule-label',file_name='curve',file_extension='txt',schedule=schedule)
        assert oracle_call(old,'CR Output Schedule To File',out)==()
        _,p3=await dispatch('CR Output Schedule To File',out)
        monkeypatch.setattr(storage,'_STORAGE',storage.PackStorage(backing))
        inp=dict(input_file_path='schedule-label',file_name='curve',file_extension='txt')
        restored,p4=await dispatch('CR Load Schedule From File',inp)
        assert restored==oracle_call(old,'CR Load Schedule From File',inp) and p3!=p4
        for node_id,args in [('CR Save Text To File',save),('CR Load Text List',load),('CR Output Schedule To File',out),('CR Load Schedule From File',inp)]:
            with pytest.raises(Exception,match='storage'):await dispatch(node_id,args,caps=())
    asyncio.run(run())
