import base64,hashlib,json
from pathlib import Path
import numpy as np,torch
from comfy_api.latest import io,sdk
from ._test_anyline_same_runtime_original import ReferenceExtension
from ._test_anime_fixture_inputs import fixture
from ._lineart import ANIME
from ._test_original_anyline import _native_anime_reference as original
DATA=json.loads(Path(__file__).with_name('_anime_native_original6_goldens.json').read_text())
def golden(case):return next(row for row in DATA['cases'] if row['case']==case)
def input_fixture(case):
    if case=='nested256':
        image=torch.ones((1,256,256,3));image[:,48:208,48:208,:]=0;image[:,80:176,80:176,:]=1;image[:,:,126:130,:]=0;return image
    if case=='wide64x96':
        image=torch.ones((1,64,96,3));image[:,12:52,16:80,:]=0;image[:,24:40,32:64,:]=1;image[:,:,46:50,:]=0;return image
    if case=='gray_checker64':return fixture('checker_rgb64')[...,:1]
    if case=='float64_checker64':return fixture('checker_rgb64').to(torch.float64)
    return fixture(case)
class AMY_Aux_Anime_Native_Input_R1(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):return io.Schema(node_id='AMY_Aux_Anime_Native_Input_R1',category='tests/controlnet_aux',inputs=[io.String.Input('case')],outputs=[io.Image.Output('native_input')])
    @classmethod
    def execute(cls,case):
        row=golden(case);image=input_fixture(row['input_case'])
        assert list(image.shape)==row['input_shape'] and str(image.dtype)==row['input_dtype']
        return io.NodeOutput(image)
class AMY_Aux_Anime_Same_Runtime_Original_Consumer_R1(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw','assets')
    @classmethod
    def define_schema(cls):return io.Schema(node_id='AMY_Aux_Anime_Same_Runtime_Original_Consumer_R1',category='tests/controlnet_aux',is_output_node=True,inputs=[io.Image.Input('actual'),io.Image.Input('original_image'),io.String.Input('case')],outputs=[io.Image.Output('verified_native_image')])
    @classmethod
    async def execute(cls,actual,original_image,case):
        row=golden(case);wanted=input_fixture(row['input_case'])
        assert original_image.shape==wanted.shape and original_image.dtype==wanted.dtype and torch.equal(original_image.cpu(),wanted)
        frozen=base64.b64decode(row['tensor_base64'],validate=True);assert hashlib.sha256(frozen).hexdigest()==row['tensor_sha256']
        asset=await sdk.ctx().assets.resolve(ANIME.folder,ANIME.catalogue_name);assert await sdk.ctx().assets.digest(asset)==ANIME.sha256
        original.STATES={ANIME.filename:await sdk.ctx().assets.load_state_dict(asset)}
        detector=original.LineartAnimeDetector.from_pretrained().to('cpu')
        expected=original.common_annotator_call(detector,original_image,resolution=row['resolution'],show_pbar=False)
        assert type(actual) is torch.Tensor and actual.dtype==expected.dtype and actual.shape==expected.shape and torch.equal(actual.cpu(),expected),case
        raw=expected.cpu().numpy().tobytes();host=torch.from_numpy(np.frombuffer(frozen,dtype='<f4').copy()).reshape(row['shape'])
        assert torch.equal(actual.cpu(),host),case
        return io.NodeOutput(actual,ui={'text':[json.dumps({'case':case,'node_id':'AnimeLineArtPreprocessor','exact_genuine_original_same_runtime_whole_pixels':True,'shape':list(actual.shape),'dtype':str(actual.dtype),'same_runtime_original_tensor_sha256':hashlib.sha256(raw).hexdigest(),'immutable_one_thread_native_host_tensor_sha256':row['tensor_sha256'],'immutable_one_thread_native_host_tensor_equal':True,'original_input_dtype':str(original_image.dtype),'original_input_shape':list(original_image.shape),'torch_threads':torch.get_num_threads(),'no_thread_runtime_or_golden_mutation':True,'reference_scope':'Literal original standalone Anime detector/network/batch mathematics and exact genuine SDK state; original host UI progress disabled only in reference, no guest RNG qualification'})]})
class AnimeExtension(ReferenceExtension):
    async def get_node_list(self):return await super().get_node_list()+[AMY_Aux_Anime_Native_Input_R1,AMY_Aux_Anime_Same_Runtime_Original_Consumer_R1]
async def comfy_entrypoint():return AnimeExtension()
