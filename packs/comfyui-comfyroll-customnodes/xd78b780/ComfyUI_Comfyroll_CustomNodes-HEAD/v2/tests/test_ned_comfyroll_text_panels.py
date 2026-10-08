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

sys.dont_write_bytecode=True;sys.argv=['ned-comfyroll-text-panels','--cpu']
CORE=Path(os.environ['COMFY_CORE_ROOT']);sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.transport import wire
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
spec=importlib.util.spec_from_file_location('ned_comfyroll_text_panels_pack',V2/'__init__.py',submodule_search_locations=[str(V2)])
NEW=importlib.util.module_from_spec(spec);sys.modules[spec.name]=NEW;spec.loader.exec_module(NEW)
LEDGER=json.loads((V2/'text-panels-draft-ledger.json').read_text())
icons=ast.literal_eval(ast.parse((PACK/'categories.py').read_text()).body[0].value)
config={}
for n in ast.parse((PACK/'config.py').read_text()).body:
    if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('COLORS','color_mapping'):config[n.targets[0].id]=ast.literal_eval(n.value)
ns={'torch':torch,'np':np,'os':os,'icons':icons,'Image':Image,'ImageDraw':ImageDraw,'ImageFont':ImageFont,'ImageEnhance':ImageEnhance,'ImageFilter':ImageFilter,'ImageOps':ImageOps,'__file__':str(PACK/'nodes/functions_graphics.py'),**config}
names={'tensor2pil','pil2tensor','get_text_size','get_color_values','hex_to_rgb','align_text','justify_text','text_panel','draw_text','combine_images'}
for n in ast.parse((PACK/'nodes/nodes_graphics_layout.py').read_text()).body:
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
                args[name]=torch.linspace(-.1,1.1,79*113*3).reshape(1,79,113,3)
                if name=='image_background':args[name]=torch.full((1,79,113,3),.27)
                continue
            opts=spec[1] if len(spec)>1 else {}
            args[name]=opts.get('default',spec[0][0] if isinstance(spec[0],list) else None)
    if node_id=='CR Simple Text Panel':args.update(panel_width=113,panel_height=79,text='Ajg\né<>',font_size=13,font_color='red',background_color='blue')
    else:args.update(header_height=17,footer_height=13,header_font_size=13,footer_font_size=11,header_text='Ajg\né<>',footer_text='FOOT',font_color='red',background_color='blue',border_color='green',border_thickness=2)
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
    assert actual[0]==expected[0], (actual if actual[0]=='error' else actual[0], expected if expected[0]=='error' else expected[0])
    if actual[0]=='error':assert actual[1:]==expected[1:]
    else:exact(actual[1],expected[1])


@pytest.mark.parametrize('node_id',list(LEDGER))
@pytest.mark.parametrize('font',NEW.secure_graphics.FONT_NAMES)
@pytest.mark.parametrize('choice',['left','center','right'])
def test_all_fonts_text_metrics_and_horizontal_justification_exact(node_id,font,choice):
    args=args_for(node_id,font_name=font)
    if node_id=='CR Page Layout':args.update(layout_options='header and footer',header_align=choice,footer_align=choice)
    else:args['justify']=choice
    parity(node_id,args)

@pytest.mark.parametrize('layout',['header','footer','header and footer','no header or footer','unknown'])
@pytest.mark.parametrize('heights',[(0,0),(17,13),(-1,13),(17,-1)])
@pytest.mark.parametrize('border',[0,2,-1])
def test_page_header_footer_zero_negative_heights_border_and_native_behavior(layout,heights,border):
    parity('CR Page Layout',args_for('CR Page Layout',layout_options=layout,header_height=heights[0],footer_height=heights[1],border_thickness=border))

@pytest.mark.parametrize('align',['top','center','bottom','unknown'])
@pytest.mark.parametrize('outline',[0,1,3,-1])
@pytest.mark.parametrize('text',['','Ajg\né<>','line1\n\nline3'])
def test_simple_text_panel_alignment_stroke_multiline_and_native_errors(align,outline,text):
    parity('CR Simple Text Panel',args_for('CR Simple Text Panel',align=align,font_outline_thickness=outline,text=text,font_outline_color='yellow'))

@pytest.mark.parametrize('node_id',list(LEDGER))
@pytest.mark.parametrize('size',[0,-1,1,31])
def test_native_zero_negative_font_size_not_silently_repaired(node_id,size):
    args=args_for(node_id)
    if node_id=='CR Page Layout':args.update(header_font_size=size,footer_font_size=size,layout_options='header and footer')
    else:args['font_size']=size
    parity(node_id,args)

@pytest.mark.parametrize('shape',[(1,19,23,3),(2,19,23,3),(1,1,13,3),(1,9,1,3),(1,9,13,1),(9,13,3),(0,9,13,3)])
@pytest.mark.parametrize('dtype',[torch.float32,torch.float16,torch.bfloat16])
def test_page_tensor_squeeze_batch_channels_dtype_and_native_boundaries(shape,dtype):
    value=torch.linspace(0,1,int(np.prod(shape))).reshape(shape).to(dtype)
    parity('CR Page Layout',args_for('CR Page Layout',image_panel=value))

