"""Exact bounded CPU Matplotlib controls and real confined dispatch; no StyleBars claim."""
import ast
import asyncio
import copy
import importlib.util
import io as buffers
import json
import os
from pathlib import Path
import sys

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import RegularPolygon
import numpy as np
from PIL import Image
import pytest
import torch

sys.dont_write_bytecode=True;sys.argv=['ned-comfyroll-matplot','--cpu']
CORE=Path(os.environ['COMFY_CORE_ROOT']);sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.transport import wire
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
spec=importlib.util.spec_from_file_location('ned_comfyroll_matplot_pack',V2/'__init__.py',submodule_search_locations=[str(V2)])
NEW=importlib.util.module_from_spec(spec);sys.modules[spec.name]=NEW;spec.loader.exec_module(NEW)
LEDGER=json.loads((V2/'matplot-draft-ledger.json').read_text())
icons=ast.literal_eval(ast.parse((PACK/'categories.py').read_text()).body[0].value)
tree=ast.parse((PACK/'nodes/nodes_graphics_matplot.py').read_text())
constants={n.targets[0].id:ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('color_mapping','COLORS','STYLES')}
ns={'torch':torch,'np':np,'icons':icons,'Image':Image,'plt':plt,'io':buffers,'RegularPolygon':RegularPolygon,**constants}
helpers=[copy.deepcopy(n) for n in tree.body if isinstance(n,ast.FunctionDef)]
exec(compile(ast.Module(body=helpers,type_ignores=[]),'pinned-matplot-helpers','exec'),ns)
OLD={}
for node_id,row in LEDGER.items():
    scope=dict(ns);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==row['class'])
    exec(compile(ast.Module(body=[copy.deepcopy(cls)],type_ignores=[]),str(PACK/'nodes/nodes_graphics_matplot.py'),'exec'),scope)
    OLD[node_id]=scope[row['class']]

def args_for(node_id,**changes):
    args={}
    for group,items in LEDGER[node_id]['source_inputs'].items():
        for name,spec in items.items():
            opts=spec[1] if len(spec)>1 else {}
            args[name]=opts.get('default',spec[0][0] if isinstance(spec[0],list) else None)
    args.update(width=61,height=47)
    for key in ('color_1','start_color','line_color','face_color'):
        if key in args:args[key]='red'
    for key in ('color_2','end_color','background_color'):
        if key in args:args[key]='blue'
    args.update(changes);return args

def exact(actual,expected):
    assert len(actual)==len(expected)
    for a,b in zip(actual,expected):
        if isinstance(b,torch.Tensor):assert a.shape==b.shape and a.dtype==b.dtype and torch.equal(a,b)
        else:assert type(a) is type(b) and a==b

def oracle(node_id,args):
    before=set(plt.get_fignums())
    try:
        obj=OLD[node_id]();return getattr(obj,obj.FUNCTION)(**args)
    finally:
        for figure in set(plt.get_fignums())-before:plt.close(figure)

def outcome(fn):
    try:
        value=fn();return 'value',value.result if hasattr(value,'result') else value
    except Exception as exc:return 'error',type(exc),str(exc)

def parity(node_id,args):
    actual=outcome(lambda:NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args));expected=outcome(lambda:oracle(node_id,args))
    assert actual[0]==expected[0],(actual if actual[0]=='error' else actual[0],expected if expected[0]=='error' else expected[0])
    if actual[0]=='error':assert actual[1:]==expected[1:]
    else:exact(actual[1],expected[1])

@pytest.mark.parametrize('node_id',list(LEDGER))
@pytest.mark.parametrize('dimensions',[(61,47),(97,73),(32,32)])
@pytest.mark.parametrize('colors',['brown','darkgray','custom'])
def test_all_eight_canvas_geometry_source_color_mapping_and_literal_hex_exact(node_id,dimensions,colors):
    args=args_for(node_id,width=dimensions[0],height=dimensions[1])
    for key in ('color_1','start_color','line_color','face_color'):
        if key in args:args[key]=colors
    for key in ('color1_hex','start_color_hex','line_color_hex','face_color_hex'):
        if key in args:args[key]='#d12173'
    parity(node_id,args)

