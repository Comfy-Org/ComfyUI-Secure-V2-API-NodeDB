"""Source/native/typed and required-guest controls; explicit provider/font roots."""
import asyncio
import contextlib
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import types
import pytest
import numpy as np
import torch

CORE=Path(os.environ['COMFY_CORE_ROOT']).resolve()
OVERLAY=Path(os.environ['MANY_POST_OVERLAY_ROOT']).resolve()
FONT=Path(os.environ['MANY_POST_ARIAL']).resolve()
assert FONT.is_file() and not FONT.is_symlink()
FONT_BYTES=FONT.read_bytes()
assert len(FONT_BYTES)<=2*1024*1024
sys.dont_write_bytecode=True
sys.path[:0]=[str(CORE),str(OVERLAY/'backend')]
from comfy.cli_args import args
args.cpu=True
from comfy_api.latest import io,_sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.packmanifest import FORMAT,encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
import execution
import folder_paths

V2=Path(__file__).resolve().parents[1]
PACK=V2.parent
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path/'__init__.py',submodule_search_locations=[str(path)])
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module
OLD=load('many_post_native',PACK)
NEW=load('many_post_converted',V2)
NATIVE=sys.modules['many_post_native.post_processing_nodes']
SECURE=sys.modules['many_post_converted._secure_nodes']
GUARD=sys.modules['many_post_converted._bounds']
IDS=list(OLD.NODE_CLASS_MAPPINGS)
for cls in NEW.NODE_CLASS_MAPPINGS.values():cls.GET_SCHEMA().validate()

@pytest.fixture(autouse=True)
def assets_and_native_font(tmp_path,monkeypatch):
    root=tmp_path/'input';(root/'post-processing').mkdir(parents=True)
    (root/'post-processing/arial.ttf').write_bytes(FONT_BYTES)
    native=root/'native';native.mkdir();(native/'arial.ttf').write_bytes(FONT_BYTES)
    monkeypatch.setattr(folder_paths,'get_input_directory',lambda:str(root))
    global NATIVE_CWD
    NATIVE_CWD=native

def native(node,inputs):
    cwd=os.getcwd()
    try:
        os.chdir(NATIVE_CWD)
        cls=OLD.NODE_CLASS_MAPPINGS[node]
        return getattr(cls(),cls.FUNCTION)(**inputs)
    finally:os.chdir(cwd)

def rng_reset(seed=193):
    torch.manual_seed(seed);np.random.seed(seed)

async def typed(node,inputs):
    resolver=_sdk.InProcessRefResolver()
    wrapped=await _sdk.wrap_inputs(resolver,inputs,{x.id:x.io_type for x in NEW.NODE_CLASS_MAPPINGS[node].GET_SCHEMA().inputs})
    # This source-differential tier uses the actual canonical in-process asset
    # domain; actual HTTP/guest confinement is measured separately below.
    context=types.SimpleNamespace(assets=_sdk._InProcessAssets())
    with _sdk.bind_runtime(resolver,context,_sdk.InProcessOps()):
        result=await NEW.NODE_CLASS_MAPPINGS[node].execute(**wrapped)
        return (await _sdk.unwrap_outputs(resolver,result)).result

def same(actual,expected):
    assert type(actual) is type(expected)
    if type(expected) is torch.Tensor:
        assert actual.shape==expected.shape and actual.dtype==expected.dtype and actual.device==expected.device
        assert torch.equal(actual.contiguous().reshape(-1).view(torch.uint8),expected.contiguous().reshape(-1).view(torch.uint8))
    elif type(expected) in (tuple,list):
        assert len(actual)==len(expected)
        for a,b in zip(actual,expected):same(a,b)
    else:assert actual==expected

def defaults(node,dtype=torch.float32,shape=(1,16,16,3)):
    cls=OLD.NODE_CLASS_MAPPINGS[node]
    inputs={}
    for name,spec in cls.INPUT_TYPES()['required'].items():
        kind=spec[0]
        if kind=='IMAGE':
            dims=shape[:-1] if node=='PixelSort' and name=='mask' else shape
            count=np.prod(dims)
            inputs[name]=torch.linspace(.03,.97,int(count)).reshape(dims).to(dtype)
            if name=='image2':inputs[name]=~inputs[name] if dtype==torch.bool else 1-inputs[name]
        elif isinstance(kind,list):inputs[name]=kind[0]
        else:inputs[name]=spec[1]['default']
    return inputs

