"""Required fresh typed guests through actual execution outer/assets/font bytes."""
import asyncio,os,shutil
import pytest
import torch
from test_amy_textoverlay import V2,PACK,NEW,NODE,FONT,load,defaults,native,same,inputs
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
import execution
from comfy_secure_nodes import packdb

def test_two_fresh_required_guests_true_outer_fonts_pixels_refusal_recovery(inputs,tmp_path):
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for generation in range(2):
                fresh=tmp_path/'guest'/str(generation);shutil.copytree(V2,fresh)
                package=load('amy_textoverlay_outer_'+str(generation),fresh)
                node=package.NODE_CLASS_MAPPINGS['Text Overlay'];node.GET_SCHEMA()
                session=await GuestSession('amy-textoverlay-'+str(generation),guest_runtime_root=fresh).start()
                capabilities=node.SDK_PERMISSIONS
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        return await session.execute(plan,runtime,capabilities=capabilities,tenant='amy-textoverlay-local-user')
                _sdk.providers.register_execution_backend(Backend())
                async def outer(fields):
                    output=await execution._async_map_node_over_list(prompt_id='amy-textoverlay-positive',unique_id='overlay-'+str(generation),
                        obj=node,input_data_all={key:[value] for key,value in fields.items()},func=node.FUNCTION,v3_data=None)
                    return output[0].result
                try:
                    assert session.sandbox_kind=='seatbelt'
                    for fields in (defaults(),defaults()|{'font':'positive.ttf','text':'😀\nhello world','font_size':16},
                        defaults()|{'font':'invalid.ttf','fill_color_hex':'#ABC'},defaults()|{'font':'positive.ttf','horizontal_alignment':'right','vertical_alignment':'middle','x_shift':-3}):
                        source=fields|{'font':str(FONT)} if fields['font']=='positive.ttf' else fields
                        if fields['font']=='invalid.ttf':source=fields|{'font':str(inputs/'textoverlay/invalid.ttf')}
                        same(await outer(fields),native(source))
                    for fields in (defaults(torch.bfloat16),defaults()|{'fill_color_hex':'badhex'}):
                        with pytest.raises(Exception) as old:native(fields)
                        with pytest.raises(Exception) as new:await outer(fields)
                        assert str(old.value) in str(new.value)
                    for fields in (defaults()|{'font':'../outside.ttf'},defaults()|{'font_size':9999},defaults()|{'text':'x'*4097}):
                        with pytest.raises(Exception,match='profile|budget|basename'):await outer(fields)
                    oversized=inputs/'textoverlay/oversize.ttf'
                    with oversized.open('wb') as output:output.truncate(2*1024*1024+1)
                    with pytest.raises(Exception,match='font byte budget'):await outer(defaults()|{'font':'oversize.ttf'})
                    same(await outer(defaults()),native(defaults()))
                    for missing in ('inspect','raw','assets'):
                        capabilities=tuple(cap for cap in node.SDK_PERMISSIONS if cap!=missing)
                        with pytest.raises(Exception,match='permission|capability|Permission|denied|not allowed'):
                            await outer(defaults())
                        capabilities=node.SDK_PERMISSIONS
                        same(await outer(defaults()),native(defaults()))
                    basename='outside-'+str(generation)+'.ttf'
                    outside=tmp_path/basename;outside.write_bytes(b'not a font')
                    link=inputs/'textoverlay'/basename;link.symlink_to(outside)
                    with pytest.raises(Exception,match='outside|escape|confined|symlink'):
                        await outer(defaults()|{'font':basename})
                    same(await outer(defaults()),native(defaults()))
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(previous)
        assert len(set(pids))==2 and os.getpid() not in pids
    asyncio.run(run())

def test_actual_manifest_proxy_executes_only_in_required_guest(inputs,tmp_path):
    async def run():
        root=tmp_path/'proxy/comfyui-textoverlay/x7ed846f';root.mkdir(parents=True)
        fresh=root/PACK.name;shutil.copytree(PACK,fresh)
        proxy=packdb.load_pack(root,mount_name='custom_nodes.amy_textoverlay_execution_proxy')
        node=proxy.node_mappings['Text Overlay'];node.GET_SCHEMA()
        assert node.SECURE_NODE_PROXY is True
        with pytest.raises(RuntimeError,match='cannot execute in the host'):await node.execute()
        session=await GuestSession('amy-textoverlay-manifest-proxy',guest_runtime_root=fresh/'v2').start()
        previous=_sdk.providers.execution_backend
        class Backend:
            async def dispatch(self,plan,local_call,runtime):
                return await session.execute(plan,runtime,capabilities=node.SDK_PERMISSIONS,tenant='amy-textoverlay-proxy-user')
        _sdk.providers.register_execution_backend(Backend())
        try:
            assert session.sandbox_kind=='seatbelt'
            for fields in (defaults(),defaults()|{'font':'positive.ttf','font_size':18}):
                output=await execution._async_map_node_over_list(prompt_id='amy-textoverlay-proxy',unique_id='proxy',obj=node,
                    input_data_all={key:[value] for key,value in fields.items()},func=node.FUNCTION,v3_data=None)
                same(output[0].result,native(fields|{'font':str(FONT)} if fields['font']=='positive.ttf' else fields))
            assert session.last_guest_pid!=os.getpid()
        finally:
            await session.kill();_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