@pytest.mark.parametrize('style',constants['STYLES'])
@pytest.mark.parametrize('reverse',['No','Yes'])
def test_halftone_every_pinned_colormap_and_reverse_exact(style,reverse):
    parity('CR Halftone Grid',args_for('CR Halftone Grid',dot_style=style,reverse_dot_style=reverse,dot_frequency=4,x_pos=.3,y_pos=.8))

@pytest.mark.parametrize('orientation',['vertical','horizontal','diagonal','alt_diagonal'])
@pytest.mark.parametrize('frequency',[0,1,9])
@pytest.mark.parametrize('offset',[0,.3,-.25])
def test_bars_orientation_frequency_offset_and_native_zero_division(orientation,frequency,offset):
    parity('CR Color Bars',args_for('CR Color Bars',orientation=orientation,bar_frequency=frequency,offset=offset))

@pytest.mark.parametrize('orientation',['horizontal','vertical'])
@pytest.mark.parametrize('distance',[0,.2,1,2,-.5])
@pytest.mark.parametrize('transition',[0,.3,1])
def test_gradient_interpolation_distance_zero_native_and_transition_exact(orientation,distance,transition):
    parity('CR Color Gradient',args_for('CR Color Gradient',orientation=orientation,gradient_distance=distance,linear_transition=transition))

@pytest.mark.parametrize('distance',[0,.2,1,-.5])
@pytest.mark.parametrize('center',[(0,0),(.5,.5),(.1,.8),(1,1)])
def test_radial_distance_center_and_native_nonfinite_intermediate_exact(distance,center):
    with np.errstate(all='ignore'):
        parity('CR Radial Gradient',args_for('CR Radial Gradient',gradient_distance=distance,radial_center_x=center[0],radial_center_y=center[1]))

@pytest.mark.parametrize('mode',['regular','stepped'])
@pytest.mark.parametrize('frequency',[0,1,4,-2])
@pytest.mark.parametrize('step',[0,2,3])
def test_checker_modes_step_grid_and_native_zero_frequency(mode,frequency,step):
    parity('CR Checker Pattern',args_for('CR Checker Pattern',mode=mode,grid_frequency=frequency,step=step))

@pytest.mark.parametrize('mode',['hexagons','triangles'])
@pytest.mark.parametrize('grid',[(2,3),(0,0),(-1,2),(7,4)])
@pytest.mark.parametrize('stroke',[0,3])
def test_polygon_vertices_grid_order_edge_width_and_native_zero_column(mode,grid,stroke):
    parity('CR Polygons',args_for('CR Polygons',mode=mode,rows=grid[0],columns=grid[1],line_width=stroke))

@pytest.mark.parametrize('count',[0,1,11])
@pytest.mark.parametrize('rotation',[0,37,720])
@pytest.mark.parametrize('center',[(0,0),(11,17)])
def test_starburst_lines_pinned_rotation_center_formula_and_native_count(count,rotation,center):
    parity('CR Starburst Lines',args_for('CR Starburst Lines',num_lines=count,rotation=rotation,center_x=center[0],center_y=center[1],line_width=2))

@pytest.mark.parametrize('count',[0,1,11])
@pytest.mark.parametrize('rotation',[0,37,720])
@pytest.mark.parametrize('bbox',[0,.7,2])
def test_starburst_colors_alternation_bbox_rotation_and_zero_loops(count,rotation,bbox):
    parity('CR Starburst Colors',args_for('CR Starburst Colors',num_triangles=count,rotation=rotation,bbox_factor=bbox,center_x=7,center_y=13))

@pytest.mark.parametrize('node_id',list(LEDGER))
@pytest.mark.parametrize('dimensions',[(0,47),(-1,47),(61,0),(1,1)])
def test_native_canvas_failures_not_minimum_clamped(node_id,dimensions):
    with np.errstate(all='ignore'):
        parity(node_id,args_for(node_id,width=dimensions[0],height=dimensions[1]))

@pytest.mark.parametrize('node_id',list(LEDGER))
def test_no_owned_figure_leak_success_failure_and_unrelated_figure_preserved(node_id):
    fig,ax=plt.subplots();ax.set_title('unrelated')
    before=set(plt.get_fignums())
    try:
        for changes in ({},{'width':-1},{'width':0}):
            outcome(lambda:NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args_for(node_id,**changes)))
            assert set(plt.get_fignums())==before and ax.get_title()=='unrelated'
    finally:plt.close(fig)

