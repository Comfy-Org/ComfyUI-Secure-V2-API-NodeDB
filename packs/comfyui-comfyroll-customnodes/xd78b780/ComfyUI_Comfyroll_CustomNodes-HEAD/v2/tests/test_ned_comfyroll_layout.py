"""Pixel-exact confined bundled-font and image-filter tests; not host/system font parity."""
import ast
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import types

import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageEnhance,ImageFilter,ImageOps
import pytest
import torch

sys.dont_write_bytecode=True;sys.argv=['ned-comfyroll-layout','--cpu']
CORE=Path(os.environ['COMFY_CORE_ROOT']);sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.transport import wire
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
spec=importlib.util.spec_from_file_location('ned_comfyroll_layout_pack',V2/'__init__.py',submodule_search_locations=[str(V2)])
NEW=importlib.util.module_from_spec(spec);sys.modules[spec.name]=NEW;spec.loader.exec_module(NEW)
LEDGER=json.loads((V2/'layout-draft-ledger.json').read_text())
icons=ast.literal_eval(ast.parse((PACK/'categories.py').read_text()).body[0].value)
config={}
for n in ast.parse((PACK/'config.py').read_text()).body:
    if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('COLORS','color_mapping','iso_sizes'):config[n.targets[0].id]=ast.literal_eval(n.value)
