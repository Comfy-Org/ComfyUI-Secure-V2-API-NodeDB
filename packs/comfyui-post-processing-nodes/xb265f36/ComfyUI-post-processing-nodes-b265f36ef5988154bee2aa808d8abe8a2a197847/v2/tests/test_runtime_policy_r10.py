"""Current typed IMAGE publication and real managed-byte transport, no shim API."""
import asyncio
import importlib
import os
from pathlib import Path
import sys
import types
import numpy as np
import pytest
import torch
from comfy_api.latest import sdk,_sdk
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
for name,path in [('post_r10',V2),('post_v1_r10',PACK)]:
    pkg=types.ModuleType(name);pkg.__path__=[str(path)];sys.modules[name]=pkg
N=importlib.import_module('post_v1_r10.post_processing_nodes')
S=importlib.import_module('post_r10._secure_nodes');B=importlib.import_module('post_r10._bounds')
@pytest.mark.parametrize('node',['HSVThresholdMask','CannyEdgeMask'])
@pytest.mark.parametrize('side',[1024,2048])
@pytest.mark.parametrize('batch',range(2,13))
def test_actual_bhw1_public_image_adapter_byte_and_dtype_exact(node,side,batch):
    # This matrix executes both actual unchanged V1 and typed SDK methods.
    ramp=torch.linspace(0,1,side*side*3).reshape(1,side,side,3)
    image=ramp.repeat(batch,1,1,1);native=N.NODE_CLASS_MAPPINGS[node]
    args={'image':image}
    for key,spec in native.INPUT_TYPES()['required'].items():
        if key=='image':continue
        args[key]=spec[0][0] if isinstance(spec[0],list) else spec[1]['default']
    expected=getattr(native(),native.FUNCTION)(**args)[0]
    async def run():
        refs=_sdk.InProcessRefResolver();plan=sdk.ExecutionPlan(prompt_id='r10',node_id='1',node_type=node,prompt={},extra_pnginfo={},permissions=S.NODE_CLASS_MAPPINGS[node].SDK_PERMISSIONS)
        ctx=_sdk.InProcessCtxProvider().build(plan)
        with _sdk.bind_runtime(refs,ctx,_sdk.InProcessOps()):
            try:
                result=await S.NODE_CLASS_MAPPINGS[node].execute(**{**args,'image':await sdk.ImageRef.from_value(image)})
                ref=result.result[0];assert ref.kind=='IMAGE'
                return await ref.raw()
            finally:refs.clear()
    actual=asyncio.run(run())
    assert actual.shape==expected.shape+(1,) and actual.dtype==expected.dtype
    assert actual.numpy().tobytes()==expected.numpy().tobytes()
@pytest.mark.parametrize('size',[0,2*1024*1024+1,17*1024*1024])
def test_actual_font_bytes_transport_including_empty_and_over_range_chunk(tmp_path,size):
    import folder_paths
    previous=folder_paths.get_input_directory();root=tmp_path/'input';(root/'post-processing').mkdir(parents=True)
    folder_paths.set_input_directory(str(root));(root/'post-processing/arial.ttf').write_bytes(b'x'*size)
    # Synthetic content tests only transport, not font decoding/Arial parity.
    async def run():
        refs=_sdk.InProcessRefResolver();plan=sdk.ExecutionPlan(prompt_id='r10',node_id='1',node_type='AsciiArt',prompt={},extra_pnginfo={},permissions=('assets',))
        with _sdk.bind_runtime(refs,_sdk.InProcessCtxProvider().build(plan),_sdk.InProcessOps()):
            try:return await B.font_bytes()
            finally:refs.clear()
    try:assert asyncio.run(run())==b'x'*size
    finally:folder_paths.set_input_directory(previous)
def test_operator_font_read_limit_and_native_kernel_scratch(monkeypatch):
    monkeypatch.setenv('COMFY_SECURE_ASSET_READ_MAX','1024')
    with pytest.raises(ValueError,match='asset-read'):B.asset_bytes(1025)
    plan=B.plan('Blur',[torch.empty((1,16,16,3),dtype=torch.float64,device='meta')],{'blur_radius':2**20})
    assert plan['workspace_bytes']>2*1024**3 # accounting only, no huge native allocation
