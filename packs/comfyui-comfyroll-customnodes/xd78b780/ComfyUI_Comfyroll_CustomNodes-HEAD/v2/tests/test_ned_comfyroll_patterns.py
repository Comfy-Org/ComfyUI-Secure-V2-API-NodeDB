"""Pinned controlled-draw patterns and real sampled guest outputs, with precise proof boundaries."""
import ast
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
import random
from pathlib import Path
import sys
import types

import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageEnhance,ImageFilter,ImageOps
import pytest
import torch

sys.dont_write_bytecode=True;sys.argv=['ned-comfyroll-patterns','--cpu']
CORE=Path(os.environ['COMFY_CORE_ROOT']);sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.transport import wire
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
spec=importlib.util.spec_from_file_location('ned_comfyroll_patterns_pack',V2/'__init__.py',submodule_search_locations=[str(V2)])
NEW=importlib.util.module_from_spec(spec);sys.modules[spec.name]=NEW;spec.loader.exec_module(NEW)
LEDGER=json.loads((V2/'patterns-draft-ledger.json').read_text())
icons=ast.literal_eval(ast.parse((PACK/'categories.py').read_text()).body[0].value)
config={}
for n in ast.parse((PACK/'config.py').read_text()).body:
    if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('COLORS','color_mapping','iso_sizes'):config[n.targets[0].id]=ast.literal_eval(n.value)
ns={'torch':torch,'np':np,'os':os,'icons':icons,'Image':Image,'ImageDraw':ImageDraw,'ImageFont':ImageFont,'ImageEnhance':ImageEnhance,'ImageFilter':ImageFilter,'ImageOps':ImageOps,**config}
names={'tensor2pil','pil2tensor','get_color_values','hex_to_rgb','combine_images','apply_outline_and_border','make_grid_panel'}
helpers=[copy.deepcopy(n) for n in ast.parse((PACK/'nodes/functions_graphics.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name in {'pil2tensor','get_color_values','hex_to_rgb'}]
helpers.extend(copy.deepcopy(n) for n in ast.parse((PACK/'nodes/shapes.py').read_text()).body if isinstance(n,ast.FunctionDef))
ns.update(math=__import__('math'),random=random.Random(0))
exec(compile(ast.Module(body=helpers,type_ignores=[]),'pinned-graphics-helpers','exec'),ns)
OLD={}
for node_id,row in LEDGER.items():
    source=PACK/'nodes'/row['source_file'];scope=dict(ns,__file__=str(source))
    cls=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.ClassDef) and n.name==row['class'])
    exec(compile(ast.Module(body=[copy.deepcopy(cls)],type_ignores=[]),str(source),'exec'),scope)
    OLD[node_id]=scope[row['class']]

def args_for(node_id,**changes):
    args={}
    for group,items in LEDGER[node_id]['source_inputs'].items():
        for name,spec in items.items():
            if spec[0]=='IMAGE':
                args[name]=None if group=='optional' else torch.linspace(-.1,1.1,9*13*3).reshape(1,9,13,3)
                continue
            opts=spec[1] if len(spec)>1 else {}
            args[name]=opts.get('default',spec[0][0] if isinstance(spec[0],list) else None)
    args.update(width=61,height=47)
    if node_id=='CR Binary Pattern':args.update(color_0='blue',color_1='red',background_color='green',outline_color='white')
    if node_id in ('CR Draw Shape','CR Draw Pie'):args.update(shape_color='red',back_color='blue')
    if node_id=='CR Random Shape Pattern':args.update(num_rows=3,num_cols=4,color1='red',color2='blue')
    args.update(changes);return args

def exact(actual,expected):
    assert len(actual)==len(expected)
    for a,b in zip(actual,expected):
        if isinstance(b,torch.Tensor):assert a.shape==b.shape and a.dtype==b.dtype and torch.equal(a,b)
        else:assert type(a) is type(b) and a==b

def oracle(node_id,args):
    obj=OLD[node_id]();return getattr(obj,obj.FUNCTION)(**args)


def outcome(fn):
    try:
        value=fn();return 'value',value.result if hasattr(value,'result') else value
    except Exception as exc:return 'error',type(exc),str(exc)

def parity(node_id,args):
    actual=outcome(lambda:NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args));expected=outcome(lambda:oracle(node_id,args))
    assert actual[0]==expected[0]
    if actual[0]=='error':assert actual[1:]==expected[1:]
    else:exact(actual[1],expected[1])


def controlled(node_id,args,monkeypatch,seed=77):
    rng=random.Random(seed)
    monkeypatch.setattr(NEW.secure_patterns,'_new_rng',lambda:rng)
    OLD[node_id].__dict__[OLD[node_id].FUNCTION].__globals__['random']=random.Random(seed)
    parity(node_id,args)

@pytest.mark.parametrize('text',['10101','01\n10','  10  \n  001  ','12\n23','','\n','1\n','1\n\n0','bad','💥','١٠','1 0'])
@pytest.mark.parametrize('dimensions',[(61,47),(1,1),(0,47),(-1,47)])
def test_simple_binary_exact_grid_uneven_unicode_and_native_parse_geometry_errors(text,dimensions):
    parity('CR Simple Binary Pattern',args_for('CR Simple Binary Pattern',binary_pattern=text,width=dimensions[0],height=dimensions[1]))

