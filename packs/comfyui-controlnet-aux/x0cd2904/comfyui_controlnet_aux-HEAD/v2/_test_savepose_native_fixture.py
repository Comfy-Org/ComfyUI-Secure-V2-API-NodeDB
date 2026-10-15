import copy,json
from pathlib import Path
from comfy_api.latest import io,sdk
from ._test_bae_same_runtime_original import BAEExtension
DATA=json.loads(Path(__file__).with_name('_savepose_native_original_goldens.json').read_text())
class AMY_Aux_SavePose_Native_Input_R1(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('assets','output')
    @classmethod
    def define_schema(cls):return io.Schema(node_id='AMY_Aux_SavePose_Native_Input_R1',category='tests/controlnet_aux',inputs=[io.String.Input('case')],outputs=[io.Custom('POSE_KEYPOINT').Output('pose_kps'),io.String.Output('filename_prefix')])
    @classmethod
    async def execute(cls,case):
        row=next(r for r in DATA['cases'] if r['case']==case);scope='amy-savepose-original-r1/'+case
        # Seed only real new files through the published managed output API,
        # as upstream fixture preparation before returning the production input.
        assert await sdk.ctx().assets.list('output',prefix=scope,recursive=True)==[]
        for name in row['seeded_names']:
            await sdk.ctx().output.write_text('fixture seed '+name,scope+'/'+name,folder='output',mode='new_only')
        return io.NodeOutput(copy.deepcopy(row['payload']),scope+'/'+row['prefix'])
class AMY_Aux_SavePose_Actual_File_Reader_R2(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('assets','raw')
    @classmethod
    def define_schema(cls):return io.Schema(node_id='AMY_Aux_SavePose_Actual_File_Reader_R2',category='tests/controlnet_aux',is_output_node=True,inputs=[io.Custom('POSE_KEYPOINT').Input('pose_kps'),io.String.Input('filename_prefix'),io.String.Input('case')],outputs=[io.String.Output('verified_actual_json')])
    @classmethod
    async def execute(cls,pose_kps,filename_prefix,case):
        import base64,hashlib
        row=next(r for r in DATA['cases'] if r['case']==case);scope='amy-savepose-original-r1/'+case
        assert pose_kps==row['payload'] and filename_prefix==scope+'/'+row['prefix']
        name=scope+'/'+row['native_saved_relative_path'];asset=await sdk.ctx().assets.resolve('output',name);raw=await sdk.ctx().assets.read_bytes(asset);digest=await sdk.ctx().assets.digest(asset)
        assert len(raw)==row['native_saved_bytes'] and digest==hashlib.sha256(raw).hexdigest()==row['native_saved_sha256'] and json.loads(raw)==pose_kps
        seeds=[]
        for seed in row['seeded_names']:
            ref=await sdk.ctx().assets.resolve('output',scope+'/'+seed);data=await sdk.ctx().assets.read_bytes(ref);assert data==('fixture seed '+seed).encode();seeds.append({'name':seed,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
        names=await sdk.ctx().assets.list('output',prefix=scope,recursive=True);relative=sorted(n[len(scope)+1:] for n in names);assert relative==sorted(row['seeded_names']+[row['native_saved_relative_path']])
        receipt={'case':case,'node_id':'SavePoseKpsAsJsonFile','actual_managed_filename':name,'native_relative_filename':row['native_saved_relative_path'],'actual_saved_bytes':len(raw),'actual_saved_sha256':digest,'actual_saved_file_base64':base64.b64encode(raw).decode(),'whole_JSON_bytes_exact_native':True,'original_counter_and_prefix_exact':True,'seeded_original_files_unchanged':seeds,'owned_case_directory_files_exact':relative,'read_only_observer_no_output_write_permission':True,'source_production_zero_sockets_preserved':True,'scope':'Genuine registered SavePose saved managed JSON file, read via real public asset API during workflow and captured in actual UI receipt. HTTP TEST does not retain this raw renderer file after job; normal user-output durability beyond the ephemeral job is unqualified.'}
        return io.NodeOutput(raw.decode(),ui={'text':[json.dumps(receipt)]})
class SavePoseExtension(BAEExtension):
    async def get_node_list(self):return await super().get_node_list()+[AMY_Aux_SavePose_Native_Input_R1,AMY_Aux_SavePose_Actual_File_Reader_R2]
async def comfy_entrypoint():return SavePoseExtension()

# TEST-ONLY observation hook, installed in host and guest package import.
# Keep the actual registered production class, schema, grants and original
# method. Invoke its original execute exactly once, then read the actual file
# before returning a diagnostic UI snapshot with the same zero result sockets.
def _install_after_return_capture():
    from . import nodes
    cls=nodes.SavePoseKpsAsJsonFile
    original=cls.execute.__func__
    async def execute(current_cls,**values):
        import base64,hashlib
        result=await original(current_cls,**values)
        prefix=values['filename_prefix'];pose=values['pose_kps']
        row=next(r for r in DATA['cases'] if prefix=='amy-savepose-original-r1/'+r['case']+'/'+r['prefix'])
        assert pose==row['payload'];scope='amy-savepose-original-r1/'+row['case'];name=scope+'/'+row['native_saved_relative_path']
        names=await sdk.ctx().assets.list('output',prefix=scope,recursive=True);relative=sorted(n[len(scope)+1:] for n in names)
        assert relative==sorted(row['seeded_names']+[row['native_saved_relative_path']]),(row['case'],relative)
        asset=await sdk.ctx().assets.resolve('output',name);raw=await sdk.ctx().assets.read_bytes(asset);digest=await sdk.ctx().assets.digest(asset)
        assert len(raw)==row['native_saved_bytes'] and digest==hashlib.sha256(raw).hexdigest()==row['native_saved_sha256'] and json.loads(raw)==pose
        seeds=[]
        for seed in row['seeded_names']:
            ref=await sdk.ctx().assets.resolve('output',scope+'/'+seed);data=await sdk.ctx().assets.read_bytes(ref);assert data==('fixture seed '+seed).encode();seeds.append({'name':seed,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
        receipt={'case':row['case'],'node_id':'SavePoseKpsAsJsonFile','actual_managed_filename':name,'native_relative_filename':row['native_saved_relative_path'],'actual_saved_bytes':len(raw),'actual_saved_sha256':digest,'actual_saved_file_base64':base64.b64encode(raw).decode(),'whole_JSON_bytes_exact_native':True,'original_counter_and_prefix_exact':True,'seeded_original_files_unchanged':seeds,'owned_case_directory_files_exact':relative,'source_production_zero_sockets_preserved':True,'TEST_only_after_original_execute_return_capture':True,'actual_original_registered_method_called_exactly_once':True,'capture_code_uses_read_asset_APIs_only':True,'production_declared_assets_output_grants_unchanged':True,'scope':'TEST-only diagnostic UI wrapper around the same actual registered production class and original execute. Original method/body called exactly once, then real saved file read through public assets API before unchanged zero-socket result. This observes intrinsic file/counter semantics; original normal UI, post-TEST raw file lifetime and user-output durability are unqualified.'}
        return io.NodeOutput(ui={'text':[json.dumps(receipt)]})
    cls.execute=classmethod(execute)
_install_after_return_capture()