@pytest.mark.parametrize('node_id',list(LEDGER))
def test_exact_metadata_options_defaults_resource_bytes_and_pristine_cache_hygiene(node_id):
    cls=NEW.NODE_CLASS_MAPPINGS[node_id];row=LEDGER[node_id];schema=cls.GET_SCHEMA()
    assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS==('raw',)
    assert schema.node_id==node_id and schema.display_name==row['display_name'] and schema.category==row['category']
    assert [o.io_type for o in schema.outputs]==row['return_types'] and [o.display_name for o in schema.outputs]==row['return_names']
    flat={k:(group,spec) for group,items in row['source_inputs'].items() for k,spec in items.items()}
    assert [i.id for i in schema.inputs]==list(flat)
    assert json.loads(json.dumps(OLD[node_id].INPUT_TYPES()))==row['source_inputs']
    for inp in schema.inputs:
        group,source=flat[inp.id];assert inp.optional==(group=='optional')
        if isinstance(source[0],list):assert inp.options==source[0]
        else:assert inp.io_type==source[0]
        for k,value in (source[1] if len(source)>1 else {}).items():assert inp.as_dict()[k]==value
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))
    for name in NEW.secure_graphics.FONT_NAMES:assert (PACK/'fonts'/name).read_bytes()==(V2/'fonts'/name).read_bytes()

@pytest.mark.parametrize('node_id',list(LEDGER))
def test_workload_and_closed_font_bounds_precede_any_pil_work(monkeypatch,node_id):
    def deny(*args,**kwargs):raise AssertionError('PIL/font before preflight')
    monkeypatch.setattr(NEW.secure_text_panels.Image,'new',deny);monkeypatch.setattr(NEW.secure_text_panels.ImageFont,'truetype',deny)
    cases=[{'font_name':'/System/Library/Fonts/Arial.ttf'},{'font_name':'../fonts/Roboto-Regular.ttf'}]
    if node_id=='CR Page Layout':
        cases.extend([{'header_text':'x'*4097},{'header_text':'x'*100,'header_font_size':1024},{'image_panel':torch.empty((1,4096,4096,3),device='meta')},{'image_panel':torch.empty((1,1,4096,3),device='meta'),'header_height':1024,'footer_height':1024,'border_thickness':1024}])
    else:cases.extend([{'text':'x'*4097},{'text':'x'*100,'font_size':1024},{'panel_width':4096,'panel_height':4096}])
    for changes in cases:
        with pytest.raises(ValueError,match='bound|immutable|workload'):
            NEW.NODE_CLASS_MAPPINGS[node_id].execute(**args_for(node_id,**changes))

def test_both_registered_nodes_all_fonts_two_actual_pids_outer_and_raw_denial():
    import execution
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for render in range(2):
                session=await GuestSession('ned-comfyroll-text-panels-'+str(render),guest_runtime_root=V2).start()
                class Backend:
                    caps=('raw',)
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=self.caps)
                backend=Backend();_sdk.providers.register_execution_backend(backend)
                try:
                    for node_id in LEDGER:
                        cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA()
                        for font in NEW.secure_graphics.FONT_NAMES:
                            args=args_for(node_id,font_name=font)
                            result=await execution._async_map_node_over_list(prompt_id='text-panels',unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                            exact(result[0].result,oracle(node_id,args))
                        backend.caps=()
                        with pytest.raises(wire.WireError,match='raw'):
                            await execution._async_map_node_over_list(prompt_id='text-panel-denial',unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args_for(node_id).items()},func=cls.FUNCTION,v3_data=None)
                        backend.caps=('raw',)
                        args=args_for(node_id,font_name='../fonts/Roboto-Regular.ttf')
                        with pytest.raises(wire.WireError,match='immutable bundled'):
                            await execution._async_map_node_over_list(prompt_id='text-panel-font-denial',unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(previous)
        assert pids[0]!=pids[1]
    asyncio.run(run())

def test_production_dispatch_both_text_panel_entrypoints(monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        previous=_sdk.providers.execution_backend;session=await GuestSession('ned-comfyroll-production-text-panels',guest_runtime_root=V2).start();backend=CloudExecutionBackend()
        monkeypatch.setattr(backend,'_is_sandbox',lambda plan:True)
        async def session_for(*args,**kwargs):return session
        monkeypatch.setattr(backend.guests,'session_for',session_for);_sdk.providers.register_execution_backend(backend)
        try:
            for node_id in LEDGER:
                args=args_for(node_id);cls=NEW.NODE_CLASS_MAPPINGS[node_id];cls.GET_SCHEMA()
                result=await execution._async_map_node_over_list(prompt_id='production-text-panels',unique_id=node_id,obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                result=await execution.resolve_map_node_over_list_results(result);exact(result[0].result,oracle(node_id,args))
            assert session.last_guest_pid not in (None,os.getpid())
        finally:await session.kill();await backend.shutdown();_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
