"""StyleBars successor only: exact small oracles, bounded512 usability, no199 promotion."""
import asyncio
import hashlib
import weakref
import matplotlib
import matplotlib.image as mimage
import numpy as np
import pytest
import torch
from test_ned_comfyroll_style_bars import oracle,args,same,styles,ns
from test_ned_comfyroll_cycle_models import NEW,V2,PACK,_sdk,GuestSession,wire
sb=NEW.secure_style_bars
strips=__import__(sb.__package__+".secure_style_bars_strips",fromlist=["*"])
ID="CR Style Bars"

@pytest.mark.parametrize("style",styles)
@pytest.mark.parametrize("orientation",["vertical","horizontal"])
@pytest.mark.parametrize("frequency",[1,5,200])
def test_all82_styles_all_frequencies_axes_source_sized_exact_png(style,orientation,frequency,monkeypatch):
    calls=[];native=sb.add_artist
    def observed(*a,**k):calls.append(1);return native(*a,**k)
    monkeypatch.setattr(sb,"add_artist",observed)
    mode=("color bars","sin wave","gradient bars")[(styles.index(style)+(1,5,200).index(frequency))%3]
    a=args(width=19,height=13,bar_style=style,orientation=orientation,mode=mode,bar_frequency=frequency)
    same(NEW.NODE_CLASS_MAPPINGS[ID].execute(**a).result,oracle(a))
    assert len(calls)==1

@pytest.mark.parametrize("mode",["color bars","sin wave","gradient bars"])
@pytest.mark.parametrize("orientation",["vertical","horizontal"])
@pytest.mark.parametrize("frequency",[-5,.5,200])
@pytest.mark.parametrize("size",[(2,2),(2,63),(63,2),(11,7),(31,23),(64,80)])
def test_rectangular_edge_controlled_native_draws_and_floor_math_exact(mode,orientation,frequency,size):
    a=args(width=size[0],height=size[1],mode=mode,orientation=orientation,bar_frequency=frequency,bar_style="Accent")
    same(NEW.NODE_CLASS_MAPPINGS[ID].execute(**a).result,oracle(a))

@pytest.mark.parametrize("changes",[
    {"width":0},{"height":0},{"width":-1},{"height":-1},{"width":1},{"height":1},
    {"mode":"unknown"},{"orientation":"unknown"},{"bar_style":"invalid"},{"bar_frequency":0}
])
def test_unsupported_small_literal_branch_and_native_errors_preserved(changes):
    a=args(width=11,height=7,**changes) if not ({"width","height"}&changes.keys()) else args(**dict({"width":11,"height":7},**changes))
    try:expected=("value",oracle(a))
    except Exception as e:expected=("error",type(e),str(e))
    try:actual=("value",NEW.NODE_CLASS_MAPPINGS[ID].execute(**a).result)
    except Exception as e:actual=("error",type(e),str(e))
    assert actual[0]==expected[0]
    if expected[0]=="error":assert actual[1:]==expected[1:]
    else:same(actual[1],expected[1])

@pytest.mark.parametrize("mode",["color bars","sin wave","gradient bars"])
@pytest.mark.parametrize("orientation",["vertical","horizontal"])
def test_default512_usability_without_original_grid_not_pristine512_equivalence(mode,orientation,monkeypatch):
    def no_original_grid(*a,**k):raise AssertionError("Never allocate original512 grid")
    monkeypatch.setattr(np,"meshgrid",no_original_grid)
    a=args(width=512,height=512,mode=mode,orientation=orientation,bar_style="Accent")
    plan=sb._preflight(a)
    assert plan["projected_bytes"]<=128*1024*1024
    result=NEW.NODE_CLASS_MAPPINGS[ID].execute(**a).result
    assert len(result)==2 and result[0].shape==(1,512,512,3)
    assert result[0].dtype is torch.float32 and torch.isfinite(result[0]).all()
    assert result[1].endswith("#cr-style-bars")

@pytest.mark.parametrize("size",[(4096,64,"vertical"),(64,4096,"horizontal"),(1024,1024,"vertical"),(4096,4096,"vertical")])
def test_simultaneous_ownership_refusal_before_axis_figure_or_grid(size,monkeypatch):
    calls=[]
    def denied(*a,**k):calls.append(a);raise AssertionError("Allocated before rejection")
    monkeypatch.setattr(np,"linspace",denied);monkeypatch.setattr(sb.plt,"subplots",denied)
    monkeypatch.setattr(sb,"_make_figure",denied)
    with pytest.raises(ValueError,match="bound"):
        NEW.NODE_CLASS_MAPPINGS[ID].execute(**args(width=size[0],height=size[1],orientation=size[2]))
    assert not calls

def test_live_strip_deleted_before_next_tile_no_global_resampler_replacement(monkeypatch):
    tile=np.tile;previous=[None];count=[0];native=mimage._resample
    def record(*a,**k):
        if previous[0] is not None:assert previous[0]() is None
        result=tile(*a,**k);previous[0]=weakref.ref(result);count[0]+=1;return result
    monkeypatch.setattr(np,"tile",record)
    result=NEW.NODE_CLASS_MAPPINGS[ID].execute(**args(width=64,height=80)).result
    assert result[0].shape==(1,80,64,3) and count[0]>=80
    assert previous[0]() is None and mimage._resample is native

