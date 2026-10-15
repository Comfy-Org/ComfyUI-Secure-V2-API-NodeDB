"""Exact pinned CPU rasterization + actual guest/outer evidence, no ATI model."""
import ast
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Tuple
import numpy as np
import pytest
import torch

sys.dont_write_bytecode = True
V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent
CORE = Path('/Users/ben/comfy/ComfyUI-secure-nodes')
BACKEND = Path('/Users/ben/comfy/ComfyUI_secure_nodes/backend')
sys.path[:0] = [str(CORE), str(BACKEND)]
os.environ.setdefault('COMFY_CORE_ROOT', str(CORE))
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession

ID = 'WanVideoATITracksVisualize'
HELPERS = ('pad_pts', 'age_to_bgr', 'paint_point_track', 'parse_json_tracks')


def candidate(root=V2):
    name = '_wan_ati_' + str(id(root))
    spec = importlib.util.spec_from_file_location(name, root/'__init__.py', submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)
    return module.NODE_CLASS_MAPPINGS[ID]


def original():
    tree = ast.parse((PACK/'ATI/nodes.py').read_text())
    keep = [x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name in HELPERS
        or isinstance(x, ast.ClassDef) and x.name == ID]
    ns = {'json': json, 'np': np, 'torch': torch, 'Tuple': Tuple, 'FIXED_LENGTH': 121}
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(PACK/'ATI/nodes.py'), 'exec'), ns)
    return ns[ID]


def images(count=1, channels=3, dtype=torch.float32, height=7, width=9):
    values = torch.arange(count*height*width*channels).reshape(count,height,width,channels)
    return (values % 29).to(dtype) / 29 if dtype.is_floating_point else (values % 29).to(dtype)


def tracks(length=8, multiple=False, as_list=False):
    one = [{'x': float(i%9)-0.25, 'y': float(i%7)+0.25} for i in range(length)]
    data = [one, [{'x': 999.0, 'y': -2.0}, {'x': 4.5, 'y': 3.5}]] if multiple else one
    if as_list:
        return [json.dumps(one), json.dumps([{'x': 2.5, 'y': 3.5}])]
    return json.dumps(data)


def call_old(kwargs):
    return original()().patchmodel(**kwargs)[0]


def call_new(kwargs):
    return candidate().execute(**kwargs).result[0]


def equal(a,b):
    assert isinstance(b,torch.Tensor)
    assert a.shape == b.shape and a.dtype == b.dtype == torch.float32
    assert a.device == b.device == torch.device('cpu')
    assert torch.equal(a,b)


def test_ati_exact_schema_census_and_unchanged_helper_bodies():
    old=original();cls=candidate();schema=cls.GET_SCHEMA()
    assert schema.node_id == ID and schema.category == old.CATEGORY
    assert schema.display_name == 'WanVideo ATI Tracks Visualize'
    assert schema.outputs[0].io_type == old.RETURN_TYPES[0] == 'IMAGE'
    assert schema.outputs[0].display_name == old.RETURN_NAMES[0]
    for field,(name,info) in zip(schema.inputs,old.INPUT_TYPES()['required'].items()):
        assert field.id==name and field.io_type==info[0]
        if len(info)>1:
            for key,value in info[1].items():assert getattr(field,key)==value
    assert len(schema.inputs)==5 and len(schema.outputs)==1
    assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS==('raw',)
    legacy=ast.parse((PACK/'ATI/nodes.py').read_text())
    converted=ast.parse((V2/'secure_ati_visual_nodes.py').read_text())
    for name in HELPERS:
        a=next(x for x in legacy.body if isinstance(x,ast.FunctionDef) and x.name==name)
        b=next(x for x in converted.body if isinstance(x,ast.FunctionDef) and x.name==name)
        assert ast.dump(a,include_attributes=False)==ast.dump(b,include_attributes=False)


