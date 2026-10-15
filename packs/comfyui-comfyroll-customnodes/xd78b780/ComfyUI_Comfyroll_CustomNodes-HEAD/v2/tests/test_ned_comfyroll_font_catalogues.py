"""Names and exact slicing against pinned controls; no host font pixels/redistribution claim."""
import ast,asyncio,copy,hashlib,json,os,platform,types
from pathlib import Path
import pytest
from test_ned_comfyroll_cycle_models import NEW,V2,PACK,_sdk,GuestSession,wire,icons
import folder_paths
IDS=('CR Font File List','CR Select Font')
LEDGER=json.loads((V2/'font-catalogues-draft-ledger.json').read_text())
def source(os_module=os,platform_module=platform):
    result={}
    for id in IDS:
        row=LEDGER[id];p=PACK/'nodes'/row['source_file']
        node=next(n for n in ast.parse(p.read_text()).body if isinstance(n,ast.ClassDef) and n.name==row['class'])
        ns={'__file__':str(p),'os':os_module,'platform':platform_module,'any_type':'*','icons':icons}
        exec(compile(ast.Module(body=[copy.deepcopy(node)],type_ignores=[]),str(p),'exec'),ns)
        result[id]=ns[row['class']]
    return result
class Catalogue:
    def __init__(self,names):self.names=names;self.calls=[]
    async def font_names(self,folder='system',prefix=''):
        self.calls.append((folder,prefix));return self.names
def args(**changes):
    a=dict(source_folder='system',start_index=0,max_rows=1000,folder_path='C:\\Windows\\Fonts');a.update(changes);return a
async def migrated(id,a,assets=None):
    with _sdk.bind_runtime(_sdk.InProcessRefResolver(),types.SimpleNamespace(assets=assets or _sdk._InProcessAssets()),_sdk.InProcessOps()):
        result=NEW.NODE_CLASS_MAPPINGS[id].execute(**a)
        if hasattr(result,'__await__'):result=await result
        return result.result if hasattr(result,'result') else result
def outcome(call):
    try:return 'value',call()
    except Exception as error:return 'error',type(error),str(error)
def compare(actual,expected):
    assert actual[0]==expected[0]
    if expected[0]=='error':assert actual[1] is expected[1]
    else:
        assert actual[1]==expected[1] and type(actual[1]) is type(expected[1])
        if isinstance(expected[1],tuple):
            assert len(actual[1])==len(expected[1])
            for a,b in zip(actual[1],expected[1]):assert type(a) is type(b)
def controlled_source(names):
    # Metadata-only source fixture; no copied or parsed system fonts.
    fake=types.SimpleNamespace(environ={'SystemRoot':'/source-windows'},listdir=lambda p:list(names),path=types.SimpleNamespace(join=os.path.join,dirname=os.path.dirname,realpath=os.path.realpath,isfile=lambda p:True,exists=lambda p:True))
    return source(fake,types.SimpleNamespace(system=lambda:'Windows'))
@pytest.mark.parametrize('names',[[],['Z.ttf'],['z.ttf','A.TTF','é.ttf','AA.ttf'],['duplicate.ttf','duplicate.ttf']])
@pytest.mark.parametrize('start',[-10,0,1,2,99,0.0,.5,True])
@pytest.mark.parametrize('rows',[-2,0,1,3,1000,0.0,.5])
def test_exact_controlled_system_order_duplicate_slice_clamp_and_native_types(names,start,rows):
    a=args(start_index=start,max_rows=rows);old=controlled_source(names)[IDS[0]]();cat=Catalogue(names)
    compare(outcome(lambda:asyncio.run(migrated(IDS[0],a,cat))),outcome(lambda:old.make_list(**a)))
    assert cat.calls==[('system','')]
@pytest.mark.parametrize('source_folder',['system','from folder'])
@pytest.mark.parametrize('names',[['z.ttf','a.TTF','é.ttf'],[]])
def test_platform_and_custom_logical_prefix_adaptations_preserve_unsorted_names(source_folder,names):
    a=args(source_folder=source_folder,folder_path='authored/fonts');cat=Catalogue(names)
    compare(outcome(lambda:asyncio.run(migrated(IDS[0],a,cat))),outcome(lambda:controlled_source(names)[IDS[0]]().make_list(**a)))
    assert cat.calls==[(('system','') if source_folder=='system' else ('input','authored/fonts'))]
@pytest.mark.parametrize('folder_path',['',None])
def test_native_empty_custom_selection_none_without_broker(folder_path):
    cat=Catalogue(['would-not-load.ttf']);a=args(source_folder='from folder',folder_path=folder_path)
    compare(outcome(lambda:asyncio.run(migrated(IDS[0],a,cat))),outcome(lambda:source()[IDS[0]]().make_list(**a)))
    assert cat.calls==[]
