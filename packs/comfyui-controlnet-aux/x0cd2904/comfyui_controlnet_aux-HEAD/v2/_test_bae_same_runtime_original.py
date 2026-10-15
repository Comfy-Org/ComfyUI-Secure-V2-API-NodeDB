import base64,hashlib,json,types,zlib
from pathlib import Path
import numpy as np,torch
from comfy_api.latest import io,sdk
from ._test_aio_same_runtime_original import AIOExtension
from ._test_bae_fixture_inputs import fixture
from ._test_bae_original_nets.NNET import NNET
from ._test_bae_native_detector import NativeNormalBaeDetector
from ._test_bae_native_batch import common_annotator_call
DATA=json.loads(Path(__file__).with_name('_bae_native_original_goldens.json').read_text())
def golden(case):return next(row for row in DATA['cases'] if row['case']==case)
class AMY_Aux_BAE_Native_Input_R1(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):return io.Schema(node_id='AMY_Aux_BAE_Native_Input_R1',category='tests/controlnet_aux',inputs=[io.String.Input('case')],outputs=[io.Image.Output('native_input')])
    @classmethod
    def execute(cls,case):
        row=golden(case);image=fixture(case);assert list(image.shape)==row['input_shape'] and str(image.dtype)==row['input_dtype'];return io.NodeOutput(image)
class AMY_Aux_BAE_Same_Runtime_Original_Consumer_R1(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw','assets')
    @classmethod
    def define_schema(cls):return io.Schema(node_id='AMY_Aux_BAE_Same_Runtime_Original_Consumer_R1',category='tests/controlnet_aux',is_output_node=True,inputs=[io.Image.Input('actual'),io.Image.Input('original_image'),io.String.Input('case')],outputs=[io.Image.Output('verified_native_image')])
    @classmethod
    async def execute(cls,actual,original_image,case):
        row=golden(case);image=fixture(case);assert original_image.dtype==image.dtype and original_image.shape==image.shape and torch.equal(original_image.cpu(),image)
        catalogue='huggingface/lllyasviel/Annotators/982e7edaec38759d914a963c48c4726685de7d96/scannet.pt'
        asset=await sdk.ctx().assets.resolve('controlnet',catalogue);digest=await sdk.ctx().assets.digest(asset);assert digest==DATA['original_weight_sha256']
        state=await sdk.ctx().assets.load_state_dict(asset)
        # The published model-only loader unwraps the original sole model member.
        # Preserve the original prefix loop and strict936-state load; no state synthesis.
        assert isinstance(state,dict) and len(state)==936
        model=NNET(types.SimpleNamespace(mode='client',architecture='BN',pretrained='scannet',sampling_ratio=0.4,importance_ratio=0.7));load_dict={}
        for k,v in state.items():
            if k.startswith('module.'):load_dict[k.replace('module.','')]=v
            else:load_dict[k]=v
        model.load_state_dict(load_dict);model.eval();detector=NativeNormalBaeDetector(model).to('cpu')
        kwargs={} if row['omit_resolution'] else {'resolution':row['resolution']}
        expected=common_annotator_call(detector,original_image,show_pbar=False,**kwargs)
        assert type(actual) is torch.Tensor and actual.dtype==expected.dtype and actual.shape==expected.shape and torch.equal(actual.cpu(),expected),case
        frozen=zlib.decompress(base64.b64decode(row['tensor_zlib_base64'],validate=True));assert hashlib.sha256(frozen).hexdigest()==row['tensor_sha256']
        host=torch.from_numpy(np.frombuffer(frozen,dtype=row['numpy_dtype']).copy()).reshape(row['shape']);assert torch.equal(actual.cpu(),host),case
        return io.NodeOutput(actual,ui={'text':[json.dumps({'case':case,'node_id':'BAE-NormalMapPreprocessor','resolution':row['resolution'],'omitted_resolution_default':row['omit_resolution'],'shape':list(actual.shape),'dtype':str(actual.dtype),'exact_genuine_original_same_runtime_whole_pixels':True,'same_runtime_original_tensor_sha256':hashlib.sha256(expected.cpu().numpy().tobytes()).hexdigest(),'immutable_one_thread_native_host_tensor_sha256':row['tensor_sha256'],'immutable_one_thread_native_host_tensor_equal':True,'original_weight_sha256':digest,'strict_original_state_members':len(state),'torch_threads':torch.get_num_threads(),'no_thread_runtime_or_golden_mutation':True,'reference_scope':'Literal original network source, detector and annotator math; original model-only restricted SDK load with preserved native prefix loop/strict936 tensors. Guest errors/empty/RNG/UI progress remain unqualified.'})]})
class BAEExtension(AIOExtension):
    async def get_node_list(self):return await super().get_node_list()+[AMY_Aux_BAE_Native_Input_R1,AMY_Aux_BAE_Same_Runtime_Original_Consumer_R1]
async def comfy_entrypoint():return BAEExtension()
