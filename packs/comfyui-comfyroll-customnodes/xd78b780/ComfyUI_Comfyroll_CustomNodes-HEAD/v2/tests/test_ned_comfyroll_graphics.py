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
from PIL import Image,ImageDraw,ImageFont,ImageEnhance,ImageFilter
import pytest
import torch

sys.dont_write_bytecode=True;sys.argv=['ned-comfyroll-graphics','--cpu']
CORE=Path(os.environ['COMFY_CORE_ROOT']);sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.transport import wire
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
spec=importlib.util.spec_from_file_location('ned_comfyroll_graphics_pack',V2/'__init__.py',submodule_search_locations=[str(V2)])
NEW=importlib.util.module_from_spec(spec);sys.modules[spec.name]=NEW;spec.loader.exec_module(NEW)
LEDGER=json.loads((V2/'graphics-draft-ledger.json').read_text())
icons=ast.literal_eval(ast.parse((PACK/'categories.py').read_text()).body[0].value)
config={}
for n in ast.parse((PACK/'config.py').read_text()).body:
    if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('COLORS','color_mapping'):config[n.targets[0].id]=ast.literal_eval(n.value)
ns={'torch':torch,'np':np,'os':os,'icons':icons,'Image':Image,'ImageDraw':ImageDraw,'ImageFont':ImageFont,'ImageEnhance':ImageEnhance,'ImageFilter':ImageFilter,**config}
names={'tensor2pil','pil2tensor','get_text_size','get_color_values','hex_to_rgb','reduce_opacity'}
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
            if name=='image':continue
            opts=spec[1] if len(spec)>1 else {}
            args[name]=opts.get('default',spec[0][0] if isinstance(spec[0],list) else None)
    args.update(image=torch.linspace(-.1,1.1,2*39*67*3).reshape(2,39,67,3));args.update(changes);return args

def exact(actual,expected):
    assert len(actual)==len(expected)
    for a,b in zip(actual,expected):
        if isinstance(b,torch.Tensor):assert a.shape==b.shape and a.dtype==b.dtype and torch.equal(a,b)
        else:assert type(a) is type(b) and a==b

def oracle(node_id,args):
    obj=OLD[node_id]();return getattr(obj,obj.FUNCTION)(**args)

WATERMARK='CR Simple Text Watermark';TINT='CR Color Tint';VIGNETTE='CR Vignette Filter'
@pytest.mark.parametrize('font',NEW.secure_graphics.FONT_NAMES)
@pytest.mark.parametrize('align',LEDGER[WATERMARK]['source_inputs']['required']['align'][0])
@pytest.mark.parametrize('opacity',[0.,.3,1.])
def test_every_bundled_font_alignment_and_opacity_exact_pixels(font,align,opacity):
    args=args_for(WATERMARK,font_name=font,align=align,opacity=opacity,font_size=13,x_margin=-3,y_margin=5,text='Aé<>&测试')
    exact(NEW.NODE_CLASS_MAPPINGS[WATERMARK].execute(**args).result,oracle(WATERMARK,args))

@pytest.mark.parametrize('mode',LEDGER[TINT]['source_inputs']['required']['mode'][0])
@pytest.mark.parametrize('strength',[.1,.5,1.])
def test_every_tint_mode_exact(mode,strength):
    args=args_for(TINT,mode=mode,strength=strength,tint_color_hex='#8a10FF')
    exact(NEW.NODE_CLASS_MAPPINGS[TINT].execute(**args).result,oracle(TINT,args))

@pytest.mark.parametrize('shape',['circle','oval','diamond','square'])
@pytest.mark.parametrize('reverse',['yes','no'])
@pytest.mark.parametrize('feather,zoom,offset',[(0,1.,0),(5,.7,2),(1,0.,0)])
def test_vignette_image_mask_pixels_and_layout_exact(shape,reverse,feather,zoom,offset):
    args=args_for(VIGNETTE,vignette_shape=shape,reverse=reverse,feather_amount=feather,zoom=zoom,x_offset=offset,y_offset=-offset)
    exact(NEW.NODE_CLASS_MAPPINGS[VIGNETTE].execute(**args).result,oracle(VIGNETTE,args))
    assert oracle(VIGNETTE,args)[1].shape==(2,1,39,67)

def test_tint_native_zero_strength_defect_and_authorized_identity_repair():
    args=args_for(TINT,strength=0.)
    actual=NEW.NODE_CLASS_MAPPINGS[TINT].execute(**args).result;expected=oracle(TINT,args)
    assert len(expected)==1 and expected[0] is args['image']
    assert len(actual)==2 and actual[0] is args['image'] and type(actual[1]) is str
    assert actual[1]==oracle(TINT,args_for(TINT,strength=1.))[1]
    assert len(NEW.NODE_CLASS_MAPPINGS[TINT].GET_SCHEMA().outputs)==2

