"""Historical native controls plus explicitly authorized strip successor scope."""
import ast,asyncio,copy,hashlib,io as buffers,json
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
import pytest,torch
from test_ned_comfyroll_cycle_models import NEW,V2,PACK,_sdk,GuestSession,wire
ID='CR Style Bars'
LEDGER=json.loads((V2/'style-bars-draft-ledger.json').read_text())[ID]
TREE=ast.parse((PACK/'nodes/nodes_graphics_matplot.py').read_text())
styles=next(ast.literal_eval(n.value) for n in TREE.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='STYLES')
ns={'torch':torch,'np':np,'Image':Image,'plt':plt,'io':buffers,'STYLES':styles,'icons':ast.literal_eval(ast.parse((PACK/'categories.py').read_text()).body[0].value)}
body=[copy.deepcopy(n) for n in TREE.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in ('CR_StyleBars','pil2tensor')]
exec(compile(ast.Module(body=body,type_ignores=[]),'pinned-original-cubic-stylebars','exec'),ns)
def args(**changes):
    a=dict(mode='color bars',width=64,height=64,bar_style='viridis',orientation='vertical',bar_frequency=5);a.update(changes);return a
def oracle(a):
    before=set(plt.get_fignums())
    try:return ns['CR_StyleBars']().draw(**a)
    finally:
        for n in set(plt.get_fignums())-before:plt.close(n)
def same(a,b):
    assert len(a)==len(b)==2 and a[1]==b[1]
    assert a[0].shape==b[0].shape and a[0].dtype is b[0].dtype is torch.float32 and torch.equal(a[0],b[0])
@pytest.mark.parametrize('mode',['color bars','sin wave','gradient bars'])
@pytest.mark.parametrize('orientation',['vertical','horizontal'])
@pytest.mark.parametrize('size',[(64,64),(80,64),(64,80)])
def test_original_cubic_small_admitted_grids_exact_final_png_pixels(mode,orientation,size):
    a=args(mode=mode,orientation=orientation,width=size[0],height=size[1])
    same(NEW.NODE_CLASS_MAPPINGS[ID].execute(**a).result,oracle(a))
@pytest.mark.parametrize('style',styles)
@pytest.mark.parametrize('orientation',['vertical','horizontal'])
def test_each_original_cmap_and_axis_on_exact_original_colors_not_failed_1d_repair(style,orientation):
    a=args(width=31,height=23,bar_style=style,orientation=orientation,mode='gradient bars',bar_frequency=7)
    same(NEW.NODE_CLASS_MAPPINGS[ID].execute(**a).result,oracle(a))
@pytest.mark.parametrize('changes',[{'width':0},{'height':0},{'width':-1},{'mode':'unknown'},{'orientation':'unknown'},{'bar_style':'no such cmap'},{'bar_frequency':0}])
def test_original_native_errors_clean_only_owned_figures(changes):
    a=args(**changes);before=set(plt.get_fignums())
    try:expected=('value',oracle(a))
    except Exception as e:expected=('error',type(e),str(e))
    try:actual=('value',NEW.NODE_CLASS_MAPPINGS[ID].execute(**a).result)
    except Exception as e:actual=('error',type(e),str(e))
    assert actual[0]==expected[0]
    if expected[0]=='error':assert actual[1:]==expected[1:]
    else:same(actual[1],expected[1])
    assert set(plt.get_fignums())==before
@pytest.mark.parametrize('orientation',['vertical','horizontal'])
def test_successor512_usability_before_any_original_cubic_grid_not_original512_equality(orientation,monkeypatch):
    calls=[]
    def denied(*a,**k):calls.append(a);raise AssertionError('No grid/materialization before workload approval')
    monkeypatch.setattr(np,'meshgrid',denied);before=set(plt.get_fignums())
    actual=NEW.NODE_CLASS_MAPPINGS[ID].execute(**args(width=512,height=512,orientation=orientation)).result
    assert actual[0].shape==(1,512,512,3) and actual[0].dtype is torch.float32 and torch.isfinite(actual[0]).all()
    assert not calls and set(plt.get_fignums())==before
    # The source would allocate two1GiB grids BEFORE colors/renderer; not executed.
@pytest.mark.parametrize('orientation,shape',[('vertical',(64*64,64)),('horizontal',(64,64*64))])
def test_unsupported_version_retains_literal_source_meshgrid_shape_in_small_branch(orientation,shape,monkeypatch):
    import matplotlib
    monkeypatch.setattr(matplotlib,'__version__','unsupported')
    original=np.meshgrid;calls=[]
    def record(*a,**k):
        result=original(*a,**k);calls.append(tuple(x.shape for x in result));return result
    monkeypatch.setattr(np,'meshgrid',record)
    actual=NEW.NODE_CLASS_MAPPINGS[ID].execute(**args(orientation=orientation)).result
    assert (shape,shape) in calls and actual[0].shape==(1,64,64,3)
def test_schema_every_mode_style_default_and_exact_output_axes_unchanged():
    cls=NEW.NODE_CLASS_MAPPINGS[ID];s=cls.GET_SCHEMA()
    assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS==('raw',)
    assert s.node_id==ID and s.display_name==LEDGER['display_name'] and s.category==LEDGER['category']
    assert [i.id for i in s.inputs]==list(LEDGER['source_inputs']['required'])
    for i in s.inputs:
        spec=LEDGER['source_inputs']['required'][i.id]
        if isinstance(spec[0],list):assert i.options==spec[0]
        for key,value in (spec[1] if len(spec)>1 else {}).items():assert i.as_dict()[key]==value
    assert [o.io_type for o in s.outputs]==LEDGER['return_types'] and [o.display_name for o in s.outputs]==LEDGER['return_names']
    assert hashlib.sha256((PACK/'nodes'/LEDGER['source_file']).read_bytes()).hexdigest()==LEDGER['source_sha256']
def test_two_recreated_confined_raw_guests_outer_png_pixels_denial_and_default_bound(monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        async def execute(a):
            cls=NEW.NODE_CLASS_MAPPINGS[ID];cls.GET_SCHEMA()
            r=await execution._async_map_node_over_list(prompt_id='stylebars',unique_id='n',obj=cls,input_data_all={k:[v] for k,v in a.items()},func=cls.FUNCTION,v3_data=None)
            r=await execution.resolve_map_node_over_list_results(r);return r[0].result
        try:
            for generation in range(2):
                session=await GuestSession('ned-stylebars-'+str(generation),guest_runtime_root=V2).start();caps={'value':('raw',)}
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=caps['value'])
                _sdk.providers.register_execution_backend(Backend())
                try:
                    for mode in ('color bars','sin wave','gradient bars'):
                        for orientation in ('vertical','horizontal'):
                            a=args(width=64,height=64,mode=mode,orientation=orientation)
                            same(await execute(a),oracle(a))
                    with pytest.raises(wire.WireError,match='bound'):await execute(args(width=4096,height=64))
                    caps['value']=()
                    with pytest.raises(wire.WireError,match='raw|permission|capability'):await execute(args())
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
            assert pids[0]!=pids[1]
            session=await GuestSession('ned-stylebars-production',guest_runtime_root=V2).start();backend=CloudExecutionBackend()
            monkeypatch.setattr(backend,'_is_sandbox',lambda plan:True)
            async def session_for(*a,**k):return session
            monkeypatch.setattr(backend.guests,'session_for',session_for);_sdk.providers.register_execution_backend(backend)
            try:same(await execute(args()),oracle(args()))
            finally:await session.kill();await backend.shutdown()
        finally:_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
