"""Execute the real Metadata writer with canonical browser-queued widget data."""
import asyncio,importlib.util,json,os,shutil,sys
from pathlib import Path
import pytest
HERE=Path(__file__).resolve().parent
CORE=Path(os.environ['COMFY_CORE_ROOT']);OVERLAY=Path(os.environ['MANY_OVERLAY_ROOT'])
sys.dont_write_bytecode=True;sys.path[:0]=[str(CORE),str(OVERLAY/'backend')]
from comfy.cli_args import args
args.cpu=True
import execution,folder_paths
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession

def test_actual_metadata_writer_consumes_canonical_worker_queue(tmp_path,monkeypatch):
 result=json.loads(Path(os.environ['MANY_BROWSER_RESULT']).read_text().splitlines()[-1])
 assert result['canonical_graph']and result['opaque_worker']and result['actual_metadata_save_text_frontend']
 fields=dict(result['queueInputs'],text='actual queued body Ω\nsecond line')
 root=tmp_path/'pack';shutil.copytree(HERE/'metadata-v2',root)
 spec=importlib.util.spec_from_file_location('many_metadata_queue',root/'__init__.py',submodule_search_locations=[str(root)])
 module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
 cls=module.NODE_CLASS_MAPPINGS['SimpleReadableMetadataSaveTextSG'];cls.GET_SCHEMA()
 assert cls.SDK_PERMISSIONS==('assets','output')
 output=tmp_path/'output';output.mkdir();inputs=tmp_path/'input';inputs.mkdir()
 monkeypatch.setattr(folder_paths,'get_output_directory',lambda:str(output))
 monkeypatch.setattr(folder_paths,'get_input_directory',lambda:str(inputs))
 async def run():
  session=await GuestSession('MetadataStory',guest_runtime_root=root).start()
  prior=_sdk.providers.execution_backend
  class Backend:
   async def dispatch(self,plan,local_call,runtime):
    assert plan.input_mode=='values'
    return await session.execute(plan,runtime,capabilities=plan.permissions,tenant='author-account')
  _sdk.providers.register_execution_backend(Backend())
  try:
   assert session.sandbox_kind==json.loads(Path(os.environ['AUTHOR_RUNTIME_PROFILE']).read_text())['sandbox_kind']
   data,missing,v3=execution.get_input_data(fields,cls,'1');assert not missing
   mapped=await execution._async_map_node_over_list('metadata-story','1',cls,data,cls.FUNCTION,v3_data=v3)
   value=(await execution.resolve_map_node_over_list_results(mapped))[0]
   assert value.result is None
   file=output/'prompt_author_Ω_00001.txt'
   assert file.read_bytes()==fields['text'].encode('utf8')
   assert value.ui=={'text_files':[{'filename':file.name,'subfolder':'','type':'output'}]}
   assert session.last_guest_pid not in(None,os.getpid())
   print('ACTUAL_QUEUED_METADATA_WRITER',session.last_guest_pid,fields['filename_prefix'])
  finally:_sdk.providers.register_execution_backend(prior);await session.kill()
 asyncio.run(run())
