"""Actual confined development guest+production outer; staged deps are explicit."""
import asyncio,hashlib,json,os,shutil,sys
from pathlib import Path
import pytest,torch
from test_amy_qr_algorithms import V2,OLD,NEW,IDS,cls,values,same,load,image
CORE=Path(os.environ['COMFY_CORE_ROOT'])
sys.path[:0]=[str(CORE),os.environ['QR_BACKEND_ROOT']]
from comfy.cli_args import args
args.cpu=True
import execution
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
PROFILE=Path(os.environ['QR_DEPENDENCY_PROFILE'])
def compose(destination):
 receipt=json.loads((PROFILE/'profile.json').read_bytes())
 assert hashlib.sha256((PROFILE/'profile.json').read_bytes()).hexdigest()=='8b0bccc4348045d0794a5b487d0ce397d8d447082a1e78f5313ddfb8da8f67ce'
 shutil.copytree(V2,destination,ignore=shutil.ignore_patterns('.pytest_cache','__pycache__'))
 for name,row in receipt['files'].items():
  source=PROFILE/'site'/name
  assert source.is_file() and not source.is_symlink()
  assert hashlib.sha256(source.read_bytes()).hexdigest()==row['sha256']
  assert len(source.read_bytes())==row['bytes']
  target=destination/name
  assert not target.exists()
  target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
 return receipt

def test_all_twelve_actual_outer_two_fresh_required_guests_and_native_BW_layout(tmp_path):
 async def run():
  prior=_sdk.providers.execution_backend;allowed=('raw',);pids=[]
  try:
   for render in range(2):
    fresh=tmp_path/str(render);compose(fresh)
    module=load('amy_qr_guest_'+str(render),fresh)
    session=await GuestSession('amy-qr-'+str(render),guest_runtime_root=fresh).start()
    class Backend:
     async def dispatch(self,plan,local_call,runtime):
      plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
      return await session.execute(plan,runtime,capabilities=allowed,tenant='amy-qr-user')
    _sdk.providers.register_execution_backend(Backend())
    async def outer(node_id,value):
     converted=module.NODE_CLASS_MAPPINGS[node_id];converted.GET_SCHEMA()
     result=await execution._async_map_node_over_list(prompt_id='amy-qr-outer',unique_id='qr-'+str(render),
      obj=converted,input_data_all={key:[val] for key,val in value.items()},func=converted.FUNCTION,v3_data=None)
     return result[0]
    try:
     assert session.sandbox_kind=='seatbelt'
     for node_id in IDS:
      value=values(node_id)
      source=OLD.NODE_CLASS_MAPPINGS[node_id]
      if source.__name__=='ShowData':
       value={'input':['AMY','😀',42],'data':['unused']}
       result=await outer(node_id,value)
       assert result.ui=={'data':source().render_data([value['input']])}
      else:
       expected=getattr(source(),source.FUNCTION)(**value)
       result=await outer(node_id,value);same(result.result,expected)
     # Typed outer currently forwards exact native CHW source values.
     bw=cls('QRCodesSimpleBW');result=await outer(bw,values(bw))
     assert result.result[0].shape==(1,53,67)
     assert torch.equal(result.result[0],result.result[2])
     # A default512 generator plus source reader through the true broker.
     qr=cls('QRCodesSimpleBW');value=values(qr,small=False)
     output=(await outer(qr,value)).result[0]
     reader_image=output
     reader=cls('QRCodeReader')
     expected=OLD.NODE_CLASS_MAPPINGS[reader]().qr_code_reader(reader_image)
     assert expected[0]==('AMY QR',)
     same((await outer(reader,{'image':reader_image})).result,expected)
     denied=cls('CreateSolidFrame');allowed=()
     with pytest.raises(Exception,match='raw|permission|capability|numeric tensor'):
      await outer(denied,values(denied))
     allowed=('raw',)
     same((await outer(denied,values(denied))).result,OLD.NODE_CLASS_MAPPINGS[denied]().render_data(**values(denied)))
     huge=values(cls('QRCodesSimple'));huge['box_size']=8192
     with pytest.raises(Exception,match='QR intermediate'):await outer(cls('QRCodesSimple'),huge)
     value=values(cls('QRCodesSegnoSimple'));value['scale']=0
     with pytest.raises(Exception):await outer(cls('QRCodesSegnoSimple'),value)
     same((await outer(denied,values(denied))).result,OLD.NODE_CLASS_MAPPINGS[denied]().render_data(**values(denied)))
     pids.append(session.last_guest_pid)
    finally:await session.kill()
  finally:_sdk.providers.register_execution_backend(prior)
  assert len(set(pids))==2 and os.getpid() not in pids
 asyncio.run(run())
