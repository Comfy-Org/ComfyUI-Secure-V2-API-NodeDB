"""Exact VACE frame/mask assembly; no VACE model or sampling is exercised."""
import ast
import asyncio
import copy
import importlib.util
import os
from pathlib import Path
import shutil
import sys
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

ID='WanVideoVACEStartToEndFrame'
INPUT_TYPES={'start_image':'IMAGE','end_image':'IMAGE','control_images':'IMAGE','inpaint_mask':'MASK'}


def original():
    tree=ast.parse((PACK/'nodes_utility.py').read_text())
    cls=next(item for item in tree.body if isinstance(item,ast.ClassDef) and item.name==ID)
    namespace={'torch':torch,'common_upscale':common_upscale}
    exec(compile(ast.Module(body=[cls],type_ignores=[]),str(PACK/'nodes_utility.py'),'exec'),namespace)
    return namespace[ID]


def candidate(root=V2):
    name='_wan_vace_frame_'+str(id(root))
    spec=importlib.util.spec_from_file_location(name,root/'__init__.py',submodule_search_locations=[str(root)])
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module.NODE_CLASS_MAPPINGS[ID]


def image(batch,height,width,channels=3,dtype=torch.float32):
    return torch.linspace(0,1,batch*height*width*channels,dtype=dtype).reshape(batch,height,width,channels)


def cases():
    values=[]
    for dtype in (torch.float32,torch.float64):
        for frames in (1,5,9):
            for start,end in ((image(2,4,6,dtype=dtype),None),(None,image(3,4,6,dtype=dtype)),
                    (image(2,4,6,dtype=dtype),image(3,3,5,dtype=dtype))):
                for control in (None,image(7,2,3,dtype=dtype)):
                    for mask in (None,image(1,3,5,1,dtype)[...,0],image(12,4,6,1,dtype)[...,0]):
                        values.append(dict(num_frames=frames,empty_frame_level=.25,start_image=start,end_image=end,
                            control_images=control,inpaint_mask=mask,start_index=2,end_index=-1))
        for control_frames in (0,1,8):
            values.append(dict(num_frames=5,empty_frame_level=.75,control_images=image(control_frames,4,6,dtype=dtype)))
    values.extend(dict(num_frames=5,empty_frame_level=.5,start_image=image(2,4,6),end_image=image(3,3,5),
        start_index=start,end_index=end) for start,end in ((0,0),(0,3),(0,20),(4,-9),(9,-1)))
    return values


def assert_output(expected,actual):
    assert len(actual)==2
    for left,right in zip(expected,actual):
        assert left.shape==right.shape and left.dtype==right.dtype and left.device==right.device
        assert torch.equal(left,right)


async def direct(inputs):
    refs=_sdk.InProcessRefResolver()
    plan=_sdk.ExecutionPlan('vace-frame','1',ID,permissions=('raw',),input_types=INPUT_TYPES)
    runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
    wrapped=await _sdk.wrap_inputs(refs,inputs,INPUT_TYPES)
    with _sdk.bind_runtime(runtime.refs,runtime.ctx,runtime.ops):result=await candidate().execute(**wrapped)
    return (await _sdk.unwrap_outputs(refs,result)).result


def test_frame_schema_exact_options_defaults_and_raw_refs():
    old=original();new=candidate();schema=new.GET_SCHEMA()
    assert schema.category==old.CATEGORY and schema.description==old.DESCRIPTION
    assert schema.display_name=='WanVideo VACE Start To End Frame'
    specs=old.INPUT_TYPES()
    assert [field.id for field in schema.inputs]==[name for fields in specs.values() for name in fields]
    for field in schema.inputs:
        spec=specs['optional' if field.optional else 'required'][field.id]
        assert field.io_type==spec[0]
        for key,value in (spec[1] if len(spec)>1 else {}).items():assert getattr(field,key)==value
    assert tuple(output.io_type for output in schema.outputs)==old.RETURN_TYPES
    assert tuple(output.display_name for output in schema.outputs)==old.RETURN_NAMES
    assert new.SDK_REFS is True and new.SDK_PERMISSIONS==('raw',)


def test_vace_frame_order_lanczos_nearest_exact_masks_and_padding_pixels():
    async def run():
        for inputs in cases():
            expected=original()().process(**copy.deepcopy(inputs))
            actual=await direct(copy.deepcopy(inputs))
            assert_output(expected,actual)
    asyncio.run(run())


