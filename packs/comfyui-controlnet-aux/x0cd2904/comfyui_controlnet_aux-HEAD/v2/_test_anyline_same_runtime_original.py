import base64,hashlib,json,types
import numpy as np
import torch
from comfy_api.latest import io,sdk
from ._test_anyline_downstream import TestExtension,golden
from ._anyline import REQUIRED_WEIGHTS
from ._test_original_anyline import _native_mteed_reference as ted,_native_lineart_reference as line,_native_anime_reference as anime,_native_manga_reference as manga
from ._test_original_anyline._native_anyline_reference import native_anyline
class AMY_Aux_AnyLine_Same_Runtime_Original_Consumer_R1(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw','assets')
    @classmethod
    def define_schema(cls):return io.Schema(node_id='AMY_Aux_AnyLine_Same_Runtime_Original_Consumer_R1',category='tests/controlnet_aux',is_output_node=True,inputs=[io.Image.Input('actual'),io.Image.Input('original_image'),io.String.Input('case')],outputs=[io.Image.Output('verified_native_image')])
    @classmethod
    async def execute(cls,actual,original_image,case):
        g=golden(case);frozen=base64.b64decode(g['tensor_base64'],validate=True);assert hashlib.sha256(frozen).hexdigest()==g['tensor_sha256']
        mode=g['controls']['merge_with_lineart'];filenames=['Anyline/MTEED.pth']
        if mode=='lineart_realisitic':filenames+=['sk_model.pth','sk_model2.pth']
        elif mode=='lineart_anime':filenames+=['netG.pth']
        elif mode=='manga_line':filenames+=['erika.pth']
        states={}
        for declaration in REQUIRED_WEIGHTS:
            if declaration.filename not in filenames:continue
            asset=await sdk.ctx().assets.resolve(declaration.folder,declaration.catalogue_name);assert await sdk.ctx().assets.digest(asset)==declaration.sha256
            states[declaration.filename.rsplit('/',1)[-1]]=await sdk.ctx().assets.load_state_dict(asset)
        # Preserve native detector order, constructor count and byte-identical
        # computation; replace only factory acquisition with genuine SDK states.
        for module in (ted,line,anime,manga):module.STATES=states
        expected=native_anyline(types.SimpleNamespace(device='cpu'),original_image,**g['controls'])[0]
        if type(actual) is not torch.Tensor or actual.shape!=expected.shape or actual.dtype!=expected.dtype or not torch.equal(actual.cpu(),expected):raise AssertionError('AnyLine genuine original same-runtime whole-tensor mismatch: '+case)
        raw=expected.cpu().numpy().tobytes();legacy=torch.from_numpy(np.frombuffer(frozen,dtype='<f4').copy()).reshape(g['shape'])
        return io.NodeOutput(actual,ui={'text':[json.dumps({'case':case,'node_id':'AnyLineArtPreprocessor_aux','exact_genuine_original_same_runtime_whole_pixels':True,'shape':list(actual.shape),'dtype':str(actual.dtype),'same_runtime_original_tensor_sha256':hashlib.sha256(raw).hexdigest(),'immutable_four_thread_golden_sha256':g['tensor_sha256'],'immutable_four_thread_golden_equal':torch.equal(actual.cpu(),legacy),'torch_threads':torch.get_num_threads(),'native_controls':g['controls'],'no_thread_runtime_or_golden_mutation':True,'reference_scope':'Original AnyLine mathematical computation and all detector/network/batch helpers preserved; only native progress construction uses a local reference counter, host UI progress not qualified; selected original SDK states in identical unmodified guest context; four merge modes, HWC morphology and manga rounding retained'})]})
class ReferenceExtension(TestExtension):
    async def get_node_list(self):return await super().get_node_list()+[AMY_Aux_AnyLine_Same_Runtime_Original_Consumer_R1]
async def comfy_entrypoint():return ReferenceExtension()
