"""Print-only numeric buffer admission; native formatting and real ref lifetime."""
import asyncio
from contextlib import redirect_stdout
from dataclasses import replace
import io
from pathlib import Path
import sys
import warnings
import numpy as np
import pytest
import torch
import test_amy_handy_v3 as proof

DTYPES=['bool','int8','int16','int32','int64','uint8','uint16','uint32','uint64',
        'float16','float32','float64','complex64','complex128']

def reject_before_format(value, monkeypatch, error, match):
    def forbidden(*args, **kwargs):
        raise AssertionError('native formatting must never run')
    source=proof.secure.SOURCES['TKPrintValueToLog']
    monkeypatch.setattr(source,source.FUNCTION,forbidden)
    with pytest.raises(error,match=match):
        asyncio.run(proof.pack.NODE_CLASS_MAPPINGS['TKPrintValueToLog'].execute(value=value,label='array'))

def test_oversize_zero_copy_broadcast_refused_before_format(monkeypatch):
    value=np.broadcast_to(np.array(0,dtype=np.float32),(9437184,))
    assert value.nbytes==37748736 and value.nbytes>proof.limits.MAX_BYTES
    assert not value.flags.owndata
    reject_before_format(value,monkeypatch,ValueError,'array byte budget')

def test_trusted_sdk_ref_projection_oversize_never_formats(monkeypatch):
    # Exact root microprobe path, explicitly trusted in-process (not guest or
    # parser/allocation profile evidence). No physical broadcast allocation.
    value=np.broadcast_to(np.array(0,dtype=np.float32),(9437184,))
    source=proof.secure.SOURCES['TKPrintValueToLog']
    def forbidden(*args,**kwargs):
        raise AssertionError('native formatting must never run')
    monkeypatch.setattr(source,source.FUNCTION,forbidden)
    plan=proof._sdk.ExecutionPlan(prompt_id='numpy-bound',node_id='print',node_type='print',
        tier='sandbox',node_module=proof.pack.__name__,inputs={})
    runtime=proof._sdk.Runtime(proof._sdk.InProcessRefResolver(),
        proof._sdk.InProcessCtxProvider().build(plan),proof._sdk.InProcessOps())
    async def run():
        with proof._sdk.bind_runtime(runtime.refs,runtime.ctx,runtime.ops):
            wrapped=await proof._sdk.wrap_inputs(runtime.refs,{'value':value,'label':'ref'})
            assert isinstance(wrapped['value'],proof._sdk.TensorRef)
            with pytest.raises(ValueError,match='array byte budget'):
                await proof.pack.NODE_CLASS_MAPPINGS['TKPrintValueToLog'].execute(**wrapped)
    asyncio.run(run())

def test_combined_torch_ndarray_logical_bytes_refused_before_format(monkeypatch):
    array=np.broadcast_to(np.array(0,dtype=np.float32),(4194305,))
    tensor=torch.zeros(4194304,dtype=torch.float32)
    reject_before_format({'array':array,'tensor':tensor},monkeypatch,ValueError,'aggregate byte budget')

@pytest.mark.parametrize('value',[
    np.zeros(1,dtype=object),np.zeros(1,dtype=[('x','f4')]),np.array(['text']),
    np.zeros((1,1,1,1,1),dtype='float32')])
def test_unsupported_arrays_refused_before_format(value,monkeypatch):
    reject_before_format(value,monkeypatch,ValueError if value.ndim>4 else TypeError,
                         'rank budget' if value.ndim>4 else 'numeric ndarray')

@pytest.mark.parametrize('value',[np.float32(np.nan),np.float64(np.inf),
    np.float32(-1000001),np.uint64(1000001),np.int64(-9223372036854775808),
    np.int32(-2147483648),np.complex64(complex(0,np.inf)),
    np.complex128(1000001j),np.str_('text'),np.bytes_('text'),np.datetime64('2026-10-07')])
def test_numpy_scalars_refused_before_format(value,monkeypatch):
    numeric=value.dtype.kind in 'biufc'
    reject_before_format(value,monkeypatch,ValueError if numeric else TypeError,
                         'finite bounded' if numeric else 'numeric numpy scalar')

def test_numpy_key_scalar_and_cumulative_item_text_budget(monkeypatch):
    assert proof.limits.value_work({np.int16(3):np.float32(.5)})==4
    reject_before_format({np.float32(np.inf):'text'},monkeypatch,ValueError,'finite bounded')
    reject_before_format([np.int8(1)]*4097,monkeypatch,ValueError,'item budget')
    reject_before_format({'x':['a'*40000,np.int8(1),'b'*40000]},monkeypatch,ValueError,'text byte budget')

def test_scalar_ceiling_exact_boundaries_without_narrow_cast_warning():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        assert proof.limits.value_work(np.float16(65504))==2
        assert proof.limits.value_work(np.float32(1000000))==4
        assert proof.limits.value_work(np.longdouble(1000000))==np.dtype(np.longdouble).itemsize
        with pytest.raises(ValueError,match='finite bounded'):
            proof.limits.value_work(np.nextafter(np.float32(1000000),np.float32(np.inf)))
        with pytest.raises(ValueError,match='finite bounded'):
            proof.limits.value_work(np.nextafter(np.longdouble(1000000),np.longdouble(np.inf)))
    assert not caught