def test_vace_frame_source_inputs_not_mutated_and_mask_precedence():
    inputs=dict(num_frames=5,empty_frame_level=.5,start_image=image(2,4,6),end_image=image(3,3,5),
        control_images=image(7,2,3),inpaint_mask=image(1,3,5,1)[...,0])
    before=copy.deepcopy(inputs)
    actual=asyncio.run(direct(inputs))
    assert_output(original()().process(**copy.deepcopy(before)),actual)
    for key,value in inputs.items():
        if isinstance(value,torch.Tensor):assert torch.equal(value,before[key])


@pytest.mark.parametrize('inputs',[
    dict(num_frames=5,empty_frame_level=.5),
    dict(num_frames=-1,empty_frame_level=.5,start_image=image(1,2,3)),
    dict(num_frames=5,empty_frame_level=.5,start_image=image(1,2,3,4)),
    dict(num_frames=5,empty_frame_level=.5,start_image=image(1,2,3),inpaint_mask=torch.empty(0,2,3)),
    dict(num_frames=5,empty_frame_level=.5,start_image=image(2,4,6),end_image=image(3,3,5),start_index=-1),
])
def test_vace_frame_bounded_native_error_equivalence(inputs):
    def failure(fn):
        try:fn()
        except Exception as error:return type(error).__name__,str(error)
        raise AssertionError('Expected native failure')
    expected=failure(lambda:original()().process(**copy.deepcopy(inputs)))
    actual=failure(lambda:asyncio.run(direct(copy.deepcopy(inputs))))
    assert actual==expected


def test_vace_frame_projected_bounds_before_output_allocation(monkeypatch):
    class RawImage:
        async def raw(self):return torch.tensor(1.).expand(1,256,256,3)
    def forbidden(*args,**kwargs):raise AssertionError('Must refuse before output allocation')
    monkeypatch.setattr(torch,'ones',forbidden)
    async def run():
        with pytest.raises(ValueError,match='projected'):
            await candidate().execute(10000,.5,start_image=RawImage())
    asyncio.run(run())


def guest_cases():
    return [cases()[0],cases()[17],cases()[36],cases()[-7],cases()[-1]]


def test_vace_frame_real_raw_guest_denial_and_fresh_filesystem(tmp_path):
    fresh=tmp_path/'fresh';shutil.copytree(V2,fresh)
    async def run():
        for root in (V2,fresh):
            cls=candidate(root);session=await GuestSession('wan-vace-frame',guest_runtime_root=root).start()
            try:
                for inputs in guest_cases():
                    refs=_sdk.InProcessRefResolver()
                    plan=_sdk.ExecutionPlan('wan-vace-frame','1',ID,node_module=cls.__module__,input_mode='refs',
                        input_types=INPUT_TYPES,permissions=('raw',),tier='sandbox',
                        inputs=await _sdk.wrap_inputs(refs,inputs,INPUT_TYPES))
                    runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                    with pytest.raises(Exception,match='raw'):
                        await session.execute(plan,runtime,capabilities=())
                    actual=await session.execute(plan,runtime,capabilities=('raw',))
                    values=await _sdk.unwrap_outputs(refs,actual)
                    assert_output(original()().process(**copy.deepcopy(inputs)),values.result)
                assert session.last_guest_pid not in (None,os.getpid())
            finally:await session.kill()
    asyncio.run(run())


def test_vace_frame_public_outer_image_mask_types_and_pixels(monkeypatch):
    monkeypatch.syspath_prepend(str(CORE))
    import execution
    cls=packdb.load_pack(PACK.parent,mount_name='custom_nodes.wan_vace_frame_outer').node_mappings[ID]
    async def run():
        previous=_sdk.providers.execution_backend
        class Backend:
            sessions=[]
            async def dispatch(self,plan,local_call,runtime):
                assert plan.input_mode=='refs' and plan.input_types['inpaint_mask']=='MASK'
                plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                session=await GuestSession('vace-frame-outer',guest_runtime_root=V2).start()
                self.sessions.append(session)
                return await session.execute(plan,runtime,capabilities=('raw',))
        backend=Backend();_sdk.providers.register_execution_backend(backend)
        try:
            for inputs in guest_cases():
                cls.GET_SCHEMA()
                finalized,missing,data=execution.get_input_data(copy.deepcopy(inputs),cls,'1',None)
                assert not missing
                values=await execution._async_map_node_over_list(prompt_id='vace-frame-outer',unique_id='1',obj=cls,
                    input_data_all=finalized,func='execute',v3_data=data)
                assert tuple(cls.RETURN_TYPES)==('IMAGE','MASK')
                assert_output(original()().process(**copy.deepcopy(inputs)),values[0].result)
        finally:
            _sdk.providers.register_execution_backend(previous)
            for session in backend.sessions:await session.kill()
    asyncio.run(run())