def cases():
    rows=[]
    for node in IDS:
        rows.append((node,{}))
        for name,spec in OLD.NODE_CLASS_MAPPINGS[node].INPUT_TYPES()['required'].items():
            if isinstance(spec[0],list):rows.extend((node,{name:choice}) for choice in spec[0][1:])
    return rows
CASES=cases()

@pytest.mark.parametrize('node,delta',CASES)
@pytest.mark.parametrize('dtype',[torch.float32,torch.float64,torch.float16,torch.bfloat16,torch.uint8,torch.int8,torch.int16,torch.int32,torch.int64,torch.bool])
def test_actual_source_defaults_all_options_dtype_and_native_errors(node,delta,dtype):
    inputs={**defaults(node,dtype),**delta}
    rng_reset()
    try:expected=native(node,inputs)
    except Exception as error:
        rng_reset()
        with pytest.raises(type(error)):asyncio.run(typed(node,inputs))
    else:
        source_torch=torch.random.get_rng_state().clone();source_numpy=np.random.get_state()
        rng_reset();actual=asyncio.run(typed(node,inputs));same(actual,expected)
        assert torch.equal(torch.random.get_rng_state(),source_torch)
        current=np.random.get_state()
        assert current[0]==source_numpy[0] and np.array_equal(current[1],source_numpy[1]) and current[2:]==source_numpy[2:]

@pytest.mark.parametrize('node',IDS)
@pytest.mark.parametrize('shape',[(2,16,16,3),(1,8,12,3),(1,1,8,3),(0,8,8,3),(1,4,4,1),(1,4,4,4)])
def test_source_batch_nonsquare_empty_native_channel_behavior(node,shape):
    inputs=defaults(node,shape=shape)
    rng_reset()
    try:expected=native(node,inputs)
    except Exception as error:
        rng_reset()
        with pytest.raises(type(error)):asyncio.run(typed(node,inputs))
    else:
        rng_reset();same(asyncio.run(typed(node,inputs)),expected)

@pytest.mark.parametrize('node,delta',[('AsciiArt',{'char_size':0}),('AsciiArt',{'font_size':0}),
 ('Blur',{'blur_radius':0}),('PencilSketch',{'blur_radius':0}),('Sharpen',{'sharpen_radius':0}),
 ('KuwaharaBlur',{'blur_radius':0}),('Pixelize',{'pixel_size':128}),('ColorTint',{'strength':0}),
 ('Vignette',{'vignette':1}),('ArithmeticBlend',{'blend_mode':'invalid'})])
def test_native_zero_error_and_identity_controls(node,delta):
    inputs={**defaults(node),**delta};rng_reset()
    try:expected=native(node,inputs)
    except Exception as error:
        rng_reset()
        with pytest.raises(type(error)):asyncio.run(typed(node,inputs))
    else:rng_reset();same(asyncio.run(typed(node,inputs)),expected)

def test_full_schema_census_permissions_source_algorithm_ast_and_resources():
    assert len(IDS)==23 and IDS==list(NEW.NODE_CLASS_MAPPINGS)
    assert list(asyncio.run(NEW.PostProcessingExtension().get_node_list()))==list(NEW.NODE_CLASS_MAPPINGS.values())
    import ast
    a=ast.parse((PACK/'post_processing_nodes.py').read_bytes());b=ast.parse((V2/'post_processing_nodes.py').read_bytes())
    allowed={'AsciiArt','ascii_art_effect'}
    for left,right in zip(a.body,b.body):
        if isinstance(left,(ast.ClassDef,ast.FunctionDef)) and left.name in allowed:continue
        assert ast.dump(left,include_attributes=False)==ast.dump(right,include_attributes=False)
    source=(PACK/'post_processing_nodes.py').read_text()
    replacements={
        'result_b = ascii_art_effect(img_b, char_size, font_size)':"result_b = ascii_art_effect(img_b, char_size, font_size, getattr(self, '_secure_font', None))",
        'def ascii_art_effect(image: torch.Tensor, char_size: int, font_size: int):':'def ascii_art_effect(image: torch.Tensor, char_size: int, font_size: int, font_data=None):',
        '    font = ImageFont.truetype("arial.ttf", font_size)':'    if font_data is not None:\n        font_data.seek(0)\n    font = ImageFont.truetype(font_data if font_data is not None else "arial.ttf", font_size)'
    }
    for old,new in replacements.items():
        assert source.count(old)==1
        source=source.replace(old,new)
    assert source==(V2/'post_processing_nodes.py').read_text()
    for node,cls in NEW.NODE_CLASS_MAPPINGS.items():
        s=cls.GET_SCHEMA()
        assert s.node_id==node and s.category==OLD.NODE_CLASS_MAPPINGS[node].CATEGORY
        original=OLD.NODE_CLASS_MAPPINGS[node].INPUT_TYPES()['required']
        assert [x.id for x in s.inputs]==list(original)
        assert [x.io_type for x in s.outputs]==list(OLD.NODE_CLASS_MAPPINGS[node].RETURN_TYPES)
        assert set(cls.SDK_PERMISSIONS)==({'raw','inspect','assets'} if node=='AsciiArt' else {'raw','inspect'})