@pytest.mark.parametrize('node_id',list(LEDGER))
def test_exact_schema_class_metadata_literal_options_and_workflow_reconstruction(node_id):
    row=LEDGER[node_id];cls=NEW.NODE_CLASS_MAPPINGS[node_id];schema=cls.GET_SCHEMA()
    assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS==('raw',)
    assert schema.node_id==node_id and schema.display_name==row['display_name'] and schema.category==row['category']
    assert [o.io_type for o in schema.outputs]==row['return_types'] and [o.display_name for o in schema.outputs]==row['return_names']
    flat={k:(group,value) for group,items in row['source_inputs'].items() for k,value in items.items()}
    assert [i.id for i in schema.inputs]==list(flat)
    assert json.loads(json.dumps(OLD[node_id].INPUT_TYPES()))==row['source_inputs']
    for inp in schema.inputs:
        group,source=flat[inp.id];assert inp.optional==(group=='optional')
        if isinstance(source[0],list):assert inp.options==source[0]
        else:assert inp.io_type==source[0]
        for k,value in (source[1] if len(source)>1 else {}).items():assert inp.as_dict()[k]==value
    args=args_for(node_id);restored=json.loads(json.dumps(args))
    exact(NEW.NODE_CLASS_MAPPINGS[node_id].execute(**restored).result,oracle(node_id,args))
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))
    assert 'CR Style Bars' not in LEDGER and matplotlib.__version__=='3.11.1'

@pytest.mark.parametrize('node_id',list(LEDGER))
def test_workload_preflight_before_plot_numpy_allocation_or_png_io(monkeypatch,node_id):
    def deny(*args,**kwargs):raise AssertionError('render/allocation before preflight')
    monkeypatch.setattr(NEW.secure_matplot.plt,'subplots',deny)
    cases=[{'width':4096,'height':4096},{'width':4097,'height':1}]
    if node_id=='CR Halftone Grid':cases.append({'dot_frequency':201})
    if node_id=='CR Polygons':cases.append({'rows':512,'columns':512})
    if node_id=='CR Starburst Lines':cases.append({'num_lines':501})
    if node_id=='CR Starburst Colors':cases.append({'num_triangles':513})
    for changes in cases:
        with pytest.raises(ValueError,match='bound'):NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args_for(node_id,**changes))

def test_all_eight_registered_two_fresh_guest_pids_exact_outer_and_raw_denial():
    import execution
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for render in range(2):
                session=await GuestSession('ned-comfyroll-matplot-'+str(render),guest_runtime_root=V2).start()
                class Backend:
                    caps=('raw',)
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=self.caps)
                backend=Backend();_sdk.providers.register_execution_backend(backend)
                try:
                    for node_id in LEDGER:
                        cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA()
                        for dimensions in ((61,47),(512,512)):
                            args=args_for(node_id,width=dimensions[0],height=dimensions[1])
                            result=await execution._async_map_node_over_list(prompt_id='matplot',unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                            exact(result[0].result,oracle(node_id,args))
                        backend.caps=()
                        with pytest.raises(wire.WireError,match='raw'):
                            await execution._async_map_node_over_list(prompt_id='matplot-denial',unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args_for(node_id).items()},func=cls.FUNCTION,v3_data=None)
                        backend.caps=('raw',)
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(previous)
        assert pids[0]!=pids[1]
    asyncio.run(run())

def test_production_dispatch_all_eight_matplot_entrypoints(monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        previous=_sdk.providers.execution_backend;session=await GuestSession('ned-comfyroll-production-matplot',guest_runtime_root=V2).start();backend=CloudExecutionBackend()
        monkeypatch.setattr(backend,'_is_sandbox',lambda plan:True)
        async def session_for(*args,**kwargs):return session
        monkeypatch.setattr(backend.guests,'session_for',session_for);_sdk.providers.register_execution_backend(backend)
        try:
            for node_id in LEDGER:
                args=args_for(node_id);cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA()
                result=await execution._async_map_node_over_list(prompt_id='production-matplot',unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                result=await execution.resolve_map_node_over_list_results(result);exact(result[0].result,oracle(node_id,args))
            assert session.last_guest_pid not in (None,os.getpid())
        finally:await session.kill();await backend.shutdown();_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())

