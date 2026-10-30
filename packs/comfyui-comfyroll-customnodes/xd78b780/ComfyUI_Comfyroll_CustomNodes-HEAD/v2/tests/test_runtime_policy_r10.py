"""Real SDK controls and metadata accounting; no trained-model/Guest success claims."""
import asyncio
import inspect
import logging
import os
from pathlib import Path
import pytest
from _current_sdk_test_support import module,runtime,sdk,torch
B=module('secure_budget');U=module('secure_upscale');T=module('secure_tensors');A=module('secure_text_artifacts')
@pytest.mark.parametrize('side',[1024,2048])
@pytest.mark.parametrize('batch',range(2,13))
def test_upscale_final_policy_and_uncapped_host_transient(side,batch,caplog):
    caplog.set_level(logging.INFO)
    # Meta tensors assert accounting/admission only, not model inference.
    host=torch.empty((batch,side*4,side*4,3),device='meta')
    assert U._pixels(host)==host.numel()*host.element_size()
    final_bytes=batch*(side*2)**2*3*4
    if final_bytes>2*1024**3:
        # 2048 b11/12 at2x exceed the actual final store dispatch, even
        # though the host's larger4x model transient itself is uncapped.
        with pytest.raises(ValueError,match='runtime'):
            U.resize_projection(side,side,8,'rescale','true',2,1024,3,batch)
    else:
        w,h=U.resize_projection(side,side,8,'rescale','true',2,1024,3,batch)
        assert (w,h)==(side*2,side*2)
        assert any('allocation estimate' in r.message for r in caplog.records)
@pytest.mark.parametrize('dtype',[torch.float16,torch.float32,torch.float64])
def test_absurd_final_output_is_refused_using_actual_dtype(dtype):
    with pytest.raises(ValueError,match='IMAGE|runtime'):
        B.canvas(1,10**9,10**9,3,itemsize=torch.empty((),dtype=dtype).element_size())
    with pytest.raises(ValueError,match='runtime'):
        U.resize_projection(2048,2048,8,'rescale','true',16,1024,3,12)
def test_actual_operator_asset_policy_is_distinct_from_store_policy(monkeypatch):
    monkeypatch.setenv('COMFY_SECURE_MAX_STORE_BYTES','1024')
    B.asset_bytes(2*1024*1024)
    monkeypatch.setenv('COMFY_SECURE_ASSET_READ_MAX','1024')
    with pytest.raises(ValueError,match='asset-read'):B.asset_bytes(1025)
def test_real_default_storage_provider_is_not_an_atomic_stub():
    S=module('secure_storage')
    with runtime():
        with pytest.raises(RuntimeError,match='storage.read and storage.compare_and_set'):S.atomic_storage()
@pytest.mark.parametrize('size',[0,2*1024*1024,17*1024*1024])
def test_real_managed_text_read_uses_asset_policy_not_kv_limit(tmp_path,size):
    import folder_paths
    previous=folder_paths.get_input_directory();root=tmp_path/'input';root.mkdir()
    folder_paths.set_input_directory(str(root))
    (root/'fixtures').mkdir()
    (root/'fixtures/test.txt').write_bytes(b'x'*size)
    async def run():
        with runtime('CR Load Schedule From File',('assets',)):
            return await A._read('input:fixtures','test','txt')
    try:assert asyncio.run(run())=='x'*size
    finally:folder_paths.set_input_directory(previous)
def test_kv_record_write_still_enforces_one_mib():
    with pytest.raises(ValueError,match='KV'):
        A._encode(A._identity('owned','test','txt'),'x'*(1024*1024))

@pytest.mark.parametrize('mode,factor,width',[('rescale',2,64),('rescale',0.5,64),('resize',2,57)])
@pytest.mark.parametrize('supersample',['true','false'])
def test_real_pil_resize_pixels_exact_against_full_original_helper(mode,factor,width,supersample):
    import importlib
    import numpy as np
    from PIL import Image
    original=importlib.import_module('comfyroll_v1_r10.nodes.functions_upscale')
    image=Image.fromarray(np.arange(16*24*3,dtype=np.uint8).reshape(16,24,3))
    expected=original.apply_resize_image(image,24,16,8,mode,supersample,factor,width,64,'bicubic')
    actual=U.apply_resize_image(image,24,16,8,mode,supersample,factor,width,64,'bicubic')
    assert actual.mode==expected.mode and actual.size==expected.size and actual.tobytes()==expected.tobytes()