def test_native_systemroot_typeerror_and_missing_filesystem_control_explicit_adaptation(monkeypatch):
    monkeypatch.delenv('SystemRoot',raising=False)
    with pytest.raises(TypeError):source()[IDS[0]]().make_list(**args())
    assert asyncio.run(migrated(IDS[0],args(),Catalogue([])))[0]==[]
    old=source()[IDS[0]]().make_list(**args(source_folder='from folder',folder_path='/ned-nonexistent-font-catalogue'))
    assert old is None
    result=asyncio.run(migrated(IDS[0],args(source_folder='from folder',folder_path='missing'),Catalogue([])))
    assert result[0]==[] # Missing managed catalogue differs from source nonexistent filesystem None.
def test_native_unknown_source_unbound_failure_has_no_catalogue_fallback():
    cat=Catalogue([]);a=args(source_folder='unsupported')
    compare(outcome(lambda:asyncio.run(migrated(IDS[0],a,cat))),outcome(lambda:source()[IDS[0]]().make_list(**a)));assert cat.calls==[]
@pytest.mark.parametrize('start,rows',[(0,1000),(-1,2),(1,3),(9,99),(99,0),(0,-1),(0,.5)])
def test_all_ten_bundled_bytes_native_iteration_order_and_slices_are_distinct_from_system(start,rows):
    a=args(source_folder='Comfyroll',start_index=start,max_rows=rows)
    class Deny:
        def __getattr__(self,key):raise AssertionError('Bundled branch has no broker operation')
    compare(outcome(lambda:asyncio.run(migrated(IDS[0],a,Deny()))),outcome(lambda:source()[IDS[0]]().make_list(**a)))
    assert NEW.secure_font_catalogues._bundled()==[p.name for p in (PACK/'fonts').iterdir() if p.is_file() and p.name.lower().endswith('.ttf')]
    assert len(NEW.secure_font_catalogues._bundled())==10
    for p in (PACK/'fonts').iterdir():assert (V2/'fonts'/p.name).read_bytes()==p.read_bytes()
@pytest.mark.parametrize('value',['Arial.ttf','<img src=x onerror=alert(1)>.ttf','../pure-lexical-not-read','C:\\Fonts\\not-read.ttf','',None,3,['A.ttf','B.ttf']])
def test_selector_source_pure_passthrough_safe_literals_not_path_io(value):
    a={'font_name':value};result=asyncio.run(migrated(IDS[1],a))
    compare(('value',result),('value',source()[IDS[1]]().select_font(**a)))
    assert result[0] is value
@pytest.mark.parametrize('value',['../host','/host','C:host','a\\b','a/../b','a//b','x'*1025])
def test_custom_logical_prefix_refusal_before_broker(value):
    cat=Catalogue([])
    with pytest.raises(ValueError,match='logical|prefix'):asyncio.run(migrated(IDS[0],args(source_folder='from folder',folder_path=value),cat))
    assert cat.calls==[]
@pytest.mark.parametrize('names',[['a.ttf']*4097,tuple(['a.ttf']),['a.otf'],['../a.ttf'],['a\\b.ttf'],['/a.ttf'],['x'*252+'.ttf'],['x\n.ttf'],[None]])
def test_forged_catalogue_basenames_count_and_utf8_bounds(names):
    with pytest.raises(ValueError,match='catalogue'):asyncio.run(migrated(IDS[0],args(),Catalogue(names)))
def test_direct_oversized_text_scalar_bounds_before_catalogue():
    cat=Catalogue([])
    with pytest.raises(ValueError,match='bound'):asyncio.run(migrated(IDS[0],args(start_index=1<<5000),cat))
    with pytest.raises(ValueError,match='bound'):asyncio.run(migrated(IDS[1],{'font_name':'x'*262145}))
    assert cat.calls==[]
