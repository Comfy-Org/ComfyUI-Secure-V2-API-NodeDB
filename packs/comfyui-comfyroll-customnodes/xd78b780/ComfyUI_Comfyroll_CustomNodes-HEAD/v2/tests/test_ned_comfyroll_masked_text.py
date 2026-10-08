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

sys.dont_write_bytecode=True;sys.argv=['ned-comfyroll-masked-text','--cpu']
CORE=Path(os.environ['COMFY_CORE_ROOT']);sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.transport import wire
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
spec=importlib.util.spec_from_file_location('ned_comfyroll_masked_text_pack',V2/'__init__.py',submodule_search_locations=[str(V2)])
NEW=importlib.util.module_from_spec(spec);sys.modules[spec.name]=NEW;spec.loader.exec_module(NEW)
LEDGER=json.loads((V2/'masked-text-draft-ledger.json').read_text())
icons=ast.literal_eval(ast.parse((PACK/'categories.py').read_text()).body[0].value)
config={}
for n in ast.parse((PACK/'config.py').read_text()).body:
    if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('COLORS','color_mapping'):config[n.targets[0].id]=ast.literal_eval(n.value)
ns={'torch':torch,'np':np,'os':os,'icons':icons,'Image':Image,'ImageDraw':ImageDraw,'ImageFont':ImageFont,'ImageEnhance':ImageEnhance,'ImageFilter':ImageFilter,'ImageOps':ImageOps,'__file__':str(PACK/'nodes/functions_graphics.py'),**config}
names={'tensor2pil','pil2tensor','get_text_size','get_color_values','hex_to_rgb','align_text','justify_text','draw_masked_text'}
for n in ast.parse((PACK/'nodes/nodes_graphics_text.py').read_text()).body:
    if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('ALIGN_OPTIONS','ROTATE_OPTIONS','JUSTIFY_OPTIONS','PERSPECTIVE_OPTIONS'):ns[n.targets[0].id]=ast.literal_eval(n.value)
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
                args[name]=torch.linspace(-.1,1.1,2*79*113*3).reshape(2,79,113,3)
                if name=='image_background':args[name]=torch.full((1,79,113,3),.27)
                continue
            opts=spec[1] if len(spec)>1 else {}
            args[name]=opts.get('default',spec[0][0] if isinstance(spec[0],list) else None)
    if node_id=='CR Draw Text':args.update(image_width=113,image_height=79)
    args.update(text='Ajg\né<>',font_size=13)
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

@pytest.mark.parametrize('node_id',list(LEDGER))
@pytest.mark.parametrize('font',NEW.secure_graphics.FONT_NAMES)
@pytest.mark.parametrize('position',[('center','center',0,0,0,0,23.,'text center'),('top','left',-3,7,-2,3,37.,'image center'),('bottom','right',3,-7,2,-3,90.,'text center')])
def test_all_four_all_ten_fonts_alignment_justification_rotation_exact(node_id,font,position):
    align,justify,x,y,margin,spacing,rotation,options=position
    parity(node_id,args_for(node_id,font_name=font,align=align,justify=justify,position_x=x,position_y=y,margins=margin,line_spacing=spacing,rotation_angle=rotation,rotation_options=options))

@pytest.mark.parametrize('node_id',list(LEDGER))
@pytest.mark.parametrize('text',['','\n','Aa\n\nbb','<img src=x onerror=evil>&"','شمس é中文','line1\nline2\nline3'])
@pytest.mark.parametrize('size',[1,27])
def test_blank_multiline_adversarial_unicode_literal_text_exact(node_id,text,size):
    parity(node_id,args_for(node_id,text=text,font_size=size))

@pytest.mark.parametrize('node_id',list(LEDGER))
@pytest.mark.parametrize('changes',[{'align':'unknown'},{'justify':'unknown'},{'rotation_options':'unknown'},{'font_color_hex':'bad','bg_color_hex':'bad'},{'font_color_hex':'123456','bg_color_hex':'8aff00'}])
def test_native_invalid_enum_and_hex_errors_without_silent_substitution(node_id,changes):
    args=args_for(node_id)
    args.update({k:v for k,v in changes.items() if k in args})
    parity(node_id,args)

@pytest.mark.parametrize('node_id',['CR Overlay Text','CR Mask Text','CR Composite Text'])
@pytest.mark.parametrize('shape',[(0,79,113,3),(1,1,13,3),(2,9,1,3),(1,9,13,1),(1,9,13,2),(1,9,13,4)])
@pytest.mark.parametrize('dtype',[torch.float32,torch.float16])
def test_first_batch_singleton_squeeze_channels_dtype_and_native_errors(node_id,shape,dtype):
    args=args_for(node_id)
    for key in ('image','image_text','image_background'):
        if key in args:args[key]=torch.linspace(0,1,int(np.prod(shape))).reshape(shape).to(dtype)
    parity(node_id,args)

def test_composite_different_dimensions_native_error_and_first_batch_selection():
    args=args_for('CR Composite Text',image_text=torch.zeros(1,19,23,3))
    parity('CR Composite Text',args)
    for node_id in ('CR Overlay Text','CR Mask Text','CR Composite Text'):
        args=args_for(node_id)
        first=NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args).result
        for key in ('image','image_text','image_background'):
            if key in args and args[key].shape[0]>1:args[key]=args[key].clone();args[key][1:]=.99
        exact(NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args).result,first)

