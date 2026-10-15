"""Source-bound native model-key correspondence through published Assets."""
import hashlib
import json
from pathlib import Path
import re

PIN='0cd290477128d42cdc3e76a826a402d866e8c684'
REPO='hr16/Unimatch'
FILENAMES=('gmflow-scale1-mixdata.pth','gmflow-scale2-mixdata.pth','gmflow-scale2-regrefine6-mixdata.pth')
MAX_BYTES=512*1024*1024


def is_sha(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


PROOF='metadata-equivalence-proof.json'


def metadata_equivalence_proof(r):
    """Recorded proof that, for THIS checkpoint sha256 only, the original UniMatch
    loaded with and without the state's _metadata has identical state and outputs.
    Any other checkpoint, revision, proof byte or source pin is refused."""
    if not is_sha(r.get('metadata_equivalence_proof_sha256')):
        raise RuntimeError('UniMatch native state _metadata present without a recorded per-checkpoint equivalence proof')
    try:
        raw=Path(__file__).with_name(PROOF).read_bytes()
    except OSError:
        raise RuntimeError('UniMatch recorded _metadata equivalence proof missing') from None
    if hashlib.sha256(raw).hexdigest()!=r['metadata_equivalence_proof_sha256']:
        raise RuntimeError('UniMatch recorded _metadata equivalence proof differs')
    proof=json.loads(raw)
    c=proof.get('checkpoint') if type(proof) is dict else None
    m=proof.get('metadata') if type(proof) is dict else None
    if (type(c) is not dict or type(m) is not dict or proof.get('kind')!='UNIMATCH_METADATA_EQUIVALENCE_PROOF'
            or proof.get('upstream_source_pin')!=PIN or c.get('sha256')!=r['sha256'] or c.get('bytes')!=r['bytes']
            or c.get('repo')!=r['source_repo'] or c.get('file')!=r['source_filename'] or c.get('revision')!=r['revision']
            or m.get('present') is not True or proof.get('state_dict_identical') is not True
            or proof.get('forward_outputs_identical') is not True or proof.get('state_tensors')!=len(r['model_state_records'])
            or not is_sha(proof.get('with_metadata_state_sha256'))
            or proof.get('with_metadata_state_sha256')!=proof.get('without_metadata_state_sha256')
            or type(proof.get('torch')) is not str):
        raise RuntimeError('UniMatch recorded _metadata equivalence proof does not cover this exact checkpoint')
    return proof


def validate_selection(item):
    if item.get('approved') is not True:
        raise RuntimeError('UniMatch checkpoint model-key/vendor/device/flow-lifetime selection pending')
    if item.get('format')!='amy-unimatch-managed-selection/1' or item.get('source_pin')!=PIN:
        raise RuntimeError('UniMatch original source unselected')
    for key in ('runtime_abi','restricted_reader_policy','native_model_key_correspondence','shared_config_namespace_lifetime',
                'device_policy','current_invocation','typed_flow_image_realm','finite_flow_workspace','projected_state_metadata_correspondence'):
        if not is_sha(item.get('authority',{}).get(key)):
            raise RuntimeError('UniMatch actual reader/vendor/device/config/flow workspace evidence missing')
    if type(item.get('device')) is not str or not re.fullmatch(r'cpu|mps|cuda(?::[0-9]+)?',item['device']):
        raise RuntimeError('UniMatch actual to-device unselected')
    r=item['resource']
    if r.get('approved') is not True or r.get('source_repo')!=REPO or r.get('source_filename') not in FILENAMES:
        raise RuntimeError('UniMatch exact immutable native checkpoint unselected')
    for k in ('sha256','raw_container_evidence_sha256','projected_model_state_evidence_sha256','cpu_storage_evidence_sha256'):
        if not is_sha(r.get(k)):raise RuntimeError('UniMatch actual raw/model/storage correspondence missing')
    if type(r.get('revision')) is not str or not re.fullmatch('[0-9a-f]{40}',r['revision']):
        raise RuntimeError('UniMatch exact publisher revision unselected')
    for k in ('folder','catalogue_name'):
        if type(r.get(k)) is not str or not r[k]:raise RuntimeError('UniMatch sealed resource unselected')
    if type(r.get('bytes')) is not int or not 0<r['bytes']<=MAX_BYTES or type(r.get('tensor_bytes')) is not int or not 0<r['tensor_bytes']<=MAX_BYTES:
        raise RuntimeError('UniMatch bounded actual resource/state count missing')
    keys=r.get('raw_top_level_keys')
    if type(keys) is not list or any(type(k) is not str for k in keys) or len(set(keys))!=len(keys) or 'model' not in keys or 'state_dict' in keys:
        raise RuntimeError('UniMatch raw model container cannot correspond to state_dict-prioritized projection')
    expected='singleton_model' if keys==['model'] else 'retained_multi_key_model'
    if r.get('reader_disposition')!=expected or r.get('native_model_is_mapping') is not True:
        raise RuntimeError('UniMatch actual reader single-child/multi-key policy unproved')
    # The canonical guest transport exports/imports a tensor per TOP-LEVEL
    # key. A retained nested model mapping is not a tensor handle. Refuse
    # that complete raw layout before RPC rather than inventing flattening.
    if expected!='singleton_model':
        raise RuntimeError('UniMatch multi-key raw model container unsupported by published tensor-only transport')
    records=r.get('model_state_records')
    if type(records) is not list or not records or any(type(v) is not dict or type(v.get('key')) is not str for v in records):
        raise RuntimeError('UniMatch actual ordered state tensor records unselected')
    if len({v['key'] for v in records})!=len(records):raise RuntimeError('UniMatch repeated selected model state key')
    # The transport must not silently lose native model state version metadata.
    # Absent metadata needs nothing more. Present metadata is accepted ONLY with
    # the recorded proof for this exact checkpoint sha256 (nothing generic).
    present=r.get('native_model_state_metadata_present')
    if present is True:
        metadata_equivalence_proof(r)
    elif present is not False:
        raise RuntimeError('UniMatch native state _metadata transport correspondence unsupported')
    return r


def selected_checkpoint(filename):
    item=json.loads(Path(__file__).with_name('asset-selection.json').read_text())
    if item.get('approved') is not True:
        raise RuntimeError('UniMatch checkpoint model-key/vendor/device/flow-lifetime selection pending')
    if filename not in FILENAMES:raise RuntimeError('UniMatch actual source filename selection pending')
    item=dict(item,resource=item['resources'][filename])
    validate_selection(item)
    closure=json.loads(Path(__file__).with_name('source-closure.json').read_text())
    for row in closure['records']:
        if hashlib.sha256((Path(__file__).parent/row['result']).read_bytes()).hexdigest()!=row['result_sha256']:
            raise RuntimeError('UniMatch exact private source closure differs')
    helper=Path(__file__).parent.parent/'_flow_mask.py'
    if hashlib.sha256(helper.read_bytes()).hexdigest()!=closure['reused_flow_helper_sha256']:
        raise RuntimeError('UniMatch actual shared color/mutation helper differs')
    return item


async def selected_resource(item,repo,filename):
    r=validate_selection(item)
    if (repo,filename)!=(r['source_repo'],r['source_filename']):
        raise RuntimeError('UniMatch constructor repo/filename differs')
    from comfy_api.latest import sdk
    assets=sdk.ctx().assets
    ref=await assets.resolve(r['folder'],r['catalogue_name'])
    if await assets.size(ref)!=r['bytes'] or await assets.digest(ref,'sha256')!=r['sha256']:
        raise RuntimeError('UniMatch actual sealed checkpoint size/digest differs')
    return ref


async def read_checkpoint(ref,item):
    validate_selection(item)
    from comfy_api.latest import sdk
    # Actual canonical restricted reader. Construction occurs BEFORE this RPC,
    # exactly where native torch.load(map_location=cpu) originally happened.
    return await sdk.ctx().assets.load_state_dict(ref)


def model_state(projected,item):
    r=validate_selection(item)
    state=projected
    if r.get('native_model_state_metadata_present') is True:
        # validate_selection bound the recorded per-checkpoint proof. Both routes
        # load the metadata-free state that proof compared (the guest transport
        # already delivers it). The proof was recorded under one torch build; its
        # version-dependent loaders are proven only there.
        import torch
        if str(torch.__version__)!=metadata_equivalence_proof(r)['torch']:
            raise RuntimeError('UniMatch _metadata equivalence proof was recorded under a different torch build')
        if isinstance(state,dict) and hasattr(state,'_metadata'):
            state=dict(state)
    if not isinstance(state,dict) or list(state)!=[v['key'] for v in r['model_state_records']] or hasattr(state,'_metadata'):
        raise RuntimeError('UniMatch native model state key/order/metadata correspondence differs')
    import torch
    total=0
    for (key,value),record in zip(state.items(),r['model_state_records']):
        if type(value) is not torch.Tensor or value.device.type!='cpu' or value.layout!=torch.strided or value.is_quantized or value.is_complex():
            raise RuntimeError('UniMatch requires actual selected dense real CPU state tensors')
        if list(value.shape)!=record['shape'] or str(value.dtype)!=record['dtype']:
            raise RuntimeError('UniMatch actual selected state tensor shape/dtype differs')
        total+=value.numel()*value.element_size()
    if total!=r['tensor_bytes'] or total>MAX_BYTES:raise RuntimeError('UniMatch actual state materialization differs')
    return state
