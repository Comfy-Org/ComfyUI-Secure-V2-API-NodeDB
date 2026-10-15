"""Pixel-exact public image-ref utility, not model inference evidence."""
import ast
import asyncio
import copy
import importlib.util
import os
from pathlib import Path
import shutil
import sys
import numpy as np
import pytest
import torch

sys.dont_write_bytecode=True
V2=Path(__file__).resolve().parents[1]
PACK=V2.parent
CORE=Path('/Users/ben/comfy/ComfyUI-secure-nodes')
BACKEND=Path('/Users/ben/comfy/ComfyUI_secure_nodes/backend')
for path in (CORE,BACKEND):sys.path.insert(0,str(path))
os.environ.setdefault('COMFY_CORE_ROOT',str(CORE))
from comfy_api.latest import _sdk
from comfy.utils import common_upscale
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes import packdb

ID='WanVideoImageResizeToClosest'


def original():
    tree=ast.parse((PACK/'nodes_utility.py').read_text())
    cls=next(item for item in tree.body if isinstance(item,ast.ClassDef) and item.name==ID)
    namespace={'np':np,'VAE_STRIDE':(4,8,8),'PATCH_SIZE':(1,2,2),'common_upscale':common_upscale}
    exec(compile(ast.Module(body=[cls],type_ignores=[]),str(PACK/'nodes_utility.py'),'exec'),namespace)
    return namespace[ID]


def candidate():
    spec=importlib.util.spec_from_file_location('_wan_image_refs',V2/'__init__.py',submodule_search_locations=[str(V2)])
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module.NODE_CLASS_MAPPINGS[ID]


def cases():
    return [dict(image=torch.linspace(0,1,batch*height*width*channels).reshape(batch,height,width,channels).to(dtype),
        generation_width=target_width,generation_height=target_height,aspect_ratio_preservation=mode)
        for batch,height,width,channels in [(1,7,12,3),(2,12,7,4),(1,8,8,1)]
        for dtype in [torch.float32,torch.float64]
        for target_width,target_height in [(64,64),(128,96),(96,128)]
        for mode in ['keep_input','stretch_to_new','crop_to_new']]


def assert_output(expected,actual):
    assert actual[1:]==expected[1:]
    assert actual[0].shape==expected[0].shape
    assert actual[0].dtype==expected[0].dtype
    assert torch.equal(actual[0],expected[0])


def test_exact_schema_for_public_ref_resize():
    old=original();new=candidate();schema=new.GET_SCHEMA()
    assert schema.category==old.CATEGORY and schema.description==old.DESCRIPTION
    assert schema.display_name=='WanVideo Image Resize To Closest'
    for field in schema.inputs:
        spec=old.INPUT_TYPES()['required'][field.id]
        assert (field.options if isinstance(spec[0],list) else field.io_type)==spec[0]
        for key,value in (spec[1] if len(spec)>1 else {}).items():assert getattr(field,key)==value
    assert tuple(output.io_type for output in schema.outputs)==old.RETURN_TYPES
    assert tuple(output.display_name for output in schema.outputs)==old.RETURN_NAMES
    assert new.SDK_REFS is True and new.SDK_PERMISSIONS==()


def test_all_modes_aspect_batch_channels_exact_lanczos_pixels():
    old=original();new=candidate()
    async def run():
        for inputs in cases():
            expected=old().process(**inputs)
            refs=_sdk.InProcessRefResolver();plan=_sdk.ExecutionPlan('resize','1',ID,permissions=())
            runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
            wrapped=await _sdk.wrap_inputs(refs,inputs,{'image':'IMAGE'})
            with _sdk.bind_runtime(runtime.refs,runtime.ctx,runtime.ops):actual=await new.execute(**wrapped)
            output=await _sdk.unwrap_outputs(refs,actual)
            assert_output(expected,output.result)
    asyncio.run(run())


def test_real_zero_capability_guest_resize_fresh_filesystem(tmp_path):
    fresh=tmp_path/'fresh/comfyui-wanvideowrapper/x088128b'/PACK.name/'v2'
    shutil.copytree(V2,fresh)
    async def run():
        for index,root in enumerate((V2,fresh)):
            loaded=packdb.load_pack(root.parent.parent,
                mount_name=f'custom_nodes.wan_resize_guest{index}')
            cls=loaded.node_mappings[ID]
            session=await GuestSession('wan-resize',guest_runtime_root=root).start()
            try:
                for inputs in cases()[::18]:
                    refs=_sdk.InProcessRefResolver()
                    plan=_sdk.ExecutionPlan('wan-resize','1',ID,node_module=cls.__module__,
                        input_mode='refs',input_types={'image':'IMAGE'},permissions=(),
                        inputs=await _sdk.wrap_inputs(refs,inputs,{'image':'IMAGE'}),tier='sandbox')
                    runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                    actual=await session.execute(plan,runtime,capabilities=())
                    output=await _sdk.unwrap_outputs(refs,actual)
                    assert_output(original()().process(**inputs),output.result)
                assert session.last_guest_pid not in (None,os.getpid())
            finally:await session.kill()
    asyncio.run(run())


def test_projected_ref_resize_refuses_before_resize_call():
    class Image:
        async def spatial_shape(self):return 1024,1024
        async def batch_size(self):return 2
        async def resize(self,*args,**kwargs):raise AssertionError('Allocation must not happen')
    async def run():
        with pytest.raises(ValueError,match='projected'):
            await candidate().execute(Image(),8096,8096,'keep_input')
        with pytest.raises(UnboundLocalError):
            await candidate().execute(Image(),64,64,'unknown')
    asyncio.run(run())


def test_public_outer_resize_output_and_typed_input_contract(monkeypatch):
    monkeypatch.syspath_prepend(str(CORE))
    import execution
    cls=packdb.load_pack(PACK.parent,mount_name='custom_nodes.wan_resize_outer').node_mappings[ID]
    async def run():
        previous=_sdk.providers.execution_backend
        class Backend:
            sessions=[]
            async def dispatch(self,plan,local_call,runtime):
                plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                session=await GuestSession('resize-outer',guest_runtime_root=V2).start()
                self.sessions.append(session)
                return await session.execute(plan,runtime,capabilities=())
        backend=Backend();_sdk.providers.register_execution_backend(backend)
        try:
            for inputs in [cases()[0],cases()[18],cases()[-1]]:
                cls.GET_SCHEMA()
                finalized,missing,data=execution.get_input_data(inputs,cls,'1',None)
                assert not missing
                values=await execution._async_map_node_over_list(prompt_id='resize-outer',unique_id='1',obj=cls,
                    input_data_all=finalized,func='execute',v3_data=data)
                assert_output(original()().process(**inputs),values[0].result)
        finally:
            _sdk.providers.register_execution_backend(previous)
            for session in backend.sessions:await session.kill()
    asyncio.run(run())