@pytest.mark.parametrize('node_id',['CR Overlay Text','CR Mask Text','CR Composite Text'])
def test_native_bfloat16_pillow_numpy_boundary_preserved(node_id):
    args=args_for(node_id)
    for key in ('image','image_text','image_background'):
        if key in args:args[key]=args[key].to(torch.bfloat16)
    parity(node_id,args)
    assert outcome(lambda:oracle(node_id,args))[0]=='error'

@pytest.mark.parametrize('node_id',list(LEDGER))
def test_exact_schema_and_bundled_resource_bytes(node_id):
    cls=NEW.NODE_CLASS_MAPPINGS[node_id];row=LEDGER[node_id];schema=cls.GET_SCHEMA()
    assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS==('raw',)
    assert schema.node_id==node_id and schema.display_name==row['display_name'] and schema.category==row['category']
    assert [o.io_type for o in schema.outputs]==row['return_types'] and [o.display_name for o in schema.outputs]==row['return_names']
    flat={k:(group,spec) for group,items in row['source_inputs'].items() for k,spec in items.items()}
    assert [i.id for i in schema.inputs]==list(flat)
    assert OLD[node_id].INPUT_TYPES()==row['source_inputs'] or json.loads(json.dumps(OLD[node_id].INPUT_TYPES()))==row['source_inputs']
    for inp in schema.inputs:
        group,source=flat[inp.id];assert inp.optional==(group=='optional')
        if isinstance(source[0],list):assert inp.options==source[0]
        else:assert inp.io_type==source[0]
        for k,value in (source[1] if len(source)>1 else {}).items():assert inp.as_dict()[k]==value
    for name in NEW.secure_graphics.FONT_NAMES:assert (PACK/'fonts'/name).read_bytes()==(V2/'fonts'/name).read_bytes()
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

@pytest.mark.parametrize('node_id',list(LEDGER))
@pytest.mark.parametrize('name',['../fonts/Roboto-Regular.ttf','/System/Library/Fonts/Arial.ttf','Arial.ttf','Roboto-Regular.ttf\x00'])
def test_font_authority_is_closed_immutable_catalogue(node_id,name):
    with pytest.raises(ValueError,match='immutable bundled'):
        NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args_for(node_id,font_name=name))

@pytest.mark.parametrize('node_id',list(LEDGER))
def test_font_glyph_input_and_canvas_preflight_precedes_any_allocation(monkeypatch,node_id):
    def deny(*args,**kwargs):raise AssertionError('PIL or font opened before bounds')
    monkeypatch.setattr(NEW.secure_masked_text.Image,'new',deny)
    monkeypatch.setattr(NEW.secure_masked_text.ImageFont,'truetype',deny)
    cases=[{'text':'x'*4097},{'text':'x'*100,'font_size':1024},{'font_size':0},{'position_x':4097},{'rotation_angle':float('nan')}]
    if node_id=='CR Draw Text':cases.append({'image_width':4096,'image_height':4096})
    else:
        key='image_text' if node_id=='CR Composite Text' else 'image'
        cases.append({key:torch.empty((16,4096,4096,3),device='meta')})
    for changes in cases:
        with pytest.raises(ValueError,match='bound|finite|workload'):
            NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args_for(node_id,**changes))

def test_registered_all_four_all_fonts_real_guest_outer_two_fresh_pids_and_raw_denial():
    import execution
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for render in range(2):
                session=await GuestSession('ned-comfyroll-masked-text-'+str(render),guest_runtime_root=V2).start()
                class Backend:
                    caps=('raw',)
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=self.caps)
                backend=Backend();_sdk.providers.register_execution_backend(backend)
                try:
                    for node_id in LEDGER:
                        for font in NEW.secure_graphics.FONT_NAMES:
                            args=args_for(node_id,font_name=font,rotation_angle=37.,rotation_options='image center',position_x=-3,position_y=2)
                            cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA()
                            result=await execution._async_map_node_over_list(prompt_id='masked-text-'+str(render),unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                            exact(result[0].result,oracle(node_id,args))
                        backend.caps=()
                        with pytest.raises(wire.WireError,match='raw'):
                            await execution._async_map_node_over_list(prompt_id='masked-denial',unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args_for(node_id).items()},func=cls.FUNCTION,v3_data=None)
                        backend.caps=('raw',)
                        denied=args_for(node_id,font_name='../fonts/Roboto-Regular.ttf')
                        with pytest.raises(wire.WireError,match='immutable bundled'):
                            await execution._async_map_node_over_list(prompt_id='masked-font-denial',unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in denied.items()},func=cls.FUNCTION,v3_data=None)
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(previous)
        assert pids[0]!=pids[1]
    asyncio.run(run())

def test_production_dispatch_all_four_text_renderers(monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        previous=_sdk.providers.execution_backend
        session=await GuestSession('ned-comfyroll-production-masked-text',guest_runtime_root=V2).start()
        backend=CloudExecutionBackend()
        monkeypatch.setattr(backend,'_is_sandbox',lambda plan:True)
        async def session_for(*args,**kwargs):return session
        monkeypatch.setattr(backend.guests,'session_for',session_for)
        _sdk.providers.register_execution_backend(backend)
        try:
            for node_id in LEDGER:
                args=args_for(node_id)
                cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA()
                result=await execution._async_map_node_over_list(prompt_id='production-masked-text',unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                result=await execution.resolve_map_node_over_list_results(result)
                exact(result[0].result,oracle(node_id,args))
            assert session.last_guest_pid not in (None,os.getpid())
        finally:await session.kill();await backend.shutdown();_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
