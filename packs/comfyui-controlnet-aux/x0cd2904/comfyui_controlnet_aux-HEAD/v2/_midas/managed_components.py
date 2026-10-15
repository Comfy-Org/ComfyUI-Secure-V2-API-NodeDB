"""Private source proposal; no production activation or constructor parity claim."""
import hashlib,json
from pathlib import Path

def checked_selection():
    root=Path(__file__).parent
    selection=json.loads((root/'SELECTION.json').read_bytes())
    if selection['approved'] is not True:
        raise RuntimeError('MiDaS original first forward, compatible profile and guest/runtime/RAM proofs remain pending')
    if selection['runtime_admission'] is not False or selection['test_only'] is not True:
        raise ValueError('This draft supports only explicitly qualified original TEST selection')
    if selection['publisher_repo']!='Intel/dpt-hybrid-midas' or selection['publisher_revision']!='11eaf7a1cf4bd70740697dbc216f98980c0aeb03':
        raise ValueError('MiDaS genuine original source selection differs')
    if selection['weight_bytes']!=489648389 or selection['weight_sha256']!='b6c4d44f9d96ca3fa76dd3bbb153989a60b4ad5526559f3c598562a368d687ec':
        raise ValueError('MiDaS original weight byte identity differs')
    if not selection.get('native_constructor_receipt_sha256') or not selection.get('verified_current_runtime_receipt_sha256') or not selection.get('accepted_RAM_plan_receipt_sha256'):
        raise ValueError('Required actual native/runtime/RAM bindings missing')
    if not selection.get('profile_admission_receipt_sha256') or not selection.get('original_native_forward_receipt_sha256'):
        raise ValueError('Original forward and compatible profile receipt bindings missing')
    if selection.get('required_private_profile_sha256')!='f65ac4fee83b39cd5f7554dae1b3469eeaa4af72d6aa6a961dd422a0b6285a43' or selection.get('required_private_lock_sha256')!='b6074c8236e480d939a828928bc91b6f21ab3877e02aff3512cf5b45bc9de0f5':
        raise ValueError('Compatible original framework profile identity differs')
    for name in ['genuine_guest_import_original414_reader_receipt_sha256','learned_model_TEST_admission_receipt_sha256']:
        if not isinstance(selection.get(name),str) or len(selection[name])!=64:
            raise ValueError('Actual genuine reader and learned TEST scheduling receipt bindings missing')
    config=(root/'config.json').read_bytes();processor=(root/'preprocessor_config.json').read_bytes()
    if hashlib.sha256(config).hexdigest()!='d469783f4a0bbfdbdafb9af7b193480ce9d87c5687984056ccc3738e5367ca66' or hashlib.sha256(processor).hexdigest()!='4da22e615634b6316e2564136943b8550ebaa77d4e300004e8a7e99c92b68c6a':
        raise ValueError('Original exact config/processor bytes differ')
    return selection,json.loads(config),json.loads(processor)

async def construct_components():
    selection,config_data,processor_data=checked_selection()
    # Every scientific import and real SDK operation follows the explicit guard.
    import importlib.metadata
    import torch
    from comfy_api.latest import sdk
    from transformers import DPTConfig,DPTImageProcessor,DPTForDepthEstimation
    if importlib.metadata.version('transformers')!='5.12.1':
        raise RuntimeError('Source-inspected original constructor version differs')
    assets=sdk.ctx().assets
    asset=await assets.resolve('controlnet',selection['catalogue_name'])
    if await assets.size(asset)!=selection['weight_bytes'] or await assets.digest(asset)!=selection['weight_sha256']:
        raise ValueError('Actual unchanged original selected managed weight differs')
    state=await assets.load_state_dict(asset)
    validate_native_state(state,selection['native_state_contract'])
    config=DPTConfig.from_dict(config_data)
    processor=DPTImageProcessor.from_dict(processor_data)
    # The actual published constructor permits None + supplied config/state.
    # Its genuine initialization, loading and evaluation implementation remains authoritative.
    model=DPTForDepthEstimation.from_pretrained(None,config=config,state_dict=state,local_files_only=True)
    if type(model) is not DPTForDepthEstimation or type(processor) is not DPTImageProcessor or model.training:
        raise ValueError('Genuine original DPT component/evaluation identity differs')
    validate_native_state(model.state_dict(),selection['native_loaded_state_contract'])
    if await assets.size(asset)!=selection['weight_bytes'] or await assets.digest(asset)!=selection['weight_sha256']:
        raise ValueError('Original managed asset identity changed during construction')
    return processor,model

def validate_native_state(state,census):
    import torch
    if not isinstance(state,dict) or not census or list(state)!=[row['key'] for row in census['ordered_tensors']]:
        raise ValueError('Original native exact ordered state keys differ')
    if hasattr(state,'_metadata')!=census['has_metadata_attribute'] or getattr(state,'_metadata',None)!=census['metadata']:
        raise ValueError('Original native exact state metadata differs')
    total=0
    for row in census['ordered_tensors']:
        value=state[row['key']]
        if not isinstance(value,torch.Tensor) or value.device.type!='cpu' or value.layout!=torch.strided or str(value.dtype)!=row['dtype'] or list(value.shape)!=row['shape']:
            raise ValueError('Original native exact CPU state dtype/shape differs')
        count=value.numel()*value.element_size()
        if count!=row['bytes'] or hashlib.sha256(value.detach().cpu().contiguous().numpy().tobytes()).hexdigest()!=row['sha256']:
            raise ValueError('Original native exact tensor byte digest differs')
        total+=count
    if len(state)!=414 or total!=census['tensor_bytes'] or total!=489511940 or total>512*1024*1024:
        raise ValueError('Original native exact state materialization bound differs')