def test_metadata_only_projection_before_raw_zero_channels_broadcast_resize_and_kernel(monkeypatch):
    async def forbidden(value):raise AssertionError('raw called before projection')
    monkeypatch.setattr(GUARD,'raw',forbidden)
    async def huge(value):return (1,10_000,10_000,0)
    monkeypatch.setattr(GUARD,'describe',huge)
    with pytest.raises(ValueError,match='budget'):asyncio.run(NEW.NODE_CLASS_MAPPINGS['CannyEdgeMask'].execute(**defaults('CannyEdgeMask')))
    with pytest.raises(ValueError,match='budget'):GUARD.plan('Vignette',[(1,1,4096,3)],{'vignette':1})
    with pytest.raises(ValueError,match='budget'):GUARD.plan('Blend',[(0,4096,4096,0),(1,2,2,3)],{})
    with pytest.raises(ValueError,match='budget'):GUARD.plan('ArithmeticBlend',[(1,4096,1,3),(1,1,4096,3)],{})
    with pytest.raises(ValueError,match='workload'):GUARD.plan('Blur',[(1,16,16,3)],{'blur_radius':2**40})
    assert GUARD.plan('Vignette',[(1,1,8,3)],{'vignette':1})['output_bytes']==1*8*8*3*16

def test_font_bounded_range_growth_short_read_and_recovery(monkeypatch):
    class Assets:
        def __init__(self,mode):self.mode=mode;self.calls=0
        async def resolve(self,folder,name):assert (folder,name)==('input','post-processing/arial.ttf');return object()
        async def size(self,ref):self.calls+=1;return 4 if self.calls==1 else (5 if self.mode=='size' else 4)
        async def read_range(self,ref,offset,length):
            return (b'x' if self.mode=='tail' else b'') if offset==4 else (b'123' if self.mode=='short' else b'1234')
    for mode in ('size','tail','short'):
        assets=Assets(mode)
        monkeypatch.setattr(GUARD.sdk,'ctx',lambda:types.SimpleNamespace(assets=assets))
        with pytest.raises(ValueError,match='changed'):asyncio.run(GUARD.font_bytes())
    monkeypatch.setattr(GUARD.sdk,'ctx',lambda:types.SimpleNamespace(assets=Assets('good')))
    assert asyncio.run(GUARD.font_bytes())==b'1234'

RNG_FIXTURE='''from comfy_api.latest import io
import numpy as np
import torch
class ResetFixture(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="PostProcessingTestRNGOnly",inputs=[io.Int.Input("seed",default=193)],outputs=[io.Int.Output()])
    @classmethod
    def execute(cls,seed):
        np.random.seed(seed)
        torch.manual_seed(seed)
        return io.NodeOutput(seed)
'''

def rng_class(package,root):
    path=root/'_rng_test_fixture.py'
    path.write_text(RNG_FIXTURE)
    name=package.__name__+'._rng_test_fixture'
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    cls=module.ResetFixture;cls.GET_SCHEMA().validate();return cls

async def outer(cls,inputs,prompt='post-processing-acceptance'):
    cls.GET_SCHEMA()
    rows=await execution._async_map_node_over_list(prompt,'1',cls,{k:[v] for k,v in inputs.items()},cls.FUNCTION)
    rows=await execution.resolve_map_node_over_list_results(rows)
    return rows[0].result

