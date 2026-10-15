"""Opaque forwarding evidence; no models or sampling methods execute."""
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
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes import packdb

ID='WanVideoSamplerExtraArgs'


def original():
    tree=ast.parse((PACK/'nodes_sampler.py').read_text())
    cls=next(item for item in tree.body if isinstance(item,ast.ClassDef) and item.name==ID)
    namespace={'rope_functions':['default','comfy','comfy_chunked']}
    exec(compile(ast.Module(body=[cls],type_ignores=[]),str(PACK/'nodes_sampler.py'),'exec'),namespace)
    return namespace[ID]


def candidate(root=V2):
    name='_wan_pass_'+str(id(root))
    spec=importlib.util.spec_from_file_location(name,root/'__init__.py',submodule_search_locations=[str(root)])
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module.NODE_CLASS_MAPPINGS[ID]


class ModelSentinel:
    def clone(self):raise AssertionError('Settings composition must not operate on a model')
    def __call__(self,*args,**kwargs):raise AssertionError('No model inference authorized')


class NoOps:
    async def apply(self,*args,**kwargs):raise AssertionError('No broker operation needed for forwarding')


def inputs(model):
    return dict(riflex_freq_index=6,feta_args={'weight':.5},context_options={'vae':model,'context_frames':81},
        cache_args={'cache_type':'TeaCache','start_step':1},slg_args={'blocks':[1,2]},rope_function='comfy_chunked',
        loop_args={'loop':True},experimental_args={'x':'setting'},unianimate_poses={'model':model},
        fantasytalking_embeds={'audio':torch.arange(12,dtype=torch.float64).reshape(1,3,4)},
        uni3c_embeds={'controlnet':model},multitalk_embeds={'audio_scale':1.})


def assert_output(expected,actual,model):
    assert isinstance(actual,tuple) and len(actual)==1
    result=actual[0]
    assert list(result)==list(expected)
    for key,value in expected.items():
        if isinstance(value,dict):
            assert list(result[key])==list(value)
            for name,item in value.items():
                if item is model:assert result[key][name] is model
                elif isinstance(item,torch.Tensor):
                    assert result[key][name].shape==item.shape and result[key][name].dtype==item.dtype
                    assert torch.equal(result[key][name],item)
                else:assert result[key][name]==item
        else:assert result[key]==value


def test_passthrough_schema_all_optional_contract_exact():
    old=original();new=candidate();schema=new.GET_SCHEMA()
    assert schema.node_id==ID and schema.category==old.CATEGORY
    assert schema.display_name=='WanVideoSampler v2 Extra Args'
    specs=old.INPUT_TYPES()['optional']
    assert [field.id for field in schema.inputs]==list(specs)
    assert all(field.optional for field in schema.inputs)
    for field in schema.inputs:
        spec=specs[field.id]
        assert (field.options if isinstance(spec[0],list) else field.io_type)==spec[0]
        for key,value in (spec[1] if len(spec)>1 else {}).items():assert getattr(field,key)==value
    assert tuple(field.io_type for field in schema.outputs)==old.RETURN_TYPES
    assert tuple(field.display_name for field in schema.outputs)==old.RETURN_NAMES
    assert new.SDK_REFS is True and new.SDK_PERMISSIONS==()


def test_passthrough_direct_native_omissions_ignored_positional_args_and_aliases():
    model=ModelSentinel();values=inputs(model)
    new=candidate();old=original()()
    assert new.execute().result==old.process()==({},)
    assert new.execute(1,2).result==old.process(1,2)==({},)
    for fields in [values,{'rope_function':'unrecognized','arbitrary':None},{'riflex_freq_index':None}]:
        result=new.execute(**fields).result
        assert list(result[0])==list(fields)
        for key,value in fields.items():assert result[0][key] is value
    with pytest.raises(ValueError,match='4096'):
        new.execute(**{str(index):None for index in range(4097)})
    with pytest.raises(ValueError,match='64 KiB'):
        new.execute(rope_function='x'*65537)


def test_passthrough_in_process_refs_are_not_resolved_or_operated_on():
    model=ModelSentinel();values=inputs(model)
    async def run():
        refs=_sdk.InProcessRefResolver()
        wrapped=await _sdk.wrap_inputs(refs,values)
        plan=_sdk.ExecutionPlan('pass','1',ID,permissions=())
        runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=NoOps())
        with _sdk.bind_runtime(runtime.refs,runtime.ctx,runtime.ops):result=candidate().execute(**wrapped)
        # The result contains the very same ref/payload arguments; host-only
        # reconstruction below is not guest materialization authority.
        for key,value in wrapped.items():assert result.result[0][key] is value
        unwrapped=await _sdk.unwrap_outputs(refs,result)
        assert_output(values,unwrapped.result,model)
    asyncio.run(run())


def test_passthrough_real_zero_capability_guest_and_fresh_worker(tmp_path):
    fresh=tmp_path/'fresh';shutil.copytree(V2,fresh)
    async def run():
        for root in (V2,fresh):
            model=ModelSentinel();values=inputs(model);cls=candidate(root)
            refs=_sdk.InProcessRefResolver()
            plan=_sdk.ExecutionPlan('wan-pass','1',ID,node_module=cls.__module__,input_mode='refs',
                permissions=(),tier='sandbox',inputs=await _sdk.wrap_inputs(refs,values))
            runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=NoOps())
            session=await GuestSession('wan-pass',guest_runtime_root=root).start()
            try:
                actual=await session.execute(plan,runtime,capabilities=())
                result=await _sdk.unwrap_outputs(refs,actual)
                assert_output(values,result.result,model)
                assert session.last_guest_pid not in (None,os.getpid())
            finally:await session.kill()
    asyncio.run(run())


def test_passthrough_public_outer_custom_output_and_opaque_identity(monkeypatch):
    monkeypatch.syspath_prepend(str(CORE))
    import execution
    cls=packdb.load_pack(PACK.parent,mount_name='custom_nodes.wan_pass_outer').node_mappings[ID]
    async def run():
        previous=_sdk.providers.execution_backend
        model=ModelSentinel();values=inputs(model)
        class Backend:
            sessions=[]
            async def dispatch(self,plan,local_call,runtime):
                assert plan.input_mode=='refs' and plan.permissions==()
                plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                session=await GuestSession('pass-outer',guest_runtime_root=V2).start()
                self.sessions.append(session)
                return await session.execute(plan,runtime,capabilities=())
        backend=Backend();_sdk.providers.register_execution_backend(backend)
        try:
            cls.GET_SCHEMA()
            finalized,missing,data=execution.get_input_data(values,cls,'1',None)
            assert not missing
            result=await execution._async_map_node_over_list(prompt_id='pass-outer',unique_id='1',obj=cls,
                input_data_all=finalized,func='execute',v3_data=data)
            assert tuple(cls.RETURN_TYPES)==('WANVIDSAMPLEREXTRAARGS',)
            assert_output(values,result[0].result,model)
        finally:
            _sdk.providers.register_execution_backend(previous)
            for session in backend.sessions:await session.kill()
    asyncio.run(run())
