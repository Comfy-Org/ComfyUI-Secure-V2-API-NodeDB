"""All23 through actual zero-capability fresh guests and production outer."""
import asyncio, os, shutil, sys
from pathlib import Path
import pytest
from test_amy_basic_math import V2, OLD, IDS, load, values, equivalent
CORE = Path(os.environ['COMFY_CORE_ROOT'])
sys.path[:0] = [str(CORE), os.environ['BASIC_MATH_BACKEND_ROOT']]
from comfy.cli_args import args
args.cpu = True
import execution
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
import torch
from comfy.model_patcher import ModelPatcher

def test_all23_actual_outer_two_fresh_required_guests_native_errors_bounds_and_recovery(tmp_path):
    async def run():
        previous = _sdk.providers.execution_backend
        pids = []
        try:
            for render in range(2):
                fresh = tmp_path/str(render)
                shutil.copytree(V2, fresh, ignore=shutil.ignore_patterns('__pycache__','.pytest_cache'))
                module = load('amy_basic_math_guest_'+str(render),fresh)
                session = await GuestSession('amy-basic-math-'+str(render),guest_runtime_root=fresh).start()
                class Backend:
                    async def dispatch(self, plan, local_call, runtime):
                        return await session.execute(plan,runtime,capabilities=(),tenant='amy-basic-math-user')
                _sdk.providers.register_execution_backend(Backend())
                async def outer(node_id, fields):
                    c=module.NODE_CLASS_MAPPINGS[node_id];c.GET_SCHEMA()
                    out=await execution._async_map_node_over_list(prompt_id='amy-basic-math-outer',unique_id='math-'+str(render),
                        obj=c,input_data_all={k:[v] for k,v in fields.items()},func=c.FUNCTION,v3_data=None)
                    return out[0].result
                try:
                    assert session.sandbox_kind == 'seatbelt'
                    for node_id in IDS:
                        source=OLD.NODE_CLASS_MAPPINGS[node_id];f=values(node_id)
                        equivalent(await outer(node_id,f),getattr(source(),source.FUNCTION)(**f))
                    controls=[('IntegerInput',dict(value=2**64-1)),('IntMath',dict(a=2,b=64,operation='**')),
                        ('BasicMath',dict(a=0,b=0,operation='/')),('BasicMath',dict(a=1,b=0,operation='%')),
                        ('UnaryMath',dict(value=0,operation='log')),('UnaryMath',dict(value=-0.,operation='sin')),
                        ('ToInt',dict(any='nonnumeric')),('ToFloat',dict(any='nan')),
                        ('ToBool',dict(any={'a':[]},invert=False)),('ToString',dict(any={'a':[1,'😀',None]})),
                        ('StringComparison',dict(a='ABC',b='[a-z]+',operation='a MATCH REGEX(b)',case_sensitive=False)),
                        ('StringComparison',dict(a='a',b='[',operation='a MATCH REGEX(b)',case_sensitive=True)),
                        ('IntMath',dict(a=1,b=-1,operation='<<'))]
                    for node_id,f in controls:
                        source=OLD.NODE_CLASS_MAPPINGS[node_id]
                        equivalent(await outer(node_id,f),getattr(source(),source.FUNCTION)(**f))
                    for node_id,f in [('IntMath',dict(a=2,b=5000,operation='**')),
                        ('ToString',dict(any=['\x00'*2000]*8)),
                        ('StringComparison',dict(a='a'*100,b='(a+)+',operation='a MATCH REGEX(b)',case_sensitive=True))]:
                        with pytest.raises(Exception,match='budget|profile|regex'):await outer(node_id,f)
                        equivalent(await outer('BasicMath',dict(a=7,b=2,operation='+')),(9,))
                    # Real canonical MODEL and generic host object are both
                    # outside this plain scalar/tree profile; no repr recovery.
                    model=ModelPatcher(torch.nn.Linear(1,1),load_device=torch.device('cpu'),offload_device=torch.device('cpu'))
                    for opaque in (model,object()):
                        with pytest.raises(Exception,match='opaque|plain-value|unsupported|raw|value-mode|wire'):
                            await outer('ToString',dict(any=opaque))
                    equivalent(await outer('ToString',dict(any='recovered')),('recovered',))
                    pids.append(session.last_guest_pid)
                finally:
                    await session.kill()
        finally:
            _sdk.providers.register_execution_backend(previous)
        assert len(set(pids)) == 2 and os.getpid() not in pids
    asyncio.run(run())