def test_ati_pixel_exact_frame_order_radii_tracks_dtypes_and_rgb_quirk():
    cases=0
    for count in (1,2,80,81,90):
        for channels,dtype in ((3,torch.float32),(4,torch.float64),(3,torch.uint8)):
            args=dict(images=images(count,channels,dtype),tracks=tracks(multiple=True),
                min_radius=0,max_radius=2,max_retain=3)
            before=args['images'].clone()
            equal(call_old(args),call_new(args))
            assert torch.equal(args['images'],before);cases+=1
    for length in (1,121,122):
        args=dict(images=images(),tracks=tracks(length),min_radius=1,max_radius=6,max_retain=50)
        equal(call_old(args),call_new(args));cases+=1
    args=dict(images=images(2),tracks=tracks(as_list=True),min_radius=6,max_radius=1,max_retain=1)
    equal(call_old(args),call_new(args));cases+=1
    result=call_new(dict(images=torch.zeros((1,7,9,3)),tracks=tracks(1),
        min_radius=0,max_radius=0,max_retain=50))
    assert result.shape==(81,7,9,3)
    # Source helper returns RGB despite BGR wording and draws 0..255 on floats.
    assert tuple(result[0,0,0].tolist())==(255.0,0.0,0.0)
    assert float(result.max())==255.0  # never silently normalise this legacy quirk
    assert cases==19


def test_ati_exact_fixed_padding_visibility_and_repeat_stride():
    module=sys.modules[candidate().__module__]
    padded=module.pad_pts([{'x':1,'y':2},{'x':3,'y':4}])
    assert padded.shape==(121,1,3) and padded.dtype==np.float32
    assert np.array_equal(padded[:2,0],[[1,2,1],[3,4,1]])
    assert not padded[2:].any()
    sampled=np.repeat(padded[None],2,axis=1)[:,::3]
    assert sampled.shape==(1,81,1,3)
    assert np.array_equal(sampled[0,:3,0,2],[1,1,0])
    source=images(80)
    actual=call_new(dict(images=source,tracks=tracks(1),min_radius=0,max_radius=0,max_retain=-1))
    # Negative retain draws nothing natively: source repeats80 to160 then slices81.
    assert torch.equal(actual[:80],source)
    assert torch.equal(actual[80],source[0])
    assert np.array_equal(module.age_to_bgr(0),(0,0,255))
    assert np.array_equal(module.age_to_bgr(1),(255,0,0))


def test_ati_native_malformed_outcomes_without_silent_repair():
    base=dict(images=images(),tracks=tracks(),min_radius=1,max_radius=2,max_retain=3)
    edits=[{'tracks':'[]'},{'tracks':'not json'},{'tracks':'[[]]'},
        {'tracks':'[{"x":1}]'},{'tracks':None},{'tracks':{}},
        {'tracks':'[{"x":"invalid","y":1}]'},{'max_retain':0},
        {'images':images(0)},{'images':images(dtype=torch.bfloat16)},
        {'min_radius':-5,'max_radius':-1},{'max_retain':'bad'}]
    for changes in edits:
        args={**base,**changes};observed=[]
        for fn in (call_old,call_new):
            try:fn(args);observed.append(None)
            except Exception as error:observed.append((type(error).__name__,str(error)))
        assert observed[0] is not None and observed[0]==observed[1],(changes,observed)


def test_ati_input_and_projected_allocation_guards_before_repeat_or_stack(monkeypatch):
    cls=candidate();module=sys.modules[cls.__module__]
    def no_stack(*args,**kwargs):pytest.fail('must refuse before stack/raster allocation')
    monkeypatch.setattr(module.np,'stack',no_stack)
    base=dict(images=images(),tracks=tracks(),min_radius=1,max_radius=2,max_retain=3)
    with pytest.raises(ValueError,match='projected'):
        cls.execute(**{**base,'images':torch.zeros((1,480,832,3))})
    with pytest.raises(ValueError,match='count'):
        cls.execute(**{**base,'tracks':json.dumps([[{'x':0,'y':0}]]*65)})
    with pytest.raises(ValueError,match='64 KiB'):
        cls.execute(**{**base,'tracks':'x'*65537})
    with pytest.raises(ValueError,match='coordinates'):
        cls.execute(**{**base,'tracks':'[{"x":1e20,"y":1}]'})
    with pytest.raises(ValueError,match='radius'):
        cls.execute(**{**base,'max_radius':101})
    with pytest.raises(ValueError,match='retention'):
        cls.execute(**{**base,'max_retain':101})
    def no_parse(*args,**kwargs):pytest.fail('must refuse text before JSON allocation')
    monkeypatch.setattr(module.json,'loads',no_parse)
    with pytest.raises(ValueError,match='64 KiB'):
        cls.execute(**{**base,'tracks':'x'*65537})