@pytest.mark.parametrize('node_id',list(LEDGER))
def test_exact_metadata_resources_and_bounded_security(node_id):
    cls=NEW.NODE_CLASS_MAPPINGS[node_id];row=LEDGER[node_id];schema=cls.GET_SCHEMA()
    assert schema.node_id==node_id and schema.display_name==row['display_name'] and schema.category==row['category']
    assert [o.io_type for o in schema.outputs]==row['return_types'] and [o.display_name for o in schema.outputs]==row['return_names']
    flat={k:(group,spec) for group,items in row['source_inputs'].items() for k,spec in items.items()}
    assert [i.id for i in schema.inputs]==list(flat)
    for inp in schema.inputs:
        group,source=flat[inp.id];assert inp.optional==(group=='optional')
        if isinstance(source[0],list):assert inp.options==source[0]
        else:assert inp.io_type==source[0]
        for k,v in (source[1] if len(source)>1 else {}).items():assert inp.as_dict()[k]==v
    assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS==('raw',)
    huge=torch.empty((16,4096,4096,3),device='meta')
    with pytest.raises(ValueError,match='allocation'):cls.execute(**args_for(node_id,image=huge))
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

@pytest.mark.parametrize('name',['../fonts/Roboto-Regular.ttf','/System/Library/Fonts/Arial.ttf','Arial.ttf','comic.ttf/../impact.ttf','Roboto-Regular.ttf\x00'])
def test_no_ambient_font_paths_or_names(name):
    with pytest.raises(ValueError,match='immutable bundled'):NEW.NODE_CLASS_MAPPINGS[WATERMARK].execute(**args_for(WATERMARK,font_name=name))

def test_font_files_identical_and_text_workload_bounded():
    for name in NEW.secure_graphics.FONT_NAMES:
        assert (PACK/'fonts'/name).read_bytes()==(V2/'fonts'/name).read_bytes()
    with pytest.raises(ValueError,match='text'):NEW.NODE_CLASS_MAPPINGS[WATERMARK].execute(**args_for(WATERMARK,text='x'*4097))
    with pytest.raises(ValueError,match='glyph workload'):NEW.NODE_CLASS_MAPPINGS[WATERMARK].execute(**args_for(WATERMARK,text='x'*100,font_size=1024))

def test_actual_confined_guest_all_fonts_pixels_outer_mask_and_raw_denial():
    import execution
    async def run():
        previous=_sdk.providers.execution_backend;session=await GuestSession('ned-comfyroll-graphics',guest_runtime_root=V2).start()
        class Backend:
            caps=('raw',)
            async def dispatch(self,plan,local_call,runtime):
                assert plan.input_mode=='values'
                # Same value-mode admission as production CloudExecutionBackend.dispatch.
                # GuestSession itself only accepts wire-safe refs, not raw tensors.
                plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                return await session.execute(plan,runtime,capabilities=self.caps)
        backend=Backend();_sdk.providers.register_execution_backend(backend)
        async def execute(node_id,args):
            cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA()
            result=await execution._async_map_node_over_list(prompt_id='ned-graphics',unique_id='1',obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
            return result[0].result
        try:
            for font in NEW.secure_graphics.FONT_NAMES:
                args=args_for(WATERMARK,font_name=font,text='Aé<>&测试',font_size=13)
                exact(await execute(WATERMARK,args),oracle(WATERMARK,args))
            for node_id in (TINT,VIGNETTE):
                args=args_for(node_id)
                if node_id==VIGNETTE:args['feather_amount']=5
                exact(await execute(node_id,args),oracle(node_id,args))
            zero=args_for(TINT,strength=0.)
            zero_result=await execute(TINT,zero)
            assert len(zero_result)==2 and torch.equal(zero_result[0],zero['image'])
            assert zero_result[1]==oracle(TINT,args_for(TINT,strength=1.))[1]
            backend.caps=()
            for node_id in LEDGER:
                with pytest.raises(wire.WireError,match='raw'):await execute(node_id,args_for(node_id))
            assert session.last_guest_pid not in (None,os.getpid())
        finally:await session.kill();_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())

def test_production_cloud_dispatch_value_admission_and_bundled_font_pixels(monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        previous=_sdk.providers.execution_backend
        session=await GuestSession('ned-comfyroll-production-graphics',guest_runtime_root=V2).start()
        backend=CloudExecutionBackend()
        # Only the fixture module/guest routing is adapted; production dispatch,
        # declared socket admission/capability filtering/output transport all run.
        monkeypatch.setattr(backend,'_is_sandbox',lambda plan:True)
        async def session_for(*args,**kwargs):return session
        monkeypatch.setattr(backend.guests,'session_for',session_for)
        _sdk.providers.register_execution_backend(backend)
        try:
            for node_id in (WATERMARK,TINT,VIGNETTE):
                args=args_for(node_id)
                if node_id==VIGNETTE:args['feather_amount']=5
                cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA()
                result=await execution._async_map_node_over_list(prompt_id='ned-production-graphics',unique_id='1',obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                result=await execution.resolve_map_node_over_list_results(result)
                exact(result[0].result,oracle(node_id,args))
            assert session.last_guest_pid not in (None,os.getpid())
        finally:await session.kill();await backend.shutdown();_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