@pytest.mark.parametrize('text',['10\n01','11111\n000','12\n23','','bad','1\n\n0'])
@pytest.mark.parametrize('bias',[-.3,0.,.37,1.,2.])
@pytest.mark.parametrize('jitter',[0,3,-2])
def test_random_binary_controlled_draw_order_bias_jitter_and_ignored_bits(monkeypatch,text,bias,jitter):
    controlled('CR Binary Pattern',args_for('CR Binary Pattern',binary_pattern=text,bias=bias,jitter_distance=jitter,outline_thickness=1),monkeypatch)

@pytest.mark.parametrize('shape',LEDGER['CR Draw Shape']['source_inputs']['required']['shape'][0]+['unknown'])
@pytest.mark.parametrize('transform',[(0,0,1.,0.),(5,-3,.7,37.),(-4,7,2.,90.),(0,0,0.,0.),(0,0,-1.,0.)])
def test_all_shape_choices_rotation_zoom_offsets_and_native_negative_geometry(shape,transform):
    parity('CR Draw Shape',args_for('CR Draw Shape',shape=shape,x_offset=transform[0],y_offset=transform[1],zoom=transform[2],rotation=transform[3]))

@pytest.mark.parametrize('angles',[(0,360),(30,330),(370,920),(-30,-330),(90,90),(360,0)])
@pytest.mark.parametrize('transform',[(0,0,1.,0.),(5,-3,.7,37.),(-4,7,2.,90.),(0,0,0.,0.),(0,0,-1.,0.)])
def test_pie_angles_rotation_geometry_native_errors_and_unused_shape_color(angles,transform):
    args=args_for('CR Draw Pie',pie_start=angles[0],pie_stop=angles[1],x_offset=transform[0],y_offset=transform[1],zoom=transform[2],rotation=transform[3])
    parity('CR Draw Pie',args)
    if transform[2]>=0:
        first=NEW.NODE_CLASS_MAPPINGS['CR Draw Pie'].execute(**args).result
        args['shape_color']='green'
        exact(NEW.NODE_CLASS_MAPPINGS['CR Draw Pie'].execute(**args).result,first)

@pytest.mark.parametrize('seed',list(range(24)))
@pytest.mark.parametrize('grid',[(3,4),(1,1),(0,0),(-1,2)])
def test_random_shape_controlled_choice_uniform_order_pixels_and_empty_loops(monkeypatch,seed,grid):
    controlled('CR Random Shape Pattern',args_for('CR Random Shape Pattern',num_rows=grid[0],num_cols=grid[1]),monkeypatch,seed)

def test_stochastic_draw_trace_all_twelve_helpers_and_no_host_global_rng_mutation(monkeypatch):
    class Traced(random.Random):
        def __init__(self,seed):super().__init__(seed);self.calls=[];self.shapes=set()
        def choice(self,values):
            value=super().choice(values)
            rendered=value.__name__ if callable(value) else value
            self.calls.append(('choice',rendered))
            if callable(value):self.shapes.add(value.__name__)
            return value
        def uniform(self,start,stop):
            value=super().uniform(start,stop);self.calls.append(('uniform',start,stop,value));return value
    shapes=set();before=random.getstate()
    for seed in range(24):
        left=Traced(seed);right=Traced(seed)
        monkeypatch.setattr(NEW.secure_patterns,'_new_rng',lambda:left)
        old=OLD['CR Random Shape Pattern'];old.__dict__[old.FUNCTION].__globals__['random']=right
        args=args_for('CR Random Shape Pattern');parity('CR Random Shape Pattern',args)
        assert left.calls==right.calls and len(left.calls)==3*4*4
        shapes.update(left.shapes)
    assert len(shapes)==12 and random.getstate()==before
    monkeypatch.undo()
    # Production path independently constructs a Random; never seeds/consumes global RNG.
    for node_id in ('CR Random Shape Pattern','CR Binary Pattern'):
        NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args_for(node_id))
    assert random.getstate()==before

@pytest.mark.parametrize('node_id',list(LEDGER))
def test_exact_schema_defaults_options_output_names_and_raw_declaration(node_id):
    cls=NEW.NODE_CLASS_MAPPINGS[node_id];row=LEDGER[node_id];schema=cls.GET_SCHEMA()
    assert cls.SDK_PERMISSIONS==('raw',) and cls.SDK_REFS is False
    assert schema.node_id==node_id and schema.display_name==row['display_name'] and schema.category==row['category']
    assert [o.io_type for o in schema.outputs]==row['return_types'] and [o.display_name for o in schema.outputs]==row['return_names']
    flat={k:(group,spec) for group,items in row['source_inputs'].items() for k,spec in items.items()}
    assert [i.id for i in schema.inputs]==list(flat)
    for inp in schema.inputs:
        group,source=flat[inp.id];assert inp.optional==(group=='optional')
        if isinstance(source[0],list):assert inp.options==source[0]
        else:assert inp.io_type==source[0]
        for k,value in (source[1] if len(source)>1 else {}).items():assert inp.as_dict()[k]==value

