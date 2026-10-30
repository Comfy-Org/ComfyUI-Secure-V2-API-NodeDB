"""Actual current-SDK VAE contract/refusals; real-model pixel parity stays open."""
import asyncio
import inspect
import pytest
from _current_sdk_test_support import module,sdk
VAE=module('secure_vae')
@pytest.mark.parametrize('tiled,circular',[(True,False),(False,True),(True,True),(1,0),(0,1)])
def test_unsupported_native_tile_or_padding_refuses_before_model_use(tiled,circular):
    assert isinstance(VAE.CR_VAEDecode.validate_inputs(tiled=tiled,circular=circular),str)
    with pytest.raises(RuntimeError,match='tiled/circular VAE capability pending'):
        asyncio.run(VAE.CR_VAEDecode.execute(None,None,tiled=tiled,circular=circular))
def test_ordinary_contract_uses_current_public_decode_without_padding_kwargs():
    assert VAE.CR_VAEDecode.validate_inputs() is True
    assert not any(p.kind is inspect.Parameter.VAR_KEYWORD for p in inspect.signature(VAE.CR_VAEDecode.validate_inputs).parameters.values())
    parameters=inspect.signature(sdk.VaeRef.decode).parameters
    assert 'padding_mode' not in parameters
    assert not hasattr(sdk.VaeRef,'decode_tiled_native')
    assert [o.io_type for o in VAE.CR_VAEDecode.GET_SCHEMA().outputs]==['IMAGE','STRING']
def test_real_model_ordinary_decode_requires_an_owned_pinned_fixture():
    pytest.skip('No trained real VAE fixture bound in this source tier; no synthetic model success credit')
