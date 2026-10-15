import base64,hashlib,json,zlib
from pathlib import Path
import numpy as np,torch
from comfy_api.latest import io,sdk
from ._test_manga_same_runtime_original import MangaExtension
from ._test_aio_fixture_inputs import fixture
from . import _test_aio_native_reference as original
from ._test_original_anyline import _native_manga_reference as manga,_native_anime_reference as anime
from ._manga import WEIGHT as MANGA
from ._lineart import ANIME
DATA=json.loads(Path(__file__).with_name('_aio_native_original_goldens.json').read_text())
def golden(case):return next(row for row in DATA['cases'] if row['case']==case)
def input_fixture(case):
    if case=='fp16_rgb_batch2':return fixture('fp16_rgba_batch2')[...,:3]
    if case=='gray_checker64':return fixture('checker_rgb64')[...,:1]
    return fixture(case)
class AMY_Aux_AIO_Native_Input_R1(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):return io.Schema(node_id='AMY_Aux_AIO_Native_Input_R1',category='tests/controlnet_aux',inputs=[io.String.Input('case')],outputs=[io.Image.Output('native_input')])
    @classmethod
    def execute(cls,case):
        row=golden(case);image=input_fixture(row['input_case']);assert list(image.shape)==row['input_shape'] and str(image.dtype)==row['input_dtype'];return io.NodeOutput(image)
class AMY_Aux_AIO_Same_Runtime_Original_Consumer_R1(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw','assets')
    @classmethod
    def define_schema(cls):return io.Schema(node_id='AMY_Aux_AIO_Same_Runtime_Original_Consumer_R1',category='tests/controlnet_aux',is_output_node=True,inputs=[io.Image.Input('actual'),io.Image.Input('original_image'),io.String.Input('case')],outputs=[io.Image.Output('verified_native_image')])
    @classmethod
    async def execute(cls,actual,original_image,case):
        row=golden(case);wanted=input_fixture(row['input_case']);assert original_image.dtype==wanted.dtype and original_image.shape==wanted.shape and torch.equal(original_image.cpu(),wanted)
        frozen=zlib.decompress(base64.b64decode(row['tensor_zlib_base64'],validate=True));assert hashlib.sha256(frozen).hexdigest()==row['tensor_sha256']
        weight=MANGA if row['preprocessor']=='Manga2Anime_LineArt_Preprocessor' else (ANIME if row['preprocessor']=='AnimeLineArtPreprocessor' else None)
        if weight is not None:
            asset=await sdk.ctx().assets.resolve(weight.folder,weight.catalogue_name);assert await sdk.ctx().assets.digest(asset)==weight.sha256
            states={weight.filename:await sdk.ctx().assets.load_state_dict(asset)};manga.STATES=anime.STATES=states
        expected=original.AIO_Preprocessor().execute(row['preprocessor'],original_image,resolution=row['resolution'])[0]
        assert type(actual) is torch.Tensor and actual.dtype==expected.dtype and actual.shape==expected.shape and torch.equal(actual.cpu(),expected),case
        raw=expected.cpu().numpy().tobytes();host=torch.from_numpy(np.frombuffer(frozen,dtype=row['numpy_dtype']).copy()).reshape(row['shape']);assert torch.equal(actual.cpu(),host),case
        return io.NodeOutput(actual,ui={'text':[json.dumps({'case':case,'node_id':'AIO_Preprocessor','preprocessor':row['preprocessor'],'resolution':row['resolution'],'exact_genuine_original_same_runtime_whole_pixels':True,'shape':list(actual.shape),'dtype':str(actual.dtype),'same_runtime_original_tensor_sha256':hashlib.sha256(raw).hexdigest(),'immutable_one_thread_native_host_tensor_sha256':row['tensor_sha256'],'immutable_one_thread_native_host_tensor_equal':True,'original_input_shape':list(original_image.shape),'original_input_dtype':str(original_image.dtype),'torch_threads':torch.get_num_threads(),'no_thread_runtime_or_golden_mutation':True,'preview_qualified':row['preview'],'omitted_widget_defaults_requested':row.get('omit_widget_defaults_in_guest_graph',False),'reference_scope':'Literal pinned original AIO execute, selected original wrapper defaults, actual original Canny and genuine Manga/Anime state computations; exact raw FP16 passthrough; CPU device/reference acquisition/UI bindings only. GuestRNG/error/empty/other53selectedtargets and FP16PNG projection not qualified'})]})
class AIOExtension(MangaExtension):
    async def get_node_list(self):return await super().get_node_list()+[AMY_Aux_AIO_Native_Input_R1,AMY_Aux_AIO_Same_Runtime_Original_Consumer_R1]
async def comfy_entrypoint():return AIOExtension()
