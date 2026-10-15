import base64,hashlib,json
from pathlib import Path
import numpy as np
import torch
from comfy_api.latest import ComfyExtension,io
from ._anyline_native_fixture_inputs import fixture
def golden(case):return next(r for r in json.loads(Path(__file__).with_name('_anyline_native_goldens.json').read_text())['cases'] if r['case']==case)
class AMY_Aux_AnyLine_Fixture_Producer_R1(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):return io.Schema(node_id='AMY_Aux_AnyLine_Fixture_Producer_R1',category='tests/controlnet_aux',inputs=[io.String.Input('case')],outputs=[io.Image.Output('image')])
    @classmethod
    def execute(cls,case):
        r=golden(case)
        if r['input_case']=='nested256':
            image=torch.ones((1,256,256,3));image[:,48:208,48:208,:]=0;image[:,80:176,80:176,:]=1;image[:,:,126:130,:]=0
        else:image=fixture(r['input_case'])
        return io.NodeOutput(image)
class AMY_Aux_AnyLine_Strict_Native_Consumer_R1(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):return io.Schema(node_id='AMY_Aux_AnyLine_Strict_Native_Consumer_R1',category='tests/controlnet_aux',is_output_node=True,inputs=[io.Image.Input('actual'),io.String.Input('case')],outputs=[io.Image.Output('verified_native_image')])
    @classmethod
    def execute(cls,actual,case):
        r=golden(case);raw=base64.b64decode(r['tensor_base64'],validate=True)
        if hashlib.sha256(raw).hexdigest()!=r['tensor_sha256']:raise AssertionError('Original AnyLine golden identity differs')
        expected=torch.from_numpy(np.frombuffer(raw,dtype='<f4').copy()).reshape(r['shape'])
        if type(actual) is not torch.Tensor or actual.shape!=expected.shape or actual.dtype!=expected.dtype or not torch.equal(actual.cpu(),expected):raise AssertionError('AnyLine original whole-pixel/dtype/shape mismatch: '+case)
        return io.NodeOutput(actual,ui={'text':[json.dumps({'case':case,'node_id':r['node_id'],'exact_native_whole_pixels':True,'shape':list(actual.shape),'dtype':str(actual.dtype),'scope':'Actual registered production model -> strict typed IMAGE consumer, only after genuine normal model-capable registration','native_tensor_sha256':r['tensor_sha256']})]})
class TestExtension(ComfyExtension):
    async def get_node_list(self):
        from .nodes import Extension
        return await Extension().get_node_list()+[AMY_Aux_AnyLine_Fixture_Producer_R1,AMY_Aux_AnyLine_Strict_Native_Consumer_R1]
async def comfy_entrypoint():return TestExtension()