@pytest.mark.parametrize('node_id',list(LEDGER))
def test_canvas_and_parse_preflight_precedes_pil_or_rng_work(monkeypatch,node_id):
    def deny(*args,**kwargs):raise AssertionError('work before preflight')
    monkeypatch.setattr(NEW.secure_patterns.Image,'new',deny)
    monkeypatch.setattr(NEW.secure_patterns,'_new_rng',deny)
    cases=[{'width':4096,'height':4096},{'width':4097},{'height':2**100}]
    if 'binary_pattern' in args_for(node_id):cases.append({'binary_pattern':'1'*16385})
    if node_id=='CR Random Shape Pattern':cases.extend([{'num_rows':129},{'num_cols':2**100}])
    for changes in cases:
        with pytest.raises(ValueError,match='bound|workload'):
            NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args_for(node_id,**changes))

@pytest.mark.parametrize('node_id',['CR Draw Shape','CR Draw Pie'])
@pytest.mark.parametrize('changes',[{'zoom':float('nan')},{'zoom':11.},{'rotation':float('inf')},{'x_offset':2049}])
def test_nonfinite_and_large_drawing_scalars_fail_closed(node_id,changes):
    with pytest.raises(ValueError,match='finite|bound'):
        NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args_for(node_id,**changes))

def test_binary_bits_unused_and_global_lifetime_not_promised(monkeypatch):
    first=args_for('CR Binary Pattern',binary_pattern='01\n10',jitter_distance=3,bias=.4)
    second={**first,'binary_pattern':'99\n22'}
    monkeypatch.setattr(NEW.secure_patterns,'_new_rng',lambda:random.Random(901))
    exact(NEW.NODE_CLASS_MAPPINGS['CR Binary Pattern'].execute(**first).result,
          NEW.NODE_CLASS_MAPPINGS['CR Binary Pattern'].execute(**second).result)

def test_all_five_registered_guest_outer_two_pids_and_raw_denial():
    import execution
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for render in range(2):
                session=await GuestSession('ned-comfyroll-patterns-'+str(render),guest_runtime_root=V2).start()
                class Backend:
                    caps=('raw',)
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=self.caps)
                backend=Backend();_sdk.providers.register_execution_backend(backend)
                try:
                    for node_id in LEDGER:
                        cases=[args_for(node_id)]
                        if node_id=='CR Binary Pattern':
                            cases=[args_for(node_id,bias=0.,jitter_distance=0),args_for(node_id,bias=1.,jitter_distance=0)]
                        if node_id=='CR Draw Shape':
                            cases=[args_for(node_id,shape=s,rotation=37.) for s in LEDGER[node_id]['source_inputs']['required']['shape'][0]]
                        for args in cases:
                            cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA()
                            result=await execution._async_map_node_over_list(prompt_id='patterns-'+str(render),unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                            actual=result[0].result
                            if node_id=='CR Random Shape Pattern':
                                image,help_url=actual
                                assert isinstance(image,torch.Tensor) and image.shape==(1,47,61,3) and image.dtype==torch.float32
                                assert torch.isfinite(image).all() and image.min()>=0 and image.max()<=1
                                allowed=torch.tensor([[1.,1.,1.],[1.,0.,0.],[0.,0.,1.]])
                                assert torch.any(torch.all(image.reshape(-1,1,3)==allowed[None,:,:],dim=2),dim=1).all()
                                assert help_url==oracle(node_id,args)[1]
                            else:exact(actual,oracle(node_id,args))
                        backend.caps=()
                        with pytest.raises(wire.WireError,match='raw'):
                            await execution._async_map_node_over_list(prompt_id='pattern-denial',unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args_for(node_id).items()},func=cls.FUNCTION,v3_data=None)
                        backend.caps=('raw',)
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(previous)
        assert pids[0]!=pids[1]
    asyncio.run(run())

def test_production_dispatch_all_five_registered_entrypoints(monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        previous=_sdk.providers.execution_backend
        session=await GuestSession('ned-comfyroll-production-patterns',guest_runtime_root=V2).start()
        backend=CloudExecutionBackend()
        monkeypatch.setattr(backend,'_is_sandbox',lambda plan:True)
        async def session_for(*args,**kwargs):return session
        monkeypatch.setattr(backend.guests,'session_for',session_for)
        _sdk.providers.register_execution_backend(backend)
        try:
            for node_id in LEDGER:
                args=args_for(node_id)
                if node_id=='CR Binary Pattern':args['bias']=0.
                if node_id=='CR Random Shape Pattern':args.update(num_rows=0,num_cols=0)
                cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA()
                result=await execution._async_map_node_over_list(prompt_id='production-patterns',unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                result=await execution.resolve_map_node_over_list_results(result)
                exact(result[0].result,oracle(node_id,args))
            assert session.last_guest_pid not in (None,os.getpid())
        finally:await session.kill();await backend.shutdown();_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())