def test_ati_actual_guest_fresh_render_raw_denial_and_pixel_exact(tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(CORE))
    monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE','required')
    fresh=tmp_path/'fresh-render';shutil.copytree(V2,fresh)
    async def run():
        pids=[]
        for root in (V2,fresh):
            cls=candidate(root);session=await GuestSession('wan-ati',guest_runtime_root=root).start()
            assert session.sandbox_kind=='seatbelt'
            try:
                for count,multiple in ((1,False),(2,True),(80,False)):
                    args=dict(images=images(count),tracks=tracks(multiple=multiple),
                        min_radius=0,max_radius=2,max_retain=3)
                    refs=_sdk.InProcessRefResolver()
                    plan=_sdk.ExecutionPlan(prompt_id='wan-ati',node_id='1',node_type=ID,
                        node_module=cls.__module__,inputs=await _sdk.wrap_inputs(refs,args),input_mode='values',
                        permissions=('raw',),tier='sandbox')
                    runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                    actual=await session.execute(plan,runtime,capabilities=('raw',),tenant='ati-owner')
                    tensor=await refs.resolve(actual.result[0])
                    equal(call_old(args),tensor)
                with pytest.raises(Exception,match='raw'):
                    await session.execute(plan,runtime,capabilities=(),tenant='ati-owner')
                # Native error is not converted into an empty "successful" image.
                plan.inputs=await _sdk.wrap_inputs(refs,{**args,'max_retain':0})
                with pytest.raises(Exception,match='division'):
                    await session.execute(plan,runtime,capabilities=('raw',),tenant='ati-owner')
                pids.append(session.last_guest_pid)
            finally:await session.kill()
        assert len(set(pids))==2 and os.getpid() not in pids
    asyncio.run(run())


def test_ati_real_outer_declared_image_and_pixel_quirk(monkeypatch):
    monkeypatch.syspath_prepend(str(CORE));monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE','required')
    import execution
    from comfy_secure_nodes import packdb
    classes=packdb.load_pack(PACK.parent,mount_name='custom_nodes.wan_ati_outer').node_mappings
    async def run():
        previous=_sdk.providers.execution_backend
        class Backend:
            sessions=[]
            async def dispatch(self,plan,local_call,runtime):
                # Match the production value-mode admission stage before IPC.
                plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs)
                session=await GuestSession('wan-ati-outer',guest_runtime_root=V2).start()
                assert session.sandbox_kind=='seatbelt';self.sessions.append(session)
                return await session.execute(plan,runtime,capabilities=('raw',),tenant='ati-owner')
        backend=Backend();_sdk.providers.register_execution_backend(backend)
        try:
            cls=classes[ID];schema=cls.GET_SCHEMA()
            args=dict(images=images(2),tracks=tracks(as_list=True),min_radius=0,max_radius=2,max_retain=3)
            finalized,missing,data=execution.get_input_data(args,cls,'1',None)
            assert not missing
            results=await execution._async_map_node_over_list(prompt_id='ati-outer',unique_id='1',
                obj=cls,input_data_all=finalized,func='execute',v3_data=data)
            tensor=results[0].result[0]
            assert schema.outputs[0].io_type=='IMAGE'
            equal(call_old(args),tensor)
            assert float(tensor.max())==255.0
        finally:
            _sdk.providers.register_execution_backend(previous)
            for session in backend.sessions:await session.kill()
    asyncio.run(run())
