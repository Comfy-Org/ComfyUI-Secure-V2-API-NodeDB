"""Bounded mutable-input transport, including real required guest admission."""
import asyncio
import importlib
import sys
from types import SimpleNamespace
import pytest
from test_amy_readable_conversion import PACK, V2, _sdk, GuestSession, folder_paths

LOADER = sys.modules[PACK.NODE_CLASS_MAPPINGS["SimpleReadableMetadataSG"].__module__]
PROBE = importlib.import_module(PACK.__name__ + ".tests.amy_read_range_probe")

@pytest.mark.parametrize("initial,body,tail,after,refused", [
    (8,b"12345678",b"",8,False), (0,b"",b"",0,False),
    (9,b"",b"",9,True), (8,b"12345678",b"9",12,True),
    (4,b"12345678",b"",8,True), (8,b"1234",b"",4,True),
    (8,b"12345678",b"",12,True)])
def test_changing_size_never_imports_whole_file(monkeypatch,initial,body,tail,after,refused):
    calls=[]
    class Assets:
        async def resolve(self,*args):return "owned"
        async def size(self,ref):
            calls.append(("size",));return initial if calls.count(("size",))==1 else after
        async def read_bytes(self,*args):raise AssertionError("unbounded read never allowed")
        async def read_range(self,ref,offset,length):
            calls.append((offset,length));assert (offset,length) in ((0,8),(8,1))
            return body if offset==0 else tail
    monkeypatch.setattr(LOADER.sdk,"ctx",lambda:SimpleNamespace(assets=Assets()))
    async def run():
        if refused:
            with pytest.raises(ValueError,match="workload|size changed"):
                await LOADER.read_input("safe.dat",8)
        else:assert await LOADER.read_input("safe.dat",8)==body
    asyncio.run(run())
    if initial>8:assert calls==[("size",)]
    else:assert calls==[("size",),(0,8),(8,1),("size",)]

def test_fresh_required_guest_range_growth_refusal_denial_and_recovery(tmp_path,monkeypatch):
    input_root=tmp_path/"input";input_root.mkdir()
    path=input_root/"probe.txt";path.write_bytes(b"12345678")
    monkeypatch.setattr(folder_paths,"get_input_directory",lambda:str(input_root))
    monkeypatch.setenv("COMFY_SECURE_SANDBOX_MODE","required")
    async def run():
        session=GuestSession("amy-readable-bounded-range",guest_runtime_root=V2.parent)
        mode="stable";ranges=[]
        original_size=session._h_assets_size
        original_range=session._h_assets_read_range
        async def size(ref):
            nonlocal mode
            result=await original_size(ref)
            if mode=="grow":path.write_bytes(b"123456789012");mode="changed"
            return result
        async def read_range(ref,offset=0,length=8*1024*1024):
            ranges.append((offset,length));return await original_range(ref,offset,length)
        async def no_whole(*args,**kwargs):raise AssertionError("read_bytes must never dispatch")
        monkeypatch.setattr(session,"_h_assets_size",size)
        monkeypatch.setattr(session,"_h_assets_read_range",read_range)
        monkeypatch.setattr(session,"_h_assets_read_bytes",no_whole)
        await session.start()
        async def call(caps=("assets",)):
            plan=_sdk.ExecutionPlan(prompt_id="bounded",node_id="1",node_type="ReadRangeProbe",
                node_module=PROBE.ReadRangeProbe.__module__,method="execute",input_mode="values",
                inputs={"label":"probe.txt","maximum":8})
            runtime=_sdk.Runtime(refs=_sdk.InProcessRefResolver(),
                ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
            return await session.execute(plan,runtime,capabilities=caps,tenant="amy-local")
        try:
            assert session.sandbox_kind=="seatbelt"
            assert (await call()).result==("12345678",)
            mode="grow"
            with pytest.raises(Exception,match="size changed|workload"):await call()
            assert ranges==[(0,8),(8,1)]*2
            with pytest.raises(Exception,match="assets|permission|capability"):await call(())
            path.write_bytes(b"12345678");mode="stable"
            assert (await call()).result==("12345678",)
            print("READABLE_RANGE_REQUIRED_GUEST",session.last_guest_pid,"growth refused; assets denial/recovery")
        finally:await session.kill()
    asyncio.run(run())
