import hashlib,json
from pathlib import Path
from comfy_api.latest import io,sdk

def checked_gate_selection():
    value=json.loads(Path(__file__).with_name('_midas_import_state_gate_selection.json').read_bytes())
    if value['approved'] is not True:
        raise RuntimeError('MiDaS import/original414 state gate is not admitted')
    if value['runtime_admission'] is not False or value['test_only'] is not True:
        raise ValueError('MiDaS import/state gate is TEST-only')
    if value['profile_sha256']!='f65ac4fee83b39cd5f7554dae1b3469eeaa4af72d6aa6a961dd422a0b6285a43' or value['lock_sha256']!='b6074c8236e480d939a828928bc91b6f21ab3877e02aff3512cf5b45bc9de0f5':
        raise ValueError('MiDaS exact canonical profile binding differs')
    for name in ['official_owned_profile_result_sha256','shared_profile_admission_receipt_sha256','verified_recovery_release_receipt_sha256','import_state_gate_admission_receipt_sha256']:
        if not isinstance(value.get(name),str) or len(value[name])!=64:
            raise ValueError('Actual required profile/release/gate receipt missing')
    return value

class AMY_Aux_MIDAS_Genuine_Imports_Original414_State_Gate_R1(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw','assets','models.download')
    SDK_REQUIRED_WEIGHTS=(sdk.HuggingFaceWeight(repo_id='Intel/dpt-hybrid-midas',filename='pytorch_model.bin',folder='controlnet',revision='11eaf7a1cf4bd70740697dbc216f98980c0aeb03',sha256='b6c4d44f9d96ca3fa76dd3bbb153989a60b4ad5526559f3c598562a368d687ec',on_demand=False),)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='AMY_Aux_MIDAS_Genuine_Imports_Original414_State_Gate_R1',category='tests/controlnet_aux',is_output_node=True,outputs=[io.Int.Output('original_state_members')])
    @classmethod
    async def execute(cls):
        selection=checked_gate_selection()
        import importlib.metadata,inspect
        import torch
        from transformers import DPTConfig,DPTImageProcessor,DPTForDepthEstimation
        from ._test_midas_original_state import validate_original_state
        assert importlib.metadata.version('transformers')=='5.12.1' and importlib.metadata.version('huggingface-hub')=='1.33.0' and importlib.metadata.version('tokenizers')=='0.22.2'
        assert issubclass(DPTForDepthEstimation,torch.nn.Module)
        before=hashlib.sha256(torch.get_rng_state().numpy().tobytes()).hexdigest()
        files={
            'config':(DPTConfig,'32fb4e584429e70dac1d0f74cc2bc88e16a975cf83d764f29ecc80201192409e'),
            'processor':(DPTImageProcessor,'f1984fc5e213e5aa0eee3c968904230c13f5da53914811bab3b986db304e3b12'),
            'model':(DPTForDepthEstimation,'97fab16082ad12cf0cd81ef214717ebfadb3613ec0e836401f18d70a3e49b2b0')}
        checked={}
        for name,(actual_class,digest) in files.items():
            file=Path(inspect.getfile(actual_class));assert hashlib.sha256(file.read_bytes()).hexdigest()==digest
            checked[name]={'class':actual_class.__module__+'.'+actual_class.__name__,'source_sha256':digest}
        assets=sdk.ctx().assets;asset=await assets.resolve('controlnet','huggingface/Intel/dpt-hybrid-midas/11eaf7a1cf4bd70740697dbc216f98980c0aeb03/pytorch_model.bin')
        assert await assets.size(asset)==489648389 and await assets.digest(asset)=='b6c4d44f9d96ca3fa76dd3bbb153989a60b4ad5526559f3c598562a368d687ec'
        state=await assets.load_state_dict(asset);validate_original_state(state,'raw')
        after=hashlib.sha256(torch.get_rng_state().numpy().tobytes()).hexdigest();assert before==after
        assert await assets.size(asset)==489648389 and await assets.digest(asset)=='b6c4d44f9d96ca3fa76dd3bbb153989a60b4ad5526559f3c598562a368d687ec'
        record={'phase':'genuine_guest_import_and_original414_reader_only','profile_sha256':selection['profile_sha256'],'lock_sha256':selection['lock_sha256'],'actual_genuine_DPT_classes':checked,'all_original_raw_state_tensor_keys_order_dtype_shape_metadata_bytes_exact':True,'original_state_members':len(state),'original_state_tensor_bytes':sum(v.numel()*v.element_size() for v in state.values()),'RNG_unchanged':before==after,'neural_model_constructed_or_forward_executed':False,'guest_image_parity_qualified':False,'accepted_delta':0}
        return io.NodeOutput(len(state),ui={'text':[json.dumps(record)]})

from .nodes import Extension
class MidasImportStateGateExtension(Extension):
    async def get_node_list(self):
        return await super().get_node_list()+[AMY_Aux_MIDAS_Genuine_Imports_Original414_State_Gate_R1]
async def comfy_entrypoint():
    return MidasImportStateGateExtension()