def test_owned_canvas_renderer_disposal_ambient_backend_rc_and_other_figure_untouched(monkeypatch):
    backend=matplotlib.get_backend();rc=dict(matplotlib.rcParams)
    unrelated=sb.plt.figure();before=set(sb.plt.get_fignums())
    canvases=[];native=sb._make_figure
    def capture(*a,**k):
        fig,ax=native(*a,**k);canvases.append(fig.canvas);return fig,ax
    monkeypatch.setattr(sb,"_make_figure",capture)
    try:
        out=NEW.NODE_CLASS_MAPPINGS[ID].execute(**args(width=512,height=512)).result
        assert out[0].shape==(1,512,512,3) and len(canvases)==1
        assert canvases[0].figure is None and canvases[0].renderer is None
        assert set(sb.plt.get_fignums())==before and matplotlib.get_backend()==backend
        assert dict(matplotlib.rcParams)==rc
    finally:sb.plt.close(unrelated)

@pytest.mark.parametrize("key,value",[
    ("image.origin","lower"),("image.interpolation","nearest"),
    ("image.interpolation_stage","data"),("image.resample",False),
    ("figure.dpi",80),("savefig.dpi",80),("savefig.bbox","tight")
])
def test_nonadmitted_native_settings_small_literal_exact_large_fail_closed(key,value):
    with matplotlib.rc_context({key:value}):
        a=args(width=11,height=7)
        assert sb._preflight(a) is None
        same(NEW.NODE_CLASS_MAPPINGS[ID].execute(**a).result,oracle(a))
        with pytest.raises(ValueError,match="native strip contract unavailable"):
            NEW.NODE_CLASS_MAPPINGS[ID].execute(**args(width=512,height=512))

def test_native_version_guard_does_not_lift_cubic_limit(monkeypatch):
    monkeypatch.setattr(matplotlib,"__version__","different")
    assert sb._preflight(args(width=11,height=7)) is None
    with pytest.raises(ValueError,match="native strip contract unavailable"):
        sb._preflight(args(width=512,height=512))

def test_native_alpha_contract_refuses_before_result_and_strip_allocation(monkeypatch):
    values=np.linspace(0,1,64);plan=strips.allocation_plan(64,64,True)
    fig,ax=sb._make_figure(64,64)
    try:
        artist=strips.add_artist(ax,values,True,plan,"Accent");artist.set_alpha(.5)
        def denied(*a,**k):raise AssertionError("Before contract admission")
        monkeypatch.setattr(np,"zeros",denied);monkeypatch.setattr(np,"tile",denied)
        with pytest.raises(ValueError,match="alpha contract"):
            artist.make_image(fig.canvas.get_renderer())
    finally:sb._dispose_figure(fig)

def test_native_failure_restores_only_private_figures_and_next_execution(monkeypatch):
    unrelated=sb.plt.figure();before=set(sb.plt.get_fignums())
    native=mimage._resample;calls=[]
    def fail(*a,**k):calls.append(1);raise MemoryError("native-render-failure")
    try:
        with monkeypatch.context() as m:
            m.setattr(mimage,"_resample",fail)
            with pytest.raises(MemoryError,match="native-render-failure"):
                NEW.NODE_CLASS_MAPPINGS[ID].execute(**args(width=64,height=80))
        assert calls and set(sb.plt.get_fignums())==before and mimage._resample is native
        same(NEW.NODE_CLASS_MAPPINGS[ID].execute(**args()).result,oracle(args()))
        assert set(sb.plt.get_fignums())==before
    finally:sb.plt.close(unrelated)

def test_real_required_fresh_guests_outer_small_exact512_cap_denial_and_recovery(monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        async def execute(a):
            cls=NEW.NODE_CLASS_MAPPINGS[ID];cls.GET_SCHEMA()
            r=await execution._async_map_node_over_list(prompt_id="stylebars-successor",unique_id="n",obj=cls,input_data_all={k:[v] for k,v in a.items()},func=cls.FUNCTION,v3_data=None)
            r=await execution.resolve_map_node_over_list_results(r);return r[0].result
        try:
            for generation in range(2):
                session=await GuestSession("ned-stylebars-successor-"+str(generation),guest_runtime_root=V2).start()
                assert session.sandbox_kind=="seatbelt"
                caps={"value":("raw",)}
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=caps["value"])
                _sdk.providers.register_execution_backend(Backend())
                try:
                    for mode in ("color bars","sin wave","gradient bars"):
                        for orientation in ("vertical","horizontal"):
                            a=args(width=31,height=23,mode=mode,orientation=orientation,bar_style="Accent",bar_frequency=200)
                            same(await execute(a),oracle(a))
                            out=await execute(dict(a,width=512,height=512,bar_frequency=5))
                            assert out[0].shape==(1,512,512,3) and out[0].dtype is torch.float32 and torch.isfinite(out[0]).all()
                    with pytest.raises(wire.WireError,match="bound"):
                        await execute(args(width=4096,height=64))
                    # Admission failure leaves dispatch usable.
                    same(await execute(args(width=11,height=7)),oracle(args(width=11,height=7)))
                    caps["value"]=()
                    with pytest.raises(wire.WireError,match="raw|permission|capability"):
                        await execute(args(width=512,height=512))
                    caps["value"]=("raw",)
                    same(await execute(args(width=11,height=7)),oracle(args(width=11,height=7)))
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
            assert pids[0]!=pids[1]
            session=await GuestSession("ned-stylebars-successor-production",guest_runtime_root=V2).start()
            assert session.sandbox_kind=="seatbelt"
            backend=CloudExecutionBackend()
            monkeypatch.setattr(backend,"_is_sandbox",lambda plan:True)
            async def session_for(*a,**k):return session
            monkeypatch.setattr(backend.guests,"session_for",session_for)
            _sdk.providers.register_execution_backend(backend)
            try:
                same(await execute(args(width=31,height=23)),oracle(args(width=31,height=23)))
                out=await execute(args(width=512,height=512))
                assert out[0].shape==(1,512,512,3) and out[0].dtype is torch.float32
            finally:await session.kill();await backend.shutdown()
        finally:_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