ns={'torch':torch,'np':np,'os':os,'icons':icons,'Image':Image,'ImageDraw':ImageDraw,'ImageFont':ImageFont,'ImageEnhance':ImageEnhance,'ImageFilter':ImageFilter,'ImageOps':ImageOps,**config}
names={'tensor2pil','pil2tensor','get_color_values','hex_to_rgb','combine_images','apply_outline_and_border','make_grid_panel'}
helpers=[copy.deepcopy(n) for n in ast.parse((PACK/'nodes/functions_graphics.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name in names]
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
    if node_id=='CR Color Panel':args.update(panel_width=13,panel_height=9)
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

@pytest.mark.parametrize('color',config['COLORS']+['not-a-color'])
@pytest.mark.parametrize('hex_color',['#8a10fF','123456','bad'])
def test_color_panel_exact_mapping_hex_and_native_invalid_colors(color,hex_color):
    parity('CR Color Panel',args_for('CR Color Panel',fill_color=color,fill_color_hex=hex_color))

@pytest.mark.parametrize('direction',['horizontal','vertical','unknown'])
@pytest.mark.parametrize('thickness',[(0,0),(2,1),(-1,-1),(1,2)])
@pytest.mark.parametrize('optional_count',[0,1,3])
def test_image_panel_geometry_padding_outlines_order_and_optional_images(direction,thickness,optional_count):
    args=args_for('CR Image Panel',border_thickness=thickness[0],outline_thickness=thickness[1],border_color='custom',border_color_hex='#4a10ff',outline_color='red',layout_direction=direction)
    for index in range(optional_count):
        args['image_'+str(index+2)]=torch.full((1,7-index,11-index,3),.2+.2*index)
    parity('CR Image Panel',args)

@pytest.mark.parametrize('batch',[0,1,2,5])
@pytest.mark.parametrize('columns',[0,1,2,3,8,-1])
def test_grid_batch_order_partial_rows_empty_and_native_column_errors(batch,columns):
    images=torch.linspace(-.1,1.1,max(1,batch)*9*13*3).reshape(max(1,batch),9,13,3)[:batch]
    parity('CR Image Grid Panel',args_for('CR Image Grid Panel',images=images,max_columns=columns,border_thickness=1,outline_thickness=2,border_color='blue',outline_color='red'))

@pytest.mark.parametrize('node_id',['CR Image Border','CR Feathered Border'])
@pytest.mark.parametrize('batch',[0,1,3])
@pytest.mark.parametrize('borders',[(0,0,0,0),(1,2,3,4),(-1,3,2,-1)])
@pytest.mark.parametrize('amount',[0,1,3])
def test_asymmetric_and_feathered_borders_batch_dtype_and_native_errors(node_id,batch,borders,amount):
    args=args_for(node_id,image=torch.linspace(0,1,max(1,batch)*9*13*3).reshape(max(1,batch),9,13,3)[:batch],top_thickness=borders[0],bottom_thickness=borders[1],left_thickness=borders[2],right_thickness=borders[3],border_color='custom',border_color_hex='#1a8a44')
    args['feather_amount' if node_id=='CR Feathered Border' else 'outline_thickness']=amount
    parity(node_id,args)

@pytest.mark.parametrize('node_id',['CR Half Drop Panel','CR Diamond Panel'])
@pytest.mark.parametrize('size',[(9,13),(13,9),(8,8)])
@pytest.mark.parametrize('drop',[0.,.37,.5,1.])
def test_every_pattern_odd_sizes_drop_percentage_and_none_identity(node_id,size,drop):
    options=LEDGER[node_id]['source_inputs']['required']['pattern'][0]
    for pattern in options+['unknown']:
        args=args_for(node_id,image=torch.linspace(0,1,size[0]*size[1]*3).reshape(1,*size,3),pattern=pattern)
        if node_id=='CR Half Drop Panel':args['drop_percentage']=drop
        parity(node_id,args)
        if pattern=='none':assert NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args).result[0] is args['image']

@pytest.mark.parametrize('angle,scale,transparency',[(0.,1.,0.),(33.,.7,.3),(90.,1.3,1.),(-33.,2.,-.2),(15.,0.,.5),(10.,-1.,0.)])
@pytest.mark.parametrize('offset',[(0,0),(-3,2),(50,-60)])
def test_transparent_rotation_scale_lanczos_center_offset_native_resize_errors(angle,scale,transparency,offset):
    overlay=torch.linspace(0,1,5*7*4).reshape(1,5,7,4)
    parity('CR Overlay Transparent Image',args_for('CR Overlay Transparent Image',overlay_image=overlay,rotation_angle=angle,overlay_scale_factor=scale,transparency=transparency,offset_x=offset[0],offset_y=offset[1]))

@pytest.mark.parametrize('node_id',list(LEDGER))
@pytest.mark.parametrize('dtype',[torch.float32,torch.float16])
def test_declared_contract_pixels_schema_defaults_and_resource_metadata(node_id,dtype):
    args=args_for(node_id)
    args={k:v.to(dtype) if isinstance(v,torch.Tensor) else v for k,v in args.items()}
    parity(node_id,args)
    cls=NEW.NODE_CLASS_MAPPINGS[node_id];row=LEDGER[node_id];schema=cls.GET_SCHEMA()
    assert cls.SDK_PERMISSIONS==tuple(row['permissions']) and cls.SDK_REFS is (node_id=='CR Select ISO Size')
    assert schema.node_id==node_id and schema.display_name==row['display_name'] and schema.category==row['category']
    assert [o.io_type for o in schema.outputs]==row['return_types'] and [o.display_name for o in schema.outputs]==row['return_names']
    flat={k:(group,spec) for group,items in row['source_inputs'].items() for k,spec in items.items()}
    assert [i.id for i in schema.inputs]==list(flat)
    for inp in schema.inputs:
        group,source=flat[inp.id];assert inp.optional==(group=='optional')
        if isinstance(source[0],list):assert inp.options==source[0]
        else:assert inp.io_type==source[0]
        for k,value in (source[1] if len(source)>1 else {}).items():assert inp.as_dict()[k]==value

@pytest.mark.parametrize('size',list(config['iso_sizes'])+['unknown'])
def test_all_ordered_iso_scalar_choices_and_native_unknown(size):
    parity('CR Select ISO Size',{'iso_size':size})

def test_projection_denied_before_any_pil_allocation(monkeypatch):
    def deny(*args,**kwargs):raise AssertionError('PIL allocated before bounded preflight')
    monkeypatch.setattr(NEW.secure_layout.Image,'new',deny)
    for node_id,args in [
      ('CR Color Panel',args_for('CR Color Panel',panel_width=4096,panel_height=4096)),
      ('CR Image Panel',args_for('CR Image Panel',image_1=torch.empty((1,1000,1000,3),device='meta'),border_thickness=1024)),
      ('CR Image Border',args_for('CR Image Border',image=torch.empty((16,4096,4096,3),device='meta'))),
      ('CR Overlay Transparent Image',args_for('CR Overlay Transparent Image',overlay_scale_factor=100.,overlay_image=torch.empty((1,512,512,3),device='meta'))),
      ('CR Half Drop Panel',args_for('CR Half Drop Panel',image=torch.empty((1,1024,1024,3),device='meta'),pattern='half drop'))]:
        with pytest.raises(ValueError,match='bound|MiB|workload'):NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args)
    with pytest.raises(ValueError,match='projected'):
        NEW.NODE_CLASS_MAPPINGS['CR Image Border'].execute(**args_for('CR Image Border',image=torch.empty((16,1,4096,3),device='meta'),left_thickness=1024,right_thickness=1024))

@pytest.mark.parametrize('node_id',['CR Image Border','CR Feathered Border','CR Image Grid Panel','CR Image Panel','CR Half Drop Panel','CR Diamond Panel'])
@pytest.mark.parametrize('shape',[(1,1,13,3),(2,9,1,3),(9,13,3),(1,9,13,1)])
def test_native_singleton_squeeze_and_hwc_direct_behavior_bounded(node_id,shape):
    key='images' if node_id=='CR Image Grid Panel' else 'image_1' if node_id=='CR Image Panel' else 'image'
    args=args_for(node_id,**{key:torch.linspace(0,1,int(np.prod(shape))).reshape(shape)})
    parity(node_id,args)

def test_all_nine_actual_guest_outer_pixels_two_fresh_pids_and_raw_denial():
    import execution
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for render in range(2):
                session=await GuestSession('ned-comfyroll-layout-'+str(render),guest_runtime_root=V2).start()
                class Backend:
                    caps=('raw',)
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=self.caps)
                backend=Backend();_sdk.providers.register_execution_backend(backend)
                try:
                    for node_id in LEDGER:
                        args=args_for(node_id)
                        if node_id=='CR Image Panel':args.update(image_2=torch.ones(1,5,7,3)*.3,border_thickness=1,outline_thickness=2,layout_direction='vertical')
                        if node_id=='CR Image Grid Panel':args.update(images=torch.linspace(0,1,3*9*13*3).reshape(3,9,13,3),max_columns=2)
                        if node_id=='CR Feathered Border':args.update(feather_amount=1,top_thickness=1)
                        if node_id=='CR Half Drop Panel':args.update(pattern='custom drop %',drop_percentage=.37)
                        if node_id=='CR Diamond Panel':args['pattern']='diamond'
                        if node_id=='CR Overlay Transparent Image':args.update(rotation_angle=33.,overlay_scale_factor=.7,transparency=.3)
                        cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA()
                        expected=oracle(node_id,args)
                        result=await execution._async_map_node_over_list(prompt_id='layout-'+str(render),unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                        exact(result[0].result,expected)
                        backend.caps=()
                        if node_id!='CR Select ISO Size':
                            with pytest.raises(wire.WireError,match='raw'):
                                await execution._async_map_node_over_list(prompt_id='layout-denial-'+str(render),unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                        else:
                            result=await execution._async_map_node_over_list(prompt_id='iso-zero-'+str(render),unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                            exact(result[0].result,expected)
                        backend.caps=('raw',)
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(previous)
        assert pids[0]!=pids[1]
    asyncio.run(run())

def test_production_dispatch_all_eight_pil_algorithms_and_scalar_iso(monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        previous=_sdk.providers.execution_backend
        session=await GuestSession('ned-comfyroll-production-layout',guest_runtime_root=V2).start()
        backend=CloudExecutionBackend()
        monkeypatch.setattr(backend,'_is_sandbox',lambda plan:True)
        async def session_for(*args,**kwargs):return session
        monkeypatch.setattr(backend.guests,'session_for',session_for)
        _sdk.providers.register_execution_backend(backend)
        try:
            for node_id in LEDGER:
                args=args_for(node_id)
                cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA()
                result=await execution._async_map_node_over_list(prompt_id='production-layout',unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                result=await execution.resolve_map_node_over_list_results(result)
                exact(result[0].result,oracle(node_id,args))
            assert session.last_guest_pid not in (None,os.getpid())
        finally:await session.kill();await backend.shutdown();_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
