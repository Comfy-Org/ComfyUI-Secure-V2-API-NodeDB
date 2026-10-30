"""Current names-only contract: bundled data works, missing host catalogue refuses."""
import asyncio
import inspect
import pytest
from _current_sdk_test_support import module,V2
F=module('secure_font_catalogues')
@pytest.mark.parametrize('source,path',[('system','fonts'),('from folder','fonts')])
def test_missing_catalogue_refuses_without_fallback(source,path):
    assert isinstance(F.CR_FontFileList.validate_inputs(source_folder=source,folder_path=path),str)
    with pytest.raises(RuntimeError,match='font catalogue capability pending'):
        asyncio.run(F.CR_FontFileList.execute(source,0,10,path))
def test_validator_keeps_core_bounds_and_combo_checks():
    fn=F.CR_FontFileList.validate_inputs
    assert not any(p.kind is inspect.Parameter.VAR_KEYWORD for p in inspect.signature(fn).parameters.values())
    assert isinstance(fn(),str) # Linked/unavailable source uses a safe default.
    assert isinstance(fn(source_folder='invalid'),str)
    assert fn(source_folder='Comfyroll') is True
    schema=F.CR_FontFileList.GET_SCHEMA()
    assert next(i for i in schema.inputs if i.id=='start_index').as_dict()['min']==0
    assert next(i for i in schema.inputs if i.id=='max_rows').as_dict()['max']==9999
def test_real_bundled_catalogue_order_and_large_direct_slice():
    expected=[p.name for p in (V2/'fonts').iterdir() if p.is_file() and p.suffix.lower()=='.ttf']
    result=asyncio.run(F.CR_FontFileList.execute('Comfyroll',0,9999))
    assert result.result[0]==expected
    assert asyncio.run(F.CR_FontFileList.execute('Comfyroll',1<<5000,9999)).result[0]==expected[-1:]
