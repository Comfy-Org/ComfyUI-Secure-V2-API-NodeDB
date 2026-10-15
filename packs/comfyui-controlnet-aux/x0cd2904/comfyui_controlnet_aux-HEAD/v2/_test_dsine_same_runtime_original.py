import base64,hashlib,json,zlib
from pathlib import Path
import numpy as np,torch
from comfy_api.latest import io,sdk
from ._test_savepose_native_fixture import SavePoseExtension
from ._test_dsine_fixture_inputs import fixture
from ._test_dsine_original_networks.models.dsine_arch import DSINE
from ._test_dsine_native_detector import NativeDsineDetector
from ._test_dsine_native_loader import load_checkpoint
from ._test_dsine_native_batch import common_annotator_call
DATA=json.loads(Path(__file__).with_name('_dsine_native_original_goldens.json').read_text())
def golden(case):return next(row for row in DATA['cases'] if row['case']==case)
class AMY_Aux_DSINE_Native_Input_R1(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):return io.Schema(node_id='AMY_Aux_DSINE_Native_Input_R1',category='tests/controlnet_aux',inputs=[io.String.Input('case')],outputs=[io.Image.Output('native_input')])
    @classmethod
    def execute(cls,case):
        row=golden(case);image=fixture(case);assert list(image.shape)==row['input_shape'] and str(image.dtype)==row['input_dtype'];return io.NodeOutput(image)
class AMY_Aux_DSINE_Same_Runtime_Original_Consumer_R1(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw','assets')
    @classmethod
    def define_schema(cls):return io.Schema(node_id='AMY_Aux_DSINE_Same_Runtime_Original_Consumer_R1',category='tests/controlnet_aux',is_output_node=True,inputs=[io.Image.Input('actual'),io.Image.Input('original_image'),io.String.Input('case')],outputs=[io.Image.Output('verified_native_image')])
    @classmethod
    async def execute(cls,actual,original_image,case):
        row=golden(case);image=fixture(case);assert original_image.dtype==image.dtype and original_image.shape==image.shape and torch.equal(original_image.cpu(),image)
        asset=await sdk.ctx().assets.resolve('controlnet','huggingface/hr16/Diffusion-Edge/401c6cd441c2e7d75208f12881f6abef8f6da3b2/dsine.pt');digest=await sdk.ctx().assets.digest(asset)
        assert digest==DATA['original_checkpoint_sha256'] and await sdk.ctx().assets.size(asset)==291298581
        loaded=await sdk.ctx().assets.load_state_dict(asset,member='model');assert isinstance(loaded,dict) and len(loaded)==918 and all(isinstance(v,torch.Tensor) for v in loaded.values())
        model=DSINE();model=load_checkpoint(loaded,model);model.eval()
        assert len(model.state_dict())==918
        detector=NativeDsineDetector(model).to('cpu')
        expected=common_annotator_call(detector,original_image,show_pbar=False,**row['params'])
        assert type(actual) is torch.Tensor and actual.dtype==expected.dtype and actual.shape==expected.shape and torch.equal(actual.cpu(),expected),case
        frozen=zlib.decompress(base64.b64decode(row['tensor_zlib_base64'],validate=True));assert hashlib.sha256(frozen).hexdigest()==row['tensor_sha256']
        host=torch.from_numpy(np.frombuffer(frozen,dtype=row['numpy_dtype']).copy()).reshape(row['shape']);assert torch.equal(actual.cpu(),host),case
        return io.NodeOutput(actual,ui={'text':[json.dumps({'case':case,'node_id':'DSINE-NormalMapPreprocessor','params':row['params'],'shape':list(actual.shape),'dtype':str(actual.dtype),'exact_genuine_original_same_runtime_whole_pixels':True,'same_runtime_original_tensor_sha256':hashlib.sha256(expected.cpu().numpy().tobytes()).hexdigest(),'immutable_one_thread_native_host_tensor_sha256':row['tensor_sha256'],'immutable_one_thread_native_host_tensor_equal':True,'original_checkpoint_sha256':digest,'actual_original_model_members':918,'torch_threads':torch.get_num_threads(),'no_thread_runtime_or_golden_mutation':True,'reference_scope':'Literal original five network files, detector and annotator; native path acquisition replaced by actual SDK restricted literal original top-level model member, original prefix/compatibility filter/diagnostics/strictFalse preserved. Guest RNG/errors/empty/UI progress and othermodelroutes remain unqualified.'})]})
class DSINEExtension(SavePoseExtension):
    async def get_node_list(self):return await super().get_node_list()+[AMY_Aux_DSINE_Native_Input_R1,AMY_Aux_DSINE_Same_Runtime_Original_Consumer_R1]
async def comfy_entrypoint():return DSINEExtension()
