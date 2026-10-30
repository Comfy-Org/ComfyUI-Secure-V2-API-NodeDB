"""Accepted PNG Preview mapping; Save/full format semantics remain explicit refusals."""
import asyncio
import importlib
import inspect
from pathlib import Path
import numpy as np
from PIL import Image
import pytest
from _current_sdk_test_support import module,runtime,io,torch
W=module('secure_output_writers')
@pytest.mark.parametrize('output,fmt',[('Save','png'),('Preview','jpg'),('Preview','webp'),('Preview','tif')])
def test_pending_write_contract_refuses_before_image_use(output,fmt):
    assert isinstance(W.CR_ImageOutput.validate_inputs(output_type=output,file_format=fmt),str)
    with pytest.raises(RuntimeError,match='writer capability pending'):
        asyncio.run(W.CR_ImageOutput.execute(None,fmt,'None',output_type=output))
def test_explicit_validator_signatures_preserve_other_core_checks():
    for cls in (W.CR_ImageOutput,W.CR_XYSaveGridImage,W.CR_OutputFlowFrames):
        assert not any(p.kind is inspect.Parameter.VAR_KEYWORD for p in inspect.signature(cls.validate_inputs).parameters.values())
    assert W.CR_ImageOutput.validate_inputs() is True
    assert isinstance(W.CR_ImageOutput.validate_inputs(output_type='bad'),str)
    assert isinstance(W.CR_ImageOutput.validate_inputs(file_format='bad'),str)
    assert W.CR_XYSaveGridImage.validate_inputs() is True
    assert isinstance(W.CR_XYSaveGridImage.validate_inputs(trigger=True),str)
    assert isinstance(W.CR_OutputFlowFrames.validate_inputs(),str)
def test_other_writer_paths_refuse_cleanly():
    with pytest.raises(RuntimeError,match='writer capability pending'):
        asyncio.run(W.CR_XYSaveGridImage.execute('Save','',None,'png',trigger=True))
    with pytest.raises(RuntimeError,match='writer capability pending'):
        asyncio.run(W.CR_OutputFlowFrames.execute('',None,0))
@pytest.mark.parametrize('batch',[1,2])
def test_real_native_and_sdk_preview_png_pixels_format_and_metadata(tmp_path,batch):
    import folder_paths
    native_module=importlib.import_module('comfyroll_v1_r10.nodes.nodes_core')
    previous_temp=folder_paths.get_temp_directory();previous_output=folder_paths.get_output_directory()
    temp=tmp_path/'temp';temp.mkdir();output=tmp_path/'output';output.mkdir()
    folder_paths.set_temp_directory(str(temp));folder_paths.set_output_directory(str(output))
    image=torch.linspace(0,1,batch*32*48*3).reshape(batch,32,48,3)
    prompt={'public':'synthetic fixture'};extra={'note':'public test'}
    try:
        original=native_module.CR_ImageOutput().save_images(image,'png','None',output_type='Preview',prompt=prompt,extra_pnginfo=extra)
        async def run():
            with runtime('CR Image Output',W.CR_ImageOutput.SDK_PERMISSIONS,prompt,extra):
                return await W.CR_ImageOutput.execute(image,'png','None',output_type='Preview')
        converted=asyncio.run(run())
        old_rows=original['ui']['images'];new_rows=converted.ui['images']
        assert len(old_rows)==len(new_rows)==batch
        assert converted.result==(False,)
        for old,new in zip(old_rows,new_rows,strict=True):
            assert old['type']==new['type']=='temp'
            with Image.open(temp/old['subfolder']/old['filename']) as a,Image.open(temp/new['subfolder']/new['filename']) as b:
                assert a.format==b.format=='PNG'
                assert a.mode==b.mode and np.array_equal(np.array(a),np.array(b))
                assert a.info['prompt']==b.info['prompt'] and a.info['note']==b.info['note']
        # Internal temp names/compressed PNG bytes are accepted differences.
        assert not list(output.iterdir())
    finally:
        folder_paths.set_temp_directory(previous_temp);folder_paths.set_output_directory(previous_output)
