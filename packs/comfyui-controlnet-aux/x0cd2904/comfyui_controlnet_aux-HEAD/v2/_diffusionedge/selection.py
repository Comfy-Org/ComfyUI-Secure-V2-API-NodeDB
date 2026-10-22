"""Real sealed bytes and restricted CPU container decoding; selection unissued."""
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import io
import json
from pathlib import Path
import re

PIN='0cd290477128d42cdc3e76a826a402d866e8c684'
REPO='hr16/Diffusion-Edge'
MAX_TOTAL_BYTES=2*1024*1024*1024
CURRENT=ContextVar('diffusion_edge_sealed_construction',default=None)
AUTHORITIES=('dependency_setup','torch_restricted_reader','raw_nested_container_storage_metadata','yaml_config',
             'device_policy','current_invocation','exclusive_global_rng_config_lifetime','image_realm','finite_patch_workspace',
             'pretrained_auxiliary_resources','vendor_source_abi','published_asset_read_limit_correspondence')

def sha(value):return hashlib.sha256(value).hexdigest()
def is_sha(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None

def validate_selection(item):
    if item.get('approved') is not True:
        raise RuntimeError('DiffusionEdge nested checkpoint/auxiliary resources/vendor/global lifetime selection pending')
    if item.get('format')!='amy-diffusionedge-managed-selection/1' or item.get('source_pin')!=PIN:
        raise RuntimeError('DiffusionEdge original source unselected')
    if any(not is_sha(item.get('authority',{}).get(k)) for k in AUTHORITIES):
        raise RuntimeError('DiffusionEdge actual setup/raw storage/vendor/YAML/RNG/workspace authority missing')
    if type(item.get('device')) is not str or not re.fullmatch(r'cpu|mps|cuda(?::[0-9]+)?',item['device']):
        raise RuntimeError('DiffusionEdge real device unselected')
    # The restricted-globals proofs use private torch APIs (get_globals_in_pkl, the default allowlist): the selection pins
    # the torch build they were inspected on, and restricted_checkpoint refuses any other.
    if type(item.get('torch_runtime_version')) is not str or not item['torch_runtime_version']:
        raise RuntimeError('DiffusionEdge restricted decode torch runtime version is unselected')
    if item.get('environment') not in ('indoor','urban','natrual'):
        raise RuntimeError('DiffusionEdge exact source environment unselected')
    if item.get('main_cpu_weights_only_correspondence') is not True or item.get('auxiliary_saved_cpu_storage_correspondence') is not True:
        raise RuntimeError('DiffusionEdge actual restricted CPU native decode correspondence missing')
    resources=item.get('resources',{})
    if set(resources)!= {'main','vgg16','lpips','swin_b'}:
        raise RuntimeError('DiffusionEdge default construction requires main/VGG16/LPIPS/Swin resources')
    total=0
    for key,r in resources.items():
        if r.get('approved') is not True or not all(is_sha(r.get(k)) for k in ('sha256','raw_structure_sha256','raw_container_evidence_sha256','saved_cpu_storage_evidence_sha256')):
            raise RuntimeError('DiffusionEdge actual immutable raw resource evidence missing')
        # Bounded by the total budget only: the pinned main checkpoint is about 1.19 GB, and resources are read in
        # bounded read_range chunks (the 64 MiB guest cap on whole-asset reads does not apply).
        if type(r.get('bytes')) is not int or not 0<r['bytes']<=MAX_TOTAL_BYTES:
            raise RuntimeError('DiffusionEdge actual bounded resource bytes missing')
        if type(r.get('tensor_bytes')) is not int or not 0<r['tensor_bytes']<=MAX_TOTAL_BYTES:
            raise RuntimeError('DiffusionEdge actual CPU tensor materialization missing')
        if not all(type(r.get(k)) is str and r[k] for k in ('folder','catalogue_name','publisher','filename','revision')):
            raise RuntimeError('DiffusionEdge genuine sealed resource/provenance missing')
        # The per-archive restricted-globals proof is pinned with the selection and checked here, before any vendor
        # import or asset read: the archive format and the exact sorted global list from the inspection.
        pinned=r.get('pickle_globals')
        if r.get('archive_format') not in ('zip','legacy') or type(pinned) is not list or not pinned or any(type(g) is not str or not g for g in pinned) or pinned!=sorted(set(pinned)):
            raise RuntimeError('DiffusionEdge restricted decode archive format/pinned pickle globals are unselected')
        total+=r['bytes']
    if total>MAX_TOTAL_BYTES:raise RuntimeError('DiffusionEdge sealed resource buffer budget exceeded')
    if resources['main']['publisher']!=REPO or resources['main']['filename']!=f"diffusion_edge_{item['environment']}.pt":
        raise RuntimeError('DiffusionEdge native main filename/repository differs')
    for k,name in (('vgg16','vgg16-397923af.pth'),('swin_b','swin_b-68c6b09e.pth'),('lpips','vgg.pth')):
        if resources[k]['filename']!=name:raise RuntimeError('DiffusionEdge native auxiliary filename differs')
    return item

def require_selected_torch(item):
    # The restricted-globals proofs rely on private torch APIs, so the running torch build must be the selected one. It is
    # compared before the sealed reads and the model build (review Low-3), and again at each decode.
    import torch
    if torch.__version__!=item['torch_runtime_version']:
        raise RuntimeError('DiffusionEdge restricted decode torch runtime differs from the selected version')

def selected_construction(environment):
    item=json.loads(Path(__file__).with_name('asset-selection.json').read_text())
    if item.get('approved') is not True:
        raise RuntimeError('DiffusionEdge nested checkpoint/auxiliary resources/vendor/global lifetime selection pending')
    if environment not in item['environments']:raise RuntimeError('DiffusionEdge actual environment resource unselected')
    item=dict(item,environment=environment,resources=item['environments'][environment])
    validate_selection(item)
    closure=json.loads(Path(__file__).with_name('source-closure.json').read_text())
    for row in closure['records']:
        if sha((Path(__file__).parent/row['result']).read_bytes())!=row['result_sha256']:
            raise RuntimeError('DiffusionEdge actual private source/config closure differs')
    return item

async def sealed_buffers(item):
    validate_selection(item)
    require_selected_torch(item)
    from comfy_api.latest import sdk
    from .._sealed_asset_read import read_sealed_asset
    assets=sdk.ctx().assets;out={}
    for key in ('vgg16','lpips','swin_b','main'):
        r=item['resources'][key];ref=await assets.resolve(r['folder'],r['catalogue_name'])
        if await assets.size(ref)!=r['bytes'] or await assets.digest(ref,'sha256')!=r['sha256']:
            raise RuntimeError('DiffusionEdge immutable resource size/digest differs')
        blob=await read_sealed_asset(assets,ref,r['bytes'],r['sha256'])
        if type(blob) is not bytes or len(blob)!=r['bytes'] or sha(blob)!=r['sha256']:
            raise RuntimeError('DiffusionEdge actual sealed buffer differs')
        out[key]=blob
    return out

@contextmanager
def construction(item,buffers):
    try:
        validate_selection(item)
        if CURRENT.get() is not None:raise RuntimeError('DiffusionEdge nested construction lifetime unsupported')
        token=CURRENT.set((item,buffers))
        try:yield
        finally:CURRENT.reset(token)
    finally:
        # Review Low-4: release every sealed buffer still held (after a refusal, or a resource never decoded) when the
        # construction ends.
        buffers.clear()

def restricted_checkpoint(key):
    current=CURRENT.get()
    if current is None:raise RuntimeError('DiffusionEdge checkpoint read outside approved construction')
    item,buffers=current;validate_selection(item)
    if key not in buffers:raise RuntimeError('DiffusionEdge optional native checkpoint/resource unselected')
    blob=buffers[key]
    if blob is None:raise RuntimeError('DiffusionEdge sealed resource already decoded; each resource is read once')
    # Release the sealed bytes with this single decode (peak memory); the decoded value is checked below.
    buffers[key]=None
    # ComfyUI registers extra torch safe globals at import, so the decode may resolve only this archive's pinned,
    # default-allowlisted globals: zip archives through _restricted_globals, legacy archives through _restricted_legacy_globals.
    record=item['resources'][key]
    import torch
    require_selected_torch(item)
    # Review Low-1: torch.load picks the zip route from the first four bytes alone, so the pinned format must match them.
    if (blob[:4]==b'PK\x03\x04')!=(record['archive_format']=='zip'):
        raise RuntimeError('DiffusionEdge restricted decode archive format differs from the selected format')
    if record['archive_format']=='zip':
        from .._restricted_globals import require_default_allowlisted
        require_default_allowlisted(blob,record['pickle_globals'])
    else:
        from .._restricted_legacy_globals import require_default_allowlisted_legacy
        require_default_allowlisted_legacy(blob,record['pickle_globals'])
    # Exact physically bound Torch reader source; no safe-global additions,
    # raw host path, default pickle, flattening, synthesized model or EMA map.
    value=torch.load(io.BytesIO(blob),map_location='cpu',weights_only=True)
    del blob
    structure,total=raw_structure(value,torch)
    if sha(json.dumps(structure,sort_keys=True,separators=(',',':')).encode())!=record['raw_structure_sha256'] or total!=record['tensor_bytes'] or total>MAX_TOTAL_BYTES:
        raise RuntimeError('DiffusionEdge actual raw nested metadata/storage structure differs')
    return value

def raw_structure(value,torch):
    """The restricted primitive/Tensor container description and its CPU tensor bytes (also used by the inspection step)."""
    storages={};total=0;count=0
    def describe(v,depth=0):
        nonlocal total,count
        count+=1
        if count>200000 or depth>64:raise RuntimeError('DiffusionEdge raw primitive container exceeds bounded work')
        if type(v) is torch.Tensor:
            if v.device.type!='cpu' or v.layout!=torch.strided or v.is_quantized or v.is_complex():
                raise RuntimeError('DiffusionEdge raw state requires real dense saved CPU tensors')
            total+=v.numel()*v.element_size()
            storage=v.untyped_storage();identity=storage._cdata
            if identity not in storages:storages[identity]=len(storages)
            return dict(kind='Tensor',shape=list(v.shape),dtype=str(v.dtype),stride=list(v.stride()),offset=v.storage_offset(),storage_alias=storages[identity],storage_bytes=storage.nbytes())
        if type(v) in (dict,OrderedDict):
            if any(type(k) is not str for k in v):raise RuntimeError('DiffusionEdge checkpoint requires primitive string keys')
            row=dict(kind=type(v).__name__,entries=[[k,describe(x,depth+1)] for k,x in v.items()])
            if hasattr(v,'_metadata'):row['native_state_metadata']=describe(v._metadata,depth+1)
            return row
        if type(v) in (list,tuple):return dict(kind=type(v).__name__,items=[describe(x,depth+1) for x in v])
        if v is None or type(v) in (str,int,float,bool):return dict(kind=type(v).__name__,value=v)
        raise RuntimeError('DiffusionEdge restricted primitive/Tensor container contract unsupported')
    structure=describe(value)
    return structure,total

def private_module_name(module_name):
    prefix='custom_controlnet_aux.diffusion_edge'
    root=__package__
    if module_name==prefix or module_name.startswith(prefix+'.'):
        return root+module_name[len(prefix):]
    if module_name=='taming' or module_name.startswith('taming.'):
        return root+'.'+module_name
    raise RuntimeError('DiffusionEdge dynamic vendor target outside selected private source unsupported')