def test_all23_options_two_fresh_required_guests_true_outer_rng_native_errors_denial_recovery(tmp_path):
    async def run():
        prior=_sdk.providers.execution_backend;pids=set()
        try:
            for generation in range(2):
                root=tmp_path/('render-'+str(generation));shutil.copytree(V2,root)
                package=load('many_post_render_'+str(generation),root)
                reset=rng_class(package,root)
                session=await GuestSession('many-post-'+str(generation),guest_runtime_root=root).start()
                assert session.sandbox_kind=='seatbelt'
                capabilities=()
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        return await session.execute(plan,runtime,capabilities=capabilities,tenant='post-processing-local-fixture')
                _sdk.providers.register_execution_backend(Backend())
                try:
                    for node,delta in CASES:
                        inputs={**defaults(node),**delta}
                        rng_reset()
                        try:expected=native(node,inputs)
                        except Exception as error:expected_error=str(error)
                        else:expected_error=None
                        capabilities=();same(await outer(reset,{'seed':193}),(193,))
                        cls=package.NODE_CLASS_MAPPINGS[node];capabilities=cls.SDK_PERMISSIONS
                        if expected_error is None:same(await outer(cls,inputs),expected)
                        else:
                            with pytest.raises(Exception) as caught:await outer(cls,inputs)
                            assert expected_error in str(caught.value)
                    for node in ('Dissolve','FilmGrain'):
                        inputs=defaults(node);rng_reset()
                        expected=[native(node,inputs),native(node,inputs)]
                        capabilities=();await outer(reset,{'seed':193})
                        capabilities=package.NODE_CLASS_MAPPINGS[node].SDK_PERMISSIONS
                        actual=[await outer(package.NODE_CLASS_MAPPINGS[node],inputs),await outer(package.NODE_CLASS_MAPPINGS[node],inputs)]
                        same(actual,expected)
                        assert not torch.equal(actual[0][0],actual[1][0])
                    for node,delta,shape,dtype in [
                        ('AsciiArt',{'char_size':0},(1,16,16,3),torch.float32),
                        ('AsciiArt',{'font_size':0},(1,16,16,3),torch.float32),
                        ('Vignette',{'vignette':1},(1,8,12,3),torch.float32),
                        ('CannyEdgeMask',{},(1,16,16,3),torch.bfloat16)]:
                        inputs={**defaults(node,dtype,shape),**delta}
                        with pytest.raises(Exception) as source_error:native(node,inputs)
                        capabilities=package.NODE_CLASS_MAPPINGS[node].SDK_PERMISSIONS
                        with pytest.raises(Exception) as guest_error:await outer(package.NODE_CLASS_MAPPINGS[node],inputs)
                        assert str(source_error.value) in str(guest_error.value)
                    # Genuine metadata-only cases must be refused before raw
                    # transport, including an empty-channel allocation trap.
                    capabilities=('inspect',)
                    with pytest.raises(Exception,match='budget'):
                        await outer(package.NODE_CLASS_MAPPINGS['CannyEdgeMask'],
                            {**defaults('CannyEdgeMask'),'image':torch.empty(1,10000,10000,0,device='meta')})
                    with pytest.raises(Exception,match='budget'):
                        await outer(package.NODE_CLASS_MAPPINGS['ArithmeticBlend'],
                            {'image1':torch.empty(1,4096,1,3,device='meta'),'image2':torch.empty(1,1,4096,3,device='meta'),'blend_mode':'add'})
                    cls=package.NODE_CLASS_MAPPINGS['Solarize'];inputs=defaults('Solarize')
                    for granted,missing in [(('inspect',),'raw'),(('raw',),'inspect')]:
                        capabilities=granted
                        with pytest.raises(Exception,match=missing):await outer(cls,inputs)
                    capabilities=('raw','inspect')
                    with pytest.raises(Exception,match='assets'):
                        await outer(package.NODE_CLASS_MAPPINGS['AsciiArt'],defaults('AsciiArt'))
                    same(await outer(cls,inputs),native('Solarize',inputs))
                    capabilities=('raw','inspect','assets')
                    same(await outer(package.NODE_CLASS_MAPPINGS['AsciiArt'],defaults('AsciiArt')),native('AsciiArt',defaults('AsciiArt')))
                    pids.add(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(prior)
        assert len(pids)==2 and os.getpid() not in pids
        print('POST_REQUIRED_GUEST_PIDS='+json.dumps(sorted(pids)))
    asyncio.run(run())

def test_production_cloud_execution_backend_all23_native_outputs(tmp_path):
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        root=tmp_path/'production';shutil.copytree(V2,root)
        package=load('many_post_production',root);reset=rng_class(package,root)
        backend=CloudExecutionBackend();prior=_sdk.providers.execution_backend
        _sdk.providers.register_execution_backend(backend)
        try:
            for node in IDS:
                inputs=defaults(node);rng_reset();expected=native(node,inputs)
                same(await outer(reset,{'seed':193},'many-post-production'),(193,))
                same(await outer(package.NODE_CLASS_MAPPINGS[node],inputs,'many-post-production'),expected)
        finally:
            await backend.guests.shutdown();_sdk.providers.register_execution_backend(prior)
    asyncio.run(run())
