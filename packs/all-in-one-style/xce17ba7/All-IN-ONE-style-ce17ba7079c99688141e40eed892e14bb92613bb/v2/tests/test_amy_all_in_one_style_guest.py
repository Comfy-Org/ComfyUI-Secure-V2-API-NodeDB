"""Fresh required zero-capability guest and actual production V3 outer."""
import asyncio,os,shutil,sys
from pathlib import Path
import pytest
from test_amy_all_in_one_style import V2,load,defaults,native,MENUS
CORE=Path(os.environ['COMFY_CORE_ROOT'])
sys.path[:0]=[str(CORE),os.environ['STYLE_BACKEND_ROOT']]
from comfy.cli_args import args
args.cpu=True
import execution
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession

def test_two_fresh_required_zero_cap_guests_native_defaults_order_logs_refusal_recovery(tmp_path):
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for render in range(2):
                fresh=tmp_path/str(render);shutil.copytree(V2,fresh)
                module=load('amy_style_outer_'+str(render),fresh)
                session=await GuestSession('amy-all-in-one-style-'+str(render),guest_runtime_root=fresh).start()
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        return await session.execute(plan,runtime,capabilities=(),tenant='amy-style-user')
                _sdk.providers.register_execution_backend(Backend())
                async def outer(fields):
                    cls=module.NODE_CLASS_MAPPINGS['ComfyUIStyler'];cls.GET_SCHEMA()
                    out=await execution._async_map_node_over_list(prompt_id='amy-style-outer',unique_id='style-'+str(render),
                        obj=cls,input_data_all={k:[v] for k,v in fields.items()},func=cls.FUNCTION,v3_data=None)
                    return out[0].result
                try:
                    assert session.sandbox_kind=='seatbelt'
                    cases=[defaults(),defaults()|{'text_positive':'😀\n{prompt}','text_negative':'bad','log_prompt':True}]
                    for menu in ('Aesthetic','artist','milehigh','environment'):
                        f=defaults();options=module._secure_nodes.source.NODE_CLASS_MAPPINGS['ComfyUIStyler'].INPUT_TYPES()['required'][menu][0]
                        f[menu]=options[-1];cases.append(f)
                    reversed_fields=dict(reversed(list(defaults().items())))
                    reversed_fields['text_positive']='reversed';cases.append(reversed_fields)
                    for fields in cases:assert await outer(fields)==native(fields)
                    with pytest.raises(Exception,match='text budget'):await outer(defaults()|{'text_positive':'x'*65537})
                    assert await outer(defaults()|{'text_positive':'recovered'})==native(defaults()|{'text_positive':'recovered'})
                    # Plain TEXT admission cannot recover host objects/tensors.
                    for bad in (object(),{'a':'x'}):
                        with pytest.raises(Exception,match='plain|unsupported|wire|STRING'):
                            await outer(defaults()|{'text_positive':bad})
                    assert await outer(defaults())==native(defaults())
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(previous)
        assert len(set(pids))==2 and os.getpid() not in pids
    asyncio.run(run())