@pytest.mark.parametrize('dtype',DTYPES)
@pytest.mark.parametrize('layout',['scalar','contiguous','slice','empty'])
def test_native_array_print_exact_without_coercion(dtype,layout):
    source=proof.controls.native['TKPrintValueToLog']()
    array=np.arange(12).astype(dtype).reshape(3,4)
    if layout=='scalar':array=np.array(1,dtype=dtype)
    elif layout=='slice':array=array[:,::2]
    elif layout=='empty':array=array[:0]
    native_log=io.StringIO();converted_log=io.StringIO()
    with redirect_stdout(native_log):
        reference=getattr(source,source.FUNCTION)(value=array,label='native')
    with redirect_stdout(converted_log):
        actual=asyncio.run(proof.pack.NODE_CLASS_MAPPINGS['TKPrintValueToLog'].execute(value=array,label='native'))
    assert native_log.getvalue()==converted_log.getvalue()
    assert reference[0] is array and actual.result[0] is array
    assert proof.limits.value_work(array)==array.nbytes

@pytest.mark.parametrize('dtype',DTYPES)
def test_native_scalar_print_exact_and_budgeted(dtype):
    value=np.array(1,dtype=dtype)[()]
    source=proof.controls.native['TKPrintValueToLog']()
    a=io.StringIO();b=io.StringIO()
    with redirect_stdout(a):getattr(source,source.FUNCTION)(value=value,label='scalar')
    with redirect_stdout(b):
        actual=asyncio.run(proof.pack.NODE_CLASS_MAPPINGS['TKPrintValueToLog'].execute(value=value,label='scalar'))
    assert a.getvalue()==b.getvalue() and actual.result[0] is value
    assert proof.limits.value_work(value)==value.dtype.itemsize

def test_required_two_guests_outer_ndarray_identity_scalars_denial_recovery(monkeypatch):
    import execution
    from comfy_secure_nodes import packdb
    monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE','required')
    cls=packdb.load_pack(proof.V2.parent.parent,mount_name='custom_nodes.amy_handy_numpy_manifest').node_mappings['TKPrintValueToLog']
    async def run():
        previous=proof._sdk.providers.execution_backend
        original=proof.packruntime.resolve_for_tenant
        pids=[]
        def selected(spec,tenant):
            resolved=original(spec,tenant)
            assert resolved.python_executable==Path(sys.executable)
            return replace(resolved,spec=replace(resolved.spec,pack_root=proof.V2))
        try:
            for repeat in range(2):
                with monkeypatch.context() as config:
                    config.setattr(proof.packruntime,'resolve_for_tenant',selected)
                    guest=await proof.GuestSession('amy-handy-numpy-'+str(repeat),module_source_root=proof.V2,
                        guest_runtime_root=proof.HOST).start()
                assert guest.sandbox_kind=='seatbelt';pids.append(guest.pid)
                caps=['raw']
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await proof._sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await guest.execute(plan,runtime,capabilities=caps,tenant='amy-handy-numpy-'+str(repeat))
                proof._sdk.providers.register_execution_backend(Backend())
                async def call(value):
                    result=await execution._async_map_node_over_list('array','TKPrintValueToLog',cls,
                        {'value':[value],'label':['array']},'execute')
                    return (await execution.resolve_map_node_over_list_results(result))[0]
                try:
                    for dtype in DTYPES:
                        value=np.arange(12).astype(dtype).reshape(3,4)[:,::2]
                        actual=await call(value)
                        assert actual.result[0] is value
                        assert actual.result[0].dtype==value.dtype
                    value=np.arange(6,dtype='float32')
                    caps[:]=[]
                    with pytest.raises(proof.wire.WireError,match='raw'):
                        await call(value)
                    caps[:]=['raw']
                    assert (await call(value)).result[0] is value
                    mixed={'array':value,'scalar':np.float32(.25),'nested':(np.int16(5),'text')}
                    returned=(await call(mixed)).result[0]
                    assert returned['array'] is value
                    assert type(returned['scalar']) is np.float32 and returned['scalar']==mixed['scalar']
                    assert type(returned['nested'][0]) is np.int16 and returned['nested']==mixed['nested']
                    with pytest.raises(proof.wire.WireError,match='finite bounded'):
                        await call(np.float32(np.inf))
                    assert (await call(value)).result[0] is value
                    print({'pid':guest.pid,'array_dtypes':DTYPES,'tier':'required-seatbelt+manifest+production-outer',
                        'qualification':'Unsealed Mac stage, exact numeric buffers/scalars; no profile/deployment grant.'})
                finally:
                    await guest.kill()
        finally:
            proof._sdk.providers.execution_backend=previous
        assert len(set(pids))==2
    asyncio.run(run())