def test_exact_schema_outputs_list_axis_names_original_default_remote_and_resource_hashes():
    old=source()
    for id in IDS:
        row=LEDGER[id];cls=NEW.NODE_CLASS_MAPPINGS[id];schema=cls.GET_SCHEMA()
        assert schema.node_id==id and schema.display_name==row['display_name'] and schema.category==old[id].CATEGORY
        assert cls.SDK_REFS is True and cls.SDK_PERMISSIONS==tuple(row['permissions'])
        assert [o.io_type for o in schema.outputs]==list(old[id].RETURN_TYPES)
        assert [o.display_name for o in schema.outputs]==list(old[id].RETURN_NAMES)
        assert [o.is_output_list for o in schema.outputs]==list(getattr(old[id],'OUTPUT_IS_LIST',(False,False)))
        flat={k:(group,info) for group,values in old[id].INPUT_TYPES().items() for k,info in values.items()}
        assert [i.id for i in schema.inputs]==list(flat)
        for i in schema.inputs:
            group,info=flat[i.id];assert i.optional==(group=='optional')
            if id==IDS[1]:assert i.options==[] and i.remote.route=='/secure-nodes/fonts/system' and i.remote.refresh_button is True
            else:
                if isinstance(info[0],list):assert i.options==info[0]
                else:assert i.io_type==info[0]
                for k,v in (info[1] if len(info)>1 else {}).items():assert i.as_dict()[k]==v
        assert hashlib.sha256((PACK/'nodes'/row['source_file']).read_bytes()).hexdigest()==row['source_sha256']
    assert NEW.NODE_CLASS_MAPPINGS[IDS[0]].GET_SCHEMA().inputs[-1].default=='C:\\Windows\\Fonts'
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))
def test_actual_names_only_input_system_fresh_guests_outer_axes_capabilities_and_production(tmp_path,monkeypatch):
    import execution
    from comfy_api.latest._font_catalogue import font_names
    from comfy_secure_nodes.execution import CloudExecutionBackend
    root=tmp_path/'input';album=root/'fonts';album.mkdir(parents=True)
    # Metadata-only managed fixtures: names service intentionally does not parse font bytes.
    for name in ['z.ttf','a.TTF','ignored.otf','é.ttf']:(album/name).write_bytes(b'fixture not font data')
    (album/'nested').mkdir();(album/'nested'/'hidden.ttf').write_bytes(b'not parsed')
    outside=tmp_path/'outside.ttf';outside.write_bytes(b'outside');(album/'escape.ttf').symlink_to(outside)
    monkeypatch.setattr(folder_paths,'get_input_directory',lambda:str(root))
    system=font_names('system');input_names=font_names('input','fonts')
    assert set(input_names)=={'z.ttf','a.TTF','é.ttf'} and 'escape.ttf' not in input_names
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        async def execute(id,a):
            cls=NEW.NODE_CLASS_MAPPINGS[id];cls.GET_SCHEMA()
            r=await execution._async_map_node_over_list(prompt_id='font-catalogue',unique_id='n',obj=cls,input_data_all={k:[v] for k,v in a.items()},func=cls.FUNCTION,v3_data=None)
            r=await execution.resolve_map_node_over_list_results(r);return r[0].result
        try:
            for generation in range(2):
                session=await GuestSession('ned-font-catalogues-'+str(generation),guest_runtime_root=V2).start();caps={'value':('assets',)}
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=caps['value'])
                _sdk.providers.register_execution_backend(Backend())
                try:
                    for a,names in [(args(),system),(args(source_folder='from folder',folder_path='fonts'),input_names),(args(source_folder='Comfyroll'),NEW.secure_font_catalogues._bundled()),(args(source_folder='from folder',folder_path='missing'),[])]:
                        actual=await execute(IDS[0],a);assert type(actual[0]) is list and actual[0]==names and type(actual[1]) is str
                    caps['value']=()
                    for a in [args(),args(source_folder='from folder',folder_path='fonts')]:
                        with pytest.raises(wire.WireError,match='assets'):await execute(IDS[0],a)
                    # Bundled metadata path has no host service and needs no raw authority.
                    assert (await execute(IDS[0],args(source_folder='Comfyroll')))[0]==NEW.secure_font_catalogues._bundled()
                    for value in ['Arial.ttf','<literal>.ttf','C:\\pure\\lexical.ttf','']:
                        actual=await execute(IDS[1],{'font_name':value});assert actual[0]==value and type(actual[0]) is str and type(actual[1]) is str
                    caps['value']=('assets',)
                    with pytest.raises(wire.WireError,match='logical'):await execute(IDS[0],args(source_folder='from folder',folder_path='../outside'))
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
            assert pids[0]!=pids[1]
            session=await GuestSession('ned-font-catalogue-production',guest_runtime_root=V2).start();backend=CloudExecutionBackend();monkeypatch.setattr(backend,'_is_sandbox',lambda p:True)
            async def session_for(*a,**k):return session
            monkeypatch.setattr(backend.guests,'session_for',session_for);_sdk.providers.register_execution_backend(backend)
            try:
                actual=await execute(IDS[0],args(source_folder='from folder',folder_path='fonts',start_index=1,max_rows=1));assert actual[0]==input_names[1:2] and type(actual[1]) is str
                actual=await execute(IDS[1],{'font_name':'a.TTF'});assert actual[0]=='a.TTF'
            finally:await session.kill();await backend.shutdown()
        finally:_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
